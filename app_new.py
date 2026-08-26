"""
Ledgr Main Application
Entry point with authentication flow.
"""

import streamlit as st
from auth import is_authenticated, get_current_merchant, logout
from login import show_login_page

# Page config
st.set_page_config(
    page_title="Ledgr - AI Reconciliation",
    page_icon="📊",
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

    # Apply consistent theme
    st.markdown("""
        <style>
        /* Color theme - Purple gradient */
        :root {
            --primary-color: #667eea;
            --secondary-color: #764ba2;
            --background: #ffffff;
            --surface: #f8fafc;
            --text-primary: #1e293b;
            --text-secondary: #64748b;
            --border: #e2e8f0;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
        }

        /* Hide Streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stDeployButton {display: none;}

        /* Header bar */
        .header-bar {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px 40px;
            color: white;
            border-radius: 0;
            margin: -80px -80px 30px -80px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .header-left {
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .app-logo {
            font-size: 32px;
        }

        .app-title {
            font-size: 24px;
            font-weight: 700;
            margin: 0;
        }

        .company-info {
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .company-badge {
            background: rgba(255, 255, 255, 0.2);
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 600;
        }

        /* Card styling */
        .card {
            background: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border: 1px solid #e2e8f0;
            margin-bottom: 20px;
        }

        .card-header {
            font-size: 18px;
            font-weight: 600;
            color: #1e293b;
            margin-bottom: 16px;
        }

        /* Metric cards */
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }

        .metric-value {
            font-size: 36px;
            font-weight: 700;
            margin: 10px 0;
        }

        .metric-label {
            font-size: 14px;
            opacity: 0.9;
        }

        /* Buttons */
        .stButton > button {
            border-radius: 8px;
            font-weight: 600;
            transition: all 0.3s;
        }

        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }

        /* Status badges */
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }

        .status-connected {
            background: #d1fae5;
            color: #065f46;
        }

        .status-disconnected {
            background: #fee2e2;
            color: #991b1b;
        }
        </style>
    """, unsafe_allow_html=True)

    # Header
    st.markdown(f"""
        <div class="header-bar">
            <div class="header-left">
                <div class="app-logo">📊</div>
                <div class="app-title">Ledgr</div>
            </div>
            <div class="company-info">
                <div class="company-badge">{merchant['logo_emoji']} {merchant['company_name']}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Logout button in sidebar
    with st.sidebar:
        st.markdown("### Account")
        st.write(f"**{merchant['company_name']}**")
        st.write(f"📧 {merchant['email']}")
        st.write(f"🏢 {merchant['industry']}")
        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            logout(st.session_state)
            st.rerun()

    # Main content
    st.markdown("## 🎯 Dashboard")

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown("""
            <div class="metric-card">
                <div class="metric-label">Total Orders</div>
                <div class="metric-value">1,247</div>
            </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
            <div class="metric-card">
                <div class="metric-label">Auto-Cleared</div>
                <div class="metric-value">1,089</div>
            </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
            <div class="metric-card">
                <div class="metric-label">AI Resolved</div>
                <div class="metric-value">23</div>
            </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown("""
            <div class="metric-card">
                <div class="metric-label">Need Review</div>
                <div class="metric-value">5</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Integrations status
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
            <div class="card">
                <div class="card-header">🔗 Integrations</div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
            <div style="margin-bottom: 15px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong>Razorpay</strong><br>
                        <span style="font-size: 12px; color: #64748b;">{merchant['razorpay_key_id']}</span>
                    </div>
                    <span class="status-badge status-connected">✓ Connected</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
            <div style="margin-bottom: 15px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong>Shopify</strong><br>
                        <span style="font-size: 12px; color: #64748b;">{merchant['shopify_url']}</span>
                    </div>
                    <span class="status-badge status-connected">✓ Connected</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown("""
            <div class="card">
                <div class="card-header">🔄 Last Sync</div>
        """, unsafe_allow_html=True)

        st.markdown("""
            <div style="margin-bottom: 15px;">
                <div style="display: flex; justify-content: space-between;">
                    <span><strong>Orders</strong></span>
                    <span style="color: #64748b;">2 mins ago</span>
                </div>
            </div>
            <div style="margin-bottom: 15px;">
                <div style="display: flex; justify-content: space-between;">
                    <span><strong>Settlements</strong></span>
                    <span style="color: #64748b;">5 mins ago</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

        st.button("🔄 Sync Now", use_container_width=True, type="primary")

        st.markdown("</div>", unsafe_allow_html=True)

    # Quick actions
    st.markdown("## 🚀 Quick Actions")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("▶️ Run Reconciliation", use_container_width=True):
            st.info("🔄 Starting reconciliation...")

    with col2:
        if st.button("📊 View Reports", use_container_width=True):
            st.info("📈 Loading reports...")

    with col3:
        if st.button("⚙️ Settings", use_container_width=True):
            st.info("⚙️ Opening settings...")

    # Placeholder for future content
    st.markdown("---")
    st.info("💡 **Coming soon:** AI investigation dashboard, detailed reports, and more!")


# Main app logic
if not is_authenticated(st.session_state):
    show_login_page()
else:
    show_main_dashboard()
