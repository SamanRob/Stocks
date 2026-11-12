"""Stock Research Lab — interactive investment research, not trading advice."""
from __future__ import annotations

from datetime import datetime, timezone
import io
import re
import pandas as pd
import streamlit as st
import yfinance as yf
from engine import build_annual, dcf, fmt_multiple, fmt_num, fmt_pct, number, screen_status, snapshot, value_latest

st.set_page_config(page_title="Stock Research Lab", page_icon="📊", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
.block-container {padding-top:1.6rem; padding-bottom:3rem; max-width:1300px}
[data-testid="stMetric"] {border:1px solid rgba(140,140,140,0.19); border-radius:14px; padding:13px 16px}
[data-testid="stMetricLabel"] p {font-size: .87rem}
[data-testid="stMetricValue"] {font-weight:650}
h1,h2,h3 {letter-spacing:-.035em}
.smallnote {color: #888; font-size: .88rem}
</style>
""", unsafe_allow_html=True)


def safe_property(ticker, property_name):
    try:
        return getattr(ticker, property_name)
    except Exception:
        return pd.DataFrame() if property_name != "info" else {}


@st.cache_data(ttl=1800, show_spinner=False)
def load_stock(ticker: str, include_history: bool = True):
    t = yf.Ticker(ticker)
    info = safe_property(t, "info") or {}
    if not isinstance(info, dict):
        info = {}
    info["symbol"] = info.get("symbol") or ticker
    # Some endpoints move between versions of yfinance. Fall back safely.
    if not info.get("currentPrice") and not info.get("regularMarketPrice"):
        try:
            fi = t.fast_info
            info["currentPrice"] = fi.last_price
            info["marketCap"] = info.get("marketCap") or fi.market_cap
            info["currency"] = info.get("currency") or fi.currency
            info["sharesOutstanding"] = info.get("sharesOutstanding") or fi.shares
        except Exception:
            pass
    income = safe_property(t, "income_stmt")
    balance = safe_property(t, "balance_sheet")
    cashflow = safe_property(t, "cashflow")
    for table in (income, balance, cashflow):
        if not isinstance(table, pd.DataFrame):
            raise ValueError("The financial data provider returned an unexpected table format.")
    history = pd.DataFrame()
    if include_history:
        try:
            history = t.history(period="1y", auto_adjust=True)
        except Exception:
            pass
    if not info.get("longName") and not info.get("shortName") and all(t.empty for t in (income, balance, cashflow)) and history.empty:
        raise ValueError(f"No reliable data was returned for {ticker}. Verify the Yahoo Finance ticker including its exchange suffix.")
    return info, income, balance, cashflow, history, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def parse_ticker(raw):
    s = raw.strip().upper()
    return s if re.fullmatch(r"[A-Z0-9^.=\-]{1,25}", s) else None


def show_metric(col, title, val, help=None):
    col.metric(title, val, help=help)


def make_markdown(ticker, company, metrics, notes, timestamp):
    lines = [f"# {company} ({ticker}) — Investment research memo", f"Data retrieved: {timestamp}",
             "", "## Metrics (latest available fiscal-year figures unless indicated)",
             f"- Share price: {fmt_num(metrics['price'], metrics['currency']+' ')}",
             f"- Market capitalization: {fmt_num(metrics['market_cap'], metrics['currency']+' ')}",
             f"- Revenue growth (last FY): {fmt_pct(metrics['revenue_growth_yoy'])}",
             f"- Operating margin: {fmt_pct(metrics['operating_margin'])}",
             f"- Return on invested capital (approx.): {fmt_pct(metrics['roic_est'])}",
             f"- Free cash flow (FY): {fmt_num(metrics['fcf'], metrics['financial_currency']+' ')}",
             f"- Forward P/E: {fmt_multiple(metrics['forward_pe'])}",
             f"- EV/EBIT (FY): {fmt_multiple(metrics['ev_ebit'])}",
             f"- FCF yield (FY): {fmt_pct(metrics['fcf_yield'])}",
             f"- PEG (provider): {fmt_multiple(metrics['peg'])}",
             "", "## Investment thesis", notes["thesis"], "", "## Why the market may be wrong", notes["variant"],
             "", "## Top risks", notes["risks"], "", "## What would invalidate my thesis?", notes["invalidation"],
             "", "## Valuation / target buying price", notes["price"],
             "", "## Important caveats",
             "Calculated metrics use available annual statements, not necessarily TTM."
             "Currency mismatch suppresses currency-dependent valuation ratios."
             " Data may be stale, incomplete, delayed, or wrong; verify with filings."
             " This memo is research material, not a buy recommendation."]
    return "\n".join(lines)


with st.sidebar:
    st.title("📊 Stock Research Lab")
    st.caption("Research first. Price second. Decision last.")
    ticker_input = st.text_input("Stock ticker", value="MSFT", help="Examples: MSFT, MELI, ASML.AS, SU.PA, 7203.T, BRK-B")
    lookup = st.button("Analyze stock", type="primary", use_container_width=True)
    st.caption("Use the ticker as shown on Yahoo Finance, including the exchange suffix when needed.")
    st.divider()
    st.subheader("What's included")
    st.markdown("✅ Fundamental metrics & trends\n\n✅ Valuation ratios\n\n✅ Fair-value scenarios\n\n✅ Peer comparison\n\n✅ ETF overlap (top holdings)\n\n✅ Downloadable research memo")
    st.divider()
    st.caption("Data: Yahoo Finance via the unofficial yfinance library. For personal research only. A free feed may be delayed or temporarily unavailable.")

if "active_ticker" not in st.session_state:
    st.session_state.active_ticker = "MSFT"
if lookup:
    parsed = parse_ticker(ticker_input)
    if parsed:
        st.session_state.active_ticker = parsed
    else:
        st.sidebar.error("Enter a valid ticker, such as MSFT or ASML.AS.")
symbol = st.session_state.active_ticker

with st.spinner(f"Retrieving market data and financial statements for {symbol}..."):
    try:
        info, income, balance, cashflow, history, fetched = load_stock(symbol)
    except Exception as exc:
        st.error(f"Unable to load {symbol}: {exc}")
        st.info("Try an exchange-qualified ticker (e.g. ASML.AS or SU.PA). The free data feed can also be rate-limited or temporarily unavailable.")
        st.stop()

annual = build_annual(income, balance, cashflow)
metrics = snapshot(info, annual)
name = metrics["name"]
ccy, fin_ccy = metrics["currency"], metrics["financial_currency"]

st.title(f"{name} · {symbol}")
st.caption(f"{metrics['sector']}  /  {metrics['industry']}  ·  Quote currency: {ccy}  ·  Financial statements: {fin_ccy}  ·  Retrieved {fetched}")
if not metrics["currencies_match"]:
    st.warning(f"Currency mismatch: share-price/market-cap figures are in {ccy}, financial statements are in {fin_ccy}. EV/EBIT, FCF yield, and DCF are disabled rather than mixing currencies.")
if metrics["quote_type"] and metrics["quote_type"] not in ("EQUITY",):
    st.warning("This ticker does not appear to be a common stock. Many valuation measures are inappropriate for ETFs/funds.")
if metrics["sector"] == "Financial Services":
    st.warning("Banks, insurers, and lenders need different valuation frameworks. Free cash flow, EV/EBIT and net debt/EBITDA are often misleading for financial institutions.")
if annual.empty:
    st.warning("Annual financial statements are unavailable for this ticker; many fundamental metrics cannot be computed.")

m1, m2, m3, m4 = st.columns(4)
show_metric(m1, "Share price", fmt_num(metrics["price"], ccy + " ", 2), "Latest available quote (not guaranteed real time)")
show_metric(m2, "Market cap", fmt_num(metrics["market_cap"], ccy + " "))
show_metric(m3, "Revenue growth · FY", fmt_pct(metrics["revenue_growth_yoy"]), "Last two available fiscal years")
show_metric(m4, "Operating margin · FY", fmt_pct(metrics["operating_margin"]))

overview, financials_tab, valuation_tab, peers_tab, overlap_tab, memo_tab = st.tabs([
    "Overview", "Financial history", "Valuation", "Peers", "ETF overlap", "Research memo"
])

with overview:
    st.subheader("Growth and quality")
    a, b, c, d = st.columns(4)
    n = metrics["revenue_cagr_years"]
    a.metric(f"Revenue CAGR · {n or 'N/A'} yr", fmt_pct(metrics["revenue_cagr"]))
    b.metric("FCF · FY", fmt_num(metrics["fcf"], fin_ccy + " "))
    c.metric("ROIC · estimated", fmt_pct(metrics["roic_est"]), help="EBIT × (1 − effective tax rate) / average (debt + equity − cash). Approximate, non-standardized.")
    d.metric("Share count change · FY", fmt_pct(metrics["shares_yoy"]), help="Year-on-year change in diluted average share count when available; can be affected by share-based compensation and buybacks.")
    st.subheader("Valuation snapshot")
    a,b,c,d = st.columns(4)
    a.metric("Forward P/E", fmt_multiple(metrics["forward_pe"]))
    b.metric("EV / EBIT · FY", fmt_multiple(metrics["ev_ebit"]))
    c.metric("FCF yield · FY", fmt_pct(metrics["fcf_yield"]))
    d.metric("PEG · provider", fmt_multiple(metrics["peg"]))
    st.caption("Forward P/E and PEG depend on market/provider estimates; EV/EBIT and FCF yield use the latest available FY financials. They are not a single consistent reporting period.")
    st.subheader("Research-screen checks")
    st.dataframe(screen_status(metrics), hide_index=True, use_container_width=True)
    st.caption("Flags are exploratory filters, never automatic buy or sell recommendations. Net debt/EBITDA requires both EBITDA and complete debt/cash figures.")
    if not history.empty and "Close" in history.columns:
        st.subheader("Adjusted 1-year share-price history")
        st.line_chart(history[["Close"]].rename(columns={"Close": f"Price ({ccy})"}))
    if metrics["description"]:
        with st.expander("Business overview (data-provider description)"):
            st.write(metrics["description"])

with financials_tab:
    st.subheader("Reported annual financials")
    if annual.empty:
        st.info("No annual statement history available.")
    else:
        charts = annual.copy().set_index("Fiscal year")
        top1, top2 = st.columns(2)
        with top1:
            st.markdown("**Revenue and operating profit**")
            cols = {"revenue": "Revenue", "operating_income": "Operating income"}
            st.bar_chart(charts[list(cols)].rename(columns=cols) / 1e9)
            st.caption(f"{fin_ccy} billions · fiscal years")
        with top2:
            st.markdown("**Free cash flow**")
            st.bar_chart(charts[["free_cash_flow"]].rename(columns={"free_cash_flow": "Free cash flow"}) / 1e9)
            st.caption(f"{fin_ccy} billions · fiscal years")
        display_columns = {
            "Fiscal year": "FY", "revenue": "Revenue", "revenue_yoy": "Revenue YoY",
            "operating_income": "Operating income", "operating_margin": "Operating margin",
            "free_cash_flow": "Free cash flow", "fcf_margin": "FCF margin", "net_income": "Net income",
            "total_debt": "Total debt", "cash": "Cash", "net_debt": "Net debt",
            "shares": "Diluted avg shares", "shares_yoy": "Shares YoY", "roic_est": "ROIC est.",
        }
        display = annual[[c for c in display_columns if c in annual]].rename(columns=display_columns).set_index("FY")
        styler = display.style.format({
            k: (lambda x: f"{x*100:,.1f}%" if pd.notna(x) else "—") for k in
            ("Revenue YoY", "Operating margin", "FCF margin", "Shares YoY", "ROIC est.") if k in display.columns
        }, na_rep="—")
        for col in display.columns:
            if col not in ("Revenue YoY", "Operating margin", "FCF margin", "Shares YoY", "ROIC est."):
                styler = styler.format({col: lambda x: f"{x:,.0f}" if pd.notna(x) else "—"}, na_rep="—")
        st.dataframe(styler, use_container_width=True)
        st.download_button("Download full financials CSV", annual.to_csv(index=False).encode(), file_name=f"{symbol}_annual_financials.csv", mime="text/csv")
        st.caption("Fiscal years may have different year-end dates. Statement availability is usually limited to the latest ~4 reporting years. Missing data is shown as unavailable, not zero.")

with valuation_tab:
    st.subheader("Valuation ratios")
    fields = [
        ("Forward P/E", fmt_multiple(metrics["forward_pe"]), "Current share price divided by forecast earnings per share"),
        ("Trailing P/E", fmt_multiple(metrics["trailing_pe"]), "Price divided by trailing earnings"),
        ("EV / EBIT · FY", fmt_multiple(metrics["ev_ebit"]), "Enterprise value / latest available full-year operating income"),
        ("EV / EBITDA · provider", fmt_multiple(metrics["ev_ebitda"]), "Enterprise value / EBITDA as reported by data provider"),
        ("Price / sales · provider", fmt_multiple(metrics["price_sales"]), "Price-to-sales ratio as provided by Yahoo"),
        ("FCF yield · FY", fmt_pct(metrics["fcf_yield"]), "Latest full-year FCF / current market cap"),
        ("PEG · provider", fmt_multiple(metrics["peg"]), "P/E relative to growth estimate; can be missing or unreliable"),
        ("Net debt / EBITDA · FY", fmt_multiple(metrics["net_debt_ebitda"]), "FY debt minus FY cash, divided by FY EBITDA"),
    ]
    st.dataframe(pd.DataFrame(fields, columns=["Metric", "Value", "Meaning"]), hide_index=True, use_container_width=True)
    st.divider()
    st.subheader("10-year discounted cash flow scenario")
    st.info("This is a transparent sensitivity model, **not** an automatic fair-value prediction. It is especially unreliable for unusually low/negative FCF or highly cyclical businesses.")
    most_recent_fcf = value_latest(annual, "free_cash_flow")
    latest_net_debt = value_latest(annual, "net_debt")
    shares = metrics["shares_outstanding"] or value_latest(annual, "shares")
    can_dcf = (metrics["currencies_match"] and most_recent_fcf is not None and most_recent_fcf > 0
               and latest_net_debt is not None and shares is not None and shares > 0 and metrics["price"])
    if not can_dcf:
        st.warning("DCF unavailable: it needs positive latest-year FCF, total debt, cash, shares outstanding, quote price, and matching currencies. Do not fill missing amounts with zero.")
    else:
        st.caption(f"Starting full-year FCF: {fmt_num(most_recent_fcf, fin_ccy+' ')} · Net debt: {fmt_num(latest_net_debt, fin_ccy+' ')} · Shares: {fmt_num(shares)}")
        x,y = st.columns(2)
        with x:
            growth_a = st.slider("Annual FCF growth · years 1–5", min_value=-20, max_value=45, value=12, step=1, format="%d%%") / 100
            growth_b = st.slider("Annual FCF growth · years 6–10", min_value=-10, max_value=25, value=7, step=1, format="%d%%") / 100
        with y:
            discount_rate = st.slider("Required return / discount rate", 6, 20, 10, step=1, format="%d%%") / 100
            terminal_rate = st.slider("Long-term perpetual FCF growth", 0, 5, 3, step=1, format="%d%%") / 100
        margin_of_safety = st.slider("Margin of safety required before buying", 0, 50, 25, step=5, format="%d%%") / 100
        cases = [
            ("Bear", max(-0.25, growth_a-0.06), max(-0.1, growth_b-0.04), min(.25, discount_rate+.02), max(0, terminal_rate-.01)),
            ("Base", growth_a, growth_b, discount_rate, terminal_rate),
            ("Bull", min(.7, growth_a+.06), min(.5, growth_b+.04), max(.05,discount_rate-.01), min(.05,terminal_rate+.01)),
        ]
        rows = []
        for label, ga, gb, d, t in cases:
            res = dcf(most_recent_fcf, latest_net_debt, shares, ga, gb, d, t)
            if res:
                fair = res["fair_price"]
                rows.append({"Case": label, "FCF growth Y1–5": fmt_pct(ga), "FCF growth Y6–10": fmt_pct(gb),
                             "Discount": fmt_pct(d), "Terminal": fmt_pct(t),
                             "Estimated fair price": f"{ccy} {fair:,.2f}",
                             "Upside/downside": fmt_pct(fair/metrics["price"] -1),
                             "Price with safety margin": f"{ccy} {max(0,fair*(1-margin_of_safety)):,.2f}",
                             "Terminal share": fmt_pct(res["terminal_share"])})
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        st.caption("Model: grow the latest available annual FCF for 10 years; discount FCF and a perpetuity terminal value; subtract net debt; divide by shares. No dilution forecast, changing capital structure, or detailed operating model. Small assumption changes can dramatically alter estimates.")

with peers_tab:
    st.subheader("Compare competing companies")
    peer_input = st.text_input("Peer tickers (up to 3)", "GOOGL, AMZN, META", help="Use comma-separated Yahoo Finance tickers")
    run_peers = st.button("Compare peers")
    if run_peers:
        peer_symbols = [parse_ticker(x) for x in peer_input.split(",") if x.strip()]
        peer_symbols = list(dict.fromkeys([symbol] + [x for x in peer_symbols if x and x != symbol]))[:4]
        peers = []
        failures = []
        with st.spinner("Loading peer fundamentals..."):
            for peer in peer_symbols:
                try:
                    p_info, p_income, p_balance, p_cf, _, _ = load_stock(peer, include_history=False)
                    p_metrics = snapshot(p_info, build_annual(p_income, p_balance, p_cf))
                    peers.append({"Ticker": peer, "Sector": p_metrics["sector"],
                                  "Mkt cap": fmt_num(p_metrics["market_cap"], p_metrics["currency"]+" "),
                                  "Revenue YoY · FY": fmt_pct(p_metrics["revenue_growth_yoy"]),
                                  "Operating margin · FY": fmt_pct(p_metrics["operating_margin"]),
                                  "ROIC est.": fmt_pct(p_metrics["roic_est"]),
                                  "Forward P/E": fmt_multiple(p_metrics["forward_pe"]),
                                  "EV/EBIT · FY": fmt_multiple(p_metrics["ev_ebit"]),
                                  "FCF yield · FY": fmt_pct(p_metrics["fcf_yield"])})
                except Exception as exc:
                    failures.append(f"{peer}: {exc}")
        if peers:
            st.dataframe(pd.DataFrame(peers), hide_index=True, use_container_width=True)
            st.caption("Comparison is not currency-neutral for market cap; valuation multiples should only be compared between firms with similar accounting, maturity, and business models.")
        if failures:
            st.warning("Some tickers couldn't be loaded: " + "; ".join(failures))

with overlap_tab:
    st.subheader("ETF overlap check")
    st.write("Enter your ETF ticker and its weight in your **whole portfolio**. The tool looks for the analyzed stock in each fund's publicly available **top holdings**.")
    st.caption("Example: if 45% of your entire portfolio is in VWCE.DE, enter VWCE.DE:45. ETF weights should add up to around 90% if 90% of your portfolio is in ETFs.")
    etf_text = st.text_area("One ETF per line, TICKER:WEIGHT", value="SPY:45\nQQQ:25\nVEA:20", height=110)
    if st.button("Check overlap"):
        results = []
        accounted = 0.0
        issues = []
        for raw in etf_text.splitlines()[:12]:
            if not raw.strip():
                continue
            try:
                candidate, weight_string = raw.split(":", 1)
                etf = parse_ticker(candidate)
                weight = float(weight_string.strip().replace("%", ""))
                if not etf or not (0 <= weight <= 100):
                    raise ValueError("Invalid ticker or weight")
                accounted += weight
                t = yf.Ticker(etf)
                holdings = t.funds_data.top_holdings
                if holdings is None or holdings.empty or "Holding Percent" not in holdings:
                    issues.append(f"{etf}: ETF top holdings not available")
                    continue
                hits = holdings.loc[[idx for idx in holdings.index if str(idx).upper() == symbol.upper()]]
                holding_weight = float(hits["Holding Percent"].iloc[0]) if not hits.empty else 0.0
                if holding_weight > 1:
                    holding_weight /= 100
                results.append({"ETF": etf, "Portfolio weight": weight,
                                "Stock within ETF (%)": holding_weight*100 if not hits.empty else None,
                                "Known portfolio exposure (%)": weight*holding_weight if not hits.empty else None,
                                "Coverage": "Matched" if not hits.empty else "Not in reported top holdings"})
            except Exception as exc:
                issues.append(f"{raw}: {exc}")
        if results:
            table = pd.DataFrame(results)
            st.dataframe(table.style.format({"Portfolio weight":"{:.1f}%", "Stock within ETF (%)":"{:.2f}%", "Known portfolio exposure (%)":"{:.2f}%"}, na_rep="—"), use_container_width=True, hide_index=True)
            known = table["Known portfolio exposure (%)"].sum()
            st.metric("Known indirect exposure from matched top holdings", f"{known:.2f}% of total portfolio")
            st.caption("This is a LOWER BOUND over successfully matched top holdings, NOT the full ETF overlap. Missing from top holdings ≠ not owned. Different ticker listings/ADRs can also prevent matches.")
        if issues:
            st.warning("Incomplete: " + "; ".join(issues))
        if accounted > 100:
            st.warning("Your input ETF allocations exceed 100% of the whole portfolio.")
    st.caption("For an accurate calculation, cross-check each ETF's latest full holdings on the issuer's website and use consistent cross-listed company identifiers.")

with memo_tab:
    st.subheader("Your one-page investment thesis")
    st.write("Keep an explicit record of what you're expecting, what could go wrong, and what price would be attractive.")
    thesis = st.text_area("Why will this business grow profitably?", placeholder="Describe the products, customers, revenue drivers, and moat.")
    variant = st.text_area("What might the market be underestimating?", placeholder="Write a testable, differentiated thesis rather than 'AI is the future'.")
    risks = st.text_area("Top 3 risks", placeholder="Competition, regulation, margin pressure, valuation, concentration...")
    invalidation = st.text_area("What evidence would change your mind?", placeholder="E.g. two years of falling margins, churn above a threshold...")
    price = st.text_input("My valuation / maximum purchase price", placeholder="Currency, price, assumptions and margin of safety")
    notes = {"thesis": thesis, "variant": variant, "risks": risks, "invalidation": invalidation, "price": price}
    md = make_markdown(symbol, name, metrics, notes, fetched)
    st.download_button("Download investment memo (.md)", md.encode("utf-8"), file_name=f"{symbol}_research_memo.md", mime="text/markdown")
    st.download_button("Download valuation metrics (.csv)", pd.DataFrame([metrics]).to_csv(index=False).encode(), file_name=f"{symbol}_metrics.csv", mime="text/csv")

st.divider()
st.caption("For education and personal investment research. Not financial advice. Free Yahoo Finance data may be delayed, incomplete, rate-limited, or incorrect. Metrics are not all TTM, and data is not audited by this application. Always verify key values in issuer filings and check the data provider's permitted usage. Nothing in this tool is a buy/sell signal.")
