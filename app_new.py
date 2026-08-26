"""
Ledgr Main Application
Entry point with authentication flow. Visual language shared with login.py
via theme.py.
"""

import streamlit as st
from auth import is_authenticated, get_current_merchant, logout
from login import show_login_page
from theme import base_css, html, INK, BODY, DIM, LINE, SOFT, MATCHED, WARN, WARN_BG, WARN_BD

# Page config
st.set_page_config(
    page_title="Ledgr - AI Reconciliation",
    page_icon="L",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize session state
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
        .block-container {{padding: 1.5rem 3rem 4rem; max-width: 1240px;}}

        .header-wordmark {{
            font-size: 25px; font-weight: 600; letter-spacing: -.035em; color: {INK};
        }}
        .company-badge {{
            display: inline-flex; align-items: center; gap: 8px;
            background: {SOFT}; border: 1px solid {LINE}; padding: 6px 14px;
            border-radius: 999px; font-size: 13px; font-weight: 500; color: {BODY};
        }}
        .metric-card {{
            background: #fff; border: 1px solid {LINE}; border-radius: 8px;
            padding: 18px 20px;
        }}
        .metric-value {{
            font-size: 32px; font-weight: 600; letter-spacing: -.03em;
            color: {INK}; line-height: 1.15; margin: 6px 0 2px;
        }}
        .metric-label {{
            font-size: 11px; font-weight: 600; letter-spacing: .06em;
            text-transform: uppercase; color: {DIM};
        }}
        .status-badge {{
            display: inline-flex; align-items: center; border-radius: 999px;
            padding: 3px 10px; font-size: 11px; font-weight: 500;
        }}
        .status-connected {{background: #E7F5EF; color: {MATCHED};}}
        .status-disconnected {{background: {WARN_BG}; color: {WARN}; border: 1px solid {WARN_BD};}}
        .sec {{
            font-size: 11.5px; font-weight: 600; letter-spacing: .1em;
            text-transform: uppercase; color: {DIM}; margin: 40px 0 16px;
        }}
        </style>
    """), unsafe_allow_html=True)

    # Header
    with st.container(border=True):
        hcol1, hcol2 = st.columns([3, 2])
        with hcol1:
            st.markdown('<div class="header-wordmark">Ledgr</div>', unsafe_allow_html=True)
        with hcol2:
            st.markdown(
                f'<div style="text-align:right;">'
                f'<span class="company-badge">{merchant["logo_emoji"]} '
                f'{merchant["company_name"]}</span></div>',
                unsafe_allow_html=True,
            )

    # Logout button in sidebar
    with st.sidebar:
        st.markdown("### Account")
        st.write(f"**{merchant['company_name']}**")
        st.write(f"{merchant['email']}")
        st.write(f"{merchant['industry']}")
        st.markdown("---")
        if st.button("Logout", use_container_width=True):
            logout(st.session_state)
            st.rerun()

    # Main content
    st.markdown("## Dashboard")

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)

    metrics = [
        ("Total Orders", "1,247"),
        ("Auto-Cleared", "1,089"),
        ("AI Resolved", "23"),
        ("Need Review", "5"),
    ]
    for col, (label, value) in zip((col1, col2, col3, col4), metrics):
        with col:
            st.markdown(html(f"""
                <div class="metric-card">
                    <div class="metric-label">{label}</div>
                    <div class="metric-value">{value}</div>
                </div>
            """), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Integrations status + Last Sync — built with st.container(border=True)
    # so the "Sync Now" button actually nests inside the card. (The previous
    # version opened a <div class="card"> in one st.markdown call and closed
    # it in another; Streamlit renders each markdown call as its own isolated
    # HTML fragment, so that div never wrapped anything — no border ever
    # showed up.)
    col1, col2 = st.columns(2)

    with col1:
        with st.container(border=True):
            st.markdown('<div style="font-size:15px; font-weight:600; '
                        f'color:{INK}; margin-bottom:16px;">Integrations</div>',
                        unsafe_allow_html=True)

            st.markdown(html(f"""
                <div style="margin-bottom:15px; display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <strong style="font-size:13.5px;">Razorpay</strong><br>
                        <span style="font-size:12px; color:{DIM};">{merchant['razorpay_key_id']}</span>
                    </div>
                    <span class="status-badge status-connected">Connected</span>
                </div>
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <strong style="font-size:13.5px;">Shopify</strong><br>
                        <span style="font-size:12px; color:{DIM};">{merchant['shopify_url']}</span>
                    </div>
                    <span class="status-badge status-connected">Connected</span>
                </div>
            """), unsafe_allow_html=True)

    with col2:
        with st.container(border=True):
            st.markdown('<div style="font-size:15px; font-weight:600; '
                        f'color:{INK}; margin-bottom:16px;">Last Sync</div>',
                        unsafe_allow_html=True)

            st.markdown(html(f"""
                <div style="margin-bottom:12px; display:flex; justify-content:space-between;">
                    <span style="font-size:13.5px;"><strong>Orders</strong></span>
                    <span style="color:{DIM}; font-size:13px;">2 mins ago</span>
                </div>
                <div style="margin-bottom:15px; display:flex; justify-content:space-between;">
                    <span style="font-size:13.5px;"><strong>Settlements</strong></span>
                    <span style="color:{DIM}; font-size:13px;">5 mins ago</span>
                </div>
            """), unsafe_allow_html=True)

            st.button("Sync Now", use_container_width=True, type="primary")

    # Quick actions
    st.markdown('<div class="sec">Quick actions</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Run Reconciliation", use_container_width=True):
            st.info("Starting reconciliation...")

    with col2:
        if st.button("View Reports", use_container_width=True):
            st.info("Loading reports...")

    with col3:
        if st.button("Settings", use_container_width=True):
            st.info("Opening settings...")

    # Placeholder for future content
    st.markdown("---")
    st.info("**Coming soon:** AI investigation dashboard, detailed reports, and more.")


# Main app logic
if not is_authenticated(st.session_state):
    show_login_page()
else:
    show_main_dashboard()
