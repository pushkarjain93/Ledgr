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
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime

import ai_client
import shopify_client
import state_store
from config import fmt, to_paise

# When may an AI "resolve" recommendation become a one-click action?
#
# NOT on the model's confidence score. Measured against this project's own
# data, that number carried almost no information: 83% of cases came back at
# exactly 10, evidence count did not correlate with it at all, and the single
# case that cleared the old 85 threshold was one the deterministic engine had
# explicitly flagged "verify before clearing". An uncalibrated self-report
# should not authorise signing off money.
#
# Gate on the facts instead. A case is one-click resolvable only when the
# exposure is genuinely small -- both relatively and in absolute terms -- and
# the model did not say it was missing something. Anything larger goes to a
# human no matter how sure the model sounds. This is the "financial risk is
# low" condition CLAUDE.md always specified but the code never implemented.
AUTO_RESOLVE_MAX_PCT = 0.10        # at-risk must be <= 10% of the order value
AUTO_RESOLVE_MAX_ABS = 50000       # and <= Rs 500.00 in absolute terms


def _may_auto_resolve(case, result) -> bool:
    """Deterministic check on whether AI's 'resolve' can be offered as one
    click. Never consults the confidence score."""
    if (result.get("missing_evidence") or []):
        return False
    at_risk = abs(int(case.get("amount_at_risk") or 0))
    expected = abs(int(case.get("expected") or 0))
    if at_risk > AUTO_RESOLVE_MAX_ABS:
        return False
    # A case with no order value to compare against (orphan credit) has no
    # meaningful ratio -- the absolute cap above is the only guard.
    if expected and at_risk > expected * AUTO_RESOLVE_MAX_PCT:
        return False
    return True

# unmatched_order/remittance_overdue are genuinely NOT ambiguous (there is
# no candidate at all) -- they're still sent to AI, but only for a next-step
# recommendation and an honestly low confidence, never a fabricated match.
# pending_settlement stays excluded: it's not broken, just still in its
# normal window, and shown separately (see the "Awaiting Settlement" widget
# in app_new.py) rather than in the Review Queue.
_AI_ELIGIBLE_TYPES = ("partial_payment", "overpayment", "ambiguous_match",
                      "unmatched_settlement", "unmatched_order", "remittance_overdue",
                      # A remittance discrepancy is DETECTED deterministically
                      # (remittance.py proves it from the file), but explaining
                      # what it means and drafting the dispute is judgement --
                      # exactly the half AI keeps.
                      "remittance_discrepancy")


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


def _find_orphan_candidates(settlement_amount_paise, settled_on, orders_lookup,
                             settled_orders=None, max_candidates=5):
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

    # Orders that ALREADY have their money. Without this the model sees an
    # exact amount match and recommends "link this settlement to that order",
    # not knowing the order was paid days ago -- which is precisely how a
    # DUPLICATE PAYMENT gets mistaken for a missing one. The right call on an
    # already-settled order is a refund, not a link.
    settled_orders = settled_orders or {}
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
            "already_settled_by": settled_orders.get(o["order_id"]),
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
    # order_id -> the settlement that already paid it, straight from the
    # engine's own matching. Cleanly matched orders never become cases, so this
    # is the only place that knowledge exists.
    settled_orders = {
        r["record_id"]: r["matched_settlement"]
        for r in result_df.to_dict("records")
        if r.get("matched_settlement") and r["matched_settlement"] != r["record_id"]
        and int(r.get("received") or 0) > 0
    }
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
            det_candidates = _find_orphan_candidates(
                int(r["received"]), settled_on, orders_lookup, settled_orders)

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


def apply_remittance_to_cases(cases, remittance_result, batch_id):
    """
    Rewrite the cases that the courier's remittance detail explains, and raise
    new ones for what it contradicts.

    Runs AFTER build_cases_for_batch, on its output. engine.py's waterfall is
    untouched: it correctly reported these orders as unpaid and the credit as
    unexplained, because on the data it had that was true. The remittance file
    is the missing evidence, and this is where it gets applied.

    Two rewrites:
      * an order named in a SQUARED batch is provably paid -- it stops being
        "overdue, chase the courier"
      * the bank credit that batch paid is provably accounted for -- it stops
        being "an unexplained credit, consider refunding"

    Those two were previously raised against the SAME money, telling the user
    to chase a courier for a payment that had already arrived and to consider
    refunding it back. Both disappear together or not at all.

    A batch whose rows do not sum to the credit links NOTHING -- see
    remittance.reconcile_remittances. Unproven paperwork must not clear money.
    """
    links = remittance_result.get("links") or {}
    batches = remittance_result.get("batches") or {}
    explained = {b["settlement_id"]: b for b in batches.values()
                 if b.get("checksum_ok") and b.get("settlement_id")}

    now = datetime.now().isoformat()
    for case in cases:
        rid = case["record_id"]
        link = links.get(rid)
        if link:
            case.update({
                "case_status": "resolved", "amount_at_risk": 0,
                "settlement_id": link["settlement_id"],
                "received": link["net_payout"],
                "explanation": (
                    f"Paid by {link['courier']} in the remittance batch settled on "
                    f"{link['remitted_on']} ({link['utr']}), which covered "
                    f"{link['batch_order_count']} orders. This order's share was "
                    f"{fmt(link['cod_collected'])} collected less "
                    f"{fmt(link['cod_fee'] + link['freight_fee'])} in courier fees, "
                    f"paid out as {fmt(link['net_payout'])}."),
                "remittance": link,
                "resolution": {"resolved": True, "resolution_type": "auto_resolved",
                               "resolved_at": now, "resolved_by": "system"},
                "_event": "matched to courier remittance detail",
            })
            continue

        batch = explained.get(rid) or explained.get(case.get("settlement_id") or "")
        if batch and case["case_type"] == "unmatched_settlement":
            case.update({
                "case_status": "resolved", "amount_at_risk": 0,
                "explanation": (
                    f"Courier remittance for {batch['courier']} covering "
                    f"{batch['order_count']} orders ({', '.join(batch['order_ids'])}). "
                    f"The per-order rows total {fmt(batch['rows_total'])}, matching this "
                    f"credit exactly."),
                "remittance_batch": batch,
                "resolution": {"resolved": True, "resolution_type": "auto_resolved",
                               "resolved_at": now, "resolved_by": "system"},
                "_event": "explained by courier remittance detail",
            })

    cases.extend(_remittance_discrepancy_cases(
        remittance_result.get("discrepancies") or [], cases, batch_id))
    return cases


def _remittance_discrepancy_cases(discrepancies, cases, batch_id):
    """
    One case per remittance discrepancy the join could not square.

    Skips anything already covered by an existing case for the same record --
    an order that is already an open exception does not need a second ticket,
    it needs the remittance evidence attached to the one it has.
    """
    by_record = {c["record_id"]: c for c in cases}
    new_cases = []
    for d in discrepancies:
        rid = d.get("order_id") or d.get("utr")
        if not rid:
            continue
        existing = by_record.get(rid)
        if existing:
            existing.setdefault("remittance_findings", []).append(d)
            existing["explanation"] = f"{existing['explanation']} {d['detail']}".strip()
            continue
        new_cases.append({
            "case_id": f"CASE-REMIT-{rid}", "record_id": rid,
            "order_id": d.get("order_id"), "settlement_id": None,
            "batch_id": batch_id, "case_type": "remittance_discrepancy",
            "tier": 5, "status": "EXCEPTION", "case_status": "needs_ai",
            "expected": 0, "received": 0, "delta": 0,
            "amount_at_risk": int(d.get("amount_at_risk") or 0),
            "reason": d["kind"], "reason_label": "Remittance discrepancy",
            "explanation": d["detail"], "priority": "",
            "candidates": [], "evidence_hash": None, "ai": None,
            "remittance_findings": [d],
            "resolution": {"resolved": False, "resolution_type": None,
                           "resolved_at": None, "resolved_by": None},
            "_event": "raised from courier remittance detail",
        })
    return new_cases


def build_case_context(case):
    """Public: the ticket page's step-by-step 'Investigate Further' UI
    calls this directly (real function boundary, not a cosmetic step)."""
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
        "candidate_rankings": [], "action": None, "investigated_at": None,
        # No provider produced a verdict -- every configured one was
        # exhausted or failed. Explicitly None, never a stale earlier value.
        "provider": None, "error": error_message,
    }
    case["_event"] = "ai investigation pending (unavailable)"


def apply_ai_result(case, result):
    """Public: also called directly by the ticket page's step-by-step
    'Investigate Further' UI, which needs to update the placeholder
    between each real call rather than after one opaque function."""
    confidence = result.get("confidence")
    action = result.get("recommended_action", "manual_review")
    # Downgrade a 'resolve' the money says a human should look at.
    if action == "resolve" and not _may_auto_resolve(case, result):
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
        # Which provider actually produced this verdict. Models calibrate
        # confidence differently, so an 80 from one is not necessarily an 80
        # from another -- recording it keeps the score auditable rather than
        # leaving "who judged this?" ambiguous.
        "provider": ai_client.last_provider(),
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
    if not pending:
        return cases
    chunks = [pending[i:i + batch_size] for i in range(0, len(pending), batch_size)]

    def run_chunk(chunk):
        """Investigate one chunk and apply its results.

        Runs entirely inside the worker thread, including apply_ai_result(),
        because ai_client tracks the answering provider per-thread -- reading it
        back on the main thread would attribute the wrong model to a case.
        """
        contexts = [build_case_context(c) for c in chunk]
        try:
            results = ai_client.investigate_batch(contexts)
        except (ai_client.AIRateLimitError, ai_client.AIAuthError,
                ai_client.AIAPIError) as exc:
            # Every provider refused this chunk. Mark ONLY this chunk pending;
            # sibling chunks are independent requests and may well succeed,
            # possibly on a different provider.
            for c in chunk:
                _mark_ai_pending(c, str(exc))
            return

        for c in chunk:
            result = results.get(c["case_id"])
            if result is None:
                _mark_ai_pending(c, "The AI response omitted this case (partial batch result).")
            else:
                apply_ai_result(c, result)

    # Chunks are fully independent, so sending them sequentially just multiplied
    # latency by the number of chunks (4 x ~10s made a sync take 40s+, when the
    # reconciliation itself takes under a second). Dispatch them together,
    # capped so a burst doesn't trip a provider's per-minute limit.
    if len(chunks) == 1:
        run_chunk(chunks[0])
    else:
        workers = min(len(chunks), ai_client.MAX_CONCURRENT_BATCHES)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            # list() forces every future to complete before returning, so all
            # cases are resolved (or marked pending) by the time we exit.
            list(pool.map(run_chunk, chunks))

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


def _find_settlement_candidates(order_amount_paise, order_date, settlements_lookup,
                                 matched_settlement_ids=None, max_candidates=5):
    """
    The mirror of _find_orphan_candidates: given an ORDER that never matched,
    find settlements that plausibly belong to it.

    Ranked by amount closeness then date proximity to the order -- the same
    reasoning used for orphan credits, because the same weakness applies:
    order values repeat across a small price set, so amount alone is a weak
    signal and date proximity is what separates a likely match from a
    coincidence.

    A settlement already reconciled to a DIFFERENT order is still returned,
    flagged with `already_matched_to`. That is deliberate: "the only
    amount-match is already reconciled elsewhere" is genuinely useful evidence
    for ruling a theory out, and hiding it would leave the model with an
    incomplete picture.

    Returns [] honestly when nothing is within tolerance.
    """
    matched_settlement_ids = matched_settlement_ids or {}
    tolerance = max(100, int(order_amount_paise * 0.02))  # Rs 1 or 2%, whichever is larger
    ordered_on = None
    if order_date:
        try:
            ordered_on = date.fromisoformat(str(order_date))
        except ValueError:
            ordered_on = None

    out = []
    for s in settlements_lookup:
        try:
            amt = to_paise(s.get("amount_received") or 0)
        except Exception:
            continue
        diff = abs(amt - order_amount_paise)
        if diff > tolerance:
            continue
        settled_on = s.get("settled_on", "")
        days = None
        if ordered_on and settled_on:
            try:
                days = (date.fromisoformat(str(settled_on)) - ordered_on).days
            except ValueError:
                days = None
        sid = s.get("settlement_id", "")
        out.append({
            "settlement_id": sid,
            "amount": fmt(amt),
            "amount_difference": fmt(diff),
            "settled_on": settled_on,
            "days_after_order": days,
            "source": s.get("source", ""),
            "bank_utr": s.get("bank_utr", ""),
            "gateway_ref_id": s.get("gateway_ref_id", ""),
            "already_matched_to": matched_settlement_ids.get(sid),
        })
    out.sort(key=lambda c: (to_paise(c["amount_difference"].replace("Rs ", "").replace(",", "")),
                            abs(c["days_after_order"]) if c["days_after_order"] is not None else 999))
    return out[:max_candidates]


def fetch_missing_evidence(case, orders_lookup, settlements_lookup=None,
                            matched_settlement_ids=None):
    """
    Deterministic, honest attempt to gather whatever additional evidence this
    system genuinely holds for a case.

    Fetches what is ACTUALLY available rather than only what the model literally
    named -- most asks are for payment-gateway logs this system does not have,
    and answering only those would make every follow-up a dead end. What IS
    fetchable:

      - candidate settlements for an order that never matched (see
        _find_settlement_candidates)
      - the customer's other orders, when the ask mentions customer history

    Anything named but unavailable is reported explicitly in
    `still_unavailable`, so the model can see the gap rather than assume the
    absence of data means absence of a problem.
    """
    missing = (case.get("ai") or {}).get("missing_evidence") or []
    evidence = {}

    # Candidate settlements -- only meaningful for an order-side case that
    # never matched. An orphan settlement already carries its candidates from
    # build_cases_for_batch, and a matched case has nothing to search for.
    if (settlements_lookup and case.get("order_id") and not case.get("settlement_id")
            and int(case.get("expected") or 0) > 0):
        candidates = _find_settlement_candidates(
            int(case["expected"]), case.get("order_date"), settlements_lookup,
            matched_settlement_ids)
        evidence["candidate_settlements"] = candidates or (
            "none -- no settlement in the current feed is within 2% of this "
            "order's value, so the money has not arrived under a different reference")

    # Customer history, when that is what was asked for.
    wants_history = any(kw in m.lower() for m in missing
                        for kw in ("customer", "history", "other order"))
    customer_name = case.get("customer_name") or next(
        (c.get("customer_name") for c in case.get("candidates", []) if c.get("customer_name")), None)
    if wants_history and customer_name:
        history = _customer_order_history(customer_name, orders_lookup,
                                           exclude_order_id=case.get("order_id"))
        evidence["customer_order_history"] = history or (
            "none -- this customer has no other orders in the current dataset")

    unavailable = [m for m in missing
                   if not any(kw in m.lower() for kw in ("customer", "history", "other order"))]
    if unavailable:
        evidence["still_unavailable"] = (
            f"Not held by this system: {'; '.join(unavailable)}. Ledgr reconciles "
            "order and settlement feeds only -- it has no access to gateway-side "
            "logs or payment-processor internals.")
        # The prose above is written FOR THE MODEL. The UI needs the bare
        # items, so keep them as a list rather than making the panel unpick a
        # sentence -- the followup snapshot below reads this one.
        evidence["still_unavailable_items"] = unavailable

    return evidence or {"note": "No additional evidence is available for this case."}


def _followup_evidence_labels(new_evidence: dict) -> list[str]:
    """
    Plain-language summary of what the follow-up actually went and checked.

    Reports the real shape of what came back -- "no matching settlement found"
    is a genuine finding and must not be presented as if nothing was looked at.
    """
    labels = []
    cand = new_evidence.get("candidate_settlements")
    if isinstance(cand, list):
        labels.append(f"Searched the settlement feed — {len(cand)} possible match"
                      f"{'' if len(cand) == 1 else 'es'} found")
    elif cand:
        labels.append("Searched the settlement feed — no payment found under any reference")

    hist = new_evidence.get("customer_history")
    if isinstance(hist, list):
        labels.append(f"Checked this customer's other orders — {len(hist)} found")
    elif hist:
        labels.append("Checked this customer's order history")
    return labels


def investigate_case_followup(state, case_id, orders_lookup,
                               settlements_lookup=None,
                               matched_settlement_ids=None):
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
    original_context = build_case_context(case)
    new_evidence = fetch_missing_evidence(
        case, orders_lookup, settlements_lookup, matched_settlement_ids)
    # Snapshot the verdict BEFORE the follow-up overwrites it. Without this the
    # UI can only show the new conclusion, which makes "Investigate further"
    # look like it did nothing when it re-confirms an existing finding -- the
    # value is in what CHANGED and what evidence was actually retrieved.
    #
    # apply_ai_result stores the verdict as `action`/`reason`/`next_step`, NOT
    # under the model's own `recommended_action`/`reasoning` names -- reading
    # the latter silently produced None on both sides and made `changed`
    # always False.
    prior = {
        "action": case["ai"].get("action"),
        "reasoning": case["ai"].get("reason"),
        "next_step": case["ai"].get("next_step"),
    }
    try:
        result = ai_client.investigate_followup(original_context, case["ai"], new_evidence)
        result.setdefault("missing_evidence", [])
        apply_ai_result(case, result)
        case["ai"]["followup"] = {
            "at": datetime.now().isoformat(timespec="seconds"),
            "evidence_checked": _followup_evidence_labels(new_evidence),
            # The LIST, not the prose sentence built for the model. Passing the
            # string through made the UI call .join() on it, which throws and
            # blanks the whole case page.
            "still_unavailable": new_evidence.get("still_unavailable_items") or [],
            "previous": prior,
            "changed": prior.get("action") != case["ai"].get("action"),
        }
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


def _customer_contact(order: dict | None) -> dict:
    """Contact fields for Ask AI context. Empty dict when the order isn't
    found (e.g. an orphan settlement has no order side) -- never placeholder
    values that could read as real contact details."""
    if not order:
        return {}
    return {k: order.get(k, "") for k in
            ("customer_name", "customer_phone", "customer_email", "courier")}


def build_ask_context(state, case_id=None):
    """
    Compact structured context for the rare question that DOES need
    Gemini (try_direct_answer returned None). With case_id: just that one
    case. Without: real cumulative totals + currently-open cases -- still
    bounded, never every historical record ever seen.
    """
    if case_id:
        case = state_store.get_case(state, case_id)
        if not case:
            return {"case": None}
        # Scoped to ONE case, so the customer's real contact details are in
        # scope -- chasing a missing payment is exactly what an operator needs
        # them for. Read fresh from the order feed rather than duplicated onto
        # the case, so there is one source of truth.
        contact = {}
        if case.get("order_id"):
            order = next((o for o in shopify_client.fetch_orders()
                          if o["order_id"] == case["order_id"]), None)
            if order:
                contact = {
                    "customer_name": order.get("customer_name", ""),
                    "customer_phone": order.get("customer_phone", ""),
                    "customer_email": order.get("customer_email", ""),
                    "courier": order.get("courier", ""),
                    "payment_mode": order.get("payment_mode", ""),
                }
        # Money must reach the model already formatted. The stored case keeps
        # amounts as integer paise (correct for arithmetic), but a model shown
        # `expected: 999950` will quote "999950" verbatim -- and a message sent
        # to a payment gateway saying that instead of "Rs 9,999.50" is a real,
        # embarrassing error. Formatting here keeps paise out of anything the
        # model can echo.
        safe_case = dict(case)
        for field in ("expected", "received", "delta", "amount_at_risk"):
            if isinstance(safe_case.get(field), int):
                safe_case[field] = fmt(safe_case[field])
        return {"case": safe_case, "customer": contact or None}

    runs = state["reconciliation_runs"]
    cases = state_store.list_cases(state)
    contacts_by_order = {o["order_id"]: o for o in shopify_client.fetch_orders()}

    # Every status, INCLUDING the ones at zero.
    #
    # Absence is ambiguous to a model: with no ai_pending entries in the list
    # it cannot tell "none are waiting on AI" from "the list was truncated".
    # Asked which cases were waiting on AI, it answered with five cases that
    # had all already been investigated -- it pattern-matched their reason
    # text ("Large variance flagged by AI") because nothing told it the count
    # was actually zero. An explicit 0 cannot be misread.
    status_counts = {s: 0 for s in (
        "pending_settlement", "needs_ai", "ai_pending",
        "ai_recommendation", "manual_review", "exception", "resolved")}
    for c in cases:
        status_counts[c["case_status"]] = status_counts.get(c["case_status"], 0) + 1

    return {
        "case_status_counts": status_counts,
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
        # Sorted by amount_at_risk so the genuinely most exposed cases are
        # first. `delta` alone is a misleading ranking signal: an order that
        # was never settled has delta 0 (there was nothing to compare against)
        # while its FULL value is at risk, so ranking on delta buries the worst
        # cases beneath small overpayments. amount_at_risk is the engine's own
        # exposure figure and is what everything else in Ledgr ranks by
        # (see engine.py's final sort).
        "open_cases": [
            {"case_id": c["case_id"], "record_id": c["record_id"], "case_type": c["case_type"],
             "case_status": c["case_status"], "expected": fmt(c["expected"]),
             "received": fmt(c["received"]), "delta": fmt(c["delta"]),
             "amount_at_risk": fmt(c["amount_at_risk"]), "priority": c.get("priority") or "",
             "order_date": c.get("order_date", ""), "reason": c["reason_label"],
             # Customer contact for OPEN cases only. An operator chasing an
             # unpaid order legitimately needs it, and open cases are the only
             # ones being chased -- resolved cases are already excluded above,
             # so closed customers' details are never sent.
             #
             # PRODUCTION NOTE: this ships customer PII to a third-party model
             # on every question. Fine for this demo's synthetic customers; a
             # real deployment should either use a provider with a
             # zero-retention agreement, or fetch contact only for the specific
             # case being discussed (the case_id branch above already does
             # exactly that).
             **_customer_contact(contacts_by_order.get(c.get("order_id") or ""))}
            for c in sorted((c for c in cases if c["case_status"] != "resolved"),
                            key=lambda c: -c["amount_at_risk"])
        ],
    }
