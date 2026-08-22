"""
ReconAI — data integrity check.

Verifies the generated data is internally consistent BEFORE the engine ever
runs. If the generator and config.py disagree about tolerance bands or COD
ageing windows, the accuracy score would be measuring nothing. This catches it.
"""
import csv
from datetime import date
from pathlib import Path

from config import (RUN_DATE, REASON_LEGEND, FEE_TYPES,
                    to_paise, fee_band, cod_age_bucket, fmt)

D = Path(__file__).parent / "data"
load = lambda f: list(csv.DictReader(open(D / f)))

orders = {o["order_id"]: o for o in load("orders.csv")}
setls = load("settlements.csv")
truth = load("ground_truth.csv")

by_ref, by_utr = {}, {}
for s in setls:
    if s["gateway_ref_id"]:
        by_ref.setdefault(s["gateway_ref_id"], []).append(s)
    if s["bank_utr"]:
        by_utr.setdefault(s["bank_utr"], []).append(s)

fails = []
check = lambda cond, msg: None if cond else fails.append(msg)

for t in truth:
    rid, scen, tier = t["record_id"], t["scenario"], int(t["expected_tier"])
    status, reason, fee_type = (t["expected_status"], t["expected_reason"],
                                t["expected_fee_type"])

    # -- reason / fee_type vocabulary ---------------------------------------
    check(reason == "" or reason in REASON_LEGEND, f"{rid}: unknown reason '{reason}'")
    check(fee_type == "" or fee_type in FEE_TYPES, f"{rid}: unknown fee_type '{fee_type}'")
    if status in ("AUTO_CLEARED", "CLEARED_WITH_FEE"):
        check(reason == "", f"{rid}: cleared record should carry no reason code")
    if status in ("MANUAL_REVIEW", "EXCEPTION", "APPROACHING_THRESHOLD",
                  "AWAITING_REMITTANCE"):
        check(reason != "", f"{rid}: unresolved record has no reason code")
    check((fee_type != "") == (status == "CLEARED_WITH_FEE"),
          f"{rid}: fee_type '{fee_type}' inconsistent with status {status}")

    if scen == "T5_UNKNOWN_CREDIT":
        continue

    o = orders.get(rid)
    check(o is not None, f"{rid}: labelled but missing from orders.csv")
    if not o:
        continue

    amt = to_paise(o["order_amount"])
    band = fee_band(amt, o["payment_mode"])

    # -- tier 0: COD timing pre-check ---------------------------------------
    if tier == 0:
        age = (RUN_DATE - date.fromisoformat(o["order_date"])).days
        check(o["payment_mode"] == "COD", f"{rid}: tier 0 but mode is {o['payment_mode']}")
        check(o["bank_utr"] == "", f"{rid}: awaiting remittance but already has a UTR")
        check(o["gateway_ref_id"] == "", f"{rid}: COD order carries a gateway ref")
        check(age >= 0, f"{rid}: order dated after the run date")
        check(cod_age_bucket(age) == status,
              f"{rid}: {age}d ages to {cod_age_bucket(age)}, labelled {status}")
        check(reason == ("R2_REMITTANCE_OVERDUE" if status == "EXCEPTION"
                         else "R1_AWAITING_REMITTANCE"),
              f"{rid}: reason {reason} does not match bucket {status}")
        continue

    # -- structural: tier 4 has no ref, tiers 1-3 must have one -------------
    if tier == 4:
        check(o["gateway_ref_id"] == "", f"{rid}: tier 4 but has a gateway_ref_id")
        check(o["bank_utr"] != "", f"{rid}: tier 4 but has no bank_utr")
    if tier in (1, 2, 3):
        check(o["gateway_ref_id"] != "", f"{rid}: tier {tier} but has no gateway_ref_id")

    # -- COD fee must be tagged as COD, online fee as gateway ---------------
    if status == "CLEARED_WITH_FEE":
        want = "COD_COLLECTION_FEE" if o["payment_mode"] == "COD" else "GATEWAY_FEE"
        check(fee_type == want, f"{rid}: {o['payment_mode']} fee tagged {fee_type}")

    matches = (by_ref.get(o["gateway_ref_id"], []) if o["gateway_ref_id"]
               else by_utr.get(o["bank_utr"], []))

    if status == "EXCEPTION" and scen != "T5_DUPLICATE_MATCH":
        check(len(matches) == 0, f"{rid}: expected no match, found {len(matches)}")
        continue
    if scen == "T5_DUPLICATE_MATCH":
        check(len(matches) == 2, f"{rid}: expected 2 competing settlements")
        continue

    check(len(matches) == 1, f"{rid}: expected exactly 1 settlement, got {len(matches)}")
    if len(matches) != 1:
        continue

    delta = to_paise(matches[0]["amount_received"]) - amt
    check(delta == to_paise(t["expected_delta"]),
          f"{rid}: delta {fmt(delta)} != labelled {t['expected_delta']}")
    check(date.fromisoformat(matches[0]["settled_on"]) <= RUN_DATE,
          f"{rid}: settled after the run date")

    if status == "AUTO_CLEARED":
        check(delta == 0, f"{rid}: AUTO_CLEARED but delta is {fmt(delta)}")
    elif status == "CLEARED_WITH_FEE":
        check(-band <= delta < 0,
              f"{rid}: CLEARED_WITH_FEE but {fmt(delta)} outside band {fmt(band)}")
    elif status == "MANUAL_REVIEW":
        check(delta > 0 or delta < -band,
              f"{rid}: MANUAL_REVIEW but {fmt(delta)} sits inside band {fmt(band)}")

# -- no settlement may be claimed by two different orders -------------------
claimed = {}
for o in orders.values():
    if not o["gateway_ref_id"] and not o["bank_utr"]:
        continue                       # COD awaiting remittance: no key yet
    key = ("ref", o["gateway_ref_id"]) if o["gateway_ref_id"] else ("utr", o["bank_utr"])
    check(key not in claimed, f"{o['order_id']}: key {key} collides with {claimed.get(key)}")
    claimed[key] = o["order_id"]

# -- every order must be labelled exactly once ------------------------------
labelled = [t["record_id"] for t in truth]
check(len(labelled) == len(set(labelled)), "duplicate record_id in ground_truth.csv")
for oid in orders:
    check(oid in set(labelled), f"{oid}: present in orders.csv but never labelled")

print("=" * 66)
print(f"  run date     {RUN_DATE}")
print(f"  orders       {len(orders):>4}")
print(f"  settlements  {len(setls):>4}")
print(f"  labels       {len(truth):>4}")
print("=" * 66)
if fails:
    print(f"  FAILED  {len(fails)} problem(s):\n")
    for f in fails[:25]:
        print("   -", f)
    print(f"\n  (showing {min(25, len(fails))} of {len(fails)})")
else:
    print("  PASS  data is consistent with config.py bands and COD ageing windows")
