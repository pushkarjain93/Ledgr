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

import streamlit as st

import razorpay_client as rzp
from auth import is_authenticated, get_current_merchant, logout
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


@st.cache_data(ttl=30, show_spinner=False)
def _cached_razorpay_status():
    """Real call to Razorpay, cached 30s so normal reruns don't hammer it."""
    return rzp.connection_status()


if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "merchant" not in st.session_state:
    st.session_state.merchant = None


def show_main_dashboard():
    """Main dashboard after login."""

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
                            st.rerun()

    # ---- real Razorpay status feeds the Settlements card only -- never
    # fabricated, same connection_status() call used throughout. ----
    rzp_status, rzp_rows, _ = _cached_razorpay_status()
    if rzp_status == rzp.STATUS_OK:
        settle_status, settle_class, settle_dot = f"Connected · {len(rzp_rows)} result(s)", "status-ready", "dot-live"
    elif rzp_status == rzp.STATUS_EMPTY:
        settle_status, settle_class, settle_dot = "Connected · Test Mode", "status-ready", "dot-live"
    else:
        settle_status, settle_class, settle_dot = "Connection failed", "status-error", "dot-error"

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
                    <div class="lg-card-dot dot-live"></div>
                    <div class="lg-card-tag">Shopify</div>
                    <div class="lg-card-title">Orders</div>
                    <div class="lg-card-status status-ready">Ready</div>
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
                    <div class="lg-card-status status-ready">Ready</div>
                </div>
            </div>

            <div style="height:20px;"></div>
            <div class="lg-lastrun">
                <div>
                    <div class="lg-lastrun-label">LAST RECONCILIATION</div>
                    <div class="lg-lastrun-value">Never synced</div>
                </div>
                <div class="lg-lastrun-status">Ready to reconcile</div>
            </div>

            <div style="height:24px;"></div>
        </div>
    """), unsafe_allow_html=True)

    scol1, scol2, scol3 = st.columns([2, 1, 2])
    with scol2:
        with st.container(key="synccta"):
            if st.button("Sync & Reconcile", use_container_width=True, key="sync_button"):
                _cached_razorpay_status.clear()
                st.toast("Starting sync… (progress screen coming soon)")
                st.rerun()

    st.markdown(html("""
        <div class="shell">
            <div style="height:28px;"></div>
            <div class="lg-activity">
                <div class="lg-activity-title">Recent activity</div>
                <div class="lg-activity-empty">
                    No reconciliation activity yet.<br>Your first sync will appear here.
                </div>
            </div>
            <div style="height:48px;"></div>
        </div>
    """), unsafe_allow_html=True)


# Main app logic
if not is_authenticated(st.session_state):
    show_login_page()
else:
    show_main_dashboard()
