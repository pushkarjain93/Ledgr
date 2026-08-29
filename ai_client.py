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
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.5-flash")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")

# Groq's free tier caps TOKENS PER MINUTE (8000 by default), and the reservation
# counts prompt + max_tokens together. A batched 5-case prompt is ~2-3k tokens,
# so this leaves comfortable headroom under that ceiling. Too high and every
# request is refused with a 413 before any work happens.
GROQ_MAX_TOKENS = int(os.environ.get("GROQ_MAX_TOKENS", "4000"))

# OpenRouter reserves the FULL max_tokens of the model up-front against your
# credit balance. Left unset it reserves the model's maximum (65k+), which a
# free-tier account cannot afford -- the request is refused with a 402 before
# any tokens are actually spent. Capping this to what a batched response
# realistically needs (5 cases x ~400 tokens of reasoning, generously rounded)
# keeps free accounts working. Gemini has no equivalent reservation, so this
# applies only to the OpenAI-compatible path.
OPENROUTER_MAX_TOKENS = int(os.environ.get("OPENROUTER_MAX_TOKENS", "8000"))

# Order matters: first configured provider wins, later ones are failover.
PROVIDER_ORDER = ("gemini", "openrouter", "groq")

# Set to the provider that produced the most recent successful response, so
# callers can record WHICH model actually judged a case. Different models
# calibrate confidence differently -- an 80 from one is not necessarily an 80
# from another -- so this is stored per case rather than left ambiguous.
_last_provider: str | None = None


def last_provider() -> str | None:
    """Provider name behind the most recent successful generation."""
    return _last_provider


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
    global _last_provider

    providers = available_providers()
    if not providers:
        raise AIAuthError(
            "No AI provider is configured. Set GEMINI_API_KEY or OPENROUTER_API_KEY in .env.")

    rate_limit_error = None
    last_error = None

    for name in providers:
        try:
            result = _PROVIDERS[name](system_prompt, user_message, schema, temperature)
            _last_provider = name
            return result
        except AIRateLimitError as exc:
            rate_limit_error = exc
            last_error = exc
        except (AIAPIError, AIAuthError) as exc:
            last_error = exc

    raise rate_limit_error or last_error


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


def _openai_compatible_generate(provider: str, url: str, model: str, extra_headers: dict,
                                system_prompt: str, user_message: str, schema: dict | None,
                                temperature: float, max_tokens: int):
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
        # Out of credits, or asking to reserve more tokens than the account
        # can afford. Same practical meaning as a rate limit -- this provider
        # cannot serve right now -- so treat it as retryable and fail over.
        raise AIRateLimitError(
            f"{provider} has insufficient credits for this request (402): {resp.text[:300]}")
    if not resp.ok:
        raise AIAPIError(f"{provider} returned {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise AIAPIError(f"{provider}'s response didn't include any text: {exc}") from exc

    if schema is None:
        return (text or "").strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise AIAPIError(f"{provider}'s response wasn't valid JSON: {exc}") from exc


def _openrouter_generate(system_prompt, user_message, schema, temperature):
    return _openai_compatible_generate(
        "openrouter", OPENROUTER_URL, OPENROUTER_MODEL,
        # OpenRouter uses these for attribution on its dashboard.
        {"HTTP-Referer": "http://localhost:5173", "X-Title": "Ledgr"},
        system_prompt, user_message, schema, temperature, OPENROUTER_MAX_TOKENS)


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
    "result per case_id you were given, in the same order."
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
    "and keep your recommendation conservative -- do not force a resolution."
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
