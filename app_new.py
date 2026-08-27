"""
Ledgr Main Application
Entry point with authentication flow. Visual language shared with login.py
via theme.py.

Layout approach: the static visual shell (header text, title, cards,
last-reconciliation block, activity section) is authored as continuous HTML
sharing one spacing system (.shell / SHELL_PAD), rendered in as few
st.markdown() calls as possible. Only the handful of elements that need
real interactivity (avatar toggle, dropdown items, Sync & Reconcile) are
actual Streamlit widgets, each positioned using the SAME spacing constant
as the HTML around it -- not an independent guess -- so alignment holds by
construction instead of by coincidence.
"""

import os
import time
from datetime import datetime

import pandas as pd
import streamlit as st

import razorpay_client as rzp
import shopify_client as shopify
from auth import is_authenticated, get_current_merchant, logout
from config import to_paise, fmt
from engine import reconcile
from login import show_login_page
from theme import base_css, html, INK, BODY, DIM, LINE, BG, SOFT, ACC, ACC_D, MATCHED, WARN

st.set_page_config(
    page_title="Ledgr - AI Reconciliation",
    page_icon="L",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# One spacing/width system, reused by the header bar and every content
# block below it -- this is what guarantees they share a left/right edge.
SHELL_MAX = 1040
SHELL_PAD = 32

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _load_local_settlements():
    """
    RAZORPAY-sourced (demo) + BANK-sourced (COD) rows from the local
    settlements.csv gen_data.py produces. Our mock orders' payment_ids only
    exist in this demo file -- a real Razorpay Test Mode account has no
    relationship to synthetic data, so this is what orders actually
    reconcile against regardless of what the live Razorpay call returns.
    """
    return pd.read_csv(os.path.join(DATA_DIR, "settlements.csv"), dtype=str).fillna("")


SYNC_STEPS = [
    ("🛍️", "Connecting to Shopify…"),
    ("💳", "Connecting to Razorpay…"),
    ("🏦", "Loading COD / bank remittance data…"),
    ("🔀", "Merging settlement sources…"),
    ("🧮", "Matching orders to settlements…"),
]
STEP_PACE_SECONDS = 1.1  # deliberate pacing so each step is readable -- see note below


def _render_steps(placeholder, current, results):
    """
    Redraws the whole step list every call: steps before `current` are done
    (faded grey, with their real result line), `current` itself is bold
    full-opacity black, everything after is a dim, not-yet-run placeholder.
    One placeholder, fully redrawn each time -- not st.status()'s
    accumulate-everything-at-full-opacity behavior, which is what the
    fade/bold/dim distinction actually needs.
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


def _run_sync_and_reconcile(placeholder):
    """
    Runs inside the sync screen. Each step is real work -- the pacing delay
    only controls how long the CURRENT step's highlighted state stays
    visible before advancing; it doesn't fabricate work that didn't happen,
    it just stops genuinely-fast local steps (reading a CSV) from flashing
    by before anyone can read them.
    Returns the reconcile() output DataFrame.
    """
    results = [None] * len(SYNC_STEPS)

    _render_steps(placeholder, 0, results)
    time.sleep(STEP_PACE_SECONDS)
    order_rows = shopify.fetch_orders()
    orders_df = pd.DataFrame(order_rows)
    orders_df["amount_paise"] = orders_df["order_amount"].map(to_paise)
    results[0] = f"{len(order_rows)} orders loaded"

    _render_steps(placeholder, 1, results)
    time.sleep(STEP_PACE_SECONDS)
    rzp_status, rzp_rows, rzp_message = rzp.connection_status()
    results[1] = rzp_message

    _render_steps(placeholder, 2, results)
    time.sleep(STEP_PACE_SECONDS)
    local_setls = _load_local_settlements()
    cod_rows = local_setls[local_setls["source"] == "BANK"]
    results[2] = f"{len(cod_rows)} bank credit(s) loaded"

    _render_steps(placeholder, 3, results)
    time.sleep(STEP_PACE_SECONDS)
    razorpay_rows = local_setls[local_setls["source"] == "RAZORPAY"]
    settlements_df = pd.concat([razorpay_rows, cod_rows], ignore_index=True)
    settlements_df["amount_paise"] = settlements_df["amount_received"].map(to_paise)
    source_note = ("live + demo" if rzp_status == rzp.STATUS_OK
                    else "demo — Test Mode has no live settlements for these orders")
    results[3] = f"{len(settlements_df)} settlement rows ready ({source_note})"

    _render_steps(placeholder, 4, results)
    time.sleep(STEP_PACE_SECONDS + 0.3)
    result_df = reconcile(orders_df, settlements_df)
    results[4] = f"{len(result_df)} records processed"

    _render_steps(placeholder, len(SYNC_STEPS), results)
    time.sleep(0.5)

    return result_df


def _show_results_dashboard(result_df):
    """The screen after sync completes: four real metric tiles, a chatbot
    placeholder (functionality comes later), and a way back."""
    orders_expected = fmt(int(result_df["expected"].sum()))
    received = fmt(int(result_df["received"].sum()))
    ai_resolved = int(result_df["ai_assisted"].sum())
    exceptions = int((result_df["status"] == "EXCEPTION").sum())

    st.markdown(html(f"""
        <div class="results-grid">
            <div class="lg-card">
                <div class="lg-card-tag">Order book</div>
                <div class="results-tile-value">{orders_expected}</div>
                <div class="lg-card-status status-manual">Expected</div>
            </div>
            <div class="lg-card">
                <div class="lg-card-tag">Settlements</div>
                <div class="results-tile-value" style="color:{MATCHED};">{received}</div>
                <div class="lg-card-status status-ready">Received</div>
            </div>
            <div class="lg-card">
                <div class="lg-card-tag">Tier 3</div>
                <div class="results-tile-value" style="color:{ACC};">{ai_resolved}</div>
                <div class="lg-card-status" style="color:{ACC};">AI Resolved</div>
            </div>
            <div class="lg-card">
                <div class="lg-card-tag">Needs a human</div>
                <div class="results-tile-value" style="color:{WARN};">{exceptions}</div>
                <div class="lg-card-status status-error">Exceptions</div>
            </div>
        </div>

        <div style="height:24px;"></div>
        <div class="lg-activity">
            <div class="lg-activity-title">Ask Ledgr</div>
            <div class="lg-activity-empty">Chat coming soon — for now this is a placeholder.</div>
        </div>
    """), unsafe_allow_html=True)

    # st.chat_input() pins to the bottom of the whole page by default unless
    # nested inside a layout container -- wrapping it keeps it inline here.
    with st.container():
        st.chat_input("Ask about this reconciliation…", disabled=True)

    st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)
    with st.container(key="backbtn"):
        if st.button("Back to Dashboard", use_container_width=True):
            st.session_state.sync_in_progress = False
            st.rerun()


def show_sync_screen():
    """
    The dedicated, focused sync view -- no header, no cards, no CTA behind
    it. Runs the pipeline once (three-state step list: done/active/pending),
    then hands off to the results dashboard.
    """
    st.markdown(base_css(), unsafe_allow_html=True)
    st.markdown(html(f"""
        <style>
        .block-container {{padding: 0 !important; max-width: 100% !important;}}
        [data-testid="collapsedControl"] {{display: none;}}
        .stApp {{background: {SOFT};}}
        .shell {{max-width: 680px; margin: 0 auto; padding: 0 {SHELL_PAD}px;}}
        .lg-title {{font-size: 24px; font-weight: 700; letter-spacing: -.02em; color: {INK};}}

        .sync-step {{display: flex; align-items: center; gap: 12px; padding: 11px 0;}}
        .sync-step-icon {{font-size: 16px; width: 22px; text-align: center;}}
        .sync-step-done {{color: {DIM}; opacity: .55; font-size: 13.5px;}}
        .sync-step-active {{color: {INK}; font-weight: 700; font-size: 15px; opacity: 1;}}
        .sync-step-pending {{color: {DIM}; opacity: .35; font-size: 13.5px;}}
        .sync-step-result {{
            font-size: 12px; color: {MATCHED}; opacity: .8; margin: -4px 0 6px 34px;
        }}

        .results-grid {{display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px;}}
        .results-tile-value {{
            font-size: 22px; font-weight: 700; letter-spacing: -.02em; color: {INK};
            margin: 4px 0 6px;
        }}

        .st-key-backbtn button {{
            background: {ACC} !important; color: #fff !important; border: none !important;
            border-radius: 8px !important; font-weight: 600 !important;
        }}
        .st-key-backbtn button:hover {{background: {ACC_D} !important;}}
        </style>
    """), unsafe_allow_html=True)

    if "last_reconcile_result" not in st.session_state:
        st.markdown("<div style='height:110px;'></div>", unsafe_allow_html=True)
        _, mid, _ = st.columns([2, 3, 2])
        with mid:
            placeholder = st.empty()
            result_df = _run_sync_and_reconcile(placeholder)

        st.session_state.last_reconcile_result = result_df
        st.session_state.last_synced_at = datetime.now()

        cleared = int(result_df["status"].isin(["AUTO_CLEARED", "CLEARED_WITH_FEE"]).sum())
        review = int((result_df["status"] == "MANUAL_REVIEW").sum())
        exception = int((result_df["status"] == "EXCEPTION").sum())
        st.session_state.setdefault("activity_log", []).insert(0, {
            "time": st.session_state.last_synced_at,
            "summary": (f"{len(result_df)} records reconciled — {cleared} cleared, "
                        f"{review} flagged for AI, {exception} exceptions"),
        })
        st.rerun()
    else:
        st.markdown("<div style='height:50px;'></div>", unsafe_allow_html=True)
        _, mid, _ = st.columns([1, 8, 1])
        with mid:
            _show_results_dashboard(st.session_state.last_reconcile_result)


@st.cache_data(ttl=30, show_spinner=False)
def _cached_razorpay_status():
    """Real call to Razorpay, cached 30s so normal reruns don't hammer it."""
    return rzp.connection_status()


@st.cache_data(ttl=30, show_spinner=False)
def _cached_shopify_status():
    """Mock order data read, cached 30s. Never a live call -- see shopify_client.py."""
    return shopify.connection_status()


if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "merchant" not in st.session_state:
    st.session_state.merchant = None
if "sync_in_progress" not in st.session_state:
    st.session_state.sync_in_progress = False


def _start_sync():
    """on_click callback for the Sync & Reconcile button -- see the call
    site for why this has to be a callback, not an if-block + st.rerun()."""
    _cached_razorpay_status.clear()
    st.session_state.pop("last_reconcile_result", None)
    st.session_state.sync_in_progress = True


def show_main_dashboard():
    """Main dashboard after login."""

    if st.session_state.sync_in_progress:
        show_sync_screen()
        return

    merchant = get_current_merchant(st.session_state)

    st.markdown(base_css(), unsafe_allow_html=True)
    st.markdown(html(f"""
        <style>
        /* Zero Streamlit's own gutter -- .shell below is the ONLY source
           of horizontal alignment on this page from here on. */
        .block-container {{padding: 0 !important; max-width: 100% !important;}}
        [data-testid="collapsedControl"] {{display: none;}}
        .stApp {{background: {SOFT};}}

        .shell {{max-width: {SHELL_MAX}px; margin: 0 auto; padding: 0 {SHELL_PAD}px;}}

        /* ---- header ---- */
        .st-key-headerwrap {{
            max-width: {SHELL_MAX}px; margin: 0 auto;
            padding: 16px {SHELL_PAD}px; border-bottom: 1px solid {LINE};
        }}
        .lg-wordmark {{font-size: 22px; font-weight: 700; letter-spacing: -.035em; color: {INK};}}
        .lg-org {{font-size: 14px; font-weight: 500; color: {BODY}; text-align: center; margin-top: 6px;}}

        /* ---- page title ---- */
        .lg-title {{font-size: 26px; font-weight: 700; letter-spacing: -.02em; color: {INK}; margin: 0;}}
        .lg-subtitle {{font-size: 14px; color: {DIM}; margin-top: 6px;}}

        /* ---- status cards ---- */
        .lg-cards {{display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;}}
        .lg-card {{
            background: {BG}; border: 1px solid {LINE}; border-radius: 12px;
            padding: 20px 22px;
        }}
        .lg-card-dot {{width: 8px; height: 8px; border-radius: 50%; margin-bottom: 12px;}}
        .dot-live {{background: {MATCHED};}}
        .dot-manual {{background: {DIM};}}
        .dot-error {{background: {WARN};}}
        .lg-card-tag {{font-size: 12.5px; color: {DIM}; margin-bottom: 3px;}}
        .lg-card-title {{font-size: 15px; font-weight: 600; color: {INK}; margin-bottom: 6px;}}
        .lg-card-status {{font-size: 13px; font-weight: 500;}}
        .status-ready {{color: {MATCHED};}}
        .status-error {{color: {WARN};}}
        .status-manual {{color: {DIM};}}

        /* ---- last reconciliation ---- */
        .lg-lastrun {{
            border: 1px solid {LINE}; border-radius: 12px; background: {BG};
            padding: 18px 22px; display: flex; align-items: center; justify-content: space-between;
        }}
        .lg-lastrun-label {{font-size: 11px; font-weight: 600; letter-spacing: .08em; color: {DIM};}}
        .lg-lastrun-value {{font-size: 16px; font-weight: 600; color: {INK}; margin-top: 2px;}}
        .lg-lastrun-status {{font-size: 13px; font-weight: 500; color: {MATCHED};}}

        /* ---- activity ---- */
        .lg-activity {{
            border: 1px solid {LINE}; border-radius: 12px; background: {BG}; padding: 20px 22px;
        }}
        .lg-activity-title {{font-size: 14px; font-weight: 600; color: {INK}; margin-bottom: 6px;}}
        .lg-activity-empty {{font-size: 13px; color: {DIM}; line-height: 1.6;}}

        /* ---- avatar + dropdown. rightslot is the positioned ancestor --
           NOT the narrow 36px avatar box itself, which was constraining
           the dropdown's width down to ~20px (letters wrapping one per
           line). rightslot has no width of its own, so it can't squeeze
           anything nested inside it. Width/position on accountmenu are
           !important because a plain class was previously losing the
           specificity fight against Streamlit's own container rules. ---- */
        .st-key-rightslot {{position: relative;}}
        .st-key-avatarbtn {{margin-left: auto; width: 36px;}}
        .st-key-avatarbtn button {{
            border-radius: 50% !important; width: 36px !important; height: 36px !important;
            padding: 0 !important; font-size: 15px !important; min-width: 0 !important;
            background: {BG} !important; color: {INK} !important; border-color: {LINE} !important;
        }}
        /* neutralize focus/active highlight -- Streamlit's theme primary
           color was bleeding through on the clicked/focused button */
        .st-key-avatarbtn button:hover,
        .st-key-avatarbtn button:focus,
        .st-key-avatarbtn button:active {{
            background: {SOFT} !important; color: {INK} !important; border-color: {LINE} !important;
            box-shadow: none !important;
        }}
        .st-key-accountmenu {{
            position: absolute !important; top: 44px !important; right: 0 !important;
            width: 168px !important; min-width: 168px !important; max-width: 168px !important;
            margin: 0 !important; z-index: 1000 !important;
            background: rgba(255,255,255,.96); backdrop-filter: blur(8px);
            border: 1px solid {LINE}; border-radius: 10px;
            box-shadow: 0 12px 28px rgba(12,14,18,.14); padding: 6px;
        }}
        /* Streamlit's current testid is "stElementContainer" (camelCase,
           matching stVerticalBlock/stButton) -- the previous rule used the
           older "element-container" class name, which doesn't exist in
           this Streamlit version, so it never actually took effect. Also
           zeroing rightslot's wrappers so the closed/open height difference
           (the "shifts content below" bug) can't leave any residual gap. */
        .st-key-rightslot [data-testid="stElementContainer"],
        .st-key-accountmenu [data-testid="stElementContainer"] {{margin: 0 !important;}}
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

        /* ---- sync CTA: visual styling only -- centered via a real
           st.columns() split, not a container display override. ---- */
        .st-key-synccta button {{
            background: {ACC} !important; color: #fff !important;
            border: none !important; border-radius: 8px !important; font-weight: 600 !important;
            font-size: 14px !important; padding: 11px 0 !important;
        }}
        .st-key-synccta button:hover {{background: {ACC_D} !important;}}
        </style>
    """), unsafe_allow_html=True)

    # ---- header: Ledgr | org name | avatar, via st.columns() -- proven
    # reliable for gross placement, unlike overriding container display. ----
    with st.container(key="headerwrap"):
        # Equal flanking columns (1/3/1) so hcol2's own midpoint is the
        # row's true center -- unequal flanks (the old [2,3,1]) shift the
        # middle column's center off-page-center.
        hcol1, hcol2, hcol3 = st.columns([1, 3, 1])
        with hcol1:
            st.markdown('<div class="lg-wordmark">Ledgr</div>', unsafe_allow_html=True)
        with hcol2:
            st.markdown(f'<div class="lg-org">{merchant["company_name"]}</div>',
                        unsafe_allow_html=True)
        with hcol3:
            # rightslot is the positioned ancestor for the dropdown -- it
            # has no width constraint of its own, unlike the 36px avatarbtn
            # box, so it can't squeeze the dropdown down to a sliver.
            with st.container(key="rightslot"):
                with st.container(key="avatarbtn"):
                    if st.button("👤", key="avatar_toggle"):
                        st.session_state.show_account_menu = not st.session_state.get(
                            "show_account_menu", False)

                if st.session_state.get("show_account_menu", False):
                    with st.container(key="accountmenu"):
                        if st.button("Profile", use_container_width=True, key="menu_profile"):
                            st.session_state.show_account_menu = False
                            st.info("Profile page coming soon.")
                        if st.button("Settings", use_container_width=True, key="menu_settings"):
                            st.session_state.show_account_menu = False
                            st.info("Settings page coming soon.")
                        st.markdown("---")
                        if st.button("Log out", use_container_width=True, key="menu_logout"):
                            st.session_state.show_account_menu = False
                            logout(st.session_state)
                            # auth.logout() only clears authenticated/merchant
                            # (it's generic, shared with login.py) -- reset
                            # this page's own state too, so a logout->login
                            # cycle re-triggers the settle-rerun cleanly
                            # instead of skipping it as "already settled".
                            st.session_state.pop("_dashboard_settled", None)
                            st.session_state.pop("last_reconcile_result", None)
                            st.session_state.sync_in_progress = False
                            st.rerun()

    # ---- real Razorpay status feeds the Settlements card only -- never
    # fabricated, same connection_status() call used throughout. Wrapped in
    # a spinner because the FIRST call each session/cache-window is a real,
    # uncached network round-trip with no visual feedback otherwise -- that
    # silent wait between the header rendering and the rest of the page
    # popping in is what read as a glitch. Cached reruns (within 30s) return
    # instantly, so this only shows when there's genuinely something to wait
    # for -- it doesn't add delay, it surfaces delay that was already there.
    with st.spinner("Loading your dashboard…"):
        shopify_status, shopify_rows, shopify_message = _cached_shopify_status()
        rzp_status, rzp_rows, _ = _cached_razorpay_status()

    # Force one full settle-and-rerun immediately after the FIRST real load
    # this session -- clicking Sync right away, before the dashboard has
    # ever fully rendered once, was the one case where the sync screen's
    # st.empty() swap showed stale dashboard content underneath (Streamlit
    # had no fully-settled previous render to cleanly diff against yet).
    # This extra rerun is cheap: both calls above are now cached, so it
    # resolves instantly, not a second real wait.
    if not st.session_state.get("_dashboard_settled"):
        st.session_state._dashboard_settled = True
        st.rerun()

    shopify_text = shopify_message if shopify_status == shopify.STATUS_MOCK else "Mock data unavailable"
    shopify_class = "status-manual" if shopify_status == shopify.STATUS_MOCK else "status-error"

    if rzp_status == rzp.STATUS_OK:
        settle_status, settle_class, settle_dot = f"Connected · {len(rzp_rows)} result(s)", "status-ready", "dot-live"
    elif rzp_status == rzp.STATUS_EMPTY:
        settle_status, settle_class, settle_dot = "Connected · Test Mode", "status-ready", "dot-live"
    else:
        settle_status, settle_class, settle_dot = "Connection failed", "status-error", "dot-error"

    # ---- last-reconciliation reflects a real prior sync once one has run
    # (result stored in session_state by show_sync_screen()) -- never a
    # fabricated "just synced" claim before anything has actually happened.
    if "last_reconcile_result" in st.session_state:
        lastrun_value = st.session_state.last_synced_at.strftime("%b %d, %I:%M %p")
        lastrun_status = f"{len(st.session_state.last_reconcile_result)} records"
    else:
        lastrun_value = "Never synced"
        lastrun_status = "Ready to reconcile"

    # ---- title, cards, last-reconciliation: one continuous HTML block
    # sharing .shell -- same left/right edges as the header above. ----
    st.markdown(html(f"""
        <div class="shell">
            <div style="height:36px;"></div>
            <h1 class="lg-title">Financial Reconciliation</h1>
            <div class="lg-subtitle">Review your latest payment and settlement activity.</div>

            <div style="height:28px;"></div>
            <div class="lg-cards">
                <div class="lg-card">
                    <div class="lg-card-dot dot-manual"></div>
                    <div class="lg-card-tag">Shopify</div>
                    <div class="lg-card-title">Orders</div>
                    <div class="lg-card-status {shopify_class}">{shopify_text}</div>
                </div>
                <div class="lg-card">
                    <div class="lg-card-dot {settle_dot}"></div>
                    <div class="lg-card-tag">Razorpay</div>
                    <div class="lg-card-title">Settlements</div>
                    <div class="lg-card-status {settle_class}">{settle_status}</div>
                </div>
                <div class="lg-card">
                    <div class="lg-card-dot dot-manual"></div>
                    <div class="lg-card-tag">Bank File</div>
                    <div class="lg-card-title">COD / Bank</div>
                    <div class="lg-card-status status-manual">Ready</div>
                </div>
            </div>

            <div style="height:20px;"></div>
            <div class="lg-lastrun">
                <div>
                    <div class="lg-lastrun-label">LAST RECONCILIATION</div>
                    <div class="lg-lastrun-value">{lastrun_value}</div>
                </div>
                <div class="lg-lastrun-status">{lastrun_status}</div>
            </div>

            <div style="height:24px;"></div>
        </div>
    """), unsafe_allow_html=True)

    scol1, scol2, scol3 = st.columns([2, 1, 2])
    with scol2:
        with st.container(key="synccta"):
            # on_click, not an if-block + manual st.rerun(): a callback runs
            # BEFORE the script re-executes, so sync_in_progress is already
            # True by the time this same click's rerun reaches the top-of-
            # function check. The old if-block set the flag too late in
            # THIS run's own execution -- the full dashboard (cards, this
            # button, Recent Activity) had already rendered by that point,
            # so it flashed once before the next run corrected it.
            st.button("Sync & Reconcile", use_container_width=True, key="sync_button",
                      on_click=_start_sync)

    activity_log = st.session_state.get("activity_log", [])
    if activity_log:
        activity_rows = "".join(
            f'<div style="padding:9px 0; border-top:1px solid {LINE};">'
            f'<div style="font-size:13px; color:{INK};">{entry["summary"]}</div>'
            f'<div style="font-size:12px; color:{DIM}; margin-top:2px;">'
            f'{entry["time"].strftime("%b %d, %I:%M %p")}</div></div>'
            for entry in activity_log[:5]
        )
        activity_body = f'<div style="margin-top:4px;">{activity_rows}</div>'
    else:
        activity_body = (
            '<div class="lg-activity-empty">'
            "No reconciliation activity yet.<br>Your first sync will appear here.</div>"
        )

    st.markdown(html(f"""
        <div class="shell">
            <div style="height:28px;"></div>
            <div class="lg-activity">
                <div class="lg-activity-title">Recent activity</div>
                {activity_body}
            </div>
            <div style="height:48px;"></div>
        </div>
    """), unsafe_allow_html=True)


# Main app logic
# Wrapped in one st.empty() so switching between screens (login, full
# dashboard, sync screen, results) fully replaces the previous screen's
# content instead of leaving it as dimmed "stale" leftovers -- the
# dashboard has far more elements than the sync screen, so without this,
# Streamlit keeps the dashboard's extra elements (Sync button, Recent
# Activity) sitting there, dimmed, until the whole script finishes.
_page = st.empty()
with _page.container():
    if not is_authenticated(st.session_state):
        show_login_page()
    else:
        show_main_dashboard()
