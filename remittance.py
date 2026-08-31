"""
Ledgr -- courier COD remittance detail.

WHAT THIS IS
------------
A bulk COD payout arrives in the bank as ONE credit ("UTR001 -> Rs 2,185").
On its own that credit cannot say which orders it covers, and the previous
behaviour was to leave the orders looking unpaid AND the credit looking
unexplained -- the same money counted twice, with the system recommending
both "chase the courier" and "consider refunding" for one payment.

Couriers do not actually make merchants guess: alongside the payment they
publish a remittance file, one row per delivered order, carrying the order id
and the per-order fee breakdown. `data/remittances.csv` is the synthetic
stand-in for that file.

This module joins those three things:

    Shopify COD order  ->  courier remittance row  ->  Bank/COD credit

DELIBERATELY DETERMINISTIC
--------------------------
There is no AI anywhere in this file, and there must not be. When structured
remittance detail exists the answer is a LOOKUP, not a judgement -- the
remittance row names the order id outright. An earlier design scored
candidate subsets by amount instead; tested against this dataset it returned
twelve equally plausible groupings for one credit and confidently mis-matched
an unrelated one. A guess is the wrong tool for a question that has a
provable answer.

AI keeps the genuinely ambiguous half: explaining a discrepancy this module
FINDS, and drafting the dispute to the courier.

SCOPE
-----
This belongs to the existing Bank / COD source. It is not a fourth data
source, and it does not touch engine.py -- the reconciliation waterfall,
tiers and matching rules are unchanged. This runs after reconcile() and
explains records the waterfall could not.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from datetime import date

from config import DATA_DIR, RUN_DATE, cod_age_bucket, fee_band, to_paise

REMITTANCE_FILE = Path(__file__).parent / DATA_DIR / "remittances.csv"

# Rupee columns on disk; everything downstream works in integer paise so no
# float arithmetic ever touches a money comparison.
_MONEY_COLUMNS = ("cod_collected", "cod_fee", "freight_fee", "net_payout")

# Discrepancy kinds. Each is a fact the join can PROVE, not an inference.
MISSING_FROM_REMITTANCE = "order_missing_from_remittance"
UNKNOWN_ORDER = "remittance_order_unknown"
DUPLICATE_ORDER = "order_in_multiple_batches"
CHECKSUM_MISMATCH = "batch_checksum_mismatch"
COLLECTED_MISMATCH = "cod_collected_mismatch"
FEE_OVER_BAND = "cod_fee_over_band"
NO_BANK_CREDIT = "remittance_batch_without_credit"


def load_remittances(path: Path | str | None = None) -> list[dict]:
    """
    Read the remittance detail file, money normalised to integer paise.

    Returns [] when the file is absent -- the feature is additive, and a
    merchant who has not supplied remittance detail must still reconcile
    exactly as before rather than crash.
    """
    p = Path(path) if path else REMITTANCE_FILE
    if not p.exists():
        return []
    rows = []
    with open(p, newline="", encoding="utf-8") as f:
        for raw in csv.DictReader(f):
            row = dict(raw)
            for col in _MONEY_COLUMNS:
                row[col] = to_paise(float(row.get(col) or 0))
            rows.append(row)
    return rows


def _bank_credits_by_utr(settlements: list[dict]) -> dict[str, dict]:
    """Bank-side credits keyed by UTR. Gateway rows are irrelevant here --
    Razorpay never sees COD cash."""
    out = {}
    for s in settlements:
        if _s(s.get("source")).upper() != "BANK":
            continue
        utr = _s(s.get("bank_utr"))
        if utr:
            out[utr] = s
    return out


def reconcile_remittances(remittances: list[dict], orders: list[dict],
                          settlements: list[dict]) -> dict:
    """
    Join remittance rows to orders and to the bank credit they belong to.

    Returns:
      links        order_id -> the remittance row + the credit that paid it.
                   These orders are PROVABLY paid; they must stop being
                   reported as awaiting or overdue.
      batches      utr -> credit, row total, checksum result, order ids
      discrepancies  everything the join could not square, each with the
                   evidence behind it. These are exceptions for a human --
                   never silently absorbed.
    """
    orders_by_id = {o["order_id"]: o for o in orders}
    credits = _bank_credits_by_utr(settlements)

    by_utr: dict[str, list[dict]] = defaultdict(list)
    for r in remittances:
        by_utr[_s(r.get("settlement_utr"))].append(r)

    # An order legitimately appears once. Twice means it was remitted twice
    # (or reported twice) -- real money either way, so it is surfaced rather
    # than deduplicated away.
    utrs_by_order: dict[str, list[str]] = defaultdict(list)
    for utr, rows in by_utr.items():
        for r in rows:
            utrs_by_order[r["order_id"]].append(utr)

    links: dict[str, dict] = {}
    batches: dict[str, dict] = {}
    discrepancies: list[dict] = []

    for utr, rows in by_utr.items():
        credit = credits.get(utr)
        rows_total = sum(r["net_payout"] for r in rows)
        credit_amount = to_paise(float(credit["amount_received"])) if credit else 0

        # ---- checksum: the rows must add up to the money that arrived -----
        checksum_ok = bool(credit) and rows_total == credit_amount
        batches[utr] = {
            "utr": utr,
            "settlement_id": credit["settlement_id"] if credit else None,
            "courier": rows[0].get("courier", ""),
            "remitted_on": rows[0].get("remitted_on", ""),
            "order_count": len(rows),
            "rows_total": rows_total,
            "credit_amount": credit_amount,
            "checksum_ok": checksum_ok,
            "order_ids": [r["order_id"] for r in rows],
        }

        if not credit:
            discrepancies.append({
                "kind": NO_BANK_CREDIT, "utr": utr, "order_id": None,
                "amount_at_risk": rows_total,
                "detail": (f"Remittance file lists {len(rows)} order(s) totalling "
                           f"{_rs(rows_total)} under {utr}, but no bank credit with "
                           f"that UTR has arrived."),
            })
        elif not checksum_ok:
            gap = credit_amount - rows_total
            discrepancies.append({
                "kind": CHECKSUM_MISMATCH, "utr": utr,
                "order_id": None, "amount_at_risk": abs(gap),
                "detail": (f"Remittance rows for {utr} total {_rs(rows_total)} but the "
                           f"bank credit is {_rs(credit_amount)} -- a gap of {_rs(abs(gap))}. "
                           f"The batch is not linked to its orders until this squares."),
            })

        for r in rows:
            oid = r["order_id"]
            order = orders_by_id.get(oid)

            if order is None:
                discrepancies.append({
                    "kind": UNKNOWN_ORDER, "utr": utr, "order_id": oid,
                    "amount_at_risk": r["net_payout"],
                    "detail": (f"{utr} remits {_rs(r['net_payout'])} for order {oid}, "
                               f"which does not exist in our order book."),
                })
                continue

            if len(set(utrs_by_order[oid])) > 1:
                discrepancies.append({
                    "kind": DUPLICATE_ORDER, "utr": utr, "order_id": oid,
                    "amount_at_risk": r["net_payout"],
                    "detail": (f"Order {oid} appears in more than one remittance batch "
                               f"({', '.join(sorted(set(utrs_by_order[oid])))})."),
                })

            expected = to_paise(float(order.get("order_amount") or 0))
            if r["cod_collected"] != expected:
                discrepancies.append({
                    "kind": COLLECTED_MISMATCH, "utr": utr, "order_id": oid,
                    "amount_at_risk": abs(expected - r["cod_collected"]),
                    "detail": (f"Courier collected {_rs(r['cod_collected'])} for {oid} but the "
                               f"order value is {_rs(expected)}."),
                })

            # The same contracted band engine.py uses at Tier 2/4, so the
            # policy is defined in exactly one place.
            band = fee_band(expected, "COD")
            charged = r["cod_fee"] + r["freight_fee"]
            if charged > band:
                discrepancies.append({
                    "kind": FEE_OVER_BAND, "utr": utr, "order_id": oid,
                    "amount_at_risk": charged - band,
                    "detail": (f"{oid} was charged {_rs(charged)} in courier fees, above the "
                               f"contracted ceiling of {_rs(band)}."),
                })

            # Only a batch that squares against the bank is allowed to mark an
            # order paid. If the money did not arrive as stated, the paperwork
            # alone must not clear anything.
            if checksum_ok:
                links[oid] = {
                    "order_id": oid, "utr": utr,
                    "settlement_id": credit["settlement_id"],
                    "awb": r.get("awb", ""),
                    "courier": r.get("courier", ""),
                    "remitted_on": r.get("remitted_on", ""),
                    "cod_collected": r["cod_collected"],
                    "cod_fee": r["cod_fee"],
                    "freight_fee": r["freight_fee"],
                    "net_payout": r["net_payout"],
                    "batch_order_count": len(rows),
                    "batch_credit": credit_amount,
                }

    discrepancies.extend(
        _find_orders_missing_from_remittance(orders, batches, links))

    return {"links": links, "batches": batches, "discrepancies": discrepancies}


def _find_orders_missing_from_remittance(orders, batches, links) -> list[dict]:
    """
    A COD order the courier has NOT accounted for.

    Deliberately narrow, on TWO conditions -- both required:

      1. the order is already past its COD collection window (the same
         threshold Tier 0 uses), and
      2. the courier has remitted a batch since the order was placed.

    Condition 1 is not optional. Couriers remit continuously, so a batch that
    happens not to contain an order proves nothing while that order is still
    inside its normal window -- it may simply be in the next batch. Without
    this the check fired on an order placed 10 days earlier that was in no way
    late, inventing a problem and contradicting Tier 0 on the same record.
    """
    latest_by_courier: dict[str, str] = {}
    for b in batches.values():
        c = _s(b.get("courier")).upper()
        if not c:
            continue
        if b["remitted_on"] > latest_by_courier.get(c, ""):
            latest_by_courier[c] = b["remitted_on"]

    out = []
    for o in orders:
        if _s(o.get("payment_mode")).upper() != "COD":
            continue
        if o["order_id"] in links or _s(o.get("bank_utr")):
            continue
        courier = _s(o.get("courier")).upper()
        remitted_on = latest_by_courier.get(courier)
        order_date = _s(o.get("order_date"))
        if not remitted_on or not order_date or remitted_on <= order_date:
            continue
        # Still inside the normal collection window -> not late, no claim.
        age = (RUN_DATE - date.fromisoformat(order_date)).days
        if cod_age_bucket(age) != "EXCEPTION":
            continue
        out.append({
            "kind": MISSING_FROM_REMITTANCE, "utr": None,
            "order_id": o["order_id"],
            "amount_at_risk": to_paise(float(o.get("order_amount") or 0)),
            "detail": (f"{courier} remitted on {remitted_on}, after this order was placed "
                       f"on {order_date}, but {o['order_id']} was not in that batch."),
        })
    return out


def _rs(paise: int) -> str:
    return f"Rs {paise / 100:,.2f}"


def _s(value) -> str:
    """
    A trimmed string for a field that may arrive as NaN.

    Callers pass rows from either csv.DictReader (empty cell -> "") or a
    pandas DataFrame (empty cell -> float NaN). Treating NaN as text raised
    AttributeError on the first real dataset, so every optional text field
    goes through here.
    """
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text
