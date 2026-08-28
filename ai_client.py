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


def _api_key():
    key = os.environ.get("GEMINI_API_KEY")
    if not key or key.startswith("your_") or key.startswith("paste_"):
        raise AIAuthError("GEMINI_API_KEY is not set (or still a placeholder) in .env.")
    return key


def _generate(system_prompt: str, user_message: str, schema: dict | None = None, temperature: float = 0.2):
    """
    Shared request/response plumbing for every Gemini call in this module.
    With a schema: returns the parsed JSON object (structured output mode).
    Without one: returns the raw response text (used by ask(), which is
    conversational, not a decision the app acts on automatically).

    Raises AIAuthError / AIRateLimitError / AIAPIError on any failure --
    every caller in this module treats that as "AI unavailable," never as
    license to guess.
    """
    key = _api_key()
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
    "have changed data, sent money, or sent a message on the user's behalf."
)


def ask(question: str, context: dict) -> str:
    """
    Free-text Q&A grounded in real reconciliation data. Plain text, not
    structured JSON -- conversational, and the app never acts on the
    answer automatically (see ASK_SYSTEM_PROMPT).

    Raises AIAuthError / AIRateLimitError / AIAPIError on failure --
    callers must show an honest "AI unavailable" message, never fabricate
    an answer.
    """
    user_message = (
        f"Question: {question}\n\n"
        "Reconciliation data (the ONLY source of truth available to you):\n"
        + json.dumps(context, indent=2, default=str)
    )
    return _generate(ASK_SYSTEM_PROMPT, user_message, schema=None, temperature=0.1)


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
