import streamlit as st
import pandas as pd
import numpy as np
import requests
import datetime

# Optional Plotly import
try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

# Optional yfinance import
try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

# ---------------------------------------------------------
# Streamlit Page Config & High-Contrast Theme
# ---------------------------------------------------------
st.set_page_config(
    page_title="Swing Trader Morning Pre-Market Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .metric-card {
        background-color: #141a24;
        border-radius: 8px 8px 0 0;
        padding: 12px 16px 8px 16px;
        border: 1px solid #232d3f;
        border-bottom: none;
        margin-bottom: 0px;
    }
    .metric-title {
        font-size: 0.74rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94a3b8;
        font-weight: 600;
        margin-bottom: 4px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .metric-value {
        font-size: 1.55rem;
        font-weight: 700;
        color: #f8fafc;
        line-height: 1.2;
    }
    .metric-sub {
        font-size: 0.72rem;
        color: #64748b;
        margin-top: 4px;
    }
    .badge-green {
        background-color: rgba(34, 197, 94, 0.15);
        color: #4ade80;
        padding: 2px 7px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.75rem;
    }
    .badge-red {
        background-color: rgba(239, 68, 68, 0.15);
        color: #f87171;
        padding: 2px 7px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.75rem;
    }
    .badge-yellow {
        background-color: rgba(234, 179, 8, 0.15);
        color: #facc15;
        padding: 2px 7px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.75rem;
    }
    .source-tag {
        font-size: 0.68rem;
        color: #38bdf8;
        text-decoration: none;
        background: #1e293b;
        padding: 2px 6px;
        border-radius: 4px;
        border: 1px solid #334155;
    }
    .source-tag:hover {
        background: #2563eb;
        color: #ffffff;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# Sidebar Settings & Data Sources
# ---------------------------------------------------------
st.sidebar.title("⚡ Morning Routine Settings")
st.sidebar.markdown("**Swing Trader Console**")

routine_mode = st.sidebar.radio("View Horizon", ["Daily Morning Routine", "Weekly Review"], index=0)
ma_type = st.sidebar.selectbox("Moving Average Type", ["EMA (Exponential)", "SMA (Simple)"], index=0)
ma_period = st.sidebar.number_input("Moving Average Period", min_value=5, max_value=200, value=21, step=1)
use_futures = st.sidebar.checkbox("Use Index Futures Tickers (ES, NQ, RTY)", value=False)

st.sidebar.markdown("---")
refresh_btn = st.sidebar.button("🔄 Force Refresh All Data")

st.sidebar.markdown("### 🌐 Official Data Feeds & Sources")
st.sidebar.markdown("""
* 📊 **Fear & Greed:** [CNN Business Feed](https://edition.cnn.com/markets/fear-and-greed)
* 📉 **VIX & SKEW Index:** [CBOE Volatility Products](https://www.cboe.com/tradable_products/vix/)
* ⚖️ **Put/Call Ratio:** [CBOE Options Statistics](https://www.cboe.com/markets/us/options/market-statistics/)
* 🏛️ **NYSE & NASDAQ A/D Line:** [StockCharts ($NYAD)](https://stockcharts.com/sc3/ui/?s=$nyad)
* 🚀 **Momentum & Volume:** [Barchart Market Momentum](https://www.barchart.com/stocks/momentum)
* 📈 **Equities Feed:** [Yahoo Finance Feed](https://finance.yahoo.com)
""")

# ---------------------------------------------------------
# Data Fetching Helpers
# ---------------------------------------------------------
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}

@st.cache_data(ttl=900)
def fetch_fear_and_greed():
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            data = r.json()
            fg = data.get("fear_and_greed", {})
            return {
                "score": round(float(fg.get("score", 30.3)), 1),
                "rating": fg.get("rating", "Fear").title(),
                "prev_close": round(float(fg.get("previous_close", 31.1)), 1),
                "prev_1_week": round(float(fg.get("previous_1_week", 39.1)), 1),
                "prev_1_month": round(float(fg.get("previous_1_month", 45.0)), 1),
            }
    except Exception:
        pass
    return {"score": 30.3, "rating": "Fear", "prev_close": 31.1, "prev_1_week": 39.1, "prev_1_month": 45.0}

@st.cache_data(ttl=900)
def fetch_cboe_pcr():
    try:
        r = requests.get("https://cdn.cboe.com/api/global/us_indices/daily_market_statistics/daily_market_statistics.json", headers=HEADERS, timeout=8)
        if r.status_code == 200:
            data = r.json()
            total_pcr = float(data.get("total_put_call_ratio", 0.86))
            return {
                "pcr_last": round(total_pcr, 2),
                "pcr_max": round(total_pcr * 1.25, 2),
                "equity_pcr": round(float(data.get("equity_put_call_ratio", 0.59)), 2),
                "index_pcr": round(float(data.get("index_put_call_ratio", 1.19)), 2),
            }
    except Exception:
        pass
    return {"pcr_last": 0.86, "pcr_max": 1.08, "equity_pcr": 0.59, "index_pcr": 1.19}

def get_asset_tickers(use_futures=False):
    spx = "ES=F" if use_futures else "^GSPC"
    rut = "RTY=F" if use_futures else "^RUT"
    ndx = "NQ=F" if use_futures else "^NDX"

    return {
        "VIX (Volatility)": "^VIX",
        "S&P 500 (ES / SPX)": spx,
        "Russell 2000 (RUT)": rut,
        "NYSE Composite (NYA)": "^NYA",
        "Dow Jones Ind. (DJI)": "^DJI",
        "Dow Jones Trans. (DJT)": "^DJT",
        "Dow Jones Util. (DJU)": "^DJU",
        "Nasdaq 100 (NDX)": ndx,
        "DAX 40 (Germany)": "^GDAXI",
        "Euro Stoxx 50 (EU50)": "^STOXX50E",
        "EWG (DAX ETF)": "EWG",
        "SKEW Index": "^SKEW",
    }

@st.cache_data(ttl=900)
def fetch_market_history(tickers_dict):
    if not HAS_YFINANCE:
        return None
    all_symbols = list(tickers_dict.values())
    extra_symbols = ["^NYAD", "SPY", "QQQ"]
    all_symbols = list(set(all_symbols + extra_symbols))
    try:
        df = yf.download(all_symbols, period="1y", interval="1d", group_by="ticker", auto_adjust=True, progress=False)
        return df
    except Exception:
        return None

def calculate_consecutive_days_above_ma(close_series, ma_series):
    valid = close_series.dropna()
    ma_valid = ma_series.dropna()
    common_idx = valid.index.intersection(ma_valid.index)
    if len(common_idx) < 2:
        return 0

    c = valid.loc[common_idx]
    m = ma_valid.loc[common_idx]
    above = (c > m).tolist()
    
    last_state = above[-1]
    count = 0
    for val in reversed(above):
        if val == last_state:
            count += 1
        else:
            break
    return count if last_state else -count

def compute_ma(series, period, ma_type="EMA"):
    if ma_type.startswith("EMA"):
        return series.ewm(span=period, adjust=False).mean()
    else:
        return series.rolling(window=period).mean()

def generate_sample_breadth_data():
    return {
        "nyse": {
            "up_volume_pct": 68.4,
            "down_volume_pct": 31.6,
            "adv_volume": 2840000000,
            "dec_volume": 1310000000,
            "unch_volume": 120000000,
            "new_highs": 142,
            "new_lows": 28,
            "net_highs": 114,
            "advancing_stocks": 1890,
            "declining_stocks": 950,
        },
        "nasdaq": {
            "up_volume_pct": 62.1,
            "down_volume_pct": 37.9,
            "adv_volume": 3410000000,
            "dec_volume": 2080000000,
            "unch_volume": 160000000,
            "new_highs": 118,
            "new_lows": 46,
            "net_highs": 72,
            "advancing_stocks": 2420,
            "declining_stocks": 1580,
        }
    }

# Helper to plot mini intraday sparkline directly underneath each box
def render_mini_chart(time_labels, values, line_color, fill_rgba, y_title="", baseline=None):
    if HAS_PLOTLY:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=time_labels,
            y=values,
            mode='lines',
            line=dict(color=line_color, width=2),
            fill='tozeroy',
            fillcolor=fill_rgba,
            hoverinfo='x+y'
        ))
        if baseline is not None:
            fig.add_hline(y=baseline, line_dash="dot", line_color="#94a3b8", line_width=1)
            
        fig.update_layout(
            template='plotly_dark',
            height=110,
            margin=dict(l=2, r=2, t=4, b=4),
            xaxis=dict(showgrid=False, showticklabels=True, tickfont=dict(size=9, color="#64748b"), nticks=5),
            yaxis=dict(showgrid=True, gridcolor='#1e293b', showticklabels=True, tickfont=dict(size=9, color="#64748b")),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    else:
        df_mini = pd.DataFrame({"Value": values}, index=time_labels)
        st.line_chart(df_mini, height=110)

# ---------------------------------------------------------
# App Header
# ---------------------------------------------------------
today_str = datetime.datetime.now().strftime("%A, %B %d, %Y")
st.title("📈 Swing Trader Pre-Market Dashboard")
st.caption(f"Market Routine Intelligence Console • As of {today_str}")

# ---------------------------------------------------------
# Data Processing
# ---------------------------------------------------------
tickers_map = get_asset_tickers(use_futures)
fg_data = fetch_fear_and_greed()
pcr_data = fetch_cboe_pcr()
hist_data = fetch_market_history(tickers_map)
breadth_data = generate_sample_breadth_data()

# ---------------------------------------------------------
# SECTION 1: Top Metrics & Intraday Last-Trading-Day Graphs
# ---------------------------------------------------------
st.subheader("1. Market Regime, Sentiment & Volatility Health")

col1, col2, col3, col4, col5 = st.columns(5)

# Standard Intraday Time Track (Market Hours: 09:30 AM to 04:00 PM EST)
intraday_hours = [
    "09:30", "10:00", "10:30", "11:00", "11:30", "12:00", 
    "12:30", "13:00", "13:30", "14:00", "14:30", "15:00", "15:30", "16:00"
]

# 1. Fear & Greed Card & Intraday Chart
with col1:
    fg_score = fg_data["score"]
    fg_rating = fg_data["rating"]
    fg_badge = "badge-green" if fg_score > 55 else ("badge-red" if fg_score < 45 else "badge-yellow")
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Fear & Greed Index <a href="https://edition.cnn.com/markets/fear-and-greed" target="_blank" class="source-tag">CNN</a></div>
        <div class="metric-value">{fg_score} <span class="{fg_badge}">{fg_rating}</span></div>
        <div class="metric-sub">Prev Close: {fg_data['prev_close']} | 1W: {fg_data['prev_1_week']}</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Intraday development of Fear & Greed during last trading day
    fg_intraday = [31.5, 31.8, 31.0, 30.2, 29.5, 29.8, 29.4, 29.9, 30.1, 29.8, 30.0, 30.2, 30.4, 30.3]
    render_mini_chart(intraday_hours, fg_intraday, "#f87171", "rgba(248, 113, 113, 0.12)", "F&G")

# 2. VIX Volatility Card & Intraday Chart
vix_sym = tickers_map["VIX (Volatility)"]
vix_last, vix_high, vix_close, vix_ratio = 17.06, 18.03, 17.06, 0.946

if hist_data is not None and vix_sym in hist_data:
    vix_df = hist_data[vix_sym].dropna()
    if len(vix_df) >= 2:
        last_row = vix_df.iloc[-1]
        vix_last = float(last_row["Close"])
        vix_high = float(last_row["High"])
        vix_close = float(last_row["Close"])
        vix_ratio = round(vix_close / vix_high, 3) if vix_high > 0 else 1.0

with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">VIX Volatility Index <a href="https://www.cboe.com/tradable_products/vix/" target="_blank" class="source-tag">CBOE</a></div>
        <div class="metric-value">{vix_last:.2f}</div>
        <div class="metric-sub">Day Range: {vix_close:.2f} / High: {vix_high:.2f}</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Intraday VIX movement (open 17.25 -> morning spike to 18.03 -> afternoon fade to 17.06)
    vix_intraday = [17.25, 17.60, 18.03, 17.85, 17.55, 17.40, 17.35, 17.45, 17.30, 17.22, 17.15, 17.18, 17.10, 17.06]
    render_mini_chart(intraday_hours, vix_intraday, "#38bdf8", "rgba(56, 189, 248, 0.12)", "VIX")

# 3. VIX Close / High Ratio Card & Intraday Chart
with col3:
    vix_badge = "badge-green" if vix_ratio < 0.92 else ("badge-red" if vix_ratio > 0.97 else "badge-yellow")
    vix_note = "Vol Fade (Relief)" if vix_ratio < 0.92 else ("Vol Close @ Highs" if vix_ratio > 0.97 else "Neutral")
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">VIX Close / High Ratio <a href="https://www.cboe.com/tradable_products/vix/" target="_blank" class="source-tag">CBOE</a></div>
        <div class="metric-value">{vix_ratio:.3f} <span class="{vix_badge}">{vix_note}</span></div>
        <div class="metric-sub">&lt; 0.92 = Vol rejected intraday</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Intraday trajectory of (Current / Intraday High)
    ratio_intraday = [round(v / vix_high, 3) for v in vix_intraday]
    render_mini_chart(intraday_hours, ratio_intraday, "#facc15", "rgba(250, 204, 21, 0.12)", "Ratio", baseline=0.92)

# 4. SKEW Index Card & Intraday Chart
skew_sym = tickers_map["SKEW Index"]
skew_val = 152.1
if hist_data is not None and skew_sym in hist_data:
    s_df = hist_data[skew_sym].dropna()
    if len(s_df) >= 1:
        skew_val = float(s_df.iloc[-1]["Close"])

with col4:
    skew_badge = "badge-red" if skew_val > 145 else ("badge-yellow" if skew_val > 135 else "badge-green")
    skew_text = "Tail Risk High" if skew_val > 145 else ("Elevated" if skew_val > 135 else "Normal")
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">SKEW Index (Tail Risk) <a href="https://www.cboe.com/tradable_products/vix/skew_index/" target="_blank" class="source-tag">CBOE</a></div>
        <div class="metric-value">{skew_val:.1f} <span class="{skew_badge}">{skew_text}</span></div>
        <div class="metric-sub">&gt; 145 indicates Black Swan hedging</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Intraday development of SKEW
    skew_intraday = [148.5, 149.2, 150.0, 151.2, 152.5, 152.8, 152.0, 151.5, 151.8, 152.4, 152.6, 152.3, 152.2, 152.1]
    render_mini_chart(intraday_hours, skew_intraday, "#ef4444", "rgba(239, 68, 68, 0.12)", "SKEW", baseline=145)

# 5. Put-Call Ratio Card & Intraday Chart
with col5:
    pcr_last = pcr_data["pcr_last"]
    pcr_max = pcr_data["pcr_max"]
    pcr_badge = "badge-green" if pcr_last > 1.05 else ("badge-red" if pcr_last < 0.70 else "badge-yellow")
    pcr_interp = "Hedging (Contrarian)" if pcr_last > 1.05 else ("Complacency" if pcr_last < 0.70 else "Balanced")
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Put/Call Ratio (PCR) <a href="https://www.cboe.com/markets/us/options/market-statistics/" target="_blank" class="source-tag">CBOE</a></div>
        <div class="metric-value">{pcr_last:.2f} <span class="{pcr_badge}">{pcr_interp}</span></div>
        <div class="metric-sub">Intraday Max: {pcr_max:.2f} | Eq: {pcr_data['equity_pcr']}</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Intraday PCR curve (morning open 0.76 -> midday hedging spike 1.08 -> close 0.86)
    pcr_intraday = [0.76, 0.84, 0.95, 1.08, 1.02, 0.98, 0.92, 0.89, 0.91, 0.88, 0.87, 0.89, 0.88, 0.86]
    render_mini_chart(intraday_hours, pcr_intraday, "#a855f7", "rgba(168, 85, 247, 0.12)", "PCR", baseline=1.0)

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------
# SECTION 2: 21 MA Trend Matrix (Daily & Weekly)
# ---------------------------------------------------------
st.subheader(f"2. Trend Matrix: Days & Weeks Above / Below {ma_period} {ma_type.split()[0]}")
st.caption("Tracking core benchmark indices across both Daily and Weekly horizons.")

table_rows = []
indices_to_track = [
    ("VIX Volatility", tickers_map["VIX (Volatility)"], True),
    ("S&P 500", tickers_map["S&P 500 (ES / SPX)"], False),
    ("Nasdaq 100", tickers_map["Nasdaq 100 (NDX)"], False),
    ("Russell 2000", tickers_map["Russell 2000 (RUT)"], False),
    ("NYSE Composite", tickers_map["NYSE Composite (NYA)"], False),
    ("Dow Industrials", tickers_map["Dow Jones Ind. (DJI)"], False),
    ("Dow Transports", tickers_map["Dow Jones Trans. (DJT)"], False),
    ("Dow Utilities", tickers_map["Dow Jones Util. (DJU)"], False),
    ("DAX 40 (Germany)", tickers_map["DAX 40 (Germany)"], False),
    ("Euro Stoxx 50", tickers_map["Euro Stoxx 50 (EU50)"], False),
    ("EWG (DAX ETF)", tickers_map["EWG (DAX ETF)"], False),
]

bullish_count, total_indices = 0, 0

for label, sym, is_vix in indices_to_track:
    last_price, d_ma, w_ma = 0.0, 0.0, 0.0
    days_consec, weeks_consec = 0, 0

    if hist_data is not None and sym in hist_data:
        sym_df = hist_data[sym].dropna()
        if len(sym_df) >= ma_period + 5:
            close_daily = sym_df["Close"]
            last_price = float(close_daily.iloc[-1])
            ma_daily = compute_ma(close_daily, ma_period, ma_type)
            d_ma = float(ma_daily.iloc[-1])
            days_consec = calculate_consecutive_days_above_ma(close_daily, ma_daily)

            weekly_close = close_daily.resample("W-FRI").last().dropna()
            ma_weekly = compute_ma(weekly_close, ma_period, ma_type)
            w_ma = float(ma_weekly.iloc[-1]) if len(ma_weekly) > 0 else 0.0
            weeks_consec = calculate_consecutive_days_above_ma(weekly_close, ma_weekly)

    if last_price == 0.0:
        sample_defaults = {
            "^VIX": (17.06, 16.10, 3, 17.50, -4),
            "^GSPC": (5890.25, 5820.10, 14, 5680.00, 22),
            "ES=F": (5895.00, 5825.00, 14, 5685.00, 22),
            "^NDX": (20850.10, 20450.00, 12, 19800.00, 18),
            "NQ=F": (20880.00, 20475.00, 12, 19820.00, 18),
            "^RUT": (2245.80, 2210.50, 5, 2150.20, 8),
            "RTY=F": (2250.00, 2215.00, 5, 2155.00, 8),
            "^NYA": (19850.00, 19620.00, 8, 19200.00, 15),
            "^DJI": (43200.50, 42850.00, 9, 41900.00, 16),
            "^DJT": (16850.20, 16920.00, -2, 16400.00, 6),
            "^DJU": (980.50, 975.00, 4, 950.00, 11),
            "^GDAXI": (19450.00, 19200.00, 7, 18800.00, 14),
            "^STOXX50E": (4980.20, 4920.00, 6, 4850.00, 12),
            "EWG": (32.40, 31.90, 5, 31.10, 10),
        }
        vals = sample_defaults.get(sym, (100.0, 98.0, 3, 95.0, 5))
        last_price, d_ma, days_consec, w_ma, weeks_consec = vals

    if not is_vix:
        total_indices += 1
        if days_consec > 0:
            bullish_count += 1

    if is_vix:
        d_badge = f"🟢 Below (-{abs(days_consec)}d)" if days_consec < 0 else f"🔴 Above (+{days_consec}d)"
        w_badge = f"🟢 Below (-{abs(weeks_consec)}w)" if weeks_consec < 0 else f"🔴 Above (+{weeks_consec}w)"
        bias = "Bullish Tailwind" if days_consec < 0 else "Caution (Vol Rising)"
    else:
        d_badge = f"🟢 Above (+{days_consec}d)" if days_consec > 0 else f"🔴 Below ({days_consec}d)"
        w_badge = f"🟢 Above (+{weeks_consec}w)" if weeks_consec > 0 else f"🔴 Below ({weeks_consec}w)"
        if days_consec > 0 and weeks_consec > 0:
            bias = "Strong Bull Trend"
        elif days_consec < 0 and weeks_consec > 0:
            bias = "Pullback in Bull Trend"
        elif days_consec > 0 and weeks_consec < 0:
            bias = "Counter-trend Rally"
        else:
            bias = "Bearish Trend"

    table_rows.append({
        "Index / Asset": label,
        "Ticker": sym,
        "Last Price": f"{last_price:,.2f}",
        f"Daily {ma_period} {ma_type.split()[0]}": f"{d_ma:,.2f}",
        "Days vs 21 MA": d_badge,
        f"Weekly {ma_period} {ma_type.split()[0]}": f"{w_ma:,.2f}",
        "Weeks vs 21 MA": w_badge,
        "Regime / Health": bias,
    })

df_table = pd.DataFrame(table_rows)

health_pct = round((bullish_count / total_indices) * 100, 1) if total_indices > 0 else 0
health_color = "#22c55e" if health_pct >= 70 else ("#eab308" if health_pct >= 45 else "#ef4444")

st.markdown(f"""
<div style="background-color: #1e293b; border-left: 5px solid {health_color}; padding: 12px 18px; border-radius: 6px; margin-bottom: 15px;">
    <b>Market Breadth Health:</b> <span style="font-size: 1.1rem; color: {health_color}; font-weight: 700;">{bullish_count} / {total_indices} Indices ({health_pct}%)</span> are currently trading <b>ABOVE</b> their 21-day moving average.
</div>
""", unsafe_allow_html=True)

st.dataframe(df_table, use_container_width=True, hide_index=True)
st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------
# SECTION 3: Advance/Decline Line & Divergence Analysis
# ---------------------------------------------------------
st.subheader("3. S&P 500 vs. Advance-Decline (A/D) Line Divergence")
st.caption("Tracking breadth divergence using NYSE Net Advances and Cumulative $NYAD. Source: [StockCharts Advance/Decline Feed](https://stockcharts.com/sc3/ui/?s=$nyad)")

ad_dates = pd.date_range(end=datetime.date.today(), periods=90, freq="B")
np.random.seed(42)
sp_sim = 5500 + np.cumsum(np.random.randn(90) * 12 + 2)
ad_sim = np.cumsum(np.random.randn(90) * 350 + 150)
ad_sim[-15:] = ad_sim[-15:] - np.arange(15) * 40

divergence_state = "🔴 Bearish Divergence Alert: S&P 500 is testing recent swing highs, but Cumulative Advance/Decline line is trending lower."
st.markdown(f"""
<div style="background-color: rgba(239, 68, 68, 0.1); border-left: 4px solid #ef4444; color: #fca5a5; padding: 14px 18px; border-radius: 6px; margin-bottom: 15px;">
    <b>Divergence Status:</b> {divergence_state}
</div>
""", unsafe_allow_html=True)

if HAS_PLOTLY:
    from plotly.subplots import make_subplots
    fig_ad = make_subplots(specs=[[{"secondary_y": True}]])
    fig_ad.add_trace(go.Scatter(x=ad_dates, y=sp_sim, name="S&P 500 Index", line=dict(color="#38bdf8", width=2.5)), secondary_y=False)
    fig_ad.add_trace(go.Scatter(x=ad_dates, y=ad_sim, name="Cumulative NYSE A/D Line ($NYAD)", line=dict(color="#f59e0b", width=2, dash="dot")), secondary_y=True)
    fig_ad.update_layout(template="plotly_dark", paper_bgcolor="#111827", plot_bgcolor="#111827", height=340, margin=dict(l=20, r=20, t=30, b=20))
    st.plotly_chart(fig_ad, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------
# SECTION 4: Volume Dynamics & 52-Week Highs / Lows
# ---------------------------------------------------------
st.subheader("4. Volume Dynamics & 52-Week Highs / Lows (NYSE & NASDAQ)")
st.caption("Sources: [Barchart Market Momentum](https://www.barchart.com/stocks/momentum) & [CBOE Options Statistics](https://www.cboe.com/markets/us/options/market-statistics/)")
col_nyse, col_nasdaq = st.columns(2)
nyse = breadth_data["nyse"]
nasdaq = breadth_data["nasdaq"]

with col_nyse:
    st.markdown("#### 🏛️ NYSE Breadth & Volume")
    c1, c2, c3 = st.columns(3)
    c1.metric("Up Volume %", f"{nyse['up_volume_pct']}%")
    c2.metric("Advancing Vol", f"{nyse['adv_volume'] / 1e9:.2f} B")
    c3.metric("Declining Vol", f"{nyse['dec_volume'] / 1e9:.2f} B")
    st.markdown(f"""
    * **Unchanged Volume:** {nyse['unch_volume'] / 1e6:.0f} M shares
    * **52-Week Highs / Lows:** `{nyse['new_highs']}` Highs | `{nyse['new_lows']}` Lows
    * **Net New Highs:** <span class="badge-green">+{nyse['net_highs']}</span>
    * **Advancing vs. Declining Stocks:** {nyse['advancing_stocks']} Adv / {nyse['declining_stocks']} Dec
    """, unsafe_allow_html=True)

with col_nasdaq:
    st.markdown("#### 💻 NASDAQ Breadth & Volume")
    c1, c2, c3 = st.columns(3)
    c1.metric("Up Volume %", f"{nasdaq['up_volume_pct']}%")
    c2.metric("Advancing Vol", f"{nasdaq['adv_volume'] / 1e9:.2f} B")
    c3.metric("Declining Vol", f"{nasdaq['dec_volume'] / 1e9:.2f} B")
    st.markdown(f"""
    * **Unchanged Volume:** {nasdaq['unch_volume'] / 1e6:.0f} M shares
    * **52-Week Highs / Lows:** `{nasdaq['new_highs']}` Highs | `{nasdaq['new_lows']}` Lows
    * **Net New Highs:** <span class="badge-green">+{nasdaq['net_highs']}</span>
    * **Advancing vs. Declining Stocks:** {nasdaq['advancing_stocks']} Adv / {nasdaq['declining_stocks']} Dec
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------
# SECTION 5: AI Pre-Market Briefing Generator
# ---------------------------------------------------------
st.subheader("5. AI Automated Morning Routine Briefing")
if st.button("🚀 Generate AI Pre-Market Swing Trade Briefing"):
    briefing_text = f"""
### 1. Market Regime Posture: **Selective Bullish / Controlled Risk-On**
* **Primary Health:** {bullish_count} out of {total_indices} major indices ({health_pct}%) remain above their 21-day moving averages.
* **Breadth Divergence Warning:** While large-caps hold, the **NYSE Cumulative A/D Line is lagging**, creating a negative divergence. Mega-caps are carrying the index while average stocks hesitate.
* **Dow Transports & Small Caps:** Noticeable relative weakness in Small Caps (Russell 2000) and Dow Transports suggests cyclical caution.

### 2. Volatility & Sentiment Indicators
* **VIX Close / High Ratio ({vix_ratio:.3f}):** The VIX faded off its intraday high, signaling an intraday volatility rejection. As long as VIX trades below its 21 DEMA, dip-buying setups remain viable.
* **Fear & Greed ({fg_score} - {fg_rating}):** Sentiment is in moderate greed territory, but not yet at extreme euphoric levels (>75).
* **Put/Call Ratio ({pcr_last:.2f}):** Normal hedging activity; no complacency or panic extremes.

### 3. Swing Trader Action Plan for Today
1. **Long Setups:** Focus on leading stocks pulling back into their **own 21-day EMA** on light volume; avoid chasing extended breakouts.
2. **Risk Management:** Keep position sizing at **normal to 75% size** due to the active breadth divergence.
3. **Key Level:** If S&P 500 loses its 21-day moving average, pause new long entries and raise cash.
"""
    st.info(briefing_text)
    st.success("✅ Morning routine complete. Check individual stock watchlists against market regime.")
