"""
Kastel Shoes – Live Shopify Dashboard
Streamlit-versjon · kjøres automatisk på streamlit.io
"""

import re
from datetime import date, datetime, timedelta
from collections import defaultdict

import requests
import streamlit as st
import plotly.graph_objects as go
import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────────
SHOP    = "kastel-shoes.myshopify.com"
TOKEN   = st.secrets.get("SHOPIFY_TOKEN", "6050b0963a3b59837b598922fd15e204")
VERSION = "2024-10"
HEADERS = {"X-Shopify-Access-Token": TOKEN}
BASE    = f"https://{SHOP}/admin/api/{VERSION}"

SKIP = ("voided", "refunded")

# ── Page setup ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Kastel Shoes Dashboard",
    page_icon="👟",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  /* Hide Streamlit chrome */
  #MainMenu, footer, header { visibility: hidden; }

  /* Font */
  html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }

  /* Metric card tweaks */
  [data-testid="metric-container"] {
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 16px 20px 14px;
    box-shadow: 0 1px 2px rgba(0,0,0,.04);
  }
  [data-testid="stMetricLabel"] { font-size: 11px !important; color: #6b7280 !important; text-transform: uppercase; letter-spacing: .5px; }
  [data-testid="stMetricValue"] { font-size: 26px !important; font-weight: 700 !important; color: #0f172a !important; }
  [data-testid="stMetricDelta"] svg { display: none; }

  /* Section headers */
  .sec { font-size: 11px; font-weight: 700; color: #9ca3af; text-transform: uppercase;
         letter-spacing: .8px; margin: 28px 0 10px; }

  /* Dashboard header */
  .dash-hdr {
    background: #0f172a; color: white;
    padding: 18px 28px; border-radius: 10px;
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 24px;
  }
  .dash-hdr h1 { font-size: 20px; font-weight: 700; }
  .dash-hdr h1 em { color: #f43f5e; font-style: normal; }
  .dash-hdr small { font-size: 12px; color: #94a3b8; }
</style>
""", unsafe_allow_html=True)


# ── Date helpers ──────────────────────────────────────────────────────────────
def midnight(d: date) -> datetime:
    return datetime(d.year, d.month, d.day)

def eod(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 23, 59, 59)

def ly(dt: datetime) -> datetime:
    try:
        return dt.replace(year=dt.year - 1)
    except ValueError:
        return dt.replace(year=dt.year - 1, day=28)


# ── API ───────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=1800, show_spinner=False)   # 30 min cache
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


# ── Metric helpers ────────────────────────────────────────────────────────────
def revenue(orders):
    return sum(float(o["total_price"]) for o in orders
               if o.get("financial_status") not in SKIP)

def order_count(orders):
    return len([o for o in orders if o.get("financial_status") not in SKIP])

def aov(orders):
    r, c = revenue(orders), order_count(orders)
    return round(r / c, 0) if c else 0

def pct(cur, prev):
    if prev == 0:
        return 100.0 if cur > 0 else 0.0
    return round((cur - prev) / prev * 100, 1)

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

def new_returning(orders):
    new = ret = 0
    for o in orders:
        c = o.get("customer")
        if c and int(c.get("orders_count", 1)) > 1:
            ret += 1
        else:
            new += 1
    return new, ret

def geo_split(orders, n=12):
    g = defaultdict(int)
    for o in orders:
        addr = o.get("shipping_address") or {}
        g[addr.get("country") or "Ukjent"] += 1
    return sorted(g.items(), key=lambda x: x[1], reverse=True)[:n]

def daily_series(orders, start: datetime, days=30):
    bucket = defaultdict(float)
    for o in orders:
        if o.get("financial_status") in SKIP:
            continue
        bucket[o["created_at"][:10]] += float(o["total_price"])
    return [
        [
            (start + timedelta(days=i)).strftime("%Y-%m-%d"),
            round(bucket[(start + timedelta(days=i)).strftime("%Y-%m-%d")], 0),
        ]
        for i in range(days)
    ]

def fulfillment_rate(orders):
    paid = [o for o in orders if o.get("financial_status") == "paid"]
    if not paid:
        return 0.0
    return round(len([o for o in paid if o.get("fulfillment_status") == "fulfilled"]) / len(paid) * 100, 1)

def refund_rate(orders):
    if not orders:
        return 0.0
    return round(len([o for o in orders if o.get("financial_status") == "refunded"]) / len(orders) * 100, 1)

def avg_items(orders):
    paid = [o for o in orders if o.get("financial_status") not in SKIP]
    if not paid:
        return 0.0
    total = sum(sum(i.get("quantity", 0) for i in o.get("line_items", [])) for o in paid)
    return round(total / len(paid), 1)

def fmt_nok(n):
    return f"{int(n):,} kr".replace(",", "\u202f")


# ── Load all data ─────────────────────────────────────────────────────────────
def load_data():
    t = date.today()

    today_s  = midnight(t);  today_e  = eod(t)
    mtd_s    = midnight(t.replace(day=1)); mtd_e = eod(t)
    d30_s    = midnight(t - timedelta(days=29)); d30_e = eod(t)

    def iso(dt): return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    today_o    = fetch_orders(iso(today_s), iso(today_e))
    ly_today_o = fetch_orders(iso(ly(today_s)), iso(ly(today_e)))
    mtd_o      = fetch_orders(iso(mtd_s), iso(mtd_e))
    ly_mtd_o   = fetch_orders(iso(ly(mtd_s)), iso(ly(mtd_e)))
    d30_o      = fetch_orders(iso(d30_s), iso(d30_e))
    ly_d30_o   = fetch_orders(iso(ly(d30_s)), iso(ly(d30_e)))

    return dict(
        today_o=today_o, ly_today_o=ly_today_o,
        mtd_o=mtd_o, ly_mtd_o=ly_mtd_o,
        d30_o=d30_o, ly_d30_o=ly_d30_o,
        d30_s=d30_s,
    )


# ── App layout ────────────────────────────────────────────────────────────────
# Header
col_hdr, col_btn = st.columns([6, 1])
with col_hdr:
    st.markdown(
        f"""<div class="dash-hdr">
          <h1>Kastel&nbsp;<em>Shoes</em>&nbsp;Dashboard</h1>
          <small>Oppdateres automatisk · {datetime.now().strftime("%d.%m.%Y kl. %H:%M")}</small>
        </div>""",
        unsafe_allow_html=True,
    )
with col_btn:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Oppdater", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── Fetch ─────────────────────────────────────────────────────────────────────
with st.spinner("Henter data fra Shopify…"):
    d = load_data()

today_o = d["today_o"];    ly_today_o = d["ly_today_o"]
mtd_o   = d["mtd_o"];     ly_mtd_o   = d["ly_mtd_o"]
d30_o   = d["d30_o"];     ly_d30_o   = d["ly_d30_o"]
d30_s   = d["d30_s"]

# Derived
today_rev  = round(revenue(today_o), 0)
ly_t_rev   = round(revenue(ly_today_o), 0)
mtd_rev    = round(revenue(mtd_o), 0)
ly_m_rev   = round(revenue(ly_mtd_o), 0)
cur_aov    = aov(mtd_o)
ly_aov_v   = aov(ly_mtd_o)
new_c, ret_c = new_returning(mtd_o)
geo_data   = geo_split(mtd_o, 12)

series_cur = daily_series(d30_o, d30_s, 30)
series_ly  = daily_series(ly_d30_o, ly(d30_s), 30)

tp_cur = dict(top_products(mtd_o, 10))
tp_ly  = dict(top_products(ly_mtd_o, 10))
all_keys = sorted(
    set(list(tp_cur.keys()) + list(tp_ly.keys())),
    key=lambda k: tp_cur.get(k, {}).get("rev", 0),
    reverse=True
)[:10]


# ── KPI row ───────────────────────────────────────────────────────────────────
st.markdown('<p class="sec">Nøkkeltall</p>', unsafe_allow_html=True)

k1, k2, k3, k4, k5, k6, k7 = st.columns(7)

k1.metric("Omsetning i dag",
          fmt_nok(today_rev),
          f"{pct(today_rev, ly_t_rev):+.1f}% vs LY ({fmt_nok(ly_t_rev)})")

k2.metric("Omsetning MTD",
          fmt_nok(mtd_rev),
          f"{pct(mtd_rev, ly_m_rev):+.1f}% vs LY ({fmt_nok(ly_m_rev)})")

k3.metric("AOV MTD",
          fmt_nok(cur_aov),
          f"{pct(cur_aov, ly_aov_v):+.1f}% vs LY")

k4.metric("Ordrer MTD",
          order_count(mtd_o),
          f"{pct(order_count(mtd_o), order_count(ly_mtd_o)):+.1f}% vs LY")

k5.metric("Nye kunder MTD",
          new_c,
          f"Returnerende: {ret_c}")

k6.metric("Fulfilment-rate",
          f"{fulfillment_rate(mtd_o)}%",
          "Betalte ordrer MTD")

k7.metric("Refund-rate",
          f"{refund_rate(mtd_o)}%",
          f"Snitt {avg_items(mtd_o)} varer/ordre")


# ── Daily chart ───────────────────────────────────────────────────────────────
st.markdown('<p class="sec">Omsetning over tid</p>', unsafe_allow_html=True)

fig_daily = go.Figure()
fig_daily.add_trace(go.Scatter(
    x=[s[0] for s in series_cur],
    y=[s[1] for s in series_cur],
    name="I år",
    line=dict(color="#0f172a", width=2.5),
    fill="tozeroy",
    fillcolor="rgba(15,23,42,0.06)",
    mode="lines+markers",
    marker=dict(size=4),
    hovertemplate="%{x}<br><b>%{y:,.0f} kr</b><extra>I år</extra>",
))
fig_daily.add_trace(go.Scatter(
    x=[s[0] for s in series_ly],
    y=[s[1] for s in series_ly],
    name="I fjor",
    line=dict(color="#f43f5e", width=2, dash="dot"),
    mode="lines+markers",
    marker=dict(size=3),
    hovertemplate="%{x}<br><b>%{y:,.0f} kr</b><extra>I fjor</extra>",
))
fig_daily.update_layout(
    height=300,
    margin=dict(l=0, r=0, t=10, b=0),
    paper_bgcolor="white",
    plot_bgcolor="white",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    xaxis=dict(showgrid=False, tickfont=dict(size=11, color="#9ca3af")),
    yaxis=dict(gridcolor="#f1f5f9", tickfont=dict(size=11, color="#9ca3af"),
               tickformat=",.0f", ticksuffix=" kr"),
    hovermode="x unified",
)
st.plotly_chart(fig_daily, use_container_width=True)


# ── Customers + Geo ───────────────────────────────────────────────────────────
st.markdown('<p class="sec">Kunder &amp; Geografi</p>', unsafe_allow_html=True)

col_nr, col_geo = st.columns(2)

with col_nr:
    fig_nr = go.Figure(go.Pie(
        labels=["Nye kunder", "Returnerende"],
        values=[new_c, ret_c],
        hole=0.65,
        marker=dict(colors=["#0f172a", "#f43f5e"], line=dict(width=0)),
        textfont=dict(size=13),
        hovertemplate="%{label}: <b>%{value}</b> ordrer<extra></extra>",
    ))
    fig_nr.update_layout(
        title=dict(text="Nye vs. returnerende kunder (MTD)", font=dict(size=13, color="#374151"), x=0),
        height=300,
        margin=dict(l=0, r=0, t=40, b=0),
        paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
        annotations=[dict(
            text=f"<b>{new_c + ret_c}</b><br>ordrer",
            x=0.5, y=0.5, font_size=15, showarrow=False
        )],
    )
    st.plotly_chart(fig_nr, use_container_width=True)

with col_geo:
    geo_labels = [g[0] for g in geo_data]
    geo_values = [g[1] for g in geo_data]
    fig_geo = go.Figure(go.Bar(
        x=geo_values,
        y=geo_labels,
        orientation="h",
        marker=dict(color="#0f172a", line=dict(width=0)),
        hovertemplate="%{y}: <b>%{x}</b> ordrer<extra></extra>",
    ))
    fig_geo.update_layout(
        title=dict(text="Geografisk fordeling – topp land (MTD)", font=dict(size=13, color="#374151"), x=0),
        height=300,
        margin=dict(l=0, r=0, t=40, b=0),
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis=dict(showgrid=True, gridcolor="#f1f5f9", tickfont=dict(size=11, color="#9ca3af")),
        yaxis=dict(showgrid=False, tickfont=dict(size=11, color="#374151"),
                   categoryorder="total ascending"),
    )
    st.plotly_chart(fig_geo, use_container_width=True)


# ── Top products table ────────────────────────────────────────────────────────
st.markdown('<p class="sec">Topp produkter</p>', unsafe_allow_html=True)

rows = []
for k in all_keys:
    cur_rev  = tp_cur.get(k, {}).get("rev", 0)
    prev_rev = tp_ly.get(k, {}).get("rev", 0)
    change   = pct(cur_rev, prev_rev)
    rows.append({
        "Produkt":       k,
        "Omsetning MTD": round(cur_rev, 0),
        "Omsetning LY":  round(prev_rev, 0),
        "Endring %":     change,
        "Enheter":       tp_cur.get(k, {}).get("units", 0),
    })

df = pd.DataFrame(rows)

def color_change(val):
    color = "#10b981" if val >= 0 else "#ef4444"
    return f"color: {color}; font-weight: 600"

styled = (
    df.style
    .format({
        "Omsetning MTD": lambda x: fmt_nok(x),
        "Omsetning LY":  lambda x: fmt_nok(x),
        "Endring %":     lambda x: f"{'▲' if x >= 0 else '▼'} {abs(x):.1f}%",
    })
    .map(color_change, subset=["Endring %"])
    .set_properties(**{"text-align": "left"})
    .set_properties(subset=["Omsetning MTD", "Omsetning LY", "Endring %", "Enheter"],
                    **{"text-align": "right"})
)

st.dataframe(styled, use_container_width=True, hide_index=True, height=390)
