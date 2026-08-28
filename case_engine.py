"""
Post-reconciliation case layer for Ledgr.

Sits STRICTLY AFTER engine.reconcile() -- nothing here ever changes what
tier or status a record lands on. It turns the deterministic engine's
per-record output into persistent, trackable "cases" (state_store.py's
`cases` dict), and owns the ONE live path to Gemini for every AI-eligible
case type uniformly (partial payment, overpayment, ambiguous multi-
candidate match, orphan settlement correlation). engine.py itself never
talks to the network any more -- see CLAUDE.md's "batched AI architecture"
session note for why the live call moved here.

Three real, deliberate cost-control mechanisms live in this file:
  1. Batching -- ai_client.investigate_batch() sends several cases per
     request (see investigate_new_cases_batched), not one call each.
  2. Evidence-hash caching -- a case whose relevant facts haven't changed
     since it was last investigated reuses that result instead of asking
     Gemini again (see _evidence_hash / build_cases_for_batch).
  3. Ask AI answers most questions directly from already-computed,
     already-persisted data (try_direct_answer) -- Gemini is only asked
     genuinely novel questions.

Also implements the one controlled, user-triggered agentic step this
project uses: when a Gemini investigation names specific missing evidence,
a human can ask Ledgr to fetch what's realistically fetchable and get one
final follow-up verdict (investigate_case_followup). Never automatic,
never looped beyond that one extra call.
"""
import hashlib
import json
import re
from datetime import date, datetime

import ai_client
import state_store
from config import fmt, to_paise

# Confidence floor below which an AI "resolve" recommendation is downgraded
# to manual_review regardless of what the model said -- mirrors this
# project's standing "never auto-clear without justification" rule.
AUTO_RESOLVE_CONFIDENCE_FLOOR = 85

# unmatched_order/remittance_overdue are genuinely NOT ambiguous (there is
# no candidate at all) -- they're still sent to AI, but only for a next-step
# recommendation and an honestly low confidence, never a fabricated match.
# pending_settlement stays excluded: it's not broken, just still in its
# normal window, and shown separately (see the "Awaiting Settlement" widget
# in app_new.py) rather than in the Review Queue.
_AI_ELIGIBLE_TYPES = ("partial_payment", "overpayment", "ambiguous_match",
                      "unmatched_settlement", "unmatched_order", "remittance_overdue")


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


def _status_from_ai_action(action):
    """
    'escalate' maps to its own 'exception' status, distinct from
    'manual_review' -- manual_review means AI found real evidence/
    candidates but couldn't resolve unambiguously (a genuine judgement
    call); exception means there was NOTHING to weigh at all (no
    candidate, no evidence), which is a harder, more urgent bucket than
    an ambiguous match.
    """
    return {"resolve": "ai_recommendation", "manual_review": "manual_review",
            "escalate": "exception"}.get(action, "manual_review")


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


def _evidence_hash(case_type, expected, received, delta, candidates, reason):
    """
    A stable fingerprint of the facts that actually matter to a case's
    investigation. If this is unchanged from the last time the case was
    investigated, the stored AI result is still valid and gets reused
    (see build_cases_for_batch) -- if a new candidate shows up, or the
    amounts shift, the hash changes and the case is queued for a fresh
    investigation instead of silently serving a stale verdict.
    """
    candidate_ids = sorted(c.get("order_id") or c.get("settlement_id", "") for c in candidates)
    payload = {"case_type": case_type, "expected": expected, "received": received,
               "delta": delta, "reason": reason, "candidates": candidate_ids}
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def build_cases_for_batch(result_df, batch_id, orders_lookup, settlements_lookup,
                           previously_open_order_ids=None, existing_cases=None):
    """
    Turn one batch's real engine.reconcile() output into case dicts ready
    for state_store.upsert_case(). Only non-clean records become cases --
    a clean auto-match doesn't need a tracked lifecycle. Deterministic
    classification and candidate-finding only; the actual Gemini call
    happens separately in investigate_new_cases_batched(), so callers
    control exactly when API quota gets spent.

    `existing_cases`: the merchant's current case store (case_id -> case),
    used for evidence-hash caching -- an AI-eligible case whose evidence
    hash matches its previous investigation reuses that result instead of
    being queued for a fresh (and costly) Gemini call.

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
    existing_cases = existing_cases or {}
    settled_on_by_id = {s["settlement_id"]: s.get("settled_on", "") for s in settlements_lookup}
    orders_by_id = {o["order_id"]: o for o in orders_lookup}
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
        case_id = f"CASE-{r['record_id']}"

        det_candidates = list(r.get("candidates") or [])
        if is_orphan_settlement and not det_candidates:
            settled_on = settled_on_by_id.get(settlement_id, "")
            det_candidates = _find_orphan_candidates(int(r["received"]), settled_on, orders_lookup)

        ai_block, evidence_hash, case_status = None, None, "manual_review"
        if is_pending:
            case_status = "pending_settlement"
        elif case_type in _AI_ELIGIBLE_TYPES:
            evidence_hash = _evidence_hash(case_type, int(r["expected"]), int(r["received"]),
                                            int(r["delta"]), det_candidates, r["reason"])
            cached = existing_cases.get(case_id)
            if (cached and cached.get("evidence_hash") == evidence_hash
                    and cached.get("ai") and not cached["ai"].get("error")):
                ai_block = cached["ai"]
                case_status = _status_from_ai_action(ai_block.get("action"))
                event = "reconciled (AI result reused -- evidence unchanged)"
            else:
                case_status = "needs_ai"
                event = "reconciled, queued for AI investigation"
        else:
            event = "reconciled"

        # Real customer/order-date context for display -- from the order
        # itself when this case has one, or from the strongest candidate
        # when it's an orphan settlement with no direct order. None/blank
        # when genuinely unavailable, never guessed.
        order_row = orders_by_id.get(order_id) if order_id else None
        customer_name = order_row.get("customer_name", "") if order_row else (
            det_candidates[0].get("customer_name", "") if det_candidates else "")
        order_date = order_row.get("order_date", "") if order_row else ""

        cases.append({
            "case_id": case_id, "record_id": r["record_id"],
            "order_id": order_id, "settlement_id": settlement_id,
            "customer_name": customer_name, "order_date": order_date,
            "batch_id": batch_id, "case_type": case_type,
            "tier": int(r["tier"]), "status": r["status"], "case_status": case_status,
            "expected": int(r["expected"]), "received": int(r["received"]), "delta": int(r["delta"]),
            "amount_at_risk": int(r["amount_at_risk"]),
            "reason": r["reason"], "reason_label": r["reason_label"],
            "explanation": r["explanation"], "priority": r["priority"],
            "candidates": det_candidates, "evidence_hash": evidence_hash, "ai": ai_block,
            "_event": event if not is_pending else "awaiting settlement",
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
                "priority": "", "candidates": [], "evidence_hash": None, "ai": None,
                "resolution": {"resolved": True, "resolution_type": "auto_resolved",
                               "resolved_at": datetime.now().isoformat(), "resolved_by": "system"},
                "_event": "settlement arrived, resolved automatically",
            })
    return cases


def _build_context(case):
    return {
        "case_id": case["case_id"], "case_type": case["case_type"],
        "record": {"id": case["record_id"], "expected": fmt(case["expected"]),
                   "received": fmt(case["received"]), "issue": case["reason_label"]},
        "candidate_matches": case["candidates"],
    }


def _mark_ai_pending(case, error_message):
    """AI hasn't given a real verdict -- NOT the same claim as
    'manual_review' (which means AI looked and a human must decide)."""
    case["case_status"] = "ai_pending"
    case["ai"] = {
        "classification": case["case_type"], "recommendation": None, "confidence": None,
        "reason": None, "next_step": None, "evidence": [], "missing_evidence": [],
        "candidate_rankings": [], "action": None, "investigated_at": None, "error": error_message,
    }
    case["_event"] = "ai investigation pending (unavailable)"


def _apply_ai_result(case, result):
    confidence = result.get("confidence")
    action = result.get("recommended_action", "manual_review")
    if action == "resolve" and (confidence or 0) < AUTO_RESOLVE_CONFIDENCE_FLOOR:
        action = "manual_review"
    candidate_id = result.get("candidate_id")
    case["ai"] = {
        "classification": result.get("decision", case["case_type"]),
        "recommendation": result.get("recommended_action"),
        "confidence": confidence,
        "reason": result.get("reasoning"),
        "next_step": result.get("next_step"),
        "evidence": result.get("evidence_used") or [],
        "missing_evidence": result.get("missing_evidence") or [],
        "candidate_rankings": ([{"id": candidate_id, "confidence": confidence,
                                 "reason": result.get("reasoning", "")}] if candidate_id else []),
        "action": action,
        "investigated_at": datetime.now().isoformat(),
        "error": None,
    }
    case["case_status"] = _status_from_ai_action(action)
    case["_event"] = "ai investigated"


def investigate_new_cases_batched(cases, batch_size=None):
    """
    Batches every case still marked 'needs_ai' into groups of
    `batch_size` (default ai_client.DEFAULT_BATCH_SIZE) and sends each
    group as ONE Gemini request. Mutates and returns the same list.

    On a rate limit: marks every case in the failed chunk AND every case
    in any chunk not yet attempted as 'ai_pending', then stops entirely
    -- further calls this run would just also fail against an exhausted
    per-minute/day cap. A "Retry AI Investigation" button lets the user
    try again later (see retry_pending_cases()).

    On any other failure for one chunk: marks that chunk's cases
    'ai_pending' too, but keeps attempting the remaining chunks.

    Partial success (Gemini's response omits a case_id it was sent):
    that one case is left 'ai_pending'; everything else in the same
    response is applied normally.
    """
    batch_size = batch_size or ai_client.DEFAULT_BATCH_SIZE
    pending = [c for c in cases if c["case_status"] == "needs_ai"]
    chunks = [pending[i:i + batch_size] for i in range(0, len(pending), batch_size)]

    for i, chunk in enumerate(chunks):
        contexts = [_build_context(c) for c in chunk]
        try:
            results = ai_client.investigate_batch(contexts)
        except ai_client.AIRateLimitError as exc:
            remaining = chunk + [c for later_chunk in chunks[i + 1:] for c in later_chunk]
            for c in remaining:
                _mark_ai_pending(c, str(exc))
            break
        except (ai_client.AIAuthError, ai_client.AIAPIError) as exc:
            for c in chunk:
                _mark_ai_pending(c, str(exc))
            continue

        for c in chunk:
            result = results.get(c["case_id"])
            if result is None:
                _mark_ai_pending(c, "Gemini's response omitted this case (partial batch result).")
            else:
                _apply_ai_result(c, result)

    return cases


def retry_pending_cases(state, case_ids):
    """
    Re-attempt investigation for specific 'ai_pending' cases, reusing the
    same batched call path (so retrying several at once still saves
    quota). Rebuilds each case's context from its own stored fields --
    no need to re-run reconcile() or re-touch source data. Persists
    results directly onto state["cases"] and returns the cases retried.
    """
    store = state.get("cases", {})
    targets = []
    for cid in case_ids:
        existing = store.get(cid)
        if existing and existing.get("case_status") == "ai_pending":
            fresh = dict(existing)
            fresh["case_status"] = "needs_ai"
            targets.append(fresh)
    if not targets:
        return []
    investigate_new_cases_batched(targets)
    for c in targets:
        state_store.upsert_case(state, c)
    return targets


def save_cases(state, cases):
    """Upsert every case into the persistent store -- the single write
    path callers should use after build_cases_for_batch()/
    investigate_new_cases_batched()."""
    for case in cases:
        state_store.upsert_case(state, case)


# ===========================================================================
# Follow-up investigation -- the one controlled, user-triggered agentic
# step. Gemini already named what evidence would raise its confidence
# (missing_evidence); this fetches whatever of that is realistically
# available and makes ONE more call for a final verdict. Never automatic.
# ===========================================================================
def _customer_order_history(customer_name, orders_lookup, exclude_order_id=None):
    """Every OTHER real order by the same customer in the currently-known
    dataset. Returns [] honestly if there are none -- never fabricates one."""
    if not customer_name:
        return []
    return [
        {"order_id": o["order_id"], "amount": fmt(to_paise(o["order_amount"])),
         "order_date": o.get("order_date", ""), "payment_mode": o.get("payment_mode", "")}
        for o in orders_lookup
        if o.get("customer_name") == customer_name and o.get("order_id") != exclude_order_id
    ]


def fetch_missing_evidence(case, orders_lookup):
    """
    Deterministic, honest attempt to fetch ONE named piece of missing
    evidence. Only customer order history is actually fetchable today --
    if the model asked for something this system genuinely doesn't have
    (e.g. a bank remittance document), this says so plainly instead of
    inventing it.
    """
    missing = (case.get("ai") or {}).get("missing_evidence") or []
    wants_history = any(kw in m.lower() for m in missing
                        for kw in ("customer", "history", "other order"))
    customer_name = next((c.get("customer_name") for c in case.get("candidates", [])
                          if c.get("customer_name")), None)
    if wants_history and customer_name:
        history = _customer_order_history(customer_name, orders_lookup, exclude_order_id=case.get("order_id"))
        if history:
            return {"customer_order_history": history}
        return {"customer_order_history": "none -- this customer has no other orders in the current dataset"}
    return {"note": "The requested evidence is not available in this system."}


def investigate_case_followup(state, case_id, orders_lookup):
    """
    The controlled agentic step: fetch whatever additional evidence is
    realistically available for this case's missing_evidence, then make
    ONE more Gemini call with that evidence for a final conclusion.
    Never automatic, never looped further -- always exactly one more
    call, always user-triggered.
    """
    case = state_store.get_case(state, case_id)
    if not case or not case.get("ai"):
        return None
    original_context = _build_context(case)
    new_evidence = fetch_missing_evidence(case, orders_lookup)
    try:
        result = ai_client.investigate_followup(original_context, case["ai"], new_evidence)
        result.setdefault("missing_evidence", [])
        _apply_ai_result(case, result)
        case["_event"] = "ai follow-up investigation completed"
    except (ai_client.AIAuthError, ai_client.AIAPIError) as exc:
        case["_event"] = f"ai follow-up investigation unavailable: {exc}"
    state_store.upsert_case(state, case)
    return case


# ===========================================================================
# Ask AI -- direct-answer-first. Most questions are answerable straight
# from already-computed, already-persisted data; Gemini is only called
# (by app_new.py, via ai_client.ask()) when this returns None.
# ===========================================================================
_ID_PATTERN = re.compile(r"\b(ORD|STL|CASE)-[A-Z0-9-]+\b", re.IGNORECASE)


def try_direct_answer(question: str, state) -> str | None:
    """
    Answers a question directly from Python/pandas over the persisted
    case store whenever possible -- exact ID lookups and aggregations
    over data that's already been computed (including any AI reasoning
    already stored per case). Returns None when the question doesn't
    match a confident pattern, so the caller falls back to a real Gemini
    call for genuinely novel questions.
    """
    q = question.lower()
    cases = state_store.list_cases(state)

    id_match = _ID_PATTERN.search(question)
    if id_match:
        raw_id = id_match.group(0).upper()
        case = next((c for c in cases if raw_id in
                    (c.get("record_id", "").upper(), (c.get("order_id") or "").upper(),
                     (c.get("settlement_id") or "").upper(), c["case_id"].upper())), None)
        if case:
            lines = [
                f"{case['record_id']} — {case['case_type'].replace('_', ' ').title()} "
                f"({case['case_status'].replace('_', ' ')}).",
                f"Expected: {fmt(case['expected'])}", f"Received: {fmt(case['received'])}",
                f"Difference: {fmt(case['delta'])}",
            ]
            if case.get("ai") and case["ai"].get("reason"):
                lines.append(f"AI finding: {case['ai']['reason']}")
            return "\n".join(lines)
        return (f"{raw_id} isn't in the review queue — it either matched cleanly during "
                f"reconciliation, or hasn't been processed yet.")

    if "pending" in q and ("order" in q or "settlement" in q):
        pending = [c for c in cases if c["case_status"] == "pending_settlement"]
        if not pending:
            return "No orders are currently pending settlement."
        lines = "\n".join(f"- {c['record_id']} ({fmt(c['expected'])})" for c in pending[:10])
        return f"{len(pending)} order(s) pending settlement:\n{lines}"

    if "unmatched" in q and "settlement" in q:
        unmatched = [c for c in cases if c["case_type"] == "unmatched_settlement"]
        if not unmatched:
            return "No unmatched settlements right now."
        lines = "\n".join(f"- {c['record_id']} ({fmt(c['received'])})" for c in unmatched[:10])
        return f"{len(unmatched)} unmatched settlement(s):\n{lines}"

    if any(kw in q for kw in ("outstanding", "how much", "total shortfall", "owed", "owe")):
        open_cases = [c for c in cases if c["case_status"] != "resolved"]
        if not open_cases:
            return "Nothing is currently outstanding -- every tracked case is resolved."
        total = sum(c["amount_at_risk"] for c in open_cases)
        by_type = {}
        for c in open_cases:
            by_type.setdefault(c["case_type"], []).append(c)
        breakdown = "; ".join(
            f"{len(items)} {t.replace('_', ' ')} ({fmt(sum(i['amount_at_risk'] for i in items))})"
            for t, items in by_type.items())
        return f"Total outstanding: {fmt(total)}, across {len(open_cases)} case(s) -- {breakdown}."

    if "ai pending" in q or ("waiting" in q and "ai" in q):
        pending_ai = [c for c in cases if c["case_status"] == "ai_pending"]
        if not pending_ai:
            return "No cases are currently waiting on AI investigation."
        return (f"{len(pending_ai)} case(s) waiting on AI investigation (likely rate-limited) -- "
                f"use Retry AI Investigation on each ticket once quota is available.")

    if "manual review" in q or "exception" in q:
        mr = [c for c in cases if c["case_status"] == "manual_review"]
        if not mr:
            return "No cases are currently in manual review."
        lines = "\n".join(f"- {c['record_id']} ({c['reason_label']})" for c in mr[:10])
        return f"{len(mr)} case(s) in manual review:\n{lines}"

    return None


def build_ask_context(state, case_id=None):
    """
    Compact structured context for the rare question that DOES need
    Gemini (try_direct_answer returned None). With case_id: just that one
    case. Without: real cumulative totals + currently-open cases -- still
    bounded, never every historical record ever seen.
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
