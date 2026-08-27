"""
Post-reconciliation case layer for Ledgr.

Sits STRICTLY AFTER engine.reconcile() -- nothing here ever changes what
tier or status a record lands on. It turns the deterministic engine's
per-record output into persistent, trackable "cases" (state_store.py's
`cases` dict), and runs the real AI investigation for the case types
engine.py's own ai_diagnose() doesn't already cover: ambiguous
multi-candidate matches and orphan/unmatched settlement correlation
(both Tier 5). The Tier 3/4 variance path is already investigated inside
engine.py itself (ai_diagnose -> _llm_diagnose -> ai_client.diagnose) --
this module does not re-investigate those, it only wraps their existing
result into the same case-store shape everything else uses, so the UI
has one consistent model regardless of which layer produced the AI output.
"""
from datetime import date, datetime

import ai_client
import state_store
from config import fmt, to_paise

# Confidence floor below which an AI "resolve" recommendation is downgraded
# to manual_review regardless of what the model said -- mirrors this
# project's standing "never auto-clear without justification" rule.
AUTO_RESOLVE_CONFIDENCE_FLOOR = 85


def _case_type_for(row, is_ambiguous, is_orphan_settlement):
    if row["status"] in ("AWAITING_REMITTANCE", "APPROACHING_THRESHOLD"):
        return "pending_settlement"
    if row["status"] == "EXCEPTION" and row["reason"] == "R2_REMITTANCE_OVERDUE":
        return "remittance_overdue"
    if row["ai_assisted"]:
        return "overpayment" if row["delta"] > 0 else "partial_payment"
    if is_ambiguous:
        return "ambiguous_match"
    if is_orphan_settlement:
        return "unmatched_settlement"
    if row["status"] == "EXCEPTION":
        return "unmatched_order"
    return "exception"


def _find_orphan_candidates(settlement_amount_paise, settled_on, orders_lookup, max_candidates=5):
    """
    Real candidate search for an orphan settlement (a credit with no
    order matched to it): every order in the currently-known dataset
    within a tight amount tolerance, ranked by amount closeness THEN date
    proximity to the settlement's settled_on date -- amount alone is a
    weak signal here since order prices are drawn from a small repeating
    set, so several unrelated orders can genuinely share one amount; date
    proximity is what actually distinguishes a likely origin order from a
    coincidental price match. Returns [] honestly when nothing plausible
    exists -- never fabricates a candidate to fill the list. `orders_lookup`
    is the raw order dicts (order_amount as a rupee string, e.g. from
    shopify_client.fetch_orders()) -- amounts are converted here.
    """
    tolerance = max(100, int(settlement_amount_paise * 0.01))  # Rs 1 or 1%, whichever is larger
    settled_date = None
    if settled_on:
        try:
            settled_date = date.fromisoformat(str(settled_on))
        except ValueError:
            settled_date = None

    candidates = []
    for o in orders_lookup:
        amt = to_paise(o["order_amount"])
        if abs(amt - settlement_amount_paise) > tolerance:
            continue
        order_date_str = o.get("order_date", "")
        days_apart = None
        if settled_date and order_date_str:
            try:
                days_apart = abs((settled_date - date.fromisoformat(order_date_str)).days)
            except ValueError:
                days_apart = None
        candidates.append({
            "order_id": o["order_id"], "amount_paise": amt,
            "order_date": order_date_str, "days_from_settlement": days_apart,
            "customer_name": o.get("customer_name", ""),
            "payment_mode": o.get("payment_mode", ""),
        })
    candidates.sort(key=lambda c: (abs(c["amount_paise"] - settlement_amount_paise),
                                    c["days_from_settlement"] if c["days_from_settlement"] is not None else 999))
    return candidates[:max_candidates]


def build_cases_for_batch(result_df, batch_id, orders_lookup, settlements_lookup,
                           previously_open_order_ids=None):
    """
    Turn one batch's real engine.reconcile() output into case dicts ready
    for state_store.upsert_case(). Only non-clean records become cases --
    a clean auto-match doesn't need a tracked lifecycle. Deterministic
    classification and candidate-finding only; the actual Gemini call for
    ambiguous/orphan cases happens separately in investigate_new_cases(),
    so callers control exactly when API quota gets spent.

    `settlements_lookup` is the raw settlement dicts (e.g. rows from
    settlements.csv) -- needed because engine.py's result_df doesn't
    carry settled_on, and an orphan credit's date is what the candidate
    search ranks against.

    `previously_open_order_ids`: order IDs re-included from an earlier
    batch (see state_store.pending_settlement_order_ids). If any of them
    landed CLEAN this time (a real settlement actually arrived and
    matched), their existing case is explicitly closed out as resolved --
    otherwise it would just vanish from the case store silently, since a
    clean row never enters the `needs_case` filter below.
    """
    settled_on_by_id = {s["settlement_id"]: s.get("settled_on", "") for s in settlements_lookup}
    needs_case = result_df[
        result_df["ai_assisted"]
        | (result_df["status"] == "EXCEPTION")
        | result_df["status"].isin(["AWAITING_REMITTANCE", "APPROACHING_THRESHOLD"])
    ]
    cases = []
    for r in needs_case.to_dict("records"):
        # Orphan credits are emitted with matched_settlement == the
        # settlement's OWN id (self-referential, see engine.py's second
        # emit() loop) -- expected == 0 is the reliable signal that this
        # is a settlement-side record, not an order-side unmatched order
        # (which always has expected == the order amount, received == 0).
        is_orphan_settlement = r["status"] == "EXCEPTION" and int(r["expected"]) == 0
        is_ambiguous = bool(r.get("candidates"))
        is_pending = r["status"] in ("AWAITING_REMITTANCE", "APPROACHING_THRESHOLD")

        order_id = None if is_orphan_settlement else r["record_id"]
        settlement_id = r["record_id"] if is_orphan_settlement else (r["matched_settlement"] or None)
        case_type = _case_type_for(r, is_ambiguous, is_orphan_settlement)

        det_candidates = list(r.get("candidates") or [])
        if is_orphan_settlement and not det_candidates:
            settled_on = settled_on_by_id.get(settlement_id, "")
            det_candidates = _find_orphan_candidates(int(r["received"]), settled_on, orders_lookup)

        # partial_payment/overpayment already got a real AI call inside
        # engine.py itself (RECONAI_LLM=1) -- confidence is set there, not
        # here. Only ambiguous_match/unmatched_settlement need this
        # module's own investigate_new_cases() call.
        already_investigated = case_type in ("partial_payment", "overpayment") and r.get("confidence") is not None
        needs_ai = case_type in ("ambiguous_match", "unmatched_settlement")

        if is_pending:
            case_status = "pending_settlement"
        elif already_investigated:
            case_status = "ai_recommendation" if r.get("ai_recommendation") != "ESCALATE" else "manual_review"
        elif needs_ai:
            case_status = "needs_ai"
        else:
            case_status = "manual_review"

        ai_block = None
        if already_investigated:
            action = "resolve" if r.get("ai_recommendation") == "AUTO_CLEAR" else "manual_review"
            ai_block = {
                "classification": case_type, "recommendation": r.get("ai_recommendation"),
                "confidence": r.get("confidence"), "reason": r["explanation"],
                "evidence": list(r.get("ai_evidence") or []), "candidate_rankings": [],
                "action": action, "investigated_at": datetime.now().isoformat(), "error": None,
            }

        cases.append({
            "case_id": f"CASE-{r['record_id']}",
            "record_id": r["record_id"],
            "order_id": order_id,
            "settlement_id": settlement_id,
            "batch_id": batch_id,
            "case_type": case_type,
            "tier": int(r["tier"]),
            "status": r["status"],
            "case_status": case_status,
            "expected": int(r["expected"]), "received": int(r["received"]), "delta": int(r["delta"]),
            "amount_at_risk": int(r["amount_at_risk"]),
            "reason": r["reason"], "reason_label": r["reason_label"],
            "explanation": r["explanation"], "priority": r["priority"],
            "candidates": det_candidates,
            "ai": ai_block,
            "_event": "reconciled" if case_status != "pending_settlement" else "awaiting settlement",
        })

    # Close out any re-included pending case that landed CLEAN this time --
    # a real settlement arrived and matched, so the case is genuinely done.
    if previously_open_order_ids:
        still_open = {c["record_id"] for c in cases}
        cleared = result_df[
            result_df["record_id"].isin(previously_open_order_ids)
            & ~result_df["record_id"].isin(still_open)
            & result_df["status"].isin(["AUTO_CLEARED", "CLEARED_WITH_FEE"])
        ]
        for r in cleared.to_dict("records"):
            cases.append({
                "case_id": f"CASE-{r['record_id']}", "record_id": r["record_id"],
                "order_id": r["record_id"], "settlement_id": r["matched_settlement"] or None,
                "batch_id": batch_id, "case_type": "settlement_matched",
                "tier": int(r["tier"]), "status": r["status"], "case_status": "resolved",
                "expected": int(r["expected"]), "received": int(r["received"]), "delta": int(r["delta"]),
                "amount_at_risk": 0, "reason": "", "reason_label": "",
                "explanation": f"Settlement arrived and matched cleanly. {r['explanation']}",
                "priority": "", "candidates": [], "ai": None,
                "resolution": {"resolved": True, "resolution_type": "auto_resolved",
                               "resolved_at": datetime.now().isoformat(), "resolved_by": "system"},
                "_event": "settlement arrived, resolved automatically",
            })
    return cases


def investigate_new_cases(cases):
    """
    Runs the real Gemini investigation for every case still marked
    'needs_ai' (ambiguous_match / unmatched_settlement only -- see
    build_cases_for_batch). Mutates and returns the same list. Safe to
    call on an already-investigated case list: anything not 'needs_ai' is
    left untouched, so this never re-spends API quota on a case that's
    already been investigated.
    """
    for case in cases:
        if case["case_status"] != "needs_ai":
            continue
        context = {
            "case_type": case["case_type"],
            "record": {
                "id": case["record_id"],
                "expected": fmt(case["expected"]),
                "received": fmt(case["received"]),
                "issue": case["reason_label"],
            },
            "candidate_matches": case["candidates"],
        }
        try:
            result = ai_client.investigate_case(case["case_type"], context)
            action = result.get("action", "manual_review")
            confidence = result.get("confidence")
            if action == "resolve" and (confidence or 0) < AUTO_RESOLVE_CONFIDENCE_FLOOR:
                action = "manual_review"
            case["ai"] = {
                "classification": result.get("classification", case["case_type"]),
                "recommendation": result.get("recommendation"),
                "confidence": confidence,
                "reason": result.get("reason"),
                "evidence": result.get("evidence") or [],
                "candidate_rankings": result.get("candidate_rankings") or [],
                "action": action,
                "investigated_at": datetime.now().isoformat(),
                "error": None,
            }
            case["case_status"] = "ai_recommendation" if action == "resolve" else "manual_review"
            case["_event"] = "ai investigated"
        except (ai_client.AIAuthError, ai_client.AIAPIError) as exc:
            case["ai"] = {
                "classification": case["case_type"], "recommendation": None, "confidence": None,
                "reason": f"AI investigation unavailable: {exc}", "evidence": [], "candidate_rankings": [],
                "action": "manual_review", "investigated_at": datetime.now().isoformat(), "error": str(exc),
            }
            case["case_status"] = "manual_review"
            case["_event"] = "ai investigation failed"
    return cases


def save_cases(state, cases):
    """Upsert every case into the persistent store -- the single write
    path callers should use after build_cases_for_batch()/investigate_new_cases()."""
    for case in cases:
        state_store.upsert_case(state, case)


def build_ask_context(state, case_id=None):
    """
    Compact structured context for Ask AI -- never the whole dataset.
    With case_id: just that one case (ticket-scoped assistant). Without:
    real cumulative totals + the currently-open cases (main Reconciliations
    page assistant) -- still bounded, not every historical record ever seen.
    """
    if case_id:
        case = state_store.get_case(state, case_id)
        return {"case": case} if case else {"case": None}

    runs = state["reconciliation_runs"]
    cases = state_store.list_cases(state)
    return {
        "cumulative_totals": {
            "total_reconciliations": len(runs),
            "auto_matched": sum(r["auto_matched"] for r in runs),
            "ai_resolved": sum(r["ai_resolved"] for r in runs),
            "exceptions": sum(r["exceptions"] for r in runs),
            "expected_amount": fmt(sum(r["expected_paise"] for r in runs)) if runs else fmt(0),
            "received_amount": fmt(sum(r["received_paise"] for r in runs)) if runs else fmt(0),
        },
        "latest_run_summary": (
            {"batch_id": runs[0]["batch_id"], "timestamp": runs[0]["timestamp"],
             "total_records": runs[0]["total_records"], "auto_matched": runs[0]["auto_matched"],
             "ai_resolved": runs[0]["ai_resolved"], "exceptions": runs[0]["exceptions"]}
            if runs else None
        ),
        "open_cases": [
            {"case_id": c["case_id"], "record_id": c["record_id"], "case_type": c["case_type"],
             "case_status": c["case_status"], "expected": fmt(c["expected"]), "received": fmt(c["received"]),
             "delta": fmt(c["delta"]), "reason": c["reason_label"]}
            for c in cases if c["case_status"] != "resolved"
        ],
    }
