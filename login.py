"""
Ledgr Login Screen
Modern, clean authentication interface with consistent branding.
"""

import streamlit as st
from auth import authenticate, DEMO_MERCHANTS


def show_login_page():
    """Display the login page with modern design."""

    # Custom CSS for login page
    st.markdown("""
        <style>
        /* Hide Streamlit default elements */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stDeployButton {display: none;}
        header {visibility: hidden;}

        /* Main container styling */
        .main {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 0;
        }

        /* Login card */
        .login-card {
            background: white;
            border-radius: 20px;
            padding: 50px 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 450px;
            margin: 0 auto;
        }

        /* Logo and header */
        .login-header {
            text-align: center;
            margin-bottom: 40px;
        }

        .logo {
            font-size: 48px;
            margin-bottom: 10px;
        }

        .app-name {
            font-size: 36px;
            font-weight: 700;
            color: #1e293b;
            margin: 0;
            letter-spacing: -1px;
        }

        .app-tagline {
            font-size: 14px;
            color: #64748b;
            margin-top: 5px;
        }

        /* Input fields */
        .stTextInput > div > div > input {
            border-radius: 10px;
            border: 2px solid #e2e8f0;
            padding: 12px 16px;
            font-size: 15px;
            transition: all 0.3s;
        }

        .stTextInput > div > div > input:focus {
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }

        /* Login button */
        .stButton > button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            padding: 14px 24px;
            font-size: 16px;
            font-weight: 600;
            width: 100%;
            transition: all 0.3s;
            cursor: pointer;
        }

        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(102, 126, 234, 0.4);
        }

        /* Demo accounts section */
        .demo-accounts {
            background: #f8fafc;
            border-radius: 12px;
            padding: 20px;
            margin-top: 30px;
        }

        .demo-title {
            font-size: 14px;
            font-weight: 600;
            color: #475569;
            margin-bottom: 12px;
            text-align: center;
        }

        .demo-account {
            background: white;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            border: 1px solid #e2e8f0;
            transition: all 0.2s;
        }

        .demo-account:hover {
            border-color: #667eea;
            transform: translateX(5px);
        }

        .demo-emoji {
            font-size: 24px;
            margin-right: 12px;
        }

        .demo-info {
            flex: 1;
        }

        .demo-company {
            font-size: 14px;
            font-weight: 600;
            color: #1e293b;
            margin: 0;
        }

        .demo-email {
            font-size: 12px;
            color: #64748b;
            margin: 2px 0 0 0;
            font-family: 'Courier New', monospace;
        }

        /* Footer */
        .login-footer {
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e2e8f0;
        }

        .footer-text {
            font-size: 12px;
            color: #94a3b8;
        }

        .razorpay-badge {
            display: inline-block;
            background: #0c2f54;
            color: white;
            padding: 4px 12px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
            margin-top: 8px;
        }

        /* Alert styling */
        .stAlert {
            border-radius: 10px;
            border: none;
            margin-bottom: 20px;
        }
        </style>
    """, unsafe_allow_html=True)

    # Center the login form
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("<div style='height: 60px;'></div>", unsafe_allow_html=True)

        # Login card container
        st.markdown('<div class="login-card">', unsafe_allow_html=True)

        # Header
        st.markdown("""
            <div class="login-header">
                <div class="logo">📊</div>
                <h1 class="app-name">Ledgr</h1>
                <p class="app-tagline">AI-Powered Reconciliation Platform</p>
            </div>
        """, unsafe_allow_html=True)

        # Login form
        email = st.text_input(
            "Email Address",
            placeholder="demo@acmecorp.com",
            key="login_email",
            label_visibility="visible"
        )

        password = st.text_input(
            "Password",
            placeholder="Enter your password",
            type="password",
            key="login_password",
            label_visibility="visible"
        )

        # Login button
        if st.button("Sign In", use_container_width=True, type="primary"):
            if not email or not password:
                st.error("⚠️ Please enter both email and password")
            else:
                success, merchant_data = authenticate(email, password)

                if success:
                    # Set session state
                    st.session_state.authenticated = True
                    st.session_state.merchant = merchant_data
                    st.success(f"✅ Welcome back, {merchant_data['company_name']}!")
                    st.rerun()
                else:
                    st.error("❌ Invalid email or password. Try a demo account below.")

        # Demo accounts section
        st.markdown("""
            <div class="demo-accounts">
                <div class="demo-title">🎯 Demo Accounts (Password: demo123)</div>
        """, unsafe_allow_html=True)

        for email_addr, merchant in DEMO_MERCHANTS.items():
            st.markdown(f"""
                <div class="demo-account">
                    <div class="demo-emoji">{merchant['logo_emoji']}</div>
                    <div class="demo-info">
                        <p class="demo-company">{merchant['company_name']}</p>
                        <p class="demo-email">{email_addr}</p>
                    </div>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

        # Footer
        st.markdown("""
            <div class="login-footer">
                <p class="footer-text">Built for merchants who demand precision</p>
                <div class="razorpay-badge">🏆 Razorpay Buildathon 2026</div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    st.set_page_config(
        page_title="Ledgr - Login",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    show_login_page()
