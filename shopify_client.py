"""
Mock Shopify client for Ledgr.

Shaped like a real Shopify Orders API client (fetch_orders(),
connection_status()) so that swapping in a live dev-store integration later
is a drop-in change to this file's internals only -- nothing downstream
(the dashboard, sync flow, engine.py) needs to change.

This is NOT a live integration. Orders come from data/orders.csv (produced
by gen_data.py), already in Ledgr's canonical schema -- schema_map.py's own
docstring says "Demo CSVs already use the engine names and must not go
through this file", so no column mapping happens here either.

Never claim a live check happened: connection_status() always reports
STATUS_MOCK, never something that reads as "Connected". The dashboard's
Orders card must stay honestly labeled ("Demo data", not "Connected"),
matching the same bar already held for the COD/bank source.

Why mocked, not real: a live Shopify integration for a dev store in your
own organization is actually achievable without OAuth (Shopify's client
credentials grant -- see CLAUDE.md's session notes). This was a deliberate
scoping choice given limited buildathon time, spent instead on the
Razorpay evidence pipeline and the AI Forensic Agent -- not a technical
wall. Orders live behind this same interface specifically so that decision
is reversible later without touching anything downstream.
"""
import os

import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
ORDERS_PATH = os.path.join(DATA_DIR, "orders.csv")

# connection_status() return values -- STATUS_MOCK is the expected, normal
# state (not an error and not "connected"); STATUS_ERROR only if the mock
# data file itself is missing.
STATUS_MOCK = "mock_data"
STATUS_ERROR = "error"


def fetch_orders():
    """
    Return orders as a list of dicts, already in Ledgr's canonical schema
    (order_id, order_date, customer_name, customer_phone, customer_email,
    courier, payment_mode, gateway_ref_id, bank_utr, order_amount).

    Raises FileNotFoundError if the mock data hasn't been generated yet
    (run gen_data.py first) -- never fabricates rows to fill the gap.
    """
    df = pd.read_csv(ORDERS_PATH, dtype=str).fillna("")
    return df.to_dict("records")


def connection_status():
    """
    Mirrors razorpay_client.connection_status()'s (status, rows, message)
    shape, so the dashboard can treat every source uniformly -- but this
    never reports a live status. Always STATUS_MOCK (or STATUS_ERROR if the
    mock file is missing), matching the honest "Demo data" dashboard label.

    Returns: (status: str, rows: list[dict], message: str)
    """
    try:
        rows = fetch_orders()
    except FileNotFoundError:
        return STATUS_ERROR, [], "Mock order data not found -- run gen_data.py first."

    return STATUS_MOCK, rows, f"Demo data -- {len(rows)} mock order(s) loaded."


if __name__ == "__main__":
    # Standalone self-test: python shopify_client.py
    status, rows, message = connection_status()
    print(f"[{status}] {message}")
    for row in rows[:5]:
        print(" ", row)
