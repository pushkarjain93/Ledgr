"""
Isolated Gemini (Google AI) client for Ledgr's AI Forensic Agent.

Talks to Google's real Generative Language API using GEMINI_API_KEY from
the environment. Same pattern as razorpay_client.py: raw REST calls (via
requests, not a vendor SDK), isolated module, one-directional and
swappable -- nothing outside this file knows or cares which provider
sits behind it.

Batched by design: investigate_batch() sends several independent cases in
ONE request and gets one structured result per case back, keyed by
case_id. This exists specifically because a free-tier API quota caps
REQUEST COUNT (RPM/RPD), not token volume -- batching 5 cases into one
call is a ~5x reduction in requests for the same amount of reasoning.
See CLAUDE.md's "batched AI architecture" session note.

The model NEVER computes a number. Every function here hands the model
facts that deterministic code has ALREADY worked out; the model's only
job is judgement -- classify, explain, and recommend, using only what
it's given.
"""
import json
import os
import re
import threading
import time

import requests
from dotenv import load_dotenv

# Loads GEMINI_API_KEY from a local .env file (see .env.example) into
# os.environ, if present -- same mechanism razorpay_client.py already uses.
load_dotenv()

API_URL_TMPL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MODEL = "gemini-3.6-flash"
TIMEOUT_SECONDS = 60  # batched multi-case responses take longer to generate than a single-case call
DEFAULT_BATCH_SIZE = 5

# --------------------------------------------------------------------------
# Provider failover
#
# Ledgr talks to several LLM providers in a fixed order and moves to the next
# one when the current provider is rate-limited or erroring. This is genuine
# resilience, not quota farming: each provider is a separate account with its
# own independent limits, which is how production systems avoid a single
# vendor's cap becoming a single point of failure.
#
# Providers are OPTIONAL -- one with no key configured is skipped silently, so
# this file works unchanged whether one key is set or all of them.
#
# CRITICAL: if every provider fails, the original AIRateLimitError still
# propagates so callers fall back to the honest `ai_pending` state. Failover
# adds capacity; it must never remove the "AI genuinely could not look at this"
# path, because that honesty is what makes the verdicts trustworthy.
# --------------------------------------------------------------------------
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# A ":free" model on purpose, NOT a paid one.
#
# OpenRouter reserves max_tokens against your CREDIT BALANCE before running
# anything, so a paid model on a nearly-empty free-tier account fails with a
# 402 on every single request -- a permanent death, not a transient limit.
# That is exactly what happened with the previous default
# (google/gemini-2.5-flash): the account could "only afford 2558" tokens while
# we asked for 3000, so OpenRouter never once served as failover and every
# overflow case fell to ai_pending.
#
# A ":free" model costs 0 credits, so nothing is reserved and no balance can
# run out. Verified against the alternatives before choosing:
#   nvidia/nemotron-3-super-120b-a12b:free  honours json_schema exactly, ~4.8s
#   minimax/minimax-m2.7:free               IGNORED the schema -- wrapped the
#                                           reply in a markdown fence and
#                                           renamed the keys. Unusable here.
# Free models are billed nothing but are flakier upstream (see the embedded
# -error handling in _openai_compatible_generate), which is acceptable for a
# failover tier whose whole job is to catch Groq's overflow.
OPENROUTER_MODEL = os.environ.get(
    "OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")

# OpenRouter accepts a `models` array (MAXIMUM 3 -- a 4th is a hard 400) and
# routes to the first one actually serving right now. Free models are hosted on
# spare capacity and genuinely do go down: nemotron returned "Service
# temporarily overloaded" mid-testing, which without a backup means the whole
# failover tier is dead for that request.
#
# The backups are strictly a last resort and are NOT equally trustworthy -- one
# observed attempt fell through to a weaker model that ignored json_schema and
# replied with prose. That is safe here only because a non-JSON reply is
# REJECTED by the parser and fails over to Gemini; a schema violation must
# never be coerced into a verdict. Ordered best-first.
OPENROUTER_FALLBACK_MODELS = [
    m.strip() for m in os.environ.get(
        "OPENROUTER_FALLBACK_MODELS",
        "z-ai/glm-5.2:free,google/gemma-4-31b-it:free").split(",") if m.strip()
]

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")

# Groq's free tier caps TOKENS PER MINUTE (8000), and the reservation counts
# prompt + max_tokens TOGETHER, across all in-flight requests.
#
# Sized from a real measurement, not a guess: a 5-case batched investigation
# prompt is ~1010 tokens (system prompt ~570 + ~90/case). So each request
# reserves 1010 + GROQ_MAX_TOKENS, and MAX_CONCURRENT_BATCHES of them must fit
# under 8000:
#
#     2 x (1010 + 2200) = 6420   <- headroom
#     2 x (1010 + 3000) = 8020   <- the old value: 20 tokens OVER the ceiling
#
# That 20-token overshoot meant the FIRST pair of concurrent chunks was always
# refused with a 429, which then tripped the provider cooldown and pushed every
# remaining chunk onto failover. A measured 5-case response is ~1.5k tokens, so
# 2200 still leaves room to finish. Do not raise this without re-checking the
# arithmetic above against MAX_CONCURRENT_BATCHES.
GROQ_MAX_TOKENS = int(os.environ.get("GROQ_MAX_TOKENS", "2200"))

# Free OpenRouter models reserve no credit, so this only needs to be large
# enough to actually finish a 5-case answer. Nemotron spends most of its
# completion budget on reasoning tokens (257 of 276 on a trivial probe), so it
# needs more headroom than the token-per-minute-constrained Groq path.
# If OPENROUTER_MODEL is ever pointed back at a PAID model, this becomes a
# credit reservation again -- _openai_compatible_generate self-heals from the
# resulting 402 by retrying once at whatever the account can afford.
OPENROUTER_MAX_TOKENS = int(os.environ.get("OPENROUTER_MAX_TOKENS", "4000"))

# Order matters: first configured provider wins, later ones are failover.
#
# Ordered by MEASURED latency on an identical 5-case batched investigation,
# not by preference. Gemini's direct endpoint was by far the slowest and also
# has the tightest daily cap, so it moved from first to last:
#
#   groq       (gpt-oss-20b)        ~1.9s   <- primary, by far the fastest
#   openrouter (gemini-2.5-flash)   ~6.5s   <- failover
#   gemini     (gemini-3.6-flash)  ~20.8s   <- slowest + 20/day cap, last resort
#
# Groq's free tier limits TOKENS PER MINUTE (8000) rather than request count,
# so GROQ_MAX_TOKENS x MAX_CONCURRENT_BATCHES must stay under that ceiling --
# see GROQ_MAX_TOKENS. Within that budget it is roughly 3x faster than the
# alternatives, which is what a user waiting on the Sync button actually feels.
PROVIDER_ORDER = ("groq", "openrouter", "gemini")

# How many batched investigation requests may be in flight at once. Chunks are
# fully independent (each carries its own cases), so running them sequentially
# just multiplies latency by the number of chunks -- 4 chunks x ~10s was making
# a sync take 40s+ when the actual reconciliation takes under a second. Kept
# modest so a burst doesn't trip per-minute limits: at 4, concurrent chunks
# were overwhelming every provider at once and whole chunks fell to
# ai_pending. 2 keeps most of the speedup without that contention.
MAX_CONCURRENT_BATCHES = int(os.environ.get("AI_MAX_CONCURRENT_BATCHES", "2"))

# Which provider produced the most recent successful response, so callers can
# record WHICH model judged a case -- models calibrate confidence differently,
# so an 80 from one is not an 80 from another.
#
# THREAD-LOCAL on purpose: batched investigations run concurrently, and a
# single shared global would let one thread's provider be recorded against
# another thread's case. Each worker reads back only its own value.
_local = threading.local()

# A provider that just refused (rate limit, out of credits) will refuse the
# next chunk too. Without this, every concurrent chunk independently pays a
# full round-trip to discover the same dead provider -- with OpenRouter out of
# credits that alone turned a ~15s sync into 60s+. Remember the failure briefly
# and skip straight to the next provider.
PROVIDER_COOLDOWN_SECONDS = int(os.environ.get("AI_PROVIDER_COOLDOWN", "60"))
_cooldown: dict[str, float] = {}
_cooldown_lock = threading.Lock()


def _is_cooling_down(provider: str) -> bool:
    with _cooldown_lock:
        until = _cooldown.get(provider, 0.0)
        if until and time.monotonic() < until:
            return True
        _cooldown.pop(provider, None)
        return False


def _start_cooldown(provider: str) -> None:
    with _cooldown_lock:
        _cooldown[provider] = time.monotonic() + PROVIDER_COOLDOWN_SECONDS


def last_provider() -> str | None:
    """Provider behind the most recent successful generation ON THIS THREAD."""
    return getattr(_local, "provider", None)


def available_providers() -> list[str]:
    """Providers with a usable key configured, in failover order."""
    out = []
    for name in PROVIDER_ORDER:
        try:
            _provider_key(name)
        except AIAuthError:
            continue
        out.append(name)
    return out


class AIAuthError(Exception):
    """GEMINI_API_KEY missing, or rejected by Google."""


class AIAPIError(Exception):
    """Gemini reachable but responded with a non-2xx status (other than
    auth/rate-limit), or the response didn't contain the expected
    structured JSON."""


class AIRateLimitError(AIAPIError):
    """
    Gemini returned 429 -- a distinct, retryable failure, not a generic
    error. A daily or per-minute cap won't clear by immediately retrying
    in the same run, so callers should:
      - mark the affected case(s) 'ai_pending' (NOT 'manual_review' --
        that would falsely imply AI looked and recommended a human
        decision, when really AI never got to look at all), and
      - stop attempting further batches in THIS run rather than burning
        more of an already-exhausted quota on calls that will also fail.
    A "Retry AI Investigation" button lets the user try again later --
    see case_engine.retry_pending_cases(). No automatic sleep/backoff:
    that would block Streamlit for no benefit against a daily cap.
    """


_ENV_KEY = {
    "gemini": "GEMINI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "groq": "GROQ_API_KEY",
}


def _provider_key(provider: str) -> str:
    env_name = _ENV_KEY[provider]
    key = os.environ.get(env_name)
    if not key or key.startswith("your_") or key.startswith("paste_"):
        raise AIAuthError(f"{env_name} is not set (or still a placeholder) in .env.")
    return key


def _api_key():
    """Back-compat alias -- the Gemini key specifically."""
    return _provider_key("gemini")


def _to_json_schema(schema: dict) -> dict:
    """
    Convert Gemini's schema dialect (uppercase type names) to standard JSON
    Schema, which every OpenAI-compatible provider expects. Purely a rename of
    type tokens -- the shape, field names and descriptions are untouched, so
    all providers are asked for the exact same structure and results stay
    directly comparable.
    """
    if not isinstance(schema, dict):
        return schema
    out = {}
    for k, v in schema.items():
        if k == "type" and isinstance(v, str):
            out[k] = v.lower()
        elif k == "properties" and isinstance(v, dict):
            out[k] = {pk: _to_json_schema(pv) for pk, pv in v.items()}
        elif k == "items":
            out[k] = _to_json_schema(v)
        else:
            out[k] = v
    # OpenAI-style strict JSON schema rejects free-form objects.
    if out.get("type") == "object" and "properties" in out:
        out.setdefault("additionalProperties", False)
    return out


def _generate(system_prompt: str, user_message: str, schema: dict | None = None,
              temperature: float = 0.2):
    """
    Generate a response, trying each configured provider in PROVIDER_ORDER
    until one succeeds.

    With a schema: returns the parsed JSON object (structured output mode).
    Without one: returns the raw response text (used by ask(), which is
    conversational, not a decision the app acts on automatically).

    Failover only moves on for RETRYABLE failures -- a rate limit, a transient
    API error, or a missing key. An AIAuthError from a provider that IS
    configured (i.e. a genuinely rejected key) is worth surfacing rather than
    silently masking behind another provider.

    If every provider fails, the LAST error is re-raised, preferring a
    rate-limit error if one occurred, so callers still land on `ai_pending`
    rather than a misleading "manual review" verdict.
    """
    providers = available_providers()
    if not providers:
        raise AIAuthError(
            "No AI provider is configured. Set GEMINI_API_KEY or OPENROUTER_API_KEY in .env.")

    failures = []
    any_rate_limited = False

    for name in providers:
        if _is_cooling_down(name):
            failures.append(f"{name}: skipped (recently rate-limited)")
            any_rate_limited = True
            continue
        try:
            result = _PROVIDERS[name](system_prompt, user_message, schema, temperature)
            _local.provider = name
            return result
        except (AIRateLimitError, AIAPIError, AIAuthError) as exc:
            if isinstance(exc, AIRateLimitError):
                any_rate_limited = True
                _start_cooldown(name)
            # First line only: provider error bodies are long, and what matters
            # is WHICH provider failed and roughly why.
            detail = str(exc).splitlines()[0][:160]
            failures.append(f"{name}: {detail}")

    # Report EVERY provider that refused, not just the last one tried. Surfacing
    # only the final failure names the wrong culprit -- a chunk that OpenRouter
    # rate-limited and Groq refused would be reported as a Gemini problem purely
    # because Gemini happens to be last in the chain.
    summary = "All AI providers failed. " + " | ".join(failures)
    raise (AIRateLimitError(summary) if any_rate_limited else AIAPIError(summary))


def _gemini_generate(system_prompt: str, user_message: str, schema: dict | None,
                     temperature: float):
    key = _provider_key("gemini")
    generation_config = {"temperature": temperature}
    if schema is not None:
        generation_config["responseMimeType"] = "application/json"
        generation_config["responseSchema"] = schema

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_message}]}],
        "generationConfig": generation_config,
    }

    try:
        resp = requests.post(
            API_URL_TMPL.format(model=MODEL),
            params={"key": key},
            json=payload,
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise AIAPIError(f"Could not reach Gemini: {exc}") from exc

    if resp.status_code in (401, 403):
        raise AIAuthError(f"Gemini rejected the API key ({resp.status_code}): {resp.text[:300]}")
    if resp.status_code == 429:
        raise AIRateLimitError(f"Gemini rate-limited this request (429): {resp.text[:300]}")
    if not resp.ok:
        raise AIAPIError(f"Gemini returned {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise AIAPIError(f"Gemini's response didn't include any text: {exc}") from exc

    if schema is None:
        return text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIAPIError(f"Gemini's response wasn't valid JSON: {exc}") from exc


# Retrying a 402 at the affordable ceiling is only worth it if that ceiling can
# still hold a real batched answer (~1.5k tokens). Below this the reply would be
# cut off mid-JSON, which is worse than failing over to a provider that can
# finish the thought.
_MIN_USEFUL_MAX_TOKENS = 1200

_AFFORDABLE_RE = re.compile(r"can only afford\s+(\d+)", re.IGNORECASE)


def _affordable_tokens(body: str) -> int | None:
    """The token budget a 402 body says the account can actually cover."""
    match = _AFFORDABLE_RE.search(body or "")
    return int(match.group(1)) if match else None


def _strip_code_fence(text: str) -> str:
    """
    Drop a ```json ... ``` wrapper before parsing.

    Providers are asked for strict json_schema output and the good ones honour
    it, but a weaker model fenced its reply as markdown even under `strict`.
    A fence is a formatting quirk, not a wrong answer -- there is no reason to
    discard an otherwise valid result over it.
    """
    stripped = (text or "").strip()
    if not stripped.startswith("```"):
        return stripped
    body = stripped[3:]
    if "\n" in body:
        first, rest = body.split("\n", 1)
        # Only a bare language tag may follow the opening fence.
        if first.strip().isalpha():
            body = rest
    return body.rsplit("```", 1)[0].strip() if body.rstrip().endswith("```") else body.strip()


def _openai_compatible_generate(provider: str, url: str, model: str, extra_headers: dict,
                                system_prompt: str, user_message: str, schema: dict | None,
                                temperature: float, max_tokens: int,
                                _retry_402: bool = True,
                                fallback_models: list[str] | None = None):
    """
    OpenAI-compatible chat-completions call (OpenRouter). The same adapter
    shape works for any OpenAI-compatible endpoint -- xAI/Grok included --
    if another is added later: only the URL, key and model change.

    Structured output uses json_schema response_format, the OpenAI-compatible
    equivalent of Gemini's responseSchema, so batched multi-case results come
    back in exactly the same shape from either provider.
    """
    key = _provider_key(provider)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if fallback_models:
        # OpenRouter caps this array at 3 entries INCLUDING the primary.
        payload["models"] = [model, *fallback_models][:3]
    if schema is not None:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "ledgr_result", "strict": True,
                            "schema": _to_json_schema(schema)},
        }

    try:
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                **extra_headers,
            },
            json=payload,
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise AIAPIError(f"Could not reach {provider}: {exc}") from exc

    if resp.status_code in (401, 403):
        raise AIAuthError(f"{provider} rejected the API key ({resp.status_code}): {resp.text[:300]}")
    if resp.status_code == 429:
        raise AIRateLimitError(f"{provider} rate-limited this request (429): {resp.text[:300]}")
    if resp.status_code == 413:
        # Groq returns 413 with code "rate_limit_exceeded" when prompt +
        # max_tokens exceeds the tokens-per-minute ceiling. Retryable, so
        # treat it as a rate limit and move to the next provider.
        raise AIRateLimitError(
            f"{provider} token-per-minute limit exceeded (413): {resp.text[:300]}")
    if resp.status_code == 402:
        # Out of credits, or -- more often -- asking to RESERVE more tokens
        # than the balance can cover. The body says exactly what is affordable
        # ("You requested up to 3000 tokens, but can only afford 2558"), so
        # retry once at that ceiling instead of discarding a provider that
        # could still answer. Only retried when the affordable budget is worth
        # having; below that the answer would be truncated anyway.
        affordable = _affordable_tokens(resp.text)
        if affordable and _retry_402 and affordable >= _MIN_USEFUL_MAX_TOKENS:
            return _openai_compatible_generate(
                provider, url, model, extra_headers, system_prompt,
                user_message, schema, temperature, affordable,
                _retry_402=False, fallback_models=fallback_models)
        raise AIRateLimitError(
            f"{provider} has insufficient credits for this request (402): {resp.text[:300]}")
    if not resp.ok:
        raise AIAPIError(f"{provider} returned {resp.status_code}: {resp.text[:300]}")

    data = resp.json()

    # OpenRouter can return HTTP 200 whose BODY carries an upstream failure
    # ("Upstream error from Nvidia: Service temporarily overloaded", code 502).
    # Without this the KeyError below would report the misleading "response
    # didn't include any text" instead of the real reason. Upstream capacity
    # errors are transient, so they are retryable and fail over.
    err = data.get("error") if isinstance(data, dict) else None
    if err:
        message = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        code = err.get("code") if isinstance(err, dict) else None
        if code in (429, 402, 502, 503) or "rate" in str(message).lower():
            raise AIRateLimitError(f"{provider} upstream error ({code}): {str(message)[:300]}")
        raise AIAPIError(f"{provider} returned an error body ({code}): {str(message)[:300]}")

    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise AIAPIError(f"{provider}'s response didn't include any text: {exc}") from exc

    if schema is None:
        return (text or "").strip()
    try:
        return json.loads(_strip_code_fence(text))
    except (json.JSONDecodeError, TypeError) as exc:
        raise AIAPIError(f"{provider}'s response wasn't valid JSON: {exc}") from exc


def _openrouter_generate(system_prompt, user_message, schema, temperature):
    return _openai_compatible_generate(
        "openrouter", OPENROUTER_URL, OPENROUTER_MODEL,
        # OpenRouter uses these for attribution on its dashboard.
        {"HTTP-Referer": "http://localhost:5173", "X-Title": "Ledgr"},
        system_prompt, user_message, schema, temperature, OPENROUTER_MAX_TOKENS,
        fallback_models=OPENROUTER_FALLBACK_MODELS)


def _groq_generate(system_prompt, user_message, schema, temperature):
    return _openai_compatible_generate(
        "groq", GROQ_URL, GROQ_MODEL, {},
        system_prompt, user_message, schema, temperature, GROQ_MAX_TOKENS)


_PROVIDERS = {
    "gemini": _gemini_generate,
    "openrouter": _openrouter_generate,
    "groq": _groq_generate,
}


# ===========================================================================
# Batched case investigation -- the one live path used for every
# AI-eligible case (variance, ambiguous match, orphan settlement alike).
# One unified schema so mixed case types can travel in the same batch.
# ===========================================================================
BATCH_RESULT_ITEM_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "case_id": {"type": "STRING", "description": "Must exactly match one of the given case_id values."},
        "decision": {
            "type": "STRING",
            "description": ("A short label for what this case is, e.g. 'partial_payment', "
                             "'overpayment', 'ambiguous_match', 'no_match'."),
        },
        "confidence": {
            "type": "INTEGER",
            "description": "0-100. Be conservative -- see the system instructions on forcing a match.",
        },
        "reasoning": {
            "type": "STRING",
            "description": ("Plain-English explanation grounded only in this case's own given "
                             "records. Never state a rupee amount other than the ones given."),
        },
        "evidence_used": {
            "type": "ARRAY", "items": {"type": "STRING"},
            "description": "Short bullets of the given facts that led to this conclusion.",
        },
        "missing_evidence": {
            "type": "ARRAY", "items": {"type": "STRING"},
            "description": ("What additional evidence, if it existed, would raise your confidence "
                             "-- e.g. 'customer order history'. Empty array if nothing would help."),
        },
        "recommended_action": {
            "type": "STRING", "enum": ["resolve", "manual_review", "escalate"],
            "description": ("'resolve' only when confidence is high AND every given fact "
                             "unambiguously supports one conclusion. 'manual_review' when real "
                             "evidence or candidates exist but multiple explanations remain "
                             "plausible, or evidence is thin -- a correct, successful outcome, "
                             "not a failure to force a match. 'escalate' specifically when there "
                             "is NO real evidence or candidate at all (nothing to weigh, not even "
                             "an ambiguous one) and a human needs to take an external action, e.g. "
                             "contacting a courier or payment gateway -- confidence should "
                             "genuinely be low in this case, not forced, since there is nothing to "
                             "be confident about."),
        },
        "next_step": {
            "type": "STRING",
            "description": ("ONE short, specific, actionable sentence telling a human exactly "
                             "what to do next, e.g. 'Escalate to courier for remittance "
                             "confirmation.' or 'Accept STL-00124; mark STL-00221 as duplicate.' "
                             "Distinct from `reasoning` -- this is the action, not the explanation."),
        },
        "candidate_id": {
            "type": "STRING",
            "description": ("If this case included candidate_matches and one is clearly the best "
                             "match, its id. Empty string if there were no candidates, or none "
                             "stood out."),
        },
    },
    "required": ["case_id", "decision", "confidence", "reasoning", "evidence_used",
                 "missing_evidence", "recommended_action", "next_step", "candidate_id"],
}

BATCH_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "results": {"type": "ARRAY", "items": BATCH_RESULT_ITEM_SCHEMA},
    },
    "required": ["results"],
}

BATCH_SYSTEM_PROMPT = (
    "You are Ledgr's AI Forensic Agent, investigating a batch of independent "
    "payment-reconciliation cases in a single pass. Each case has already had "
    "its amounts, deltas, and tolerance bands computed by deterministic code -- "
    "treat those as ground truth; never recompute or restate a different "
    "number than what you were given, and never invent an order, settlement, "
    "date, or candidate that isn't present in that case's own records. "
    "CASES ARE INDEPENDENT: never use one case's evidence to judge another. "
    "Some cases will have real candidate_matches to weigh; others will have "
    "NONE at all -- for those, do not invent a match. Confirm plainly that "
    "nothing was found, explain why in one sentence, recommend 'escalate' "
    "with a genuinely low confidence (there is nothing to be confident "
    "about), and give a concrete next_step a human can act on (e.g. verify "
    "with the payment gateway, or chase the courier for remittance). For "
    "cases that DO have real evidence or candidates but remain genuinely "
    "ambiguous, recommend 'manual_review' instead -- that is a correct, "
    "successful outcome, never a failure to force a match. Recommend "
    "'resolve' only when the evidence is unambiguous. Return exactly one "
    "result per case_id you were given, in the same order. "
    "IF A CANDIDATE ORDER HAS `already_settled_by` SET, that order has ALREADY BEEN PAID by the settlement named there. Never recommend linking a second settlement to it or marking it settled again -- the order is not missing its money. A credit that exactly matches an already-paid order is most likely a DUPLICATE PAYMENT (a checkout retry that charged the customer twice). Say so, recommend manual_review, and make the next step about verifying and refunding the customer, not about reconciling the order. "
    "WRITE FOR A NON-SPECIALIST. The reader runs a shop, not a payments team. Use everyday words: say 'the money never arrived' not 'settlement not identified'; 'the customer paid less than the order total' not 'amount variance outside tolerance'; 'the courier hasn't sent the cash yet' not 'remittance pending'. Avoid jargon such as reconciliation, tier, disposition, gateway ref, UTR, MDR, delta and exception unless you immediately explain it in plain words. Short sentences. Say what happened, then what it means for their money, then what to do."
)


def investigate_batch(cases: list[dict]) -> dict:
    """
    Investigate multiple independent cases in ONE request. `cases` is a
    list of compact context dicts, each with at least a "case_id" key
    (see case_engine.py for the exact shape). Returns a dict keyed by
    case_id -> result, so callers can detect a case the model's response
    omitted (partial success) by checking membership.

    Raises AIAuthError / AIRateLimitError / AIAPIError if the WHOLE
    request fails -- callers must mark every case in the batch as
    ai_pending in that case, never fabricate a result for any of them.
    """
    user_message = (
        f"Investigate these {len(cases)} independent reconciliation cases. "
        "Return one result per case_id, in the same order:\n\n"
        + json.dumps(cases, indent=2, default=str)
    )
    result = _generate(BATCH_SYSTEM_PROMPT, user_message, schema=BATCH_RESPONSE_SCHEMA)
    return {r["case_id"]: r for r in result.get("results", []) if r.get("case_id")}


# ===========================================================================
# Follow-up investigation -- the one controlled, user-triggered agentic
# step: the model already named what evidence would help (missing_evidence
# above); the user asks Ledgr to fetch it; this makes ONE more call with
# that new evidence for a final conclusion. Never automatic, never looped.
# ===========================================================================
FOLLOWUP_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "decision": {"type": "STRING"},
        "confidence": {"type": "INTEGER"},
        "reasoning": {"type": "STRING"},
        "evidence_used": {"type": "ARRAY", "items": {"type": "STRING"}},
        "recommended_action": {"type": "STRING", "enum": ["resolve", "manual_review", "escalate"]},
        "next_step": {"type": "STRING", "description": "One short, specific, actionable sentence."},
        "candidate_id": {"type": "STRING"},
    },
    "required": ["decision", "confidence", "reasoning", "evidence_used",
                 "recommended_action", "next_step", "candidate_id"],
}

FOLLOWUP_SYSTEM_PROMPT = (
    "You previously investigated a reconciliation case and said you needed "
    "additional evidence to be more confident. You are now given that "
    "evidence -- or told plainly that it isn't available in this system. "
    "Give your FINAL conclusion using everything you now have. If the new "
    "evidence resolves the ambiguity, say so and raise your confidence "
    "accordingly. If it doesn't help, or wasn't available, say that plainly "
    "and keep your recommendation conservative -- do not force a resolution. "
    "WRITE FOR A NON-SPECIALIST: everyday words, short sentences, no jargon "
    "(avoid 'reconciliation', 'tier', 'UTR', 'MDR', 'delta', 'exception' "
    "unless you explain them plainly). Say what happened, what it means for "
    "their money, and what to do."
)


def investigate_followup(original_context: dict, original_result: dict, new_evidence: dict) -> dict:
    """
    ONE additional call for a single case, after the user explicitly asks
    Ledgr to fetch the evidence the model itself said it was missing. Not
    part of the batched pass, not automatic, and never looped further --
    this always produces a final answer, one round only.

    Raises AIAuthError / AIRateLimitError / AIAPIError on failure --
    callers must leave the case's existing result untouched and report
    the follow-up as unavailable, never overwrite a real prior result
    with a fabricated one.
    """
    user_message = (
        "ORIGINAL CASE:\n" + json.dumps(original_context, indent=2, default=str)
        + "\n\nYOUR PREVIOUS FINDING:\n" + json.dumps(original_result, indent=2, default=str)
        + "\n\nNEWLY GATHERED EVIDENCE (you asked for this):\n" + json.dumps(new_evidence, indent=2, default=str)
        + "\n\nGive your final conclusion now."
    )
    return _generate(FOLLOWUP_SYSTEM_PROMPT, user_message, schema=FOLLOWUP_RESPONSE_SCHEMA)


# ===========================================================================
# Draft message -- the one pure text-generation task in this project.
#
# Zero financial-decision risk by construction: the model writes a draft, a
# human reads and edits it, and the human's own mail client sends it. Ledgr
# never sends anything and never commits the merchant to a refund, a payment,
# or a deadline.
# ===========================================================================
DRAFT_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "subject": {
            "type": "STRING",
            "description": "Short, specific email subject line. Include the order/settlement ID.",
        },
        "body": {
            "type": "STRING",
            "description": ("The full message. Plain text, no markdown. Professional and "
                             "concise. State the facts and make one clear request."),
        },
        "facts_used": {
            "type": "ARRAY", "items": {"type": "STRING"},
            "description": "Each concrete fact from the case that the message cites.",
        },
    },
    "required": ["subject", "body", "facts_used"],
}

DRAFT_SYSTEM_PROMPT = (
    "You are drafting a message on behalf of a merchant's finance team about a "
    "payment reconciliation issue. A human WILL read, edit and send this -- you "
    "are not sending it. "
    "\n\n"
    "Use ONLY the facts in the case data provided. Never invent an order ID, "
    "settlement ID, amount, date, reference number, or person. Never state a "
    "rupee figure other than the ones you were given. If something needed for a "
    "complete message is genuinely missing, write the message without it rather "
    "than inventing a value or leaving a placeholder like [AMOUNT]. "
    "\n\n"
    "Never commit the merchant to anything: do not promise a refund, offer "
    "compensation, threaten legal or punitive action, accept fault, or set a "
    "deadline that was not given to you. Ask a clear question or make one "
    "specific, reasonable request. "
    "\n\n"
    "Match the recipient. To a PAYMENT GATEWAY or COURIER: factual and "
    "businesslike, cite the reference IDs they need to look the transaction up, "
    "and ask them to investigate or confirm. To a CUSTOMER: polite and plain, "
    "avoid internal jargon (never say 'reconciliation exception', 'tier', or "
    "'case ID'), and explain simply what is being checked. "
    "\n\n"
    "Plain text only -- no markdown, no bold, no bullet characters other than "
    "simple hyphens. Sign off as 'Finance Team' followed by the merchant's "
    "company name if given. Keep it under 200 words."
)


def draft_message(case_context: dict, recipient_type: str, merchant_name: str = "") -> dict:
    """
    Draft an outbound message about one case. `recipient_type` is one of
    'gateway', 'courier' or 'customer' -- it changes tone and what the
    message asks for, so it is passed explicitly rather than guessed.

    Returns {subject, body, facts_used}. Raises the usual AI errors on
    failure; callers must show that honestly rather than substituting a
    canned template, because a fabricated "AI-written" message is worse
    than no message.
    """
    user_message = (
        f"Recipient type: {recipient_type}\n"
        f"Merchant company name: {merchant_name or 'the merchant'}\n\n"
        "Case data (the ONLY facts you may use):\n"
        + json.dumps(case_context, indent=2, default=str)
    )
    return _generate(DRAFT_SYSTEM_PROMPT, user_message, schema=DRAFT_RESPONSE_SCHEMA,
                     temperature=0.3)


# ===========================================================================
# Ask AI -- free-text Q&A. Only reached for genuinely novel questions;
# case_engine.try_direct_answer() answers most questions from Python
# first, without spending a Gemini call at all.
# ===========================================================================
ASK_SYSTEM_PROMPT = (
    "You are Ledgr's reconciliation assistant. Answer the user's question "
    "using ONLY the reconciliation data provided below -- never invent an "
    "order, settlement, amount, date, or status that isn't in the given "
    "data. If the answer cannot be determined from what's given, say so "
    "plainly instead of guessing. Keep answers short and concrete, and cite "
    "actual IDs and amounts from the data when relevant. You are read-only: "
    "you explain, search, summarize, and recommend -- you never claim to "
    "have changed data, sent money, or sent a message on the user's behalf. "
    "\n\n"
    "WHEN RANKING OR PRIORITISING CASES, use `amount_at_risk` -- never "
    "`delta`. They are not the same thing. An order that was never settled "
    "has a delta of Rs 0.00 because no payment arrived to compare against, "
    "yet its ENTIRE value is unrecovered and at risk. Ranking by delta "
    "therefore buries the worst cases below trivial ones. "
    "\n\n"
    "Money not received outranks money over-received. An overpayment is "
    "already in the merchant's account -- it is a liability to reconcile, "
    "not a loss. Unmatched, short-paid and overdue cases are money the "
    "merchant is owed and has not got, which can become permanently "
    "unrecoverable once gateway claim windows or courier dispute deadlines "
    "pass. Age matters too: an older unresolved case is more urgent than a "
    "newer one of similar value. "
    "\n\n"
    "Reply in plain text. Do not use markdown formatting such as ** for "
    "bold -- it is rendered literally."
)


def ask(question: str, context: dict, history: list[dict] | None = None) -> str:
    """
    Free-text Q&A grounded in real reconciliation data. Plain text, not
    structured JSON -- conversational, and the app never acts on the
    answer automatically (see ASK_SYSTEM_PROMPT).

    `history` carries the recent turns of this conversation so follow-up
    questions can resolve their references -- without it "what is his name?"
    has no antecedent and the model can only answer that it doesn't know.
    Earlier turns supply the SUBJECT being referred to; the reconciliation
    data below remains the only source of facts.

    Raises AIAuthError / AIRateLimitError / AIAPIError on failure --
    callers must show an honest "AI unavailable" message, never fabricate
    an answer.
    """
    parts = []
    if history:
        convo = "\n".join(
            f"User: {h.get('question', '')}\nAssistant: {h.get('answer', '')}"
            for h in history if h.get("question")
        )
        if convo:
            parts.append(
                "Earlier in this conversation -- use ONLY to resolve references "
                "like 'it', 'his', 'that order'. It is not a source of facts:\n"
                + convo
            )
    parts.append(f"Question: {question}")
    parts.append(
        "Reconciliation data (the ONLY source of truth available to you):\n"
        + json.dumps(context, indent=2, default=str)
    )
    return _generate(ASK_SYSTEM_PROMPT, "\n\n".join(parts), schema=None, temperature=0.1)


if __name__ == "__main__":
    # Standalone self-test: python ai_client.py
    # Never prints the key itself, only pass/fail + the returned results.
    key = os.environ.get("GEMINI_API_KEY")
    placeholder = key is None or key.startswith("your_") or key.startswith("paste_")

    print("=" * 60)
    if placeholder:
        print("RESULT: NOT CONFIGURED")
        print("  .env still has a placeholder value for GEMINI_API_KEY.")
        print("  Edit .env (not .env.example) and paste your real key in.")
    else:
        print(f"Using key ending in ...{key[-4:]} (rest is never shown)")
        sample_cases = [
            {"case_id": "CASE-TEST-1", "case_type": "partial_payment",
             "record": {"id": "ORD-00042", "expected": "Rs 9,999.00", "received": "Rs 4,999.50",
                        "issue": "Partial payment"}, "candidate_matches": []},
            {"case_id": "CASE-TEST-2", "case_type": "unmatched_settlement",
             "record": {"id": "STL-00099", "expected": "Rs 0.00", "received": "Rs 6,499.99",
                        "issue": "Unmatched / ambiguous"},
             "candidate_matches": [{"order_id": "ORD-00007", "amount_paise": 649999,
                                    "order_date": "2026-08-06", "days_from_settlement": 2}]},
        ]
        try:
            results = investigate_batch(sample_cases)
            print(f"RESULT: BATCH CALL SUCCEEDED -- {len(results)}/{len(sample_cases)} cases returned")
            for case_id, r in results.items():
                print(f"  --- {case_id} ---")
                for k, v in r.items():
                    print(f"    {k}: {v}")
        except AIRateLimitError as exc:
            print(f"RESULT: RATE LIMITED -- {exc}")
        except AIAuthError as exc:
            print(f"RESULT: AUTH FAILED -- {exc}")
        except AIAPIError as exc:
            print(f"RESULT: API ERROR -- {exc}")
    print("=" * 60)
