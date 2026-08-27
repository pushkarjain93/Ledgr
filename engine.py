"""
ReconAI — 5-tier waterfall reconciliation engine (plus the Tier 0 pre-check).

    Tier 0   COD timing pre-check   COD with no remittance yet -> age it
    Tier 1   Exact match            gateway_ref_id + amount identical
    Tier 2   Known deduction        ref matches, shortfall inside the fee band
    Tier 3   Variance               ref matches, amount does not -> AI diagnostic
    Tier 4   UTR fallback           no ref, match on bank_utr, then classify
    Tier 5   Unmatched              never guess; exception with a stated reason

Two rules the whole engine obeys:

  1. Money is integer paise. No float arithmetic, anywhere.
  2. The model never produces a number. Tier 3 hands the model engine-computed
     facts and receives back a category plus one sentence. Arithmetic is code's
     job; judgement is the model's.

Run:  python3 engine.py            (offline, deterministic AI stub)
      RECONAI_LLM=1 python3 engine.py   (once a real client is wired in)
"""
import os
import sys
from datetime import date

import pandas as pd
from dotenv import load_dotenv

from config import (RUN_DATE, REASON_LEGEND, TIER_NAMES, to_paise, to_rupees,
                    fmt, fee_band, cod_age_bucket, priority_of)

# Loaded here (not just in ai_client.py/razorpay_client.py) so RECONAI_LLM=1
# in .env takes effect regardless of which module happens to import engine.py
# first -- relying on import order across files to populate os.environ would
# be fragile.
load_dotenv()

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
USE_LLM = os.environ.get("RECONAI_LLM") == "1"


# ===========================================================================
# Tier 3 adjudication
# ===========================================================================
def ai_diagnose(facts: dict) -> dict:
    """
    Given engine-computed facts about a variance, return a dict:
    {reason_code, explanation, confidence, evidence, recommendation}.

    confidence/evidence/recommendation are None/[] on the offline path --
    there's no "confidence" in a hand-written if-else, only a category and
    a sentence. Only the real model path (RECONAI_LLM=1) populates them,
    since only a real judgement call has a confidence to report.

    The offline path is deterministic so the engine can be developed and
    scored without network access or spend. The model is never asked to
    compute anything, on either path -- it receives already-computed facts
    and returns a classification + explanation, nothing else.
    """
    if USE_LLM:
        return _llm_diagnose(facts)
    reason_code, explanation = _offline_diagnose(facts)
    return {"reason_code": reason_code, "explanation": explanation,
            "confidence": None, "evidence": [], "recommendation": None}


def _offline_diagnose(facts: dict):
    """The original deterministic stand-in -- unchanged logic, just given
    its own name now that ai_diagnose() is a thin dispatcher. Still used
    directly as ai_diagnose()'s offline path, AND as _llm_diagnose()'s
    fallback when the real API call fails."""
    delta, amt, band = facts["delta"], facts["order_amount"], facts["band"]
    pct = abs(delta) / amt * 100 if amt else 0

    if delta > 0:
        if abs(delta - amt) <= 100:
            return ("R5_AI_VARIANCE",
                    f"Settled amount is exactly double the order value on a matched "
                    f"reference. Consistent with a duplicate capture, not a fee or "
                    f"refund. Do not clear; confirm with the gateway before posting.")
        return ("R5_AI_VARIANCE",
                f"Received {fmt(delta)} more than the order value ({pct:.1f}% over) "
                f"on a matched reference. Overpayment of this shape is usually a "
                f"duplicate capture or a misapplied credit. Route to gateway ops.")

    if facts["payment_mode"] == "COD":
        return ("R4_PARTIAL_PAYMENT",
                f"COD remittance is {fmt(-delta)} short ({pct:.1f}% of order value), "
                f"beyond the {fmt(band)} collection-fee band for this order. Not "
                f"explainable as a standard courier fee; raise with the courier.")

    if pct >= 20:
        return ("R4_PARTIAL_PAYMENT",
                f"Settled {fmt(-delta)} short, {pct:.1f}% of order value. Far outside "
                f"the {fmt(band)} fee band. Shape is consistent with a refund or "
                f"chargeback netted off the same reference. Verify before clearing.")

    return ("R5_AI_VARIANCE",
            f"Deduction of {fmt(-delta)} ({pct:.2f}%) exceeds the contracted "
            f"{fmt(band)} band for this payment mode. Small enough to look like a "
            f"fee, large enough that it is not the agreed one. Check the MDR "
            f"schedule for this transaction type.")


def _llm_diagnose(facts: dict) -> dict:
    """
    Real model call, via the isolated ai_client.py (same pattern as
    razorpay_client.py -- raw REST, no vendor SDK). Validates the response
    before trusting it: reason_code must be one of REASON_LEGEND's real
    codes. Any failure at all -- network, auth, malformed response, an
    invalid reason code -- falls back to the deterministic offline path
    rather than crashing or fabricating a diagnosis. This mirrors the
    project's existing rule for Razorpay: "API fails = flag for review,
    never guess."
    """
    import ai_client
    try:
        result = ai_client.diagnose(facts)
        if result.get("reason_code") not in REASON_LEGEND:
            raise ai_client.AIAPIError(f"invalid reason_code: {result.get('reason_code')!r}")
    except (ai_client.AIAuthError, ai_client.AIAPIError) as exc:
        reason_code, explanation = _offline_diagnose(facts)
        return {"reason_code": reason_code,
                "explanation": f"[AI unavailable -- {exc}] {explanation}",
                "confidence": None, "evidence": [], "recommendation": None}

    return {
        "reason_code": result["reason_code"],
        "explanation": result.get("explanation", ""),
        "confidence": result.get("confidence"),
        "evidence": result.get("evidence") or [],
        "recommendation": result.get("recommendation"),
    }


# ===========================================================================
# Engine
# ===========================================================================
def load():
    orders = pd.read_csv(f"{DATA}/orders.csv", dtype=str).fillna("")
    setls = pd.read_csv(f"{DATA}/settlements.csv", dtype=str).fillna("")
    orders["amount_paise"] = orders["order_amount"].map(to_paise)
    setls["amount_paise"] = setls["amount_received"].map(to_paise)
    return orders, setls


def reconcile(orders: pd.DataFrame, setls: pd.DataFrame) -> pd.DataFrame:
    # index the settlement feed by each identifier it can be joined on
    by_ref, by_utr = {}, {}
    for s in setls.to_dict("records"):
        if s["gateway_ref_id"]:
            by_ref.setdefault(s["gateway_ref_id"], []).append(s)
        if s["bank_utr"]:
            by_utr.setdefault(s["bank_utr"], []).append(s)

    consumed, out = set(), []

    def emit(rid, tier, status, reason, fee_type, expected, received, delta,
             at_risk, explanation, matched, age, confidence=None, ai_evidence=None,
             ai_recommendation=None):
        out.append(dict(
            record_id=rid, tier=tier, tier_name=TIER_NAMES[tier], status=status,
            reason=reason, reason_label=REASON_LEGEND[reason][0] if reason else "",
            fee_type=fee_type, expected=expected, received=received, delta=delta,
            amount_at_risk=at_risk, priority=priority_of(at_risk, tier) if at_risk else "",
            explanation=explanation, matched_settlement=matched, age_days=age,
            ai_assisted=(tier == 3 or (tier == 4 and status == "MANUAL_REVIEW")),
            # Real AI output when RECONAI_LLM=1 diagnosed this record; None/[]
            # on every other path (deterministic clears, offline stub, non-AI
            # exceptions) -- there's no "confidence" to report when no
            # judgement call was made.
            confidence=confidence, ai_evidence=ai_evidence or [],
            ai_recommendation=ai_recommendation))

    for o in orders.to_dict("records"):
        rid, amt, mode = o["order_id"], o["amount_paise"], o["payment_mode"]
        age = (RUN_DATE - date.fromisoformat(o["order_date"])).days
        band = fee_band(amt, mode)

        # ---------------- Tier 0: COD timing pre-check ----------------------
        # Runs before the waterfall. A COD order with no remittance yet is not
        # a matching failure -- it is a clock that is still running.
        if mode == "COD" and not o["bank_utr"]:
            bucket = cod_age_bucket(age)
            if bucket == "EXCEPTION":
                emit(rid, 0, "EXCEPTION", "R2_REMITTANCE_OVERDUE", "", amt, 0, 0,
                     amt, f"COD order is {age} days old with no courier remittance. "
                          f"Past the 14-day threshold; chase the courier.", "", age)
            else:
                emit(rid, 0, bucket, "R1_AWAITING_REMITTANCE", "", amt, 0, 0, 0,
                     f"COD order placed {age} days ago, inside the normal "
                     f"0-14 day collection window. No action needed.", "", age)
            continue

        # ---------------- identifier selection ------------------------------
        # Online orders join on gateway_ref_id. COD and direct transfers have
        # no ref at all, which is what routes them to Tier 4.
        if o["gateway_ref_id"]:
            cands = by_ref.get(o["gateway_ref_id"], [])
            path_tier, ident = None, o["gateway_ref_id"]
        else:
            cands = by_utr.get(o["bank_utr"], [])
            path_tier, ident = 4, o["bank_utr"]

        # ---------------- Tier 5: nothing, or too many ----------------------
        if not cands:
            emit(rid, 5, "EXCEPTION", "R3_UNMATCHED_AMBIGUOUS", "", amt, 0, 0, amt,
                 f"No settlement in the feed carries {ident}. The full order value "
                 f"is unaccounted for.", "", age)
            continue

        if len(cands) > 1:
            ids = ", ".join(c["settlement_id"] for c in cands)
            emit(rid, 5, "EXCEPTION", "R3_UNMATCHED_AMBIGUOUS", "", amt, 0, 0, amt,
                 f"{len(cands)} settlements claim {ident} ({ids}). Refusing to pick "
                 f"one; a wrong match here books the wrong revenue.", "", age)
            for c in cands:
                consumed.add(c["settlement_id"])
            continue

        # ---------------- matched: now classify the amount ------------------
        m = cands[0]
        consumed.add(m["settlement_id"])
        recv = m["amount_paise"]
        delta = recv - amt
        fee_type = "COD_COLLECTION_FEE" if mode == "COD" else "GATEWAY_FEE"

        if delta == 0:
            tier = path_tier or 1
            emit(rid, tier, "AUTO_CLEARED", "", "", amt, recv, 0, 0,
                 f"Matched on {ident}; amount identical to the paise.",
                 m["settlement_id"], age)

        elif -band <= delta < 0:
            tier = path_tier or 2
            emit(rid, tier, "CLEARED_WITH_FEE", "", fee_type, amt, recv, delta, 0,
                 f"Short by {fmt(-delta)}, inside the {fmt(band)} "
                 f"{'COD collection fee' if mode == 'COD' else 'gateway fee'} band "
                 f"for this order.", m["settlement_id"], age)

        else:
            # outside every band: Tier 3 logic, whichever path got us here
            diagnosis = ai_diagnose(dict(
                record_id=rid, order_amount=amt, received=recv, delta=delta,
                band=band, payment_mode=mode, identifier=ident, age_days=age,
                settlement_id=m["settlement_id"]))
            tier = path_tier or 3
            emit(rid, tier, "MANUAL_REVIEW", diagnosis["reason_code"], "", amt, recv, delta,
                 abs(delta), diagnosis["explanation"], m["settlement_id"], age,
                 confidence=diagnosis["confidence"], ai_evidence=diagnosis["evidence"],
                 ai_recommendation=diagnosis["recommendation"])

    # ---------------- Tier 5: credits with no order behind them -------------
    for s in setls.to_dict("records"):
        if s["settlement_id"] in consumed:
            continue
        emit(s["settlement_id"], 5, "EXCEPTION", "R3_UNMATCHED_AMBIGUOUS", "",
             0, s["amount_paise"], s["amount_paise"], s["amount_paise"],
             f"Credit of {fmt(s['amount_paise'])} in the feed with no order behind "
             f"it. Narration: {s['narration']}", s["settlement_id"], None)

    df = pd.DataFrame(out)
    return df.sort_values(["amount_at_risk", "record_id"], ascending=[False, True])


# ===========================================================================
# Scorecard
# ===========================================================================
def score(res: pd.DataFrame):
    gt = pd.read_csv(f"{DATA}/ground_truth.csv", dtype=str).fillna("")
    gt = gt.set_index("record_id")
    j = res.set_index("record_id").join(gt, how="outer", rsuffix="_gt")

    missing = j[j["tier"].isna()]
    extra = j[j["expected_tier"].isna()]
    j = j.dropna(subset=["tier", "expected_tier"])

    j["tier_ok"] = j["tier"].astype(int) == j["expected_tier"].astype(int)
    j["status_ok"] = j["status"] == j["expected_status"]
    j["reason_ok"] = j["reason"] == j["expected_reason"]

    CLEAR = {"AUTO_CLEARED", "CLEARED_WITH_FEE"}
    pred_clear = j["status"].isin(CLEAR)
    true_clear = j["expected_status"].isin(CLEAR)
    tp = int((pred_clear & true_clear).sum())
    fp = int((pred_clear & ~true_clear).sum())
    fn = int((~pred_clear & true_clear).sum())

    n = len(j)
    w = 30
    print("=" * 74)
    print("RECONCILIATION SCORECARD".center(74))
    print("=" * 74)
    print(f"  {'records scored':<{w}}{n:>6}")
    if len(missing):
        print(f"  {'LABELLED BUT NOT PROCESSED':<{w}}{len(missing):>6}  <-- bug")
    if len(extra):
        print(f"  {'PROCESSED BUT NOT LABELLED':<{w}}{len(extra):>6}  <-- bug")
    print(f"  {'tier correct':<{w}}{j['tier_ok'].sum():>6}   {j['tier_ok'].mean():>7.2%}")
    print(f"  {'disposition correct':<{w}}{j['status_ok'].sum():>6}   {j['status_ok'].mean():>7.2%}")
    print(f"  {'reason code correct':<{w}}{j['reason_ok'].sum():>6}   {j['reason_ok'].mean():>7.2%}")

    print(f"\n  clearing decision")
    print(f"    {'precision':<{w-4}}{tp/(tp+fp) if tp+fp else 1:>9.2%}   "
          f"false clears: {fp}  (money wrongly signed off)")
    print(f"    {'recall':<{w-4}}{tp/(tp+fn) if tp+fn else 1:>9.2%}   "
          f"missed clears: {fn}  (humans bothered for nothing)")

    ai = int(res["ai_assisted"].sum())
    print(f"\n  {'resolved without any AI call':<{w}}{len(res)-ai:>6}   "
          f"{(len(res)-ai)/len(res):>7.2%}")
    print(f"  {'sent to the model':<{w}}{ai:>6}   {ai/len(res):>7.2%}")

    print("\n  tier distribution        engine   labelled")
    for t in range(6):
        e = int((res["tier"] == t).sum())
        g = int((gt["expected_tier"].astype(int) == t).sum())
        flag = "" if e == g else "   <-- differs"
        print(f"    tier {t}  {TIER_NAMES[t]:<26}{e:>4}   {g:>8}{flag}")

    bad = j[~j["tier_ok"] | ~j["status_ok"] | ~j["reason_ok"]]
    if len(bad):
        print(f"\n  MISCLASSIFIED ({len(bad)})")
        for rid, r in bad.head(15).iterrows():
            print(f"    {rid:<12} got tier {int(r['tier'])}/{r['status']}/{r['reason']}"
                  f"   want tier {r['expected_tier']}/{r['expected_status']}/"
                  f"{r['expected_reason']}   [{r['scenario']}]")
    else:
        print("\n  PERFECT  every record landed on its labelled tier, disposition "
              "and reason")
    return len(bad) == 0 and not len(missing) and not len(extra)


def summary(res: pd.DataFrame):
    cleared = res[res["status"].isin(["AUTO_CLEARED", "CLEARED_WITH_FEE"])]
    inflight = res[res["status"].isin(["AWAITING_REMITTANCE", "APPROACHING_THRESHOLD"])]
    action = res[res["status"].isin(["MANUAL_REVIEW", "EXCEPTION"])]
    print("\n" + "=" * 74)
    print("BATCH SUMMARY".center(74))
    print("=" * 74)
    print(f"  records processed   {len(res):>5}")
    print(f"  auto-matched        {len(cleared):>5}   {len(cleared)/len(res):.1%}")
    print(f"  in flight           {len(inflight):>5}   healthy COD, not failures")
    print(f"  needs action        {len(action):>5}   {fmt(int(action['amount_at_risk'].sum()))} at risk")

    print("\n  EXCEPTION QUEUE  (top 10 by amount at risk)")
    print(f"    {'PRI':<8}{'RECORD':<12}{'TIER':<6}{'REASON':<30}{'AT RISK':>13}")
    for r in action.head(10).to_dict("records"):
        print(f"    {r['priority']:<8}{r['record_id']:<12}{r['tier']:<6}"
              f"{r['reason_label'][:28]:<30}{fmt(r['amount_at_risk']):>13}")
    print(f"\n    ... {len(action)-10} more")


if __name__ == "__main__":
    orders, setls = load()
    res = reconcile(orders, setls)
    res_out = res.copy()
    for c in ("expected", "received", "delta", "amount_at_risk"):
        res_out[c] = res_out[c].map(to_rupees)
    res_out.to_csv(f"{DATA}/run_results.csv", index=False)
    ok = score(res)
    summary(res)
    print(f"\n  wrote {DATA}/run_results.csv")
    sys.exit(0 if ok else 1)
