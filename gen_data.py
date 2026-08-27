"""
Ledgr — synthetic data generator.

Produces three files in data/:

  orders.csv        internal system of record (what we believe we sold)
  settlements.csv   bank + gateway feed      (what actually landed)
  ground_truth.csv  labelled expected outcome for every record

Design notes
------------
* Scenarios are STRATIFIED, not random: a fixed quota of each case is emitted
  so the accuracy score is measured against a known, balanced distribution.
* Every order carries gateway_ref_id (online) OR bank_utr (COD / direct
  transfer), never both. That is what forces the Tier 4 fallback path.
* COD orders are aged deliberately against config.RUN_DATE so the timing
  pre-check has fresh / approaching / overdue cases to find.
* Ground truth records the tier that SHOULD resolve each record, the expected
  disposition, the expected rupee delta, and the expected reason code.
"""
import csv
import os
import random
from datetime import timedelta
from pathlib import Path

from config import (RUN_DATE, to_paise, to_rupees, fee_band, cod_age_bucket)

random.seed(int(os.environ.get("RECONAI_SEED", 20260905)))
OUT = Path(__file__).parent / "data"
OUT.mkdir(exist_ok=True)

START_DATE = RUN_DATE - timedelta(days=31)

CUSTOMERS = [
    "Aarav Sharma", "Diya Patel", "Vihaan Reddy", "Ananya Iyer", "Kabir Singh",
    "Meera Nair", "Rohan Gupta", "Ishita Bose", "Arjun Menon", "Sara Khan",
    "Aditya Rao", "Nisha Verma", "Kartik Joshi", "Priya Desai", "Yash Malhotra",
]
COURIERS = ["DELHIVERY", "BLUEDART", "ECOM EXPRESS", "XPRESSBEES"]
ONLINE_MODES = ["UPI", "CARD", "NETBANKING", "WALLET"]

# Deterministic per-customer contact info -- same customer always gets the
# same phone/email, so Tier-3 AI correlation (Case 2/3: does this orphan
# settlement's evidence match a real customer we already have an order for)
# has something consistent to match against.
def _slug(name):
    return name.lower().replace(" ", ".")


CUSTOMER_PHONE = {c: f"+91 9{800000000 + i * 1111:09d}" for i, c in enumerate(CUSTOMERS)}
CUSTOMER_EMAIL = {c: f"{_slug(c)}@example.com" for c in CUSTOMERS}

# Each courier gets a genuinely different bank narration FORMAT, not just a
# name swap in one shared template -- Case 6 (narration parsing) only means
# something if the formats actually differ structurally.
def courier_narration(courier, utr, batch_no=None):
    if courier == "DELHIVERY":
        return f"NEFT CR-DELHIVERY COD REMIT-{utr}"
    if courier == "BLUEDART":
        return f"IMPS/BLUEDART/COD-SETL/{batch_no or utr[-4:]}"
    if courier == "ECOM EXPRESS":
        return f"RTGS-ECOMEXP-CODCOLL-{utr[-6:]}"
    return f"NEFT CR {utr[-9:]} XXXXX"  # XPRESSBEES: bank truncates hard, no courier name at all

# ---------------------------------------------------------------------------
# Scenario quotas. Weighted like a real book: most things are clean.
# ---------------------------------------------------------------------------
PLAN = (
    ["T1_EXACT"]                * 82   # UPI / zero-MDR, settles at face value
    + ["T2_MDR_FEE"]            * 46   # card / wallet, MDR + GST inside band
    + ["T2_FLAT_FEE"]           * 14   # netbanking flat Rs 2-3
    + ["T3_OVERCHARGED_FEE"]    *  7   # deduction exceeds contracted MDR band
    + ["T3_PARTIAL_SETTLEMENT"] *  8   # refund/chargeback netted off silently
    + ["T3_OVERPAYMENT"]        *  4   # settled MORE than the order value
    + ["T4_COD_EXACT"]          * 18   # courier remitted full value
    + ["T4_COD_FEE"]            * 22   # courier collection fee inside COD band
    + ["T4_COD_SHORTFALL"]      *  6   # COD gap too wide -> review, still T4
    + ["T4_DIRECT_TRANSFER"]    * 10   # B2B NEFT, no gateway involved
    + ["T0_COD_AWAITING"]       * 12   # COD, 0-7 days, clock still running
    + ["T0_COD_APPROACHING"]    *  7   # COD, 8-14 days, visible but not broken
    + ["T0_COD_OVERDUE"]        *  5   # COD, 15+ days, chase the courier
    + ["T5_NO_SETTLEMENT"]      *  9   # online payment, money never arrived
    + ["T5_DUPLICATE_MATCH"]    *  4   # two credits claim the same ref
    + ["T5_ORPHAN_REF"]         *  5   # ref exists in orders, nowhere in feed
)
random.shuffle(PLAN)

ORPHAN_CREDITS = 6                     # settlements with no order behind them

orders, settlements, truth = [], [], []


def new_utr(seq: int) -> str:
    return f"UTR{seq:09d}"


def add_settlement(sid, day, ref, utr, paise, source, narration):
    settlements.append({
        "settlement_id": sid,
        "settled_on": str(day),
        "gateway_ref_id": ref or "",
        "bank_utr": utr,
        "amount_received": to_rupees(paise),
        "source": source,
        "narration": narration,
    })


def add_truth(rid, scenario, tier, status, delta_paise, reason, fee_type, note):
    truth.append({
        "record_id": rid,
        "scenario": scenario,
        "expected_tier": tier,
        "expected_status": status,
        "expected_delta": to_rupees(delta_paise),
        "expected_reason": reason,
        "expected_fee_type": fee_type,
        "note": note,
    })


# ---------------------------------------------------------------------------
for i, scenario in enumerate(PLAN, start=1):
    order_id = f"ORD-{i:05d}"
    amount = to_paise(random.choice([349, 599, 899, 1249, 1899, 2499, 3999, 6499, 9999])
                      + random.choice([0, 0.50, 0.99]))
    cust = random.choice(CUSTOMERS)
    sid = f"STL-{i:05d}"
    utr = new_utr(400000 + i)

    # -- order date is chosen per scenario so COD ageing is deliberate -------
    if scenario == "T0_COD_AWAITING":
        order_day = RUN_DATE - timedelta(days=random.randint(0, 7))
    elif scenario == "T0_COD_APPROACHING":
        order_day = RUN_DATE - timedelta(days=random.randint(8, 14))
    elif scenario == "T0_COD_OVERDUE":
        order_day = RUN_DATE - timedelta(days=random.randint(15, 30))
    elif scenario.startswith("T4_COD"):
        # must leave room for a 3-12 day courier remittance lag
        order_day = START_DATE + timedelta(days=random.randint(0, 16))
    else:
        order_day = START_DATE + timedelta(days=random.randint(0, 28))

    is_cod = scenario.startswith(("T4_COD", "T0_COD"))
    is_direct = scenario == "T4_DIRECT_TRANSFER"

    if is_cod:
        mode, ref, order_utr = "COD", "", utr
        lag = random.randint(3, 12)
    elif is_direct:
        mode, ref, order_utr = "BANK_TRANSFER", "", utr
        lag = random.randint(1, 3)
    else:
        mode = random.choice(ONLINE_MODES)
        ref, order_utr = f"pay_{i:06d}{random.choice('ABCDEF')}", ""
        lag = random.randint(1, 2)

    settle_day = min(order_day + timedelta(days=lag), RUN_DATE)

    # COD orders awaiting remittance have no UTR on the order yet either --
    # the reference only exists once the courier actually remits.
    if scenario.startswith("T0_COD"):
        order_utr = ""

    # Courier is a delivery/fulfillment detail, independent of payment mode --
    # a prepaid order still ships via a courier, COD only describes how the
    # customer paid. Populated for every order (Case 7 needs an addressee).
    courier = random.choice(COURIERS)

    orders.append({
        "order_id": order_id,
        "order_date": str(order_day),
        "customer_name": cust,
        "customer_phone": CUSTOMER_PHONE[cust],
        "customer_email": CUSTOMER_EMAIL[cust],
        "courier": courier,
        "payment_mode": mode,
        "gateway_ref_id": ref,
        "bank_utr": order_utr,
        "order_amount": to_rupees(amount),
    })

    band = fee_band(amount, mode)
    gw_narr = f"RAZORPAY SETTLEMENT {utr}"
    bank_narr = courier_narration(courier, utr)
    b2b_narr = f"NEFT CR-{cust.upper()}-{utr}"

    # ---------------- Tier 0: COD timing pre-check --------------------------
    if scenario.startswith("T0_COD"):
        age = (RUN_DATE - order_day).days
        bucket = cod_age_bucket(age)
        reason = ("R2_REMITTANCE_OVERDUE" if bucket == "EXCEPTION"
                  else "R1_AWAITING_REMITTANCE")
        add_truth(order_id, scenario, 0, bucket, 0, reason, "",
                  f"COD, {age} days since order, no remittance yet")

    # ---------------- Tier 1 ------------------------------------------------
    elif scenario == "T1_EXACT":
        add_settlement(sid, settle_day, ref, utr, amount, "RAZORPAY", gw_narr)
        add_truth(order_id, scenario, 1, "AUTO_CLEARED", 0, "", "",
                  "ref + amount exact")

    # ---------------- Tier 2 ------------------------------------------------
    elif scenario == "T2_MDR_FEE":
        mdr = int(amount * random.choice([0.010, 0.012, 0.015]))
        fee = mdr + int(mdr * 0.18)
        add_settlement(sid, settle_day, ref, utr, amount - fee, "RAZORPAY", gw_narr)
        add_truth(order_id, scenario, 2, "CLEARED_WITH_FEE", -fee, "", "GATEWAY_FEE",
                  "MDR + 18% GST, inside contracted band")

    elif scenario == "T2_FLAT_FEE":
        fee = random.choice([200, 250, 300])
        add_settlement(sid, settle_day, ref, utr, amount - fee, "RAZORPAY", gw_narr)
        add_truth(order_id, scenario, 2, "CLEARED_WITH_FEE", -fee, "", "GATEWAY_FEE",
                  "flat netbanking fee, inside band")

    # ---------------- Tier 3 ------------------------------------------------
    elif scenario == "T3_OVERCHARGED_FEE":
        fee = band + int(amount * random.uniform(0.008, 0.02)) + 150
        add_settlement(sid, settle_day, ref, utr, amount - fee, "RAZORPAY", gw_narr)
        add_truth(order_id, scenario, 3, "MANUAL_REVIEW", -fee, "R5_AI_VARIANCE", "",
                  "deduction exceeds contracted MDR band")

    elif scenario == "T3_PARTIAL_SETTLEMENT":
        cut = int(amount * random.choice([0.25, 0.40, 0.50]))
        add_settlement(sid, settle_day, ref, utr, amount - cut, "RAZORPAY", gw_narr)
        add_truth(order_id, scenario, 3, "MANUAL_REVIEW", -cut, "R4_PARTIAL_PAYMENT", "",
                  "large shortfall, likely refund or chargeback netted off")

    elif scenario == "T3_OVERPAYMENT":
        extra = int(amount * random.choice([0.10, 1.00]))
        add_settlement(sid, settle_day, ref, utr, amount + extra, "RAZORPAY", gw_narr)
        add_truth(order_id, scenario, 3, "MANUAL_REVIEW", extra, "R5_AI_VARIANCE", "",
                  "settled above order value, possible duplicate capture")

    # ---------------- Tier 4 ------------------------------------------------
    elif scenario == "T4_COD_EXACT":
        add_settlement(sid, settle_day, "", utr, amount, "BANK", bank_narr)
        add_truth(order_id, scenario, 4, "AUTO_CLEARED", 0, "", "",
                  "COD remitted in full, matched on UTR")

    elif scenario == "T4_COD_FEE":
        fee = min(band, random.choice([2000, 2500, 3000, 4000, 5000]))
        add_settlement(sid, settle_day, "", utr, amount - fee, "BANK", bank_narr)
        add_truth(order_id, scenario, 4, "CLEARED_WITH_FEE", -fee, "",
                  "COD_COLLECTION_FEE", "COD collection fee, inside COD band")

    elif scenario == "T4_COD_SHORTFALL":
        fee = band + int(amount * random.uniform(0.03, 0.12)) + 2500
        add_settlement(sid, settle_day, "", utr, amount - fee, "BANK", bank_narr)
        add_truth(order_id, scenario, 4, "MANUAL_REVIEW", -fee, "R4_PARTIAL_PAYMENT", "",
                  "COD shortfall beyond collection-fee band")

    elif scenario == "T4_DIRECT_TRANSFER":
        add_settlement(sid, settle_day, "", utr, amount, "BANK", b2b_narr)
        add_truth(order_id, scenario, 4, "AUTO_CLEARED", 0, "", "",
                  "direct bank transfer, no gateway ref, matched on UTR")

    # ---------------- Tier 5 ------------------------------------------------
    elif scenario == "T5_NO_SETTLEMENT":
        add_truth(order_id, scenario, 5, "EXCEPTION", -amount,
                  "R3_UNMATCHED_AMBIGUOUS", "",
                  "no settlement record found for this order")

    elif scenario == "T5_DUPLICATE_MATCH":
        add_settlement(sid, settle_day, ref, utr, amount, "RAZORPAY", gw_narr)
        add_settlement(f"{sid}-D", settle_day + timedelta(days=1), ref,
                       new_utr(900000 + i), amount, "RAZORPAY",
                       f"RAZORPAY SETTLEMENT REPOST {utr}")
        add_truth(order_id, scenario, 5, "EXCEPTION", 0,
                  "R3_UNMATCHED_AMBIGUOUS", "",
                  "two settlements claim the same gateway ref, cannot pick one")

    elif scenario == "T5_ORPHAN_REF":
        add_truth(order_id, scenario, 5, "EXCEPTION", -amount,
                  "R3_UNMATCHED_AMBIGUOUS", "",
                  "gateway ref absent from settlement feed")

# ---------------- Case 2: shadow duplicate payment --------------------------
# One real, cleanly-settled order gets a SECOND orphan Razorpay settlement:
# same amount, one day later, different payment_id/UTR -- the checkout-retry
# duplicate-capture story (see CLAUDE.md Case 2). The original order's own
# outcome is untouched (still a clean Tier 1 match); this is purely an extra
# unmatched settlement for the AI to correlate back to that order via
# amount + timing (customer_phone/email are the evidence Razorpay's real
# payment API would additionally provide in a live system).
_shadow_source = next(t for t in truth if t["scenario"] == "T1_EXACT")
_shadow_order = next(o for o in orders if o["order_id"] == _shadow_source["record_id"])
_shadow_amt = to_paise(_shadow_order["order_amount"])
_shadow_day = min(RUN_DATE, __import__("datetime").date.fromisoformat(_shadow_order["order_date"])
                   + timedelta(days=1))
add_settlement("STL-SHADOW01", _shadow_day, f"pay_shadow{random.randint(100,999)}A",
               new_utr(800001), _shadow_amt, "RAZORPAY",
               f"RAZORPAY SETTLEMENT {new_utr(800001)}")
add_truth("STL-SHADOW01", "T5_SHADOW_DUPLICATE", 5, "EXCEPTION", _shadow_amt,
          "R3_UNMATCHED_AMBIGUOUS", "",
          f"probable duplicate payment for {_shadow_order['order_id']} -- same amount, "
          f"settled one day later under a different payment_id; correlate via "
          f"customer contact ({_shadow_order['customer_name']}) once fetched from Razorpay")

# ---------------- Case 5: COD bulk remittance (one UTR, many orders) --------
# engine.py's by_utr matching is strictly 1:1 (see CLAUDE.md) -- it has no
# concept of one settlement covering several orders. This batch is REAL data
# demonstrating the problem Case 5 needs to solve; it is deliberately left
# OUT of ground_truth.csv (no "correct" tier exists for a pattern the engine
# doesn't support yet), so score() reports these as unlabelled rather than
# silently grading a future feature as a current failure.
_bulk_courier = "DELHIVERY"
_bulk_day = START_DATE + timedelta(days=20)
_bulk_orders = []
for k in range(1, 6):
    oid = f"ORD-BULK{k:02d}"
    amt = to_paise(random.choice([699, 999, 1499, 1999, 2499]))
    cust = random.choice(CUSTOMERS)
    orders.append({
        "order_id": oid, "order_date": str(_bulk_day), "customer_name": cust,
        "customer_phone": CUSTOMER_PHONE[cust], "customer_email": CUSTOMER_EMAIL[cust],
        "courier": _bulk_courier, "payment_mode": "COD", "gateway_ref_id": "",
        "bank_utr": "", "order_amount": to_rupees(amt),
    })
    _bulk_orders.append(amt)
_bulk_utr = new_utr(850001)
_bulk_gross = sum(_bulk_orders)
_bulk_fee_total = sum(min(fee_band(a, "COD"), int(a * 0.025)) for a in _bulk_orders)
add_settlement("STL-BULK01", _bulk_day + timedelta(days=7), "", _bulk_utr,
               _bulk_gross - _bulk_fee_total, "BANK",
               courier_narration(_bulk_courier, _bulk_utr, batch_no="BATCH07"))
# No ground_truth entries for ORD-BULK01..05 or STL-BULK01 -- intentional.

# ---------------- settlements with no order behind them --------------------
for j in range(1, ORPHAN_CREDITS + 1):
    sid = f"STL-X{j:04d}"
    utr = new_utr(700000 + j)
    amt = to_paise(random.randint(800, 9000))
    add_settlement(sid, START_DATE + timedelta(days=random.randint(0, 28)),
                   "", utr, amt, "BANK",
                   random.choice([f"NEFT CR-UNKNOWN REMITTER-{utr}",
                                  f"IMPS/{utr}/MISC CREDIT",
                                  f"NEFT CR-STRIPE PAYMENTS-{utr}"]))
    add_truth(sid, "T5_UNKNOWN_CREDIT", 5, "EXCEPTION", amt,
              "R3_UNMATCHED_AMBIGUOUS", "",
              "credit in bank feed with no corresponding order")

random.shuffle(settlements)

# ---------------------------------------------------------------------------
def dump(name, rows):
    with open(OUT / name, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return len(rows)


counts = {
    "orders.csv": dump("orders.csv", orders),
    "settlements.csv": dump("settlements.csv", settlements),
    "ground_truth.csv": dump("ground_truth.csv", truth),
}

print("=" * 66)
print("SYNTHETIC DATA GENERATED".center(66))
print("=" * 66)
print(f"  run date (as of)     {RUN_DATE}")
for k, v in counts.items():
    print(f"  {k:<20} {v:>5} rows")

print("\n  expected tier distribution")
for tier in range(0, 6):
    rows = [t for t in truth if t["expected_tier"] == tier]
    if not rows:
        continue
    print(f"    tier {tier}  {len(rows):>4}   " +
          ", ".join(sorted({t['scenario'] for t in rows})))

print("\n  expected reason codes (unresolved / informational only)")
for code in sorted({t["expected_reason"] for t in truth if t["expected_reason"]}):
    n = sum(1 for t in truth if t["expected_reason"] == code)
    print(f"    {code:<26} {n:>4}")

gross = sum(to_paise(o["order_amount"]) for o in orders)
recv = sum(to_paise(s["amount_received"]) for s in settlements)
cod_pending = [t for t in truth if t["scenario"].startswith("T0_COD")]
print(f"\n  order book value     Rs {gross/100:>13,.2f}")
print(f"  settlements received Rs {recv/100:>13,.2f}")
print(f"  gap to explain       Rs {(gross-recv)/100:>13,.2f}")
print(f"\n  COD orders           {sum(1 for o in orders if o['payment_mode']=='COD')}"
      f"   ({len(cod_pending)} still awaiting remittance)")
print(f"  orders with no ref   {sum(1 for o in orders if not o['gateway_ref_id'])}")
