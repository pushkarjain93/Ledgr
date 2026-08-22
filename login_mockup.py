"""
ReconAI — cosmetic sign-in screen mockup.

IMPORTANT: this screen performs no authentication. It exists for visual
polish in the demo only. Any input proceeds. In production this would be
replaced by the company's existing SSO.
"""
from pathlib import Path

BG, PANEL, LINE = "#0d1117", "#161b22", "#30363d"
TXT, MUT, DIM = "#e6edf3", "#8b949e", "#6e7681"
GRN, BLU, AMB = "#3fb950", "#58a6ff", "#d29922"
F = "system-ui,-apple-system,Segoe UI,Roboto,sans-serif"
M = "ui-monospace,SFMono-Regular,Menlo,monospace"

W, H = 1400, 820
s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
add = s.append


def rect(x, y, w, h, fill=PANEL, stroke=LINE, r=10, sw=1, op=1):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="{sw}" opacity="{op}"/>')


def txt(x, y, t, size=13, fill=TXT, weight=400, anchor="start", font=F, ls=0):
    t = str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    add(f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" fill="{fill}" '
        f'font-weight="{weight}" text-anchor="{anchor}" letter-spacing="{ls}">{t}</text>')


add(f'<rect width="{W}" height="{H}" fill="{BG}"/>')
add(f'<defs><radialGradient id="g" cx="50%" cy="0%" r="80%">'
    f'<stop offset="0%" stop-color="#1f6feb" stop-opacity="0.16"/>'
    f'<stop offset="100%" stop-color="#0d1117" stop-opacity="0"/></radialGradient></defs>')
add(f'<rect width="{W}" height="{H}" fill="url(#g)"/>')

# ------------------------------------------------------------- card ---------
cx, cw = W / 2, 420
x0, y0, ch = cx - cw / 2, 132, 470
add(f'<rect x="{x0+5}" y="{y0+7}" width="{cw}" height="{ch}" rx="16" fill="#000" opacity="0.4"/>')
rect(x0, y0, cw, ch, r=16)

add(f'<circle cx="{cx}" cy="{y0+62}" r="26" fill="{BLU}" opacity="0.14"/>')
txt(cx, y0 + 71, "R", 26, BLU, 800, "middle")
txt(cx, y0 + 118, "ReconAI", 24, TXT, 700, "middle")
txt(cx, y0 + 141, "AI Finance Controller", 12, DIM, 400, "middle")

fx, fw = x0 + 40, cw - 80
txt(fx, y0 + 186, "WORK EMAIL", 9.5, DIM, 700, ls=0.6)
rect(fx, y0 + 196, fw, 42, fill="#0d1117", r=8)
txt(fx + 14, y0 + 222, "finance.ops@merchant.in", 12.5, MUT, font=M)

txt(fx, y0 + 264, "PASSWORD", 9.5, DIM, 700, ls=0.6)
rect(fx, y0 + 274, fw, 42, fill="#0d1117", r=8)
txt(fx + 14, y0 + 301, "\u2022" * 12, 13, MUT, font=M)

rect(fx, y0 + 336, fw, 44, fill="#238636", stroke="#2ea043", r=8)
txt(cx, y0 + 363, "Continue to dashboard", 13.5, "#fff", 700, "middle")

add(f'<line x1="{fx}" y1="{y0+404}" x2="{fx+fw}" y2="{y0+404}" stroke="{LINE}"/>')
txt(cx, y0 + 434, "Demo build - any input proceeds", 11, DIM, 400, "middle")

# ------------------------------------------------------- honesty banner -----
by, bh = y0 + ch + 40, 96
rect(x0 - 190, by, cw + 380, bh, fill="#1c1408", stroke="#5c4413", r=10)
add(f'<circle cx="{x0-160}" cy="{by+34}" r="11" fill="{AMB}" opacity="0.2"/>')
txt(x0 - 160, by + 39, "!", 14, AMB, 800, "middle")
txt(x0 - 138, by + 30, "This screen is cosmetic. It is not authentication.", 13, AMB, 700)
txt(x0 - 138, by + 52,
    "No identity is verified, no credentials are checked, nothing is stored. Any input proceeds to the dashboard.", 11.5, MUT)
txt(x0 - 138, by + 72,
    "Pitch line: \"in production this sits behind the company's existing SSO\" - it is a placeholder screen, not a built feature.",
    11.5, DIM)

add("</svg>")
out = Path(__file__).parent / "login_mockup.svg"
out.write_text("\n".join(s))
print("wrote", out)
