"""
Checks for remittance.py -- run directly:  python test_remittance.py

Uses small in-memory fixtures rather than the demo dataset on purpose. The
demo data is deliberately CLEAN (both bulk batches square exactly), because
its job is to prove the happy path end to end. Each failure mode still has to
be proven to fire, and seeding six broken batches into the demo file just to
exercise them would make the demo itself look broken.
"""
import remittance as R
from config import to_rupees

PASS, FAIL = [], []


def check(name, condition, detail=""):
    (PASS if condition else FAIL).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}{'' if condition else '  <- ' + detail}")


def order(oid, amount, courier="DELHIVERY", mode="COD", date="2026-08-10", utr=""):
    return {"order_id": oid, "order_amount": to_rupees(amount), "courier": courier,
            "payment_mode": mode, "order_date": date, "bank_utr": utr}


def credit(sid, utr, paise, date="2026-08-20"):
    return {"settlement_id": sid, "bank_utr": utr, "amount_received": to_rupees(paise),
            "source": "BANK", "settled_on": date, "gateway_ref_id": "", "narration": ""}


def rem(utr, oid, collected, fee=0, freight=0, net=None, courier="DELHIVERY",
        date="2026-08-20"):
    return {"settlement_utr": utr, "order_id": oid, "awb": "AWB1",
            "cod_collected": collected, "cod_fee": fee, "freight_fee": freight,
            "net_payout": collected - fee - freight if net is None else net,
            "remitted_on": date, "courier": courier}


def kinds(result):
    return {d["kind"] for d in result["discrepancies"]}


print("\nremittance.py checks\n" + "-" * 60)

# --- 1. happy path: a batch that squares links every order ------------------
res = R.reconcile_remittances(
    [rem("U1", "O1", 100000, 2500), rem("U1", "O2", 50000, 1250)],
    [order("O1", 100000), order("O2", 50000)],
    [credit("S1", "U1", 146250)])
check("clean batch links all its orders", set(res["links"]) == {"O1", "O2"})
check("clean batch reports no discrepancy", not res["discrepancies"],
      str(kinds(res)))
check("checksum passes when rows sum to the credit",
      res["batches"]["U1"]["checksum_ok"])

# --- 2. checksum mismatch ---------------------------------------------------
res = R.reconcile_remittances(
    [rem("U1", "O1", 100000, 2500)],
    [order("O1", 100000)],
    [credit("S1", "U1", 90000)])          # credit != rows
check("checksum mismatch is detected", R.CHECKSUM_MISMATCH in kinds(res))
check("mismatched batch links NOTHING (never guesses)", res["links"] == {},
      f"linked {list(res['links'])}")

# --- 3. remittance names an order we do not have ----------------------------
res = R.reconcile_remittances(
    [rem("U1", "GHOST", 100000, 2500)],
    [order("O1", 100000)],
    [credit("S1", "U1", 97500)])
check("unknown order id is detected", R.UNKNOWN_ORDER in kinds(res))

# --- 4. same order remitted in two batches ----------------------------------
res = R.reconcile_remittances(
    [rem("U1", "O1", 100000, 2500), rem("U2", "O1", 100000, 2500)],
    [order("O1", 100000)],
    [credit("S1", "U1", 97500), credit("S2", "U2", 97500)])
check("duplicate order across batches is detected",
      R.DUPLICATE_ORDER in kinds(res))

# --- 5. courier collected less than the order was worth ---------------------
res = R.reconcile_remittances(
    [rem("U1", "O1", 80000, 2000)],
    [order("O1", 100000)],
    [credit("S1", "U1", 78000)])
check("short collection is detected", R.COLLECTED_MISMATCH in kinds(res))

# --- 6. fee above the contracted band ---------------------------------------
# COD band is max(COD_TOLERANCE_ABS, 2.5%); on Rs 10,000 that is Rs 250, so
# Rs 900 of fees is unambiguously over.
res = R.reconcile_remittances(
    [rem("U1", "O1", 1000000, 90000)],
    [order("O1", 1000000)],
    [credit("S1", "U1", 910000)])
check("fee over the contracted band is detected", R.FEE_OVER_BAND in kinds(res))

# --- 7. remittance file with no matching bank credit ------------------------
res = R.reconcile_remittances(
    [rem("U9", "O1", 100000, 2500)], [order("O1", 100000)], [])
check("batch with no bank credit is detected", R.NO_BANK_CREDIT in kinds(res))
check("batch with no credit links nothing", res["links"] == {})

# --- 8. overdue order the courier left out ----------------------------------
# O1 is remitted; O2 is far older than the COD window and was not included.
res = R.reconcile_remittances(
    [rem("U1", "O1", 100000, 2500, date="2026-08-28")],
    [order("O1", 100000, date="2026-08-20"),
     order("O2", 70000, date="2026-07-01")],
    [credit("S1", "U1", 97500)])
check("overdue order omitted from remittance is detected",
      R.MISSING_FROM_REMITTANCE in kinds(res))

# --- 9. an order still inside its COD window is NOT accused -----------------
# Same shape, but O2 was placed recently, so its absence proves nothing.
res = R.reconcile_remittances(
    [rem("U1", "O1", 100000, 2500, date="2026-08-30")],
    [order("O1", 100000, date="2026-08-20"),
     order("O2", 70000, date="2026-08-29")],
    [credit("S1", "U1", 97500)])
check("in-window order is NOT reported as missing",
      R.MISSING_FROM_REMITTANCE not in kinds(res), str(kinds(res)))

# --- 10. no remittance file at all is not an error --------------------------
res = R.reconcile_remittances([], [order("O1", 100000)], [credit("S1", "U1", 1)])
check("empty remittance data reconciles cleanly",
      res["links"] == {} and res["discrepancies"] == [])

print("-" * 60)
print(f"  {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("  FAILED: " + ", ".join(FAIL))
raise SystemExit(1 if FAIL else 0)
