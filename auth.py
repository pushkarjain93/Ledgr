"""
Authentication module for Ledgr.
Handles login, session management, and demo merchant accounts.
"""

# Demo merchant accounts for buildathon
DEMO_MERCHANTS = {
    "demo@acmecorp.com": {
        "password": "demo123",
        "company_name": "Acme Corporation",
        "merchant_id": "merchant_acme_001",
        "razorpay_key_id": "rzp_test_acme123",
        "razorpay_key_secret": "secret_acme_xyz789",
        "shopify_url": "acme-store.myshopify.com",
        "industry": "Electronics & Gadgets",
        "logo_emoji": "⚡"
    },
    "demo@betastore.com": {
        "password": "demo123",
        "company_name": "Beta Fashion Store",
        "merchant_id": "merchant_beta_002",
        "razorpay_key_id": "rzp_test_beta456",
        "razorpay_key_secret": "secret_beta_uvw012",
        "shopify_url": "beta-fashion.myshopify.com",
        "industry": "Fashion & Apparel",
        "logo_emoji": "👗"
    },
    "demo@gammafoods.com": {
        "password": "demo123",
        "company_name": "Gamma Organic Foods",
        "merchant_id": "merchant_gamma_003",
        "razorpay_key_id": "rzp_test_gamma789",
        "razorpay_key_secret": "secret_gamma_abc345",
        "shopify_url": "gamma-foods.myshopify.com",
        "industry": "Food & Beverages",
        "logo_emoji": "🌱"
    },
    "demo@deltatech.com": {
        "password": "demo123",
        "company_name": "Delta Tech Solutions",
        "merchant_id": "merchant_delta_004",
        "razorpay_key_id": "rzp_test_delta012",
        "razorpay_key_secret": "secret_delta_def678",
        "shopify_url": "delta-tech.myshopify.com",
        "industry": "Software & Services",
        "logo_emoji": "💻"
    }
}


def authenticate(email: str, password: str) -> tuple[bool, dict | None]:
    """
    Authenticate a user with email and password.

    Returns:
        (success: bool, merchant_data: dict | None)
    """
    email = email.strip().lower()
    password = password.strip()

    if email not in DEMO_MERCHANTS:
        return False, None

    merchant = DEMO_MERCHANTS[email]

    # Case-insensitive: these are throwaway demo credentials, not real
    # secrets, and caps-lock/autofill shouldn't break the demo.
    if merchant["password"].lower() == password.lower():
        # Don't return password in session data
        session_data = {k: v for k, v in merchant.items() if k != "password"}
        session_data["email"] = email
        return True, session_data

    return False, None


def get_merchant_by_email(email: str) -> dict | None:
    """
    Look up a merchant's session data by email alone, no password check.
    Used to restore an already-authenticated session after a browser
    refresh (see login.py writing st.query_params, and app_new.py reading
    it back) -- this is a restore path, not a login path, so it must
    never be reachable from user-typed input without a prior real
    authenticate() call having succeeded first.
    """
    email = (email or "").strip().lower()
    merchant = DEMO_MERCHANTS.get(email)
    if not merchant:
        return None
    session_data = {k: v for k, v in merchant.items() if k != "password"}
    session_data["email"] = email
    return session_data


def is_authenticated(session_state) -> bool:
    """Check if user is authenticated."""
    return hasattr(session_state, "authenticated") and session_state.authenticated


def get_current_merchant(session_state) -> dict | None:
    """Get current logged-in merchant data."""
    if not is_authenticated(session_state):
        return None
    return getattr(session_state, "merchant", None)


def logout(session_state):
    """Clear session and logout user."""
    session_state.authenticated = False
    session_state.merchant = None
