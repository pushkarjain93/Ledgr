"""
Isolated Razorpay client for Ledgr.

Talks to Razorpay's real REST API using RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET
from the environment. Does not touch engine.py, schema_map.py's rename
logic, or any reconciliation rule -- this module only fetches and normalizes
raw Razorpay data into plain Python dicts/lists. Nothing here writes to
orders.csv/settlements.csv or calls reconcile().

Orders are NOT fetched here -- those come from the merchant's e-commerce
platform API (Shopify etc., mocked for the buildathon). This module is
settlements only.

Two Razorpay endpoints are used:

  GET /v1/settlements/
      Settlement BATCH headers only (id, amount, utr, created_at, status).
      No per-payment reference -- cannot populate `gateway_ref_id`, so its
      rows alone cannot satisfy SETTLEMENT_REQUIRED in schema_map.py. Kept
      here only for a "last settlement" summary view.

  GET /v1/settlements/recon/combined
      Per-transaction breakdown (payments, refunds, transfers,
      adjustments) for a given month/day. Has `payment_id` +
      `settlement_id` + `settlement_utr` together, which is what actually
      maps onto our per-order settlement schema. See to_settlement_rows().

Razorpay's Test Mode never generates real settlements -- no real money
moves, so there is nothing to settle (confirmed via Razorpay's own docs:
https://razorpay.com/docs/payments/settlements/faqs/,
https://razorpay.com/docs/payments/dashboard/test-live-modes/). An empty
result from either endpoint is therefore the EXPECTED state in test mode,
not a bug. Callers must treat STATUS_EMPTY as "connected fine, nothing to
show" and must never fabricate rows to fill the gap -- see
connection_status() below and CLAUDE.md's "never invent evidence" rule.
"""
import os
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

# Loads RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET from a local .env file (see
# .env.example) into os.environ, if present. Does not override a variable
# that's already set in the real environment, and never touches/prints the
# values themselves -- this just makes them visible to os.environ.get()
# below the same way they'd appear if you'd exported them in your shell.
load_dotenv()

API_BASE = "https://api.razorpay.com/v1"
TIMEOUT_SECONDS = 15

# connection_status() return values -- pick the matching UI message from these,
# never re-derive "empty vs broken" from the raw data yourself.
STATUS_OK = "connected_has_data"
STATUS_EMPTY = "connected_empty"          # expected in Test Mode
STATUS_AUTH_ERROR = "auth_error"          # bad/missing key id or secret
STATUS_API_ERROR = "api_error"            # network issue or non-auth failure


class RazorpayAuthError(Exception):
    """RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET missing, or rejected by Razorpay."""


class RazorpayAPIError(Exception):
    """Razorpay reachable but responded with a non-2xx status other than auth."""


def _credentials():
    key_id = os.environ.get("RAZORPAY_KEY_ID")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET")
    if not key_id or not key_secret:
        raise RazorpayAuthError(
            "RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET are not set in the environment."
        )
    return key_id, key_secret


def _get(path, params=None):
    key_id, key_secret = _credentials()
    try:
        resp = requests.get(
            f"{API_BASE}{path}",
            auth=(key_id, key_secret),
            params=params or {},
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise RazorpayAPIError(f"Could not reach Razorpay: {exc}") from exc

    if resp.status_code == 401:
        raise RazorpayAuthError("Razorpay rejected the key id/secret (401 Unauthorized).")
    if not resp.ok:
        raise RazorpayAPIError(f"Razorpay returned {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def _paise_to_rupees(paise):
    return round((paise or 0) / 100, 2)


def fetch_settlements(count=100, skip=0):
    """
    GET /v1/settlements/ -- settlement batch headers.

    Returns a list of raw Razorpay settlement dicts. Empty list means
    Razorpay has nothing to report (normal in Test Mode) -- not an error.
    Raises RazorpayAuthError / RazorpayAPIError on real failures.
    """
    data = _get("/settlements/", params={"count": count, "skip": skip})
    return data.get("items", [])


def fetch_settlement_recon(year, month, day=None, count=100, skip=0):
    """
    GET /v1/settlements/recon/combined -- per-transaction breakdown for one
    month (optionally one day). This is the endpoint with payment_id, i.e.
    the one that can be mapped to our per-order settlement schema.

    Returns a list of raw Razorpay transaction dicts. Empty list means
    nothing settled in that period (normal in Test Mode) -- not an error.
    Raises RazorpayAuthError / RazorpayAPIError on real failures.
    """
    params = {"year": year, "month": month, "count": count, "skip": skip}
    if day is not None:
        params["day"] = day
    data = _get("/settlements/recon/combined", params=params)
    return data.get("items", [])


def to_settlement_rows(recon_items):
    """
    Normalize recon/combined `type == "payment"` items into our
    SETTLEMENT_REQUIRED shape (schema_map.py):
    settlement_id, settled_on, gateway_ref_id, bank_utr, amount_received,
    plus optional source/narration. Refunds/transfers/adjustments are
    skipped here -- they need separate handling, not silently folded in.

    Pure function: takes data in, returns dicts out. Does not call the API,
    does not touch engine.py, does not write anywhere.
    """
    rows = []
    for item in recon_items:
        if item.get("type") != "payment":
            continue
        settled_at = item.get("settled_at")
        rows.append({
            "settlement_id": item.get("settlement_id"),
            "settled_on": (
                datetime.fromtimestamp(settled_at, tz=timezone.utc).date().isoformat()
                if settled_at else None
            ),
            "gateway_ref_id": item.get("payment_id"),
            "bank_utr": item.get("settlement_utr"),
            "amount_received": _paise_to_rupees(item.get("credit") or item.get("amount")),
            "source": item.get("method"),
            "narration": item.get("description"),
        })
    return rows


def connection_status(year=None, month=None):
    """
    Make a real call and report one of STATUS_OK / STATUS_EMPTY /
    STATUS_AUTH_ERROR / STATUS_API_ERROR, plus whatever rows came back.

    Defaults to the current UTC month if year/month aren't given. This is
    the one function a UI should call -- it always hits the real API
    first, and only ever returns STATUS_EMPTY when Razorpay genuinely
    reported zero items, never as a stand-in for a real failure.

    Returns: (status: str, rows: list[dict], message: str)
    """
    now = datetime.now(timezone.utc)
    year = year or now.year
    month = month or now.month

    try:
        recon_items = fetch_settlement_recon(year=year, month=month)
    except RazorpayAuthError as exc:
        return STATUS_AUTH_ERROR, [], str(exc)
    except RazorpayAPIError as exc:
        return STATUS_API_ERROR, [], str(exc)

    rows = to_settlement_rows(recon_items)
    if not rows:
        return (
            STATUS_EMPTY,
            [],
            "Connected to Razorpay, but no settlements available "
            "(expected in Test Mode -- no real money moves, so nothing settles).",
        )
    return STATUS_OK, rows, f"Connected to Razorpay -- {len(rows)} settlement row(s) found."


if __name__ == "__main__":
    # Standalone self-test: run `python razorpay_client.py` after putting
    # your real Razorpay TEST MODE keys in .env (see .env.example). Nothing
    # here gets wired into the app -- this only proves the client works.
    # Never prints the key id/secret themselves, only pass/fail + counts.
    key_id, key_secret = os.environ.get("RAZORPAY_KEY_ID"), os.environ.get("RAZORPAY_KEY_SECRET")
    placeholder = {"rzp_test_your_key_id_here", "your_key_secret_here", None}

    print("=" * 60)
    if key_id in placeholder or key_secret in placeholder:
        print("RESULT: NOT CONFIGURED")
        print("  .env still has placeholder values. Edit .env (not .env.example)")
        print("  and paste your real Razorpay Test Mode Key ID / Key Secret in.")
    else:
        print(f"Using key id ending in ...{key_id[-4:]} (secret is never shown)")
        status, rows, message = connection_status()
        if status == STATUS_AUTH_ERROR:
            print("RESULT: CONNECTION FAILED (bad credentials)")
        elif status == STATUS_API_ERROR:
            print("RESULT: CONNECTION FAILED (network/API error)")
        elif status == STATUS_EMPTY:
            print("RESULT: CONNECTION SUCCEEDED -- 0 settlements returned")
        else:
            print(f"RESULT: CONNECTION SUCCEEDED -- {len(rows)} settlement row(s)")
        print(f"  {message}")
        for row in rows[:10]:
            print(" ", row)
    print("=" * 60)
