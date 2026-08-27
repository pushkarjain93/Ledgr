"""
Upload-only column aliases.

Demo CSVs already use the engine names and must not go through this file.

Each canonical field has a list of accepted headers. map_columns() folds
those names (any case / spacing / punctuation) onto the engine schema
before any required-field check.

  orders        order_id, order_date, payment_mode, gateway_ref_id,
                bank_utr, order_amount          (+ customer_name optional)
  settlements   settlement_id, settled_on, gateway_ref_id, bank_utr,
                amount_received                 (+ source, narration optional)

bank_trans_id is a settlement_id alias (bank export row id), not bank_utr.
"""
import re

# ---------------------------------------------------------------------------
# Canonical field → accepted headers (canonical name is always first).
# ---------------------------------------------------------------------------

ORDER_REQUIRED = {
    "order_id": [
        "order_id", "orderid", "order_no", "order_number", "order_num",
        "ord_id", "oid", "invoice_id", "invoice_no", "invoice_number",
    ],
    "order_date": [
        "order_date", "orderdate", "date", "order_dt", "placed_on",
        "created_on", "created_at", "invoice_date", "order_datetime",
    ],
    "payment_mode": [
        "payment_mode", "paymentmode", "payment_method", "payment_type",
        "pay_mode", "pay_type", "mode", "method", "channel", "instrument",
    ],
    "gateway_ref_id": [
        "gateway_ref_id", "gateway_ref", "gateway_id", "payment_id",
        "pay_id", "pg_ref", "pg_ref_id", "razorpay_payment_id",
        "razorpay_id", "reference", "ref_id", "txn_ref",
    ],
    "bank_utr": [
        "bank_utr", "utr", "utr_no", "utr_number", "utr_id",
        "bank_txn_id", "bank_transaction_id", "bank_ref", "bank_reference",
    ],
    "order_amount": [
        "order_amount", "expected_amount", "amount", "order_value",
        "invoice_amount", "gross_amount", "amount_expected", "expected",
        "order_amt",
    ],
}

ORDER_OPTIONAL = {
    "customer_name": [
        "customer_name", "customer", "name", "buyer", "buyer_name",
        "client", "client_name",
    ],
    # Evidence fields for Tier 3 AI review (orphan-settlement/ambiguous-match
    # correlation, courier escalation addressing) -- NOT used by reconcile()'s
    # matching logic, which still runs on gateway_ref_id/bank_utr/amount only.
    "customer_phone": [
        "customer_phone", "phone", "mobile", "mobile_no", "mob_no",
        "contact_number", "phone_number", "customer_mobile",
    ],
    "customer_email": [
        "customer_email", "email", "email_address", "buyer_email",
    ],
    "courier": [
        "courier", "carrier", "delivery_partner", "shipping_partner",
        "logistics_partner", "tracking_company",
    ],
}

SETTLEMENT_REQUIRED = {
    "settlement_id": [
        "settlement_id", "settlementid", "stl_id", "stl_no",
        "payout_id", "credit_id", "settlement_no", "settlement_number",
        "bank_trans_id", "txn_id", "transaction_id", "trans_id",
        "settlement_ref", "settlement_ref_id",
    ],
    "settled_on": [
        "settled_on", "settlement_date", "settled_date", "date",
        "payout_date", "credit_date", "settlement_dt", "value_date",
        "posting_date", "txn_date", "transaction_date",
    ],
    "gateway_ref_id": [
        "gateway_ref_id", "gateway_ref", "gateway_id", "payment_id",
        "pay_id", "pg_ref", "pg_ref_id", "razorpay_payment_id",
        "razorpay_id", "reference", "ref_id", "txn_ref",
    ],
    "bank_utr": [
        "bank_utr", "utr", "utr_no", "utr_number", "utr_id",
        "bank_txn_id", "bank_transaction_id", "bank_ref", "bank_reference",
    ],
    "amount_received": [
        "amount_received", "received", "received_amount", "settlement_amount",
        "net_amount", "amount", "credit_amount", "settled_amount",
        "paid_amount", "amt_received", "net_settled",
    ],
}

SETTLEMENT_OPTIONAL = {
    "source": ["source", "src"],
    "narration": [
        "narration", "description", "remarks", "remark", "notes",
        "particulars", "particular",
    ],
}

NEED_ORDERS = list(ORDER_REQUIRED)
NEED_SETTLEMENTS = list(SETTLEMENT_REQUIRED)


def _key(name):
    """Fold a header to the lookup key used in the alias dictionaries."""
    s = str(name).replace("\ufeff", "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def _lookup(schema):
    """Invert canonical → [aliases] into alias-key → canonical."""
    table = {}
    for canon, names in schema.items():
        table[_key(canon)] = canon
        for n in names:
            table[_key(n)] = canon
    return table


ORDER_LOOKUP = _lookup({**ORDER_REQUIRED, **ORDER_OPTIONAL})
SETTLEMENT_LOOKUP = _lookup({**SETTLEMENT_REQUIRED, **SETTLEMENT_OPTIONAL})
ORDER_TARGETS = set(ORDER_REQUIRED) | set(ORDER_OPTIONAL)
SETTLEMENT_TARGETS = set(SETTLEMENT_REQUIRED) | set(SETTLEMENT_OPTIONAL)


def _rename(df, lookup, targets):
    """Rename one frame. Never overwrite a canonical column that is already there."""
    out = df.copy()
    out.columns = [str(c).replace("\ufeff", "").strip() for c in out.columns]
    rename = {}
    taken = set()
    # First pass: already-canonical headers (any case/spacing) claim their target.
    for col in out.columns:
        k = _key(col)
        if k in targets:
            if col != k:
                rename[col] = k
            taken.add(k)
    # Second pass: aliases whose target is still free.
    for col in out.columns:
        if col in rename:
            continue
        target = lookup.get(_key(col))
        if not target or _key(col) == target:
            continue
        if target in taken:
            continue
        rename[col] = target
        taken.add(target)
    if rename:
        out = out.rename(columns=rename)
    return out, rename


def map_columns(odf, sdf):
    """Rename uploaded order / settlement headers onto the engine schema."""
    o, _ = _rename(odf, ORDER_LOOKUP, ORDER_TARGETS)
    s, _ = _rename(sdf, SETTLEMENT_LOOKUP, SETTLEMENT_TARGETS)
    return o, s


def unused_columns(df, targets):
    """Headers that are not already a canonical field — the manual-pick list."""
    return [c for c in df.columns if c not in targets]


def missing_required(df, needed):
    return [c for c in needed if c not in df.columns]
