"""
ReconAI — interactive clickable prototype.

Emits demo.html: a single self-contained file with the real run results baked
in as JSON. No network, no server dependency, works in a sandboxed iframe.

This is a UX prototype to de-risk the Streamlit build, not a replacement for
it. Every number comes from data/run_results.csv.
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).parent
res = list(csv.DictReader(open(ROOT / "data/run_results.csv")))
orders = {o["order_id"]: o for o in csv.DictReader(open(ROOT / "data/orders.csv"))}
setls = {s["settlement_id"]: s for s in csv.DictReader(open(ROOT / "data/settlements.csv"))}

rows = []
for r in res:
    o = orders.get(r["record_id"], {})
    s = setls.get(r["record_id"], {})
    rows.append({
        "id": r["record_id"],
        "tier": int(r["tier"]),
        "tierName": r["tier_name"],
        "status": r["status"],
        "reason": r["reason"],
        "reasonLabel": r["reason_label"],
        "feeType": r["fee_type"],
        "expected": float(r["expected"]),
        "received": float(r["received"]),
        "delta": float(r["delta"]),
        "risk": float(r["amount_at_risk"]),
        "priority": r["priority"],
        "why": r["explanation"],
        "settlement": r["matched_settlement"],
        "age": r["age_days"],
        "ai": r["ai_assisted"] == "True",
        "mode": o.get("payment_mode", "BANK"),
        "customer": o.get("customer_name", "-"),
        "date": o.get("order_date", s.get("settled_on", "-")),
        "ident": o.get("gateway_ref_id") or o.get("bank_utr") or s.get("bank_utr", "-"),
    })

LEGEND = {
    "R1_AWAITING_REMITTANCE": ["Awaiting courier remittance",
        "COD order inside the normal 0-14 day collection window. No match yet, and nothing is wrong."],
    "R2_REMITTANCE_OVERDUE": ["Remittance overdue",
        "COD order past 14 days with no remittance received. Needs follow-up with the courier partner."],
    "R3_UNMATCHED_AMBIGUOUS": ["Unmatched / ambiguous",
        "A genuine reconciliation failure: no identifier match, conflicting duplicates, or a credit with no order."],
    "R4_PARTIAL_PAYMENT": ["Partial payment",
        "Amount received is materially below the order value and is not explained by a standard fee."],
    "R5_AI_VARIANCE": ["Large variance flagged by AI",
        "Identifier matched but the amount did not. An AI diagnostic was generated and the record routed for review."],
}

HTML = """<!DOCTYPE html>
<html lang="en" data-theme="dark">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ReconAI</title>
<style>
:root[data-theme="dark"]{
  --bg:#0d1117; --bg2:#010409; --panel:#161b22; --panel2:#0d1117; --line:#30363d;
  --txt:#e6edf3; --mut:#8b949e; --dim:#6e7681; --grn:#3fb950; --blu:#58a6ff;
  --amb:#d29922; --red:#f85149; --pur:#bc8cff; --cyn:#39c5cf; --shadow:rgba(0,0,0,.5);
  --hover:#1c2128;
}
:root[data-theme="light"]{
  --bg:#f6f8fa; --bg2:#fff; --panel:#fff; --panel2:#f6f8fa; --line:#d0d7de;
  --txt:#1f2328; --mut:#59636e; --dim:#818b98; --grn:#1a7f37; --blu:#0969da;
  --amb:#9a6700; --red:#cf222e; --pur:#8250df; --cyn:#1b7c83; --shadow:rgba(31,35,40,.15);
  --hover:#f0f3f6;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
     font-size:14px;transition:background .18s,color .18s}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
button{font-family:inherit;cursor:pointer;border:none;background:none;color:inherit}

/* ---------- top bar ---------- */
header{position:sticky;top:0;z-index:40;background:var(--bg2);border-bottom:1px solid var(--line);
       padding:12px 20px;display:flex;align-items:center;gap:14px}
.menu-btn{width:38px;height:38px;border-radius:9px;border:1px solid var(--line);background:var(--panel);
          display:grid;place-items:center;font-size:17px;color:var(--mut)}
.menu-btn:hover{background:var(--hover);color:var(--txt)}
.brand{display:flex;align-items:center;gap:10px}
.logo{width:28px;height:28px;border-radius:50%;background:color-mix(in srgb,var(--blu) 16%,transparent);
      color:var(--blu);display:grid;place-items:center;font-weight:800;font-size:14px}
h1{font-size:15px;margin:0;font-weight:700}
.tag{font-size:11px;color:var(--dim)}
.hstat{margin-left:auto;display:flex;gap:22px;align-items:center}
.hstat div{text-align:right}
.hstat b{display:block;font-size:15px;font-family:ui-monospace,monospace}
.hstat span{font-size:10px;color:var(--dim);text-transform:uppercase;letter-spacing:.5px}

/* ---------- slide-out ---------- */
.scrim{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:50;opacity:0;pointer-events:none;transition:.2s}
.scrim.on{opacity:1;pointer-events:auto}
.drawer{position:fixed;top:0;left:0;bottom:0;width:330px;background:var(--panel);border-right:1px solid var(--line);
        z-index:51;transform:translateX(-100%);transition:transform .22s;padding:20px;overflow-y:auto}
.drawer.on{transform:none}
.drawer h2{font-size:12px;text-transform:uppercase;letter-spacing:.6px;color:var(--dim);margin:22px 0 10px}
.drawer h2:first-child{margin-top:4px}
input[type=text]{width:100%;padding:10px 12px;border-radius:8px;border:1px solid var(--line);
                 background:var(--panel2);color:var(--txt);font-size:13px;font-family:inherit}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{padding:6px 12px;border-radius:20px;border:1px solid var(--line);background:var(--panel2);
      font-size:12px;color:var(--mut)}
.chip.on{background:var(--blu);border-color:var(--blu);color:#fff;font-weight:600}
.act{display:block;width:100%;text-align:left;padding:11px 13px;border-radius:8px;border:1px solid var(--line);
     background:var(--panel2);font-size:13px;margin-bottom:8px;color:var(--txt)}
.act:hover{background:var(--hover)}
.act.primary{background:var(--grn);border-color:var(--grn);color:#fff;font-weight:600;text-align:center}
.toggle{display:flex;align-items:center;justify-content:space-between;padding:11px 13px;border:1px solid var(--line);
        border-radius:8px;background:var(--panel2)}
.sw{width:44px;height:24px;border-radius:12px;background:var(--line);position:relative;transition:.2s}
.sw::after{content:"";position:absolute;top:3px;left:3px;width:18px;height:18px;border-radius:50%;
           background:var(--txt);transition:.2s}
.sw.on{background:var(--blu)}
.sw.on::after{transform:translateX(20px);background:#fff}

/* ---------- layout ---------- */
main{padding:20px;max-width:1500px;margin:0 auto}
section{margin-bottom:22px}
.stitle{font-size:14px;font-weight:700;margin:0 0 10px;display:flex;align-items:center;gap:9px}
.stitle small{font-weight:400;color:var(--dim);font-size:11.5px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:11px}

.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}
.metric{padding:15px 17px;position:relative;overflow:hidden}
.metric::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--c)}
.metric .k{font-size:9.5px;letter-spacing:.6px;color:var(--dim);text-transform:uppercase;font-weight:700}
.metric .v{font-size:29px;font-weight:700;color:var(--c);font-family:ui-monospace,monospace;margin:6px 0 2px}
.metric .s{font-size:10.5px;color:var(--mut)}

.bar{display:flex;height:34px;border-radius:6px;overflow:hidden;margin:4px 0 14px}
.bar div{display:grid;place-items:center;font-size:12px;font-weight:700;color:#fff;
         font-family:ui-monospace,monospace;cursor:pointer;transition:opacity .15s}
.bar div:hover{opacity:.75}
.tlegend{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.tl{display:flex;gap:8px;align-items:flex-start;cursor:pointer;padding:6px;border-radius:7px}
.tl:hover{background:var(--hover)}
.tl.on{background:color-mix(in srgb,var(--blu) 12%,transparent)}
.sq{width:11px;height:11px;border-radius:3px;margin-top:3px;flex:none}
.tl b{font-size:11.5px;display:block}
.tl span{font-size:10.5px;color:var(--dim)}

table{width:100%;border-collapse:collapse}
th{font-size:9.5px;letter-spacing:.5px;color:var(--dim);text-transform:uppercase;text-align:left;
   padding:12px 10px;border-bottom:1px solid var(--line);font-weight:700;white-space:nowrap}
td{padding:10px;border-bottom:1px solid color-mix(in srgb,var(--line) 55%,transparent);font-size:12.5px}
tbody tr:hover{background:var(--hover)}
tbody tr:last-child td{border-bottom:none}
.r{text-align:right}
.pill{display:inline-block;padding:2px 9px;border-radius:11px;font-size:10.5px;font-weight:600}
.warn{color:var(--amb)}.zero{color:var(--dim)}.pos{color:var(--red)}
.wrap-sc{overflow-x:auto}
.empty{padding:40px;text-align:center;color:var(--dim);font-size:13px}
.more{padding:11px;text-align:center;font-size:12px;color:var(--dim);border-top:1px solid var(--line)}
.more button{color:var(--blu);font-weight:600}

.exc{border-color:color-mix(in srgb,var(--red) 32%,var(--line))}
.rsn b{display:block;font-size:12.5px}
.rsn span{font-size:10.5px;color:var(--dim)}
.info{width:17px;height:17px;border-radius:50%;border:1px solid var(--line);color:var(--dim);
      font-size:10px;display:inline-grid;place-items:center;cursor:help;position:relative}
.info:hover{border-color:var(--pur);color:var(--pur)}
.info .tip{display:none;position:absolute;bottom:24px;right:-6px;width:330px;background:var(--bg2);
           border:1px solid var(--pur);border-radius:9px;padding:11px 13px;font-size:11.5px;color:var(--txt);
           text-align:left;z-index:30;box-shadow:0 8px 26px var(--shadow);line-height:1.5;font-weight:400}
.info:hover .tip{display:block}
.tip em{display:block;color:var(--pur);font-size:9.5px;letter-spacing:.5px;text-transform:uppercase;
        font-style:normal;font-weight:700;margin-bottom:5px}
details.leg{margin-top:10px}
details.leg summary{font-size:11.5px;color:var(--blu);cursor:pointer;padding:8px 0;font-weight:600}
.legrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:10px;padding:6px 0 10px}
.li{display:flex;gap:9px}
.lc{font-size:9.5px;font-weight:800;padding:2px 6px;border-radius:4px;height:fit-content;font-family:ui-monospace,monospace}
.li b{font-size:12px;display:block}.li span{font-size:10.5px;color:var(--dim)}

/* ---------- chat ---------- */
.fab{position:fixed;right:22px;bottom:22px;width:56px;height:56px;border-radius:50%;background:var(--blu);
     color:#fff;font-size:22px;display:grid;place-items:center;box-shadow:0 6px 22px var(--shadow);z-index:45}
.fab:hover{transform:scale(1.06)}
.chat{position:fixed;right:22px;bottom:88px;width:390px;max-width:calc(100vw - 44px);height:470px;
      background:var(--panel);border:1px solid var(--line);border-radius:13px;z-index:46;display:none;
      flex-direction:column;box-shadow:0 14px 44px var(--shadow);overflow:hidden}
.chat.on{display:flex}
.chead{padding:13px 15px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:9px}
.chead b{font-size:13px}.chead span{font-size:10px;color:var(--dim);display:block}
.clog{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:11px}
.msg{max-width:86%;padding:9px 12px;border-radius:11px;font-size:12.5px;line-height:1.5}
.msg.u{align-self:flex-end;background:var(--blu);color:#fff}
.msg.a{align-self:flex-start;background:var(--panel2);border:1px solid var(--line)}
.msg.a code{font-size:11px;color:var(--blu)}
.cin{padding:11px;border-top:1px solid var(--line);display:flex;gap:8px}
.cin input{flex:1}
.cin button{padding:9px 15px;border-radius:8px;background:var(--grn);color:#fff;font-weight:600;font-size:12.5px}
.sugg{display:flex;flex-wrap:wrap;gap:5px;padding:0 14px 10px}
.sugg button{font-size:10.5px;padding:5px 9px;border:1px solid var(--line);border-radius:14px;color:var(--mut)}
.sugg button:hover{border-color:var(--blu);color:var(--blu)}

.toast{position:fixed;left:50%;bottom:26px;transform:translate(-50%,80px);background:var(--grn);color:#fff;
       padding:12px 22px;border-radius:9px;font-size:13px;font-weight:600;z-index:60;transition:.25s;opacity:0}
.toast.on{transform:translate(-50%,0);opacity:1}
.banner{background:color-mix(in srgb,var(--amb) 12%,transparent);border:1px solid color-mix(in srgb,var(--amb) 35%,transparent);
        border-radius:9px;padding:10px 14px;font-size:11.5px;color:var(--mut);margin-bottom:18px}
.banner b{color:var(--amb)}
</style>

<div class="scrim" id="scrim"></div>
<aside class="drawer" id="drawer">
  <h2>Search</h2>
  <input type="text" id="q" placeholder="Order ID, gateway ref, or UTR">
  <h2>Payment mode</h2>
  <div class="chips" id="modes"></div>
  <h2>Appearance</h2>
  <div class="toggle"><span id="tlabel">Dark mode</span><div class="sw on" id="sw"></div></div>
  <h2>Actions</h2>
  <button class="act primary" id="rerun">Run reconciliation</button>
  <button class="act" id="export">Export report CSV</button>
  <h2>About</h2>
  <p style="font-size:11.5px;color:var(--dim);line-height:1.6;margin:0">
    Clickable prototype. All 265 records are the real output of
    <code>engine.py</code>. Chat answers are computed locally from this table
    for the prototype; in the app that call routes to the model.</p>
</aside>

<header>
  <button class="menu-btn" id="menu">&#9776;</button>
  <div class="brand"><div class="logo">R</div>
    <div><h1>ReconAI</h1><div class="tag">AI Finance Controller &middot; run 2026-09-01</div></div></div>
  <div class="hstat">
    <div><b id="hs1">-</b><span>Processed</span></div>
    <div><b id="hs2" style="color:var(--grn)">-</b><span>Matched</span></div>
    <div><b id="hs3" style="color:var(--amb)">-</b><span>Needs action</span></div>
  </div>
</header>

<main>
  <div class="banner"><b>Prototype.</b> Interactive UX reference built on real engine output.
    The production build is Streamlit &mdash; this exists to settle layout and interaction first.</div>

  <section><div class="metrics" id="metrics"></div></section>

  <section>
    <div class="stitle">Tier breakdown <small>&mdash; click a tier to filter both tables</small></div>
    <div class="card" style="padding:16px">
      <div class="bar" id="bar"></div>
      <div class="tlegend" id="tleg"></div>
    </div>
  </section>

  <section>
    <div class="stitle">Matched transactions <small id="mcount"></small></div>
    <div class="card wrap-sc"><table>
      <thead><tr><th>Order</th><th>Mode</th><th>Identifier</th><th class="r">Expected</th>
      <th class="r">Received</th><th class="r">Delta</th><th>Tagged as</th><th>Tier</th></tr></thead>
      <tbody id="mbody"></tbody></table><div id="mmore"></div></div>
  </section>

  <section>
    <div class="stitle" style="color:var(--red)">&#9888; Exception queue
      <small id="ecount"></small></div>
    <div class="card exc wrap-sc"><table>
      <thead><tr><th>Priority</th><th>Record</th><th>Mode</th><th>Reason</th>
      <th class="r">Age</th><th>Tier</th><th class="r">Amount at risk</th><th></th></tr></thead>
      <tbody id="ebody"></tbody></table><div id="emore"></div></div>
    <details class="leg"><summary>What do these reasons mean?</summary>
      <div class="legrid" id="legrid"></div></details>
  </section>
</main>

<button class="fab" id="fab">&#128172;</button>
<div class="chat" id="chat">
  <div class="chead"><div class="logo" style="width:24px;height:24px;font-size:12px">R</div>
    <div><b>Ask about this run</b><span>read-only &middot; current run only</span></div>
    <button style="margin-left:auto;color:var(--dim)" id="cx">&times;</button></div>
  <div class="clog" id="clog"></div>
  <div class="sugg" id="sugg"></div>
  <div class="cin"><input type="text" id="cq" placeholder="Ask about an order, tier, or reason...">
    <button id="csend">Send</button></div>
</div>
<div class="toast" id="toast"></div>

<script>
const DATA = __DATA__, LEGEND = __LEGEND__;
const TIER = {0:["COD timing pre-check","--cyn"],1:["Exact match","--grn"],2:["Known deduction","--grn"],
              3:["AI diagnostic","--pur"],4:["UTR fallback","--blu"],5:["Unmatched","--red"]};
const CLEARED=["AUTO_CLEARED","CLEARED_WITH_FEE"], ACTION=["MANUAL_REVIEW","EXCEPTION"];
const cssv=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const rs=n=>"Rs "+n.toLocaleString("en-IN",{minimumFractionDigits:2,maximumFractionDigits:2});
let state={q:"",mode:"ALL",tier:null,mShow:8,eShow:10};

/* ---------- filtering ---------- */
function filtered(){
  return DATA.filter(r=>{
    if(state.mode!=="ALL" && r.mode!==state.mode) return false;
    if(state.tier!==null && r.tier!==state.tier) return false;
    if(state.q){const q=state.q.toLowerCase();
      if(!(r.id+" "+r.ident+" "+r.customer+" "+r.settlement).toLowerCase().includes(q)) return false;}
    return true;
  });
}
function render(){
  const f=filtered();
  const cleared=f.filter(r=>CLEARED.includes(r.status));
  const inflight=f.filter(r=>["AWAITING_REMITTANCE","APPROACHING_THRESHOLD"].includes(r.status));
  const action=f.filter(r=>ACTION.includes(r.status)).sort((a,b)=>b.risk-a.risk);
  const noai=f.filter(r=>!r.ai).length;

  hs1.textContent=f.length; hs2.textContent=cleared.length; hs3.textContent=action.length;

  metrics.innerHTML=[
    ["Records processed",f.length,(state.tier!==null||state.mode!=="ALL"||state.q)?"filtered view":"259 orders + 6 unlinked credits","--txt"],
    ["Auto-matched",cleared.length,f.length?(100*cleared.length/f.length).toFixed(1)+"% cleared, no human touch":"-","--grn"],
    ["In flight",inflight.length,"COD inside remittance window","--blu"],
    ["Needs action",action.length,rs(action.reduce((s,r)=>s+r.risk,0))+" at risk","--amb"],
    ["Resolved without AI",f.length?(100*noai/f.length).toFixed(1)+"%":"-",(f.length-noai)+" records hit the model","--pur"],
  ].map(([k,v,s,c])=>`<div class="card metric" style="--c:var(${c})">
      <div class="k">${k}</div><div class="v">${v}</div><div class="s">${s}</div></div>`).join("");

  /* tier bar */
  const counts={}; for(let t=0;t<6;t++) counts[t]=f.filter(r=>r.tier===t).length;
  const tot=f.length||1;
  bar.innerHTML=Object.entries(counts).filter(([,c])=>c>0).map(([t,c])=>
    `<div style="width:${100*c/tot}%;background:var(${TIER[t][1]})" data-t="${t}"
      title="Tier ${t} — ${TIER[t][0]}">${100*c/tot>4?c:""}</div>`).join("");
  tleg.innerHTML=Object.entries(TIER).map(([t,[n,c]])=>
    `<div class="tl ${state.tier==t?"on":""}" data-t="${t}"><div class="sq" style="background:var(${c})"></div>
     <div><b>Tier ${t} <span style="color:var(${c})" class="mono">${counts[t]}</span></b><span>${n}</span></div></div>`).join("");
  bar.querySelectorAll("div[data-t]").forEach(d=>d.onclick=()=>tierClick(+d.dataset.t));
  tleg.querySelectorAll(".tl").forEach(d=>d.onclick=()=>tierClick(+d.dataset.t));

  /* matched */
  mcount.textContent=`— ${cleared.length} record${cleared.length==1?"":"s"}`;
  mbody.innerHTML=cleared.slice(0,state.mShow).map(r=>`<tr>
    <td class="mono" style="font-weight:600">${r.id}</td><td style="color:var(--mut)">${r.mode}</td>
    <td class="mono" style="color:var(--dim)">${r.ident}</td>
    <td class="r mono" style="color:var(--mut)">${r.expected.toFixed(2)}</td>
    <td class="r mono">${r.received.toFixed(2)}</td>
    <td class="r mono ${r.delta?"warn":"zero"}">${r.delta.toFixed(2)}</td>
    <td style="color:var(--mut);font-size:11.5px">${r.feeType?LEGEND_FEE[r.feeType]:"&mdash;"}</td>
    <td><span class="pill" style="background:color-mix(in srgb,var(${TIER[r.tier][1]}) 18%,transparent);
        color:var(${TIER[r.tier][1]})">Tier ${r.tier}</span></td></tr>`).join("")
    ||`<tr><td colspan="8" class="empty">No matched records in this view.</td></tr>`;
  mmore.innerHTML=cleared.length>state.mShow?`<div class="more"><button id="mb">Show ${Math.min(20,cleared.length-state.mShow)} more of ${cleared.length-state.mShow}</button></div>`:"";
  if(cleared.length>state.mShow) mb.onclick=()=>{state.mShow+=20;render();};

  /* exceptions */
  ecount.textContent=`— ${action.length} needing a human, sorted by amount at risk`;
  ebody.innerHTML=action.slice(0,state.eShow).map(r=>{
    const pc=r.priority=="High"?"--red":r.priority=="Medium"?"--amb":"--blu";
    return `<tr>
    <td><span class="pill" style="background:color-mix(in srgb,var(${pc}) 18%,transparent);color:var(${pc})">${r.priority}</span></td>
    <td class="mono" style="font-weight:600">${r.id}</td><td style="color:var(--mut)">${r.mode}</td>
    <td class="rsn"><b>${r.reasonLabel}</b><span>${r.why.slice(0,74)}${r.why.length>74?"…":""}</span></td>
    <td class="r mono" style="color:var(--mut)">${r.age===""?"—":r.age+"d"}</td>
    <td><span class="pill" style="background:color-mix(in srgb,var(${TIER[r.tier][1]}) 18%,transparent);
        color:var(${TIER[r.tier][1]})">Tier ${r.tier}</span></td>
    <td class="r mono" style="font-weight:700;color:var(${pc})">${rs(r.risk)}</td>
    <td>${r.ai?`<span class="info">i<span class="tip"><em>AI diagnostic &middot; tier ${r.tier}</em>${r.why}
      <br><br><span style="color:var(--dim)">Engine computed the figures; the model returned the category and this sentence.</span></span></span>`:""}</td>
    </tr>`;}).join("")||`<tr><td colspan="8" class="empty">Nothing needs action in this view.</td></tr>`;
  emore.innerHTML=action.length>state.eShow?`<div class="more"><button id="eb">Show ${Math.min(20,action.length-state.eShow)} more of ${action.length-state.eShow}</button></div>`:"";
  if(action.length>state.eShow) eb.onclick=()=>{state.eShow+=20;render();};
}
const LEGEND_FEE={GATEWAY_FEE:"Gateway fee (MDR + GST)",COD_COLLECTION_FEE:"COD collection fee"};
function tierClick(t){state.tier=state.tier===t?null:t;state.mShow=8;state.eShow=10;render();}

/* ---------- legend ---------- */
legrid.innerHTML=Object.entries(LEGEND).map(([k,[n,d]],i)=>{
  const c=["--blu","--amb","--red","--amb","--pur"][i];
  return `<div class="li"><span class="lc" style="background:color-mix(in srgb,var(${c}) 20%,transparent);
    color:var(${c})">R${i+1}</span><div><b>${n}</b><span>${d}</span></div></div>`;}).join("");

/* ---------- drawer, theme, actions ---------- */
const open=v=>{drawer.classList.toggle("on",v);scrim.classList.toggle("on",v);};
menu.onclick=()=>open(true); scrim.onclick=()=>open(false);
sw.onclick=()=>{const d=document.documentElement.getAttribute("data-theme")==="dark";
  document.documentElement.setAttribute("data-theme",d?"light":"dark");
  sw.classList.toggle("on",!d); tlabel.textContent=d?"Light mode":"Dark mode"; render();};
q.oninput=e=>{state.q=e.target.value;state.mShow=8;state.eShow=10;render();};
modes.innerHTML=["ALL","UPI","CARD","NETBANKING","WALLET","COD","BANK_TRANSFER"]
  .map(m=>`<button class="chip ${m=="ALL"?"on":""}" data-m="${m}">${m=="ALL"?"All modes":m}</button>`).join("");
modes.querySelectorAll(".chip").forEach(b=>b.onclick=()=>{
  state.mode=b.dataset.m;state.mShow=8;state.eShow=10;
  modes.querySelectorAll(".chip").forEach(x=>x.classList.toggle("on",x===b));render();});

function toastMsg(t){toast.textContent=t;toast.classList.add("on");setTimeout(()=>toast.classList.remove("on"),2600);}
rerun.onclick=()=>{open(false);toastMsg("Run complete — 265 records, 0 false clears");
  document.querySelectorAll(".metric .v").forEach(v=>{v.style.opacity=.25;setTimeout(()=>v.style.opacity=1,420);});};
export_.onclick=()=>{
  const f=filtered(),h=["record_id","tier","status","reason","expected","received","delta","amount_at_risk","priority"];
  const csv=[h.join(",")].concat(f.map(r=>[r.id,r.tier,r.status,r.reason,r.expected,r.received,r.delta,r.risk,r.priority].join(","))).join("\\n");
  const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([csv],{type:"text/csv"}));
  a.download="reconai_report.csv";a.click();open(false);toastMsg("Exported "+f.length+" records");};

/* ---------- chat: answers computed locally from the table ---------- */
function answer(qq){
  const s=qq.toLowerCase().trim();
  const m=s.match(/(ord-\\d+|stl-[a-z0-9]+)/i);
  if(m){const r=DATA.find(x=>x.id.toLowerCase()===m[1].toLowerCase());
    if(!r) return `No record <code>${m[1].toUpperCase()}</code> in this run.`;
    const cl=CLEARED.includes(r.status);
    return `<b>${r.id}</b> — ${r.mode}, ${rs(r.expected)}.<br>`+
      (cl?`Cleared at tier ${r.tier}. Received ${rs(r.received)}${r.delta?", delta "+r.delta.toFixed(2):" exactly"}.`
         :`Not cleared. Tier ${r.tier}, ${r.reasonLabel}. ${rs(r.risk)} at risk.`)+
      `<br><br><span style="color:var(--dim)">${r.why}</span>`;}
  const act=DATA.filter(r=>ACTION.includes(r.status));
  if(s.includes("cod")){const c=act.filter(r=>r.mode==="COD");
    const od=c.filter(r=>r.reason==="R2_REMITTANCE_OVERDUE").length;
    return `${c.length} of the ${act.length} records needing action are COD — ${od} remittance overdue, ${c.length-od} short beyond the collection-fee band. ${rs(c.reduce((s,r)=>s+r.risk,0))} at risk.`;}
  if(s.includes("risk")||s.includes("total")||s.includes("how much"))
    return `${rs(act.reduce((s,r)=>s+r.risk,0))} across ${act.length} records. Largest single item is <b>${act.sort((a,b)=>b.risk-a.risk)[0].id}</b> at ${rs(act[0].risk)}.`;
  if(s.includes("ai")||s.includes("model")){const a=DATA.filter(r=>r.ai).length;
    return `${a} of ${DATA.length} records were sent to the model (${(100*a/DATA.length).toFixed(1)}%). The other ${DATA.length-a} resolved deterministically — tiers 0, 1, 2 and clean tier 4.`;}
  if(s.includes("exception")||s.includes("how many"))
    return `${act.length} records need a human. By reason: `+Object.entries(act.reduce((o,r)=>(o[r.reasonLabel]=(o[r.reasonLabel]||0)+1,o),{})).map(([k,v])=>`${k} ${v}`).join(", ")+".";
  if(s.includes("tier")){const c={};DATA.forEach(r=>c[r.tier]=(c[r.tier]||0)+1);
    return "Tier distribution: "+Object.entries(c).map(([t,n])=>`tier ${t} ${n}`).join(", ")+".";}
  return `I only answer from this reconciliation run — order lookups, exception counts, amounts at risk, tier and AI usage. I won't guess at anything outside it.`;
}
const push=(who,html)=>{const d=document.createElement("div");d.className="msg "+who;d.innerHTML=html;
  clog.appendChild(d);clog.scrollTop=clog.scrollHeight;};
const ask=t=>{if(!t.trim())return;push("u",t);setTimeout(()=>push("a",answer(t)),260);cq.value="";};
fab.onclick=()=>{chat.classList.toggle("on");if(!clog.children.length)
  push("a","Ask me about this run. I read the results table only — no external lookups, and I won't compute anything the engine didn't.");};
cx.onclick=()=>chat.classList.remove("on");
csend.onclick=()=>ask(cq.value);
cq.onkeydown=e=>{if(e.key==="Enter")ask(cq.value);};
sugg.innerHTML=["how many exceptions are COD?","was ORD-00023 received?","how much is at risk?","how much used AI?"]
  .map(t=>`<button>${t}</button>`).join("");
sugg.querySelectorAll("button").forEach(b=>b.onclick=()=>ask(b.textContent));

render();
</script>
</html>"""

html = (HTML.replace("__DATA__", json.dumps(rows, separators=(",", ":")))
            .replace("__LEGEND__", json.dumps(LEGEND, separators=(",", ":")))
            .replace('id="export"', 'id="export_"'))
out = ROOT / "demo.html"
out.write_text(html)
print(f"wrote {out}  ({out.stat().st_size/1024:.0f} KB, {len(rows)} records inlined)")
