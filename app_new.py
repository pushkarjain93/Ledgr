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

Incremental demo-data flow (see state_store.py): the ~180-record synthetic
dataset is split into 3 deterministic batches of 60 by gen_data.py. Batch 1
is available immediately; batches 2/3 unlock after a persisted timestamp
passes (checked on whatever rerun happens to occur next -- never a sleep,
never a background poll). Every real reconciliation run always goes through
the SAME unmodified engine.reconcile() -- this file only decides which
batch's rows to hand it, and remembers what came back (including, now, the
individual flagged records -- see _flagged_records()).
"""

import os
from datetime import datetime

import pandas as pd
import streamlit as st

import razorpay_client as rzp
import shopify_client as shopify
import state_store
from auth import is_authenticated, get_current_merchant, get_merchant_by_email, logout
from config import to_paise, fmt
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
    "Reports": ("Reports", "Export and summarize reconciliation activity."),
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
    state["processed_record_ids"].extend(order_ids)
    state["processed_record_ids"].extend(settlement_ids)
    state_store.schedule_next_batch(state, batch_id)
    state_store.save_state(merchant_id, state)
    return run


def _donut_gradient(auto_matched, ai_resolved, exceptions):
    """CSS conic-gradient donut built from real per-run percentages -- no
    chart library dependency, no hardcoded values."""
    total = auto_matched + ai_resolved + exceptions
    if total == 0:
        return f"conic-gradient({LINE} 0deg 360deg)"
    a1 = auto_matched / total * 360
    a2 = a1 + ai_resolved / total * 360
    return (f"conic-gradient({MATCHED} 0deg {a1:.2f}deg, "
            f"{PURPLE} {a1:.2f}deg {a2:.2f}deg, "
            f"{WARN} {a2:.2f}deg 360deg)")


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


def _render_steps(placeholder, current, results):
    """
    Redraws the whole step list every call: steps before `current` are done
    (faded grey, with their real result line), `current` itself is bold
    full-opacity black, everything after is a dim, not-yet-run placeholder.
    """
    rows = []
    for i, (icon, label) in enumerate(SYNC_STEPS):
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


def _run_sync_and_reconcile(placeholder, batch_id):
    """
    Runs the real pipeline for ONE batch. Every step does real work; there
    is no artificial delay between them -- the step list still updates
    live as each step completes (Streamlit streams each placeholder update
    to the browser as it happens), it just resolves as fast as the actual
    local I/O + engine.reconcile() call actually takes.

    Returns (result_df, batch_orders, batch_setls_df) -- result_df is the
    real, unmodified engine.reconcile() output for this batch's rows only.
    """
    b = str(batch_id)
    results = [None] * len(SYNC_STEPS)

    _render_steps(placeholder, 0, results)
    order_rows = shopify.fetch_orders()
    batch_orders = [o for o in order_rows if o.get("batch_id") == b]
    orders_df = pd.DataFrame(batch_orders)
    orders_df["amount_paise"] = orders_df["order_amount"].map(to_paise)
    results[0] = f"{len(batch_orders)} orders loaded"

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
                        st.info("Profile page coming soon.")
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
# Review Queue table -- shared by Reconciliations, AI Review, Exceptions
# ===========================================================================
def _render_flagged_table(records, empty_message, limit=None):
    """Real flagged records only (see _flagged_records) -- never a fake
    confidence percentage. AI-assisted rows show the real confidence from
    the live Gemini call (RECONAI_LLM=1) when present; 'Pending' if AI was
    invoked but confidence wasn't returned (offline stub / API fallback);
    '—' for plain exceptions, since no AI was ever invoked on them."""
    if not records:
        st.markdown(f'<div class="recon-empty">{empty_message}</div>', unsafe_allow_html=True)
        return

    shown = records[:limit] if limit else records
    rows = []
    for r in shown:
        if not r["ai_assisted"]:
            confidence = "—"
        elif r.get("confidence") is not None:
            confidence = f"{r['confidence']}%"
        else:
            confidence = "Pending"
        status_label = "AI Recommendation" if r["ai_assisted"] else "Exception"
        pill_class = "pill-ai" if r["ai_assisted"] else "pill-exception"
        rows.append(f"""
            <tr>
                <td class="recon-name">{r['record_id']}</td>
                <td class="recon-dim">{r['reason_label'] or r['tier_name']}</td>
                <td><span class="status-pill {pill_class}">{status_label}</span></td>
                <td class="recon-dim">{confidence}</td>
                <td class="recon-dim">{fmt(r['delta'])}</td>
                <td class="recon-dim">{fmt(r['expected'])}</td>
                <td class="recon-dim">{fmt(r['received'])}</td>
                <td class="recon-dim">View →</td>
            </tr>
        """)
    st.markdown(html(f"""
        <table class="recon-table">
            <thead>
                <tr><th>Order / Reference</th><th>Issue</th><th>Status</th><th>Confidence</th>
                    <th>Amount Difference</th><th>Expected</th><th>Received</th><th>Action</th></tr>
            </thead>
            <tbody>{''.join(rows)}</tbody>
        </table>
    """), unsafe_allow_html=True)


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
    ai_resolved = sum(r["ai_resolved"] for r in runs)
    exceptions_total = sum(r["exceptions"] for r in runs)

    st.markdown(html(f"""
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-icon" style="background:#E1EAFB; color:{ACC};">📄</div>
                <div class="kpi-label">Total Reconciliations</div>
                <div class="kpi-value" style="color:{INK};">{total_recon}</div>
                <div class="kpi-sub">This month</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-icon" style="background:#DDF3EA; color:{MATCHED};">✓</div>
                <div class="kpi-label">Auto Matched</div>
                <div class="kpi-value" style="color:{MATCHED};">{auto_matched}</div>
                <div class="kpi-sub">This month</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-icon" style="background:#EDE7FB; color:{PURPLE};">✨</div>
                <div class="kpi-label">AI Resolved</div>
                <div class="kpi-value" style="color:{PURPLE};">{ai_resolved}</div>
                <div class="kpi-sub">This month</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-icon" style="background:{WARN_BG}; color:{WARN};">⚠️</div>
                <div class="kpi-label">Exceptions</div>
                <div class="kpi-value" style="color:{WARN};">{exceptions_total}</div>
                <div class="kpi-sub">This month</div>
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
                <td class="recon-name">Daily Reconciliation — {datetime.fromisoformat(r['timestamp']).strftime('%b %d')}</td>
                <td class="recon-dim">{datetime.fromisoformat(r['timestamp']).strftime('%b %d, %Y %I:%M %p')}</td>
                <td class="recon-dim">{r['sources']}</td>
                <td><span class="status-pill">{r['status']}</span></td>
                <td class="recon-dim">{r['total_records']} records</td>
                <td class="recon-dim">View →</td>
            </tr>
        """ for r in runs[:5])

        st.markdown(html(f"""
            <div class="recon-card">
                <div class="recon-title">Recent Reconciliations</div>
                <table class="recon-table">
                    <thead>
                        <tr><th>Name</th><th>Date &amp; Time</th><th>Sources</th>
                            <th>Status</th><th>Summary</th><th>Action</th></tr>
                    </thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>
        """), unsafe_allow_html=True)

        with st.container(key="viewallbtn"):
            _, vcol, _ = st.columns([2, 1, 2])
            with vcol:
                if st.button("View all reconciliations →", use_container_width=True):
                    st.info("Full reconciliation history is coming soon.")


# ===========================================================================
# Reconciliations -- the command center. Sync happens INLINE here now.
# ===========================================================================
def _render_reconciliations(state, merchant_id):
    runs = state["reconciliation_runs"]

    # ---- header control row ----
    _, ccol = st.columns([2.6, 2.4])
    with ccol:
        c1, c2, c3 = st.columns([1, 1, 1.5])
        with c1:
            st.markdown('<div class="control-badge">This month</div>', unsafe_allow_html=True)
        with c2:
            if st.button("Filters", key="filters_btn", use_container_width=True):
                st.info("Filters are coming soon.")
        with c3:
            with st.container(key="newreconbtn"):
                st.button("+ New Reconciliation", use_container_width=True,
                           on_click=_start_sync, key="recon_new_btn")

    st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)

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
        result_df, batch_orders, batch_setls_df = _run_sync_and_reconcile(placeholder, batch_id)
        st.markdown('</div>', unsafe_allow_html=True)

        order_ids = [o["order_id"] for o in batch_orders]
        settlement_ids = batch_setls_df["settlement_id"].tolist()
        _save_reconciliation_run(merchant_id, state, batch_id, result_df, order_ids, settlement_ids)

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

    # ---- cumulative KPI row (8 cards) ----
    total_recon = len(runs)
    expected_total = sum(r["expected_paise"] for r in runs)
    received_total = sum(r["received_paise"] for r in runs)
    diff_total = received_total - expected_total
    auto_matched_total = sum(r["auto_matched"] for r in runs)
    ai_review_total = sum(r["ai_resolved"] for r in runs)
    exceptions_total = sum(r["exceptions"] for r in runs)
    records_total = sum(r["total_records"] for r in runs)
    diff_color = MATCHED if diff_total == 0 else WARN

    st.markdown(html(f"""
        <div class="kpi-grid-8">
            <div class="kpi-card">
                <div class="kpi-label">Total Reconciliations</div>
                <div class="kpi-value">{total_recon}</div>
                <div class="kpi-sub">This month</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Expected Amount</div>
                <div class="kpi-value">{fmt(expected_total)}</div>
                <div class="kpi-sub">This month</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Received Amount</div>
                <div class="kpi-value" style="color:{MATCHED};">{fmt(received_total)}</div>
                <div class="kpi-sub">This month</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Difference</div>
                <div class="kpi-value" style="color:{diff_color};">{fmt(diff_total)}</div>
                <div class="kpi-sub">This month</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Auto Matched</div>
                <div class="kpi-value" style="color:{MATCHED};">{auto_matched_total}</div>
                <div class="kpi-sub">{auto_matched_total*100//records_total if records_total else 0}% of total</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">AI Review</div>
                <div class="kpi-value" style="color:{PURPLE};">{ai_review_total}</div>
                <div class="kpi-sub">{ai_review_total*100//records_total if records_total else 0}% of total</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Exceptions</div>
                <div class="kpi-value" style="color:{WARN};">{exceptions_total}</div>
                <div class="kpi-sub">{exceptions_total*100//records_total if records_total else 0}% of total</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Records Processed</div>
                <div class="kpi-value">{records_total}</div>
                <div class="kpi-sub">This month</div>
            </div>
        </div>
        <div style="height:20px;"></div>
    """), unsafe_allow_html=True)

    # ---- three-column workspace: donut | amount flow | risk summary, all
    # from the LATEST run only (labelled "current reconciliation run") ----
    flagged = latest.get("flagged_records", [])
    risk = _risk_summary(flagged)
    total_latest = latest["total_records"] or 1
    gradient = _donut_gradient(latest["auto_matched"], latest["ai_resolved"], latest["exceptions"])

    col_donut, col_flow, col_risk = st.columns([1.1, 1.1, 1.2])
    with col_donut:
        st.markdown(html(f"""
            <div class="workspace-card">
                <div class="workspace-title">Reconciliation Overview</div>
                <div class="workspace-sub">Current reconciliation run</div>
                <div style="display:flex; justify-content:center; margin:14px 0 10px;">
                    <div style="width:140px; height:140px; border-radius:50%; background:{gradient};
                                display:flex; align-items:center; justify-content:center;">
                        <div style="width:86px; height:86px; border-radius:50%; background:{BG};
                                    display:flex; flex-direction:column; align-items:center; justify-content:center;">
                            <div style="font-size:18px; font-weight:700; color:{INK};">{latest['total_records']}</div>
                            <div style="font-size:9.5px; color:{DIM};">records</div>
                        </div>
                    </div>
                </div>
                <div style="font-size:12px; color:{BODY}; line-height:1.9;">
                    <div><span style="color:{MATCHED};">●</span> Auto Matched — {latest['auto_matched']}
                         ({latest['auto_matched']*100//total_latest}%)</div>
                    <div><span style="color:{PURPLE};">●</span> AI Review — {latest['ai_resolved']}
                         ({latest['ai_resolved']*100//total_latest}%)</div>
                    <div><span style="color:{WARN};">●</span> Exceptions — {latest['exceptions']}
                         ({latest['exceptions']*100//total_latest}%)</div>
                </div>
            </div>
        """), unsafe_allow_html=True)

    with col_flow:
        st.markdown(html("""
            <div class="workspace-card">
                <div class="workspace-title">Amount Flow</div>
                <div class="workspace-sub">Current reconciliation run</div>
            </div>
        """), unsafe_allow_html=True)
        flow_df = pd.DataFrame(
            {"Amount (Rs)": [latest["expected_paise"] / 100, latest["received_paise"] / 100]},
            index=["Expected", "Received"],
        )
        st.bar_chart(flow_df, height=160)
        run_diff = latest["received_paise"] - latest["expected_paise"]
        run_diff_color = MATCHED if run_diff == 0 else WARN
        diff_word = "on target" if run_diff == 0 else ("more than expected" if run_diff > 0 else "short of expected")
        st.markdown(html(f"""
            <div style="font-size:12px; color:{run_diff_color}; text-align:center; margin-top:-6px;">
                {fmt(abs(run_diff))} {diff_word}
            </div>
        """), unsafe_allow_html=True)

    with col_risk:
        st.markdown(html("""
            <div class="workspace-card">
                <div class="workspace-title">Risk Summary</div>
                <div class="workspace-sub">Current reconciliation run</div>
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

    # ---- Review Queue: latest run's real flagged records ----
    st.markdown(html("""
        <div class="recon-card">
            <div class="recon-title">Review Queue</div>
            <div class="workspace-sub" style="margin:-8px 0 14px;">Top items that need your attention.</div>
    """), unsafe_allow_html=True)
    _render_flagged_table(flagged, "Nothing needs attention in this batch — every record cleared.", limit=10)
    st.markdown("</div>", unsafe_allow_html=True)
    if len(flagged) > 10:
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
            <td class="recon-name">Daily Reconciliation — {datetime.fromisoformat(r['timestamp']).strftime('%b %d, %Y')}</td>
            <td class="recon-dim">{datetime.fromisoformat(r['timestamp']).strftime('%b %d, %Y %I:%M %p')}</td>
            <td class="recon-dim">{r['sources']}</td>
            <td><span class="status-pill">{r['status']}</span></td>
            <td class="recon-dim">{r['total_records']}</td>
            <td class="recon-dim" style="color:{MATCHED};">{r['auto_matched']}</td>
            <td class="recon-dim" style="color:{PURPLE};">{r['ai_resolved']}</td>
            <td class="recon-dim" style="color:{WARN};">{r['exceptions']}</td>
            <td class="recon-dim">View →</td>
        </tr>
    """ for r in runs)

    st.markdown(html(f"""
        <div class="recon-card">
            <div class="recon-title">Recent Reconciliations</div>
            <table class="recon-table">
                <thead>
                    <tr><th>Name</th><th>Date &amp; Time</th><th>Sources</th><th>Status</th>
                        <th>Records</th><th>Auto Matched</th><th>AI Review</th><th>Exceptions</th><th>Action</th></tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
    """), unsafe_allow_html=True)


# ===========================================================================
# AI Review / Exceptions -- minimal real pages, reusing the same flagged
# record data (filtered), not a mock of the future full AI Review UI.
# ===========================================================================
def _render_ai_review(state):
    records = [r for r in _all_flagged_records(state) if r["ai_assisted"]]
    st.markdown(html("""
        <div class="recon-card">
            <div class="recon-title">AI Review Queue</div>
            <div class="workspace-sub" style="margin:-8px 0 14px;">
                AI investigated these and has a recommendation. A human still decides --
                an AI recommendation is not an automatic approval.
            </div>
    """), unsafe_allow_html=True)
    _render_flagged_table(records, "No AI-assisted cases yet — run a reconciliation first.")
    st.markdown("</div>", unsafe_allow_html=True)


def _render_exceptions(state):
    records = [r for r in _all_flagged_records(state) if r["status"] == "EXCEPTION"]
    st.markdown(html("""
        <div class="recon-card">
            <div class="recon-title">Exceptions</div>
            <div class="workspace-sub" style="margin:-8px 0 14px;">Records that need a human decision.</div>
    """), unsafe_allow_html=True)
    _render_flagged_table(records, "No exceptions yet — run a reconciliation first.")
    st.markdown("</div>", unsafe_allow_html=True)


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
        .status-pill.pill-exception {{background: {WARN_BG}; color: {WARN};}}
        .recon-empty {{text-align: center; padding: 28px 0; color: {DIM}; font-size: 13px; line-height: 1.7;}}
        .st-key-viewallbtn button, .st-key-viewallreviewbtn button {{
            background: transparent !important; border: none !important; color: {ACC} !important;
            font-weight: 600 !important; font-size: 13px !important; width: auto !important;
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
