"""
Kastel Shoes – Live Shopify Dashboard
"""

import re
import calendar
from datetime import date, datetime, timedelta
from collections import defaultdict

import requests
import streamlit as st
import plotly.graph_objects as go
import pandas as pd

# ── CONFIG ─────────────────────────────────────────────────────────────────────
SHOP    = "kastel-shoes.myshopify.com"
TOKEN   = st.secrets["SHOPIFY_TOKEN"]
VERSION = "2024-10"
HEADERS = {"X-Shopify-Access-Token": TOKEN}
BASE    = f"https://{SHOP}/admin/api/{VERSION}"
SKIP    = {"voided", "refunded"}

# ── PAGE CONFIG ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Kastel Dashboard",
    page_icon="👟",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  #MainMenu, footer, header { visibility: hidden; }

  /* Dark background */
  .stApp, [data-testid="stAppViewContainer"],
  section.main, [data-testid="stHeader"] {
    background-color: #1c1f1a !important;
  }
  [data-testid="block-container"] {
    background-color: #1c1f1a !important;
    padding: 16px 24px 32px !important;
    max-width: 100% !important;
  }

  /* Columns */
  [data-testid="stHorizontalBlock"] { gap: 10px !important; align-items: stretch !important; }
  [data-testid="stColumn"] { padding: 0 !important; }
  [data-testid="stColumn"] > div { height: 100% !important; }
  .element-container { margin: 0 !important; }
  .stMarkdown { width: 100% !important; }

  /* Scrollbar */
  ::-webkit-scrollbar { width: 4px; height: 4px; }
  ::-webkit-scrollbar-track { background: #1c1f1a; }
  ::-webkit-scrollbar-thumb { background: #3d7a6e; border-radius: 2px; }

  /* KPI Cards */
  .kc {
    background: #252923; border: 1px solid #363b33; border-radius: 8px;
    padding: 13px 14px; display: flex; flex-direction: column; gap: 3px;
    height: 100%; box-sizing: border-box;
  }
  .kc.t { border-left: 2.5px solid #3d7a6e; }
  .kc.a { border-left: 2.5px solid #c8963a; }
  .kc-hd { display: flex; align-items: flex-start; justify-content: space-between; gap: 6px; margin-bottom: 1px; }
  .k-lbl  { font-size: 9.5px; text-transform: uppercase; letter-spacing: 0.6px; color: #7a7a6a; font-weight: 600; line-height: 1.3; }
  .k-desc { font-size: 9px; color: #6a6a5a; margin-top: 1px; }
  .k-val  { font-size: 20px; font-weight: 800; color: #e8e4dc; letter-spacing: -0.3px; line-height: 1.1; margin-top: 4px; }
  .k-val.sm { font-size: 14px !important; letter-spacing: -0.2px; }
  .k-dy  { font-size: 10px; font-weight: 600; margin-top: 2px; display: block; }
  .ku  { color: #4a9e6a; }
  .kd  { color: #c05050; }
  .kw  { color: #c8963a; }
  .k-sub { font-size: 9px; color: #6a6a5a; }

  /* Badges */
  .b  { font-size: 8px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;
        padding: 2px 6px; border-radius: 3px; white-space: nowrap; flex-shrink: 0; display: inline-block; }
  .bs { background: rgba(78,154,140,0.12);  color: #4e9a8c; border: 1px solid rgba(78,154,140,0.22); }
  .bg { background: rgba(160,160,144,0.12); color: #a0a090; border: 1px solid rgba(160,160,144,0.22); }
  .bt { background: rgba(200,150,58,0.12);  color: #c8963a; border: 1px solid rgba(200,150,58,0.22); }

  /* Section headers */
  .sh { display: flex; align-items: center; gap: 9px; margin: 20px 0 12px; }
  .sh-t { font-size: 10px; text-transform: uppercase; letter-spacing: 1.1px; color: #7a7a6a; font-weight: 700; white-space: nowrap; }
  .sh-hr { flex: 1; border: none; border-top: 1px solid #363b33; margin: 0; }
  .pill  { font-size: 9px; font-weight: 700; letter-spacing: 0.4px; text-transform: uppercase;
           padding: 2px 7px; border-radius: 20px; white-space: nowrap; }
  .pt  { background: rgba(78,154,140,0.14); color: #4e9a8c; }
  .pm  { background: rgba(122,122,106,0.11); color: #7a7a6a; }
  .pb  { background: rgba(200,150,58,0.12); color: #c8963a; }

  /* Dashboard header */
  .dash-hdr {
    background: #252923; border: 1px solid #363b33; border-radius: 8px;
    padding: 11px 20px; display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 4px;
  }
  .dash-logo { font-size: 17px; font-weight: 800; color: #e8e4dc; text-transform: lowercase; }
  .dash-logo em { color: #4e9a8c; font-style: normal; }
  .dash-date { font-size: 11px; color: #7a7a6a; }
  .dash-date strong { color: #d8d4cc; }

  /* Donut card */
  .donut-card {
    background: #252923; border: 1px solid #363b33; border-radius: 8px;
    padding: 13px 14px; height: 100%; box-sizing: border-box;
  }
  .dc-hd { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
  .dc-title { font-size: 9.5px; text-transform: uppercase; letter-spacing: 0.6px; color: #7a7a6a; font-weight: 600; }
  .donut-leg { display: flex; flex-direction: column; gap: 5px; margin-top: 6px; }
  .dl-row { display: flex; align-items: center; justify-content: space-between;
            padding: 6px 9px; background: #2e332b; border-radius: 5px; }
  .dl-l   { display: flex; align-items: center; gap: 7px; }
  .dl-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
  .dl-name { font-size: 11px; color: #d8d4cc; font-weight: 500; }
  .dl-sub  { font-size: 9px; color: #6a6a5a; }
  .dl-val  { font-size: 11px; font-weight: 700; color: #e8e4dc; text-align: right; }
  .dl-pct  { font-size: 9px; color: #7a7a6a; }

  /* Chart card */
  .chart-card { background: #252923; border: 1px solid #363b33; border-radius: 8px; padding: 15px 18px; }
  .cc-hd { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 8px; gap: 10px; }
  .cc-title { font-size: 12px; font-weight: 700; color: #e8e4dc; }
  .cc-desc  { font-size: 9.5px; color: #7a7a6a; margin-top: 2px; }
  .cc-right { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
  .leg { display: flex; gap: 12px; align-items: center; }
  .leg-item { font-size: 9.5px; color: #7a7a6a; display: flex; align-items: center; gap: 4px; }
  .leg-sq { display: inline-block; width: 9px; height: 9px; border-radius: 2px; }
  .leg-li { display: inline-block; width: 16px; height: 2px; border-radius: 2px; vertical-align: middle; }

  /* B2B placeholder */
  .b2b-soon {
    background: #252923; border: 1px solid rgba(200,150,58,0.25); border-left: 2.5px solid #c8963a;
    border-radius: 8px; padding: 20px 16px; text-align: center; color: #7a7a6a; font-size: 11px;
    height: 100%; box-sizing: border-box; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px;
  }
  .b2b-soon .b2b-icon { font-size: 22px; }
  .b2b-soon .b2b-label { font-size: 9.5px; text-transform: uppercase; letter-spacing: 0.6px; color: #c8963a; font-weight: 700; }

  /* Inline table */
  .dtable { width: 100%; border-collapse: collapse; }
  .dtable th { font-size: 9px; text-transform: uppercase; letter-spacing: 0.5px; color: #7a7a6a; font-weight: 600; padding: 0 8px 8px; border-bottom: 1px solid #363b33; text-align: left; }
  .dtable th:not(:first-child) { text-align: right; }
  .dtable td { padding: 7px 8px; font-size: 11.5px; border-bottom: 1px solid #363b33; color: #d8d4cc; }
  .dtable tr:last-child td { border-bottom: none; }
  .dtable td:not(:first-child) { text-align: right; font-variant-numeric: tabular-nums; }
  .p-rank { color: #6a6a5a; font-size: 9.5px; margin-right: 4px; }
  .p-name { font-weight: 500; }
  .dp { font-size: 9.5px; font-weight: 600; padding: 2px 6px; border-radius: 10px; display: inline-block; }
  .dpu  { background: rgba(74,158,106,0.12); color: #4a9e6a; }
  .dpd  { background: rgba(192,80,74,0.12);  color: #c05050; }
  .dpn  { background: rgba(122,122,106,0.1); color: #7a7a6a; }

  /* Streamlit button override */
  .stButton > button {
    background: #3d7a6e !important; color: white !important; border: none !important;
    border-radius: 5px !important; font-size: 11px !important; font-weight: 600 !important;
    padding: 5px 14px !important;
  }
  .stButton > button:hover { background: #4e9a8c !important; }
</style>
""", unsafe_allow_html=True)


# ── DATE HELPERS ───────────────────────────────────────────────────────────────
def midnight(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 0, 0, 0)

def eod(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 23, 59, 59)

def ly(dt: datetime) -> datetime:
    try:
        return dt.replace(year=dt.year - 1)
    except ValueError:
        return dt.replace(year=dt.year - 1, day=28)

def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ── API ────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_orders(start_iso: str, end_iso: str) -> list:
    orders, url = [], f"{BASE}/orders.json"
    params = {
        "created_at_min": start_iso,
        "created_at_max": end_iso,
        "status": "any",
        "limit": 250,
        "fields": (
            "id,created_at,total_price,customer,"
            "shipping_address,line_items,financial_status,fulfillment_status"
        ),
    }
    while url:
        r = requests.get(url, headers=HEADERS, params=params, timeout=30)
        r.raise_for_status()
        orders += r.json().get("orders", [])
        m = re.search(r'<([^>]+)>;\s*rel="next"', r.headers.get("Link", ""))
        url, params = (m.group(1), {}) if m else (None, {})
    return orders


# ── METRIC HELPERS ─────────────────────────────────────────────────────────────
def revenue(orders):
    return sum(float(o["total_price"]) for o in orders
               if o.get("financial_status") not in SKIP)

def order_count(orders):
    return len([o for o in orders if o.get("financial_status") not in SKIP])

def aov(orders):
    r, c = revenue(orders), order_count(orders)
    return round(r / c, 0) if c else 0.0

def pct(cur, prev):
    if prev == 0:
        return 100.0 if cur > 0 else 0.0
    return round((cur - prev) / prev * 100, 1)

def fmt(n):
    """Format as Norwegian currency"""
    return f"{int(round(n)):,} kr".replace(",", "\u202f")

def new_returning(orders):
    """Count new vs returning customers using orders_count on customer object."""
    new_c = ret_c = 0
    for o in orders:
        if o.get("financial_status") in SKIP:
            continue
        c = o.get("customer")
        if not c:
            new_c += 1
            continue
        try:
            cnt = int(c.get("orders_count") or 0)
        except (ValueError, TypeError):
            cnt = 0
        if cnt > 1:
            ret_c += 1
        else:
            new_c += 1
    return new_c, ret_c

def refund_rate_60d(orders_r60):
    """Refund rate over rolling 60-day window."""
    if not orders_r60:
        return 0.0
    total = len(orders_r60)
    refunded = len([o for o in orders_r60 if o.get("financial_status") == "refunded"])
    return round(refunded / total * 100, 1)

def top_products(orders, n=10):
    p = defaultdict(lambda: {"rev": 0.0, "units": 0})
    for o in orders:
        if o.get("financial_status") in SKIP:
            continue
        for item in o.get("line_items", []):
            key = item.get("title", "Ukjent")
            p[key]["rev"]   += float(item.get("price", 0)) * item.get("quantity", 0)
            p[key]["units"] += item.get("quantity", 0)
    return sorted(p.items(), key=lambda x: x[1]["rev"], reverse=True)[:n]

def geo_split(orders, n=8):
    """Split by city for Norwegian orders, country for international."""
    g = defaultdict(float)
    for o in orders:
        if o.get("financial_status") in SKIP:
            continue
        addr = o.get("shipping_address") or {}
        country_code = (addr.get("country_code") or "").upper()
        if country_code in ("NO", ""):
            loc = addr.get("city") or addr.get("province") or "Norge (ukjent)"
        else:
            loc = addr.get("country") or "Ukjent"
        g[loc] += float(o.get("total_price", 0))
    return sorted(g.items(), key=lambda x: x[1], reverse=True)[:n]

def monthly_revenue(orders):
    """Aggregate orders into dict {month_int: revenue}."""
    m = defaultdict(float)
    for o in orders:
        if o.get("financial_status") in SKIP:
            continue
        month = int(o["created_at"][5:7])
        m[month] += float(o["total_price"])
    return dict(m)


# ── LOAD DATA ──────────────────────────────────────────────────────────────────
def load_data():
    t = date.today()

    # Today
    today_s = midnight(t);  today_e = eod(t)
    # MTD
    mtd_s = midnight(t.replace(day=1));  mtd_e = eod(t)
    # Rolling 60 days (refund rate)
    r60_s = midnight(t - timedelta(days=59));  r60_e = eod(t)
    # Full current year (monthly chart)
    yr_s = midnight(date(t.year, 1, 1));  yr_e = eod(t)
    # Full last year
    ly_yr_s = midnight(date(t.year - 1, 1, 1))
    ly_yr_e = eod(date(t.year - 1, 12, 31))

    today_o    = fetch_orders(iso(today_s),   iso(today_e))
    ly_today_o = fetch_orders(iso(ly(today_s)), iso(ly(today_e)))
    mtd_o      = fetch_orders(iso(mtd_s),     iso(mtd_e))
    ly_mtd_o   = fetch_orders(iso(ly(mtd_s)), iso(ly(mtd_e)))
    r60_o      = fetch_orders(iso(r60_s),     iso(r60_e))
    yr_o       = fetch_orders(iso(yr_s),      iso(yr_e))
    ly_yr_o    = fetch_orders(iso(ly_yr_s),   iso(ly_yr_e))

    return dict(
        today_o=today_o, ly_today_o=ly_today_o,
        mtd_o=mtd_o,     ly_mtd_o=ly_mtd_o,
        r60_o=r60_o,
        yr_o=yr_o,       ly_yr_o=ly_yr_o,
        today=t,
    )


# ── HTML HELPERS ───────────────────────────────────────────────────────────────
def badge(src):
    cls = {"shopify": "bs", "ga4": "bg", "tripletex": "bt"}.get(src, "bs")
    lbl = {"shopify": "Shopify", "ga4": "GA4", "tripletex": "Tripletex"}.get(src, src)
    return f'<span class="b {cls}">{lbl}</span>'

def delta_cls(v):
    if v is None: return "kw"
    return "ku" if v >= 0 else "kd"

def delta_arrow(v):
    return "↑" if v is None or v >= 0 else "↓"

def kpi(label, value, delta_pct, prev_label, src="shopify", accent="", desc="", warn=False):
    val_cls = "k-val sm" if len(str(value)) > 9 else "k-val"
    dcls = "kw" if warn else delta_cls(delta_pct)
    arr  = delta_arrow(None if warn else delta_pct)
    desc_html = f'<div class="k-desc">{desc}</div>' if desc else ""
    dp = abs(delta_pct) if delta_pct is not None else 0.0
    return f"""
<div class="kc {accent}">
  <div class="kc-hd"><span class="k-lbl">{label}</span>{badge(src)}</div>
  {desc_html}
  <div class="{val_cls}">{value}</div>
  <span class="k-dy {dcls}">{arr} {dp:.1f}% vs. i fjor</span>
  <div class="k-sub">{prev_label}</div>
</div>"""

def section_hd(title, pill, pill_cls):
    return (f'<div class="sh"><span class="sh-t">{title}</span>'
            f'<span class="pill {pill_cls}">{pill}</span>'
            f'<hr class="sh-hr"></div>')

def dp_pill(v):
    if v is None or abs(v) < 0.5:
        return '<span class="dp dpn">→ 0%</span>'
    if v >= 0:
        return f'<span class="dp dpu">↑ +{v:.0f}%</span>'
    return f'<span class="dp dpd">↓ {v:.0f}%</span>'


# ── PLOTLY THEME DEFAULTS ──────────────────────────────────────────────────────
DARK = dict(
    paper_bgcolor="#252923",
    plot_bgcolor="#252923",
    font=dict(family="Inter, sans-serif", color="#7a7a6a", size=10),
    margin=dict(l=0, r=0, t=4, b=0),
)
GRID = dict(gridcolor="#2e332b", zerolinecolor="#363b33")


# ══════════════════════════════════════════════════════════════════════════════
#  APP
# ══════════════════════════════════════════════════════════════════════════════

# ── HEADER ────────────────────────────────────────────────────────────────────
now = datetime.now()
hdr_col, btn_col = st.columns([9, 1])
with hdr_col:
    st.markdown(f"""
<div class="dash-hdr">
  <span class="dash-logo">kastel <em>·</em> dashboard</span>
  <span class="dash-date">Oppdatert: <strong>{now.strftime("%A %d. %B %Y, kl. %H:%M")}</strong></span>
</div>""", unsafe_allow_html=True)
with btn_col:
    st.markdown("<div style='padding-top:4px'>", unsafe_allow_html=True)
    if st.button("↻ Oppdater", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

# ── FETCH ─────────────────────────────────────────────────────────────────────
with st.spinner("Henter data fra Shopify…"):
    d = load_data()

today_o    = d["today_o"];    ly_today_o = d["ly_today_o"]
mtd_o      = d["mtd_o"];     ly_mtd_o   = d["ly_mtd_o"]
r60_o      = d["r60_o"]
yr_o       = d["yr_o"];      ly_yr_o    = d["ly_yr_o"]
t          = d["today"]

# Derived values
today_rev   = revenue(today_o);       ly_t_rev  = revenue(ly_today_o)
today_cnt   = order_count(today_o);   ly_t_cnt  = order_count(ly_today_o)
today_aov   = aov(today_o);           ly_t_aov  = aov(ly_today_o)
mtd_rev     = revenue(mtd_o);         ly_m_rev  = revenue(ly_mtd_o)
mtd_cnt     = order_count(mtd_o);     ly_m_cnt  = order_count(ly_mtd_o)
mtd_aov     = aov(mtd_o);             ly_m_aov  = aov(ly_mtd_o)
rr          = refund_rate_60d(r60_o)
ly_rr_o     = d["r60_o"]  # we'll compare LY refund rate below
new_c, ret_c = new_returning(mtd_o)
ly_new, ly_ret = new_returning(ly_mtd_o)
geo_data    = geo_split(mtd_o, 8)
ly_geo      = dict(geo_split(ly_mtd_o, 20))

tp_cur = dict(top_products(mtd_o, 10))
tp_ly  = dict(top_products(ly_mtd_o, 10))
all_keys = sorted(
    set(list(tp_cur.keys()) + list(tp_ly.keys())),
    key=lambda k: tp_cur.get(k, {}).get("rev", 0),
    reverse=True
)[:10]

# Monthly for yearly chart
mo_cur = monthly_revenue(yr_o)
mo_ly  = monthly_revenue(ly_yr_o)
month_names = ["Jan","Feb","Mar","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Des"]
# Mark current month with *
month_labels = [
    (month_names[i] + ("*" if (i + 1) == t.month else ""))
    for i in range(12)
]
y_cur = [mo_cur.get(m, None) for m in range(1, 13)]
y_ly  = [mo_ly.get(m, 0)    for m in range(1, 13)]
# Zero out future months for current year
for i in range(t.month, 12):
    y_cur[i] = None

# LY R60 for comparison
from datetime import timedelta as _td
ly_r60_s = midnight(t - _td(days=59)).replace(year=(t - _td(days=59)).year - 1) if False else \
    midnight((t - timedelta(days=59)).replace(year=(t - timedelta(days=59)).year - 1)
             if (t - timedelta(days=59)).month != 2 or (t - timedelta(days=59)).day != 29
             else (t - timedelta(days=59)).replace(year=(t - timedelta(days=59)).year - 1, day=28))
ly_r60_e = eod(t.replace(year=t.year - 1) if t.month != 2 or t.day != 29
               else t.replace(year=t.year - 1, day=28))
ly_r60_o = fetch_orders(iso(ly_r60_s), iso(ly_r60_e))
ly_rr    = refund_rate_60d(ly_r60_o)


# ══════════════════════════════════════════════════════════════════════════════
#  I DAG
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(section_hd("I dag", t.strftime("%-d. %B %Y"), "pt"), unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(kpi(
        "Omsetning", fmt(today_rev),
        pct(today_rev, ly_t_rev),
        f"i fjor: {fmt(ly_t_rev)}",
        accent="t"
    ), unsafe_allow_html=True)
with c2:
    st.markdown(kpi(
        "Ordrer", str(today_cnt),
        pct(today_cnt, ly_t_cnt),
        f"i fjor: {ly_t_cnt} ordrer",
        accent="t"
    ), unsafe_allow_html=True)
with c3:
    st.markdown(kpi(
        "Snittordre (AOV)", fmt(today_aov),
        pct(today_aov, ly_t_aov),
        f"i fjor: {fmt(ly_t_aov)}",
        accent="t"
    ), unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  DENNE MÅNEDEN
# ══════════════════════════════════════════════════════════════════════════════
mtd_pill = f"1.–{t.day}. {t.strftime('%B %Y')} vs. {t.strftime('%B %Y').replace(str(t.year), str(t.year-1))}"
st.markdown(section_hd("Denne måneden", mtd_pill, "pm"), unsafe_allow_html=True)

# Row 1: 4 Shopify KPI cards + donut (1.7x wide)
c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 1.7])

with c1:
    st.markdown(kpi(
        "Omsetning MTD", fmt(mtd_rev),
        pct(mtd_rev, ly_m_rev),
        f"i fjor: {fmt(ly_m_rev)}"
    ), unsafe_allow_html=True)
with c2:
    st.markdown(kpi(
        "Ordrer MTD", str(mtd_cnt),
        pct(mtd_cnt, ly_m_cnt),
        f"i fjor: {ly_m_cnt}"
    ), unsafe_allow_html=True)
with c3:
    st.markdown(kpi(
        "AOV MTD", fmt(mtd_aov),
        pct(mtd_aov, ly_m_aov),
        f"i fjor: {fmt(ly_m_aov)}"
    ), unsafe_allow_html=True)
with c4:
    warn_rr = rr > ly_rr
    st.markdown(kpi(
        "Refusjonsrate", f"{rr}%",
        pct(rr, ly_rr),
        f"i fjor: {ly_rr}%",
        desc="Rullende 60 dager",
        warn=warn_rr
    ), unsafe_allow_html=True)
with c5:
    # Donut chart + legend
    total_c = new_c + ret_c
    ret_pct = round(ret_c / total_c * 100) if total_c else 0
    new_pct = 100 - ret_pct

    fig_donut = go.Figure(go.Pie(
        labels=["Returnerende", "Nye kunder"],
        values=[ret_c, new_c],
        hole=0.72,
        marker=dict(
            colors=["#3d7a6e", "#2e332b"],
            line=dict(color=["#4e9a8c", "#555"], width=1.5)
        ),
        textinfo="none",
        hovertemplate="%{label}: <b>%{value}</b><extra></extra>",
        sort=False,
    ))
    fig_donut.add_annotation(
        text=f"<b>{total_c}</b><br><span style='font-size:9px'>totalt</span>",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=15, color="#e8e4dc", family="Inter"),
    )
    fig_donut.update_layout(**DARK, height=115, showlegend=False)
    fig_donut.update_layout(margin=dict(l=0, r=0, t=0, b=0))

    ret_chg = pct(ret_c, ly_ret)
    new_chg = pct(new_c, ly_new)
    ret_arr = "↑" if ret_chg >= 0 else "↓"
    new_arr = "↑" if new_chg >= 0 else "↓"
    ret_col = "#4a9e6a" if ret_chg >= 0 else "#c05050"
    new_col = "#4a9e6a" if new_chg >= 0 else "#c05050"

    st.markdown(f"""
<div class="donut-card">
  <div class="dc-hd">
    <span class="dc-title">Nye vs. returnerende kunder</span>
    <span class="b bs">Shopify</span>
  </div>""", unsafe_allow_html=True)
    st.plotly_chart(fig_donut, use_container_width=True, config={"displayModeBar": False})
    st.markdown(f"""
  <div class="donut-leg">
    <div class="dl-row">
      <div class="dl-l">
        <div class="dl-dot" style="background:#3d7a6e;border:1.5px solid #4e9a8c;"></div>
        <div><div class="dl-name">Returnerende</div>
          <div class="dl-sub" style="color:{ret_col}">{ret_arr} {abs(ret_chg):.0f}% vs. i fjor</div></div>
      </div>
      <div><div class="dl-val">{ret_c}</div><div class="dl-pct">{ret_pct}%</div></div>
    </div>
    <div class="dl-row">
      <div class="dl-l">
        <div class="dl-dot" style="background:#2e332b;border:1.5px solid #6a6a5a;"></div>
        <div><div class="dl-name">Nye kunder</div>
          <div class="dl-sub" style="color:{new_col}">{new_arr} {abs(new_chg):.0f}% vs. i fjor</div></div>
      </div>
      <div><div class="dl-val">{new_c}</div><div class="dl-pct">{new_pct}%</div></div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

# Row 2: 4 GA4 placeholder cards
st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
g1, g2, g3, g4 = st.columns(4)

ga_placeholder = """
<div class="kc">
  <div class="kc-hd"><span class="k-lbl">{label}</span><span class="b bg">GA4</span></div>
  <div class="k-desc">{desc}</div>
  <div class="k-val" style="font-size:13px;color:#5a5a4a;margin-top:8px;">Kobles til</div>
  <span class="k-dy kw">Venter på GA4-integrasjon</span>
</div>"""

with g1:
    st.markdown(ga_placeholder.format(label="Besøkende MTD", desc="Unike brukere på kastelshoes.com"), unsafe_allow_html=True)
with g2:
    st.markdown(ga_placeholder.format(label="Konverteringsrate", desc="Besøk som endte i kjøp"), unsafe_allow_html=True)
with g3:
    st.markdown(ga_placeholder.format(label="Abandoned cart rate", desc="Handlekurver ikke betalt"), unsafe_allow_html=True)
with g4:
    st.markdown(ga_placeholder.format(label="Inntekt per besøk", desc="Omsetning / antall besøk"), unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  B2B  (Tripletex — kobles til)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(section_hd("B2B", "via Tripletex · kobles til", "pb"), unsafe_allow_html=True)

b1, b2 = st.columns([1, 3])
with b1:
    st.markdown("""
<div class="b2b-soon">
  <div class="b2b-icon">📊</div>
  <div class="b2b-label">Tripletex</div>
  <div>B2B-omsetning kobles til via Tripletex API. API-nøkkel trengs for aktivering.</div>
</div>""", unsafe_allow_html=True)
with b2:
    st.markdown("""
<div class="b2b-soon">
  <div class="b2b-icon">🏪</div>
  <div class="b2b-label">Topp B2B-kunder</div>
  <div>Topp 5 kunder med fakturert omsetning MTD og vs. i fjor gises her når Tripletex er koblet til.</div>
</div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  MÅNEDLIG OMSETNING — YEARLY CHART
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
st.markdown(f"""
<div class="chart-card">
  <div class="cc-hd">
    <div>
      <div class="cc-title">Månedlig omsetning — {t.year} vs. {t.year - 1}</div>
      <div class="cc-desc">D2C via Shopify · {t.strftime("%B %Y")} er hittil-tall</div>
    </div>
    <div class="cc-right">
      <span class="b bs">Shopify</span>
      <div class="leg" style="margin-left:8px;">
        <div class="leg-item"><span class="leg-sq" style="background:#3d7a6e;"></span>{t.year}</div>
        <div class="leg-item"><span class="leg-sq" style="background:rgba(55,60,50,0.9);border:1px solid #555;"></span>{t.year-1}</div>
      </div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

fig_yr = go.Figure()
fig_yr.add_trace(go.Bar(
    x=month_labels, y=y_cur,
    name=str(t.year),
    marker=dict(color="#3d7a6e", line=dict(color="#4e9a8c", width=1)),
    hovertemplate="<b>%{x} %s</b><br>%{y:,.0f} kr<extra></extra>" % t.year,
))
fig_yr.add_trace(go.Bar(
    x=month_labels, y=y_ly,
    name=str(t.year - 1),
    marker=dict(color="rgba(55,60,50,0.8)", line=dict(color="#4a4f46", width=1)),
    hovertemplate="<b>%{x} %s</b><br>%{y:,.0f} kr<extra></extra>" % (t.year - 1),
))
fig_yr.update_layout(
    **DARK,
    height=230,
    barmode="group",
    bargap=0.25,
    bargroupgap=0.05,
    showlegend=False,
    xaxis=dict(showgrid=False, tickfont=dict(size=10, color="#5a5a4a")),
    yaxis=dict(
        **GRID,
        tickfont=dict(size=10, color="#5a5a4a"),
        tickformat=".2s",
        ticksuffix=" kr",
    ),
    hovermode="x unified",
)
# Format y-axis in M
fig_yr.update_yaxes(
    tickvals=[0, 500_000, 1_000_000, 1_500_000, 2_000_000],
    ticktext=["0", "0.5M", "1M", "1.5M", "2M"],
)
st.plotly_chart(fig_yr, use_container_width=True, config={"displayModeBar": False})


# ══════════════════════════════════════════════════════════════════════════════
#  TOPP PRODUKTER + REGIONER
# ══════════════════════════════════════════════════════════════════════════════
col_prod, col_geo = st.columns(2)

with col_prod:
    rows_html = ""
    for i, k in enumerate(all_keys):
        cr = tp_cur.get(k, {}).get("rev", 0)
        pr = tp_ly.get(k, {}).get("rev", 0)
        chg = pct(cr, pr) if pr > 0 else None
        rows_html += f"""
<tr>
  <td><span class="p-rank">{i+1}</span><span class="p-name">{k}</span></td>
  <td>{fmt(cr)}</td>
  <td>{dp_pill(chg)}</td>
</tr>"""

    st.markdown(f"""
<div class="chart-card">
  <div class="cc-hd">
    <div>
      <div class="cc-title">Topp produkter</div>
      <div class="cc-desc">D2C omsetning · {t.strftime("%B %Y")} vs. {t.strftime("%B")} {t.year-1}</div>
    </div>
    <span class="b bs">Shopify</span>
  </div>
  <table class="dtable">
    <thead><tr><th>Produkt</th><th>Omsetning MTD</th><th>vs. i fjor</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>""", unsafe_allow_html=True)

with col_geo:
    geo_rows = ""
    for loc, rev_val in geo_data:
        ly_rev_val = ly_geo.get(loc, 0)
        chg = pct(rev_val, ly_rev_val) if ly_rev_val > 0 else None
        geo_rows += f"""
<tr>
  <td>{loc}</td>
  <td>{fmt(rev_val)}</td>
  <td>{dp_pill(chg)}</td>
</tr>"""

    st.markdown(f"""
<div class="chart-card">
  <div class="cc-hd">
    <div>
      <div class="cc-title">Omsetning per region</div>
      <div class="cc-desc">D2C · {t.strftime("%B %Y")} vs. {t.strftime("%B")} {t.year-1}</div>
    </div>
    <span class="b bs">Shopify</span>
  </div>
  <table class="dtable">
    <thead><tr><th>Region</th><th>Omsetning MTD</th><th>vs. i fjor</th></tr></thead>
    <tbody>{geo_rows}</tbody>
  </table>
</div>""", unsafe_allow_html=True)
