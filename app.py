"""
Ledgr — reconciliation dashboard.

All reconciliation happens in engine.py. This file imports load() and
reconcile() and only displays what they return.

Flow:  entry (scroll to choose source)  ->  dashboard (zeros)  ->  results

Run:  streamlit run app.py
"""
import html
import os
import re
import io
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import tempfile
import time
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import engine
from config import (REASON_LEGEND, TIER_NAMES, to_paise,
                    to_rupees, fmt)
from engine import load, reconcile
from schema_map import (map_columns, NEED_ORDERS, NEED_SETTLEMENTS,
                        ORDER_TARGETS, SETTLEMENT_TARGETS, unused_columns,
                        missing_required)

# Wall-clock "today" in India. The as-at picker and the settlement graph
# cannot move past this — no future dates, no future money.
TODAY = datetime.now(ZoneInfo("Asia/Kolkata")).date()

st.set_page_config(page_title="Ledgr", page_icon="L", layout="wide",
                   initial_sidebar_state="collapsed")

CLEARED = ["AUTO_CLEARED", "CLEARED_WITH_FEE"]
INFLIGHT = ["AWAITING_REMITTANCE", "APPROACHING_THRESHOLD"]
FEE_LABEL = {"GATEWAY_FEE": "Payment processing fee",
             "COD_COLLECTION_FEE": "Cash collection fee", "": ""}

INK, BODY, DIM = "#0C0E12", "#4B5563", "#8A9099"
LINE, BG, SOFT = "#E5E7EB", "#FFFFFF", "#FAFAFA"
ACC, ACC_D = "#1A56DB", "#1443B0"          # the single accent
MATCHED, WAITING = "#0E7C5A", "#8A9099"    # status only
REVIEW = "#6941C6"                          # AI-flagged, resolvable
WARN, WARN_BG, WARN_BD = "#B42318", "#FEF3F2", "#FDA29B"
TIER_TONE = {0: (WAITING, .70), 1: (MATCHED, 1), 2: (MATCHED, .62),
             3: (REVIEW, 1), 4: (MATCHED, .80), 5: (WARN, 1)}

ss = st.session_state
for k, v in dict(source=None, datadir=None, results=None, runs=0, ms=None,
                 menu=False, q="",
                 status="All statuses", chat_open=False, ask="",
                 asat=TODAY, dfrom=None, dto=None, pick=None,
                 reason=None, jump=False, jumps=0, focus=None,
                 resolve_id=None, contact_id=None, hide_resolved=None, land_top=False, pending=None,
                 up_o=None, up_s=None, filt_open=False, filt_gen=0).items():
    ss.setdefault(k, v)

st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html,body,.stApp,[class*="css"]{{font-family:'Inter',-apple-system,BlinkMacSystemFont,
 'Segoe UI',Roboto,sans-serif;-webkit-font-smoothing:antialiased}}
.stApp{{color:{INK};background:{SOFT}}}
.block-container{{padding:2rem 3rem 7rem;max-width:1240px}}
#MainMenu,footer{{visibility:hidden;height:0}}
header[data-testid="stHeader"]{{background:transparent;height:0}}
h1,h2,h3,p,span,div,label{{color:{INK}}}

/* ---- inputs, light and legible ------------------------------------------*/
.stTextInput input,.stTextArea textarea{{background:{BG}!important;color:{INK}!important;
 border:1px solid {LINE}!important;border-radius:7px!important;font-size:13.5px!important}}
.stTextInput input::placeholder{{color:{DIM}!important;opacity:1!important}}
.stTextInput input:focus{{border-color:{ACC}!important;
 box-shadow:0 0 0 3px rgba(26,86,219,.14)!important}}
div[data-baseweb="select"]>div{{background:{BG}!important;color:{INK}!important;
 border:1px solid {LINE}!important;border-radius:7px!important;font-size:13px!important;
 white-space:nowrap;cursor:pointer!important}}
div[data-baseweb="select"] div[title]{{overflow:visible!important;
 text-overflow:clip!important;max-width:none!important}}
div[data-baseweb="select"] *{{color:{INK}!important}}
div[data-baseweb="select"] svg{{fill:{DIM}!important}}
div[data-baseweb="select"] input{{caret-color:transparent!important;
 user-select:none!important;-webkit-user-select:none!important;
 pointer-events:none!important}}
div[data-baseweb="select"] input::selection{{background:transparent!important}}
div[data-baseweb="popover"] div[data-baseweb="menu"],
div[data-baseweb="popover"] ul[role="listbox"]{{background:{BG}!important;
 border:1px solid {LINE}!important;border-radius:9px!important;
 box-shadow:0 6px 18px rgba(12,14,18,.10)!important}}
div[data-baseweb="popover"] li[role="option"]{{background:{BG}!important;
 color:{INK}!important;font-size:14px!important}}
div[data-baseweb="popover"] li[role="option"]:hover,
div[data-baseweb="popover"] li[aria-selected="true"]{{background:{SOFT}!important}}
[data-testid="stFileUploaderDropzone"]{{background:{BG};
 border:1px dashed {LINE};border-radius:8px}}
[data-testid="stFileUploaderDropzone"] *{{color:{BODY}!important}}
div[data-testid="stDataFrame"]{{border:1px solid {LINE};border-radius:10px;
 background:{BG}}}

/* ---- buttons: white, fill with colour on hover --------------------------*/
.stButton button,.stDownloadButton button{{border-radius:7px;font-size:13.5px;
 font-weight:500;padding:.66rem 1.2rem;border:1px solid {LINE};
 background:{BG};color:{INK};width:100%;
 transition:background .18s,color .18s,border-color .18s,transform .18s,box-shadow .18s}}
.stButton button:hover,.stDownloadButton button:hover{{background:{ACC};color:#fff;
 border-color:{ACC};transform:translateY(-1px);
 box-shadow:none}}
.stButton button:hover *,.stDownloadButton button:hover *{{color:#fff!important}}
.stButton button:active{{transform:none;background:{ACC_D};border-color:{ACC_D}}}

/* ---- entry screen -------------------------------------------------------*/
/* the wordmark is a sticky bar spanning the whole entry page, so it can
   shrink into a header as the page scrolls */
.st-key-brandbar{{position:sticky;top:0;z-index:20;background:{SOFT};
 padding:26px 0 10px;border-bottom:1px solid transparent}}
.st-key-brandbar .wordmark{{font-size:92px;font-weight:600;letter-spacing:-.055em;
 line-height:1;margin:0;transform-origin:left center;white-space:nowrap}}

@keyframes shrinkmark{{
 from{{font-size:92px;letter-spacing:-.055em}}
 to{{font-size:25px;letter-spacing:-.03em}}}}
@keyframes barline{{
 from{{border-bottom-color:transparent;padding-top:26px;padding-bottom:10px}}
 to{{border-bottom-color:{LINE};padding-top:14px;padding-bottom:12px}}}}
@keyframes fadeaway{{
 0%{{opacity:1;transform:none}}
 100%{{opacity:0;transform:translateY(-16px)}}}}

@supports (animation-timeline:scroll()){{
 .st-key-brandbar .wordmark{{animation:shrinkmark linear both;
  animation-timeline:scroll(nearest);animation-range:0 260px}}
 .st-key-brandbar{{animation:barline linear both;
  animation-timeline:scroll(nearest);animation-range:0 260px}}
 .herobody{{animation:fadeaway linear both;
  animation-timeline:scroll(nearest);animation-range:0 220px}}
}}
@supports not (animation-timeline:scroll()){{
 .st-key-brandbar{{position:static}}
}}

.hero{{min-height:58vh;display:flex;flex-direction:column;justify-content:center}}
.tag{{font-size:25px;font-weight:400;letter-spacing:-.02em;line-height:1.4;
 max-width:660px;margin:0 0 18px}}
.lede{{font-size:16px;color:{BODY};line-height:1.75;max-width:540px}}
.hint{{margin-top:12vh;font-size:13px;color:{DIM};letter-spacing:.03em;
 display:flex;align-items:center;gap:9px}}
.hint b{{font-weight:500;color:{BODY}}}
@keyframes bob{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(5px)}}}}
.hint span{{animation:bob 1.9s ease-in-out infinite}}

@keyframes rise{{from{{opacity:0;transform:translateY(30px)}}to{{opacity:1;transform:none}}}}
@supports (animation-timeline:view()){{
 .st-key-choices,.reveal{{animation:rise linear both;animation-timeline:view();
  animation-range:entry 6% cover 30%}}}}
.card{{border:1px solid {LINE};border-radius:8px;padding:26px 26px 4px;
 background:{BG}}}
.card h4{{font-size:21px;font-weight:600;letter-spacing:-.025em;margin:0 0 8px}}
.card p{{font-size:14px;color:{BODY};line-height:1.65;margin:0 0 20px;min-height:44px}}

/* ---- dashboard ----------------------------------------------------------*/
.brand{{font-size:25px;font-weight:600;letter-spacing:-.035em;display:flex;
 align-items:center;gap:11px}}
.st-key-backhome button{{width:auto!important;min-width:36px!important;
 min-height:32px!important;height:32px!important;padding:0 .55rem!important;
 font-size:16px!important;line-height:1!important}}
.brandsub{{font-size:12.5px;color:{DIM};margin-top:4px}}
.flab{{font-size:10.5px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;
 color:{DIM};margin:0 0 6px;height:14px}}
.st-key-asatbox [data-testid="stDateInput"] div[data-baseweb="input"]>div,
.st-key-asatbox input{{min-height:42px!important}}
.st-key-runbox .stButton button{{min-height:42px!important;margin-top:0!important}}

.sec{{font-size:11.5px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;
 color:{DIM};margin:50px 0 18px}}
.panel{{border:1px solid {LINE};border-radius:8px;padding:6px 18px 2px;
 background:{BG};margin-top:16px}}
.figs{{display:flex;gap:52px;flex-wrap:wrap;align-items:flex-start}}
.fig .n{{font-size:35px;font-weight:600;letter-spacing:-.03em;line-height:1.15}}
.fig .l{{font-size:13.5px;color:{BODY};margin-top:5px}}
.fig .t{{font-size:12px;color:{DIM};margin-top:2px}}
.alert{{border:1px solid {WARN_BD};background:{WARN_BG};border-radius:8px;
 padding:12px 18px 14px;margin-top:-13px}}
.alert .n{{font-size:35px;font-weight:600;letter-spacing:-.03em;color:{WARN};
 line-height:1.15;display:flex;align-items:center;gap:9px}}
.alert .l{{font-size:13.5px;color:{WARN};font-weight:500;margin-top:4px}}
.alert .t{{font-size:12px;color:{WARN};opacity:.85;margin-top:2px}}
.bang{{width:21px;height:21px;border-radius:50%;background:{WARN};color:{WARN_BG};
 font-size:13px;font-weight:700;display:inline-grid;place-items:center;flex:none}}
.idle{{color:{DIM}!important}}
.statrow{{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px;max-width:280px}}
.stat{{display:inline-flex;align-items:center;border-radius:999px;padding:3px 9px;
 font-size:11px;font-weight:500;letter-spacing:.01em;font-variant-numeric:tabular-nums;
 line-height:1.35;white-space:nowrap}}
.stat b{{font-weight:600;margin-right:5px}}
.stat.short{{color:{WARN};background:{WARN_BG};border:1px solid {WARN_BD}}}
.stat.over{{color:#B54708;background:#FFFAEB;border:1px solid #F7C948}}

/* ---- bar chart ----------------------------------------------------------*/
.chart{{border:1px solid {LINE};border-radius:8px;background:{BG};
 padding:26px 30px 20px}}
.dbars{{display:flex;align-items:flex-end;gap:3px;height:78px}}
.dbar{{flex:1;height:100%;display:flex;align-items:flex-end;position:relative;
 cursor:default}}
.dfill{{width:100%;border-radius:2px 2px 0 0;min-height:3px;transition:filter .12s}}
.dbar:hover .dfill{{filter:brightness(.82)}}
.dbar .tip{{display:none;position:absolute;bottom:100%;left:50%;
 transform:translateX(-50%);background:{INK};color:#fff;padding:7px 10px;
 border-radius:6px;font-size:11.5px;line-height:1.45;white-space:nowrap;
 z-index:60;margin-bottom:8px;box-shadow:0 6px 18px rgba(12,14,18,.22);
 pointer-events:none}}
.dbar .tip b{{color:#fff;font-weight:600;display:block;font-size:12.5px}}
.dbar .tip::after{{content:"";position:absolute;top:100%;left:50%;
 transform:translateX(-50%);border:5px solid transparent;border-top-color:{INK}}}
.dbar:hover .tip{{display:block}}
.dbar:first-child .tip{{left:0;transform:none}}
.dbar:first-child .tip::after{{left:14px}}
.dbar:last-child .tip{{left:auto;right:0;transform:none}}
.dbar:last-child .tip::after{{left:auto;right:14px}}
/* outcome + reason cards: count / label / amount are three distinct tiers.
   The Streamlit button is an invisible hit-target over the painted face. */
.oc-card{{border:1px solid {LINE};border-radius:9px;padding:16px 16px 14px;
 height:148px;min-height:148px;box-sizing:border-box;display:flex;flex-direction:column;background:{BG};
 transition:border-color .15s,box-shadow .15s,transform .15s}}
.oc-top{{display:flex;align-items:center;gap:8px;line-height:1}}
.oc-ico{{font-size:20px;line-height:1;flex:none}}
.oc-n{{font-size:34px;font-weight:600;letter-spacing:-.03em;line-height:1.05}}
.oc-l{{font-size:13.5px;font-weight:500;color:{BODY};margin-top:8px;line-height:1.35;min-height:2.7em}}
.oc-a{{margin-top:auto;padding-top:10px;border-top:1px solid {LINE};
 font-size:13px;font-weight:500;color:{WARN};font-variant-numeric:tabular-nums}}
.oc-matched{{border-color:{MATCHED}44;background:{MATCHED}0F}}
.oc-matched .oc-n,.oc-matched .oc-ico{{color:{MATCHED}}}
.oc-waiting{{border-color:{WAITING}55;background:{WAITING}12}}
.oc-waiting .oc-n,.oc-waiting .oc-ico{{color:{BODY}}}
.oc-look{{border-color:{WARN}40;background:{WARN}0D}}
.oc-look .oc-n,.oc-look .oc-ico{{color:{WARN}}}
.oc-all{{border-style:dashed;background:{BG}}}
.oc-all .oc-n,.oc-all .oc-ico,.oc-all .oc-l{{color:{DIM}}}
.oc-matched.on{{background:{MATCHED};border-color:{MATCHED}}}
.oc-matched.on .oc-n,.oc-matched.on .oc-ico,.oc-matched.on .oc-l{{color:#fff}}
.oc-waiting.on{{background:{WAITING};border-color:{WAITING}}}
.oc-waiting.on .oc-n,.oc-waiting.on .oc-ico,.oc-waiting.on .oc-l{{color:#fff}}
.oc-look.on{{background:{WARN};border-color:{WARN}}}
.oc-look.on .oc-n,.oc-look.on .oc-ico,.oc-look.on .oc-l{{color:#fff}}
.oc-look.on .oc-a{{color:#fff;border-top-color:rgba(255,255,255,.28)}}
.st-key-oc_matched:hover .oc-card,.st-key-oc_waiting:hover .oc-card,
.st-key-oc_look:hover .oc-card,.st-key-oc_all:hover .oc-card,
div[class*="st-key-rg_"]:hover .oc-card{{transform:translateY(-1px);
 box-shadow:0 4px 12px rgba(12,14,18,.06)}}
.st-key-oc_all:hover .oc-card{{border-color:{ACC}}}
.st-key-oc_all:hover .oc-n,.st-key-oc_all:hover .oc-ico,
.st-key-oc_all:hover .oc-l{{color:{ACC}}}
/* Button stays in the document flow so Streamlit actually receives the click.
   The painted face sits on top of it and lets the click pass through. */
.st-key-oc_matched,.st-key-oc_waiting,.st-key-oc_look,.st-key-oc_all,
div[class*="st-key-rg_"]{{position:relative;cursor:pointer}}
.st-key-oc_matched [data-testid="stVerticalBlock"],
.st-key-oc_waiting [data-testid="stVerticalBlock"],
.st-key-oc_look [data-testid="stVerticalBlock"],
.st-key-oc_all [data-testid="stVerticalBlock"],
div[class*="st-key-rg_"] [data-testid="stVerticalBlock"]{{gap:0!important}}
.st-key-oc_matched .stButton button,.st-key-oc_waiting .stButton button,
.st-key-oc_look .stButton button,.st-key-oc_all .stButton button,
div[class*="st-key-rg_"] .stButton button{{
 min-height:148px!important;width:100%!important;opacity:0!important;
 cursor:pointer!important;border:none!important;background:transparent!important;
 box-shadow:none!important;transform:none!important;padding:0!important}}
.st-key-oc_matched [data-testid="stElementContainer"]:has(.oc-card),
.st-key-oc_waiting [data-testid="stElementContainer"]:has(.oc-card),
.st-key-oc_look [data-testid="stElementContainer"]:has(.oc-card),
.st-key-oc_all [data-testid="stElementContainer"]:has(.oc-card),
div[class*="st-key-rg_"] [data-testid="stElementContainer"]:has(.oc-card){{
 height:0!important;min-height:0!important;overflow:visible!important;
 margin:0!important;padding:0!important}}
.st-key-oc_matched [data-testid="stMarkdownContainer"],
.st-key-oc_waiting [data-testid="stMarkdownContainer"],
.st-key-oc_look [data-testid="stMarkdownContainer"],
.st-key-oc_all [data-testid="stMarkdownContainer"],
div[class*="st-key-rg_"] [data-testid="stMarkdownContainer"]{{
 position:relative;margin-top:-148px!important;pointer-events:none!important;
 z-index:1}}
.st-key-oc_matched [data-testid="stMarkdownContainer"] p,
.st-key-oc_waiting [data-testid="stMarkdownContainer"] p,
.st-key-oc_look [data-testid="stMarkdownContainer"] p,
.st-key-oc_all [data-testid="stMarkdownContainer"] p,
div[class*="st-key-rg_"] [data-testid="stMarkdownContainer"] p{{margin:0}}
.oc-card{{pointer-events:none}}
.jump-to{{scroll-margin-top:18px;border-radius:6px}}
@keyframes ledgrflash{{
 0%{{background:rgba(26,86,219,.12)}}
 35%{{background:rgba(26,86,219,.07)}}
 100%{{background:transparent}}}}
.ledgr-flash{{animation:ledgrflash .85s ease-out}}


/* active filter chip */
.chip{{display:inline-flex;align-items:center;gap:9px;background:{ACC}12;
 border:1px solid {ACC}55;color:{ACC};border-radius:20px;padding:7px 15px;
 font-size:13px;font-weight:600}}
.chip s{{text-decoration:none;color:{ACC};opacity:.6;font-weight:400}}
.tier{{display:inline-block;font-size:9.5px;font-weight:600;letter-spacing:.04em;
 padding:1px 6px;border-radius:4px;border:1px solid {LINE};color:{DIM}}}
.gamt{{text-align:right;font-variant-numeric:tabular-nums;font-size:14px;
 color:{WARN};padding-top:10px;font-weight:500}}
.bars{{display:flex;align-items:flex-end;gap:22px;height:230px;
 border-bottom:1px solid {LINE};padding-bottom:2px}}
.bcol{{flex:1;display:flex;flex-direction:column;justify-content:flex-end;
 align-items:center;height:100%}}
.bval{{font-size:15px;font-weight:600;margin-bottom:8px;font-variant-numeric:tabular-nums}}
.bfill{{width:100%;max-width:88px;border-radius:4px 4px 0 0;min-height:3px;
 transition:filter .18s}}
.bcol:hover .bfill{{filter:brightness(1.12) saturate(1.15)}}
.blabs{{display:flex;gap:22px;padding-top:13px}}
.blab{{flex:1;text-align:center}}
.blab .k{{font-size:13px;font-weight:600}}
.blab .v{{font-size:11.5px;color:{DIM};line-height:1.35;margin-top:3px}}

/* ---- tables / lists -----------------------------------------------------*/
table.t{{width:100%;border-collapse:collapse;table-layout:fixed;font-size:13.5px;
 border:none!important}}
table.t th,table.t td{{border:none!important;border-bottom:1px solid {LINE}!important;
 background:transparent!important}}
table.t th{{text-align:left;font-size:10.5px;font-weight:600;letter-spacing:.07em;
 text-transform:uppercase;color:{DIM};padding:0 12px 10px 0}}
table.t td{{padding:12px 12px 12px 0;vertical-align:top}}
table.t tr:last-child td{{border-bottom:none!important}}
table.t th.num,table.t td.num,.num{{text-align:right!important;
 font-variant-numeric:tabular-nums;padding-right:0!important}}
.sub{{font-size:12px;color:{DIM};margin-top:3px}}
.tg{{display:inline-block;font-size:10.5px;font-weight:500;padding:2px 7px;
 border-radius:5px;background:{SOFT};border:1px solid {LINE};color:{BODY}}}
.mt{{color:{MATCHED}}} .wn{{color:{WARN}}} .wt{{color:{WAITING}}} .muted{{color:{BODY}}}
details.ld{{border:1px solid {LINE};border-radius:8px;
 background:{BG};padding:0 20px;margin-bottom:14px}}
details.ld>summary{{cursor:pointer;list-style:none;padding:18px 0;
 font-size:15px;font-weight:600;display:flex;align-items:center;gap:10px}}
details.ld>summary::-webkit-details-marker{{display:none}}
details.ld>summary::after{{content:"▾";margin-left:auto;color:{DIM};font-size:13px;
 transition:transform .2s}}
details.ld[open]>summary::after{{transform:rotate(180deg)}}
details.ld>summary small{{font-weight:400;color:{DIM};font-size:12.5px}}
details.ld .inner{{padding-bottom:18px;border-top:1px solid {LINE};padding-top:6px}}

/* ---- assistant ----------------------------------------------------------*/
.st-key-asklaunch{{position:fixed;bottom:24px;right:24px;z-index:1001;width:auto}}
.st-key-asklaunch button{{width:auto!important;border-radius:7px!important;
 padding:.7rem 1.35rem!important;background:{INK}!important;
 border:1px solid {INK}!important;box-shadow:none!important;
 font-weight:500!important;font-size:14px!important}}
.st-key-asklaunch button,.st-key-asklaunch button *,
.st-key-asklaunch button p,.st-key-asklaunch button div{{color:#FFFFFF!important}}
.st-key-asklaunch button:hover{{background:{ACC}!important;border-color:{ACC}!important;
 transform:translateY(-1px)}}
.st-key-asklaunch button:hover *{{color:#FFFFFF!important}}
.st-key-askpanel{{position:fixed;bottom:78px;right:24px;z-index:1000;width:372px;
 background:{BG};border:1px solid {LINE};border-radius:8px;padding:18px 18px 8px;
 box-shadow:0 8px 24px rgba(12,14,18,.10)}}
.st-key-askpanel .stButton button{{font-size:12px;padding:.36rem .6rem;
 border-radius:6px;color:{BODY}}}

/* ---- manual resolution -----------------------------------------------*/
.oktag{{display:inline-block;font-size:10.5px;font-weight:600;color:{MATCHED};
 background:{MATCHED}14;border:1px solid {MATCHED}44;border-radius:5px;
 padding:2px 7px;margin-left:7px;vertical-align:middle}}
.dimrow{{opacity:.55}}
.rrow{{display:grid;grid-template-columns:.42fr 1.45fr .7fr .85fr 1.55fr .8fr .75fr 1fr;
 gap:10px;align-items:start;padding:12px 0;border-bottom:1px solid {LINE};
 font-size:13.5px}}
.rrow .sno{{color:{DIM};font-variant-numeric:tabular-nums;font-size:13px;padding-top:2px}}
.rrow.head{{font-size:10.5px;font-weight:600;letter-spacing:.07em;
 text-transform:uppercase;color:{DIM};padding:0 0 10px;border-bottom:1px solid {LINE}}}
.rrow.head .num,.rrow .num{{text-align:right}}
div[class*="st-key-rv_"] button,div[class*="st-key-cf_"] button,
div[class*="st-key-ct_"] button,div[class*="st-key-acts_"] button{{
 width:100%!important;font-size:12px!important;padding:0 .55rem!important;
 min-height:32px!important;height:32px!important;white-space:nowrap!important}}
div[class*="st-key-rv_"],div[class*="st-key-ct_"],div[class*="st-key-acts_"]{{
 margin:0!important}}
div[class*="st-key-acts_"] [data-testid="stHorizontalBlock"]{{
 gap:6px!important;align-items:center!important}}
div[class*="st-key-acts_"] [data-testid="stVerticalBlock"]{{gap:0!important}}
.ccard{{border:1px solid {LINE};border-left:3px solid {ACC};border-radius:8px;
 background:{BG};padding:14px 16px 8px;margin:8px 0 12px}}
.ccard .ch{{font-size:12.5px;font-weight:600;margin:0 0 12px}}
.ccard .ck{{font-size:10.5px;font-weight:600;letter-spacing:.07em;
 text-transform:uppercase;color:{DIM};margin-bottom:2px}}
.ccard .cv{{font-size:14px;font-weight:500;margin-bottom:10px}}
.ccard .warnline{{font-size:13.5px;color:{WARN};font-weight:500}}
.st-key-restog button{{font-size:12.5px!important;padding:.45rem .85rem!important}}
.fbox{{border:1px solid {LINE};border-radius:8px;background:{BG};padding:14px 18px 8px;
 margin:8px 0 18px}}
.st-key-filtbox [data-testid="stCheckbox"] label p{{font-size:13px!important;color:{INK}!important}}
.st-key-filttrig .stButton button{{min-height:40px!important;white-space:nowrap!important;
 padding:.66rem .75rem!important}}
.st-key-filtdrop{{border:1px solid {LINE};border-radius:9px;background:{BG};
 padding:16px 18px 10px;margin:6px 0 12px;
 box-shadow:0 8px 24px rgba(12,14,18,.10)}}
.st-key-filtdrop [data-testid="stCheckbox"] label p{{font-size:13px!important;color:{INK}!important}}
.st-key-load_orders,.st-key-load_setls{{border:1px solid {LINE};border-radius:9px;
 background:{BG};padding:22px 22px 14px;
 box-shadow:0 1px 3px rgba(12,14,18,.05)}}
.st-key-load_orders [data-testid="stVerticalBlock"],
.st-key-load_setls [data-testid="stVerticalBlock"]{{gap:.55rem!important}}
.st-key-actfil [data-testid="stHorizontalBlock"]{{flex-wrap:wrap!important;gap:8px!important}}
.st-key-actfil .stButton button{{width:auto!important;min-width:0!important;
 border-radius:20px!important;padding:.38rem .9rem!important;font-size:12.5px!important;
 min-height:32px!important;font-weight:600!important;background:{ACC}12!important;
 border:1px solid {ACC}55!important;color:{ACC}!important}}
.st-key-actfil .stButton button:hover{{background:{ACC}!important;color:#fff!important;
 border-color:{ACC}!important}}
.st-key-actfil .st-key-clearall button{{background:{BG}!important;color:{BODY}!important;
 border:1px solid {LINE}!important;font-weight:500!important}}
</style>""", unsafe_allow_html=True)


def only_cols(df, cols):
    """Pick columns that actually exist so uploaded files cannot crash the table."""
    return df[[c for c in cols if c in df.columns]]


def soften_inputs(odf, sdf):
    """Optional columns the demo has but a user's CSV may not."""
    odf, sdf = odf.copy(), sdf.copy()
    odf.columns = [str(c).strip() for c in odf.columns]
    sdf.columns = [str(c).strip() for c in sdf.columns]
    if "customer_name" not in odf.columns:
        odf["customer_name"] = ""
    if "source" not in sdf.columns:
        sdf["source"] = ""
    if "narration" not in sdf.columns:
        sdf["narration"] = ""
    return odf, sdf


DEMO_DATA = str(Path(__file__).parent / "data")


def demo_mode():
    """True on Streamlit Cloud when DEMO_MODE=1. Local default is off."""
    if os.environ.get("DEMO_MODE", "").strip().lower() in ("1", "true", "yes"):
        return True
    try:
        v = st.secrets.get("DEMO_MODE", "")
    except Exception:
        return False
    return str(v).strip().lower() in ("1", "true", "yes")


def go_demo():
    """Only flags the transition. The wait screen does the actual switch."""
    st.session_state.pending = "demo"


def ask_run():
    st.session_state.pending = "run"


def go_upload():
    st.session_state.source = "upload_pending"
    st.session_state.land_top = True


def _clear_colmap_keys():
    for k in [k for k in st.session_state.keys() if str(k).startswith("cmap_")]:
        del st.session_state[k]


MODE_CHOICES = ["BANK_TRANSFER", "Bank credit", "CARD", "COD",
                "NETBANKING", "UPI", "WALLET"]
SIDE_LABEL = {"short": "Shortfall", "over": "Overpaid / unexplained"}


def _reset_filter_widgets():
    """Default: no mode / amount-type / status checks.

    Bump filt_gen so open-panel checkboxes remount unchecked. Writing the
    old widget keys while they are on screen leaves the ticks in place.
    """
    ss = st.session_state
    ss.keep_modes = []
    ss.keep_sides = []
    ss.hide_resolved = None
    ss._filt_restored = False
    ss.filt_gen = int(ss.filt_gen or 0) + 1


def _filt_key(prefix, name=""):
    return f"{prefix}{int(st.session_state.filt_gen or 0)}_{name}"


def _on_hide_resolved():
    ss = st.session_state
    hide_k, show_k = _filt_key("st", "hide"), _filt_key("st", "show")
    if ss[hide_k]:
        ss[show_k] = False
        ss.hide_resolved = True
    else:
        ss.hide_resolved = False if ss[show_k] else None


def _on_show_resolved():
    ss = st.session_state
    hide_k, show_k = _filt_key("st", "hide"), _filt_key("st", "show")
    if ss[show_k]:
        ss[hide_k] = False
        ss.hide_resolved = False
    else:
        ss.hide_resolved = True if ss[hide_k] else None


def change_source():
    """Back to Use demo data / Upload files. One place for that reset."""
    ss = st.session_state
    ss.source = None
    ss.datadir = None
    ss.results = None
    ss.pick = None
    ss.reason = None
    ss.q = ""
    _reset_filter_widgets()
    ss.contact_id = None
    ss.resolve_id = None
    ss.dfrom = None
    ss.dto = None
    ss.ask = ""
    ss.chat_open = False
    ss.pending = None
    ss.up_o = None
    ss.up_s = None
    ss.filt_open = False
    _clear_colmap_keys()
    ss.land_top = True


def back_to_files():
    """Remap screen → file pickers."""
    ss = st.session_state
    ss.source = "upload_pending"
    ss.up_o = None
    ss.up_s = None
    _clear_colmap_keys()
    ss.land_top = True


def accept_upload(odf, sdf):
    """Soften, write mapped frames, enter the pre-run inspection."""
    odf, sdf = soften_inputs(odf, sdf)
    miss_o = missing_required(odf, NEED_ORDERS)
    miss_s = missing_required(sdf, NEED_SETTLEMENTS)
    if miss_o or miss_s:
        return False, miss_o, miss_s
    tmp = tempfile.mkdtemp(prefix="ledgr_")
    odf.to_csv(Path(tmp, "orders.csv"), index=False)
    sdf.to_csv(Path(tmp, "settlements.csv"), index=False)
    engine.DATA = tmp
    load()
    ss = st.session_state
    ss.datadir, ss.source, ss.results = tmp, "upload", None
    ss.up_o, ss.up_s = None, None
    _clear_colmap_keys()
    ss.land_top = True
    return True, [], []


def wait_screen(title, sub):
    st.markdown(
        f'<div style="min-height:72vh;display:flex;flex-direction:column;'
        f'justify-content:center">'
        f'<div class="brand">Ledgr</div>'
        f'<div style="font-size:28px;font-weight:600;letter-spacing:-.03em;'
        f'margin-top:32px">{title}</div>'
        f'<div class="sub" style="margin-top:10px;font-size:15px;max-width:420px">'
        f'{sub}</div></div>',
        unsafe_allow_html=True)


if ss.pending == "demo":
    wait_screen("Loading demo data",
                "Preparing orders and settlements.")
    time.sleep(1.5)
    ss.pending = None
    ss.source, ss.datadir, ss.results = "demo", DEMO_DATA, None
    engine.DATA = DEMO_DATA
    ss.dfrom, ss.dto = None, None
    ss.land_top = True
    st.rerun()

# ============================================================ entry =========
if ss.source is None:
    with st.container(key="brandbar"):
        st.markdown('<div class="wordmark">Ledgr</div>', unsafe_allow_html=True)

    st.markdown('<div class="hero herobody">'
                '<div class="tag">Financial reconciliation, without the '
                'spreadsheet chaos.</div>'
                '<div class="lede">Ledgr takes what you sold and what you were '
                'actually paid, matches them line by line, accounts for the fees '
                'in between, and leaves you with only the differences worth '
                'looking at.</div>'
                '<div class="hint"><b>Scroll to choose your data</b>'
                '<span>&darr;</span></div></div>', unsafe_allow_html=True)

    st.markdown('<div class="reveal sec" style="margin-top:14vh">Get started</div>',
                unsafe_allow_html=True)
    with st.container(key="choices"):
        c1, c2 = st.columns(2, gap="large")
        with c1:
            st.markdown('<div class="card"><h4>Use demo data</h4>'
                        '<p>Explore Ledgr with a bundled synthetic dataset of orders '
                        'and settlements across every payment mode.</p></div>',
                        unsafe_allow_html=True)
            st.button("Use demo data", on_click=go_demo, key="go_demo")
        with c2:
            st.markdown('<div class="card"><h4>Upload your files</h4>'
                        '<p>Bring your own orders and settlements as CSV or Excel. '
                        'Everything is processed on this machine.</p></div>',
                        unsafe_allow_html=True)
            st.button("Upload files", on_click=go_upload, key="go_upload")
    st.markdown('<div style="height:26vh"></div>', unsafe_allow_html=True)
    st.stop()

# ============================================================ upload ========
if ss.source == "upload_pending":
    st.markdown(f'<div style="height:5vh"></div>'
                f'<div class="brand">Upload your files</div><div class="brandsub" '
                f'style="margin-bottom:28px">Orders is what you sold. Settlements '
                f'is what you were paid.</div>', unsafe_allow_html=True)
    u1, u2 = st.columns(2, gap="large")
    with u1:
        o_up = st.file_uploader("Orders", type=["csv", "xlsx", "xls"])
    with u2:
        s_up = st.file_uploader("Settlements", type=["csv", "xlsx", "xls"])
    st.markdown('<div class="sub" style="margin-top:16px;max-width:780px">Orders '
                'needs order_id, order_date, payment_mode, gateway_ref_id, bank_utr '
                'and order_amount. Settlements needs settlement_id, settled_on, '
                'gateway_ref_id, bank_utr and amount_received. Aliases are mapped '
                'first — expected_amount → order_amount, bank_trans_id → '
                'settlement_id, settlement_date → settled_on, and the rest of '
                'the dictionary in schema_map.py. Anything the dictionary does '
                'not recognise, you pick by hand on the next screen.</div>',
                unsafe_allow_html=True)
    st.write("")
    b1, b2, _ = st.columns([1, 1.3, 3.2])
    with b1:
        if st.button("Back", on_click=change_source):
            pass
    with b2:
        if st.button("Continue", disabled=not (o_up and s_up)):
            try:
                frames = {}
                for up, name in ((o_up, "orders.csv"), (s_up, "settlements.csv")):
                    if up.name.lower().endswith((".xlsx", ".xls")):
                        frames[name] = pd.read_excel(up)
                    else:
                        frames[name] = pd.read_csv(up)
                # upload → map aliases → if a required field is still
                # missing, pause for a manual pick. Do not hard-fail.
                odf, sdf = map_columns(frames["orders.csv"], frames["settlements.csv"])
                miss_o = missing_required(odf, NEED_ORDERS)
                miss_s = missing_required(sdf, NEED_SETTLEMENTS)
                if miss_o or miss_s:
                    ss.up_o, ss.up_s = odf, sdf
                    ss.source = "upload_remap"
                    ss.land_top = True
                    st.rerun()
                ok, _, _ = accept_upload(odf, sdf)
                if ok:
                    st.rerun()
            except Exception as e:
                st.error(f"Could not read those files: {e}")
    st.stop()


# ============================================================ remap =========
if ss.source == "upload_remap":
    odf, sdf = ss.up_o, ss.up_s
    if odf is None or sdf is None:
        ss.source = "upload_pending"
        st.rerun()

    miss_o = missing_required(odf, NEED_ORDERS)
    miss_s = missing_required(sdf, NEED_SETTLEMENTS)
    if not miss_o and not miss_s:
        ok, _, _ = accept_upload(odf, sdf)
        if ok:
            st.rerun()

    NONE = "— pick a column —"
    st.markdown(
        '<div style="height:5vh"></div>'
        '<div class="brand">Match your columns</div>'
        '<div class="brandsub" style="margin-bottom:8px;max-width:640px">'
        'Ledgr recognised the headers it knows. For each field still open, '
        'pick the leftover column from your file.</div>',
        unsafe_allow_html=True)

    def _pick_fields(title, df, missing, targets, need, prefix):
        st.markdown(f'<div class="sec" style="margin-top:28px">{title}</div>',
                    unsafe_allow_html=True)
        hit = [c for c in need if c in df.columns]
        if hit:
            st.markdown('<div class="sub" style="margin-bottom:14px">'
                        'Already matched: ' + ", ".join(hit) + '</div>',
                        unsafe_allow_html=True)
        leftover = unused_columns(df, targets)
        taken = []
        picks = {}
        for field in missing:
            st.markdown(f'<div class="flab">{field}</div>', unsafe_allow_html=True)
            opts = [c for c in leftover if c not in taken]
            if not opts:
                st.markdown('<div class="sub" style="margin-bottom:14px">'
                            'No unused column left in this file for '
                            f'<b>{html.escape(field)}</b>.</div>',
                            unsafe_allow_html=True)
                picks[field] = None
                continue
            choice = st.selectbox(field, [NONE] + opts, key=f"{prefix}{field}",
                                  label_visibility="collapsed",
                                  filter_mode=None)
            if choice != NONE:
                picks[field] = choice
                taken.append(choice)
            else:
                picks[field] = None
        if not missing:
            st.markdown('<div class="sub">Every required field is already '
                        'matched.</div>', unsafe_allow_html=True)
        return picks

    left, right = st.columns(2, gap="large")
    with left:
        po = _pick_fields("Orders", odf, miss_o, ORDER_TARGETS,
                          NEED_ORDERS, "cmap_o_")
    with right:
        ps = _pick_fields("Settlements", sdf, miss_s, SETTLEMENT_TARGETS,
                          NEED_SETTLEMENTS, "cmap_s_")

    ready = (all(po[f] for f in miss_o) if miss_o else True) and \
            (all(ps[f] for f in miss_s) if miss_s else True)

    st.write("")
    b1, b2, _ = st.columns([1, 1.3, 3.2])
    with b1:
        if st.button("Back", on_click=back_to_files, key="remap_back"):
            pass
    with b2:
        if st.button("Continue", disabled=not ready, key="remap_go"):
            o2 = odf.rename(columns={src: dest for dest, src in po.items() if src})
            s2 = sdf.rename(columns={src: dest for dest, src in ps.items() if src})
            ok, _, _ = accept_upload(o2, s2)
            if ok:
                st.rerun()
            ss.up_o, ss.up_s = o2, s2
            st.rerun()
    st.stop()

if ss.datadir:
    engine.DATA = ss.datadir

if ss.land_top:
    ss.land_top = False
    components.html(
        """<script>
(function(){
  function top(){
    var docs = [document];
    try { docs.push(window.parent.document); } catch(e) {}
    try { docs.push(window.parent.parent.document); } catch(e) {}
    docs.forEach(function(d){
      var nodes = [
        d.scrollingElement, d.documentElement, d.body,
        d.querySelector('section.main'),
        d.querySelector('[data-testid="stAppViewContainer"]'),
        d.querySelector('[data-testid="stAppScrollToBottomContainer"]')
      ];
      nodes.forEach(function(box){
        if (!box) return;
        if (box.scrollTo) box.scrollTo({top: 0, behavior: 'auto'});
        box.scrollTop = 0;
      });
    });
    try { window.parent.scrollTo(0,0); } catch(e) {}
    window.scrollTo(0,0);
  }
  top(); setTimeout(top, 30); setTimeout(top, 120); setTimeout(top, 320);
})();
</script>""",
        height=1)

# ============================================================ engine ========
@st.cache_data(show_spinner="Reconciling…")
def run_engine(datadir: str, as_at, mode: str):
    """Load from datadir and reconcile. Cache key is (datadir, as_at, mode).

    Do not prefix these args with _. Streamlit drops underscore names from
    the cache key, so every click reused the first result.
    """
    engine.DATA = datadir
    engine.RUN_DATE = as_at
    orders, setls = load()
    if mode == "upload":
        orders, setls = map_columns(orders, setls)
        orders, setls = soften_inputs(orders, setls)
    out = reconcile(orders, setls)
    print(f"reconcile() returned {len(out)} records  mode={mode}  "
          f"dir={engine.DATA}  orders={len(orders)}  setls={len(setls)}",
          flush=True)
    return out


def execute():
    try:
        t0 = time.perf_counter()
        mode = "upload" if ss.source == "upload" else "demo"
        if mode == "upload":
            path = ss.datadir
            if not path or path == DEMO_DATA:
                st.error("Upload folder is missing. Go back and upload the files again.")
                return False
            if not Path(path, "orders.csv").exists():
                st.error("Uploaded orders.csv is gone. Upload the files again.")
                return False
        else:
            path = ss.datadir or DEMO_DATA
        out = run_engine(path, ss.asat, mode)
        print(f"before session_state  len(results)={len(out)}  path={path}  mode={mode}",
              flush=True)
        if len(out) == 0:
            st.error("Reconciliation returned 0 records.")
            return False
        ss.results = out
        ss.runs = int(ss.runs or 0) + 1
        ss.ms = (time.perf_counter() - t0) * 1000
        ss.dfrom, ss.dto = None, None
        ss.land_top = True
        return True
    except FileNotFoundError as e:
        st.error(f"Input data is missing: `{e.filename}`.")
    except Exception as e:
        st.error(f"Reconciliation failed — {type(e).__name__}: {e}")
    ss.runs -= 1
    return False


@st.cache_data(show_spinner=False)
def date_bounds(_dir: str):
    """Earliest and latest date present in the loaded data. The 'as at' date
    cannot sit outside this window: before it there are no records, after it
    there is nothing to reconcile against."""
    o, st_ = load()
    dates = list(o["order_date"]) + list(st_["settled_on"])
    lo, hi = min(dates), max(dates)
    return date.fromisoformat(lo), date.fromisoformat(hi)


REVIEW_LOG = Path(__file__).parent / "review_log.csv"
CUSTOMERS = Path(__file__).parent / "customers.csv"


def load_review_log():
    """Append-only human resolutions. Missing file = nobody has resolved yet.

    DEMO_MODE never reads the on-disk file — session-only list instead.
    """
    empty = pd.DataFrame(columns=["record_id", "resolved_at", "note"])
    if demo_mode():
        rows = st.session_state.get("demo_review") or []
        if not rows:
            return empty
        df = pd.DataFrame(rows)
        for c in ("record_id", "resolved_at", "note"):
            if c not in df.columns:
                df[c] = ""
        return df[["record_id", "resolved_at", "note"]].fillna("")
    if not REVIEW_LOG.exists() or REVIEW_LOG.stat().st_size == 0:
        return empty
    try:
        df = pd.read_csv(REVIEW_LOG)
    except Exception:
        return empty
    for c in ("record_id", "resolved_at", "note"):
        if c not in df.columns:
            df[c] = ""
    return df[["record_id", "resolved_at", "note"]].fillna("")


def load_customers():
    """Contact directory, separate from the engine files. Missing = no phone/email."""
    empty = pd.DataFrame(columns=["customer_name", "phone", "email", "city"])
    if not CUSTOMERS.exists() or CUSTOMERS.stat().st_size == 0:
        return empty
    try:
        df = pd.read_csv(CUSTOMERS)
    except Exception:
        return empty
    for c in ("customer_name", "phone", "email", "city"):
        if c not in df.columns:
            df[c] = ""
    return df[["customer_name", "phone", "email", "city"]].fillna("")


def contact_via_order(order_id, orders_df=None, people_df=None):
    """order_id → orders.csv customer_name → customers.csv phone/email/city.

    Never match a person by name from the question. The order id is unique.
    """
    info = {"customer": "", "phone": "", "email": "", "city": ""}
    oid = "" if order_id is None else str(order_id).strip()
    if not oid:
        return info
    try:
        if orders_df is None:
            orders_df, _ = load()
        hit = orders_df[orders_df["order_id"].astype(str) == oid]
        if not len(hit):
            return info
        name = str(hit.iloc[0].get("customer_name") or "").strip()
        info["customer"] = name
        if not name:
            return info
        if people_df is None:
            people_df = load_customers()
        row = people_df[people_df["customer_name"].astype(str) == name]
        if len(row):
            p = row.iloc[0]
            info["phone"] = str(p.get("phone") or "")
            info["email"] = str(p.get("email") or "")
            info["city"] = str(p.get("city") or "")
    except Exception:
        pass
    return info


def append_review(record_id, note):
    note = (note or "").strip()
    if not note:
        return False
    row = pd.DataFrame([{
        "record_id": record_id,
        "resolved_at": datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S"),
        "note": note,
    }])
    if demo_mode():
        log = list(st.session_state.get("demo_review") or [])
        log.append(row.iloc[0].to_dict())
        st.session_state.demo_review = log
        return True
    header = (not REVIEW_LOG.exists()) or REVIEW_LOG.stat().st_size == 0
    row.to_csv(REVIEW_LOG, mode="a", header=header, index=False)
    return True


try:
    DMIN, DMAX = date_bounds(ss.datadir or "")
except Exception:
    DMIN, DMAX = ss.asat, ss.asat
# Never allow a date after today (India). If the files only contain future
# rows, collapse the picker to today.
PICK_MAX = min(DMAX, TODAY)
PICK_MIN = min(DMIN, PICK_MAX)
capped = min(max(ss.asat, PICK_MIN), PICK_MAX)
if capped != ss.asat:
    ss.asat, ss.results = capped, None

ran = ss.results is not None

# ============================================================ top bar =======
t0, t1, t2, t3 = st.columns([0.42, 3.88, 1.5, 1.5])
with t0:
    st.markdown('<div class="flab">&nbsp;</div>', unsafe_allow_html=True)
    with st.container(key="backhome"):
        st.button("←", help="Back to source", on_click=change_source)
with t1:
    st.markdown(f'<div class="brand">Ledgr</div>'
                f'<div class="brandsub">As at {ss.asat} · '
                f'{"demo data" if ss.source == "demo" else "uploaded files"}'
                + (f' · run {ss.runs} · {ss.ms:.0f} ms' if ran
                   else ' · not yet reconciled') + '</div>',
                unsafe_allow_html=True)
with t2:
    st.markdown('<div class="flab">Reconcile as at</div>', unsafe_allow_html=True)
    with st.container(key="asatbox"):
        picked = st.date_input("Reconcile as at", ss.asat, min_value=PICK_MIN,
                               max_value=PICK_MAX, label_visibility="collapsed",
                               help=f"Cash-on-delivery orders are aged against this "
                                    f"date. Limited to {PICK_MIN} – {PICK_MAX} "
                                    f"(today in India). Future dates are blocked.")
    if picked != ss.asat:
        already = ss.results is not None
        ss.asat = picked
        ss.dfrom, ss.dto = None, None
        if already:
            execute()
        else:
            ss.results = None
        st.rerun()
with t3:
    st.markdown('<div class="flab">&nbsp;</div>', unsafe_allow_html=True)
    with st.container(key="runbox"):
        if st.button("Run reconciliation", on_click=execute):
            pass

# ============================================================ pre-run =======
if not ran:
    try:
        odf, sdf = load()
        if ss.source == "upload":
            odf, sdf = map_columns(odf, sdf)
            odf, sdf = soften_inputs(odf, sdf)
    except Exception as e:
        st.error(f"Could not read the data: {e}")
        st.stop()

    o_total = sum(to_paise(v) for v in odf["order_amount"])
    s_total = sum(to_paise(v) for v in sdf["amount_received"])

    st.markdown('<div class="sec">Loaded data</div>', unsafe_allow_html=True)
    i1, i2 = st.columns(2, gap="large")

    def preview(df, cols, headers, money=None):
        def val(r, c, last):
            v = r[c]
            if money and c == money:
                try:
                    v = f"{to_paise(v)/100:,.2f}"
                except Exception:
                    pass
            klass = ' class="num"' if last else ""
            return f"<td{klass}>{v}</td>"
        rows = "".join(
            "<tr>" + "".join(val(r, c, h == headers[-1])
                             for c, h in zip(cols, headers)) + "</tr>"
            for _, r in df.head(5).iterrows())
        ths = "".join(f'<th{" class=\"num\"" if h == headers[-1] else ""}>{h}</th>'
                      for h in headers)
        return (f'<table class="t" style="margin-top:14px">'
                f'<col style="width:42%"><col style="width:30%"><col style="width:28%">'
                f'<thead><tr>{ths}</tr></thead><tbody>{rows}</tbody></table>')

    with i1:
        with st.container(key="load_orders"):
            st.markdown(
                f'<div class="figs"><div class="fig"><div class="n">{len(odf)}</div>'
                f'<div class="l">Orders</div><div class="t">{fmt(o_total)} invoiced'
                f'</div></div></div>' + preview(odf, ["order_id", "order_date",
                                                      "order_amount"],
                                                ["Order", "Date", "Amount"],
                                                money="order_amount"),
                unsafe_allow_html=True)
            with st.expander(f"View all {len(odf)} orders"):
                st.dataframe(only_cols(odf, ["order_id", "order_date", "customer_name",
                                  "payment_mode", "gateway_ref_id", "bank_utr",
                                  "order_amount"]), hide_index=True, width="stretch")
    with i2:
        with st.container(key="load_setls"):
            st.markdown(
                f'<div class="figs"><div class="fig"><div class="n">{len(sdf)}</div>'
                f'<div class="l">Settlements</div><div class="t">{fmt(s_total)} received'
                f'</div></div></div>' + preview(sdf, ["settlement_id", "settled_on",
                                                      "amount_received"],
                                                ["Settlement", "Date", "Amount"],
                                                money="amount_received"),
                unsafe_allow_html=True)
            with st.expander(f"View all {len(sdf)} settlements"):
                st.dataframe(only_cols(sdf, ["settlement_id", "settled_on", "gateway_ref_id",
                                  "bank_utr", "amount_received", "source"]),
                             hide_index=True, width="stretch")

    st.markdown(f'<div class="sec">Ready to reconcile</div>'
                f'<div class="sub" style="max-width:640px">Ledgr will match each '
                f'order to its settlement, account for processing and collection '
                f'fees, and set aside only the records that genuinely differ. '
                f'Nothing is guessed.</div>', unsafe_allow_html=True)
    st.write("")
    rc1, _ = st.columns([1.4, 3.6])
    with rc1:
        if st.button("Reconcile", type="primary", key="prerun", on_click=execute):
            pass
    st.stop()

# ============================================================ results =======
res = ss.results.copy()
# Display-only. Engine still stores R5_AI_VARIANCE / the original label.
R5_UI = "Large variance — needs review"
if "reason" in res.columns:
    res.loc[res["reason"].astype(str) == "R5_AI_VARIANCE", "reason_label"] = R5_UI
if ss.reason == "Large variance flagged by AI":
    ss.reason = R5_UI
try:
    odf, sdf = load()
    if ss.source == "upload":
        odf, sdf = map_columns(odf, sdf)
        odf, sdf = soften_inputs(odf, sdf)
    om = odf.set_index("order_id")
    sm = sdf.set_index("settlement_id")
    res["mode"] = res["record_id"].map(om["payment_mode"]).fillna("Bank credit")
    res["ident"] = (res["record_id"].map(om["gateway_ref_id"]).fillna("")
                    .where(lambda s: s != "", res["record_id"].map(om["bank_utr"]))
                    ).fillna("")
    # order_id → orders.csv (customer_name) → customers.csv (phone/email/city)
    people_df = load_customers()
    res["customer"] = res["record_id"].map(om["customer_name"]).fillna("")
    # run_results.csv has no dates -- join them back from the source files
    res["date"] = (res["record_id"].map(om["order_date"])
                   .fillna(res["record_id"].map(sm["settled_on"])))
    res["settled_on"] = res["matched_settlement"].map(sm["settled_on"])
    pm = people_df.drop_duplicates("customer_name").set_index("customer_name")
    res["phone"] = res["customer"].map(pm["phone"]).fillna("")
    res["email"] = res["customer"].map(pm["email"]).fillna("")
    res["city"] = res["customer"].map(pm["city"]).fillna("")
except Exception:
    odf, sdf, people_df = None, None, load_customers()
    for c in ("mode", "ident", "customer", "date", "settled_on",
              "phone", "email", "city"):
        res[c] = ""

res["bucket"] = res["status"].map(
    lambda s: "Matched" if s in CLEARED else "Waiting" if s in INFLIGHT
    else "Needs a look")
log = load_review_log()
res["resolved"] = res["record_id"].astype(str).isin(set(log["record_id"].astype(str)))

# ---- settlement activity by date ------------------------------------------
# Driven by the as-at picker: 1st of that month → the selected day.
# Bar heights are the real settlements that landed on each of those days.
st.markdown('<div class="sec" style="margin-top:30px">Settlement activity</div>',
            unsafe_allow_html=True)
sdf2 = sdf.copy()
sdf2["paise"] = sdf2["amount_received"].map(to_paise)
byday = (sdf2.groupby("settled_on")["paise"].sum().sort_index())
d_lo, d_hi = ss.asat.replace(day=1), ss.asat
series = []
d = d_lo
while d <= d_hi:
    series.append((d, int(byday.get(d.isoformat(), 0))))
    d += timedelta(days=1)

if ss.dfrom is None or ss.dto is None:
    ss.dfrom, ss.dto = d_lo, d_hi
ss.dfrom = min(max(ss.dfrom, d_lo), d_hi)
ss.dto = min(max(ss.dto, d_lo), d_hi)
if ss.dfrom > ss.dto:
    ss.dfrom, ss.dto = d_lo, d_hi
if d_lo < d_hi:
    rng = st.slider("dr", min_value=d_lo, max_value=d_hi,
                    value=(ss.dfrom, ss.dto),
                    format="DD MMM", label_visibility="collapsed",
                    key=f"dr_{ss.asat.isoformat()}")
    if rng != (ss.dfrom, ss.dto):
        ss.dfrom, ss.dto = rng
        st.rerun()

peak_day = max((v for _, v in series), default=0) or 1
bars = "".join(
    f'<div class="dbar"><div class="tip">'
    f'<b>{d:%a %d %b %Y}</b>{fmt(int(v))} settled</div>'
    f'<div class="dfill" style="height:{max(3, 100*v/peak_day)}%;'
    f'background:{ACC if ss.dfrom <= d <= ss.dto else LINE}">'
    f'</div></div>' for d, v in series)
in_rng = [(d, v) for d, v in series if ss.dfrom <= d <= ss.dto]
n_days = sum(1 for _, v in in_rng if v)
got = sum(v for _, v in in_rng)
st.markdown(f'<div class="chart" style="padding:18px 22px 12px">'
            f'<div class="dbars">{bars}</div>'
            f'<div class="sub" style="margin-top:12px">'
            f'{d_lo:%d %b} to {d_hi:%d %b} &middot; as at {ss.asat:%d %b} '
            f'&middot; {n_days} settlement day{"s" if n_days != 1 else ""} '
            f'&middot; {fmt(int(got))} received</div></div>',
            unsafe_allow_html=True)

def _in_window(d):
    if d is None or (isinstance(d, float) and pd.isna(d)):
        return True
    s = str(d).strip()
    if s in ("", "nan", "NaT", "None"):
        return True
    try:
        dd = date.fromisoformat(s[:10])
    except Exception:
        return True
    return ss.dfrom <= dd <= ss.dto

# Date window. Blank/bad dates stay in — do not zero the whole page.
dated = res[[_in_window(d) for d in res["date"]]] if len(res) else res
if len(dated) == 0 and len(res):
    dated = res.copy()

# Live totals: engine categories stay as-is, but resolved rows drop out of
# "still at risk" / "needs a look" so the dashboard matches the review log.
look_all = dated[dated["bucket"] == "Needs a look"]
look_open = look_all[~look_all["resolved"].astype(bool)]
n_resolved = int(dated["resolved"].astype(bool).sum())
risk_live = int(look_open["amount_at_risk"].sum()) if len(look_open) else 0
risk_handled = int(look_all.loc[look_all["resolved"].astype(bool),
                                "amount_at_risk"].sum()) if n_resolved else 0
# Display-only split of open needs-a-look / unmatched. Engine numbers unchanged.
if len(look_open):
    _gap = (look_open["expected"].astype("int64")
            - look_open["received"].astype("int64"))
    short_live = int(_gap[_gap > 0].sum()) if (_gap > 0).any() else 0
    over_live = int((-_gap)[_gap < 0].sum()) if (_gap < 0).any() else 0
else:
    short_live = over_live = 0

# ---- money position --------------------------------------------------------
st.markdown('<div class="sec">Money position</div>', unsafe_allow_html=True)
exp_t, rec_t = int(dated["expected"].sum()), int(dated["received"].sum())
gap = exp_t - rec_t
chips = (
    f'<div class="statrow">'
    f'<span class="stat short"><b>{fmt(short_live)}</b> shortfall</span>'
    f'<span class="stat over"><b>{fmt(over_live)}</b> overpaid / unexplained</span>'
    f'</div>'
)
st.markdown(
    f'<div class="figs">'
    f'<div class="fig"><div class="n">{fmt(exp_t)}</div><div class="l">Expected</div>'
    f'<div class="t">across {len(dated)} records</div></div>'
    f'<div class="fig"><div class="n">{fmt(rec_t)}</div><div class="l">Received</div>'
    f'<div class="t">actually settled</div></div>'
    f'<div class="fig"><div class="n" style="color:{WARN if gap else MATCHED}">'
    f'{fmt(gap)}</div><div class="l">Gap</div>'
    f'<div class="t">fees, timing and exceptions</div>{chips}</div></div>'
    f'<div class="sub" style="margin-top:14px">'
    f'{n_resolved} record{"s" if n_resolved != 1 else ""} resolved manually'
    + (f' &middot; {fmt(risk_handled)} taken off at-risk' if n_resolved else '')
    + f' &middot; {fmt(risk_live)} still at risk</div>',
    unsafe_allow_html=True)

def card_face(icon, count, label, amount=None, tone="look", on=False):
    """Paint the visible card. The Streamlit button underneath still does the click."""
    cls = f"oc-card oc-{tone}{' on' if on else ''}"
    n = f'<span class="oc-n">{count}</span>' if count is not None else ""
    amt = f'<div class="oc-a">{html.escape(amount)}</div>' if amount else ""
    return (f'<div class="{cls}"><div class="oc-top">'
            f'<span class="oc-ico">{icon}</span>{n}</div>'
            f'<div class="oc-l">{html.escape(label)}</div>{amt}</div>')


# ---- outcome buckets, clickable -------------------------------------------
st.markdown('<div class="sec">Outcome</div>', unsafe_allow_html=True)
b_counts = {b: int((dated["bucket"] == b).sum())
            for b in ("Matched", "Waiting", "Needs a look")}
b_counts["Needs a look"] = int(len(look_open))
ICON = {"Matched": "\u2713", "Waiting": "\u25f7", "Needs a look": "\u26a0"}
SLUG = {"Matched": "matched", "Waiting": "waiting", "Needs a look": "look"}
TONE = {"Matched": "matched", "Waiting": "waiting", "Needs a look": "look"}
b1, b2, b3, b4 = st.columns([1, 1, 1, 1])
for col, name in ((b1, "Matched"), (b2, "Waiting"), (b3, "Needs a look")):
    with col:
        with st.container(key=f"oc_{SLUG[name]}"):
            on = ss.pick == name
            if st.button(f"{ICON[name]}  {b_counts[name]}\n{name}",
                         key=f"b{SLUG[name]}",
                         type="primary" if on else "secondary"):
                ss.pick = None if on else name
                ss.reason = None
                ss.jump = True
                st.rerun()
            st.markdown(card_face(ICON[name], b_counts[name], name,
                                  tone=TONE[name], on=on),
                        unsafe_allow_html=True)
with b4:
    with st.container(key="oc_all"):
        if st.button("\u21ba\nShow everything", key="ball"):
            ss.pick, ss.reason = None, None
            ss.jump = True
            st.rerun()
        st.markdown(card_face("\u21ba", None, "Show everything", tone="all"),
                    unsafe_allow_html=True)

# ---- reason groups inside 'Needs a look' ----------------------------------
look = dated[dated["bucket"] == "Needs a look"]
if len(look):
    st.markdown('<div class="sec" style="margin-top:34px">Needs a look, by reason'
                '</div>', unsafe_allow_html=True)
    grp = (look_open.groupby("reason_label")["amount_at_risk"]
           .agg(["count", "sum"]).sort_values("sum", ascending=False)) if len(look_open) else look_open
    if len(look_open):
      gcols = st.columns(min(len(grp), 4))
      for i, (name, row) in enumerate(grp.iterrows()):
        with gcols[i % len(gcols)]:
            slug = "".join(ch for ch in name.lower() if ch.isalnum())
            with st.container(key=f"rg_{slug}"):
                on = ss.reason == name
                if st.button(f"\u26a0  {int(row['count'])}\n{name}\n"
                             f"{fmt(int(row['sum']))}", key=f"g{slug}",
                             type="primary" if on else "secondary"):
                    ss.reason = None if on else name
                    ss.pick = None
                    ss.jump = True
                    st.rerun()
                st.markdown(card_face("\u26a0", int(row["count"]), name,
                                      amount=fmt(int(row["sum"])),
                                      tone="look", on=on),
                            unsafe_allow_html=True)

# ---- search + Flipkart-style filters --------------------------------------
st.markdown('<div class="sec" style="margin-top:34px">Find a record</div>',
            unsafe_allow_html=True)
c_q, c_f, c_x = st.columns([4.45, 1.1, 0.75])
with c_q:
    ss.q = st.text_input("q", ss.q, label_visibility="collapsed",
                         placeholder="Look up S.No., order ID, reference or customer")
with c_f:
    with st.container(key="filttrig"):
        _open = bool(ss.filt_open)
        if st.button("Filters ▴" if _open else "Filters ▾", key="filt_btn",
                     type="primary" if _open else "secondary"):
            ss.filt_open = not _open
            st.rerun()
with c_x:
    if st.button("Clear", key="qclear"):
        ss.q = ""
        _reset_filter_widgets()
        st.rerun()

if "hide_resolved" not in ss or ss.hide_resolved not in (True, False, None):
    ss.hide_resolved = None

mode_opts = list(MODE_CHOICES)
for m in sorted(str(x) for x in res["mode"].unique() if str(x)):
    if m not in mode_opts:
        mode_opts.append(m)
ss.setdefault("keep_modes", [])
ss.setdefault("keep_sides", [])
ss.setdefault("_filt_restored", False)
ss.setdefault("filt_gen", 0)

# Panel closed = widgets not mounted. Picks live in keep_modes / keep_sides.
# Checkbox keys include filt_gen so Clear remounts them unchecked.
if ss.filt_open:
    if not ss._filt_restored:
        for m in mode_opts:
            ss[_filt_key("fm", m)] = m in ss.keep_modes
        ss[_filt_key("at", "short")] = "short" in ss.keep_sides
        ss[_filt_key("at", "over")] = "over" in ss.keep_sides
        ss[_filt_key("st", "hide")] = ss.hide_resolved is True
        ss[_filt_key("st", "show")] = ss.hide_resolved is False
        ss._filt_restored = True
    with st.container(key="filtdrop"):
        with st.container(key="filtbox"):
            st.markdown('<div class="flab">Payment mode</div>', unsafe_allow_html=True)
            mcols = st.columns(4)
            for i, m in enumerate(mode_opts):
                with mcols[i % 4]:
                    st.checkbox(m, key=_filt_key("fm", m))
            st.markdown('<div class="flab" style="margin-top:12px">Amount type</div>',
                        unsafe_allow_html=True)
            ac1, ac2, _ = st.columns([1.4, 2.1, 2.0])
            with ac1:
                st.checkbox("Shortfall", key=_filt_key("at", "short"))
            with ac2:
                st.checkbox("Overpaid / unexplained", key=_filt_key("at", "over"))
            st.markdown('<div class="flab" style="margin-top:12px">Status</div>',
                        unsafe_allow_html=True)
            sc1, sc2, _ = st.columns([1.5, 1.6, 2.4])
            with sc1:
                st.checkbox("Hide resolved", key=_filt_key("st", "hide"),
                            on_change=_on_hide_resolved)
            with sc2:
                st.checkbox("Show resolved", key=_filt_key("st", "show"),
                            on_change=_on_show_resolved)
    ss.keep_modes = [m for m in mode_opts if ss.get(_filt_key("fm", m))]
    ss.keep_sides = [s for s, on in (
        ("short", ss.get(_filt_key("at", "short"))),
        ("over", ss.get(_filt_key("at", "over"))),
    ) if on]
else:
    ss._filt_restored = False

ss.modes = list(ss.keep_modes)
ss.sides = list(ss.keep_sides)

# Active-filter chips stay visible under the trigger, panel open or not.
active = []
if ss.pick:
    active.append((ss.pick, "pick"))
if ss.reason:
    active.append((ss.reason, "reason"))
if ss.dfrom != d_lo or ss.dto != d_hi:
    active.append((f"{ss.dfrom:%d %b} to {ss.dto:%d %b}", "date"))
for m in ss.modes:
    active.append((m, "mode:" + m))
for s in ss.sides:
    active.append((SIDE_LABEL[s], "side:" + s))
if ss.hide_resolved is True:
    active.append(("Hide resolved", "status"))
elif ss.hide_resolved is False:
    active.append(("Show resolved", "status"))
if ss.q:
    active.append((f'"{ss.q}"', "q"))

if active:
    with st.container(key="actfil"):
        nchip = len(active) + (1 if len(active) >= 2 else 0)
        cols = st.columns(nchip)
        for i, (label, kind) in enumerate(active):
            with cols[i]:
                if st.button(f"{label}  ×", key=f"rmf_{kind}"):
                    if kind == "pick":
                        ss.pick = None
                    elif kind == "reason":
                        ss.reason = None
                    elif kind == "date":
                        ss.dfrom, ss.dto = d_lo, d_hi
                    elif kind.startswith("mode:"):
                        m = kind.split(":", 1)[1]
                        ss.keep_modes = [x for x in ss.keep_modes if x != m]
                        ss.filt_gen = int(ss.filt_gen or 0) + 1
                        ss._filt_restored = False
                    elif kind.startswith("side:"):
                        s = kind.split(":", 1)[1]
                        ss.keep_sides = [x for x in ss.keep_sides if x != s]
                        ss.filt_gen = int(ss.filt_gen or 0) + 1
                        ss._filt_restored = False
                    elif kind == "status":
                        ss.hide_resolved = None
                        ss.filt_gen = int(ss.filt_gen or 0) + 1
                        ss._filt_restored = False
                    elif kind == "q":
                        ss.q = ""
                    st.rerun()
        if len(active) >= 2:
            with cols[-1]:
                with st.container(key="clearall"):
                    if st.button("Clear all", key="chipclear"):
                        ss.pick, ss.reason, ss.q = None, None, ""
                        ss.dfrom, ss.dto = d_lo, d_hi
                        _reset_filter_widgets()
                        st.rerun()
    st.write("")

# ---- the one table, driven by every selection above -----------------------
f = dated
if ss.pick:
    f = f[f["bucket"] == ss.pick]
if ss.reason:
    f = f[f["reason_label"] == ss.reason]
if ss.modes:
    f = f[f["mode"].isin(ss.modes)]
if ss.sides:
    bits = []
    if "short" in ss.sides:
        bits.append(f["expected"] > f["received"])
    if "over" in ss.sides:
        bits.append(f["received"] > f["expected"])
    mask = bits[0]
    for b in bits[1:]:
        mask = mask | b
    f = f[mask]
if ss.q:
    ql = ss.q.lower()
    f = f[f.apply(lambda r: ql in
                  f"{r['record_id']} {r['ident']} {r['customer']}".lower(), axis=1)]
if ss.hide_resolved is True:
    f = f[~f["resolved"].astype(bool)]
elif ss.hide_resolved is False:
    f = f[f["resolved"].astype(bool)]
f = f.sort_values("amount_at_risk", ascending=False)
f = f.copy()
f["sno"] = range(1, len(f) + 1)

st.markdown(f'<div id="ledgr-results" data-ledgr="results" class="sec jump-to">Records <span style="text-transform:none;'
            f'letter-spacing:0;font-weight:400">&middot; {len(f)} shown, sorted by '
            f'amount at risk</span></div>', unsafe_allow_html=True)

if ss.jump:
    ss.jump = False
    ss.jumps = int(ss.jumps or 0) + 1
    n = ss.jumps
    components.html(
        f"""<script>
(function(){{
  function find(d){{
    return d.getElementById('ledgr-results')
        || d.querySelector('[data-ledgr="results"]');
  }}
  function scroller(d, el){{
    var p = el.parentElement;
    while (p && p !== d.body && p !== d.documentElement){{
      var s = d.defaultView.getComputedStyle(p);
      if ((s.overflowY === 'auto' || s.overflowY === 'scroll')
          && p.scrollHeight > p.clientHeight + 8) return p;
      p = p.parentElement;
    }}
    return d.querySelector('section.main')
        || d.querySelector('[data-testid="stAppViewContainer"]')
        || d.scrollingElement || d.documentElement;
  }}
  function go(){{
    var d = window.parent.document;
    var e = find(d);
    if (!e) return;
    var box = scroller(d, e);
    var extra = (box.getBoundingClientRect ? box.getBoundingClientRect().top : 0);
    var top = e.getBoundingClientRect().top - extra + (box.scrollTop || 0) - 16;
    if (box.scrollTo) box.scrollTo({{top: Math.max(0, top), behavior: 'smooth'}});
    else e.scrollIntoView({{behavior: 'smooth', block: 'start'}});
    e.classList.add('ledgr-flash');
    setTimeout(function(){{ e.classList.remove('ledgr-flash'); }}, 900);
  }}
  go();
  setTimeout(go, 70);
  setTimeout(go, 200);
  setTimeout(go, 420);
}})();
</script><span style="display:none">{n}</span>""",
        height=1)

def row_html(r):
    """One record as a grid row. Resolved rows stay dimmed and keep the engine label."""
    tag = ('<span class="oktag">\u2713 Resolved manually</span>'
           if getattr(r, "resolved", False) else "")
    dim = " dimrow" if getattr(r, "resolved", False) else ""
    reason = html.escape(str(r.reason_label or r.bucket))
    who = html.escape(str(r.customer)) if getattr(r, "customer", "") else ""
    sub = who or (html.escape(str(r.ident)) if r.ident else "&mdash;")
    return (
        f'<div class="rrow{dim}">'
        f'<div class="sno">{int(getattr(r, "sno", 0)) or "&mdash;"}</div>'
        f'<div><div>{html.escape(str(r.record_id))}</div>'
        f'<div class="sub">{sub}</div></div>'
        f'<div><span class="tg">{html.escape(str(r.mode))}</span></div>'
        f'<div class="sub">{html.escape(str(r.date)) if r.date else "&mdash;"}</div>'
        f'<div><div>{reason}{tag}</div>'
        f'<div class="sub"><span class="tier">Tier {r.tier}</span></div></div>'
        f'<div class="num muted">{r.expected/100:,.2f}</div>'
        f'<div class="num">{r.received/100:,.2f}</div>'
        f'<div class="num {"wn" if r.amount_at_risk else "sub"}">'
        f'{fmt(r.amount_at_risk) if r.amount_at_risk else "&mdash;"}</div></div>'
    )


def contact_panel(r):
    """Inline card. Person only via order_id → orders.csv → customers.csv."""
    rid = str(r.record_id)
    c = contact_via_order(rid, odf, people_df)
    unlinked = (int(getattr(r, "expected", 0) or 0) == 0
                and int(getattr(r, "received", 0) or 0) > 0) or (not c["customer"])
    if unlinked and not c["customer"]:
        return ('<div class="ccard"><div class="ch">Contact details</div>'
                '<div class="warnline">No order on file — cannot identify sender</div>'
                '<div class="sub" style="margin-top:8px">This is an unlinked bank '
                'credit. There is no customer to contact.</div></div>')
    cells = [
        ("Customer", c["customer"] or "not on this order"),
        ("Phone", c["phone"] or "not on file"),
        ("Email", c["email"] or "not on file"),
        ("City", c["city"] or "not on file"),
        ("Amount at risk", fmt(r.amount_at_risk) if r.amount_at_risk else "none"),
        ("Reason", r.reason_label or r.bucket),
    ]
    body = "".join(f'<div class="ck">{html.escape(k)}</div>'
                   f'<div class="cv">{html.escape(str(v))}</div>'
                   for k, v in cells)
    return f'<div class="ccard"><div class="ch">Contact details</div>{body}</div>'


def render_rows(df, prefix):
    # Header lives in the same split as every data row, otherwise the
    # money labels sit over the resolve buttons instead of the numbers.
    split = [5.7, 2.1]
    h1, h2 = st.columns(split)
    with h1:
        st.markdown(
            '<div class="rrow head"><div>S.No.</div><div>Record</div><div>Mode</div>'
            '<div>Date</div><div>Outcome</div><div class="num">Expected</div>'
            '<div class="num">Received</div><div class="num">At risk</div></div>',
            unsafe_allow_html=True)
    for r in df.itertuples():
        rid = str(r.record_id)
        look = r.bucket == "Needs a look"
        openable = look and (not bool(r.resolved))
        left, right = st.columns(split)
        with left:
            st.markdown(row_html(r), unsafe_allow_html=True)
        with right:
            with st.container(key=f"acts_{prefix}_{rid}"):
                ba, bb = st.columns([3.4, 1])
                with ba:
                    if openable:
                        if st.button("Mark as resolved", key=f"mr_{prefix}_{rid}",
                                     help=("Live demo — saved for this session only, not written to disk"
                                           if demo_mode() else "Mark as resolved")):
                            ss.resolve_id = rid
                            st.rerun()
                with bb:
                    if look:
                        on = ss.contact_id == rid
                        if st.button("✕" if on else "👤",
                                     key=f"ctb_{prefix}_{rid}",
                                     help="Contact"):
                            ss.contact_id = None if on else rid
                            st.rerun()
        if look and ss.contact_id == rid:
            with st.container(key=f"cdetail_{prefix}_{rid}"):
                st.markdown(contact_panel(r), unsafe_allow_html=True)
        if openable and ss.resolve_id == rid:
            st.markdown('<div class="flab" style="margin-top:8px">Resolution note</div>',
                        unsafe_allow_html=True)
            note = st.text_input("Resolution note", key=f"rn_{prefix}_{rid}",
                                 label_visibility="collapsed",
                                 placeholder="Confirmed with courier — payment received late")
            cf, _ = st.columns([1.7, 3.8])
            with cf:
                with st.container(key=f"cf_{prefix}_{rid}"):
                    if st.button("Confirm resolution", key=f"ok_{prefix}_{rid}",
                                 disabled=not (note or "").strip()):
                        if append_review(rid, note):
                            ss.resolve_id = None
                            st.rerun()


if len(f):
    render_rows(f.head(20), "top")
    if len(f) > 20:
        with st.expander(f"View all {len(f)} records"):
            render_rows(f.iloc[20:], "more")
else:
    st.markdown('<div class="muted">No records match this selection.</div>',
                unsafe_allow_html=True)

with st.expander("What these reasons mean"):
    for code, (name, desc) in REASON_LEGEND.items():
        if code == "R5_AI_VARIANCE":
            name = R5_UI
        n = int((res["reason"] == code).sum())
        if n:
            st.markdown(f"**{name}** — {n} record{'s' if n != 1 else ''}  \n"
                        f"<span class='sub'>{desc}</span>", unsafe_allow_html=True)

out = f.copy()
for c in ("expected", "received", "delta", "amount_at_risk"):
    out[c] = out[c].map(to_rupees)
buf = io.StringIO()
out.drop(columns=["tier_name", "resolved"], errors="ignore").to_csv(buf, index=False)
d1, _ = st.columns([1.5, 4])
with d1:
    st.download_button(f"Export {len(f)} records", buf.getvalue(),
                       "ledgr_reconciliation.csv", "text/csv")


# ============================================================ assistant =====
ADVICE = {
    "R1_AWAITING_REMITTANCE": "No action. Check again once the collection window closes.",
    "R2_REMITTANCE_OVERDUE": "Raise a remittance query with the courier partner.",
    "R3_UNMATCHED_AMBIGUOUS": "Confirm with the bank before posting anything.",
    "R4_PARTIAL_PAYMENT": "Ask the payer or partner to account for the shortfall.",
    "R5_AI_VARIANCE": "Verify against the agreed fee schedule before clearing.",
}


def record_card(r):
    """Contact card. Person is resolved only via order_id → orders.csv → customers.csv."""
    line = lambda k, v: f"| **{k}** | {v} |"
    c = contact_via_order(r["record_id"], odf, people_df)
    sno = r["sno"] if "sno" in getattr(r, "index", []) and pd.notna(r["sno"]) else ""
    rows = [
        "| | |", "|---|---|",
        line("S.No.", int(sno) if sno != "" else "—"),
        line("Customer", c["customer"] or "not on this order"),
        line("Phone", c["phone"] or "not on file"),
        line("Email", c["email"] or "not on file"),
        line("City", c["city"] or "not on file"),
        line("Order", f"{r['record_id']}  ·  placed {r['date'] or 'unknown'}"),
        line("At risk", fmt(r["amount_at_risk"]) if r["amount_at_risk"] else "none"),
        line("Reason", r["reason_label"] or r["bucket"]),
        line("Payment mode", r["mode"]),
        line("Expected", fmt(r["expected"])),
        line("Received", fmt(r["received"]) if r["received"] else "nothing received"),
    ]
    out = "\n".join(rows)
    if int(r["expected"] or 0) == 0 and int(r["received"] or 0) > 0:
        out += ("\n\nThis is an unlinked bank credit: money arrived with no "
                "matching order. Expected is Rs 0.00. That is not a data error "
                "— there is simply no order to attach this settlement to.")
    elif r["amount_at_risk"] and c["customer"]:
        reach = c["phone"] or c["email"] or "the contact on file"
        out += (f"\n\nRecover {fmt(r['amount_at_risk'])} by contacting "
                f"**{c['customer']}** ({reach}).")
    return out


def find_sno(s):
    """S.No. 3 / sno 3 / serial 3 / #3 → that row in the list on screen."""
    m = re.search(r"(?:s\.?\s*no\.?|serial(?:\s*no(?:\.|umber)?)?|#)\s*(\d+)",
                  s, flags=re.I)
    if not m:
        return None
    n = int(m.group(1))
    if "sno" not in f.columns:
        return None
    hit = f[f["sno"] == n]
    return hit.iloc[0] if len(hit) else n


def find_record(s):
    """Match an order/settlement id anywhere in the question."""
    ids = res["record_id"].str.lower()
    for tok in s.replace("?", " ").replace(",", " ").replace(".", " ").split():
        tok = tok.strip("'\"()")
        hit = res[ids == tok]
        if len(hit):
            return hit.iloc[0]
        if len(tok) >= 5:                      # partial id, e.g. "00023"
            hit = res[ids.str.contains(tok, regex=False)]
            if len(hit) == 1:
                return hit.iloc[0]
    return None


def reply(text):
    s = text.lower().strip()

    # 1. S.No. on the visible table → that row's order_id → orders.csv → customers.csv
    got = find_sno(s)
    if isinstance(got, (int, float)) and not hasattr(got, "record_id"):
        return (f"There is no S.No. {int(got)} in the current list. "
                f"{len(f)} record{'s' if len(f) != 1 else ''} are showing.")
    if got is not None:
        ss.focus = got["record_id"]
        return record_card(got)

    # 2. order id (e.g. ORD-00023) → orders.csv → customers.csv. No name search.
    r = find_record(s)
    if r is not None:
        ss.focus = r["record_id"]
        return record_card(r)

    # 3. live totals first, so a follow-up word inside another question
    #    (e.g. "it" in "credits") cannot steal the answer.
    act = look_open.sort_values("amount_at_risk", ascending=False)

    if any(k in s for k in ("resolved", "handled", "manually")):
        if not n_resolved:
            return "No records have been resolved manually this session."
        return (f"{n_resolved} record{'s' if n_resolved != 1 else ''} resolved "
                f"manually this session, {fmt(risk_handled)} taken off at-risk. "
                f"{fmt(risk_live)} still at risk across {len(act)} open record"
                f"{'s' if len(act) != 1 else ''}.")

    if any(k in s for k in ("unlinked", "bank credit", "no order", "no matching",
                            "orphan", "unmatched credit", "without an order",
                            "expected 0", "received but")):
        creds = dated[(dated["expected"] == 0) & (dated["received"] > 0)]
        if not len(creds):
            return ("There are no unlinked bank credits in this view — every "
                    "received amount has an order behind it.")
        top = creds.sort_values("received", ascending=False).iloc[0]
        return (f"{len(creds)} unlinked bank credit"
                f"{'s' if len(creds) != 1 else ''} — money received "
                f"({fmt(int(creds['received'].sum()))}) with no matching order. "
                f"Expected is Rs 0.00. This is not a data error; the settlement "
                f"has nothing to attach to. Largest is **{top['record_id']}** at "
                f"{fmt(int(top['received']))}.")

    if "cod" in s or "cash" in s:
        c = act[act["mode"] == "COD"]
        w = dated[(dated["bucket"] == "Waiting") & (dated["mode"] == "COD")]
        extra = (f" {n_resolved} more COD/other items were resolved manually."
                 if n_resolved else "")
        return (f"{len(c)} cash-on-delivery records still need a look, "
                f"{fmt(int(c['amount_at_risk'].sum()))} at risk. Another {len(w)} "
                f"are still inside their collection window.{extra}")
    if any(k in s for k in ("risk", "unexplained", "gap", "how much", "total")):
        if not len(act):
            extra = (f" {n_resolved} were resolved manually."
                     if n_resolved else "")
            return "Nothing is still at risk in this view." + extra
        extra = (f" {n_resolved} resolved manually are no longer in that figure."
                 if n_resolved else "")
        split = ""
        if short_live or over_live:
            split = (f" {fmt(short_live)} shortfall, {fmt(over_live)} "
                     f"overpaid / unexplained.")
        return (f"{fmt(risk_live)} still at risk across {len(act)} open record"
                f"{'s' if len(act) != 1 else ''}.{split} Largest is "
                f"**{act.iloc[0]['record_id']}** at "
                f"{fmt(act.iloc[0]['amount_at_risk'])} "
                f"({act.iloc[0]['reason_label']}).{extra}")
    if any(k in s for k in ("exception", "review", "look", "attention", "how many")):
        if not len(act):
            extra = (f" {n_resolved} were resolved manually."
                     if n_resolved else "")
            return "Nothing still needs a look in this view." + extra
        by = act["reason_label"].value_counts()
        extra = (f" Another {n_resolved} resolved manually are tagged but not counted."
                 if n_resolved else "")
        return (f"{len(act)} records still need a look — "
                + ", ".join(f"{k.lower()} {v}" for k, v in by.items())
                + "." + extra)
    if any(k in s for k in ("match", "cleared", "waiting", "summary", "tier")):
        b = dated["bucket"].value_counts()
        return (f"{b.get('Matched', 0)} matched, {b.get('Waiting', 0)} waiting, "
                f"{len(act)} still need a look"
                + (f", {n_resolved} resolved manually" if n_resolved else "")
                + f", out of {len(dated)} records in view.")

    if ss.focus and re.search(r"\b(why|what|explain|this|reason|next)\b", s):
        m = res[res["record_id"] == ss.focus]
        if len(m):
            r = m.iloc[0]
            if r["reason"]:
                return (f"**{r['record_id']}** — {r['reason_label']}.\n\n"
                        f"{r['explanation']}\n\n"
                        f"*Suggested:* {ADVICE.get(r['reason'], 'Review manually.')}")
            return (f"**{r['record_id']}** cleared with no exception. "
                    f"{r['explanation']}")

    return ("Give me an S.No. such as `S.No. 3` or an order ID such as "
            "`ORD-00023`. I look up that order, then the person on it, then "
            "their phone and email. I do not search by name.")


if ss.chat_open:
    with st.container(key="askpanel"):
        st.markdown(f'<div style="font-size:14px;font-weight:600">Ask Ledgr</div>'
                    f'<div class="sub" style="margin-bottom:12px">Reads the live '
                    f'totals on screen, after manual resolutions.</div>',
                    unsafe_allow_html=True)
        typed = st.text_input("a", "", label_visibility="collapsed",
                              placeholder="S.No. 3 or ORD-00023…")
        g1, g2 = st.columns(2)
        with g1:
            if st.button("What needs review?", key="s1"):
                ss.ask = "what needs review?"
        with g2:
            if st.button("How much is unexplained?", key="s2"):
                ss.ask = "how much is unexplained?"
        if typed:
            ss.ask = typed
        if ss.ask:
            st.markdown(f'<div style="border-top:1px solid {LINE};margin-top:12px;'
                        f'padding-top:12px;font-size:13.5px">{reply(ss.ask)}</div>',
                        unsafe_allow_html=True)

with st.container(key="asklaunch"):
    if st.button(("✕  Close" if ss.chat_open else "💬  Ask Ledgr"), key="asktoggle"):
        ss.chat_open = not ss.chat_open
        if not ss.chat_open:
            ss.ask = ""
        st.rerun()
