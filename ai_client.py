"""
Isolated Gemini (Google AI) client for Ledgr's AI Forensic Agent.

Talks to Google's real Generative Language API using GEMINI_API_KEY from
the environment. Same pattern as razorpay_client.py: raw REST calls (via
requests, not a vendor SDK), isolated module, never touches engine.py's
matching/tier logic directly -- engine.py only ever calls diagnose() and
reads the dict back; which real provider sits behind that call is entirely
this file's business.

The model NEVER computes a number. engine.py's ai_diagnose() hands this
module facts it has ALREADY worked out (delta, band, order_amount, age,
etc.); this module's only job is judgement -- pick the single best-fitting
reason code, explain the shape of the variance in plain English, and
recommend what should happen next. The response is forced into Gemini's
structured JSON output mode (a response schema), so there's nothing
free-text to parse and no room for the model to invent a different shape
than what's expected.
"""
import json
import os

import requests
from dotenv import load_dotenv

from config import fmt

# Loads GEMINI_API_KEY from a local .env file (see .env.example) into
# os.environ, if present -- same mechanism razorpay_client.py already uses.
load_dotenv()

API_URL_TMPL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MODEL = "gemini-3.6-flash"
TIMEOUT_SECONDS = 20


class AIAuthError(Exception):
    """GEMINI_API_KEY missing, or rejected by Google."""


class AIAPIError(Exception):
    """Gemini reachable but responded with a non-2xx status, or the
    response didn't contain the expected structured JSON."""


# The five reason codes are engine.py's own REASON_LEGEND -- duplicated
# here (not imported) so this module has zero dependency on engine.py and
# stays a one-directional, swappable client, exactly like razorpay_client.py.
_REASON_CODES = [
    "R1_AWAITING_REMITTANCE", "R2_REMITTANCE_OVERDUE", "R3_UNMATCHED_AMBIGUOUS",
    "R4_PARTIAL_PAYMENT", "R5_AI_VARIANCE",
]

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "reason_code": {
            "type": "STRING", "enum": _REASON_CODES,
            "description": "The single best-fitting reason code for this variance.",
        },
        "confidence": {
            "type": "INTEGER",
            "description": "Your confidence in this classification, 0-100. Be conservative.",
        },
        "explanation": {
            "type": "STRING",
            "description": ("One or two plain-English sentences a finance-ops reviewer would "
                             "read. Never state a rupee amount other than the ones you were given."),
        },
        "evidence": {
            "type": "ARRAY", "items": {"type": "STRING"},
            "description": "Short bullet points of the given facts that led to this conclusion.",
        },
        "recommendation": {
            "type": "STRING", "enum": ["AUTO_CLEAR", "HUMAN_REVIEW", "ESCALATE"],
            "description": ("What should happen next. Only recommend AUTO_CLEAR when "
                             "confidence is 90+ and every given fact unambiguously supports it."),
        },
    },
    "required": ["reason_code", "confidence", "explanation", "evidence", "recommendation"],
}

SYSTEM_PROMPT = (
    "You are Ledgr's AI Forensic Agent, investigating a single payment "
    "reconciliation variance. You are given FACTS that deterministic code has "
    "already computed -- amounts, deltas, tolerance bands, dates. Treat them as "
    "ground truth; do not recompute or restate a different number than what you "
    "were given. Your job is judgement, not arithmetic: pick the single best "
    "reason code, explain the shape of the variance in plain English, and "
    "recommend what should happen next. Be conservative -- recommending "
    "AUTO_CLEAR is only appropriate when the evidence is unambiguous; when in "
    "doubt, recommend HUMAN_REVIEW."
)


_MONEY_FIELDS = {"order_amount", "received", "delta", "band"}


def _humanize_facts(facts: dict) -> dict:
    """
    Paise -> 'Rs 1,234.56' for known money fields, for the PROMPT TEXT
    only. engine.py's own facts dict stays raw paise -- it's also used
    for real arithmetic in _offline_diagnose() (both as the deterministic
    path and as _llm_diagnose()'s fallback on failure), which would break
    if it received formatted strings instead of numbers.
    """
    out = dict(facts)
    for k in _MONEY_FIELDS:
        if k in out and isinstance(out[k], (int, float)):
            out[k] = fmt(int(out[k]))
    return out


def _api_key():
    key = os.environ.get("GEMINI_API_KEY")
    if not key or key.startswith("your_") or key.startswith("paste_"):
        raise AIAuthError("GEMINI_API_KEY is not set (or still a placeholder) in .env.")
    return key


def diagnose(facts: dict) -> dict:
    """
    Send engine-computed facts to Gemini and get back a structured
    diagnosis: {reason_code, confidence, explanation, evidence, recommendation}.

    Raises AIAuthError / AIAPIError on any failure -- callers must treat
    an exception as "could not verify via AI, fall back to human review",
    never as license to guess.
    """
    key = _api_key()
    user_message = (
        "Investigate this reconciliation variance. Facts (already computed, "
        "treat as ground truth -- do not restate a different number):\n"
        + json.dumps(_humanize_facts(facts), indent=2, default=str)
    )
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": user_message}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
            "temperature": 0.2,
        },
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
    if not resp.ok:
        raise AIAPIError(f"Gemini returned {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raise AIAPIError(f"Gemini's response didn't match the expected shape: {exc}") from exc


if __name__ == "__main__":
    # Standalone self-test: python ai_client.py
    # Never prints the key itself, only pass/fail + the returned diagnosis.
    key = os.environ.get("GEMINI_API_KEY")
    placeholder = key is None or key.startswith("your_") or key.startswith("paste_")

    print("=" * 60)
    if placeholder:
        print("RESULT: NOT CONFIGURED")
        print("  .env still has a placeholder value for GEMINI_API_KEY.")
        print("  Edit .env (not .env.example) and paste your real key in.")
    else:
        print(f"Using key ending in ...{key[-4:]} (rest is never shown)")
        sample_facts = {
            "record_id": "ORD-00042", "order_amount": 999900, "received": 949900,
            "delta": -50000, "band": 25000, "payment_mode": "CARD",
            "identifier": "pay_000042A", "age_days": 2, "settlement_id": "STL-00042",
        }
        try:
            result = diagnose(sample_facts)
            print("RESULT: CALL SUCCEEDED")
            for k, v in result.items():
                print(f"  {k}: {v}")
        except AIAuthError as exc:
            print(f"RESULT: AUTH FAILED -- {exc}")
        except AIAPIError as exc:
            print(f"RESULT: API ERROR -- {exc}")
    print("=" * 60)
