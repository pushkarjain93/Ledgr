"""Build Ledgr_Handoff_GPT_Claude.pdf — paste-ready briefing for another model."""
from pathlib import Path

from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, ListFlowable, ListItem, HRFlowable, Preformatted,
)

OUT = Path("/home/user/reconai/Ledgr_Handoff_GPT_Claude.pdf")

INK = HexColor("#0C0E12")
BODY = HexColor("#4B5563")
DIM = HexColor("#8A9099")
LINE = HexColor("#E5E7EB")
SOFT = HexColor("#F7F9FC")
ACC = HexColor("#1A56DB")
WARN = HexColor("#B42318")
OK = HexColor("#0E7C5A")

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(INK)
    canvas.rect(0, PAGE_H - 12 * mm, PAGE_W, 12 * mm, fill=1, stroke=0)
    canvas.setFillColor(white)
    canvas.setFont("Times-Bold", 8)
    canvas.drawString(MARGIN, PAGE_H - 8 * mm, "LEDGR  ·  HANDOFF FOR GPT / CLAUDE")
    canvas.setFont("Times-Roman", 8)
    canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 8 * mm, "Do not modify engine.py")
    canvas.setFillColor(LINE)
    canvas.rect(0, 0, PAGE_W, 10 * mm, fill=1, stroke=0)
    canvas.setFillColor(DIM)
    canvas.setFont("Times-Roman", 8)
    canvas.drawString(MARGIN, 4 * mm, "reconai  ·  Razorpay Buildathon  ·  22 Aug 2026")
    canvas.drawRightString(PAGE_W - MARGIN, 4 * mm, f"Page {doc.page}")
    canvas.restoreState()


def styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("H1", fontName="Times-Bold", fontSize=20, leading=24,
                         textColor=INK, spaceAfter=8, spaceBefore=4))
    s.add(ParagraphStyle("H2", fontName="Times-Bold", fontSize=13, leading=17,
                         textColor=ACC, spaceBefore=14, spaceAfter=6))
    s.add(ParagraphStyle("H3", fontName="Times-Bold", fontSize=11, leading=14,
                         textColor=INK, spaceBefore=10, spaceAfter=4))
    s.add(ParagraphStyle("P", fontName="Times-Roman", fontSize=9.5, leading=13,
                         textColor=BODY, alignment=TA_JUSTIFY, spaceAfter=6))
    s.add(ParagraphStyle("B", fontName="Times-Roman", fontSize=9.5, leading=13,
                         textColor=BODY, spaceAfter=3, leftIndent=8))
    s.add(ParagraphStyle("Note", fontName="Times-Italic", fontSize=9, leading=12,
                         textColor=DIM, spaceAfter=8, spaceBefore=2))
    s.add(ParagraphStyle("CodeBlock", fontName="Courier", fontSize=7.4, leading=10,
                         textColor=INK, backColor=SOFT, leftIndent=4, rightIndent=4,
                         spaceBefore=4, spaceAfter=8))
    s.add(ParagraphStyle("Warn", fontName="Times-Bold", fontSize=9.5, leading=13,
                         textColor=WARN, spaceAfter=6, spaceBefore=4))
    s.add(ParagraphStyle("Ok", fontName="Times-Bold", fontSize=9.5, leading=13,
                         textColor=OK, spaceAfter=6))
    s.add(ParagraphStyle("Cap", fontName="Times-Bold", fontSize=8, leading=10,
                         textColor=DIM, letterSpacing=1.2, spaceBefore=2, spaceAfter=4))
    s.add(ParagraphStyle("Li", fontName="Times-Roman", fontSize=9.5, leading=13,
                         textColor=BODY, leftIndent=14, spaceAfter=2))
    return s


def hr():
    return HRFlowable(width="100%", thickness=0.6, color=LINE, spaceBefore=4, spaceAfter=8)


def code_block(text, st):
    return Preformatted(text.strip("\n"), st["CodeBlock"])


def bullets(items, st):
    return [Paragraph(f"•  {i}", st["Li"]) for i in items]


def kv_table(rows):
    data = [[Paragraph(f"<b>{a}</b>", ParagraphStyle("k", fontName="Times-Bold",
             fontSize=8.5, leading=11, textColor=INK)),
             Paragraph(b, ParagraphStyle("v", fontName="Times-Roman",
             fontSize=8.5, leading=11, textColor=BODY))] for a, b in rows]
    t = Table(data, colWidths=[42 * mm, 130 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), SOFT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BOX", (0, 0), (-1, -1), 0.4, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
    ]))
    return t


def build():
    st = styles()
    doc = SimpleDocTemplate(
        str(OUT), pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=18 * mm, bottomMargin=16 * mm,
        title="Ledgr — Handoff for GPT and Claude",
        author="Ledgr / reconai",
    )
    S = []
    P, H1, H2, H3 = st["P"], st["H1"], st["H2"], st["H3"]

    S += [Paragraph("HANDOFF BRIEF", st["Cap"]),
          Paragraph("Ledgr  —  what we built, what we used, how to continue", H1),
          Paragraph(
              "Give this PDF (or its text) to GPT or Claude as the first message, "
              "then state the next task. This is the full conversation state for the "
              "Ledgr / ReconAI Streamlit dashboard as of 22 August 2026.", P),
          hr()]

    S += [Paragraph("1.  What this project is", H2),
          Paragraph(
              "Ledgr (repo name ReconAI) is a Razorpay Buildathon Track 04 project: "
              "an <b>internal finance-ops reconciliation dashboard</b>, not a marketing "
              "site. It takes orders (what you sold) and settlements (what you were paid), "
              "matches them line by line, accounts for gateway and COD fees, ages cash-on-delivery "
              "remittances, and leaves only the differences a human should touch.", P),
          Paragraph(
              "The product promise: <b>the engine classifies; the dashboard only displays "
              "and lets a person act. No LLM invents rupees.</b>", P),
          Paragraph(
              "User location for date logic: Dhanbad / India. Wall-clock “today” in the app "
              "is <b>22 August 2026</b> (Asia/Kolkata). Do not let models assume 2024.", P)]

    S += [Paragraph("2.  Where the code lives", H2),
          Paragraph("Real project: <b>/home/user/reconai</b>. Ignore leftover scratch at /home/user/recon.", P),
          kv_table([
              ("app.py", "Streamlit frontend. This is what we iterate on."),
              ("engine.py", "5-tier waterfall + Tier 0 COD pre-check. DO NOT MODIFY."),
              ("config.py", "Paise helpers, fee bands, COD windows, reason legend, priority."),
              ("gen_data.py", "Synthetic data generator. DO NOT MODIFY."),
              ("validate_data.py", "Asserts labels vs config. DO NOT MODIFY."),
              ("customers.csv", "Additive contact directory (phone, email, city)."),
              ("review_log.csv", "Append-only human resolutions."),
              ("data/orders.csv", "259 demo orders. Do not edit."),
              ("data/settlements.csv", "231 demo settlements. Do not edit."),
              ("data/ground_truth.csv", "265 labelled expected outcomes."),
              ("data/run_results.csv", "Engine CLI dump only. App must not read this as source."),
              (".streamlit/config.toml", "Light theme, bind 0.0.0.0:8501, fileWatcherType=poll."),
          ]),
          Spacer(1, 6),
          Paragraph(
              "Design leftovers (not runtime): demo.html, index.html, mockup.py, "
              "dashboard_mockup.svg, login_mockup.*, FEATURES.md, PROJECT_MAP.md "
              "(PROJECT_MAP is stale — it still says app.py is not built).", P)]

    S += [Paragraph("3.  Stack we used", H2),
          kv_table([
              ("Language", "Python 3.13"),
              ("UI", "Streamlit 1.62 (single app, no multipage, no auth)"),
              ("Data", "pandas 2.2, openpyxl 1.x for Excel upload"),
              ("Money", "Integer paise via decimal in config.py — never float math"),
              ("Dates", "datetime + zoneinfo Asia/Kolkata"),
              ("Voice / LLM APIs", "None. Ask Ledgr is local/deterministic."),
              ("DB / Docker / auth", "None. Files + session_state only."),
              ("Theme", "Light only. Accent #1A56DB / #2D5BFF, ink #0C0E12."),
              ("Preview host", "Streamlit on 0.0.0.0:8501. Health /_stcore/health ≠ code reloaded."),
              ("Verify UI", "streamlit.testing.v1.AppTest — do not import app.py as a module."),
          ]),
          Spacer(1, 6),
          Paragraph("Run command", H3),
          code_block("""
cd /home/user/reconai
pip install streamlit   # packages do not persist across sandbox recycle
streamlit run app.py --server.address 0.0.0.0 --server.port 8501 \\
  --server.headless true --server.enableCORS false \\
  --server.enableXsrfProtection false --server.fileWatcherType poll
""", st)]

    S += [Paragraph("4.  Architecture that must stay true", H2),
          code_block("""
CSV data
    →  engine.load()
    →  engine.reconcile()     # real classification
    →  session_state.results
    →  app.py Streamlit dashboard

Frontend joins (never change engine for these):
    order_date / customer / mode  ← orders.csv on record_id
    settled_on                    ← settlements.csv
    phone / email / city          ← order_id → orders.customer_name → customers.csv
    resolved flag                 ← review_log.csv (append-only)
""", st),
          Paragraph(
              "Run reconciliation must call real load()+reconcile(), optionally after "
              "soften_inputs() so uploaded files missing optional columns do not KeyError. "
              "Never treat run_results.csv as the app data source.", P),
          Paragraph("DO NOT TOUCH engine.py, gen_data.py, validate_data.py, orders.csv, "
                    "settlements.csv, or run_results.csv. Do not add OpenAI/Gemini/Claude "
                    "APIs, .env, or st.secrets.", st["Warn"])]

    S += [Paragraph("5.  Engine waterfall (frozen — for understanding only)", H2),
          Paragraph(
              "config.RUN_DATE is 2026-09-01 for reproducible CLI scoring. The app overrides "
              "engine.RUN_DATE with the dashboard “Reconcile as at” date (capped at today in India).", P)]
    S += bullets([
              "<b>Tier 0</b> — COD, no remittance yet. Age vs as-at: 0–7 wait, 8–14 approaching, 15+ overdue exception.",
              "<b>Tier 1</b> — gateway_ref_id + amount exact → AUTO_CLEARED.",
              "<b>Tier 2</b> — ref match, shortfall inside fee_band (online 2%/₹3 or COD 2.5%/₹50).",
              "<b>Tier 3</b> — ref match, amount off-band → ai_diagnose(facts). Model never computes money.",
              "<b>Tier 4</b> — no ref → bank_utr fallback, then classify.",
              "<b>Tier 5</b> — unmatched / ambiguous / unlinked bank credit (STL-X*: received &gt; 0, expected = 0).",
          ], st)
    S += [Spacer(1, 4),
          Paragraph(
              "CLI: <font face='Courier'>python3 engine.py</font> → 265 records scored, PERFECT vs ground_truth. "
              "Demo: 259 orders (2026-08-01→2026-09-01), 231 settlements (2026-08-02→2026-08-31). "
              "Modes: COD, CARD, WALLET, BANK_TRANSFER, UPI, NETBANKING.", P)]

    S += [Paragraph("6.  What we built in this conversation (in order)", H2),
          Paragraph("All of this is in app.py plus two additive files. Engine and source CSVs were not changed.", P)]
    H3_items = [
              ("6.1  Shell dashboard",
               "Streamlit app importing load/reconcile. Demo vs upload. Light theme. "
               "fileWatcherType had been none (edits invisible) — set to poll. Dark theme "
               "was tried and rejected (contrast). Marketing-site rewrite was rejected — stay internal."),
              ("6.2  Pre-run inspection",
               "After source choice, show real order/settlement counts and totals, preview tables, "
               "then Reconcile. No fake 0 Matched/Waiting before the first run."),
              ("6.3  Live as-at date",
               "COD ageing is live against the picker. Waiting records are COD with no UTR yet, "
               "not hardcoded. Picker max = today India (2026-08-22). Future dates blocked. "
               "Changing as-at re-runs if already reconciled. Button label is always "
               "“Run reconciliation”, never “Run again”."),
              ("6.4  Settlement graph + money + plain-language buckets",
               "Bars from settlements.settled_on. Window = 1st of as-at month → as-at (no future money). "
               "Hover tooltips. Slider filters the table. Money: Expected / Received / Gap. "
               "Outcomes: Matched / Waiting / Needs a look / Show everything. Reason cards: "
               "Unmatched, Remittance overdue, Partial payment, Large variance flagged by AI. "
               "Click filters + scroll to the record list."),
              ("6.5  Home scroll wordmark",
               "Entry page: large “Ledgr” (no logo icon) shrinks to top-left on scroll via "
               "CSS animation-timeline. Flat light background, no grid/gradient."),
              ("6.6  Ask Ledgr (local)",
               "No Gemini/GPT. Deterministic reply() on the current run. Order ID and later S.No. "
               "lookup. Aggregates for risk / review / COD / summary. Never invent figures."),
              ("6.7  Manual resolution",
               "Needs a look → Mark as resolved → required note → append review_log.csv. "
               "Row keeps original tier/reason + green “Resolved manually”. "
               "Live Needs a look count and at-risk exclude resolved. "
               "Show resolved = only resolved rows. Hide resolved (default) = only open. "
               "Toggle sits under Find a record."),
              ("6.8  Contacts",
               "customers.csv for 15 demo people. Lookup is only "
               "order_id → orders.customer_name → customers.csv. No name search. "
               "Inline 👤 Contact expand on Needs a look rows. Unlinked STL-X: "
               "“No order on file — cannot identify sender”."),
              ("6.9  Upload hardening",
               "User CSVs crashed on missing customer_name, source, narration. "
               "soften_inputs() fills those empty. run_engine() calls "
               "reconcile(*soften_inputs(*load())). Required columns still validated."),
              ("6.10  Navigation + pacing",
               "← next to Ledgr calls change_source() (same as upload Back). "
               "Demo click: 1.5s “Loading demo data” then inspection at top. "
               "Reconcile loading animation was added then removed — click goes "
               "straight to results. execute() is cached on (datadir, as-at); "
               "do not nonce-bust every click."),
          ]
    for title, body in H3_items:
        S += [Paragraph(title, H3), Paragraph(body, P)]

    S += [Paragraph("7.  Current user-facing flow", H2),
          code_block("""
Home (scroll) → Use demo data (1.5s wait) or Upload
    → Pre-run: 259/231 (or user files), date picker ≤ today
    → Run reconciliation (instant after cache; land at top)
    → Results:
         settlement bars (1st → as-at)
         money + “N resolved · still at risk”
         outcome + reason cards (click → filter + scroll)
         find record
         Show resolved / Hide resolved
         table with S.No., Resolve, Contact
         Ask Ledgr (bottom right)
    → ← Back resets to home (change_source)
""", st)]

    S += [Paragraph("8.  Important session keys", H2),
          Paragraph(
              "source, datadir, results, runs, ms, asat, dfrom, dto, pick, reason, q, mode, "
              "chat_open, ask, focus, resolve_id, contact_id, hide_resolved (default True = open only), "
              "land_top, pending (demo wait), jump, jumps.", P)]

    S += [Paragraph("9.  Lessons (do not repeat these bugs)", H2)]
    S += bullets([
              "fileWatcherType=none meant edits never appeared. Use poll. Health=ok is not proof of reload.",
              "Do not import app.py outside Streamlit (session_state is None → crash). Use AppTest.",
              "Outcome cards: HTML face + invisible overlay ate clicks. Keep the Streamlit button in document flow; face sits on top with pointer-events:none.",
              "components.html scroll scripts must change (nonce) or Streamlit will not re-run them.",
              "Table header must share the same column split as rows, or money headings sit over the action buttons.",
              "Contact + Resolve stacked doubled row height. Keep them on one row; Contact is a person icon + tooltip.",
              "Ask Ledgr must not search by customer name. Follow-up keywords like “it” stole “credits” — use word boundaries; check unlinked/resolved aggregates first.",
              "Fake 100/200/259 progress over seconds while the engine is 1ms is dishonest. Loading UI was removed.",
              "A full marketing-site rewrite was rejected. Stay an internal dashboard. Light mode only.",
          ], st)

    S += [Paragraph("10.  How Ask Ledgr resolves a person", H2),
          code_block("""
S.No. 3 / sno 3 / #3 / serial 3
    → row N in the currently visible filtered table
    → that row’s record_id (order_id)
    → orders.csv customer_name
    → customers.csv phone, email, city

ORD-00023 / “who do I contact for ORD-00023”
    → same chain. No name search.

STL-X0002 (expected 0, received > 0)
    → unlinked bank credit, not a data error, no customer.
""", st)]

    S += [Paragraph("11.  Demo script for a judge", H2)]
    S += bullets([
              "Use demo data → 259 orders, 231 settlements (real CSV totals).",
              "Run reconciliation → live buckets (as-at 22 Aug, not config 1 Sep).",
              "Move as-at earlier/later → waiting vs overdue COD changes. Not hardcoded.",
              "Click Waiting / Needs a look → list filters and scrolls.",
              "Contact icon on a row → name, phone, email, city via order_id.",
              "Mark resolved + note → Needs a look count and at-risk drop; row stays with tag.",
              "Ask Ledgr: S.No. 1, ORD-00023, how much is at risk, STL-X0002.",
          ], st)

    S += [Paragraph("12.  What to tell GPT or Claude to do next", H2),
          Paragraph(
              "Start from this brief. Work only in /home/user/reconai. Prefer app.py. "
              "Do not touch the engine or source CSVs. Keep it a single internal dashboard. "
              "After UI edits, restart Streamlit (poll watcher; do not trust HTTP 200). "
              "Verify with AppTest when you can. Be concise with the user; show evidence, not essays.", P),
          Paragraph(
              "Judge one-liner: Two CSVs go into a deterministic waterfall. The dashboard "
              "shows only what reconcile() returned. A human contacts the person on that "
              "order_id and marks it handled. The engine’s classification stays; live "
              "at-risk updates. No API key, no hallucinated rupees.", st["Ok"])]

    S += [Spacer(1, 10), hr(),
          Paragraph(
              "End of handoff. Paste the text of this PDF, or attach the file, as the first "
              "message to GPT or Claude, then give the next instruction.", st["Note"])]

    doc.build(S, onFirstPage=header_footer, onLaterPages=header_footer)
    print("wrote", OUT, OUT.stat().st_size)


if __name__ == "__main__":
    build()
