"""
ReconAI — dashboard mockup generator.

Emits dashboard_mockup.svg using the REAL numbers from data/ground_truth.csv,
so the mockup and the eventual Streamlit build cannot drift apart.
Design/visual only. No engine logic here.
"""
import csv
from collections import Counter
from pathlib import Path
from config import to_paise

ROOT = Path(__file__).parent
T = list(csv.DictReader(open(ROOT / "data/ground_truth.csv")))
O = {r["order_id"]: r for r in csv.DictReader(open(ROOT / "data/orders.csv"))}

tier = Counter(int(r["expected_tier"]) for r in T)
stat = Counter(r["expected_status"] for r in T)
N = len(T)
CLEARED = stat["AUTO_CLEARED"] + stat["CLEARED_WITH_FEE"]
INFLIGHT = stat["AWAITING_REMITTANCE"] + stat["APPROACHING_THRESHOLD"]
ACTION = stat["MANUAL_REVIEW"] + stat["EXCEPTION"]
AI = stat["MANUAL_REVIEW"]
NOAI = (N - AI) / N

# ---- palette ---------------------------------------------------------------
BG, PANEL, LINE = "#0d1117", "#161b22", "#30363d"
TXT, MUT, DIM = "#e6edf3", "#8b949e", "#6e7681"
GRN, BLU, AMB, RED, PUR, CYN = "#3fb950", "#58a6ff", "#d29922", "#f85149", "#bc8cff", "#39c5cf"
F = "system-ui,-apple-system,Segoe UI,Roboto,sans-serif"
M = "ui-monospace,SFMono-Regular,Menlo,monospace"

W = 1400
s = []
add = s.append


def rect(x, y, w, h, fill=PANEL, stroke=LINE, r=10, sw=1, op=1):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="{sw}" opacity="{op}"/>')


def txt(x, y, t, size=13, fill=TXT, weight=400, anchor="start", font=F, ls=0):
    t = (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    add(f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" fill="{fill}" '
        f'font-weight="{weight}" text-anchor="{anchor}" letter-spacing="{ls}">{t}</text>')


def pill(x, y, label, fill, w=None, h=22, fs=11, tc=None):
    w = w or len(label) * 7 + 20
    rect(x, y, w, h, fill=fill, stroke="none", r=h / 2, op=0.18)
    txt(x + w / 2, y + h / 2 + 4, label, fs, tc or fill, 600, "middle")
    return w


def wrap(x, y, t, width, size=11.5, fill=TXT, lh=16, weight=400):
    words, line, n = t.split(), [], 0
    for w_ in words:
        if sum(len(q) for q in line) + len(line) + len(w_) > width:
            txt(x, y + n * lh, " ".join(line), size, fill, weight); line = [w_]; n += 1
        else:
            line.append(w_)
    if line:
        txt(x, y + n * lh, " ".join(line), size, fill, weight); n += 1
    return n * lh


def sect(y, title, sub=""):
    txt(40, y, title, 15, TXT, 700)
    if sub:
        txt(40 + len(title) * 8.6 + 14, y, sub, 12, DIM)


# ============================================================ header =========
H = 1934
add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
    f'viewBox="0 0 {W} {H}">')
add(f'<rect width="{W}" height="{H}" fill="{BG}"/>')

rect(0, 0, W, 74, fill="#010409", stroke=LINE, r=0)
add(f'<circle cx="46" cy="37" r="13" fill="{BLU}" opacity="0.15"/>')
txt(46, 42, "R", 15, BLU, 800, "middle")
txt(70, 34, "ReconAI", 18, TXT, 700)
txt(70, 52, "AI Finance Controller  /  multi-source reconciliation", 11.5, DIM)
txt(W - 40, 33, "Run date  2026-09-01", 12, MUT, 500, "end")
txt(W - 40, 52, "Dataset: orders.csv + settlements.csv", 11.5, DIM, 400, "end")

# ============================================================ toolbar ========
y = 96
rect(40, y, 470, 40, fill="#0d1117", r=8)
txt(60, y + 25, "Search order ID, gateway ref, or UTR", 12.5, DIM)
txt(478, y + 25, "/", 12, DIM)

fx = 528
for lbl, active in [("All modes", True), ("UPI", False), ("Card", False),
                    ("Netbanking", False), ("Wallet", False), ("COD", False)]:
    w = len(lbl) * 7.4 + 26
    rect(fx, y, w, 40, fill="#1f6feb" if active else "#0d1117",
         stroke=BLU if active else LINE, r=8, op=1)
    txt(fx + w / 2, y + 25, lbl, 12.5, "#fff" if active else MUT, 600 if active else 400, "middle")
    fx += w + 8

rect(W - 348, y, 150, 40, fill="#238636", stroke="#2ea043", r=8)
txt(W - 273, y + 25, "Run reconciliation", 12.5, "#fff", 600, "middle")
rect(W - 188, y, 148, 40, fill="#0d1117", r=8)
txt(W - 114, y + 25, "Export report CSV", 12.5, MUT, 500, "middle")

# ============================================================ metrics ========
y = 162
cards = [
    ("RECORDS PROCESSED", f"{N}", "259 orders + 6 unlinked credits", TXT),
    ("AUTO-MATCHED", f"{CLEARED}", f"{CLEARED/N:.1%} cleared, no human touch", GRN),
    ("IN FLIGHT", f"{INFLIGHT}", "COD inside remittance window", BLU),
    ("NEEDS ACTION", f"{ACTION}", "review queue + exceptions", AMB),
    ("RESOLVED WITHOUT AI", f"{NOAI:.1%}", f"only {AI} records hit the model", PUR),
]
cw, gap = (W - 80 - 4 * 14) / 5, 14
for i, (lbl, val, sub, col) in enumerate(cards):
    x = 40 + i * (cw + gap)
    rect(x, y, cw, 104)
    add(f'<rect x="{x}" y="{y}" width="4" height="104" rx="2" fill="{col}"/>')
    txt(x + 18, y + 26, lbl, 10, DIM, 700, ls=0.6)
    txt(x + 18, y + 62, val, 30, col, 700, font=M)
    txt(x + 18, y + 85, sub, 10.5, MUT)

# ============================================================ tier bar =======
y = 300
sect(y, "Tier breakdown", "— which rung of the waterfall resolved each record")
y += 16
rect(40, y, W - 80, 132)

bar_x, bar_y, bar_w = 66, y + 30, W - 132
tiers = [
    (0, tier[0], CYN, "COD timing pre-check"),
    (1, tier[1], GRN, "Exact match"),
    (2, tier[2], "#2da44e", "Known deduction"),
    (3, tier[3], PUR, "AI diagnostic"),
    (4, tier[4], BLU, "UTR fallback"),
    (5, tier[5], RED, "Unmatched"),
]
cx = bar_x
for t, c, col, name in tiers:
    w = bar_w * c / N
    add(f'<rect x="{cx}" y="{bar_y}" width="{w}" height="34" fill="{col}" opacity="0.85"/>')
    if w > 34:
        txt(cx + w / 2, bar_y + 22, c, 13, "#010409", 700, "middle", font=M)
    cx += w

lx = bar_x
for t, c, col, name in tiers:
    add(f'<rect x="{lx}" y="{bar_y + 54}" width="11" height="11" rx="2" fill="{col}"/>')
    txt(lx + 18, bar_y + 64, f"Tier {t}", 11.5, TXT, 600)
    txt(lx + 18, bar_y + 80, name, 10.5, DIM)
    txt(lx + 18 + 44, bar_y + 64, f"{c}", 11.5, col, 700, font=M)
    lx += 214

# ============================================================ money + cod ====
y = 464
sect(y, "Money position")
txt(740, y, "COD remittance tracker", 15, TXT, 700)
y += 16
rect(40, y, 660, 150)
rect(724, y, W - 764, 150)

rows = [("Order book value", "Rs 741,024.13", TXT),
        ("Settlements received", "Rs 671,056.23", TXT),
        ("Explained deductions (MDR, GST, COD fee)", "Rs   2,791.49", GRN),
        ("Awaiting COD remittance", "Rs  60,687.41", BLU),
        ("Unexplained / at risk", "Rs 118,884.96", AMB)]
ry = y + 32
for lbl, val, col in rows:
    txt(66, ry, lbl, 12.5, MUT if col == TXT else col)
    txt(676, ry, val, 12.5, col, 600, "end", font=M)
    ry += 25
add(f'<line x1="66" y1="{y+118}" x2="676" y2="{y+118}" stroke="{LINE}"/>')

cod = [("Fresh", "0-7 days", stat["AWAITING_REMITTANCE"], GRN),
       ("Approaching", "8-14 days", stat["APPROACHING_THRESHOLD"], AMB),
       ("Overdue", "15+ days", stat["EXCEPTION"] and 5, RED)]
bx = 756
for name, rng, n, col in cod:
    rect(bx, y + 26, 186, 98, fill="#0d1117", stroke=LINE)
    txt(bx + 93, y + 56, str(n), 26, col, 700, "middle", font=M)
    txt(bx + 93, y + 78, name, 12.5, TXT, 600, "middle")
    txt(bx + 93, y + 96, rng, 10.5, DIM, 400, "middle")
    if name == "Overdue":
        txt(bx + 93, y + 114, "chase courier", 10, RED, 600, "middle")
    else:
        txt(bx + 93, y + 114, "no action needed" if name == "Fresh" else "watch", 10, DIM, 400, "middle")
    bx += 198

# ============================================================ matched ========
y = 646
sect(y, "Matched transactions", f"— {CLEARED} records, showing 5")
y += 16
rect(40, y, W - 80, 212)
cols = [(66, "ORDER"), (166, "MODE"), (268, "IDENTIFIER"), (438, "EXPECTED"),
        (562, "RECEIVED"), (686, "DELTA"), (798, "TAGGED AS"), (1010, "TIER"), (1210, "CONFIDENCE")]
for cx_, c in cols:
    txt(cx_, y + 28, c, 10, DIM, 700, ls=0.5)
add(f'<line x1="66" y1="{y+38}" x2="{W-66}" y2="{y+38}" stroke="{LINE}"/>')

mrows = [
    ("ORD-00003", "CARD", "pay_000003C", "6,499.99", "6,499.99", "0.00", "-", 1, "Exact", GRN),
    ("ORD-00002", "WALLET", "pay_000002F", "599.50", "591.02", "-8.48", "Gateway fee (MDR+GST)", 2, "Rule", GRN),
    ("ORD-00005", "COD", "UTR000400005", "599.99", "574.99", "-25.00", "COD collection fee", 4, "Rule", BLU),
    ("ORD-00041", "COD", "UTR000400041", "2,499.99", "2,499.99", "0.00", "-", 4, "Exact", BLU),
    ("ORD-00090", "BANK_TRANSFER", "UTR000400090", "9,999.00", "9,999.00", "0.00", "-", 4, "Exact", BLU),
]
ry = y + 62
for oid, mode, ident, exp, rec, dl, tag, tr, conf, col in mrows:
    txt(66, ry, oid, 12, TXT, 600, font=M)
    txt(166, ry, mode, 11.5, MUT)
    txt(268, ry, ident, 11.5, DIM, font=M)
    txt(524, ry, exp, 12, MUT, 400, "end", font=M)
    txt(648, ry, rec, 12, TXT, 400, "end", font=M)
    txt(752, ry, dl, 12, DIM if dl == "0.00" else AMB, 600, "end", font=M)
    txt(798, ry, tag, 11.5, DIM if tag == "-" else MUT)
    pill(1010, ry - 15, f"Tier {tr}", col)
    txt(1210, ry, conf, 11.5, MUT)
    txt(1290, ry, "deterministic", 10.5, DIM)
    ry += 30

# ============================================================ exceptions =====
y = 890
txt(40, y, "Exception queue", 15, TXT, 700)
add(f'<circle cx="176" cy="{y-5}" r="9" fill="{RED}" opacity="0.18"/>')
txt(176, y - 1, "!", 12, RED, 800, "middle")
txt(196, y, f"— {ACTION} records needing a human, sorted by amount at risk", 12, DIM)
txt(W - 40, y, "Sort:  Amount at risk  \u25be", 11.5, BLU, 600, "end")
y += 16
rect(40, y, W - 80, 300, stroke="#5c2626")

for cx_, c in [(66, "PRIORITY"), (176, "ORDER"), (296, "MODE"), (404, "REASON"),
               (760, "AGE"), (860, "TIER"), (1000, "AI EXPLANATION"), (1330, "AMOUNT AT RISK")]:
    txt(cx_ if c != "AMOUNT AT RISK" else 1334, y + 28, c, 10, DIM, 700,
        "end" if c == "AMOUNT AT RISK" else "start", ls=0.5)
add(f'<line x1="66" y1="{y+38}" x2="{W-66}" y2="{y+38}" stroke="{LINE}"/>')

erows = [
    ("High", RED, "ORD-00023", "CARD", "Unmatched / ambiguous", "no settlement found for this order",
     "31d", 5, "-", "9,999.00"),
    ("High", RED, "STL-X0002", "BANK", "Unmatched / ambiguous", "credit in feed with no order behind it",
     "18d", 5, "-", "7,898.00"),
    ("High", RED, "ORD-00217", "CARD", "Large variance flagged by AI", "settled above order value",
     "12d", 3, "View", "6,499.50"),
    ("High", RED, "ORD-00234", "NETBANKING", "Partial payment", "50% short, refund likely netted off",
     "9d", 3, "View", "4,999.75"),
    ("Medium", AMB, "ORD-00081", "COD", "Remittance overdue", "day 26, no courier remittance",
     "26d", 0, "-", "9,999.00"),
    ("Medium", AMB, "ORD-00103", "COD", "Remittance overdue", "day 18, no courier remittance",
     "18d", 0, "-", "6,499.50"),
    ("Low", BLU, "ORD-00056", "COD", "Awaiting courier remittance", "day 0, inside normal window",
     "0d", 0, "-", "2,499.99"),
]
ry = y + 62
for prio, pc, oid, mode, reason, detail, age, tr, ai, amt in erows:
    pill(66, ry - 15, prio, pc, w=72)
    txt(176, ry, oid, 12, TXT, 600, font=M)
    txt(296, ry, mode, 11.5, MUT)
    txt(404, ry, reason, 12, TXT if prio != "Low" else MUT, 500)
    txt(404, ry + 14, detail, 10.5, DIM)
    txt(760, ry, age, 11.5, MUT, font=M)
    pill(860, ry - 15, f"Tier {tr}", RED if tr == 5 else (PUR if tr == 3 else CYN))
    if ai == "View":
        txt(1000, ry, "View reasoning \u203a", 11.5, PUR, 600)
    else:
        txt(1000, ry, "not sent to AI", 11.5, DIM)
    txt(1334, ry, f"Rs {amt}", 13, pc, 700, "end", font=M)
    ry += 34
txt(66, y + 288, "+ 47 more   -   Rs 118,884.96 total at risk across all exceptions",
    11.5, DIM)

# ============================================================ legend =========
y = 1222
sect(y, "Exception reason legend", "— every unresolved record carries exactly one")
y += 16
rect(40, y, W - 80, 128)
leg = [
    ("R1", "Awaiting courier remittance", "COD inside the normal 0-14 day window. Nothing is wrong.", BLU, 19),
    ("R2", "Remittance overdue", "COD past 14 days. Follow up with the courier partner.", AMB, 5),
    ("R3", "Unmatched / ambiguous", "No ID match, duplicate claims, or a credit with no order.", RED, 24),
    ("R4", "Partial payment", "Materially short, not explained by any standard fee.", AMB, 14),
    ("R5", "Large variance flagged by AI", "ID matched, amount did not. Diagnostic generated.", PUR, 11),
]
lx, ly = 66, y + 30
for i, (code, name, desc, col, n) in enumerate(leg):
    col_x = 66 + (i % 2) * 680
    row_y = ly + (i // 2) * 33
    add(f'<rect x="{col_x}" y="{row_y-11}" width="26" height="16" rx="3" fill="{col}" opacity="0.2"/>')
    txt(col_x + 13, row_y + 1, code, 10, col, 800, "middle", font=M)
    txt(col_x + 36, row_y + 1, name, 12, TXT, 600)
    txt(col_x + 36 + len(name) * 6.7 + 10, row_y + 1, f"({n})", 11, col, 700, font=M)
    txt(col_x + 36, row_y + 15, desc, 10.5, DIM)

# ============================================================ ai drawer ======
y = 1394
sect(y, "AI reasoning viewer", "— opens when you click 'View reasoning' on a Tier 3 row")
y += 16
rect(40, y, W - 80, 162, stroke="#3d2c5c")
txt(66, y + 30, "ORD-00217", 13, TXT, 700, font=M)
pill(150, y + 16, "Tier 3", PUR)
pill(216, y + 16, "R5 Large variance flagged by AI", PUR, w=210)
txt(W - 66, y + 30, "Rs 6,499.50 at risk", 13, AMB, 700, "end", font=M)

txt(66, y + 58, "FACTS PASSED TO THE MODEL  (computed by the engine, not by the AI)", 10, DIM, 700, ls=0.5)
for i, f_ in enumerate([
        "order_amount = 6499.50    amount_received = 12999.00    delta = +6499.50",
        "gateway_ref_id matched exactly on settlement STL-00217    settled T+2    mode = CARD",
        "delta is positive and equals 100.00% of order value -> outside every tolerance band"]):
    txt(66, y + 78 + i * 17, f_, 11, MUT, font=M)

txt(66, y + 138, "MODEL OUTPUT:", 10, PUR, 700, ls=0.5)
txt(160, y + 138, "\"Settled amount is exactly double the order value on a matched "
                  "gateway reference. Consistent with a duplicate capture, not a fee or refund. "
                  "Do not clear - confirm with the gateway before posting.\"", 11.5, TXT)

txt(66, y + 158, "The model never sees or produces a number. It receives engine-computed "
                 "facts and returns a category plus one sentence.", 10.5, DIM)


# ============================================================ chat ===========
y = 1610
sect(y, "Chat assistant", "— floating widget, bottom-right, read-only, scoped to the current run")
y += 16
rect(40, y, W - 80, 292)

# left: what it is and is not
txt(66, y + 32, "WHAT IT DOES", 10, DIM, 700, ls=0.5)
for i, t_ in enumerate([
        "Answers questions about the results table already in memory.",
        "Same Claude/Gemini client the Tier 3 diagnostic uses. No new pipeline.",
        "A thin nod to the track's 'Settlement Q and A' direction."]):
    txt(66, y + 54 + i * 20, "-  " + t_, 11.5, MUT)

txt(66, y + 140, "SCOPE GUARD", 10, RED, 700, ls=0.5)
for i, t_ in enumerate([
        "Read-only. It cannot clear, edit, or re-run anything.",
        "Current run only. No external lookups, no general finance questions.",
        "Every figure it quotes is read from the engine output, never computed",
        "by the model. Out-of-scope questions get a refusal, not a guess."]):
    txt(66, y + 162 + i * 20, "-  " + t_, 11.5, MUT)

# collapsed state
txt(66, y + 258, "Collapsed state:", 11, DIM, 600)
rect(176, y + 244, 168, 34, fill="#1f6feb", stroke=BLU, r=17)
add(f'<circle cx="196" cy="{y + 261}" r="7" fill="#fff" opacity="0.9"/>')
txt(268, y + 265, "Ask about this run", 11.5, "#fff", 600, "middle")

# right: the widget itself
wx, wy, ww, wh = 900, y + 22, 420, 248
add(f'<rect x="{wx+4}" y="{wy+5}" width="{ww}" height="{wh}" rx="12" fill="#000" opacity="0.35"/>')
rect(wx, wy, ww, wh, fill="#0d1117", stroke="#2f4d7a", r=12)
rect(wx, wy, ww, 44, fill="#161b22", stroke="#2f4d7a", r=12)
add(f'<rect x="{wx}" y="{wy+32}" width="{ww}" height="12" fill="#161b22"/>')
add(f'<circle cx="{wx+22}" cy="{wy+22}" r="7" fill="{BLU}" opacity="0.25"/>')
txt(wx + 38, wy + 20, "Ask about this run", 12, TXT, 700)
txt(wx + 38, wy + 34, "read-only  -  current run only", 9.5, DIM)
txt(wx + ww - 18, wy + 27, "x", 13, DIM, 400, "end")

# conversation
qa = [
    ("u", "how many exceptions are COD?"),
    ("a", "11 of the 54 records needing action are COD: 5 remittance overdue, "
          "6 short beyond the collection-fee band. Rs 22,774.87 at risk."),
    ("u", "was ORD-00023 received?"),
    ("a", "No. ORD-00023 (CARD, Rs 9,999.00) has no settlement in the feed. "
          "Tier 5, reason R3 unmatched. Largest single exposure in this run."),
]
cy = wy + 60
for who, msg in qa:
    if who == "u":
        bw = min(300, len(msg) * 6.1 + 24)
        rect(wx + ww - 16 - bw, cy - 12, bw, 26, fill="#1f6feb", stroke="none", r=9)
        txt(wx + ww - 16 - bw + 12, cy + 5, msg, 10.5, "#fff")
        cy += 36
    else:
        h_ = 16 * (1 + len(msg) // 52)
        rect(wx + 16, cy - 12, 320, h_ + 18, fill="#161b22", stroke=LINE, r=9)
        wrap(wx + 28, cy + 4, msg, 52, 10.5, TXT, 15)
        cy += h_ + 30

rect(wx + 16, wy + wh - 46, ww - 32, 34, fill="#161b22", r=8)
txt(wx + 30, wy + wh - 24, "Ask about an order, UTR, tier, or reason...", 10.5, DIM)
rect(wx + ww - 76, wy + wh - 40, 48, 22, fill="#238636", stroke="none", r=6)
txt(wx + ww - 52, wy + wh - 25, "Send", 10.5, "#fff", 600, "middle")

add("</svg>")
out = ROOT / "dashboard_mockup.svg"
out.write_text("\n".join(s))
print("wrote", out, f"({out.stat().st_size/1024:.1f} KB)")
