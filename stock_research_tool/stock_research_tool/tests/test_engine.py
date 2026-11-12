import os
import sys
import unittest
import pandas as pd
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine import build_annual, snapshot, dcf, fmt_pct, growth_cagr, screen_status

class TestFinancialEngine(unittest.TestCase):
    def setUp(self):
        dates = [pd.Timestamp('2025-12-31'), pd.Timestamp('2024-12-31'), pd.Timestamp('2023-12-31'), pd.Timestamp('2022-12-31')]
        self.income = pd.DataFrame({
            dates[0]: [190, 35, 28, 40, 5, 34, 12],
            dates[1]: [155, 25, 20, 30, 4, 25, 12.5],
            dates[2]: [125, 19, 16, 22, 3, 20, 13],
            dates[3]: [100, 14, 11, 17, 2, 15, 13.5],
        }, index=['Total Revenue', 'Operating Income', 'Net Income', 'EBITDA', 'Tax Provision', 'Pretax Income', 'Diluted Average Shares'])
        self.balance = pd.DataFrame({
            dates[0]: [40, 8, 100], dates[1]: [43, 6, 90], dates[2]: [45, 5, 82], dates[3]: [45, 4, 77]
        }, index=['Total Debt', 'Cash And Cash Equivalents', 'Stockholders Equity'])
        self.cash = pd.DataFrame({
            dates[0]: [30, -8], dates[1]: [24, -7], dates[2]: [20, -6], dates[3]: [16, -5]
        }, index=['Operating Cash Flow', 'Capital Expenditure'])

    def test_financial_computations(self):
        df = build_annual(self.income, self.balance, self.cash)
        self.assertEqual(len(df), 4)
        last = df.iloc[-1]
        self.assertEqual(last['free_cash_flow'], 22)
        self.assertEqual(last['net_debt'], 32)
        self.assertAlmostEqual(last['operating_margin'], 35/190)
        self.assertAlmostEqual(last['revenue_yoy'], 190/155 - 1)
        self.assertAlmostEqual(last['shares_yoy'], 12/12.5-1)
        g, periods = growth_cagr(df)
        self.assertEqual(periods, 3)
        self.assertAlmostEqual(g, (1.9)**(1/3)-1)

    def test_snapshot_and_currency_mismatch(self):
        df = build_annual(self.income, self.balance, self.cash)
        info = {'symbol':'TEST', 'currentPrice':20, 'marketCap':1000, 'enterpriseValue':1032,
                'sharesOutstanding':50, 'forwardPE':20, 'currency':'USD', 'financialCurrency':'USD'}
        s = snapshot(info, df)
        self.assertAlmostEqual(s['fcf_yield'], 0.022)
        self.assertAlmostEqual(s['ev_ebit'], 1032/35)
        info['financialCurrency'] = 'EUR'
        s2 = snapshot(info, df)
        self.assertIsNone(s2['fcf_yield'])
        self.assertIsNone(s2['ev_ebit'])

    def test_dcf_and_missing_input(self):
        self.assertIsNone(dcf(None, 1, 1, .1, .05, .1, .03))
        self.assertIsNone(dcf(10, 1, 1, .1, .05, .03, .03))
        fair = dcf(10, 2, 20, .10, .05, .11, .03)
        self.assertTrue(fair['fair_price'] > 0)
        self.assertTrue(0 < fair['terminal_share'] < 1)

    def test_no_silent_zeros(self):
        df = build_annual(self.income, self.balance, pd.DataFrame())
        self.assertTrue(pd.isna(df.iloc[-1]['free_cash_flow']))
        self.assertEqual(fmt_pct(None), 'N/A')
        self.assertIn('No data', screen_status(snapshot({}, df))['Result'].values)

if __name__ == '__main__': unittest.main()
