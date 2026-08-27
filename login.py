"""
Ledgr Login Screen
UI/UX only -- authentication logic, routing, and demo-account data are
untouched (still auth.authenticate() / auth.DEMO_MERCHANTS). Split-panel
layout: dark brand panel (always dark, independent of the toggle) + a
light/dark-toggle sign-in form with demo-account cards, centered as one
fixed-max-width card in the viewport rather than stretched edge-to-edge.
"""

import streamlit as st
from auth import authenticate, DEMO_MERCHANTS
from theme import base_css, html, INK, BODY, DIM, LINE, BG, SOFT, ACC, ACC_D

# Dark-navy brand panel palette -- fixed, does not respond to the toggle.
NAVY_BG = "#0B1230"
NAVY_BG_2 = "#0E1B45"

# Form-panel palettes -- these DO respond to the light/dark toggle. Scoped
# to login.py only; the rest of the app (dashboard, sync screen) is
# untouched by this and stays on the single light theme in theme.py.
FORM_LIGHT = dict(bg=BG, page=SOFT, text=INK, dim=DIM, border=LINE, card=BG)
FORM_DARK = dict(bg="#141B33", page="#0B1024", text="#F1F5F9", dim="#94A3B8",
                  border="#2A3457", card="#1A2340")

# Demo-account avatar accents -- purely decorative, cycled per merchant.
AVATAR_STYLES = [
    ("#6941C6", "#EDE7FB"),  # purple
    ("#0E7C5A", "#DDF3EA"),  # green
    ("#B45309", "#FDECD8"),  # amber
]

FEATURES = [
    ("🗄️", "Connect data sources", "Shopify, Razorpay, Bank & more", "#E1EAFB"),
    ("⚡", "Automated matching", "Smart rules + AI to match transactions", "#EDE7FB"),
    ("✨", "AI-assisted review", "Intelligent recommendations & insights", "#DDF3EA"),
    ("📊", "Real-time insights", "Track reconciliation health in real time", "#FDECD8"),
]


def show_login_page():
    """Display the login page, styled to match the rest of Ledgr."""

    st.session_state.setdefault("login_dark_mode", False)
    dark = st.session_state.login_dark_mode
    f = FORM_DARK if dark else FORM_LIGHT

    st.markdown(base_css(), unsafe_allow_html=True)

    st.markdown(html(f"""
        <style>
        /* Page: light neutral background, card centered both horizontally
           and vertically -- not stretched edge-to-edge. Scoped to
           .block-container only (our own content), not .stApp itself,
           so Streamlit's separate header/toolbar chrome is untouched. */
        .stApp {{background: {SOFT};}}
        .block-container {{
            padding: 24px !important; max-width: 100% !important;
            display: flex; align-items: center; justify-content: center;
            min-height: 100vh;
        }}

        [data-testid="stVerticalBlockBorderWrapper"] {{
            max-width: 1200px; width: 100%; min-height: 680px;
            margin: 0 auto; padding: 0 !important;
            overflow: hidden; border-radius: 16px !important;
            box-shadow: 0 20px 50px rgba(12,14,18,.12);
            border-color: {f['border']} !important;
        }}
        [data-testid="stHorizontalBlock"] {{gap: 0 !important;}}
        [data-testid="column"], [data-testid="stColumn"] {{padding: 0 !important;}}

        /* ---- left: brand panel, always dark navy regardless of toggle.
           The card above has an explicit min-height now (not a guess), so
           the wave texture below has a real, known box to sit inside. ---- */
        .st-key-brandpanel {{
            background: linear-gradient(165deg, {NAVY_BG} 0%, {NAVY_BG_2} 60%, {NAVY_BG} 100%);
            padding: 32px 34px; height: 100%; min-height: 680px;
            position: relative; overflow: hidden;
        }}
        .brand-logo {{display: flex; align-items: center; gap: 9px; margin-bottom: 22px; position: relative; z-index: 1;}}
        .brand-logo-mark {{
            width: 30px; height: 30px; border-radius: 8px;
            background: linear-gradient(135deg, {ACC}, #7C6CF0);
            display: flex; align-items: center; justify-content: center; font-size: 14px;
        }}
        .brand-logo-word {{font-size: 19px; font-weight: 700; color: #fff; letter-spacing: -.02em;}}
        .brand-heading {{
            font-size: 23px; font-weight: 700; line-height: 1.25; color: #fff;
            margin: 0 0 10px; max-width: 290px; position: relative; z-index: 1;
        }}
        .brand-sub {{
            font-size: 13px; color: rgba(255,255,255,.65); line-height: 1.55;
            max-width: 290px; margin-bottom: 22px; position: relative; z-index: 1;
        }}
        .feature-row {{display: flex; gap: 11px; margin-bottom: 13px; position: relative; z-index: 1;}}
        .feature-icon {{
            width: 30px; height: 30px; border-radius: 8px; flex: none;
            display: flex; align-items: center; justify-content: center; font-size: 13px;
        }}
        .feature-title {{font-size: 13px; font-weight: 600; color: #fff;}}
        .feature-desc {{font-size: 11.5px; color: rgba(255,255,255,.55); margin-top: 1px;}}

        /* Wave texture: fixed pixel height (not a percentage or a
           non-uniform "none" stretch, both of which caused clipping/
           distortion last time), aspect-ratio preserved and cropped
           ("slice") to its own box rather than stretched -- so it can't
           visually overrun the panel regardless of exact content height
           above it. Low opacity, bottom-anchored, purely decorative. */
        .brand-wave {{
            position: absolute; left: 0; right: 0; bottom: 0; height: 170px;
            z-index: 0; opacity: .5; pointer-events: none;
        }}

        /* ---- right: form panel, responds to the toggle. Only the toggle
           row spans the full panel width (so it hugs the true top-right
           corner) -- everything else lives inside .st-key-forminner,
           a narrower centered block (see below). ---- */
        .st-key-formpanel {{background: {f['bg']}; padding: 20px 30px 24px; position: relative;}}
        .st-key-forminner {{max-width: 480px; margin: 0 auto;}}
        .login-heading {{font-size: 22px; font-weight: 700; letter-spacing: -.02em; color: {f['text']}; margin: 0 0 3px; text-align: center;}}
        .login-subheading {{font-size: 12.5px; color: {f['dim']}; margin-bottom: 16px; text-align: center;}}

        .st-key-formpanel .stTextInput input {{
            background: {f['bg']} !important; color: {f['text']} !important;
            border-color: {f['border']} !important; padding: 9px 12px !important;
        }}
        .st-key-formpanel .stTextInput label {{color: {f['text']} !important; font-size: 13px !important;}}
        .st-key-formpanel .stCheckbox label p {{color: {f['dim']} !important; font-size: 12.5px !important;}}

        /* Tighten the default gap Streamlit puts between stacked widgets --
           stElementContainer is the current camelCase testid (matching
           stVerticalBlock/stButton); an older "element-container" class
           name here would silently match nothing. */
        .st-key-signincard [data-testid="stElementContainer"] {{margin-bottom: 6px !important;}}
        .st-key-signincard {{padding: 18px 20px !important;}}

        .st-key-themetoggle button {{
            background: transparent !important; border: none !important; color: {f['dim']} !important;
            font-size: 12.5px !important; padding: 4px 0 !important;
            box-shadow: none !important; float: right;
        }}
        .st-key-themetoggle button:hover {{color: {f['text']} !important;}}

        /* sign-in fields sit in their own bordered card -- a real
           st.container(border=True), separate from the heading above and
           the demo accounts below (the div-across-markdown-calls trick
           can't wrap real widgets, so this has to be a genuine container). */
        .st-key-signincard {{background: {f['card']}; border-color: {f['border']} !important;}}
        .forgot-link {{
            float: right; font-size: 12.5px; color: {ACC}; text-decoration: none;
            position: relative; top: 30px; z-index: 2;
        }}

        .demo-divider {{
            text-align: center; font-size: 10.5px; font-weight: 600; letter-spacing: .07em;
            color: {f['dim']}; text-transform: uppercase; margin: 14px 0 9px;
        }}
        .demo-grid {{display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;}}
        .demo-card {{
            border: 1px solid {f['border']}; border-radius: 9px; background: {f['card']};
            padding: 9px 10px;
        }}
        .demo-avatar {{
            width: 22px; height: 22px; border-radius: 50%; display: flex; align-items: center;
            justify-content: center; font-size: 11px; margin-bottom: 6px;
        }}
        .demo-name {{font-size: 11.5px; font-weight: 600; color: {f['text']}; margin-bottom: 3px;}}
        .demo-line {{font-size: 10px; color: {f['dim']}; line-height: 1.4;}}
        .demo-value {{color: {ACC}; font-weight: 500;}}

        .login-footer {{text-align: center; font-size: 10.5px; color: {f['dim']}; margin-top: 12px; line-height: 1.5;}}
        .login-footer a {{color: {ACC};}}
        </style>
    """), unsafe_allow_html=True)

    with st.container(border=True):
        col_brand, col_form = st.columns([5, 6], gap="small")

        with col_brand:
            with st.container(key="brandpanel"):
                feature_rows = "".join(html(f"""
                    <div class="feature-row">
                        <div class="feature-icon" style="background:{icon_bg};">{icon}</div>
                        <div>
                            <div class="feature-title">{title}</div>
                            <div class="feature-desc">{desc}</div>
                        </div>
                    </div>
                """) for icon, title, desc, icon_bg in FEATURES)

                st.markdown(html(f"""
                    <div class="brand-logo">
                        <div class="brand-logo-mark">⬡</div>
                        <div class="brand-logo-word">Ledgr</div>
                    </div>
                    <div class="brand-heading">AI-Powered Financial Reconciliation</div>
                    <div class="brand-sub">
                        Reconcile orders, settlements and payments automatically.
                        Investigate exceptions with AI intelligence.
                    </div>
                    {feature_rows}
                """), unsafe_allow_html=True)

                # Fixed-height, aspect-preserved, cropped-to-box -- can't
                # overrun the panel the way the earlier "none" stretch did.
                st.markdown(html("""
                    <svg class="brand-wave" viewBox="0 0 400 220" preserveAspectRatio="xMidYMax slice">
                        <path d="M0,140 C60,100 100,160 160,130 C220,100 260,150 320,125
                                 C350,112 380,135 400,120 L400,220 L0,220 Z"
                              fill="url(#wg1)"/>
                        <path d="M0,165 C70,140 120,180 180,155 C240,130 280,170 340,150
                                 C365,140 385,155 400,148 L400,220 L0,220 Z"
                              fill="url(#wg2)"/>
                        <circle cx="70" cy="118" r="1.6" fill="#8FA6FF" opacity=".8"/>
                        <circle cx="210" cy="98" r="1.4" fill="#B9A8FF" opacity=".7"/>
                        <circle cx="330" cy="112" r="1.6" fill="#8FA6FF" opacity=".8"/>
                        <circle cx="150" cy="150" r="1.2" fill="#B9A8FF" opacity=".6"/>
                        <defs>
                            <linearGradient id="wg1" x1="0" y1="0" x2="1" y2="0">
                                <stop offset="0%" stop-color="#3B4CCA" stop-opacity=".5"/>
                                <stop offset="100%" stop-color="#7C6CF0" stop-opacity=".35"/>
                            </linearGradient>
                            <linearGradient id="wg2" x1="0" y1="0" x2="1" y2="0">
                                <stop offset="0%" stop-color="#5B6EE8" stop-opacity=".4"/>
                                <stop offset="100%" stop-color="#9B8CF5" stop-opacity=".25"/>
                            </linearGradient>
                        </defs>
                    </svg>
                """), unsafe_allow_html=True)

        with col_form:
            with st.container(key="formpanel"):
                # Only the toggle spans the full panel width, so it hugs the
                # true top-right corner of the card. Everything else below
                # lives inside forminner, a narrower centered block (480px
                # max) -- the form should not span the whole panel.
                with st.container(key="themetoggle"):
                    toggle_label = "☀️ Light mode" if dark else "🌙 Dark mode"
                    tcol1, tcol2 = st.columns([6, 1])
                    with tcol2:
                        if st.button(toggle_label, key="theme_toggle_btn"):
                            st.session_state.login_dark_mode = not dark
                            st.rerun()

                with st.container(key="forminner"):
                    st.markdown(html("""
                        <div class="login-heading">Welcome back</div>
                        <div class="login-subheading">Sign in to your Ledgr account</div>
                    """), unsafe_allow_html=True)

                    # sign-in fields sit in their own bordered card -- a real
                    # st.container(border=True), separate from the heading
                    # above and the demo accounts below.
                    with st.container(key="signincard", border=True):
                        email = st.text_input("Email", placeholder="Enter your email", key="login_email")
                        st.markdown('<a class="forgot-link" href="#">Forgot password?</a>',
                                    unsafe_allow_html=True)
                        password = st.text_input("Password", placeholder="Enter your password",
                                                  type="password", key="login_password")
                        st.checkbox("Remember me", value=True, key="login_remember")

                        if st.button("Sign In", use_container_width=True, type="primary"):
                            if not email or not password:
                                st.error("Please enter both email and password.")
                            else:
                                with st.spinner("Signing in…"):
                                    success, merchant_data = authenticate(email, password)

                                if success:
                                    st.session_state.authenticated = True
                                    st.session_state.merchant = merchant_data
                                    # Persisted in the URL (not just
                                    # session_state) so a browser refresh
                                    # can restore the session instead of
                                    # bouncing back to this login page --
                                    # see app_new.py's restore-from-
                                    # query-params check at startup.
                                    st.query_params["m"] = merchant_data["email"]
                                    st.rerun()
                                else:
                                    st.error("Invalid email or password. Try a demo account below.")

                    st.markdown('<div class="demo-divider">Or use a demo account</div>',
                                unsafe_allow_html=True)

                    # 3 of our 4 real merchants, single row -- not a switch to
                    # role-based identities, which would be a different
                    # account model (users within one company) than our
                    # current multi-tenant one (different companies). Auth
                    # logic itself (authenticate / DEMO_MERCHANTS) untouched.
                    demo_subset = list(DEMO_MERCHANTS.items())[:3]
                    cards = []
                    for i, (email_addr, merchant) in enumerate(demo_subset):
                        fg, bg = AVATAR_STYLES[i % len(AVATAR_STYLES)]
                        cards.append(html(f"""
                            <div class="demo-card">
                                <div class="demo-avatar" style="background:{bg}; color:{fg};">
                                    {merchant['logo_emoji']}
                                </div>
                                <div class="demo-name">{merchant['company_name']}</div>
                                <div class="demo-line">Email: <span class="demo-value">{email_addr}</span></div>
                                <div class="demo-line">Password: <span class="demo-value">demo123</span></div>
                            </div>
                        """))

                    st.markdown(html(f'<div class="demo-grid">{"".join(cards)}</div>'),
                                unsafe_allow_html=True)

                    st.markdown(html("""
                        <div class="login-footer">
                            By continuing, you agree to Ledgr's<br>
                            <a href="#">Terms of Service</a> and <a href="#">Privacy Policy</a>
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
