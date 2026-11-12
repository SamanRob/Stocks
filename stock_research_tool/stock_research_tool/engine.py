"""Pure computations for Stock Research Lab. No live requests are made here."""
from __future__ import annotations
import math
import re
from typing import Optional
import pandas as pd


def number(x):
    try:
        if x is None or pd.isna(x):
            return None
        n = float(x)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def ratio(numerator, denominator):
    a, b = number(numerator), number(denominator)
    return a / b if a is not None and b is not None and b != 0 else None


def fmt_num(x, unit="", decimals=1):
    n = number(x)
    if n is None:
        return "N/A"
    prefix = "−" if n < 0 else ""
    n = abs(n)
    for scale, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if n >= scale:
            return f"{prefix}{unit}{n / scale:,.{decimals}f}{suffix}"
    return f"{prefix}{unit}{n:,.{decimals}f}"


def fmt_pct(x, decimals=1):
    n = number(x)
    return f"{n*100:.{decimals}f}%" if n is not None else "N/A"


def fmt_multiple(x):
    n = number(x)
    return f"{n:,.1f}×" if n is not None and n > 0 else "N/A"


def normalize(s):
    return re.sub(r"[^a-z0-9]", "", str(s).casefold())


def get_statement_row(df, names):
    if df is None or df.empty:
        return pd.Series(dtype="float64")
    available = {normalize(idx): idx for idx in df.index}
    for candidate in names:
        if normalize(candidate) in available:
            row = df.loc[available[normalize(candidate)]]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            return pd.to_numeric(row, errors="coerce")
    return pd.Series(dtype="float64")


def get_by_year(series, year):
    for date, value in series.items():
        try:
            if pd.Timestamp(date).year == year:
                return number(value)
        except (TypeError, ValueError):
            pass
    return None


def statement_years(*statements):
    years = set()
    for statement in statements:
        if statement is not None and not statement.empty:
            for col in statement.columns:
                try:
                    years.add(pd.Timestamp(col).year)
                except (TypeError, ValueError):
                    continue
    return sorted(years)


def build_annual(income, balance, cash):
    """Collect fiscal-year values. Never substitute a missing field with zero."""
    specs = {
        "revenue": (income, ["Total Revenue", "Operating Revenue"]),
        "operating_income": (income, ["Operating Income", "Operating Income Or Loss"]),
        "net_income": (income, ["Net Income", "Net Income Common Stockholders"]),
        "ebitda": (income, ["EBITDA", "Normalized EBITDA"]),
        "pretax_income": (income, ["Pretax Income", "Income Before Tax"]),
        "tax_provision": (income, ["Tax Provision", "Income Tax Expense"]),
        "cash_from_ops": (cash, ["Operating Cash Flow", "Total Cash From Operating Activities", "Cash Flow From Continuing Operating Activities"]),
        "capex": (cash, ["Capital Expenditure", "Capital Expenditures", "Purchase Of PPE"]),
        "free_cash_flow": (cash, ["Free Cash Flow"]),
        "total_debt": (balance, ["Total Debt"]),
        "current_debt": (balance, ["Current Debt And Capital Lease Obligation", "Current Debt", "Current Portion Of Long Term Debt"]),
        "long_term_debt": (balance, ["Long Term Debt And Capital Lease Obligation", "Long Term Debt", "Long Term Debt Noncurrent"]),
        "cash": (balance, ["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents", "Cash And Short Term Investments"]),
        "equity": (balance, ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest", "Total Stockholder Equity"]),
        "shares": (income, ["Diluted Average Shares", "Basic Average Shares"]),
        "balance_shares": (balance, ["Ordinary Shares Number", "Share Issued", "Common Stock Shares Outstanding"]),
    }
    values = {key: get_statement_row(stmt, names) for key, (stmt, names) in specs.items()}
    records = []
    for year in statement_years(income, balance, cash):
        r = {"Fiscal year": year}
        for key, data in values.items():
            r[key] = get_by_year(data, year)
        if r["free_cash_flow"] is None and r["cash_from_ops"] is not None and r["capex"] is not None:
            r["free_cash_flow"] = r["cash_from_ops"] - abs(r["capex"])
        if r["total_debt"] is None:
            chunks = (r["current_debt"], r["long_term_debt"])
            if any(x is not None for x in chunks):
                r["total_debt"] = sum(x or 0 for x in chunks)
        if r["shares"] is None:
            r["shares"] = r["balance_shares"]
        if r["ebitda"] is None:
            r["ebitda"] = None  # EBIT is not EBITDA; no silent substitution.
        r["operating_margin"] = ratio(r["operating_income"], r["revenue"])
        r["fcf_margin"] = ratio(r["free_cash_flow"], r["revenue"])
        r["net_debt"] = (r["total_debt"] - r["cash"]) if r["total_debt"] is not None and r["cash"] is not None else None
        r["invested_capital"] = (r["total_debt"] + r["equity"] - r["cash"]) if all(r[k] is not None for k in ("total_debt", "equity", "cash")) else None
        tr = ratio(r["tax_provision"], r["pretax_income"])
        r["effective_tax_rate"] = min(0.4, max(0, tr)) if tr is not None and (r["pretax_income"] or 0) > 0 else None
        records.append(r)
    df = pd.DataFrame.from_records(records)
    if df.empty:
        return df
    df = df.sort_values("Fiscal year").drop_duplicates("Fiscal year", keep="last").reset_index(drop=True)
    df["revenue_yoy"] = df["revenue"].pct_change(fill_method=None) if "revenue" in df else None
    df["shares_yoy"] = df["shares"].pct_change(fill_method=None) if "shares" in df else None
    roics = []
    for i, row in df.iterrows():
        invested = number(row["invested_capital"])
        if i and number(df.iloc[i-1]["invested_capital"]) is not None and invested is not None:
            invested = (invested + number(df.iloc[i-1]["invested_capital"])) / 2
        tax = number(row["effective_tax_rate"])
        tax = 0.25 if tax is None else tax
        ebit = number(row["operating_income"])
        roics.append((ebit * (1-tax) / invested) if ebit is not None and invested is not None and invested > 0 else None)
    df["roic_est"] = roics
    return df


def value_latest(df, key):
    if df is None or df.empty or key not in df.columns:
        return None
    for _, row in df.iloc[::-1].iterrows():
        v = number(row.get(key))
        if v is not None:
            return v
    return None


def growth_cagr(df, key="revenue", max_periods=3):
    if df is None or df.empty or key not in df.columns:
        return (None, None)
    values = df[["Fiscal year", key]].dropna().sort_values("Fiscal year")
    if len(values) < 2:
        return (None, None)
    last = values.iloc[-1]
    early = values[values["Fiscal year"] >= last["Fiscal year"] - max_periods].iloc[0]
    span = int(last["Fiscal year"] - early["Fiscal year"])
    if span == 0 or early[key] <= 0 or last[key] <= 0:
        return (None, None)
    return ((last[key]/early[key]) ** (1/span)-1, span)


def snapshot(info: dict, annual: pd.DataFrame) -> dict:
    """Mix stock quote metadata with latest audited fiscal-year financials.

    Currency-sensitive cross-ratios are not produced if quote currency and
    financial statement currency differ. No FX conversion is attempted.
    """
    price = number(info.get("currentPrice")) or number(info.get("regularMarketPrice"))
    marketcap = number(info.get("marketCap"))
    shares = number(info.get("sharesOutstanding"))
    if marketcap is None and price is not None and shares is not None:
        marketcap = price * shares
    quote_currency = info.get("currency") or "?"
    financial_currency = info.get("financialCurrency") or quote_currency
    currencies_match = quote_currency == financial_currency
    sales = value_latest(annual, "revenue")
    ebit = value_latest(annual, "operating_income")
    fcf = value_latest(annual, "free_cash_flow")
    debt = value_latest(annual, "total_debt")
    cash = value_latest(annual, "cash")
    cap = value_latest(annual, "invested_capital")
    net_debt = value_latest(annual, "net_debt")  # Debt and cash must come from the same FY.
    ev = number(info.get("enterpriseValue"))
    if ev is None and marketcap is not None and net_debt is not None and currencies_match:
        ev = marketcap + net_debt
    rev_cagr, years = growth_cagr(annual)
    current_rev_yoy = value_latest(annual, "revenue_yoy")
    out = {
        "name": info.get("longName") or info.get("shortName") or info.get("symbol") or "Unknown company",
        "ticker": info.get("symbol") or "",
        "sector": info.get("sector") or "Unknown",
        "industry": info.get("industry") or "Unknown",
        "quote_type": info.get("quoteType"),
        "description": info.get("longBusinessSummary") or "",
        "currency": quote_currency,
        "financial_currency": financial_currency,
        "currencies_match": currencies_match,
        "price": price,
        "market_cap": marketcap,
        "shares_outstanding": shares,
        "revenue": sales,
        "revenue_growth_yoy": current_rev_yoy,
        "revenue_cagr": rev_cagr,
        "revenue_cagr_years": years,
        "operating_margin": value_latest(annual, "operating_margin"),
        "fcf": fcf,
        "fcf_margin": value_latest(annual, "fcf_margin"),
        "roic_est": value_latest(annual, "roic_est"),
        "shares_yoy": value_latest(annual, "shares_yoy"),
        "net_debt": net_debt,
        "net_debt_ebitda": ratio(net_debt, value_latest(annual, "ebitda")) if value_latest(annual, "ebitda") and value_latest(annual, "ebitda") > 0 else None,
        "forward_pe": number(info.get("forwardPE")),
        "trailing_pe": number(info.get("trailingPE")),
        "peg": number(info.get("trailingPegRatio")) or number(info.get("pegRatio")),
        "ev_ebitda": number(info.get("enterpriseToEbitda")),
        "price_sales": number(info.get("priceToSalesTrailing12Months")),
        "ev_ebit": ratio(ev, ebit) if currencies_match and ebit is not None and ebit > 0 else None,
        "fcf_yield": ratio(fcf, marketcap) if currencies_match else None,
        "fiscal_year": int(annual["Fiscal year"].max()) if not annual.empty else None,
    }
    return out


def dcf(fcf, net_debt, shares, growth_1_5, growth_6_10, discount, terminal_growth):
    """Simple 10-year equity valuation (current FCF -> growing future FCF)."""
    vals = [number(v) for v in (fcf, net_debt, shares, growth_1_5, growth_6_10, discount, terminal_growth)]
    if any(v is None for v in vals):
        return None
    fcf, net_debt, shares, growth_1_5, growth_6_10, discount, terminal_growth = vals
    if fcf <= 0 or shares <= 0 or not -0.7 < growth_1_5 < 1 or not -0.7 < growth_6_10 < 1 or terminal_growth >= discount or discount <= 0:
        return None
    pv = 0.0
    cash = fcf
    for year in range(1, 11):
        cash *= 1 + (growth_1_5 if year <= 5 else growth_6_10)
        pv += cash / (1 + discount)**year
    terminal = cash * (1+terminal_growth) / (discount-terminal_growth)
    enterprise_value = pv + terminal / (1+discount)**10
    equity_value = enterprise_value - net_debt
    return {
        "fair_price": max(0.0, equity_value / shares),  # Equity has a theoretical floor at zero.
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "terminal_share": (terminal / (1+discount)**10) / enterprise_value if enterprise_value else None,
    }


def screen_status(metrics):
    """Simple screening flags; not a buy/sell signal."""
    flags = []
    for name, key, predicate in [
        ("Revenue growth", "revenue_growth_yoy", lambda x: x >= .15),
        ("Operating margin", "operating_margin", lambda x: x >= .10),
        ("FCF positive", "fcf", lambda x: x > 0),
        ("ROIC (approx.)", "roic_est", lambda x: x >= .12),
        ("Net debt / EBITDA", "net_debt_ebitda", lambda x: x < 3.0),
    ]:
        v = number(metrics.get(key))
        flags.append({"Check": name, "Result": "Pass" if v is not None and predicate(v) else "Review" if v is not None else "No data", "Metric": fmt_num(v) if key == "fcf" else fmt_multiple(v) if key == "net_debt_ebitda" else fmt_pct(v)})
    return pd.DataFrame(flags)
