"""
Shared visual theme for Ledgr's Streamlit surfaces (login.py, app_new.py).

Tokens mirror app.py's INK/BODY/DIM/LINE/BG/SOFT/ACC constants so every
screen in the product shares one palette and typography. If app.py's
palette ever changes, update it here too — this is the single source of
truth for the login/dashboard shell.
"""

INK, BODY, DIM = "#0C0E12", "#4B5563", "#8A9099"
LINE, BG, SOFT = "#E5E7EB", "#FFFFFF", "#FAFAFA"
ACC, ACC_D = "#1A56DB", "#1443B0"
MATCHED, WARN, WARN_BG, WARN_BD = "#0E7C5A", "#B42318", "#FEF3F2", "#FDA29B"


def html(markup: str) -> str:
    """
    Strip per-line leading whitespace from a triple-quoted HTML literal.

    st.markdown(..., unsafe_allow_html=True) still runs the string through a
    Markdown parser first — unsafe_allow_html only stops HTML tags from being
    escaped, it does not turn off Markdown's own block rules. Once an f-string
    literal sits inside a few nested `with` blocks, every line picks up 12-24
    spaces of incidental Python indentation; any blank line in the middle
    (e.g. from joining several `f\"\"\"\\n...\"\"\"` fragments) then resets the
    block context, and the following indented lines get parsed as a fenced
    *code* block instead of raw HTML — text shows up literally instead of
    rendering. Route every multi-line HTML literal through this before
    passing it to st.markdown() to avoid that.
    """
    return "\n".join(line.strip() for line in markup.strip("\n").split("\n"))


def base_css() -> str:
    """CSS shared by every screen: font, chrome removal, inputs, buttons."""
    return f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        html,body,.stApp,[class*="css"] {{
            font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
            -webkit-font-smoothing:antialiased;
        }}
        .stApp {{background:{SOFT}; color:{INK};}}

        /* Streamlit swaps the whole page on every rerun (login -> dashboard
           included) -- there's a real network round-trip that can't be
           eliminated without leaving Streamlit's execution model. This
           doesn't remove that latency, it masks the abruptness: new
           content eases in instead of popping in, so the wait reads as
           intentional rather than a jarring flash. */
        @keyframes lg-fade-in {{from {{opacity:0; transform:translateY(4px);}} to {{opacity:1; transform:none;}}}}
        [data-testid="stMain"] {{animation: lg-fade-in .25s ease-out;}}

        /* Hide all Streamlit chrome, including the newer Deploy toolbar */
        #MainMenu, footer, .stDeployButton {{visibility:hidden; display:none;}}
        header[data-testid="stHeader"] {{background:transparent; height:0;}}
        [data-testid="stToolbar"] {{visibility:hidden; display:none;}}
        [data-testid="stDecoration"] {{display:none;}}
        [data-testid="stStatusWidget"] {{visibility:hidden; display:none;}}

        .stTextInput input {{
            background:{BG} !important; color:{INK} !important;
            border:1px solid {LINE} !important; border-radius:7px !important;
            padding:12px 14px !important; font-size:13.5px !important;
        }}
        .stTextInput input::placeholder {{color:{DIM} !important; opacity:1 !important;}}
        .stTextInput input:focus {{
            border-color:{ACC} !important;
            box-shadow:0 0 0 3px rgba(26,86,219,.14) !important;
        }}
        .stTextInput label {{color:{BODY} !important; font-size:13px !important;}}

        .stButton > button {{
            border-radius:7px; font-size:13.5px; font-weight:500;
            padding:.7rem 1.2rem; border:1px solid {LINE};
            background:{BG}; color:{INK}; width:100%;
            transition:background .18s,color .18s,border-color .18s,transform .18s;
        }}
        .stButton > button:hover {{
            background:{ACC}; color:#fff; border-color:{ACC};
            transform:translateY(-1px);
        }}
        .stButton > button:active {{background:{ACC_D}; border-color:{ACC_D};}}
        .stButton > button[kind="primary"] {{background:{ACC}; color:#fff; border-color:{ACC};}}
        .stButton > button[kind="primary"]:hover {{background:{ACC_D}; border-color:{ACC_D};}}

        /* Native bordered containers (st.container(border=True)) — our "cards" */
        [data-testid="stVerticalBlockBorderWrapper"] {{
            border-radius:10px !important;
            border-color:{LINE} !important;
        }}

        .stAlert {{border-radius:8px; border:1px solid {LINE};}}
        </style>
    """
