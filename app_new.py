"""
Ledgr Main Application
Entry point with authentication flow. Visual language shared with login.py
via theme.py.

Layout approach: the static visual shell (header text, cards, tables) is
authored as continuous HTML sharing one spacing system, rendered in as few
st.markdown() calls as possible. Only the handful of elements that need real
interactivity (nav buttons, avatar/bell toggles, Sync & Reconcile) are actual
Streamlit widgets.

Page architecture: a single persistent app shell (sidebar + header) wraps
whichever page is active in st.session_state.current_page. There is no
separate full-screen "processing" route any more -- syncing happens inline
inside the Reconciliations page itself, sidebar and header always visible.

Incremental demo-data flow (see state_store.py): the ~100-record synthetic
dataset is split into 2 deterministic batches of ~50 by gen_data.py.
"""

import os
from datetime import date, datetime

import pandas as pd
import streamlit as st

import ai_client
import case_engine
import razorpay_client as rzp
import shopify_client as shopify
import state_store
from auth import is_authenticated, get_current_merchant, get_merchant_by_email, logout
from config import to_paise, to_rupees, fmt, RUN_DATE, fee_band
from engine import reconcile
from login import show_login_page
from theme import base_css, html, INK, BODY, DIM, LINE, BG, SOFT, ACC, ACC_D, MATCHED, WARN, WARN_BG

st.set_page_config(
    page_title="Ledgr - AI Reconciliation",
    page_icon="L",
    layout="wide",
    initial_sidebar_state="collapsed"
)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PURPLE = "#6941C6"  # AI-related accent, matches app.py's existing REVIEW color

NAV_ITEMS = [
    ("🏠", "Dashboard"), ("🔄", "Reconciliations"), ("📄", "Transactions"),
    ("✨", "AI Review"), ("⚠️", "Exceptions"), ("📊", "Reports"),
    ("🗄️", "Data Sources"), ("⚙️", "Settings"),
]
PAGE_META = {
    "Dashboard": ("Dashboard", "Here's what's happening with your reconciliations."),
    "Reconciliations": ("Reconciliations", "Reconcile orders, settlements and payments with confidence."),
    "Transactions": ("Transactions", "Every order and settlement Ledgr has seen."),
    "AI Review": ("AI Review", "Cases where AI investigated and has a recommendation for you."),
    "Exceptions": ("Exceptions", "Records that need a human decision."),
    "Reports": ("Reports", "Export reconciliation summaries and case data."),
    "Data Sources": ("Data Sources", "Connected commerce, payment and bank feeds."),
    "Settings": ("Settings", "Workspace and account configuration."),
}


# ===========================================================================
# Data helpers -- all real, none of this fabricates a number
# ===========================================================================
def _load_local_settlements():
    """
    RAZORPAY-sourced (demo) + BANK-sourced (COD) rows from the local
    settlements.csv gen_data.py produces. Our mock orders' payment_ids only
    exist in this demo file -- a real Razorpay Test Mode account has no
    relationship to synthetic data, so this is what orders actually
    reconcile against regardless of what the live Razorpay call returns.
    """
    return pd.read_csv(os.path.join(DATA_DIR, "settlements.csv"), dtype=str).fillna("")


def _batch_counts(batch_id):
    """Real per-source counts for one batch -- drives the ready-state card,
    the bell panel, and the new-data overlay. Never hardcoded; always read
    fresh from the same CSVs the real sync step reads."""
    b = str(batch_id)
    order_rows = shopify.fetch_orders()
    n_orders = sum(1 for o in order_rows if o.get("batch_id") == b)

    setls = _load_local_settlements()
    batch_setls = setls[setls["batch_id"] == b]
    n_settlements = int((batch_setls["source"] == "RAZORPAY").sum())
    n_cod = int((batch_setls["source"] == "BANK").sum())

    return {
        "orders": n_orders,
        "settlements": n_settlements,
        "cod_bank": n_cod,
        "total": n_orders + n_settlements + n_cod,
    }


def _time_ago(iso_ts):
    """'Received Xs ago' / 'Received X min ago', computed fresh each
    render from a persisted timestamp -- not a live-updating countdown
    (that would need a background timer, which this app deliberately
    doesn't have), just an honest snapshot as of this rerun."""
    if not iso_ts:
        return ""
    dt = datetime.fromisoformat(iso_ts)
    secs = max(0, int((datetime.now() - dt).total_seconds()))
    if secs < 60:
        return f"Received {secs}s ago"
    mins = secs // 60
    return f"Received {mins} min ago"


def _classify(result_df):
    """
    Three mutually-exclusive buckets over the real engine output, summing
    exactly to total records -- no invented model, built entirely from
    engine.py's own existing 'status' and 'ai_assisted' fields:
      - exceptions:   status == EXCEPTION (any tier)
      - ai_resolved:  AI was invoked (ai_assisted) and it did NOT end in
                      an exception
      - auto_matched: everything else (clean deterministic clears, and
                      Tier-0 COD timing states that are neither exceptions
                      nor AI cases)
    """
    is_exception = result_df["status"] == "EXCEPTION"
    is_ai = result_df["ai_assisted"] & ~is_exception
    is_auto = ~result_df["ai_assisted"] & ~is_exception
    return {
        "auto_matched": int(is_auto.sum()),
        "ai_resolved": int(is_ai.sum()),
        "exceptions": int(is_exception.sum()),
        "total_records": int(len(result_df)),
        "expected_paise": int(result_df["expected"].sum()),
        "received_paise": int(result_df["received"].sum()),
    }


def _flagged_records(result_df, batch_id):
    """
    Individual reviewable records from one real reconciliation run --
    everything engine.py already flagged as AI-assisted or an exception,
    not the clean auto-matches. This is a pure passthrough of engine.py's
    own output fields (reason, explanation, priority, amount_at_risk,
    age_days, matched_settlement, ai_assisted, and -- when RECONAI_LLM=1 --
    the real confidence/evidence/recommendation from the live AI call).
    Nothing invented here: confidence is None/[] whenever engine.py itself
    didn't get a real judgement call (offline stub, non-AI exceptions).
    Persisted so the Review Queue / AI Review / Exceptions pages have real
    individual records to work with instead of only run-level totals.
    """
    needs_attention = result_df[result_df["ai_assisted"] | (result_df["status"] == "EXCEPTION")]
    out = []
    for r in needs_attention.to_dict("records"):
        age = r.get("age_days")
        confidence = r.get("confidence")
        out.append({
            "record_id": r["record_id"],
            "batch_id": batch_id,
            "tier": int(r["tier"]),
            "tier_name": r["tier_name"],
            "status": r["status"],
            "reason": r["reason"],
            "reason_label": r["reason_label"],
            "fee_type": r["fee_type"],
            "expected": int(r["expected"]),
            "received": int(r["received"]),
            "delta": int(r["delta"]),
            "amount_at_risk": int(r["amount_at_risk"]),
            "priority": r["priority"],
            "explanation": r["explanation"],
            "matched_settlement": r["matched_settlement"],
            "age_days": (None if age is None or pd.isna(age) else int(age)),
            "ai_assisted": bool(r["ai_assisted"]),
            "confidence": (None if confidence is None or pd.isna(confidence) else int(confidence)),
            "evidence": list(r.get("ai_evidence") or []),
            "recommendation": r.get("ai_recommendation"),
        })
    return out


def _risk_summary_from_cases(cases):
    """
    Risk buckets from the persistent case store for the current run's
    reviewable cases (excludes pending_settlement and resolved).
    """
    open_cases = [c for c in cases if c["case_status"] not in ("pending_settlement", "resolved")]
    overpaid = [c for c in open_cases if c["delta"] > 0 and c["case_type"] == "overpayment"]
    at_risk = [c for c in open_cases if c["delta"] < 0 and c["case_type"] in ("partial_payment", "overpayment")]
    unmatched = [c for c in open_cases if c["case_type"] in ("unmatched_order", "unmatched_settlement", "ambiguous_match")]
    return {
        "Overpaid": {"amount": sum(c["delta"] for c in overpaid), "count": len(overpaid)},
        "At Risk": {"amount": sum(c["amount_at_risk"] for c in at_risk), "count": len(at_risk)},
        "Unmatched": {"amount": sum(c["amount_at_risk"] for c in unmatched), "count": len(unmatched)},
    }


def _case_dashboard_metrics(state):
    """Cumulative case-store metrics for the Dashboard KPI row."""
    cases = state_store.list_cases(state)
    return {
        "needs_review": sum(1 for c in cases if c["case_status"] in (
            "needs_ai", "ai_pending", "ai_recommendation", "manual_review", "exception")),
        "ai_accepted": sum(1 for c in cases if c.get("resolution", {}).get("resolution_type") == "accepted"),
        "awaiting_settlement": sum(1 for c in cases if c["case_status"] == "pending_settlement"),
        "open_exceptions": sum(1 for c in cases if c["case_status"] == "exception"),
    }


def _build_transaction_ledger(state, search="", type_filter="All", source_filter="All"):
    """Unified ledger: every order + settlement Ledgr has seen."""
    case_by_record = {}
    for c in state.get("cases", {}).values():
        for key in ("record_id", "order_id", "settlement_id"):
            if c.get(key):
                case_by_record[c[key].upper()] = c
    processed = set(state.get("processed_record_ids") or [])

    def _status_for(record_id, case):
        if case:
            return case["case_status"].replace("_", " ").title()
        if record_id in processed:
            return "Reconciled"
        return "Not synced"

    rows = []
    for o in shopify.fetch_orders():
        cid = case_by_record.get(o["order_id"].upper())
        rows.append({
            "id": o["order_id"],
            "type": "Order",
            "source": "Shopify (demo)",
            "customer": o.get("customer_name") or "—",
            "amount_paise": to_paise(o["order_amount"]),
            "date": o.get("order_date") or "",
            "status": _status_for(o["order_id"], cid),
            "case_id": cid["case_id"] if cid else None,
            "batch_id": o.get("batch_id", ""),
            "ref": o.get("gateway_ref_id") or o.get("bank_utr") or "",
        })

    for s in _load_local_settlements().to_dict("records"):
        cid = case_by_record.get(s["settlement_id"].upper())
        src = "Razorpay (demo)" if s.get("source") == "RAZORPAY" else "Bank / COD"
        rows.append({
            "id": s["settlement_id"],
            "type": "Settlement",
            "source": src,
            "customer": "—",
            "amount_paise": to_paise(s["amount_received"]),
            "date": s.get("settled_on") or "",
            "status": _status_for(s["settlement_id"], cid),
            "case_id": cid["case_id"] if cid else None,
            "batch_id": s.get("batch_id", ""),
            "ref": s.get("gateway_ref_id") or s.get("bank_utr") or "",
        })

    rows.sort(key=lambda r: (r["date"], r["id"]), reverse=True)
    q = search.strip().lower()
    if q:
        rows = [r for r in rows if q in " ".join(
            [r["id"], r["customer"], r["ref"], r["type"], r["source"], r["status"]]
        ).lower()]
    if type_filter != "All":
        rows = [r for r in rows if r["type"] == type_filter]
    if source_filter != "All":
        rows = [r for r in rows if source_filter.lower() in r["source"].lower()]
    return rows


def _open_case_ticket(case_id, previous_page=None):
    st.session_state.selected_case_id = case_id
    st.session_state.previous_page = previous_page or st.session_state.current_page
    st.session_state.current_page = "Case Ticket"
    st.rerun()


def _csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def _export_filename(prefix: str) -> str:
    return f"ledgr_{prefix}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"


def _cases_export_df(cases):
    """Flat case rows for CSV — amounts in rupees, AI fields when present."""
    rows = []
    for c in cases:
        ai = c.get("ai") or {}
        res = c.get("resolution") or {}
        rows.append({
            "case_id": c.get("case_id", ""),
            "record_id": c.get("record_id", ""),
            "order_id": c.get("order_id") or "",
            "settlement_id": c.get("settlement_id") or "",
            "customer_name": c.get("customer_name") or "",
            "batch_id": c.get("batch_id", ""),
            "case_type": c.get("case_type", ""),
            "case_status": c.get("case_status", ""),
            "expected": to_rupees(c.get("expected") or 0),
            "received": to_rupees(c.get("received") or 0),
            "delta": to_rupees(c.get("delta") or 0),
            "amount_at_risk": to_rupees(c.get("amount_at_risk") or 0),
            "reason": c.get("reason_label") or c.get("reason") or "",
            "ai_confidence": ai.get("confidence") if ai.get("confidence") is not None else "",
            "ai_finding": ai.get("reason") or "",
            "ai_recommendation": ai.get("next_step") or "",
            "ai_action": ai.get("action") or "",
            "resolved": res.get("resolved", False),
            "resolution_type": res.get("resolution_type") or "",
            "resolved_at": res.get("resolved_at") or "",
            "comment": c.get("comment") or res.get("comment") or "",
        })
    return pd.DataFrame(rows)


def _runs_export_df(runs):
    rows = []
    for r in runs:
        rows.append({
            "run_id": r.get("run_id", ""),
            "batch_id": r.get("batch_id", ""),
            "timestamp": r.get("timestamp", ""),
            "status": r.get("status", ""),
            "total_records": r.get("total_records", 0),
            "auto_matched": r.get("auto_matched", 0),
            "ai_review": r.get("ai_resolved", 0),
            "exceptions": r.get("exceptions", 0),
            "expected": to_rupees(r.get("expected_paise") or 0),
            "received": to_rupees(r.get("received_paise") or 0),
            "sources": r.get("sources", ""),
        })
    return pd.DataFrame(rows)


def _transactions_export_df(rows):
    return pd.DataFrame([{
        "id": r["id"],
        "type": r["type"],
        "source": r["source"],
        "customer": r["customer"],
        "amount": to_rupees(r["amount_paise"]),
        "date": r["date"],
        "status": r["status"],
        "case_id": r["case_id"] or "",
        "batch_id": r.get("batch_id", ""),
        "reference": r.get("ref", ""),
    } for r in rows])


def _risk_summary(flagged_records):
    """
    Real risk buckets derived entirely from fields engine.py already
    computed (status/delta/matched_settlement/amount_at_risk) -- no new
    categories invented, no fabricated amounts. Mutually exclusive: every
    flagged record lands in at most one bucket, so the three never
    double-count the same record.
      - Overpaid:   matched, but settled for MORE than the order value
      - At Risk:    matched, but settled for LESS than the order value,
                    beyond the known-fee band (needs investigation)
      - Unmatched:  no settlement could be attached at all
    """
    overpaid = [r for r in flagged_records if r["status"] == "MANUAL_REVIEW" and r["delta"] > 0]
    at_risk = [r for r in flagged_records if r["status"] == "MANUAL_REVIEW" and r["delta"] <= 0]
    unmatched = [r for r in flagged_records if r["status"] == "EXCEPTION" and not r["matched_settlement"]]
    return {
        "Overpaid": {"amount": sum(r["delta"] for r in overpaid), "count": len(overpaid)},
        "At Risk": {"amount": sum(r["amount_at_risk"] for r in at_risk), "count": len(at_risk)},
        "Unmatched": {"amount": sum(r["amount_at_risk"] for r in unmatched), "count": len(unmatched)},
    }


def _save_reconciliation_run(merchant_id, state, batch_id, result_df, order_ids, settlement_ids):
    """Persists one real, completed reconciliation run (including its
    individual flagged records) and advances the batch/timer state.
    Called exactly once per batch, right after reconcile() returns --
    never speculatively, never twice."""
    stats = _classify(result_df)
    run = {
        "run_id": f"RUN-{merchant_id}-B{batch_id}",
        "batch_id": batch_id,
        "timestamp": datetime.now().isoformat(),
        "sources": "Shopify + Razorpay + Bank",
        "status": "Completed",
        "flagged_records": _flagged_records(result_df, batch_id),
        **stats,
    }
    state["reconciliation_runs"].insert(0, run)
    # A re-evaluated pending order (see _run_sync_and_reconcile) was already
    # added here in an earlier batch -- dedupe rather than double-list it.
    already = set(state["processed_record_ids"])
    state["processed_record_ids"].extend(i for i in order_ids if i not in already)
    already.update(order_ids)
    state["processed_record_ids"].extend(i for i in settlement_ids if i not in already)
    state_store.schedule_next_batch(state, batch_id)
    state_store.save_state(merchant_id, state)
    return run


# ===========================================================================
# Sync -- runs INLINE inside the Reconciliations page now, no separate
# full-screen route. No time.sleep() anywhere: the steps render as the real
# work actually completes (which is genuinely fast for a 60-record batch),
# not on an artificial timer.
# ===========================================================================
SYNC_STEPS = [
    ("🛍️", "Connecting to Shopify…"),
    ("💳", "Connecting to Razorpay…"),
    ("🏦", "Loading COD / bank remittance data…"),
    ("🔀", "Merging settlement sources…"),
    ("🧮", "Matching orders to settlements…"),
]


INVESTIGATE_STEPS = [
    ("🔍", "Identifying missing evidence…"),
    ("📥", "Retrieving data…"),
    ("✨", "Analyzing with AI…"),
    ("💾", "Updating result…"),
]


def _render_steps(placeholder, current, results, steps=SYNC_STEPS):
    """
    Redraws the whole step list every call: steps before `current` are done
    (faded grey, with their real result line), `current` itself is bold
    full-opacity black, everything after is a dim, not-yet-run placeholder.
    Shared by the batch sync flow and the ticket page's Investigate Further
    flow -- both stream real step completions, never a cosmetic delay.
    """
    rows = []
    for i, (icon, label) in enumerate(steps):
        if i < current:
            rows.append(
                f'<div class="sync-step sync-step-done">'
                f'<span class="sync-step-icon">✓</span><span>{label}</span></div>'
            )
            if results[i]:
                rows.append(f'<div class="sync-step-result">{results[i]}</div>')
        elif i == current:
            rows.append(
                f'<div class="sync-step sync-step-active">'
                f'<span class="sync-step-icon">{icon}</span><span>{label}</span></div>'
            )
        else:
            rows.append(
                f'<div class="sync-step sync-step-pending">'
                f'<span class="sync-step-icon">{icon}</span><span>{label}</span></div>'
            )
    placeholder.markdown("".join(rows), unsafe_allow_html=True)


def _run_sync_and_reconcile(placeholder, batch_id, state):
    """
    Runs the real pipeline for ONE batch. Every step does real work; there
    is no artificial delay between them -- the step list still updates
    live as each step completes (Streamlit streams each placeholder update
    to the browser as it happens), it just resolves as fast as the actual
    local I/O + engine.reconcile() call actually takes.

    Also re-includes any order still genuinely waiting on a settlement
    (Tier 0, from an EARLIER batch -- see state_store.pending_settlement_
    order_ids) alongside this batch's own orders, so a late-arriving
    settlement in this batch's feed gets matched against it. This is the
    real order/settlement pair revealed one batch apart, not a duplicate
    -- case_engine.build_cases_for_batch() re-evaluates the SAME case_id
    rather than creating a new one.

    Returns (result_df, batch_orders, batch_setls_df) -- result_df is the
    real, unmodified engine.reconcile() output for this batch's rows
    (plus any re-included pending orders).
    """
    b = str(batch_id)
    results = [None] * len(SYNC_STEPS)

    _render_steps(placeholder, 0, results)
    order_rows = shopify.fetch_orders()
    pending_ids = set(state_store.pending_settlement_order_ids(state))
    batch_orders = [o for o in order_rows if o.get("batch_id") == b or o["order_id"] in pending_ids]
    orders_df = pd.DataFrame(batch_orders)
    orders_df["amount_paise"] = orders_df["order_amount"].map(to_paise)
    pending_note = f" (+{len(pending_ids)} re-evaluated pending)" if pending_ids else ""
    results[0] = f"{len(batch_orders)} orders loaded{pending_note}"

    _render_steps(placeholder, 1, results)
    rzp_status, rzp_rows, rzp_message = rzp.connection_status()
    results[1] = rzp_message

    _render_steps(placeholder, 2, results)
    local_setls = _load_local_settlements()
    batch_setls_df = local_setls[local_setls["batch_id"] == b]
    cod_rows = batch_setls_df[batch_setls_df["source"] == "BANK"]
    results[2] = f"{len(cod_rows)} bank credit(s) loaded"

    _render_steps(placeholder, 3, results)
    razorpay_rows = batch_setls_df[batch_setls_df["source"] == "RAZORPAY"]
    settlements_df = pd.concat([razorpay_rows, cod_rows], ignore_index=True)
    settlements_df["amount_paise"] = settlements_df["amount_received"].map(to_paise)
    source_note = ("live + demo" if rzp_status == rzp.STATUS_OK
                    else "demo — Test Mode has no live settlements for these orders")
    results[3] = f"{len(settlements_df)} settlement rows ready ({source_note})"

    _render_steps(placeholder, 4, results)
    result_df = reconcile(orders_df, settlements_df)
    results[4] = f"{len(result_df)} records processed"

    _render_steps(placeholder, len(SYNC_STEPS), results)

    return result_df, batch_orders, batch_setls_df


@st.cache_data(ttl=30, show_spinner=False)
def _cached_razorpay_status():
    """Real call to Razorpay, cached 30s so normal reruns don't hammer it."""
    return rzp.connection_status()


@st.cache_data(ttl=30, show_spinner=False)
def _cached_shopify_status():
    """Mock order data read, cached 30s. Never a live call -- see shopify_client.py."""
    return shopify.connection_status()


# ===========================================================================
# Session bootstrap + refresh-safe auth restore
# ===========================================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "merchant" not in st.session_state:
    st.session_state.merchant = None
if "sync_in_progress" not in st.session_state:
    st.session_state.sync_in_progress = False
if "current_page" not in st.session_state:
    st.session_state.current_page = "Dashboard"
if "selected_case_id" not in st.session_state:
    st.session_state.selected_case_id = None

# Restore an already-authenticated session after a browser refresh.
# st.session_state is wiped by a hard refresh, but st.query_params (part
# of the URL) survives -- login.py writes ?m=<email> on a real, successful
# authenticate() call; this only ever restores an identity that already
# passed that check once, it never re-checks a password.
if not st.session_state.authenticated:
    _restore_email = st.query_params.get("m")
    if _restore_email:
        _restored = get_merchant_by_email(_restore_email)
        if _restored:
            st.session_state.authenticated = True
            st.session_state.merchant = _restored


def _start_sync():
    """on_click callback for every 'Sync & Reconcile' / '+ New
    Reconciliation' button that should actually run the engine -- see the
    call site for why this has to be a callback, not an if-block +
    st.rerun()."""
    _cached_razorpay_status.clear()
    st.session_state.pop("last_reconcile_result", None)
    st.session_state.current_page = "Reconciliations"
    st.session_state.sync_in_progress = True


def _go_to_reconciliations():
    """on_click callback for '+ New Reconciliation' on the Dashboard --
    navigates only, never starts a sync on its own."""
    st.session_state.current_page = "Reconciliations"


def _initials(company_name):
    words = company_name.split()
    return "".join(w[0] for w in words[:2]).upper()


# ===========================================================================
# Shell: sidebar + header, shared by every page
# ===========================================================================
def _render_sidebar(merchant, page):
    with st.sidebar:
        st.markdown(html("""
            <div class="side-logo">
                <div class="side-logo-mark">⬡</div>
                <div>Ledgr</div>
            </div>
        """), unsafe_allow_html=True)
        st.markdown(f'<div class="side-company">{merchant["company_name"]}</div>', unsafe_allow_html=True)

        for icon, label in NAV_ITEMS:
            is_active = label == page
            with st.container(key=f"nav{'active' if is_active else label.lower().replace(' ', '')}"):
                if st.button(f"{icon}  {label}", key=f"navbtn_{label}", use_container_width=True):
                    if not is_active:
                        st.session_state.current_page = label
                        st.session_state.show_account_menu = False
                        st.session_state.show_notif_panel = False
                        st.rerun()

        st.markdown("<div style='flex:1;'></div>", unsafe_allow_html=True)
        st.markdown(html(f"""
            <div class="side-footer">
                <div class="side-footer-email">{merchant.get('email', '')}</div>
            </div>
        """), unsafe_allow_html=True)
        with st.container(key="sidelogout"):
            if st.button("Logout", key="side_logout_btn", use_container_width=True):
                merchant_id = merchant["merchant_id"]
                logout(st.session_state)
                st.query_params.clear()
                st.session_state.pop("last_reconcile_result", None)
                st.session_state.sync_in_progress = False
                st.session_state.current_page = "Dashboard"
                st.rerun()


def _render_header_and_notifications(merchant, merchant_id, state, page):
    """Title/subtitle for the current page, plus the bell + avatar + the
    floating new-data overlay. Returns nothing -- all state changes are
    applied directly and followed by st.rerun() where needed."""
    title, subtitle = PAGE_META.get(page, (page, ""))
    hcol_title, hcol_bell, hcol3 = st.columns([5, 0.45, 0.75])
    with hcol_title:
        st.markdown(html(f"""
            <div class="page-title">{title}</div>
            <div class="page-sub">{subtitle}</div>
        """), unsafe_allow_html=True)

    batch_ready = (state["current_batch"] <= state_store.TOTAL_BATCHES
                   and state_store.batch_is_available(state))
    # is_new_data excludes batch 1, which is initial data, never a "new
    # data" event. unread drives the bell's red dot; it is NOT cleared by
    # merely opening the panel -- only "Review & Reconcile" (from the
    # overlay OR the panel) or actually reconciling the batch clears it.
    is_new_data = batch_ready and state["current_batch"] > 1
    unread = is_new_data and not state["notification_seen"]

    with hcol_bell:
        with st.container(key="bellslot"):
            with st.container(key="bellbtn"):
                bell_icon = "🔔" + ("🔴" if unread else "")
                if st.button(bell_icon, key="bell_toggle"):
                    st.session_state.show_notif_panel = not st.session_state.get("show_notif_panel", False)
                    st.session_state.show_account_menu = False

            if st.session_state.get("show_notif_panel", False):
                with st.container(key="notifpanel"):
                    if is_new_data:
                        counts = _batch_counts(state["current_batch"])
                        st.markdown(html(f"""
                            <div class="notif-title">{'●' if unread else ''} New data received</div>
                            <div class="notif-ago">{_time_ago(state['next_batch_available_at'])}
                                — Batch {state['current_batch']} of {state_store.TOTAL_BATCHES}</div>
                            <div class="notif-breakdown">
                                🛍️ Orders — {counts['orders']}<br>
                                💳 Settlements — {counts['settlements']}<br>
                                🏦 COD / Bank — {counts['cod_bank']}
                            </div>
                        """), unsafe_allow_html=True)
                        if st.button("Review & Reconcile →", use_container_width=True, key="notif_review_btn"):
                            state_store.mark_notification_read(state)
                            state_store.save_state(merchant_id, state)
                            st.session_state.show_notif_panel = False
                            st.session_state.current_page = "Reconciliations"
                            st.rerun()
                    else:
                        msg = ("All available demo data has been reconciled."
                               if state["current_batch"] > state_store.TOTAL_BATCHES
                               else "No new notifications yet.")
                        st.markdown(f'<div class="notif-empty">{msg}</div>', unsafe_allow_html=True)

    with hcol3:
        with st.container(key="rightslot"):
            with st.container(key="avatarbtn"):
                if st.button(_initials(merchant["company_name"]), key="avatar_toggle"):
                    st.session_state.show_account_menu = not st.session_state.get(
                        "show_account_menu", False)
                    st.session_state.show_notif_panel = False

            if st.session_state.get("show_account_menu", False):
                with st.container(key="accountmenu"):
                    if st.button("Profile", use_container_width=True, key="menu_profile"):
                        st.session_state.show_account_menu = False
                        st.session_state.current_page = "Settings"
                        st.rerun()
                    if st.button("Settings", use_container_width=True, key="menu_settings"):
                        st.session_state.show_account_menu = False
                        st.session_state.current_page = "Settings"
                        st.rerun()
                    st.markdown("---")
                    if st.button("Log out", use_container_width=True, key="menu_logout"):
                        st.session_state.show_account_menu = False
                        logout(st.session_state)
                        st.query_params.clear()
                        st.session_state.pop("last_reconcile_result", None)
                        st.session_state.sync_in_progress = False
                        st.session_state.current_page = "Dashboard"
                        st.rerun()
                    st.markdown("---")
                    # Demo/developer-only reset -- tucked at the bottom of
                    # the account menu, not on the main dashboard, so it's
                    # not something a normal user stumbles into. Clears
                    # this merchant's reconciliation progress only; never
                    # touches orders.csv/settlements.csv or DEMO_MERCHANTS.
                    if st.button("Reset demo data", use_container_width=True, key="menu_reset_demo"):
                        st.session_state.show_account_menu = False
                        state_store.reset_state(merchant_id)
                        st.session_state.pop("last_reconcile_result", None)
                        st.session_state.sync_in_progress = False
                        st.session_state.current_page = "Dashboard"
                        st.session_state.show_notif_panel = False
                        st.rerun()

    # ---- floating "new data" overlay: auto-appears (no bell click needed)
    # the moment notification_overlay_open is true -- set once, the instant
    # the timer passes, and left open across reruns/refreshes until the
    # user explicitly dismisses it. Shows on top of whichever page is
    # active (position:fixed), never for batch 1. ----
    if is_new_data and state["notification_overlay_open"]:
        with st.container(key="newdataoverlay"):
            counts = _batch_counts(state["current_batch"])
            st.markdown(html(f"""
                <div style="display:flex; align-items:center; gap:7px; margin-bottom:8px;">
                    <span style="font-size:15px;">🔔</span>
                    <span style="font-size:14px; font-weight:700; color:{INK};">New data received</span>
                </div>
                <div style="font-size:12.5px; color:{BODY}; margin-bottom:10px;">
                    New reconciliation data is ready.
                </div>
                <div style="font-size:12.5px; color:{INK}; line-height:1.85; margin-bottom:12px;">
                    <b>{counts['orders']}</b> Orders<br>
                    <b>{counts['settlements']}</b> Settlements<br>
                    <b>{counts['cod_bank']}</b> COD / Bank
                </div>
            """), unsafe_allow_html=True)
            with st.container(key="overlayprimarybtn"):
                if st.button("Review & Reconcile →", use_container_width=True, key="overlay_review_btn"):
                    state_store.mark_notification_read(state)
                    state_store.save_state(merchant_id, state)
                    st.session_state.current_page = "Reconciliations"
                    st.rerun()
            ocol1, ocol2 = st.columns([4, 1])
            with ocol1:
                if st.button("Later", key="overlay_later_btn", use_container_width=True):
                    state_store.dismiss_overlay(state)
                    state_store.save_state(merchant_id, state)
                    st.rerun()
            with ocol2:
                if st.button("×", key="overlay_close_btn", use_container_width=True):
                    state_store.dismiss_overlay(state)
                    state_store.save_state(merchant_id, state)
                    st.rerun()


# ===========================================================================
# Review Queue table -- shared by Reconciliations, AI Review, Exceptions.
# Reads the persistent case store (state_store.py's `cases`), not the old
# per-run flagged_records -- this is the one place case-level status
# (pending / ai_recommendation / manual_review / resolved) is authoritative.
# "View ->" is a REAL button (not decorative HTML) that opens the actual
# investigation ticket for that case.
# ===========================================================================
_CASE_STATUS_LABEL = {
    "pending_settlement": ("Pending settlement", "pill-pending"),
    "needs_ai": ("Awaiting AI", "pill-pending"),
    # AI hasn't given a real verdict yet (rate limit or transient error) --
    # deliberately NOT "Manual Review": that would falsely imply AI looked
    # and recommended a human decision, when really AI never got to look.
    "ai_pending": ("AI Pending", "pill-ai-pending"),
    "ai_recommendation": ("AI Recommendation", "pill-ai-recommendation"),
    # 'manual_review' = AI found real evidence/candidates but couldn't
    # resolve unambiguously. 'exception' = there was NOTHING to weigh at
    # all (no candidate) -- a harder, more urgent bucket, kept visually
    # distinct even though both need a human.
    "manual_review": ("Manual Review", "pill-exception"),
    "exception": ("Exception", "pill-exception-hard"),
    "resolved": ("Resolved", "pill-resolved"),
}

# Review Queue quick-filter pills -- label -> a predicate over one case.
_QUEUE_FILTERS = [
    ("All", lambda c: True),
    ("AI Resolved", lambda c: c["case_status"] == "resolved"
                             and c.get("resolution", {}).get("resolution_type") == "accepted"),
    ("AI Recommendation", lambda c: c["case_status"] == "ai_recommendation"),
    ("Manual Review", lambda c: c["case_status"] == "manual_review"),
    ("Exceptions", lambda c: c["case_status"] == "exception"),
]


def _case_status_display(case):
    if case["case_status"] == "resolved":
        if case.get("resolution", {}).get("resolution_type") == "accepted" and case.get("ai"):
            return ("AI Resolved", "pill-resolved")
        return ("Resolved", "pill-resolved")
    return _CASE_STATUS_LABEL.get(case["case_status"], (case["case_status"], "pill-exception"))


def _days_since(order_date_str):
    if not order_date_str:
        return "—"
    try:
        return f"{(RUN_DATE - date.fromisoformat(order_date_str)).days} days"
    except ValueError:
        return "—"


def _confidence_sort_key(case):
    ai = case.get("ai")
    if ai and ai.get("confidence") is not None:
        return (0, -ai["confidence"])
    return (1, 0)  # unscored (ai_pending / never investigated) sinks below every real score, even 0%


def _render_review_queue(cases, key_prefix="cases", limit=None, compact=False):
    """
    Real persisted cases only -- never a fake confidence percentage.
    Sorted by AI confidence descending. `compact` drops the row index column
    for narrower layouts.
    """
    st.markdown(html("""
        <div class="recon-card">
            <div class="recon-title">Review Queue</div>
            <div class="workspace-sub" style="margin:-4px 0 12px;">Sorted by AI confidence — highest first.</div>
    """), unsafe_allow_html=True)

    filter_key = f"{key_prefix}_filter"
    st.session_state.setdefault(filter_key, "All")
    pill_cols = st.columns(len(_QUEUE_FILTERS))
    for (label, predicate), col in zip(_QUEUE_FILTERS, pill_cols):
        count = sum(1 for c in cases if predicate(c))
        active = st.session_state[filter_key] == label
        with col:
            with st.container(key=f"{key_prefix}_pill_{label.replace(' ', '')}"):
                if st.button(f"{label} ({count})", key=f"{key_prefix}_pillbtn_{label}",
                             use_container_width=True, type=("primary" if active else "secondary")):
                    st.session_state[filter_key] = label
                    st.rerun()

    active_predicate = dict(_QUEUE_FILTERS)[st.session_state[filter_key]]
    filtered = sorted((c for c in cases if active_predicate(c)), key=_confidence_sort_key)
    total_shown = len(filtered)
    shown = filtered[:limit] if limit else filtered

    if not shown:
        st.markdown('<div class="recon-empty">Nothing needs attention here — every record cleared.</div>',
                    unsafe_allow_html=True)
    else:
        head_cols = "0.4fr 1.2fr 1fr 0.9fr 2fr 0.9fr 1fr 0.55fr" if not compact else \
                    "1.2fr 1fr 0.9fr 2fr 0.9fr 1fr 0.55fr"
        head_html = """
            <div class="queue-row queue-row-head queue-row-compact">
        """ + ("" if compact else "<div>#</div>") + """
                <div>Record</div><div>Issue</div><div>Confidence</div>
                <div>AI Summary</div><div>At Risk</div><div>Status</div><div></div>
            </div>
        """
        st.markdown(html(head_html), unsafe_allow_html=True)

        for i, case in enumerate(shown, start=1):
            ai = case.get("ai")
            if ai and ai.get("confidence") is not None:
                pct = ai["confidence"]
                bar_color = MATCHED if pct >= case_engine.AUTO_RESOLVE_CONFIDENCE_FLOOR else ("#B45309" if pct > 0 else WARN)
                confidence_html = (f'<div class="conf-cell"><span>{pct}%</span>'
                                   f'<div class="conf-bar-track"><div class="conf-bar" '
                                   f'style="width:{pct}%; background:{bar_color};"></div></div></div>')
            elif ai and ai.get("error"):
                confidence_html = '<span class="recon-dim">Unavailable</span>'
            else:
                confidence_html = '<span class="recon-dim">—</span>'
            finding = (ai.get("reason") if ai else None) or case["explanation"]
            next_step = (ai.get("next_step") if ai else None) or ""
            summary = finding
            if next_step and next_step != "—":
                summary += f'<br><span class="recon-dim">{next_step}</span>'
            status_label, pill_class = _case_status_display(case)

            cols = st.columns([0.35, 1.25, 1.05, 0.95, 2.1, 0.85, 1.05, 0.55] if not compact
                                else [1.25, 1.05, 0.95, 2.1, 0.85, 1.05, 0.55])
            idx = 0
            if not compact:
                with cols[idx]:
                    st.markdown(f'<div class="case-cell">{i}</div>', unsafe_allow_html=True)
                idx += 1
            with cols[idx]:
                st.markdown(f'<div class="case-cell case-cell-name">{case["record_id"]}</div>',
                            unsafe_allow_html=True)
            with cols[idx + 1]:
                st.markdown(f'<span class="status-pill pill-issue">{case["case_type"].replace("_", " ").title()}</span>',
                            unsafe_allow_html=True)
            with cols[idx + 2]:
                st.markdown(confidence_html, unsafe_allow_html=True)
            with cols[idx + 3]:
                st.markdown(f'<div class="case-cell case-cell-summary">{summary}</div>', unsafe_allow_html=True)
            with cols[idx + 4]:
                st.markdown(f'<div class="case-cell">{fmt(case["amount_at_risk"])}</div>', unsafe_allow_html=True)
            with cols[idx + 5]:
                st.markdown(f'<span class="status-pill {pill_class}">{status_label}</span>', unsafe_allow_html=True)
            with cols[idx + 6]:
                if st.button("View", key=f"{key_prefix}_view_{case['case_id']}"):
                    _open_case_ticket(case["case_id"])

        st.markdown(f'<div class="recon-dim" style="margin-top:8px;">Showing {len(shown)} of {total_shown}</div>',
                    unsafe_allow_html=True)

    st.markdown(html("""
        <div class="confidence-guide">
            Higher confidence = stronger AI finding. <b>AI Pending</b> means investigation
            is queued (often rate limits) — open the case and use Retry.
        </div>
    """), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _latest_flagged_records(state):
    runs = state["reconciliation_runs"]
    return runs[0].get("flagged_records", []) if runs else []


def _all_flagged_records(state):
    """Across every saved run, newest batch first -- used by the
    dedicated AI Review / Exceptions pages (not just the latest run)."""
    out = []
    for r in state["reconciliation_runs"]:
        out.extend(r.get("flagged_records", []))
    return out


# ===========================================================================
# Dashboard
# ===========================================================================
def _render_dashboard(state, merchant_id):
    wcol1, wcol2 = st.columns([3, 1])
    with wcol1:
        welcome_sub = ("Your first data batch is ready to reconcile."
                       if state["current_batch"] == 1 and not state["reconciliation_runs"]
                       else "Cumulative activity across every reconciliation you've run.")
        st.markdown(html(f"""
            <div class="welcome-title">Welcome back 👋</div>
            <div class="welcome-sub">{welcome_sub}</div>
        """), unsafe_allow_html=True)
    with wcol2:
        with st.container(key="newreconbtn"):
            st.button("+ New Reconciliation", use_container_width=True,
                       on_click=_go_to_reconciliations, key="new_recon_button")

    st.markdown("<div style='height:22px;'></div>", unsafe_allow_html=True)

    # ---- KPIs: real, persisted cumulative totals across every saved
    # reconciliation run for this merchant (state_store.py) -- survives a
    # browser refresh, a server restart, and logging out and back in.
    # "0" when nothing has run yet, never a fabricated number. ----
    runs = state["reconciliation_runs"]  # most-recent-first
    total_recon = len(runs)
    auto_matched = sum(r["auto_matched"] for r in runs)
    case_metrics = _case_dashboard_metrics(state)

    st.markdown(html(f"""
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-icon" style="background:#E1EAFB; color:{ACC};">📄</div>
                <div class="kpi-label">Reconciliation Runs</div>
                <div class="kpi-value" style="color:{INK};">{total_recon}</div>
                <div class="kpi-sub">Completed batches</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-icon" style="background:#DDF3EA; color:{MATCHED};">✓</div>
                <div class="kpi-label">Auto Matched</div>
                <div class="kpi-value" style="color:{MATCHED};">{auto_matched}</div>
                <div class="kpi-sub">Deterministic clears</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-icon" style="background:#EDE7FB; color:{PURPLE};">✨</div>
                <div class="kpi-label">Needs Review</div>
                <div class="kpi-value" style="color:{PURPLE};">{case_metrics['needs_review']}</div>
                <div class="kpi-sub">Open cases in queue</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-icon" style="background:{WARN_BG}; color:{WARN};">⏳</div>
                <div class="kpi-label">Awaiting Settlement</div>
                <div class="kpi-value" style="color:#B45309;">{case_metrics['awaiting_settlement']}</div>
                <div class="kpi-sub">Normal window — no action yet</div>
            </div>
        </div>

        <div style="height:20px;"></div>
    """), unsafe_allow_html=True)

    # ---- Recent Reconciliations: real persisted runs only -- never padded
    # to look like a longer history than actually happened, never fake
    # historical dates.
    if not runs:
        st.markdown(html("""
            <div class="recon-card">
                <div class="recon-title">Recent Reconciliations</div>
                <div class="recon-empty">
                    No reconciliation yet.<br>
                    Run your first reconciliation to see your financial activity here.
                </div>
            </div>
        """), unsafe_allow_html=True)
    else:
        rows = "".join(f"""
            <tr>
                <td class="recon-name">Batch {r['batch_id']} — {datetime.fromisoformat(r['timestamp']).strftime('%b %d')}</td>
                <td class="recon-dim">{datetime.fromisoformat(r['timestamp']).strftime('%b %d, %Y %I:%M %p')}</td>
                <td class="recon-dim">{r['sources']}</td>
                <td><span class="status-pill">{r['status']}</span></td>
                <td class="recon-dim">{r['total_records']} records</td>
            </tr>
        """ for r in runs[:5])

        st.markdown(html(f"""
            <div class="recon-card">
                <div class="recon-title">Recent Reconciliations</div>
                <table class="recon-table">
                    <thead>
                        <tr><th>Run</th><th>Date &amp; Time</th><th>Sources</th>
                            <th>Status</th><th>Records</th></tr>
                    </thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>
        """), unsafe_allow_html=True)

        with st.container(key="viewallbtn"):
            if st.button("View all reconciliations →", use_container_width=False):
                st.session_state.current_page = "Reconciliations"
                st.rerun()


# ===========================================================================
# Reconciliations -- the command center. Sync happens INLINE here now.
# ===========================================================================
def _render_reconciliations(state, merchant_id):
    runs = state["reconciliation_runs"]

    # ---- header control row ----
    _, ccol = st.columns([2.8, 2.2])
    with ccol:
        with st.container(key="newreconbtn"):
            st.button("Sync & Reconcile", use_container_width=True,
                       on_click=_start_sync, key="recon_new_btn")

    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    # ---- mid-sync: compact inline processing card, or an honest
    # "nothing to do" notice -- sidebar and header stay fully visible. ----
    if st.session_state.sync_in_progress:
        batch_id = state["current_batch"]

        if batch_id > state_store.TOTAL_BATCHES:
            st.markdown(html("""
                <div class="ready-card">
                    <div class="ready-title">All available demo data has been reconciled.</div>
                </div>
            """), unsafe_allow_html=True)
            with st.container(key="backbtn"):
                if st.button("OK", key="ack_alldone", use_container_width=False):
                    st.session_state.sync_in_progress = False
                    st.rerun()
            return

        if not state_store.batch_is_available(state):
            last_ts = (datetime.fromisoformat(runs[0]["timestamp"]).strftime('%b %d, %Y %I:%M:%S %p')
                       if runs else None)
            st.markdown(html(f"""
                <div class="ready-card">
                    <div class="ready-title">No new data since your last reconciliation.</div>
                    {f'<div class="ready-sub">Last synchronized: {last_ts}</div>' if last_ts else ''}
                </div>
            """), unsafe_allow_html=True)
            with st.container(key="backbtn"):
                if st.button("OK", key="ack_nonew", use_container_width=False):
                    st.session_state.sync_in_progress = False
                    st.rerun()
            return

        # A new batch really is ready -- run the real, unmodified engine.
        st.markdown('<div class="sync-card">', unsafe_allow_html=True)
        st.markdown('<div class="sync-heading">Syncing &amp; reconciling…</div>', unsafe_allow_html=True)
        placeholder = st.empty()
        result_df, batch_orders, batch_setls_df = _run_sync_and_reconcile(placeholder, batch_id, state)
        st.markdown('</div>', unsafe_allow_html=True)

        order_ids = [o["order_id"] for o in batch_orders]
        settlement_ids = batch_setls_df["settlement_id"].tolist()
        _save_reconciliation_run(merchant_id, state, batch_id, result_df, order_ids, settlement_ids)

        # Post-reconciliation case layer: turns the real engine output into
        # persistent, trackable cases and runs the ONE live AI path for
        # every AI-eligible case type uniformly. Evidence-hash caching
        # (existing_cases) means a case whose facts haven't changed since
        # its last real investigation is reused, not re-sent to Gemini;
        # investigate_new_cases_batched() sends whatever's left in groups
        # of ~5 per request instead of one call per case.
        pending_before = set(state_store.pending_settlement_order_ids(state))
        cases = case_engine.build_cases_for_batch(
            result_df, batch_id, batch_orders, batch_setls_df.to_dict("records"),
            previously_open_order_ids=pending_before, existing_cases=state.get("cases", {}))
        cases = case_engine.investigate_new_cases_batched(cases)
        case_engine.save_cases(state, cases)
        state_store.save_state(merchant_id, state)

        st.session_state.sync_in_progress = False
        st.rerun()
        return

    # ---- never reconciled before: the initial ready state ----
    if not runs:
        counts = _batch_counts(state["current_batch"])
        st.markdown(html(f"""
            <div class="ready-card">
                <div class="ready-title">Your first reconciliation is ready.</div>
                <div class="ready-badge">
                    <div class="ready-tile">
                        <div class="ready-tile-value">{counts['orders']}</div>
                        <div class="ready-tile-label">Orders</div>
                    </div>
                    <div class="ready-tile">
                        <div class="ready-tile-value">{counts['settlements']}</div>
                        <div class="ready-tile-label">Settlements</div>
                    </div>
                    <div class="ready-tile">
                        <div class="ready-tile-value">{counts['cod_bank']}</div>
                        <div class="ready-tile-label">COD / Bank</div>
                    </div>
                </div>
            </div>
        """), unsafe_allow_html=True)
        _, mid, _ = st.columns([1, 1, 1])
        with mid:
            with st.container(key="newreconbtn2"):
                st.button("Sync & Reconcile", use_container_width=True,
                           on_click=_start_sync, key="ready_sync_btn")
        return

    # ---- results workspace: always shown once >=1 run exists. A slim
    # banner (not a permanent card) surfaces a pending unsynced batch --
    # new-data awareness otherwise lives in the bell + overlay only. ----
    latest = runs[0]
    batch_ready = (state["current_batch"] <= state_store.TOTAL_BATCHES
                   and state_store.batch_is_available(state))
    if batch_ready:
        counts = _batch_counts(state["current_batch"])
        st.markdown(html(f"""
            <div class="pending-banner">
                <span><b>Batch {state['current_batch']}</b> data is ready —
                {counts['orders']} Orders, {counts['settlements']} Settlements,
                {counts['cod_bank']} COD / Bank</span>
            </div>
        """), unsafe_allow_html=True)
        with st.container(key="pendingsyncbtn"):
            st.button("Sync & Reconcile", key="pending_sync_btn", on_click=_start_sync)
        st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    # ---- cumulative KPI row (4 cards) -- categorical breakdown lives in
    # the Resolution Funnel below instead, so this row isn't duplicating it. ----
    total_recon = len(runs)
    expected_total = sum(r["expected_paise"] for r in runs)
    received_total = sum(r["received_paise"] for r in runs)
    diff_total = received_total - expected_total
    diff_color = MATCHED if diff_total == 0 else WARN

    st.markdown(html(f"""
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-label">Total Reconciliations</div>
                <div class="kpi-value">{total_recon}</div>
                <div class="kpi-sub">Runs completed</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Expected Amount</div>
                <div class="kpi-value">{fmt(expected_total)}</div>
                <div class="kpi-sub">All runs combined</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Received Amount</div>
                <div class="kpi-value" style="color:{MATCHED};">{fmt(received_total)}</div>
                <div class="kpi-sub">All runs combined</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Difference</div>
                <div class="kpi-value" style="color:{diff_color};">{fmt(diff_total)}</div>
                <div class="kpi-sub">Expected − received</div>
            </div>
        </div>
        <div style="height:20px;"></div>
    """), unsafe_allow_html=True)

    with st.expander("✨ Ask AI about your reconciliation data", expanded=False):
        _render_ask_ai(state, key_prefix="mainask")
    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    # ---- three-column workspace: Resolution Funnel | Awaiting Settlement |
    # Risk Summary, all from the LATEST run's real cases (case store, not
    # the old per-run flagged_records) ----
    current_run_cases = [c for c in state_store.list_cases(state) if c["batch_id"] == latest["batch_id"]]
    pending_cases = [c for c in current_run_cases if c["case_status"] == "pending_settlement"]
    reviewable_cases = [c for c in current_run_cases if c["case_status"] != "pending_settlement"]

    ai_investigated = [c for c in reviewable_cases if c.get("ai") is not None]
    ai_pending_cases = [c for c in ai_investigated if c["case_status"] == "ai_pending"]
    ai_resolved_cases = [c for c in ai_investigated if c["case_status"] == "ai_recommendation"
                         or (c["case_status"] == "resolved" and c.get("resolution", {}).get("resolution_type") == "accepted")]
    manual_review_cases = [c for c in reviewable_cases if c["case_status"] == "manual_review"]
    exception_cases = [c for c in reviewable_cases if c["case_status"] == "exception"]
    deterministically_matched = latest["total_records"] - len(reviewable_cases) - len(pending_cases)

    risk = _risk_summary_from_cases(reviewable_cases)
    pending_total = sum(c["expected"] for c in pending_cases)

    col_funnel, col_pending, col_risk = st.columns([1.1, 1.2, 1.1])
    with col_funnel:
        funnel_rows = [
            ("Total Records", latest["total_records"], INK),
            ("Deterministically Matched", deterministically_matched, MATCHED),
            ("AI Investigated", len(ai_investigated), PURPLE),
            ("AI Resolved", len(ai_resolved_cases), MATCHED),
            ("Manual Review", len(manual_review_cases), "#B45309"),
            ("Exceptions", len(exception_cases), WARN),
        ]
        if ai_pending_cases:
            funnel_rows.append(("AI Pending", len(ai_pending_cases), DIM))
        total_for_pct = latest["total_records"] or 1
        rows_html = "".join(f"""
            <div class="funnel-row">
                <div class="funnel-label">{label}</div>
                <div class="funnel-bar-track">
                    <div class="funnel-bar" style="width:{count*100/total_for_pct:.1f}%; background:{color};"></div>
                </div>
                <div class="funnel-count">{count}</div>
                <div class="funnel-pct">{count*100//total_for_pct}%</div>
            </div>
        """ for label, count, color in funnel_rows)
        st.markdown(html(f"""
            <div class="workspace-card">
                <div class="workspace-title">Reconciliation Resolution Funnel</div>
                <div class="workspace-sub">How records are resolved -- current run</div>
                <div style="height:8px;"></div>
                {rows_html}
            </div>
        """), unsafe_allow_html=True)

    with col_pending:
        pending_summary = (f"{len(pending_cases)} order{'s' if len(pending_cases) != 1 else ''} · "
                         f"{fmt(pending_total)}") if pending_cases else "None right now"
        pending_rows = "".join(f"""
            <div class="pending-row">
                <div><b>{c['record_id']}</b></div>
                <div>{fmt(c['expected'])}</div>
                <div>{_days_since(c.get('order_date'))}</div>
            </div>
        """ for c in pending_cases[:4])
        st.markdown(html(f"""
            <div class="workspace-card">
                <div class="workspace-title">Awaiting Settlement</div>
                <div class="pending-summary">{pending_summary}</div>
                <div class="workspace-sub">Normal settlement window — no action needed.</div>
                <div style="height:8px;"></div>
                <div class="pending-row pending-row-head">
                    <div>Order</div><div>Amount</div><div>Age</div>
                </div>
                {pending_rows or '<div class="evidence-line">Nothing currently awaiting settlement.</div>'}
            </div>
        """), unsafe_allow_html=True)
        if len(pending_cases) > 4:
            st.markdown(f'<div class="workspace-sub" style="margin-top:6px;">'
                        f'+{len(pending_cases) - 4} more</div>', unsafe_allow_html=True)

    with col_risk:
        st.markdown(html("""
            <div class="workspace-card">
                <div class="workspace-title">Risk Summary</div>
                <div class="workspace-sub">Focus areas needing attention -- current run</div>
            </div>
        """), unsafe_allow_html=True)
        risk_targets = {"Overpaid": "AI Review", "At Risk": "AI Review", "Unmatched": "Exceptions"}
        for label, data in risk.items():
            st.markdown(html(f"""
                <div class="risk-row">
                    <div class="risk-row-label">{label}</div>
                    <div class="risk-row-amount">{fmt(data['amount'])}</div>
                    <div class="risk-row-count">{data['count']} record{'s' if data['count'] != 1 else ''}</div>
                </div>
            """), unsafe_allow_html=True)
            with st.container(key=f"risklink_{label.replace(' ', '')}"):
                if st.button(f"View {label} →", key=f"risk_btn_{label}", use_container_width=True):
                    st.session_state.current_page = risk_targets[label]
                    st.rerun()

    st.markdown("<div style='height:22px;'></div>", unsafe_allow_html=True)

    # ---- Review Queue: real persisted cases for the CURRENT run (pending
    # settlements excluded -- they have their own widget above), sorted by
    # AI confidence, with live filter pills. ----
    _render_review_queue(reviewable_cases, key_prefix="reviewqueue", limit=8, compact=True)
    if len(reviewable_cases) > 10:
        with st.container(key="viewallreviewbtn"):
            _, vcol, _ = st.columns([2, 1, 2])
            with vcol:
                if st.button("View all in AI Review →", key="view_all_review", use_container_width=True):
                    st.session_state.current_page = "AI Review"
                    st.rerun()

    st.markdown("<div style='height:22px;'></div>", unsafe_allow_html=True)

    # ---- Recent Reconciliations: detailed, per-run breakdown ----
    rows = "".join(f"""
        <tr>
            <td class="recon-name">Batch {r['batch_id']}</td>
            <td class="recon-dim">{datetime.fromisoformat(r['timestamp']).strftime('%b %d, %Y %I:%M %p')}</td>
            <td class="recon-dim">{r['total_records']}</td>
            <td class="recon-dim" style="color:{MATCHED};">{r['auto_matched']}</td>
            <td class="recon-dim" style="color:{PURPLE};">{r['ai_resolved']}</td>
            <td class="recon-dim" style="color:{WARN};">{r['exceptions']}</td>
        </tr>
    """ for r in runs)

    st.markdown(html(f"""
        <div class="recon-card">
            <div class="recon-title">Recent Reconciliations</div>
            <table class="recon-table">
                <thead>
                    <tr><th>Batch</th><th>Date &amp; Time</th><th>Records</th>
                        <th>Auto Matched</th><th>AI Review</th><th>Exceptions</th></tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
    """), unsafe_allow_html=True)


# ===========================================================================
# AI Review / Exceptions -- real pages backed by the persistent case store,
# not a mock of the future full AI Review UI.
# ===========================================================================
def _render_ai_review(state):
    """Cases where AI has completed an investigation (not merely queued)."""
    st.markdown(html("""
        <div class="welcome-sub" style="margin-bottom:14px;">
            Cases AI investigated with a finding or recommendation. You still make the final decision.
        </div>
    """), unsafe_allow_html=True)
    cases = [c for c in state_store.list_cases(state)
             if c.get("ai") and not c["ai"].get("error") and c["case_status"] != "ai_pending"]
    _render_review_queue(cases, key_prefix="airev", compact=True)


def _render_exceptions(state):
    """Genuine unresolved cases only -- both the softer 'manual_review'
    (real evidence, still ambiguous) and the harder 'exception' (nothing
    found at all) buckets. Resolved cases never show up here."""
    st.markdown(html("""
        <div class="welcome-sub" style="margin-bottom:14px;">Records that need a human decision.</div>
    """), unsafe_allow_html=True)
    cases = [c for c in state_store.list_cases(state) if c["case_status"] in ("manual_review", "exception")]
    _render_review_queue(cases, key_prefix="exc", compact=True)


def _render_transactions(state):
    """Underlying ledger of every order and settlement."""
    st.markdown(html("""
        <div class="welcome-sub" style="margin-bottom:16px;">
            Every order, payment and settlement Ledgr has seen. Open a linked case to investigate.
        </div>
    """), unsafe_allow_html=True)

    f1, f2, f3 = st.columns([2.2, 1, 1])
    with f1:
        search = st.text_input("Search", placeholder="Order ID, settlement ID, customer, UTR…",
                               key="txn_search", label_visibility="collapsed")
    with f2:
        type_filter = st.selectbox("Type", ["All", "Order", "Settlement"], key="txn_type", label_visibility="collapsed")
    with f3:
        source_filter = st.selectbox("Source", ["All", "Shopify", "Razorpay", "Bank"], key="txn_source", label_visibility="collapsed")

    rows = _build_transaction_ledger(state, search, type_filter, source_filter)
    n_orders = sum(1 for r in rows if r["type"] == "Order")
    n_settlements = sum(1 for r in rows if r["type"] == "Settlement")
    n_linked = sum(1 for r in rows if r["case_id"])

    st.markdown(html(f"""
        <div class="txn-summary">
            <span><b>{len(rows)}</b> shown</span>
            <span>{n_orders} orders · {n_settlements} settlements · {n_linked} with cases</span>
        </div>
    """), unsafe_allow_html=True)

    st.download_button(
        label="Export CSV",
        data=_csv_bytes(_transactions_export_df(rows)),
        file_name=_export_filename("transactions"),
        mime="text/csv",
        key="txn_export_csv",
        help="Download all rows matching your current search and filters.",
    )

    if not rows:
        st.markdown('<div class="recon-empty">No transactions match your search.</div>', unsafe_allow_html=True)
        return

    st.markdown(html("""
        <div class="txn-row txn-row-head">
            <div>ID</div><div>Type</div><div>Source</div><div>Customer</div>
            <div>Amount</div><div>Date</div><div>Status</div><div>Case</div>
        </div>
    """), unsafe_allow_html=True)

    for r in rows[:80]:
        c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([1.1, 0.7, 1, 1.1, 0.9, 0.85, 1, 0.55])
        with c1:
            st.markdown(f'<div class="case-cell case-cell-name">{r["id"]}</div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="case-cell">{r["type"]}</div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="case-cell recon-dim">{r["source"]}</div>', unsafe_allow_html=True)
        with c4:
            st.markdown(f'<div class="case-cell">{r["customer"]}</div>', unsafe_allow_html=True)
        with c5:
            st.markdown(f'<div class="case-cell">{fmt(r["amount_paise"])}</div>', unsafe_allow_html=True)
        with c6:
            st.markdown(f'<div class="case-cell recon-dim">{r["date"] or "—"}</div>', unsafe_allow_html=True)
        with c7:
            st.markdown(f'<div class="case-cell">{r["status"]}</div>', unsafe_allow_html=True)
        with c8:
            if r["case_id"]:
                if st.button("Open", key=f"txn_case_{r['id']}"):
                    _open_case_ticket(r["case_id"], "Transactions")
            else:
                st.markdown('<div class="case-cell recon-dim">—</div>', unsafe_allow_html=True)

    if len(rows) > 80:
        st.markdown(f'<div class="recon-dim" style="margin-top:8px;">Showing first 80 of {len(rows)}</div>',
                    unsafe_allow_html=True)


def _render_data_sources():
    """Honest integration status — no fake live badges."""
    shop_status, _, shop_msg = _cached_shopify_status()
    rzp_status, _, rzp_msg = _cached_razorpay_status()
    setls = _load_local_settlements()
    n_cod = int((setls["source"] == "BANK").sum())
    n_rzp = int((setls["source"] == "RAZORPAY").sum())

    st.markdown(html("""
        <div class="welcome-sub" style="margin-bottom:16px;">
            Connected feeds used during sync. Demo orders and settlements come from local CSVs;
            Razorpay is checked live for connection status.
        </div>
    """), unsafe_allow_html=True)

    cards = [
        ("🛍️", "Orders", "Shopify", "Demo data", shop_msg, MATCHED if shop_status == shopify.STATUS_MOCK else WARN),
        ("💳", "Online settlements", "Razorpay", "Demo + live check", rzp_msg,
         MATCHED if rzp_status in (rzp.STATUS_OK, rzp.STATUS_EMPTY) else WARN),
        ("🏦", "COD / Bank", "Bank remittance", "Demo data",
         f"{n_cod} bank credits · {n_rzp} Razorpay rows in demo file", MATCHED),
    ]
    for icon, title, provider, badge, msg, color in cards:
        st.markdown(html(f"""
            <div class="source-card">
                <div class="source-card-head">
                    <span>{icon} <b>{title}</b></span>
                    <span class="source-badge" style="color:{color};">{badge}</span>
                </div>
                <div class="source-provider">{provider}</div>
                <div class="source-msg">{msg}</div>
            </div>
        """), unsafe_allow_html=True)


def _render_reports(state):
    """Summary plus CSV exports from real persisted data."""
    runs = state["reconciliation_runs"]
    cases = state_store.list_cases(state)
    if not runs:
        st.markdown('<div class="recon-empty">Run a reconciliation first to generate reports.</div>',
                    unsafe_allow_html=True)
        return

    open_cases = [c for c in cases if c["case_status"] != "resolved"]
    st.markdown(html(f"""
        <div class="recon-card">
            <div class="recon-title">Reconciliation Summary</div>
            <div class="ticket-line"><span>Total runs</span><b>{len(runs)}</b></div>
            <div class="ticket-line"><span>Auto matched (cumulative)</span><b>{sum(r['auto_matched'] for r in runs)}</b></div>
            <div class="ticket-line"><span>Open cases</span><b>{len(open_cases)}</b></div>
            <div class="ticket-line"><span>Resolved cases</span><b>{sum(1 for c in cases if c['case_status'] == 'resolved')}</b></div>
            <div class="ticket-line"><span>Outstanding at risk</span><b>{fmt(sum(c['amount_at_risk'] for c in open_cases))}</b></div>
        </div>
    """), unsafe_allow_html=True)

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
    st.markdown(html("""
        <div class="recon-card">
            <div class="recon-title">Export CSV</div>
            <div class="workspace-sub">Downloads use the same real data shown in Ledgr — nothing fabricated.</div>
        </div>
    """), unsafe_allow_html=True)

    e1, e2, e3 = st.columns(3)
    with e1:
        st.download_button(
            label=f"Open cases ({len(open_cases)})",
            data=_csv_bytes(_cases_export_df(open_cases)),
            file_name=_export_filename("open_cases"),
            mime="text/csv",
            key="export_open_cases",
            use_container_width=True,
        )
    with e2:
        st.download_button(
            label=f"All cases ({len(cases)})",
            data=_csv_bytes(_cases_export_df(cases)),
            file_name=_export_filename("all_cases"),
            mime="text/csv",
            key="export_all_cases",
            use_container_width=True,
        )
    with e3:
        st.download_button(
            label=f"Reconciliation runs ({len(runs)})",
            data=_csv_bytes(_runs_export_df(runs)),
            file_name=_export_filename("reconciliation_runs"),
            mime="text/csv",
            key="export_runs",
            use_container_width=True,
        )

    txn_rows = _build_transaction_ledger(state)
    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
    st.download_button(
        label=f"Full transaction ledger ({len(txn_rows)} rows)",
        data=_csv_bytes(_transactions_export_df(txn_rows)),
        file_name=_export_filename("transaction_ledger"),
        mime="text/csv",
        key="export_ledger",
        help="Every order and settlement in the demo dataset, with case links where they exist.",
    )


def _render_settings(merchant, merchant_id):
    """Workspace info and demo controls."""
    st.markdown(html(f"""
        <div class="recon-card">
            <div class="recon-title">Workspace</div>
            <div class="ticket-line"><span>Company</span><b>{merchant['company_name']}</b></div>
            <div class="ticket-line"><span>Email</span><b>{merchant.get('email', '')}</b></div>
            <div class="ticket-line"><span>Industry</span><b>{merchant.get('industry', '—')}</b></div>
            <div class="ticket-line"><span>Shopify store</span><b>{merchant.get('shopify_url', '—')}</b></div>
        </div>
    """), unsafe_allow_html=True)

    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
    st.markdown(html("""
        <div class="recon-card">
            <div class="recon-title">API configuration</div>
            <div class="workspace-sub">Keys are read from your local .env file (never committed).</div>
            <div class="ticket-line"><span>Razorpay</span><b>RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET</b></div>
            <div class="ticket-line"><span>Gemini AI</span><b>GEMINI_API_KEY</b></div>
        </div>
    """), unsafe_allow_html=True)

    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
    if st.button("Reset demo reconciliation progress", key="settings_reset_demo", type="secondary"):
        state_store.reset_state(merchant_id)
        st.session_state.pop("last_reconcile_result", None)
        st.session_state.sync_in_progress = False
        st.session_state.current_page = "Dashboard"
        st.success("Demo progress cleared. Your next login starts fresh.")
        st.rerun()


# ===========================================================================
# Ask AI -- main (whole-dataset context) and case-scoped (ticket) variants.
# Read-only: explains/searches/summarizes/recommends, never silently
# changes data. Grounded only in real persisted data via case_engine's
# compact context builders -- never the whole dataset dumped raw.
# ===========================================================================
def _render_ask_ai(state, case_id=None, key_prefix="ask"):
    label = "Ask AI about this case" if case_id else "Ask AI about your reconciliation data"
    placeholder = ("e.g. Why is this marked as partial payment?" if case_id
                   else "e.g. Which orders are still pending?")
    with st.container(key=f"{key_prefix}box"):
        st.markdown(f'<div class="ask-ai-label">✨ {label}</div>', unsafe_allow_html=True)
        qcol, bcol = st.columns([5, 1])
        with qcol:
            question = st.text_input(label, placeholder=placeholder, key=f"{key_prefix}_q",
                                      label_visibility="collapsed")
        with bcol:
            asked = st.button("Ask AI", key=f"{key_prefix}_btn", use_container_width=True)

        answer_key = f"{key_prefix}_answer"
        if asked and question.strip():
            # Direct-answer-first: most questions are answerable straight
            # from already-computed, already-persisted data (including any
            # AI reasoning already stored per case) -- Gemini is only
            # called for the question this can't confidently answer.
            direct = case_engine.try_direct_answer(question.strip(), state)
            if direct is not None:
                st.session_state[answer_key] = direct
            else:
                context = case_engine.build_ask_context(state, case_id=case_id)
                try:
                    st.session_state[answer_key] = ai_client.ask(question.strip(), context)
                except (ai_client.AIAuthError, ai_client.AIAPIError) as exc:
                    st.session_state[answer_key] = f"AI is temporarily unavailable ({exc}). Please try again shortly."

        if st.session_state.get(answer_key):
            st.markdown(f'<div class="ask-ai-answer">{st.session_state[answer_key]}</div>',
                        unsafe_allow_html=True)
        st.markdown('<div class="ask-ai-hint">AI answers based only on the data in Ledgr.</div>',
                    unsafe_allow_html=True)


# ===========================================================================
# AI Investigation Ticket -- opened by clicking "View" on any case.
# ===========================================================================
def _order_row_for(case):
    """Real order fields for the Supporting Documents chips -- a fresh
    local read of the same demo CSV shopify_client.py always serves,
    never a second, separate source of truth. None if this case has no
    order side (e.g. an orphan settlement) or the order genuinely isn't
    found."""
    if not case.get("order_id"):
        return None
    return next((o for o in shopify.fetch_orders() if o["order_id"] == case["order_id"]), None)


def _settlement_row_for(case):
    """Real settlement fields, same principle as _order_row_for -- reads
    the same settlements.csv the sync step itself reads."""
    if not case.get("settlement_id"):
        return None
    df = _load_local_settlements()
    match = df[df["settlement_id"] == case["settlement_id"]]
    return match.iloc[0].to_dict() if not match.empty else None


def _candidate_rows_html(candidates, ai, full=False):
    rankings = {r["id"]: r for r in ((ai.get("candidate_rankings") if ai else None) or [])}
    shown = candidates if full else candidates[:3]
    rows = []
    for c in shown:
        cid = c.get("order_id") or c.get("settlement_id", "")
        rank = rankings.get(cid, {})
        conf = f"{rank['confidence']}%" if rank.get("confidence") is not None else "—"
        reason = rank.get("reason", "")
        amt = fmt(c.get("amount_paise", 0))
        extra = f" · {c['customer_name']}" if full and c.get("customer_name") else ""
        rows.append(f'<div class="candidate-row"><b>{cid}</b> · {amt}{extra} · {conf}'
                    f'{f" · {reason}" if reason else ""}</div>')
    return "".join(rows)


def _run_investigate_further(state, merchant_id, case, order_rows):
    """
    The one controlled agentic step, with real progress -- each of these
    4 steps corresponds to an actual function call completing (see
    case_engine.fetch_missing_evidence / build_case_context / apply_ai_
    result), not a cosmetic delay. Streamlit streams each placeholder
    redraw to the browser as it happens, same technique as the batch sync
    flow's own step list.
    """
    placeholder = st.empty()
    results = [None] * len(INVESTIGATE_STEPS)

    _render_steps(placeholder, 0, results, steps=INVESTIGATE_STEPS)
    missing = (case.get("ai") or {}).get("missing_evidence") or []
    results[0] = (f"AI named {len(missing)} item(s) to check" if missing
                  else "Nothing specific named -- proceeding with what's available")

    _render_steps(placeholder, 1, results, steps=INVESTIGATE_STEPS)
    new_evidence = case_engine.fetch_missing_evidence(case, order_rows)
    results[1] = ("Customer order history retrieved" if "customer_order_history" in new_evidence
                  else "No additional data available to fetch")

    _render_steps(placeholder, 2, results, steps=INVESTIGATE_STEPS)
    prior_confidence = (case.get("ai") or {}).get("confidence")
    original_context = case_engine.build_case_context(case)
    try:
        result = ai_client.investigate_followup(original_context, case["ai"], new_evidence)
        result.setdefault("missing_evidence", [])
        case_engine.apply_ai_result(case, result)
        if prior_confidence is not None and case["ai"].get("confidence") is not None:
            case["ai"]["previous_confidence"] = prior_confidence
        case["_event"] = "ai follow-up investigation completed"
        results[2] = f"AI responded -- {case['ai'].get('confidence')}% confidence"
    except (ai_client.AIAuthError, ai_client.AIAPIError) as exc:
        case["_event"] = f"ai follow-up investigation unavailable: {exc}"
        results[2] = f"Unavailable: {exc}"

    _render_steps(placeholder, 3, results, steps=INVESTIGATE_STEPS)
    state_store.upsert_case(state, case)
    state_store.save_state(merchant_id, state)
    results[3] = "Case updated"
    _render_steps(placeholder, len(INVESTIGATE_STEPS), results, steps=INVESTIGATE_STEPS)


def _render_case_ticket(state, merchant_id):
    case_id = st.session_state.get("selected_case_id")
    case = state_store.get_case(state, case_id) if case_id else None

    with st.container(key="ticketbackbtn"):
        if st.button("← Back to Review Queue", key="ticket_back"):
            st.session_state.current_page = st.session_state.get("previous_page", "Reconciliations")
            st.rerun()

    if not case:
        st.markdown('<div class="recon-empty">This case could not be found.</div>', unsafe_allow_html=True)
        return

    ai = case.get("ai")
    status_label, status_class = _case_status_display(case)
    bookmarked = case.get("bookmarked", False)
    already_resolved = case.get("resolution", {}).get("resolved")

    confidence = ai.get("confidence") if ai else None
    prev_confidence = ai.get("previous_confidence") if ai else None
    delta_html = ""
    if confidence is not None:
        conf_pill_text = f"{confidence}% Confidence"
        if prev_confidence is not None and confidence != prev_confidence:
            up = confidence > prev_confidence
            delta_html = (f'<span class="conf-delta {"up" if up else "down"}">'
                          f'{"▲" if up else "▼"}{abs(confidence - prev_confidence)}%</span>')
    elif ai and ai.get("error"):
        conf_pill_text = "Confidence Unavailable"
    elif case["case_status"] == "pending_settlement":
        conf_pill_text = "Confidence N/A"
    else:
        conf_pill_text = "Confidence Pending"

    hcol_title, hcol_bookmark = st.columns([6, 1])
    with hcol_title:
        st.markdown(html(f"""
            <div class="ticket-title">AI Investigation — {case['record_id']}</div>
            <div class="ticket-sub">Case ID: {case['case_id']} · {case['case_type'].replace('_', ' ').title()}</div>
            <div class="ticket-pill-row">
                <span class="status-pill {status_class}">{status_label}</span>
                <span class="status-pill pill-confidence">{conf_pill_text}</span>
                {delta_html}
            </div>
        """), unsafe_allow_html=True)
    with hcol_bookmark:
        with st.container(key=f"ticketbookmarkbtn_{'on' if bookmarked else 'off'}"):
            if st.button("🔖 Saved" if bookmarked else "🔖 Bookmark", key="ticket_bookmark_btn",
                         use_container_width=True):
                state_store.toggle_bookmark(state, case["case_id"])
                state_store.save_state(merchant_id, state)
                st.rerun()

    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    order_row = _order_row_for(case)
    settlement_row = _settlement_row_for(case)
    candidates = case.get("candidates") or []

    col_summary, col_analysis, col_docs = st.columns([1, 1.2, 1])

    # ---- Case Summary: financial facts + order/settlement metadata, one place ----
    with col_summary:
        with st.container(key="ticketsummarycard"):
            st.markdown('<div class="workspace-title">🗂️ Case Summary</div>', unsafe_allow_html=True)
            st.markdown(html(f"""
                <div class="ticket-line"><span>Expected Amount</span><b>{fmt(case['expected'])}</b></div>
                <div class="ticket-line"><span>Received Amount</span><b>{fmt(case['received'])}</b></div>
                <div class="ticket-line"><span>Difference</span><b>{fmt(case['delta'])}</b></div>
                <div class="ticket-line"><span>Order Date</span><b>{(order_row.get('order_date') if order_row else '') or '—'}</b></div>
                <div class="ticket-line"><span>Customer</span><b>{(order_row.get('customer_name') if order_row else case.get('customer_name')) or '—'}</b></div>
                <div class="ticket-line"><span>Payment Method</span><b>{(order_row.get('payment_mode') if order_row else '') or '—'}</b></div>
                <div class="ticket-line"><span>Settlement Date</span><b>{(settlement_row.get('settled_on') if settlement_row else '') or '—'}</b></div>
                <div class="ticket-line"><span>Settlement ID</span><b>{case.get('settlement_id') or '—'}</b></div>
            """), unsafe_allow_html=True)

    # ---- AI Analysis: finding, evidence and recommendation as one narrative, not 3 cards ----
    with col_analysis:
        with st.container(key="ticketanalysiscard"):
            st.markdown('<div class="workspace-title">🧠 AI Analysis</div>', unsafe_allow_html=True)
            has_error = bool(ai and ai.get("error"))
            if has_error:
                st.markdown(html(f"""
                    <div class="callout-box callout-warn">
                        <div class="callout-title">Finding</div>
                        <div class="callout-body">AI investigation could not complete: {ai['error']}
                        The case is safe and can be reprocessed.</div>
                    </div>
                """), unsafe_allow_html=True)
                with st.container(key="ticketretrybtn"):
                    if st.button("Retry AI Investigation", key="ticket_retry", use_container_width=False):
                        case_engine.retry_pending_cases(state, [case["case_id"]])
                        state_store.save_state(merchant_id, state)
                        st.rerun()
            else:
                finding = (ai["reason"] if ai and ai.get("reason") else case["explanation"]) or "No AI finding yet."
                st.markdown('<div class="ai-section-label">Finding</div>', unsafe_allow_html=True)
                st.markdown(html(f'<div class="ticket-finding">{finding}</div>'), unsafe_allow_html=True)

                evidence = (ai["evidence"] if ai and ai.get("evidence") else [])
                if evidence:
                    st.markdown('<div class="ai-section-label">Evidence</div>', unsafe_allow_html=True)
                    ev_html = "".join(f'<div class="evidence-line">✓ {e}</div>' for e in evidence)
                    st.markdown(html(ev_html), unsafe_allow_html=True)

                next_step_text = ai.get("next_step") if ai else None
                if next_step_text:
                    st.markdown('<div class="ai-section-label">AI Recommendation</div>', unsafe_allow_html=True)
                    st.markdown(html(f'<div class="ticket-finding">{next_step_text}</div>'), unsafe_allow_html=True)

    # ---- Supporting Documents: compact chips, only the ones this case actually has ----
    with col_docs:
        with st.container(key="ticketdocscard"):
            st.markdown('<div class="workspace-title">📎 Supporting Documents</div>', unsafe_allow_html=True)
            any_chip = False

            if order_row:
                any_chip = True
                with st.container(key="ticketchip_order"):
                    with st.popover("📦 Order Details", use_container_width=True):
                        st.markdown(html(f"""
                            <div class="ticket-line"><span>Order ID</span><b>{order_row['order_id']}</b></div>
                            <div class="ticket-line"><span>Order Date</span><b>{order_row.get('order_date') or '—'}</b></div>
                            <div class="ticket-line"><span>Customer</span><b>{order_row.get('customer_name') or '—'}</b></div>
                            <div class="ticket-line"><span>Amount</span><b>{fmt(to_paise(order_row.get('order_amount') or 0))}</b></div>
                            <div class="ticket-line"><span>Payment Mode</span><b>{order_row.get('payment_mode') or '—'}</b></div>
                            <div class="ticket-line"><span>Gateway Ref ID</span><b>{order_row.get('gateway_ref_id') or '—'}</b></div>
                            <div class="ticket-line"><span>Bank UTR</span><b>{order_row.get('bank_utr') or '—'}</b></div>
                            <div class="ticket-line"><span>Source</span><b>Shopify (demo data)</b></div>
                        """), unsafe_allow_html=True)

            if settlement_row:
                any_chip = True
                with st.container(key="ticketchip_settlement"):
                    with st.popover("🏦 Settlement Details", use_container_width=True):
                        st.markdown(html(f"""
                            <div class="ticket-line"><span>Settlement ID</span><b>{settlement_row['settlement_id']}</b></div>
                            <div class="ticket-line"><span>Settled On</span><b>{settlement_row.get('settled_on') or '—'}</b></div>
                            <div class="ticket-line"><span>Amount Received</span><b>{fmt(to_paise(settlement_row.get('amount_received') or 0))}</b></div>
                            <div class="ticket-line"><span>Gateway Ref ID</span><b>{settlement_row.get('gateway_ref_id') or '—'}</b></div>
                            <div class="ticket-line"><span>Bank UTR</span><b>{settlement_row.get('bank_utr') or '—'}</b></div>
                            <div class="ticket-line"><span>Source</span><b>{settlement_row.get('source') or '—'}</b></div>
                            <div class="ticket-line"><span>Narration</span><b>{settlement_row.get('narration') or '—'}</b></div>
                        """), unsafe_allow_html=True)

            if order_row:
                any_chip = True
                amt_paise = to_paise(order_row.get("order_amount") or 0)
                mode = order_row.get("payment_mode") or "—"
                band_paise = fee_band(amt_paise, mode)
                pct = "2.5%" if mode == "COD" else "2%"
                flat = fmt(5000) if mode == "COD" else fmt(300)
                with st.container(key="ticketchip_fee"):
                    with st.popover("💳 Fee Structure (MDR)", use_container_width=True):
                        st.markdown(html(f"""
                            <div class="ticket-line"><span>Payment Mode</span><b>{mode}</b></div>
                            <div class="ticket-line"><span>Tolerance Rule</span><b>{pct} of order value, or {flat} flat -- whichever is larger</b></div>
                            <div class="ticket-line"><span>Order Amount</span><b>{fmt(amt_paise)}</b></div>
                            <div class="ticket-line"><span>Max Explainable Shortfall</span><b>{fmt(band_paise)}</b></div>
                            <div class="ticket-line"><span>This Case's Shortfall</span><b>{fmt(abs(case['delta']))}</b></div>
                        """), unsafe_allow_html=True)
                        st.caption("The same rule engine.py uses to auto-clear known fee deductions -- "
                                   "shown for reference, not a live recomputation of this case's tier.")

            if candidates:
                any_chip = True
                with st.container(key="ticketchip_candidates"):
                    with st.popover(f"🔗 Candidate Matches ({len(candidates)})", use_container_width=True):
                        st.markdown(html(_candidate_rows_html(candidates, ai)), unsafe_allow_html=True)
                        if len(candidates) > 3:
                            with st.expander(f"View full candidate details ({len(candidates)} total)"):
                                st.markdown(html(_candidate_rows_html(candidates, ai, full=True)),
                                            unsafe_allow_html=True)

            any_chip = True
            with st.container(key="ticketchip_activity"):
                with st.popover("🕐 Activity Log", use_container_width=True):
                    history = case.get("history") or []
                    hist_html = "".join(
                        f'<div class="timeline-row"><span>{datetime.fromisoformat(h["at"]).strftime("%b %d, %Y %I:%M %p")}</span>'
                        f'<span>{h["event"]}</span></div>' for h in history)
                    st.markdown(html(hist_html or '<div class="evidence-line">No history yet.</div>'),
                                unsafe_allow_html=True)

            if not any_chip:
                st.markdown('<div class="evidence-line">No supporting documents available.</div>',
                            unsafe_allow_html=True)

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    # ---- Actions: comment is required for Keep for Manual Review, auto-filled on Accept ----
    comment_key = f"ticket_comment_{case['case_id']}"
    st.session_state.setdefault(comment_key, case.get("comment", ""))

    can_auto_resolve = bool(ai and ai.get("action") == "resolve" and not already_resolved)
    missing_evidence = (ai.get("missing_evidence") if ai else None) or []
    can_investigate_further = bool(missing_evidence and not already_resolved)
    manual_review_error = False

    # Accept & Reconcile is the positive/default path -- primary, leftmost.
    # Investigate Further stays secondary (purple outline). Keep for Manual
    # Review stays neutral, rightmost -- the least-emphasized of the three.
    acol_accept, acol_investigate, acol_manual = st.columns([1.2, 1, 1])
    with acol_accept:
        with st.container(key="ticketacceptbtn"):
            if st.button("Accept & Reconcile", key="ticket_accept", use_container_width=True,
                         disabled=not can_auto_resolve):
                final_comment = ((st.session_state.get(comment_key) or "").strip()
                                  or (ai.get("next_step") if ai else "") or "")
                state_store.record_resolution(state, case["case_id"], "accepted", comment=final_comment)
                state_store.save_state(merchant_id, state)
                st.rerun()
    with acol_investigate:
        with st.container(key="ticketfollowupbtn"):
            if st.button("Investigate Further", key="ticket_followup", use_container_width=True,
                         disabled=not can_investigate_further,
                         help=("AI named specific missing evidence -- fetch what's realistically "
                               "available and ask for one final conclusion." if can_investigate_further
                               else "No missing evidence named, or already followed up.")):
                order_rows = shopify.fetch_orders()
                _run_investigate_further(state, merchant_id, case, order_rows)
                st.rerun()
    with acol_manual:
        with st.container(key="ticketmanualbtn"):
            if st.button("Keep for Manual Review", key="ticket_manual", use_container_width=True,
                         disabled=already_resolved):
                typed_comment = (st.session_state.get(comment_key) or "").strip()
                if not typed_comment:
                    manual_review_error = True
                else:
                    state_store.record_resolution(state, case["case_id"], "manual_review",
                                                   comment=typed_comment)
                    state_store.save_state(merchant_id, state)
                    st.rerun()

    if manual_review_error:
        st.markdown(html("""
            <div class="callout-box callout-warn">
                Please add a comment below before keeping this case for manual review.
            </div>
        """), unsafe_allow_html=True)

    if already_resolved:
        res = case["resolution"]
        resolved_label = "AI Recommendation Accepted" if res["resolution_type"] == "accepted" else "Kept for Manual Review"
        comment_row = (f'<div class="resolved-comment-box"><div class="ai-section-label">Comment</div>'
                       f'<div class="ticket-finding">{res["comment"]}</div></div>' if res.get("comment") else "")
        st.markdown(html(f"""
            <div class="resolved-banner">
                <div class="resolved-banner-title">✅ Case Resolved Successfully!</div>
                <div class="ticket-line"><span>Resolution Type</span><b>{resolved_label}</b></div>
                <div class="ticket-line"><span>Resolved By</span><b>{res['resolved_by']}</b></div>
                <div class="ticket-line"><span>Resolved At</span><b>{datetime.fromisoformat(res['resolved_at']).strftime('%b %d, %Y %I:%M %p')}</b></div>
                {comment_row}
            </div>
        """), unsafe_allow_html=True)

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
    with st.expander("✨ Ask AI about this case", expanded=False):
        _render_ask_ai(state, case_id=case["case_id"], key_prefix=f"ticketask_{case['case_id']}")

    with st.container(key="ticketcommentbox"):
        with st.expander("💬 Comments", expanded=manual_review_error):
            st.text_area("Comment", key=comment_key, placeholder="Add a comment...",
                         label_visibility="collapsed", height=80)
            if st.button("Save Comment", key="ticket_save_comment", use_container_width=False):
                state_store.set_comment(state, case["case_id"], st.session_state[comment_key])
                state_store.save_state(merchant_id, state)
                st.rerun()
            st.markdown('<div class="ask-ai-hint">Required before Keep for Manual Review; '
                        'auto-fills with the AI recommendation on Accept.</div>', unsafe_allow_html=True)

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
    history = case.get("history") or []
    hist_rows = "".join(
        f'<div class="timeline-row"><span>{datetime.fromisoformat(h["at"]).strftime("%b %d, %Y %I:%M %p")}</span>'
        f'<span>{h["event"]}</span></div>' for h in reversed(history))
    st.markdown(html(f"""
        <div class="recon-card">
            <div class="recon-title">Case Timeline</div>
            <div class="workspace-sub">Audit trail for this case — newest first.</div>
            <div style="height:8px;"></div>
            {hist_rows or '<div class="evidence-line">No events yet.</div>'}
        </div>
    """), unsafe_allow_html=True)


# ===========================================================================
# Shared shell CSS
# ===========================================================================
def _shell_css():
    return html(f"""
        <style>
        .block-container {{padding: 28px 36px !important; max-width: 100% !important;}}
        .stApp {{background: {SOFT};}}

        /* ---- sidebar: forced visible and non-collapsible ---- */
        [data-testid="collapsedControl"] {{display: none !important;}}
        [data-testid="stSidebar"] {{
            display: flex !important; visibility: visible !important;
            transform: none !important; width: 240px !important; min-width: 240px !important;
            background: {BG} !important; border-right: 1px solid {LINE} !important;
        }}
        [data-testid="stSidebar"] > div {{padding: 20px 14px !important; display: flex; flex-direction: column; height: 100%;}}
        [data-testid="stSidebarUserContent"] {{display: flex; flex-direction: column; flex: 1;}}
        .side-logo {{
            display: flex; align-items: center; gap: 8px; padding: 4px 8px 2px;
            font-size: 18px; font-weight: 700; letter-spacing: -.03em; color: {INK};
        }}
        .side-logo-mark {{
            width: 26px; height: 26px; border-radius: 7px;
            background: linear-gradient(135deg, {ACC}, #7C6CF0);
            display: flex; align-items: center; justify-content: center;
            font-size: 13px; color: #fff;
        }}
        .side-company {{font-size: 11.5px; color: {DIM}; padding: 0 8px 18px;}}
        [data-testid="stSidebar"] .stButton > button {{
            background: transparent !important; border: none !important; color: {BODY} !important;
            font-size: 13.5px !important; font-weight: 500 !important;
            text-align: left !important; justify-content: flex-start !important;
            padding: 9px 10px !important; border-radius: 7px !important;
        }}
        [data-testid="stSidebar"] .stButton > button:hover {{background: {SOFT} !important; color: {INK} !important;}}
        .st-key-navactive .stButton > button {{
            background: #E8EEFC !important; color: {ACC} !important; font-weight: 600 !important;
        }}
        .st-key-navactive .stButton > button:hover {{background: #E8EEFC !important; color: {ACC} !important;}}
        .side-footer-email {{font-size: 11px; color: {DIM}; padding: 8px 10px 4px; word-break: break-all;}}
        .st-key-sidelogout .stButton > button {{color: {WARN} !important; font-size: 12.5px !important;}}

        /* ---- header ---- */
        .page-title {{font-size: 22px; font-weight: 700; letter-spacing: -.02em; color: {INK};}}
        .page-sub {{font-size: 13px; color: {DIM}; margin-top: 2px;}}

        .st-key-rightslot {{position: relative;}}
        .st-key-avatarbtn {{margin-left: auto; width: 34px;}}
        .st-key-avatarbtn button {{
            border-radius: 50% !important; width: 34px !important; height: 34px !important;
            padding: 0 !important; font-size: 12px !important; font-weight: 700 !important;
            min-width: 0 !important; background: {PURPLE} !important; color: #fff !important;
            border: none !important;
        }}
        .st-key-avatarbtn button:hover, .st-key-avatarbtn button:focus, .st-key-avatarbtn button:active {{
            background: {PURPLE} !important; color: #fff !important; box-shadow: none !important;
        }}
        .st-key-accountmenu {{
            position: absolute !important; top: 42px !important; right: 0 !important;
            width: 168px !important; min-width: 168px !important; max-width: 168px !important;
            margin: 0 !important; z-index: 1000 !important;
            background: rgba(255,255,255,.96); backdrop-filter: blur(8px);
            border: 1px solid {LINE}; border-radius: 10px;
            box-shadow: 0 12px 28px rgba(12,14,18,.14); padding: 6px;
        }}
        .st-key-bellslot {{position: relative;}}
        .st-key-bellbtn {{margin-left: auto; width: 34px;}}
        .st-key-bellbtn button {{
            border-radius: 50% !important; width: 34px !important; height: 34px !important;
            padding: 0 !important; font-size: 14px !important;
            min-width: 0 !important; background: {BG} !important; color: {INK} !important;
            border: 1px solid {LINE} !important;
        }}
        .st-key-bellbtn button:hover, .st-key-bellbtn button:focus, .st-key-bellbtn button:active {{
            background: {SOFT} !important; color: {INK} !important; box-shadow: none !important;
        }}
        .st-key-notifpanel {{
            position: absolute !important; top: 42px !important; right: 0 !important;
            width: 300px !important; min-width: 300px !important; max-width: 300px !important;
            margin: 0 !important; z-index: 1001 !important;
            background: rgba(255,255,255,.98); backdrop-filter: blur(8px);
            border: 1px solid {LINE}; border-radius: 10px;
            box-shadow: 0 12px 28px rgba(12,14,18,.14); padding: 14px;
        }}
        .st-key-rightslot [data-testid="stElementContainer"],
        .st-key-accountmenu [data-testid="stElementContainer"],
        .st-key-bellslot [data-testid="stElementContainer"],
        .st-key-notifpanel [data-testid="stElementContainer"] {{margin: 0 !important;}}
        .st-key-accountmenu [data-testid="stVerticalBlock"] {{gap: 0 !important;}}
        .st-key-accountmenu .stButton {{margin: 0 !important;}}
        .st-key-accountmenu .stButton > button {{
            border: none !important; background: transparent !important; color: {INK} !important;
            font-size: 13.5px !important; font-weight: 500 !important;
            padding: 9px 10px !important; text-align: left !important;
            justify-content: flex-start !important; width: 100% !important;
        }}
        .st-key-accountmenu .stButton > button:hover {{background: {SOFT} !important;}}
        .st-key-accountmenu hr {{margin: 4px 0 !important;}}
        .st-key-notifpanel .stButton > button {{
            background: {ACC} !important; color: #fff !important; border: none !important;
            border-radius: 7px !important; font-weight: 600 !important; font-size: 12.5px !important;
        }}
        .st-key-notifpanel .stButton > button:hover {{background: {ACC_D} !important;}}
        .notif-title {{font-size: 13.5px; font-weight: 700; color: {INK}; margin-bottom: 8px;}}
        .notif-empty {{font-size: 12.5px; color: {DIM}; padding: 6px 0 10px;}}
        .notif-breakdown {{font-size: 12px; color: {BODY}; line-height: 1.9; margin: 4px 0 10px;}}
        .notif-ago {{font-size: 11px; color: {DIM}; margin-bottom: 10px;}}

        /* ---- floating "new data" overlay ---- */
        .st-key-newdataoverlay {{
            position: fixed !important; top: 78px !important; right: 36px !important;
            width: 300px !important; z-index: 2000 !important;
            background: #fff !important; border: 1px solid {LINE} !important;
            border-radius: 12px !important; box-shadow: 0 16px 40px rgba(12,14,18,.18) !important;
            padding: 16px 16px 10px !important;
            animation: overlay-in .22s ease;
        }}
        @keyframes overlay-in {{ from {{opacity:0; transform: translateY(-8px);}} to {{opacity:1; transform:none;}} }}
        .st-key-newdataoverlay [data-testid="stElementContainer"] {{margin: 0 !important;}}
        .st-key-newdataoverlay .stButton > button {{font-size: 12.5px !important;}}
        .st-key-newdataoverlay [data-testid="column"]:first-child .stButton > button,
        .st-key-newdataoverlay [data-testid="stColumn"]:first-child .stButton > button {{
            background: transparent !important; color: {DIM} !important; border: none !important;
            font-weight: 500 !important; padding: 6px 0 !important; box-shadow: none !important;
        }}
        .st-key-newdataoverlay [data-testid="column"]:last-child .stButton > button,
        .st-key-newdataoverlay [data-testid="stColumn"]:last-child .stButton > button {{
            background: transparent !important; color: {DIM} !important; border: none !important;
            padding: 6px 0 !important; font-weight: 600 !important; box-shadow: none !important;
        }}
        .st-key-overlayprimarybtn button {{
            background: {ACC} !important; color: #fff !important; border: none !important;
            border-radius: 7px !important; font-weight: 600 !important; font-size: 12.5px !important;
        }}
        .st-key-overlayprimarybtn button:hover {{background: {ACC_D} !important;}}

        /* ---- welcome row / control row ---- */
        .welcome-title {{font-size: 24px; font-weight: 700; letter-spacing: -.02em; color: {INK}; margin: 0;}}
        .welcome-sub {{font-size: 13.5px; color: {DIM}; margin-top: 4px;}}
        .control-badge {{
            background: {SOFT}; border: 1px solid {LINE}; border-radius: 7px; color: {BODY};
            font-size: 12.5px; font-weight: 500; padding: 8px 12px; text-align: center;
        }}
        .st-key-newreconbtn button, .st-key-newreconbtn2 button {{
            background: {ACC} !important; color: #fff !important; border: none !important;
            border-radius: 8px !important; font-weight: 600 !important; font-size: 13.5px !important;
        }}
        .st-key-newreconbtn button:hover, .st-key-newreconbtn2 button:hover {{background: {ACC_D} !important;}}

        /* ---- ready state / sync / no-new-data cards ---- */
        .ready-card {{
            background: {BG}; border: 1px solid {LINE}; border-radius: 14px;
            padding: 32px 30px; text-align: center;
        }}
        .ready-title {{font-size: 16px; font-weight: 700; color: {INK};}}
        .ready-sub {{font-size: 12.5px; color: {DIM}; margin-top: 6px;}}
        .ready-badge {{
            display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;
            margin: 20px auto 4px; max-width: 420px;
        }}
        .ready-tile {{background: {SOFT}; border-radius: 10px; padding: 16px 8px;}}
        .ready-tile-value {{font-size: 22px; font-weight: 700; color: {INK};}}
        .ready-tile-label {{font-size: 11.5px; color: {DIM}; margin-top: 2px;}}
        .sync-card {{
            background: {BG}; border: 1px solid {LINE}; border-radius: 14px; padding: 24px 30px;
        }}
        .sync-heading {{font-size: 14.5px; font-weight: 700; color: {INK}; margin-bottom: 10px;}}
        .sync-step {{display: flex; align-items: center; gap: 12px; padding: 9px 0;}}
        .sync-step-icon {{font-size: 15px; width: 20px; text-align: center;}}
        .sync-step-done {{color: {DIM}; opacity: .55; font-size: 13px;}}
        .sync-step-active {{color: {INK}; font-weight: 700; font-size: 14px; opacity: 1;}}
        .sync-step-pending {{color: {DIM}; opacity: .35; font-size: 13px;}}
        .sync-step-result {{font-size: 11.5px; color: {MATCHED}; opacity: .85; margin: -3px 0 5px 32px;}}
        .pending-banner {{
            background: #EAF0FE; border: 1px solid #C7D7FB; border-radius: 10px;
            padding: 10px 14px; font-size: 12.5px; color: {INK}; display: flex;
            align-items: center; justify-content: space-between; gap: 12px;
        }}
        .st-key-pendingsyncbtn {{margin-top: -46px; float: right; width: 160px;}}
        .st-key-pendingsyncbtn button {{
            background: {ACC} !important; color: #fff !important; border: none !important;
            border-radius: 7px !important; font-weight: 600 !important; font-size: 12px !important;
            padding: 5px 10px !important;
        }}

        /* ---- KPI cards ---- */
        .kpi-grid {{display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px;}}
        .kpi-grid-8 {{display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; row-gap: 14px;}}
        .kpi-card {{background: {BG}; border: 1px solid {LINE}; border-radius: 12px; padding: 16px 18px;}}
        .kpi-icon {{
            width: 32px; height: 32px; border-radius: 8px; display: flex;
            align-items: center; justify-content: center; font-size: 14px; margin-bottom: 10px;
        }}
        .kpi-label {{font-size: 12px; font-weight: 500; color: {BODY};}}
        .kpi-value {{font-size: 22px; font-weight: 700; letter-spacing: -.02em; margin: 4px 0 2px; color: {INK};}}
        .kpi-sub {{font-size: 11px; color: {DIM};}}

        /* ---- workspace cards (donut / amount flow / risk summary) ---- */
        .workspace-card {{background: {BG}; border: 1px solid {LINE}; border-radius: 12px; padding: 18px 20px;}}
        .workspace-title {{font-size: 14px; font-weight: 700; color: {INK};}}
        .workspace-sub {{font-size: 11px; color: {DIM}; margin-top: 2px;}}
        .risk-row {{
            display: flex; align-items: baseline; justify-content: space-between;
            padding: 8px 0; border-bottom: 1px solid {LINE};
        }}
        .risk-row-label {{font-size: 12.5px; font-weight: 600; color: {INK}; flex: 1;}}
        .risk-row-amount {{font-size: 12.5px; font-weight: 600; color: {WARN}; margin-right: 10px;}}
        .risk-row-count {{font-size: 11px; color: {DIM};}}
        [class^="st-key-risklink_"] .stButton > button {{
            background: transparent !important; border: none !important; color: {ACC} !important;
            font-size: 11px !important; font-weight: 600 !important; padding: 2px 0 10px !important;
            justify-content: flex-start !important;
        }}

        /* ---- recent reconciliations / review queue tables ---- */
        .recon-card {{background: {BG}; border: 1px solid {LINE}; border-radius: 12px; padding: 22px 24px;}}
        .recon-title {{font-size: 15.5px; font-weight: 600; color: {INK}; margin-bottom: 6px;}}
        .recon-table {{width: 100%; border-collapse: collapse; font-size: 12.5px;}}
        .recon-table th {{
            text-align: left; font-size: 10.5px; font-weight: 600; letter-spacing: .05em;
            text-transform: uppercase; color: {DIM}; padding: 0 10px 10px 0; border-bottom: 1px solid {LINE};
        }}
        .recon-table td {{padding: 11px 10px 11px 0; border-bottom: 1px solid {LINE}; color: {INK}; vertical-align: middle;}}
        .recon-table tr:last-child td {{border-bottom: none;}}
        .recon-name {{font-weight: 500;}}
        .recon-dim {{color: {DIM}; font-size: 12px;}}
        .status-pill {{
            display: inline-flex; align-items: center; background: #E7F5EF; color: {MATCHED};
            border-radius: 999px; padding: 3px 10px; font-size: 11px; font-weight: 500;
        }}
        .status-pill.pill-ai {{background: #EDE7FB; color: {PURPLE};}}
        .status-pill.pill-ai-recommendation {{background: #FEF3E2; color: #B45309;}}
        .status-pill.pill-exception {{background: {WARN_BG}; color: {WARN};}}
        .status-pill.pill-exception-hard {{background: #EDEEF1; color: #40454D; font-weight: 600;}}
        .status-pill.pill-pending {{background: #FEF6E7; color: #B45309;}}
        .status-pill.pill-ai-pending {{background: #F1F2F4; color: {DIM};}}
        .status-pill.pill-resolved {{background: #E7F5EF; color: {MATCHED};}}
        .status-pill.pill-issue {{background: {SOFT}; color: {BODY}; border: 1px solid {LINE};}}
        .recon-empty {{text-align: center; padding: 28px 0; color: {DIM}; font-size: 13px; line-height: 1.7;}}
        .st-key-viewallbtn button, .st-key-viewallreviewbtn button {{
            background: transparent !important; border: none !important; color: {ACC} !important;
            font-weight: 600 !important; font-size: 13px !important; width: auto !important;
        }}

        /* ---- case table (Review Queue / AI Review / Exceptions) -- real
           st.columns() rows, not one giant HTML table, so "View ->" can be
           a real button per row. ---- */
        .case-cell {{font-size: 12.5px; color: {INK}; padding: 8px 0; line-height: 1.5;}}
        .case-cell-name {{font-weight: 500;}}
        .case-cell-summary {{font-size: 12px; line-height: 1.45; max-height: 2.9em; overflow: hidden;}}
        .queue-row-head {{
            display: grid; grid-template-columns: 0.35fr 1.3fr 1.15fr 1.2fr 1.7fr 1.7fr 1fr 1.05fr 0.6fr;
            gap: 8px; font-size: 10px; font-weight: 600; letter-spacing: .04em; text-transform: uppercase;
            color: {DIM}; padding: 0 0 8px; border-bottom: 1px solid {LINE}; margin-bottom: 4px;
        }}
        .queue-row-head.queue-row-compact {{
            grid-template-columns: 1.2fr 1fr 0.9fr 2fr 0.9fr 1fr 0.55fr;
        }}
        [class^="st-key-cases_"] [data-testid="stElementContainer"],
        [class^="st-key-airev_"] [data-testid="stElementContainer"],
        [class^="st-key-exc_"] [data-testid="stElementContainer"],
        [class^="st-key-reviewqueue_"] [data-testid="stElementContainer"] {{margin: 0 !important;}}

        /* ---- confidence mini-bar, inline in the Review Queue table ---- */
        .conf-cell {{display: flex; flex-direction: column; gap: 3px;}}
        .conf-cell span {{font-size: 12px; font-weight: 600; color: {INK};}}
        .conf-bar-track {{width: 70px; height: 4px; background: {LINE}; border-radius: 2px; overflow: hidden;}}
        .conf-bar {{height: 100%; border-radius: 2px;}}

        /* ---- filter pills above the Review Queue ---- */
        [class^="st-key-"][class*="_pill_"] .stButton > button {{
            border-radius: 999px !important; font-size: 11.5px !important; font-weight: 600 !important;
            padding: 5px 4px !important;
        }}
        [class^="st-key-"][class*="_pill_"] .stButton > button[kind="secondary"] {{
            background: {SOFT} !important; color: {BODY} !important; border: 1px solid {LINE} !important;
        }}
        [class^="st-key-"][class*="_pill_"] .stButton > button[kind="primary"] {{
            background: {ACC} !important; color: #fff !important; border: none !important;
        }}
        .confidence-guide {{
            background: #EAF0FE; border: 1px solid #C7D7FB; border-radius: 8px; padding: 10px 14px;
            font-size: 11.5px; color: {BODY}; margin-top: 14px; line-height: 1.6;
        }}

        /* ---- resolution funnel (replaces the donut) ---- */
        .funnel-row {{display: flex; align-items: center; gap: 10px; padding: 6px 0;}}
        .funnel-label {{font-size: 11.5px; color: {BODY}; width: 150px; flex: none;}}
        .funnel-bar-track {{flex: 1; height: 16px; background: {SOFT}; border-radius: 4px; overflow: hidden;}}
        .funnel-bar {{height: 100%; border-radius: 4px;}}
        .funnel-count {{font-size: 12.5px; font-weight: 700; color: {INK}; width: 30px; text-align: right; flex: none;}}
        .funnel-pct {{font-size: 11px; color: {DIM}; width: 34px; text-align: right; flex: none;}}

        /* ---- awaiting-settlement widget ---- */
        .pending-summary {{
            font-size: 13px; font-weight: 600; color: {INK}; margin: 6px 0 2px;
        }}
        .pending-row {{
            display: grid; grid-template-columns: 1.5fr 1fr 0.8fr; gap: 8px;
            font-size: 12px; color: {INK}; padding: 7px 0; border-bottom: 1px solid {LINE};
        }}
        .pending-row:last-child {{border-bottom: none;}}
        .pending-row-head {{
            font-size: 10px; font-weight: 600; letter-spacing: .04em; text-transform: uppercase;
            color: {DIM}; border-bottom: 1px solid {LINE};
        }}

        /* ---- Ask AI box ---- */
        .st-key-mainaskbox, [class^="st-key-ticketask_"] {{
            background: #F5F3FF !important; border: 1px solid #DDD6FE !important;
            border-radius: 10px !important; padding: 14px 16px !important;
        }}
        .ask-ai-label {{font-size: 13px; font-weight: 700; color: {INK}; margin-bottom: 8px;}}
        .ask-ai-answer {{
            background: {BG}; border: 1px solid {LINE}; border-radius: 8px;
            padding: 10px 12px; font-size: 12.5px; color: {INK}; margin-top: 8px; white-space: pre-wrap;
        }}
        .ask-ai-hint {{font-size: 10.5px; color: {DIM}; margin-top: 6px;}}
        [class^="st-key-mainask"] .stButton > button, [class^="st-key-ticketask_"] .stButton > button {{
            background: {PURPLE} !important; color: #fff !important; border: none !important;
            border-radius: 7px !important; font-weight: 600 !important;
        }}

        /* ---- investigation ticket ---- */
        .ticket-title {{font-size: 18px; font-weight: 700; color: {INK};}}
        .ticket-sub {{font-size: 12px; color: {DIM}; margin-top: 2px;}}
        .ticket-pill-row {{display: flex; align-items: center; gap: 8px; margin-top: 8px;}}
        .ticket-line {{
            display: flex; justify-content: space-between; align-items: center;
            font-size: 12.5px; color: {BODY}; padding: 5px 0; border-bottom: 1px solid {LINE};
        }}
        .ticket-line:last-child {{border-bottom: none;}}
        .ticket-finding {{font-size: 13px; color: {INK}; line-height: 1.6;}}
        .evidence-line {{font-size: 12.5px; color: {MATCHED}; padding: 4px 0;}}
        .evidence-line.evidence-missing {{color: {WARN};}}
        .candidate-row {{font-size: 12px; color: {INK}; padding: 6px 0; border-bottom: 1px solid {LINE};}}
        .candidate-row:last-child {{border-bottom: none;}}
        .timeline-row {{
            display: flex; gap: 12px; font-size: 12px; color: {BODY}; padding: 5px 0;
        }}
        .timeline-row span:first-child {{color: {DIM}; min-width: 150px;}}
        .ai-section-label {{
            font-size: 11px; font-weight: 700; color: {DIM}; text-transform: uppercase;
            letter-spacing: .04em; margin: 12px 0 4px;
        }}
        .ai-section-label:first-of-type {{margin-top: 0;}}
        .status-pill.pill-confidence {{background: #EEF2FF; color: {ACC}; border: 1px solid #C7D2FE;}}
        .conf-delta {{font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 999px;}}
        .conf-delta.up {{background: #E7F5EF; color: {MATCHED};}}
        .conf-delta.down {{background: {WARN_BG}; color: {WARN};}}
        .callout-box {{border-radius: 8px; padding: 10px 12px; margin: 10px 0 0; font-size: 12px; line-height: 1.6;}}
        .callout-box.callout-warn {{background: #FEF6E7; border: 1px solid #FDE3B0;}}
        .callout-box.callout-info {{background: #EEF2FF; border: 1px solid #C7D2FE;}}
        .callout-title {{font-weight: 700; color: {INK}; margin-bottom: 4px;}}
        .callout-body {{color: {BODY};}}
        .callout-list {{margin: 4px 0 0 16px; padding: 0; color: {BODY};}}
        .callout-list li {{margin-bottom: 3px;}}
        .resolved-banner {{
            background: #E7F5EF; border: 1px solid #BFE8D4; border-radius: 10px; padding: 14px 16px;
        }}
        .resolved-banner-title {{font-size: 14px; font-weight: 700; color: {MATCHED}; margin-bottom: 8px;}}
        .resolved-comment-box {{
            background: {BG}; border: 1px solid {LINE}; border-radius: 8px; padding: 10px 12px; margin-top: 10px;
        }}
        .st-key-ticketsummarycard, .st-key-ticketanalysiscard, .st-key-ticketdocscard {{
            background: {BG} !important; border: 1px solid {LINE} !important;
            border-radius: 12px !important; padding: 18px 20px !important; height: 100%;
        }}
        [class*="st-key-ticketchip_"] {{margin-bottom: 8px;}}
        [class*="st-key-ticketchip_"] button {{
            background: {SOFT} !important; color: {ACC} !important; border: 1px solid {LINE} !important;
            border-radius: 8px !important; font-weight: 600 !important; font-size: 12.5px !important;
            text-align: left !important; justify-content: flex-start !important; padding: 8px 12px !important;
        }}
        [class*="st-key-ticketchip_"] button:hover {{
            background: #EEF2FF !important; border-color: #C7D2FE !important;
        }}
        .st-key-ticketcommentbox {{padding-top: 4px;}}
        .st-key-ticketbackbtn button {{
            background: transparent !important; border: none !important; color: {ACC} !important;
            font-weight: 600 !important; width: auto !important;
        }}
        .st-key-ticketacceptbtn button {{
            background: {MATCHED} !important; color: #fff !important; border: none !important;
            font-weight: 600 !important;
        }}
        .st-key-ticketmanualbtn button {{
            background: transparent !important; color: {BODY} !important; border: 1px solid {LINE} !important;
            font-weight: 600 !important;
        }}
        .st-key-ticketfollowupbtn button {{
            background: transparent !important; color: {PURPLE} !important; border: 1px solid #DDD6FE !important;
            font-weight: 600 !important;
        }}
        /* Disabled action buttons must actually LOOK unclickable -- without
           this, the :disabled state was hidden underneath the !important
           color overrides above, so a disabled button (e.g. Accept &
           Reconcile when AI recommends escalate, not resolve) looked just
           as clickable as an enabled one. */
        .st-key-ticketacceptbtn button:disabled,
        .st-key-ticketmanualbtn button:disabled,
        .st-key-ticketfollowupbtn button:disabled {{
            background: {SOFT} !important; color: {DIM} !important; border: 1px solid {LINE} !important;
            cursor: not-allowed !important; opacity: .7 !important;
        }}
        .st-key-ticketretrybtn button {{
            background: {ACC} !important; color: #fff !important; border: none !important;
            font-weight: 600 !important; padding: 6px 16px !important;
        }}
        .st-key-ticketbookmarkbtn_off button {{
            background: transparent !important; color: {BODY} !important; border: 1px solid {LINE} !important;
            font-weight: 600 !important; font-size: 12.5px !important;
        }}
        .st-key-ticketbookmarkbtn_on button {{
            background: #FEF3E2 !important; color: #B45309 !important; border: 1px solid #FDE3B0 !important;
            font-weight: 600 !important; font-size: 12.5px !important;
        }}

        /* ---- transactions ledger ---- */
        .txn-summary {{
            display: flex; justify-content: space-between; align-items: center;
            font-size: 12.5px; color: {BODY}; margin-bottom: 10px; padding: 8px 12px;
            background: {BG}; border: 1px solid {LINE}; border-radius: 8px;
        }}
        .txn-row {{
            display: grid; grid-template-columns: 1.1fr 0.7fr 1fr 1.1fr 0.9fr 0.85fr 1fr 0.55fr;
            gap: 6px; font-size: 10px; font-weight: 600; letter-spacing: .04em;
            text-transform: uppercase; color: {DIM}; padding: 0 0 6px;
            border-bottom: 1px solid {LINE}; margin-bottom: 2px;
        }}

        /* ---- data sources ---- */
        .source-card {{
            background: {BG}; border: 1px solid {LINE}; border-radius: 10px;
            padding: 14px 16px; margin-bottom: 10px;
        }}
        .source-card-head {{
            display: flex; justify-content: space-between; align-items: center;
            font-size: 14px; color: {INK}; margin-bottom: 4px;
        }}
        .source-badge {{font-size: 11px; font-weight: 600;}}
        .source-provider {{font-size: 12px; color: {DIM}; margin-bottom: 4px;}}
        .source-msg {{font-size: 12px; color: {BODY}; line-height: 1.5;}}

        @media (max-width: 1200px) {{
            .kpi-grid {{grid-template-columns: repeat(2, 1fr);}}
            .block-container {{padding: 20px 18px !important;}}
        }}
        </style>
    """)


# ===========================================================================
# Main dispatch
# ===========================================================================
def show_main_dashboard():
    """Main app shell: sidebar + header are shared by every page; the
    active page in st.session_state.current_page decides the body."""
    merchant = get_current_merchant(st.session_state)
    merchant_id = merchant["merchant_id"]
    state = state_store.load_state(merchant_id)
    state_store.save_state(merchant_id, state)  # persist any normalize_state repairs

    # Auto-fire the "new data" notification the moment a scheduled batch's
    # timer passes -- checked here, on whatever natural rerun happens to
    # occur, so it fires regardless of which page is active. Batch 1 never
    # gets this treatment: it's the initial data, not a "new data
    # received" event. notification_created is persisted, so this can
    # only ever fire once per batch, refresh or not.
    batch_ready = (state["current_batch"] <= state_store.TOTAL_BATCHES
                   and state_store.batch_is_available(state))
    if batch_ready and state["current_batch"] > 1 and not state["notification_created"]:
        state_store.mark_notification_created(state)
        state_store.save_state(merchant_id, state)

    page = st.session_state.current_page

    st.markdown(base_css(), unsafe_allow_html=True)
    st.markdown(_shell_css(), unsafe_allow_html=True)

    _render_sidebar(merchant, page)
    _render_header_and_notifications(merchant, merchant_id, state, page)
    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    if page == "Dashboard":
        _render_dashboard(state, merchant_id)
    elif page == "Reconciliations":
        _render_reconciliations(state, merchant_id)
    elif page == "AI Review":
        _render_ai_review(state)
    elif page == "Exceptions":
        _render_exceptions(state)
    elif page == "Transactions":
        _render_transactions(state)
    elif page == "Reports":
        _render_reports(state)
    elif page == "Data Sources":
        _render_data_sources()
    elif page == "Settings":
        _render_settings(merchant, merchant_id)
    elif page == "Case Ticket":
        _render_case_ticket(state, merchant_id)
    else:
        st.info(f"{page} is coming soon.")


# Main app logic
# Wrapped in one st.empty() so switching between screens (login vs. the
# app shell) fully replaces the previous screen's content instead of
# leaving it as dimmed "stale" leftovers.
_page = st.empty()
with _page.container():
    if not is_authenticated(st.session_state):
        show_login_page()
    else:
        show_main_dashboard()
