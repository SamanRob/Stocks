# Stock Research Lab

An interactive **personal stock research dashboard** that retrieves publicly available company figures, estimates fundamental metrics, compares peers, checks possible ETF overlap and models valuation scenarios.

## Quick start (your computer)

Requires Python 3.10+.

```bash
pip install -r requirements.txt
streamlit run app.py
```

Streamlit opens a local browser tab. Type a ticker (e.g. `MSFT`, `MELI`, `ASML.AS`, `SU.PA`, `7203.T`) and press **Analyze stock**. Refresh the app if the upstream provider is temporarily unavailable.

## Put it online (free Streamlit Community Cloud)

1. Create a GitHub repository and upload **all the files** in this folder, keeping `app.py`, `engine.py` and `requirements.txt` in the root and `.streamlit/config.toml` in its subfolder.
2. Visit <https://share.streamlit.io>, sign in using GitHub, then choose **Create app**.
3. Select your repository, branch, and `app.py` as the entrypoint and select **Deploy**.
4. Open the resulting `*.streamlit.app` address in a browser.

**Note:** This builds a working app, but it is not deployed or hosted by ChatGPT. The free Yahoo Finance source is *unofficial* and can be blocked, throttled, delayed or change without warning; a production-grade/public commercial service should use a properly licensed data API and respect provider terms.

## What's included

- Stock lookup by Yahoo Finance ticker, with exchange suffixes for many non-US shares.
- Market capitalization, FY revenue growth and multi-year CAGR, operating margin, free cash flow, ROIC estimate, debt/EBITDA, share dilution.
- Forward/trailing P/E, EV/EBIT, EV/EBITDA, P/S, FCF yield, PEG (when provided).
- Price chart, annual financial trends and exportable raw data.
- 10-year user-adjustable free cash flow DCF with bear/base/bull scenarios and required margin of safety.
- Peer comparison for up to 4 companies including the target.
- ETF top-holdings overlap **lower-bound** estimator using the ETF ticker and its whole-portfolio weight.
- Downloadable one-page research memo and metrics CSV.

## Important financial limitations

- The app labels ratios using **latest available full-year** statements; provider-supplied valuation metrics may use different (often forward or trailing) periods. These must not be treated as perfectly like-for-like.
- **No FX conversion.** When the share's quoted currency is different from the financial-statement currency, the app deliberately leaves EV/EBIT and FCF yield unavailable and disables DCF. Look up the issuer's local listing instead (e.g. `ASML.AS` rather than the US ADR).
- **ROIC is an approximation**: EBIT × (1 – effective tax rate, default 25% if missing) / approximate average (interest-bearing debt + equity – cash). It does not adjust for every accounting item. Compare with the issuer's own disclosed ROIC where available.
- Yearly diluted-average shares are not always an exact proxy for current shares or dilution. The DCF defaults to current reported shares outstanding when available.
- Missing rows remain missing; the app does not quietly set absent FCF, EBITDA, cash or debt to zero. The data provider can report incomplete statements.
- **DCF is a deliberately simplified scenario** and assumes annual FCF grows at chosen rates. It does not forecast revenues, capital spending, tax policy or share dilution separately. It is particularly unsuitable with volatile or negative base-year cash flow.
- **ETFs:** Only holdings returned among the provider's **top holdings** are inspected. The method uses exact ticker matches and can miss local shares, ADRs and smaller holdings. Never assume a non-match means no overlap. Check actual issuer holdings.
- Banks, insurers, REITs, commodity firms and young unprofitable companies need different analysis. Generic metrics like EV/EBIT and FCF yield can be misleading.
- No automated investment recommendation is made. All stock ideas need original financial filings, valuation analysis and risk assessment.
- Usage of Yahoo Finance/yfinance is subject to upstream terms and permissions; the library itself is not an official Yahoo API.

## Useful primary sources

- US companies: <https://www.sec.gov/edgar/search/>
- Company investor relations / annual reports (most accurate)
- yfinance API documentation: <https://ranaroussi.github.io/yfinance/>
- Streamlit deployment documentation: <https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy>

## Test the financial calculations

```bash
python -m unittest discover -s tests -v
```

Tests use small synthetic financial statements; they do not connect to Yahoo Finance. Live data retrieval requires the app to run with an internet connection.
