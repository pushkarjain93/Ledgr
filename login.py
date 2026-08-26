"""
Ledgr Login Screen
Split-panel layout: brand story + live reconciliation preview on the left,
sign-in form on the right. Palette/typography shared with app.py via theme.py.
"""

import streamlit as st
from auth import authenticate, DEMO_MERCHANTS
from theme import base_css, html, INK, BODY, DIM, LINE, BG, SOFT, ACC, ACC_D


def show_login_page():
    """Display the login page, styled to match the rest of Ledgr."""

    st.markdown(base_css(), unsafe_allow_html=True)

    st.markdown(html(f"""
        <style>
        .stApp {{
            background:
                radial-gradient(1100px 550px at 10% -10%, rgba(26,86,219,.09), transparent 60%),
                radial-gradient(900px 500px at 100% 115%, rgba(105,65,198,.07), transparent 60%),
                {SOFT};
        }}

        /* the split card */
        [data-testid="stVerticalBlockBorderWrapper"] {{
            max-width: 900px;
            margin: 32px auto 0;
            padding: 0 !important;
            overflow: hidden;
            box-shadow: 0 24px 60px rgba(12,14,18,.10);
        }}
        [data-testid="stHorizontalBlock"] {{gap: 0 !important;}}
        [data-testid="column"], [data-testid="stColumn"] {{padding: 0 !important;}}

        /* left: brand panel */
        .st-key-brandpanel {{
            background: linear-gradient(155deg, {ACC} 0%, #15409E 55%, {ACC_D} 100%);
            padding: 46px 42px;
            min-height: 100%;
            position: relative;
            overflow: hidden;
        }}
        .st-key-brandpanel::before {{
            content: "";
            position: absolute; top: -35%; right: -15%;
            width: 320px; height: 320px; border-radius: 50%;
            background: radial-gradient(circle, rgba(255,255,255,.14), transparent 70%);
        }}
        .brand-wordmark {{
            font-size: 28px; font-weight: 700; letter-spacing: -.03em;
            color: #fff; margin: 0 0 20px; position: relative; z-index: 1;
        }}
        .brand-tag {{
            font-size: 20px; font-weight: 500; letter-spacing: -.01em;
            line-height: 1.4; color: #fff; margin: 0 0 30px; max-width: 300px;
            position: relative; z-index: 1;
        }}
        .preview-row {{
            display: flex; align-items: center; justify-content: space-between;
            background: rgba(255,255,255,.10); border: 1px solid rgba(255,255,255,.16);
            border-radius: 8px; padding: 11px 14px; margin-bottom: 8px;
            position: relative; z-index: 1;
        }}
        .pv-id {{font-size: 12px; color: rgba(255,255,255,.72); font-weight: 500;}}
        .pv-amt {{font-size: 13.5px; color: #fff; font-weight: 600; margin-top: 1px;}}
        .pv-pill {{font-size: 11px; font-weight: 600; padding: 3px 9px; border-radius: 999px; white-space: nowrap;}}
        .pv-ok {{background: rgba(16,185,129,.22); color: #6EE7B7;}}
        .pv-flag {{background: rgba(245,158,11,.22); color: #FCD34D;}}
        .brand-foot {{
            font-size: 12px; color: rgba(255,255,255,.65); margin-top: 26px;
            position: relative; z-index: 1;
        }}

        /* right: form panel */
        .st-key-formpanel {{background: {BG}; padding: 46px 42px;}}
        .login-heading {{font-size: 24px; font-weight: 600; letter-spacing: -.03em; color: {INK}; margin: 0 0 4px;}}
        .login-subheading {{font-size: 13px; color: {DIM}; margin-bottom: 26px;}}
        </style>
    """), unsafe_allow_html=True)

    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)

    with st.container(border=True):
        col_brand, col_form = st.columns([5, 6], gap="small")

        with col_brand:
            with st.container(key="brandpanel"):
                preview_rows = html(f"""
                    <div class="preview-row">
                        <div>
                            <div class="pv-id">Order #A182</div>
                            <div class="pv-amt">₹12,450</div>
                        </div>
                        <span class="pv-pill pv-ok">Matched</span>
                    </div>
                    <div class="preview-row">
                        <div>
                            <div class="pv-id">Order #A183</div>
                            <div class="pv-amt">₹8,200</div>
                        </div>
                        <span class="pv-pill pv-ok">Matched</span>
                    </div>
                    <div class="preview-row">
                        <div>
                            <div class="pv-id">Order #A184</div>
                            <div class="pv-amt">₹3,150 → ₹2,980</div>
                        </div>
                        <span class="pv-pill pv-flag">AI reviewing</span>
                    </div>
                """)

                st.markdown(html(f"""
                    <div class="brand-wordmark">Ledgr</div>
                    <div class="brand-tag">Financial reconciliation,
                        without the spreadsheet chaos.</div>
                    {preview_rows}
                    <div class="brand-foot">Built for merchants who demand precision</div>
                """), unsafe_allow_html=True)

        with col_form:
            with st.container(key="formpanel"):
                st.markdown(html(f"""
                    <div class="login-heading">Sign in</div>
                    <div class="login-subheading">Access your merchant dashboard</div>
                """), unsafe_allow_html=True)

                email = st.text_input(
                    "Email Address",
                    placeholder="demo@acmecorp.com",
                    key="login_email",
                )

                password = st.text_input(
                    "Password",
                    placeholder="Enter your password",
                    type="password",
                    key="login_password",
                )

                if st.button("Sign In", use_container_width=True, type="primary"):
                    if not email or not password:
                        st.error("Please enter both email and password.")
                    else:
                        success, merchant_data = authenticate(email, password)

                        if success:
                            st.session_state.authenticated = True
                            st.session_state.merchant = merchant_data
                            st.rerun()
                        else:
                            st.error("Invalid email or password. Try a demo account below.")

                # Built as one HTML string (not split across st.markdown calls) —
                # Streamlit renders each markdown call as an isolated fragment,
                # so a div opened in one call never wraps content from another.
                rows = []
                for i, (email_addr, merchant) in enumerate(DEMO_MERCHANTS.items()):
                    border_top = f"border-top:1px solid {LINE};" if i else ""
                    rows.append(html(f"""
                        <div style="display:flex; align-items:center; gap:12px;
                                    padding:9px 0; {border_top}">
                            <div style="font-size:18px;">{merchant['logo_emoji']}</div>
                            <div style="flex:1; min-width:0;">
                                <p style="font-size:13.5px; font-weight:600; color:{INK};
                                          margin:0;">{merchant['company_name']}</p>
                                <p style="font-size:12px; color:{DIM}; margin:1px 0 0 0;">
                                    {email_addr}</p>
                            </div>
                        </div>
                    """))

                st.markdown(html(f"""
                    <div style="border:1px solid {LINE}; border-radius:8px;
                                padding:16px 18px 6px; margin-top:22px; background:{SOFT};">
                        <div style="font-size:11px; font-weight:600; letter-spacing:.08em;
                                    text-transform:uppercase; color:{DIM}; margin-bottom:4px;">
                            Demo accounts &middot; password: demo123
                        </div>
                        {''.join(rows)}
                    </div>
                """), unsafe_allow_html=True)


if __name__ == "__main__":
    st.set_page_config(
        page_title="Ledgr - Login",
        page_icon="L",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    show_login_page()
