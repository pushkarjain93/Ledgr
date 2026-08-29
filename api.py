"""
Ledgr HTTP API.

The React frontend's only door into this project's Python core. Everything
below is a thin transport layer over modules that already exist and are
already verified -- engine.py (the deterministic 5-tier waterfall),
case_engine.py (batched Gemini investigation + evidence-hash caching +
the case lifecycle), state_store.py (per-merchant persistence),
razorpay_client.py / shopify_client.py (the two real data sources).

Hard rule for this file: it orchestrates and serialises, it does not
decide. No reconciliation logic, no matching rules, no confidence
scoring, no financial arithmetic lives here. If a number needs to be
computed, it is computed by the module that already owns that
responsibility and passed through untouched. This mirrors the same
boundary the old Streamlit app respected -- the UI layer was never
allowed to invent a figure, and neither is this one.

Money crosses this API as INTEGER PAISE, exactly as engine.py produces
it. Formatting to "Rs 1,234.56" is the frontend's job -- converting here
would mean two sources of truth for rounding, which is how reconciliation
tools quietly lose money.

Run:  uvicorn api:app --reload --port 8000
Docs: http://localhost:8000/docs
"""
import secrets
from datetime import datetime

import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import ai_client
import case_engine
import razorpay_client as rzp
import shopify_client as shopify
import state_store
from auth import authenticate, get_merchant_by_email
from config import (
    COD_FRESH_DAYS,
    COD_TOLERANCE_ABS,
    COD_TOLERANCE_PCT,
    COD_WARN_DAYS,
    FEE_TOLERANCE_ABS,
    FEE_TOLERANCE_PCT,
    RUN_DATE,
    fee_band,
    to_paise,
)
from engine import reconcile

app = FastAPI(title="Ledgr API", version="1.0.0")

# The Vite dev server. Tightened to explicit origins rather than "*"
# because these endpoints carry a session token.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Auth
#
# In-memory bearer tokens: token -> merchant dict. Deliberately simple and
# deliberately NOT production auth -- there is no expiry, no refresh, and
# every token is lost on restart. That is an honest match for auth.py's
# own hardcoded demo accounts; pretending otherwise would be security
# theatre. Real deployment would need real sessions.
# ---------------------------------------------------------------------------
_SESSIONS: dict[str, dict] = {}


def current_merchant(authorization: str | None = Header(default=None)) -> dict:
    """FastAPI dependency: resolves the bearer token to a merchant, or 401s."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    merchant = _SESSIONS.get(authorization.removeprefix("Bearer ").strip())
    if not merchant:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return merchant


def _load(merchant: dict):
    return state_store.load_state(merchant["merchant_id"])


def _save(merchant: dict, state) -> None:
    state_store.save_state(merchant["merchant_id"], state)


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------
class LoginBody(BaseModel):
    email: str
    password: str


class ResolveBody(BaseModel):
    resolution_type: str  # "accepted" | "manual_review"
    comment: str | None = None


class CommentBody(BaseModel):
    comment: str


class ReopenBody(BaseModel):
    reason: str


class DraftBody(BaseModel):
    recipient_type: str  # "gateway" | "courier" | "customer"


class AskTurn(BaseModel):
    question: str
    answer: str


class AskBody(BaseModel):
    question: str
    case_id: str | None = None
    # Recent turns, so follow-ups ("his name?", "what about that one?") have
    # an antecedent. Capped server-side -- see ask_ai.
    history: list[AskTurn] = []


# ---------------------------------------------------------------------------
# Shared data helpers -- the same reads the old Streamlit sync step used
# ---------------------------------------------------------------------------
def _local_settlements() -> pd.DataFrame:
    """RAZORPAY-sourced (demo) + BANK-sourced (COD) rows from the generated
    settlements.csv. Our mock orders' payment_ids only exist in this file --
    a real Razorpay Test Mode account has no relationship to synthetic data,
    so this is what orders actually reconcile against regardless of what the
    live Razorpay call returns."""
    import os

    path = os.path.join(shopify.DATA_DIR, "settlements.csv")
    return pd.read_csv(path, dtype=str).fillna("")


def _batch_frames(batch_ids: list[str], extra_order_ids: set[str] | None = None):
    """Build the (orders_df, settlements_df, order_rows, settlement_rows)
    that engine.reconcile() expects, for one or more batches. `extra_order_ids`
    re-includes still-open orders from EARLIER batches so a late-arriving
    settlement matches against them instead of looking like a fresh orphan --
    see state_store.pending_settlement_order_ids for why this matters."""
    extra_order_ids = extra_order_ids or set()
    order_rows = [
        o for o in shopify.fetch_orders()
        if o.get("batch_id") in batch_ids or o["order_id"] in extra_order_ids
    ]
    orders_df = pd.DataFrame(order_rows)
    if not orders_df.empty:
        orders_df["amount_paise"] = orders_df["order_amount"].map(to_paise)

    setls = _local_settlements()
    setls = setls[setls["batch_id"].isin(batch_ids)]
    settlements_df = setls.copy()
    if not settlements_df.empty:
        settlements_df["amount_paise"] = settlements_df["amount_received"].map(to_paise)

    return orders_df, settlements_df, order_rows, settlements_df.to_dict("records")


def _classify(result_df) -> dict:
    """Three mutually-exclusive buckets over the real engine output, summing
    exactly to total records. Built entirely from engine.py's own `status`
    and `ai_assisted` fields -- no invented model."""
    is_exception = result_df["status"] == "EXCEPTION"
    is_ai = result_df["ai_assisted"] & ~is_exception
    is_auto = ~result_df["ai_assisted"] & ~is_exception
    return {
        "auto_matched": int(is_auto.sum()),
        "ai_resolved": int(is_ai.sum()),
        "exceptions": int(is_exception.sum()),
        "total_records": int(len(result_df)),
        "expected_paise": int(result_df["expected"].sum()),
        "received_paise": int(result_df["received"].sum()),
    }


def _processed_batch_ids(state) -> list[str]:
    return [str(r["batch_id"]) for r in state.get("reconciliation_runs", [])]


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------
@app.post("/api/login")
def login(body: LoginBody):
    ok, merchant = authenticate(body.email, body.password)
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = secrets.token_urlsafe(32)
    _SESSIONS[token] = merchant
    return {"token": token, "merchant": merchant}


@app.post("/api/logout")
def logout(authorization: str | None = Header(default=None)):
    if authorization and authorization.startswith("Bearer "):
        _SESSIONS.pop(authorization.removeprefix("Bearer ").strip(), None)
    return {"ok": True}


@app.get("/api/me")
def me(merchant: dict = Depends(current_merchant)):
    return {"merchant": merchant}


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
@app.get("/api/state")
def get_state(merchant: dict = Depends(current_merchant)):
    """Everything the shell needs on load: batch progress, saved runs, the
    full case store, and whether a new batch is available right now.

    `run_date` is exposed deliberately -- all COD ageing in this project is
    measured against config.RUN_DATE, not the wall clock, so runs stay
    reproducible. The frontend must age cases against this same date or its
    buckets will silently disagree with the engine's own thresholds."""
    state = _load(merchant)
    return {
        "current_batch": state["current_batch"],
        "total_batches": state_store.TOTAL_BATCHES,
        "batch_available": state_store.batch_is_available(state),
        "next_batch_available_at": state.get("next_batch_available_at"),
        "notification_seen": state.get("notification_seen", True),
        "notification_batch": state.get("notification_batch"),
        "reconciliation_runs": state.get("reconciliation_runs", []),
        "cases": state.get("cases", {}),
        "run_date": RUN_DATE.isoformat(),
    }


@app.get("/api/sources")
def sources(merchant: dict = Depends(current_merchant)):
    """Live connection status for all three data sources. The Razorpay call
    is real; Shopify is honestly reported as mock data, never as 'connected'
    (see shopify_client.py's own docstring on why that label matters)."""
    rzp_status, rzp_rows, rzp_message = rzp.connection_status()
    shop_status, shop_rows, shop_message = shopify.connection_status()
    bank_rows = _local_settlements()
    bank_rows = bank_rows[bank_rows["source"] == "BANK"]
    return {
        "orders": {"name": "Shopify", "status": shop_status,
                   "message": shop_message, "count": len(shop_rows)},
        "settlements": {"name": "Razorpay", "status": rzp_status,
                        "message": rzp_message, "count": len(rzp_rows)},
        "bank": {"name": "Bank / COD", "status": "demo_data",
                 "message": f"Demo data -- {len(bank_rows)} bank credit(s).",
                 "count": len(bank_rows)},
    }


@app.get("/api/settings")
def settings(merchant: dict = Depends(current_merchant)):
    """The real tolerance policy engine.py enforces -- surfaced so the
    thresholds read as configurable policy rather than hidden magic numbers.
    Read-only: editing these would change reconciliation outcomes, which is
    not something this API is allowed to do."""
    return {
        "fee_tolerance_pct": FEE_TOLERANCE_PCT,
        "fee_tolerance_abs_paise": FEE_TOLERANCE_ABS,
        "cod_tolerance_pct": COD_TOLERANCE_PCT,
        "cod_tolerance_abs_paise": COD_TOLERANCE_ABS,
        "cod_fresh_days": COD_FRESH_DAYS,
        "cod_warn_days": COD_WARN_DAYS,
        "run_date": RUN_DATE.isoformat(),
        "ai_model": ai_client.MODEL,
        "ai_batch_size": ai_client.DEFAULT_BATCH_SIZE,
        # Providers with a key configured, in failover order. Shown so the
        # UI can be honest about how much AI capacity actually exists rather
        # than implying a single hardcoded vendor.
        "ai_providers": ai_client.available_providers(),
        "auto_resolve_confidence_floor": case_engine.AUTO_RESOLVE_CONFIDENCE_FLOOR,
        "total_batches": state_store.TOTAL_BATCHES,
    }


@app.post("/api/reset")
def reset(merchant: dict = Depends(current_merchant)):
    """Demo reset: wipes this merchant's progress/cases only. Never touches
    orders.csv / settlements.csv -- that's shared source data, not per-merchant
    state."""
    state_store.reset_state(merchant["merchant_id"])
    return {"ok": True}


# ---------------------------------------------------------------------------
# The main pipeline
# ---------------------------------------------------------------------------
@app.post("/api/sync-and-reconcile")
def sync_and_reconcile(merchant: dict = Depends(current_merchant)):
    """
    Runs the real pipeline for the next available batch, in the same order
    and through the same functions the old Streamlit flow used:

        fetch orders -> check Razorpay -> load bank/COD -> merge settlements
        -> engine.reconcile() -> build cases -> ONE batched AI pass -> persist

    Returns the completed steps with their real result lines, so the UI can
    render the same step list. Note honestly: the work is done by the time
    this responds, so the frontend animates completed steps rather than
    watching them live. Streaming (SSE) would be a genuine improvement, but
    is deliberately not faked here with artificial delays.
    """
    state = _load(merchant)
    if not state_store.batch_is_available(state):
        raise HTTPException(status_code=409, detail="No batch is currently available")

    batch_id = state["current_batch"]
    steps: list[dict] = []

    pending_ids = set(state_store.pending_settlement_order_ids(state))
    orders_df, settlements_df, order_rows, settlement_rows = _batch_frames(
        [str(batch_id)], extra_order_ids=pending_ids)
    if orders_df.empty:
        raise HTTPException(status_code=404, detail=f"No orders found for batch {batch_id}")
    note = f" (+{len(pending_ids)} re-evaluated pending)" if pending_ids else ""
    steps.append({"label": "Connecting to Shopify",
                  "result": f"{len(order_rows)} orders loaded{note}"})

    rzp_status, _rows, rzp_message = rzp.connection_status()
    steps.append({"label": "Connecting to Razorpay", "result": rzp_message})

    cod_count = int((settlements_df["source"] == "BANK").sum()) if not settlements_df.empty else 0
    steps.append({"label": "Loading COD / bank remittance data",
                  "result": f"{cod_count} bank credit(s) loaded"})

    source_note = ("live + demo" if rzp_status == rzp.STATUS_OK
                   else "demo -- Test Mode has no live settlements for these orders")
    steps.append({"label": "Merging settlement sources",
                  "result": f"{len(settlements_df)} settlement rows ready ({source_note})"})

    result_df = reconcile(orders_df, settlements_df)
    steps.append({"label": "Matching orders to settlements",
                  "result": f"{len(result_df)} records processed"})

    # Case layer: deterministic classification + evidence-hash cache check
    # first, then exactly one batched AI pass over whatever genuinely needs
    # investigating. Quota is only ever spent here.
    cases = case_engine.build_cases_for_batch(
        result_df, batch_id, order_rows, settlement_rows,
        previously_open_order_ids=pending_ids,
        existing_cases=state.get("cases", {}))
    needs_ai = sum(1 for c in cases if c.get("case_status") == "needs_ai")
    cases = case_engine.investigate_new_cases_batched(cases)
    case_engine.save_cases(state, cases)
    pending_after = sum(1 for c in cases if c.get("case_status") == "ai_pending")
    # Deliberately does not claim WHY a case is still pending -- ai_pending
    # is usually a rate limit but can be any transient failure, and the real
    # reason is already stored per-case in ai.error. Don't assert a cause
    # this line doesn't actually know.
    steps.append({
        "label": "AI investigation",
        "result": (f"{needs_ai} case(s) sent to AI"
                   + (f", {pending_after} still awaiting investigation" if pending_after else "")
                   if needs_ai else "No cases required AI investigation"),
    })

    run = {
        "run_id": f"RUN-{merchant['merchant_id']}-B{batch_id}",
        "batch_id": batch_id,
        "timestamp": datetime.now().isoformat(),
        "sources": "Shopify + Razorpay + Bank",
        "status": "Completed",
        **_classify(result_df),
    }
    state["reconciliation_runs"].insert(0, run)

    already = set(state["processed_record_ids"])
    order_ids = [o["order_id"] for o in order_rows]
    settlement_ids = settlements_df["settlement_id"].tolist() if not settlements_df.empty else []
    state["processed_record_ids"].extend(i for i in order_ids if i not in already)
    already.update(order_ids)
    state["processed_record_ids"].extend(i for i in settlement_ids if i not in already)

    state_store.schedule_next_batch(state, batch_id)
    _save(merchant, state)

    return {"run": run, "steps": steps, "cases": state.get("cases", {})}


@app.get("/api/transactions")
def transactions(merchant: dict = Depends(current_merchant)):
    """
    EVERY record from every reconciled batch -- including the ~80% that
    matched cleanly and never became a case. Recomputed by re-running the
    same deterministic engine over the already-processed batches rather
    than stored separately, so this can never drift from what the engine
    actually decided. Cheap at demo volumes; would want an "open items"
    ledger at real scale (see CLAUDE.md's note on that).
    """
    state = _load(merchant)
    batch_ids = _processed_batch_ids(state)
    if not batch_ids:
        return {"records": [], "total": 0}

    orders_df, settlements_df, order_rows, _s = _batch_frames(batch_ids)
    if orders_df.empty:
        return {"records": [], "total": 0}
    result_df = reconcile(orders_df, settlements_df)

    orders_by_id = {o["order_id"]: o for o in order_rows}
    cases_by_record = {c["record_id"]: c["case_id"] for c in state.get("cases", {}).values()}
    records = []
    for r in result_df.to_dict("records"):
        age = r.get("age_days")
        order = orders_by_id.get(r["record_id"])
        records.append({
            "record_id": r["record_id"],
            "order_date": order.get("order_date", "") if order else "",
            "payment_mode": order.get("payment_mode", "") if order else "",
            "tier": int(r["tier"]),
            "tier_name": r["tier_name"],
            "status": r["status"],
            "reason": r["reason"],
            "reason_label": r["reason_label"],
            "expected": int(r["expected"]),
            "received": int(r["received"]),
            "delta": int(r["delta"]),
            "amount_at_risk": int(r["amount_at_risk"]),
            "priority": r["priority"],
            "explanation": r["explanation"],
            "matched_settlement": r["matched_settlement"],
            "age_days": (None if age is None or pd.isna(age) else int(age)),
            "ai_assisted": bool(r["ai_assisted"]),
            "case_id": cases_by_record.get(r["record_id"]),
        })
    return {"records": records, "total": len(records)}


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------
@app.get("/api/cases")
def list_cases(case_status: str | None = None, case_type: str | None = None,
               merchant: dict = Depends(current_merchant)):
    state = _load(merchant)
    return {"cases": state_store.list_cases(state, case_status=case_status,
                                            case_type=case_type)}


@app.get("/api/cases/{case_id}")
def get_case(case_id: str, merchant: dict = Depends(current_merchant)):
    case = state_store.get_case(_load(merchant), case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@app.get("/api/cases/{case_id}/evidence")
def case_evidence(case_id: str, merchant: dict = Depends(current_merchant)):
    """
    The real underlying records behind a case -- what the "Supporting
    Documents" panel shows.

    Read straight from the same orders.csv / settlements.csv the engine
    itself reconciled, so this can never drift from what was actually
    matched. Any section with no real record behind it comes back as null
    rather than an empty shell, so the UI can hide it instead of showing a
    document that doesn't exist (an orphan settlement genuinely has no
    order; a still-unmatched order genuinely has no settlement).

    `fee_structure` is the actual Tier-2 tolerance band config.fee_band()
    applies to THIS order -- the same rule the engine used to decide whether
    the shortfall was an explainable fee. Not a static reference table.
    """
    state = _load(merchant)
    case = state_store.get_case(state, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    order = None
    if case.get("order_id"):
        order = next((o for o in shopify.fetch_orders()
                      if o["order_id"] == case["order_id"]), None)

    settlement = None
    if case.get("settlement_id"):
        setls = _local_settlements()
        match = setls[setls["settlement_id"] == case["settlement_id"]]
        if not match.empty:
            settlement = match.iloc[0].to_dict()

    order_block = None
    fee_block = None
    if order:
        amount_paise = to_paise(order.get("order_amount") or 0)
        mode = order.get("payment_mode") or ""
        order_block = {
            "order_id": order["order_id"],
            "order_date": order.get("order_date", ""),
            "customer_name": order.get("customer_name", ""),
            "customer_phone": order.get("customer_phone", ""),
            "customer_email": order.get("customer_email", ""),
            "courier": order.get("courier", ""),
            "payment_mode": mode,
            "gateway_ref_id": order.get("gateway_ref_id", ""),
            "bank_utr": order.get("bank_utr", ""),
            "amount": amount_paise,
            "source": "Shopify (demo data)",
        }
        band = fee_band(amount_paise, mode)
        is_cod = mode == "COD"
        # A fee-band comparison only means something once money has actually
        # arrived. For an order with NO settlement at all, delta is 0 simply
        # because there was nothing to compare -- reporting that as a 0.00
        # shortfall "within band" would imply the payment is fine when the
        # entire amount is missing. Mark it not-comparable instead.
        received = int(case.get("received") or 0)
        comparable = received > 0
        shortfall = max(0, int(case.get("expected") or 0) - received) if comparable else None
        fee_block = {
            "payment_mode": mode,
            "tolerance_pct": COD_TOLERANCE_PCT if is_cod else FEE_TOLERANCE_PCT,
            "tolerance_flat": COD_TOLERANCE_ABS if is_cod else FEE_TOLERANCE_ABS,
            "order_amount": amount_paise,
            "max_explainable_shortfall": band,
            "comparable": comparable,
            "actual_shortfall": shortfall,
            "within_band": (shortfall <= band) if comparable else None,
        }

    settlement_block = None
    if settlement:
        settlement_block = {
            "settlement_id": settlement["settlement_id"],
            "settled_on": settlement.get("settled_on", ""),
            "amount_received": to_paise(settlement.get("amount_received") or 0),
            "gateway_ref_id": settlement.get("gateway_ref_id", ""),
            "bank_utr": settlement.get("bank_utr", ""),
            "source": settlement.get("source", ""),
            "narration": settlement.get("narration", ""),
        }

    return {
        "order": order_block,
        "settlement": settlement_block,
        "fee_structure": fee_block,
        "history": case.get("history", []),
    }


@app.get("/api/cases/{case_id}/message-options")
def message_options(case_id: str, merchant: dict = Depends(current_merchant)):
    """
    Who it makes sense to contact about this case, and whether we actually
    hold an address for them.

    Recipients are derived from the case's own facts, not offered blindly:
    there is no point drafting a courier chase for an online card payment,
    or a customer email for an orphan settlement with no customer attached.

    `address` is empty when we genuinely don't have one -- courier and
    gateway support addresses are not in this dataset. The UI must show
    that plainly; inventing "support@razorpay.com" would be fabricating
    contact details.
    """
    state = _load(merchant)
    case = state_store.get_case(state, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    order = None
    if case.get("order_id"):
        order = next((o for o in shopify.fetch_orders()
                      if o["order_id"] == case["order_id"]), None)
    mode = (order or {}).get("payment_mode", "")
    courier = (order or {}).get("courier", "")
    options = []

    if mode == "COD" and courier:
        options.append({
            "recipient_type": "courier", "label": f"Courier ({courier})",
            "address": "",
            "note": f"No email on file for {courier} — copy the draft into your own thread.",
            "why": "COD cash is collected by the courier and remitted separately.",
        })
    if mode and mode != "COD":
        options.append({
            "recipient_type": "gateway", "label": "Payment gateway (Razorpay)",
            "address": "",
            "note": "No support address on file — copy the draft into your gateway ticket.",
            "why": "The payment was taken online, so the gateway holds the transaction record.",
        })
    if order and order.get("customer_email"):
        options.append({
            "recipient_type": "customer",
            "label": f"Customer ({order.get('customer_name') or 'unknown'})",
            "address": order["customer_email"],
            "note": "",
            "why": "The customer can confirm what they were charged or paid.",
        })

    return {"options": options}


@app.post("/api/cases/{case_id}/draft-message")
def draft_message(case_id: str, body: DraftBody,
                  merchant: dict = Depends(current_merchant)):
    """
    Draft an outbound message about this case.

    DRAFTS ONLY. This endpoint never sends anything, and there is no send
    endpoint -- the drafted text goes back to the UI for a human to read,
    edit, and send from their own mail client. That boundary is deliberate:
    a reconciliation tool must never message a customer or a gateway
    autonomously about money.
    """
    if body.recipient_type not in ("gateway", "courier", "customer"):
        raise HTTPException(status_code=400, detail="Unknown recipient type")

    state = _load(merchant)
    case = state_store.get_case(state, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    context = case_engine.build_ask_context(state, case_id=case_id)
    try:
        draft = ai_client.draft_message(
            context, body.recipient_type, merchant.get("company_name", ""))
    except ai_client.AIRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except (ai_client.AIAuthError, ai_client.AIAPIError) as exc:
        raise HTTPException(status_code=503, detail=f"AI is temporarily unavailable: {exc}")

    return {
        "subject": draft.get("subject", ""),
        "body": draft.get("body", ""),
        "facts_used": draft.get("facts_used", []),
        "recipient_type": body.recipient_type,
        "provider": ai_client.last_provider(),
    }


@app.post("/api/cases/{case_id}/resolve")
def resolve_case(case_id: str, body: ResolveBody,
                 merchant: dict = Depends(current_merchant)):
    """
    Records a real human decision.

    The mandatory-comment rule for manual review is enforced HERE, not only
    in the UI -- a reviewer's justification is the audit trail, and an API
    that accepts an unexplained manual escalation makes that trail
    optional. Accepting an AI recommendation may fall back to the model's
    own next_step text, which is a real stored string, never invented.
    """
    if body.resolution_type not in ("accepted", "manual_review"):
        raise HTTPException(status_code=400, detail="Invalid resolution_type")

    state = _load(merchant)
    case = state_store.get_case(state, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    comment = (body.comment or "").strip()
    if body.resolution_type == "manual_review" and not comment:
        raise HTTPException(
            status_code=400,
            detail="A comment is required when keeping a case for manual review")
    if body.resolution_type == "accepted" and not comment:
        comment = (case.get("ai") or {}).get("next_step") or ""

    updated = state_store.record_resolution(state, case_id, body.resolution_type,
                                            comment=comment)
    _save(merchant, state)
    return updated


@app.post("/api/cases/{case_id}/reopen")
def reopen_case(case_id: str, body: ReopenBody,
                merchant: dict = Depends(current_merchant)):
    """Send a resolved case back to the review queue after a mistaken click.
    Requires a reason for the audit trail. System auto-resolved cases cannot
    be reopened through this endpoint."""
    reason = (body.reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="A reason is required to reopen a case")

    state = _load(merchant)
    case = state_store.get_case(state, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if not case.get("resolution", {}).get("resolved"):
        raise HTTPException(status_code=400, detail="Case is not resolved")
    if case.get("resolution", {}).get("resolution_type") == "auto_resolved":
        raise HTTPException(
            status_code=400,
            detail="Auto-resolved cases cannot be reopened — bookmark the case to flag it")

    updated = state_store.record_reopen(state, case_id, reason)
    if updated is None:
        raise HTTPException(status_code=400, detail="Case could not be reopened")
    _save(merchant, state)
    return updated


@app.post("/api/cases/{case_id}/bookmark")
def toggle_bookmark(case_id: str, merchant: dict = Depends(current_merchant)):
    state = _load(merchant)
    result = state_store.toggle_bookmark(state, case_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Case not found")
    _save(merchant, state)
    return {"case_id": case_id, "bookmarked": result}


@app.post("/api/cases/{case_id}/comment")
def set_comment(case_id: str, body: CommentBody,
                merchant: dict = Depends(current_merchant)):
    state = _load(merchant)
    updated = state_store.set_comment(state, case_id, body.comment)
    if updated is None:
        raise HTTPException(status_code=404, detail="Case not found")
    _save(merchant, state)
    return updated


@app.post("/api/cases/{case_id}/retry-ai")
def retry_ai(case_id: str, merchant: dict = Depends(current_merchant)):
    """Re-attempt a case left ai_pending by a rate limit. User-triggered
    only -- nothing in this system retries a failed AI call on its own."""
    state = _load(merchant)
    if not state_store.get_case(state, case_id):
        raise HTTPException(status_code=404, detail="Case not found")
    case_engine.retry_pending_cases(state, [case_id])
    _save(merchant, state)
    return state_store.get_case(state, case_id)


@app.post("/api/cases/{case_id}/investigate-further")
def investigate_further(case_id: str, merchant: dict = Depends(current_merchant)):
    """
    The one controlled agentic step: fetch whatever additional evidence is
    genuinely available for this case's named missing_evidence, then make
    exactly ONE more AI call for a final verdict. Never automatic, never
    looped beyond that single extra call.

    `previous_confidence` is stashed so the UI can show a real before/after
    delta -- a diff of two genuine scores, not a fabricated trend.
    """
    state = _load(merchant)
    case = state_store.get_case(state, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if not case.get("ai"):
        raise HTTPException(status_code=400,
                            detail="This case has not been investigated yet")

    prior = (case.get("ai") or {}).get("confidence")
    updated = case_engine.investigate_case_followup(state, case_id, shopify.fetch_orders())
    if updated and updated.get("ai") and prior is not None:
        if updated["ai"].get("confidence") is not None:
            updated["ai"]["previous_confidence"] = prior
    _save(merchant, state)
    return state_store.get_case(state, case_id)


# ---------------------------------------------------------------------------
# Ask AI
# ---------------------------------------------------------------------------
@app.post("/api/ask-ai")
def ask_ai(body: AskBody, merchant: dict = Depends(current_merchant)):
    """
    Direct-answer-first: most questions are answerable straight from
    already-persisted data via pandas, at zero API cost. Gemini is only
    asked what Python genuinely cannot answer.

    `source` is returned so the UI can be honest about which path ran.
    This endpoint is read-only -- asking a question must never change a
    case's status or resolution.
    """
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    state = _load(merchant)
    context = case_engine.build_ask_context(state, case_id=body.case_id)
    try:
        # Only the last few turns: enough for pronouns to resolve, without
        # growing the prompt unboundedly as a session goes on.
        history = [h.model_dump() for h in body.history][-6:]
        answer = ai_client.ask(question, context, history=history)
        return {"answer": answer, "source": ai_client.last_provider() or "ai"}
    except (ai_client.AIRateLimitError, ai_client.AIAuthError, ai_client.AIAPIError) as exc:
        # Every provider is down or exhausted. The deterministic answerer can
        # still handle a few common questions from persisted data -- better a
        # correct partial answer than nothing. It is ONLY a fallback: it does
        # keyword matching, so on the primary path it can confidently answer
        # the wrong question (e.g. reading "how much manual work did we
        # eliminate" as an outstanding-total query), which is worse than
        # spending an API call.
        fallback = case_engine.try_direct_answer(question, state)
        if fallback is not None:
            return {"answer": fallback, "source": "python"}
        if isinstance(exc, ai_client.AIRateLimitError):
            raise HTTPException(status_code=429, detail=str(exc))
        raise HTTPException(status_code=503, detail=f"AI is temporarily unavailable: {exc}")


@app.get("/api/health")
def health():
    return {"ok": True}
