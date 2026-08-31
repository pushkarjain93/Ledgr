"""
ReconAI — shared configuration.

Money rule for the whole project: every amount is stored and compared as an
INTEGER NUMBER OF PAISE. Floats are never used for arithmetic on money.
CSVs carry human-readable rupee decimals; the loader converts on the way in.
This is also how Razorpay's own API represents amounts.
"""

# ---------------------------------------------------------------- money -----
def to_paise(rupees) -> int:
    """'1234.56' or 1234.56 -> 123456 paise. Half-up, never truncating."""
    from decimal import Decimal, ROUND_HALF_UP
    return int(Decimal(str(rupees)).quantize(Decimal("0.01"), ROUND_HALF_UP) * 100)


def to_rupees(paise: int) -> str:
    """123456 -> '1234.56' for CSV / display."""
    return f"{paise / 100:.2f}"


def fmt(paise: int) -> str:
    """123456 -> 'Rs 1,234.56' for the dashboard."""
    return f"Rs {paise / 100:,.2f}"


# ------------------------------------------------- tier 2 tolerance bands ---
# A shortfall is a "known deduction" (Tier 2) if it falls inside the band for
# that payment mode. Anything wider is a real variance and escalates to Tier 3.

# Online payments: gateway MDR + 18% GST on MDR, or a small flat fee.
FEE_TOLERANCE_PCT = 0.02          # 2% of order value
FEE_TOLERANCE_ABS = 300           # or Rs 3.00 flat, whichever is larger

# COD: courier collection fee is a flat-ish charge, so on small orders it is a
# much larger percentage. Needs its own band or every small COD order would
# false-positive into Tier 3.
COD_TOLERANCE_PCT = 0.025         # 2.5% of order value
COD_TOLERANCE_ABS = 5000          # or Rs 50.00 flat, whichever is larger


def fee_band(order_amount_paise: int, payment_mode: str) -> int:
    """Max shortfall (paise) still explainable as a known deduction."""
    if payment_mode == "COD":
        return max(COD_TOLERANCE_ABS, int(order_amount_paise * COD_TOLERANCE_PCT))
    return max(FEE_TOLERANCE_ABS, int(order_amount_paise * FEE_TOLERANCE_PCT))


# ------------------------------------------------------------------ misc ----
PAYMENT_MODES = ["UPI", "CARD", "NETBANKING", "WALLET", "COD", "BANK_TRANSFER"]

# The date the reconciliation run is executed "as of". All COD ageing is
# measured against this, so runs are reproducible instead of drifting with
# the wall clock.
from datetime import date
RUN_DATE = date(2026, 9, 1)

TIER_NAMES = {
    0: "COD timing pre-check",
    1: "Exact match",
    2: "Known deduction",
    3: "Variance - AI diagnostic",
    4: "UTR fallback match",
    5: "Unmatched - exception",
}

# ------------------------------------------- COD remittance ageing windows --
# Applies ONLY to payment_mode == COD. Runs before the waterfall: a COD order
# with no remittance yet is not a failure, it is a clock still running.
COD_FRESH_DAYS = 7        # 0-7   : normal, no flag
COD_WARN_DAYS = 14        # 8-14  : visible on dashboard, not an exception
#                           15+   : overdue, goes to the exception queue


def cod_age_bucket(days_since_order: int) -> str:
    if days_since_order <= COD_FRESH_DAYS:
        return "AWAITING_REMITTANCE"
    if days_since_order <= COD_WARN_DAYS:
        return "APPROACHING_THRESHOLD"
    return "EXCEPTION"


# --------------------------------------------------- exception reason codes -
# Every unresolved record carries one of these. The dashboard renders the
# legend so a reviewer can tell "still waiting" apart from "genuinely broken".
REASON_LEGEND = {
    "R1_AWAITING_REMITTANCE": (
        "Awaiting courier remittance",
        "COD order inside the normal 0-14 day collection window. No match yet, "
        "and nothing is wrong. Informational only."),
    "R2_REMITTANCE_OVERDUE": (
        "Remittance overdue",
        "COD order past 14 days with no remittance received. Needs follow-up "
        "with the courier partner."),
    "R3_UNMATCHED_AMBIGUOUS": (
        "Unmatched / ambiguous",
        "A genuine reconciliation failure: no identifier match, conflicting "
        "duplicate settlements, or a credit with no order behind it."),
    "R4_PARTIAL_PAYMENT": (
        "Partial payment",
        "Amount received is materially below the order value and cannot be "
        "explained by a standard gateway or COD collection fee."),
    "R5_AI_VARIANCE": (
        "Large variance flagged by AI",
        "Tier 3 case. The identifier matched but the amount did not; an AI "
        "diagnostic was generated and the record routed for review."),
}

# ------------------------------------------------ review priority banding ---
# Exceptions are worked highest-money-first. Tier 0 (a courier who is merely
# late) is capped at Medium even on a large order: same rupees, different
# urgency to money that may not exist at all.
PRIORITY_HIGH = 500000            # Rs 5,000 and above
PRIORITY_MEDIUM = 100000          # Rs 1,000 and above


def priority_of(amount_at_risk_paise: int, tier: int) -> str:
    if amount_at_risk_paise >= PRIORITY_HIGH:
        p = "High"
    elif amount_at_risk_paise >= PRIORITY_MEDIUM:
        p = "Medium"
    else:
        p = "Low"
    if tier == 0 and p == "High":
        p = "Medium"
    return p


# What a settled record's deduction gets tagged as, by payment mode.
FEE_TYPES = {
    "GATEWAY_FEE": "Gateway/bank charges (MDR + GST)",
    "COD_COLLECTION_FEE": "COD collection fee (courier)",
}

DATA_DIR = "data"



# ---------------------------------------------------------------------------
# Demo contact addresses (courier remittance desks / gateway support)
#
# THESE ARE PLACEHOLDERS ON A RESERVED EXAMPLE DOMAIN, NOT REAL INBOXES.
# RFC 2606 reserves example.com precisely so sample addresses can never
# collide with, or accidentally deliver to, a real mailbox. Using a plausible
# real address here (support@bluedart.com) would be worse than having none:
# a drafted chase could actually reach a stranger.
#
# They exist so the "draft a message" flow has a recipient to show end to end.
# Ledgr still NEVER sends -- a human copies the draft into their own client --
# so an unroutable address is exactly right for a demo.
#
# Replace with the merchant's genuine remittance/support contacts before any
# real use; `is_demo` on the API response is what tells the UI to say so.
# ---------------------------------------------------------------------------
DEMO_CONTACTS_ARE_PLACEHOLDERS = True

COURIER_CONTACTS = {
    "BLUEDART": "remittance@bluedart.example.com",
    "DELHIVERY": "remittance@delhivery.example.com",
    "XPRESSBEES": "remittance@xpressbees.example.com",
    "ECOM EXPRESS": "remittance@ecomexpress.example.com",
}

GATEWAY_CONTACT = "support@razorpay.example.com"


def courier_contact(courier: str) -> str:
    """Demo remittance-desk address for a courier, or "" if unknown."""
    return COURIER_CONTACTS.get((courier or "").strip().upper(), "")
