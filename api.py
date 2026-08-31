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
import os
import secrets
import threading
import time
from datetime import datetime

import pandas as pd
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import ai_client
import case_engine
import razorpay_client as rzp
import shopify_client as shopify
import remittance
import state_store
from auth import authenticate, get_merchant_by_email
import config
from config import (
    fmt,
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
from engine import reconcile, score_metrics

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
def _cases_with_payment_mode(state) -> dict:
    """The case store keyed by case_id, each enriched with payment_mode.

    /api/state is what the UI's context actually reads, so anything the case
    LIST needs must be attached here too -- attaching it only to /api/cases
    leaves every row showing a blank payment mode.
    """
    orders_by_id = {o["order_id"]: o for o in shopify.fetch_orders()}
    return {cid: _with_payment_mode(c, orders_by_id)
            for cid, c in (state.get("cases") or {}).items()}


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
        "cases": _cases_with_payment_mode(state),
        # Cases still queued for AI. The UI polls until this reaches zero.
        "ai_in_progress": sum(1 for c in (state.get("cases") or {}).values()
                              if c.get("case_status") == "needs_ai"),
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
        # Courier remittance detail belongs to THIS source -- it is the
        # per-order breakdown behind a bank credit, not a separate
        # integration, so it is reported here rather than as a fourth source.
        "bank": {"name": "Bank / COD", "status": "demo_data",
                 "message": (f"Demo data -- {len(bank_rows)} bank credit(s), "
                             f"{len(remittance.load_remittances())} remittance detail row(s)."),
                 "count": len(bank_rows),
                 "remittance_rows": len(remittance.load_remittances())},
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
        # The auto-resolve gate is EXPOSURE-based, not confidence-based. This
        # used to report case_engine.AUTO_RESOLVE_CONFIDENCE_FLOOR, which was
        # deleted when confidence scores were removed (they carried almost no
        # signal -- 83% of them were exactly 10). Nothing in the UI reads this
        # endpoint, so the stale attribute went unnoticed and returned a 500.
        "auto_resolve_max_pct": case_engine.AUTO_RESOLVE_MAX_PCT,
        "auto_resolve_max_abs_paise": case_engine.AUTO_RESOLVE_MAX_ABS,
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
# ---------------------------------------------------------------------------
# Background AI investigation
#
# Reconciliation itself takes well under a second; the AI pass takes tens of
# seconds because free-tier providers are slow and throttled. Blocking the Sync
# button on it made a ~1s operation feel like a 30-60s one. So the request now
# returns as soon as the real reconciliation is done -- every case exists
# immediately, marked `needs_ai` -- and verdicts fill in behind it.
#
# The UI polls /api/state and watches `ai_in_progress` fall to zero.
# ---------------------------------------------------------------------------
# Per-minute provider budgets recover, so a rate-limited chunk is retried a
# few times before being given up on. Nobody is waiting on this work.
#
# Sized against the real constraint: Groq is the only consistently-available
# provider and caps TOKENS PER MINUTE (8000). A full first batch is ~29
# AI-eligible cases = 6 chunks of 5, and each chunk reserves prompt + max_tokens
# (~3.2k), so the whole set genuinely cannot clear in under ~2-3 minutes no
# matter how it is scheduled. Three rounds spanned only ~105s, which is why a
# third of the cases were still `ai_pending` when the user looked. Six rounds
# covers ~210s with headroom.
AI_RETRY_ROUNDS = int(os.environ.get("AI_RETRY_ROUNDS", "6"))
AI_RETRY_DELAY_SECONDS = int(os.environ.get("AI_RETRY_DELAY_SECONDS", "35"))

_state_lock = threading.Lock()


def _merge_investigated(merchant_id: str, investigated: list[dict]) -> None:
    """Merge AI verdicts back into stored state, preserving human decisions.

    Re-reads state under a lock before writing: the user may have resolved or
    bookmarked something while this was running, and a blind overwrite would
    silently discard their action.
    """
    with _state_lock:
        fresh = state_store.load_state(merchant_id)
        for case in investigated:
            existing = state_store.get_case(fresh, case["case_id"])
            # The case is gone from current state -- the demo was reset (or
            # the batch re-run) while this pass was in flight. Writing it
            # back would RESURRECT deleted cases, which is exactly what
            # happened once: batch-2 cases reappeared after a reset and
            # outlived the run that created them, leaving AI reasoning that
            # referenced orders no longer in the ledger.
            if not existing:
                continue
            # A human decision taken while AI was thinking always wins.
            if existing.get("resolution", {}).get("resolved"):
                continue
            state_store.upsert_case(fresh, case)
        state_store.save_state(merchant_id, fresh)


def _investigate_in_background(merchant_id: str, case_ids: list[str]) -> None:
    """Investigate the given cases, then merge results back into stored state.

    Re-reads state under a lock before writing: the user may have resolved or
    bookmarked something while this was running, and a blind overwrite would
    silently discard their action.
    """
    try:
        state = state_store.load_state(merchant_id)
        pending = [c for c in state_store.list_cases(state) if c["case_id"] in set(case_ids)]
        if not pending:
            return
        investigated = case_engine.investigate_new_cases_batched(pending)
        # Persist after EVERY round, not once at the end. Retries can span
        # several minutes; holding all verdicts until the last round meant the
        # UI showed nothing filling in for the whole window, and a crash or
        # restart part-way through discarded every verdict already paid for.
        _merge_investigated(merchant_id, investigated)

        # Free tiers cap TOKENS PER MINUTE, so a large batch routinely exhausts
        # the budget partway and leaves most cases `ai_pending`. That limit
        # RECOVERS on its own -- and since nobody is waiting on this request,
        # we can simply pause and pick up the rest. Bounded retries only; if
        # capacity genuinely never returns the cases stay honestly `ai_pending`
        # and the user can retry them by hand.
        for _ in range(AI_RETRY_ROUNDS):
            stuck = [c for c in investigated if c.get("case_status") == "ai_pending"]
            if not stuck:
                break
            time.sleep(AI_RETRY_DELAY_SECONDS)
            for c in stuck:
                c["case_status"] = "needs_ai"
            case_engine.investigate_new_cases_batched(stuck)
            _merge_investigated(merchant_id, stuck)
    except Exception as exc:  # never let a worker crash take the server with it
        print(f"[background AI] {merchant_id}: {type(exc).__name__}: {exc}")


@app.post("/api/sync-and-reconcile")
def sync_and_reconcile(background: BackgroundTasks,
                        merchant: dict = Depends(current_merchant)):
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
    # Courier remittance detail -- part of the existing Bank / COD source, not
    # a new one. Deterministic join: a bulk credit's own paperwork names the
    # orders it paid, so no model is asked to guess the grouping.
    #
    # Scoped to EXACTLY the batch whose orders and settlements were loaded
    # above. The scope has to match on both sides: reading the whole file
    # surfaced batch 2's rows during batch 1 (a credit that had not arrived
    # yet), and reading every processed batch surfaced batch 1's rows during
    # batch 2, whose orders are no longer in scope -- reporting real orders as
    # "not in our order book".
    remit_rows = [r for r in remittance.load_remittances()
                  if str(r.get("batch_id", "")) == str(batch_id)]
    if remit_rows:
        remit = remittance.reconcile_remittances(remit_rows, order_rows, settlement_rows)
        case_engine.apply_remittance_to_cases(cases, remit, batch_id)
        linked = len(remit["links"])
        issues = len(remit["discrepancies"])
        steps.append({
            "label": "Courier remittance detail",
            "result": (f"{linked} order(s) matched to bulk remittances"
                       + (f", {issues} discrepancy(ies) raised" if issues else "")
                       if linked or issues else "No bulk remittances to match"),
        })

    needs_ai_ids = [c["case_id"] for c in cases if c.get("case_status") == "needs_ai"]
    needs_ai = len(needs_ai_ids)
    case_engine.save_cases(state, cases)
    # Deliberately does not claim WHY a case is still pending -- ai_pending
    # is usually a rate limit but can be any transient failure, and the real
    # reason is already stored per-case in ai.error. Don't assert a cause
    # this line doesn't actually know.
    steps.append({
        "label": "AI investigation",
        "result": (f"{needs_ai} case(s) queued — verdicts will appear shortly"
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

    if needs_ai_ids:
        background.add_task(_investigate_in_background,
                            merchant["merchant_id"], needs_ai_ids)

    return {"run": run, "steps": steps, "cases": _cases_with_payment_mode(state),
            "ai_queued": len(needs_ai_ids)}


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
            "record_kind": "order",
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
    # ---- settlement side ----------------------------------------------
    # reconcile() emits every ORDER plus orphan credits, but a settlement that
    # was considered and not matched (e.g. two settlements claiming the same
    # payment ref, where the engine correctly refused to pick) is emitted
    # nowhere. That left most of the settlement feed invisible: a user -- or an
    # AI cross-link -- searching for STL-00014-D found nothing, even though the
    # record exists and is central to the case. The ledger claims to cover
    # "orders and settlements", so it has to actually contain both.
    already = {r["record_id"] for r in records}
    matched = _matched_settlement_map(state)
    for srow in settlements_df.to_dict("records"):
        sid = srow.get("settlement_id", "")
        if not sid or sid in already:
            continue
        amount = to_paise(srow.get("amount_received") or 0)
        matched_order = matched.get(sid)
        records.append({
            "record_id": sid,
            "record_kind": "settlement",
            # Settlements have a settled_on, not an order date. Reusing the
            # same field keeps the existing date filter working for both.
            "order_date": srow.get("settled_on", ""),
            "payment_mode": "",
            "tier": None,
            "tier_name": "Settlement feed",
            "status": "MATCHED" if matched_order else "UNMATCHED",
            "reason": "",
            "reason_label": (f"Reconciled to {matched_order}" if matched_order
                             else "No order matched to this credit"),
            "expected": 0,
            "received": amount,
            "delta": 0,
            # Money already reconciled to an order is not at risk; an
            # unclaimed credit is money that cannot be accounted for.
            "amount_at_risk": 0 if matched_order else amount,
            "priority": "",
            "explanation": (
                f"Settlement of {fmt(amount)} from {srow.get('source', '')} on "
                f"{srow.get('settled_on', '')}."
                + (f" Reconciled to order {matched_order}." if matched_order
                   else " No order in the feed claims this credit.")),
            "matched_settlement": matched_order or "",
            "age_days": None,
            "ai_assisted": False,
            "case_id": cases_by_record.get(sid),
        })

    return {"records": records, "total": len(records)}


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------
def _with_payment_mode(case: dict, orders_by_id: dict | None = None) -> dict:
    """
    Attach the order's payment_mode to a case for display.

    Read from the order feed rather than stored on the case, so it works for
    cases created before this field existed -- no re-sync required. Blank when
    the case has no order side (an orphan settlement genuinely has no payment
    mode) rather than guessed.
    """
    if not case:
        return case
    if orders_by_id is None:
        orders_by_id = {o["order_id"]: o for o in shopify.fetch_orders()}
    order = orders_by_id.get(case.get("order_id") or "")
    return {**case, "payment_mode": (order or {}).get("payment_mode", "")}


@app.get("/api/cases")
def list_cases(case_status: str | None = None, case_type: str | None = None,
               merchant: dict = Depends(current_merchant)):
    state = _load(merchant)
    cases = state_store.list_cases(state, case_status=case_status, case_type=case_type)
    orders_by_id = {o["order_id"]: o for o in shopify.fetch_orders()}
    return {"cases": [_with_payment_mode(c, orders_by_id) for c in cases]}


@app.get("/api/cases/{case_id}")
def get_case(case_id: str, merchant: dict = Depends(current_merchant)):
    case = state_store.get_case(_load(merchant), case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return _with_payment_mode(case)


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


def _matched_settlement_map(state) -> dict:
    """
    settlement_id -> the record it is already reconciled to, across every
    processed batch.

    Derived by re-running the engine rather than read from the case store,
    because CLEANLY MATCHED records never become cases -- reading only the
    case store would report the vast majority of settlements as unmatched.
    Handing that to the follow-up investigation would be actively misleading:
    an exact-amount settlement described as "unmatched" invites the model to
    conclude it belongs to this order when it is already reconciled elsewhere.
    """
    batch_ids = _processed_batch_ids(state)
    if not batch_ids:
        return {}
    orders_df, settlements_df, _o, _s = _batch_frames(batch_ids)
    if orders_df.empty:
        return {}
    result_df = reconcile(orders_df, settlements_df)
    out = {}
    for r in result_df.to_dict("records"):
        sid = r.get("matched_settlement")
        # An orphan credit is emitted with matched_settlement == its OWN id
        # (self-referential); that is not "matched to an order".
        if sid and sid != r["record_id"]:
            out[sid] = r["record_id"]
    return out


@app.get("/api/cases/{case_id}/message-options")
def message_options(case_id: str, merchant: dict = Depends(current_merchant)):
    """
    Who it makes sense to contact about this case, and whether we actually
    hold an address for them.

    Recipients are derived from the case's own facts, not offered blindly:
    there is no point drafting a courier chase for an online card payment,
    or a customer email for an orphan settlement with no customer attached.

    Courier and gateway addresses come from config.py's DEMO contact table
    and are flagged `is_demo: true`. They are on the RFC-2606 reserved
    example.com domain, so they are unroutable by construction -- the flow
    can be demonstrated end to end without any chance of a draft reaching a
    real stranger's inbox. A customer address, by contrast, is real data off
    the order and is never flagged.

    `address` is still empty when we genuinely hold nothing (an unknown
    courier), and the UI must say so rather than invent one.
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
        addr = config.courier_contact(courier)
        options.append({
            "recipient_type": "courier", "label": f"Courier ({courier})",
            "address": addr,
            "is_demo": bool(addr),
            "note": (
                "Demo remittance address — replace with the courier's real desk before sending."
                if addr
                else f"No email on file for {courier} — copy the draft into your own thread."
            ),
            "why": "COD cash is collected by the courier and remitted separately.",
        })
    if mode and mode != "COD":
        options.append({
            "recipient_type": "gateway", "label": "Payment gateway (Razorpay)",
            "address": config.GATEWAY_CONTACT,
            "is_demo": True,
            "note": "Demo support address — replace with your real gateway ticket contact.",
            "why": "The payment was taken online, so the gateway holds the transaction record.",
        })
    if order and order.get("customer_email"):
        options.append({
            "recipient_type": "customer",
            "label": f"Customer ({order.get('customer_name') or 'unknown'})",
            "address": order["customer_email"],
            # Real data off the order, not a placeholder.
            "is_demo": False,
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
    # Settlements + which are already reconciled elsewhere, so the follow-up can
    # search for a settlement this order might actually belong to.
    settlements = _local_settlements().to_dict("records")
    matched = _matched_settlement_map(state)
    updated = case_engine.investigate_case_followup(
        state, case_id, shopify.fetch_orders(), settlements, matched)
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


@app.get("/api/reports")
def reports(merchant: dict = Depends(current_merchant)):
    """
    The evidence page: measured accuracy, where the money sits, what the
    system could NOT resolve, and how that was decided.

    Accuracy comes from engine.score_metrics() -- the same scorecard the CLI
    prints -- graded against the labelled ground_truth.csv. Nothing here is
    estimated or projected; every figure is a count or a ratio over records
    the engine actually processed.
    """
    state = _load(merchant)
    batch_ids = _processed_batch_ids(state)
    if not batch_ids:
        return {"has_data": False}

    orders_df, settlements_df, _o, _s = _batch_frames(batch_ids)
    result_df = reconcile(orders_df, settlements_df)
    accuracy = score_metrics(result_df)

    cases = state_store.list_cases(state)
    open_cases = [c for c in cases if not c.get("resolution", {}).get("resolved")]

    # --- exceptions the system could not resolve, grouped by what went wrong
    by_type: dict[str, dict] = {}
    for c in open_cases:
        t = c["case_type"]
        row = by_type.setdefault(t, {"case_type": t, "count": 0, "amount_at_risk": 0})
        row["count"] += 1
        row["amount_at_risk"] += int(c.get("amount_at_risk") or 0)
    exceptions = sorted(by_type.values(), key=lambda r: -r["amount_at_risk"])

    # --- how AI actually performed, from stored verdicts only
    investigated = [c for c in cases if (c.get("ai") or {}).get("investigated_at")]
    providers: dict[str, int] = {}
    for c in investigated:
        p = (c.get("ai") or {}).get("provider")
        if p:
            providers[p] = providers.get(p, 0) + 1
    ai_actions: dict[str, int] = {}
    for c in investigated:
        a = (c.get("ai") or {}).get("action") or "unknown"
        ai_actions[a] = ai_actions.get(a, 0) + 1

    runs = state.get("reconciliation_runs", [])
    return {
        "has_data": True,
        "generated_at": datetime.now().isoformat(),
        "accuracy": accuracy,
        "coverage": {
            "records_processed": accuracy["total_records"],
            "records_labelled": accuracy["records_scored"],
            # Orphan credits have no order-side label in ground_truth.csv, so
            # they are processed but not graded. Stated rather than hidden --
            # quietly scoring only the easy subset would inflate the result.
            "records_unlabelled": accuracy["processed_not_labelled"],
        },
        "throughput": {
            "runs": len(runs),
            "records_total": sum(int(r.get("total_records") or 0) for r in runs),
            "last_run_at": runs[0]["timestamp"] if runs else None,
        },
        "money": {
            "expected": int(result_df["expected"].sum()),
            "received": int(result_df["received"].sum()),
            "at_risk_open": sum(int(c.get("amount_at_risk") or 0) for c in open_cases),
            "recovered": sum(int(c.get("amount_at_risk") or 0) for c in cases
                             if c.get("resolution", {}).get("resolved")),
        },
        "exceptions": exceptions,
        "ai": {
            "cases_investigated": len(investigated),
            "actions": ai_actions,
            "providers": providers,
            "never_reached": sum(1 for c in cases if c["case_status"] == "ai_pending"),
            "model_batch_size": ai_client.DEFAULT_BATCH_SIZE,
            "providers_configured": ai_client.available_providers(),
        },
    }


@app.get("/api/health")
def health():
    return {"ok": True}
