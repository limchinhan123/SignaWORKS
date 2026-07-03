#!/usr/bin/env python3
"""
Golden-value and property tests for pricing.py
Catches: off-by-one conventions, hand-rolled CDF errors, math regressions.
Run: pytest test_pricing.py -v
"""

import math
import sys
sys.path.insert(0, '/root/.hermes/skills/options-position-review/references')
from pricing import (
    bs_put, bs_put_greeks, calc_put_delta, _years, R, TRADING_DAYS, CALENDAR_DAYS,
    risk_matrix, iv_scenarios, breakeven_analysis, prob_otm,
    one_day_shocks, gamma_profile, expected_vs_actual, correlation_check,
)
from scipy.stats import norm
import numpy as np


# ═══════════════════════════════════════════════════════════
# Golden-value tests: known inputs → known outputs
# ═══════════════════════════════════════════════════════════

class TestGoldenValues:
    """Reference values validated against three independent BS implementations."""

    def test_bs_price_deep_otm(self):
        """Deep OTM put: WDC $450P, spot $537, 28 DTE, 106% IV"""
        S, K, dte, iv = 537.0, 450.0, 28, 1.06
        T = _years(dte)
        price = bs_put(S, K, T, iv)
        assert abs(price - 23.62) < 0.05, f"price={price}, expected 23.62"

    def test_bs_price_atm(self):
        """ATM put: spot=strike, 30 DTE, 20% IV. Approximation holds to ~0.25."""
        S, K, dte, iv = 100.0, 100.0, 30, 0.20
        T = _years(dte)
        price = bs_put(S, K, T, iv)
        expected = S * iv * math.sqrt(T) / math.sqrt(2 * math.pi)
        # ATM put ≈ spot * σ * √T / √(2π) (ignoring carry, accurate to ~0.25)
        assert abs(price - expected) < 0.25, f"price={price}, expected~{expected:.2f}"

    def test_bs_price_deep_itm(self):
        """
        Deep ITM European put: S=50, K=100, T=30/365, IV=30%.
        A European put cannot be exercised early, so minimum bound is
        PV(K) - S, not K - S (intrinsic). Verify price >= discounted bound.
        """
        S, K, dte, iv = 50.0, 100.0, 30, 0.30
        T = _years(dte)
        price = bs_put(S, K, T, iv)
        min_value = K * math.exp(-R * T) - S  # present-value floor
        assert price >= min_value, f"price={price} < min={min_value} (PV bound)"
        # Should be very close to min_value for deep ITM
        assert price - min_value < 0.50, f"price={price} far above min={min_value}"

    def test_greeks_otm_put(self):
        """WDC greeks: delta -0.22, gamma ~0.002, theta ~-1.19, vega ~0.44"""
        S, K, dte, iv = 537.0, 450.0, 28, 1.06
        T = _years(dte)
        g = bs_put_greeks(S, K, T, iv)
        assert abs(g['delta'] - (-0.2235)) < 0.001, f"delta={g['delta']}"
        assert abs(g['gamma'] - 0.001895) < 0.0002, f"gamma={g['gamma']}"
        assert abs(g['theta'] - (-1.1925)) < 0.01, f"theta={g['theta']}"
        assert abs(g['vega'] - 0.4443) < 0.005, f"vega={g['vega']}"

    def test_greeks_atm_put(self):
        """ATM put Greeks: delta ≈ -0.5, gamma positive, theta negative, vega positive."""
        S, K, dte, iv = 100.0, 100.0, 30, 0.20
        T = _years(dte)
        g = bs_put_greeks(S, K, T, iv)
        assert abs(g['delta'] - (-0.47)) < 0.10, f"delta={g['delta']}"
        assert g['gamma'] > 0, f"gamma={g['gamma']}"
        assert g['vega'] > 0, f"vega={g['vega']}"
        assert g['theta'] < 0, f"theta={g['theta']}"

    def test_calc_put_delta_sign(self):
        """Put delta must always be negative or zero."""
        test_cases = [
            (500, 450, 0.30, 30/365),
            (450, 500, 0.30, 30/365),
            (100, 100, 0.20, 30/365),
            (100, 100, 0.01, 30/365),
            (100, 100, 2.00, 30/365),
        ]
        for S, K, sigma, T in test_cases:
            d = calc_put_delta(S, K, sigma, T)
            assert d is not None, f"delta=None for S={S}, K={K}, sigma={sigma}, T={T}"
            assert d <= 0, f"delta={d} > 0 for S={S}, K={K}"

    def test_wdc_iv_scenarios(self):
        """WDC IV scenarios: pin exact values from session analysis."""
        S, K, dte, premium = 537.0, 450.0, 28, 7.99
        scenarios = iv_scenarios(S, K, dte, premium, [0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00, 1.06, 1.20])
        pnl_map = {s['iv_pct']: s['pnl'] for s in scenarios}

        assert pnl_map[40.0] == 680
        assert pnl_map[50.0] == 491
        assert pnl_map[60.0] == 223
        assert pnl_map[70.0] == -103
        assert pnl_map[80.0] == -473
        assert pnl_map[90.0] == -875
        assert pnl_map[106.0] == -1563
        assert pnl_map[120.0] == -2198

    def test_wdc_breakeven(self):
        """WDC breakeven: IV 67% at current spot ($537)."""
        S, K, dte, iv, premium = 537.0, 450.0, 28, 1.06, 7.99
        be = breakeven_analysis(S, K, dte, iv, premium)
        assert be['be_iv_pct'] == 67.0

    def test_wdc_risk_matrix_at_current(self):
        """WDC risk matrix at spot $537: P&L $-1,563 at 28 DTE, profitable by DTE 7."""
        S, K, dte, iv, premium = 537.0, 450.0, 28, 1.06, 7.99
        rm = risk_matrix(S, K, dte, iv, premium, dte_points=[28, 21, 14, 7, 0])
        current = [r for r in rm if r['spot'] == S]
        assert current, f"No row for spot={S} in risk matrix"
        row = current[0]
        assert abs(row['dte_28'] - (-1563)) < 5, f"rm[537][28]={row['dte_28']}"
        assert row['dte_7'] > 0, f"rm[537][7]={row['dte_7']} should be positive"
        assert abs(row['dte_0']) < 1, f"rm[537][0]={row['dte_0']} should be ~0 at expiry"

    def test_prob_otm_wdc(self):
        """WDC prob OTM with HV=110%: ~71.9%"""
        p = prob_otm(537.0, 450.0, 28, 1.10)
        assert abs(p - 0.719) < 0.01, f"prob_otm={p:.4f}, expected 0.719"


# ═══════════════════════════════════════════════════════════
# Property tests: mathematical invariants
# ═══════════════════════════════════════════════════════════

class TestPutCallParity:
    """Put-call parity: C - P = S - K*e^(-rT)."""

    def _bs_call_direct(self, S, K, T, sigma):
        """BS call: S*N(d1) - K*e^(-rT)*N(d2)"""
        d1 = (math.log(S/K) + (R + 0.5*sigma**2)*T) / (sigma*math.sqrt(T))
        d2 = d1 - sigma*math.sqrt(T)
        return S * norm.cdf(d1) - K * math.exp(-R*T) * norm.cdf(d2)

    def test_parity_atm(self):
        S, K, T, sigma = 100, 100, 30/365, 0.20
        put = bs_put(S, K, T, sigma)
        call_via_parity = put + S - K * math.exp(-R * T)
        call_direct = self._bs_call_direct(S, K, T, sigma)
        assert abs(call_via_parity - call_direct) < 0.0001

    def test_parity_otm(self):
        S, K, T, sigma = 120, 100, 45/365, 0.25
        put = bs_put(S, K, T, sigma)
        call_via_parity = put + S - K * math.exp(-R * T)
        call_direct = self._bs_call_direct(S, K, T, sigma)
        assert abs(call_via_parity - call_direct) < 0.0001

    def test_parity_itm(self):
        S, K, T, sigma = 80, 100, 60/365, 0.35
        put = bs_put(S, K, T, sigma)
        call_via_parity = put + S - K * math.exp(-R * T)
        call_direct = self._bs_call_direct(S, K, T, sigma)
        assert abs(call_via_parity - call_direct) < 0.0001


class TestDeltaMonotonicity:
    """Delta must be monotonic in strike: higher K → more negative delta."""

    def test_delta_rises_with_strike(self):
        """Higher strike = more ITM put = more negative delta."""
        S, T, sigma = 100, 30/365, 0.20
        d_low = calc_put_delta(S, 90, sigma, T)
        d_atm = calc_put_delta(S, 100, sigma, T)
        d_high = calc_put_delta(S, 110, sigma, T)
        assert d_low > d_atm > d_high, \
            f"delta 90={d_low:.4f}, 100={d_atm:.4f}, 110={d_high:.4f}"

    def test_delta_approaches_zero_as_K_drops(self):
        """As strike K → 0, put is worthless, delta → 0 (from below)."""
        S, T, sigma = 100, 30/365, 0.20
        d = calc_put_delta(S, 1, sigma, T)
        assert d <= 0, f"delta for K=1 should be <= 0, got {d}"
        assert abs(d) < 1e-6, f"delta for K=1 near 0, got {d}"

    def test_delta_approaches_negative_one_as_K_rises(self):
        """As K → ∞, deep ITM put, delta → -1."""
        S, T, sigma = 100, 30/365, 0.20
        d = calc_put_delta(S, 10000, sigma, T)
        assert d is not None
        assert -1.01 < d < -0.95, f"delta for K=10000 near -1, got {d}"


class TestTimeDecay:
    """Put price → intrinsic value as T → 0."""

    def test_convergence_to_intrinsic(self):
        """As T → 0, OTM put → 0, ITM put → K*e^(-rT)-S, ATM put → small."""
        sigma = 0.20
        R_val = 0.045
        T_tiny = 1 / 365 / 24  # ~1 hour

        # ITM: S=80, K=100, price ≈ PV(K) - S
        p_itm = bs_put(80, 100, T_tiny, sigma)
        min_itm = 100 * math.exp(-R_val * T_tiny) - 80
        assert abs(p_itm - min_itm) < 0.01, f"ITM put near expiry: {p_itm} vs {min_itm}"

        # OTM: S=120, K=100, price ≈ 0
        p_otm = bs_put(120, 100, T_tiny, sigma)
        assert p_otm < 0.01

        # ATM: S=100, K=100, price small (< 0.10 even with 20% IV)
        p_atm = bs_put(100, 100, T_tiny, sigma)
        assert p_atm < 0.10, f"ATM put near expiry: {p_atm}"


class TestVegaPositive:
    """Vega must be positive: higher IV → higher option price."""

    def test_vega_sign(self):
        S, K, T = 100, 100, 30/365
        p_low = bs_put(S, K, T, 0.10)
        p_high = bs_put(S, K, T, 0.50)
        assert p_high > p_low

    def test_vega_tends_zero_for_deep_displacement(self):
        """Deep OTM or deep ITM, vega should be >= 0 (approaching 0 but never negative)."""
        S, T = 100, 30/365
        g_otm = bs_put_greeks(S, 1, T, 0.20)
        assert g_otm['vega'] >= 0
        g_itm = bs_put_greeks(S, 10000, T, 0.20)
        assert g_itm['vega'] >= 0


# ═══════════════════════════════════════════════════════════
# Regression test: WDC case study — pin inputs, pin verdict
# ═══════════════════════════════════════════════════════════

class TestWDCRegression:
    """
    WDC 450P Jul 31. Any math change that flips these values fails CI.
    Inputs: spot=$537, strike=$450, DTE=28, IV=106%, premium=$7.99
    """

    INPUTS = dict(S=537.0, K=450.0, dte=28, iv=1.06, premium=7.99, hv=1.10)

    def test_verdict_unforced_loss(self):
        """WDC is a loss but has NOT hit the 2.0x hard override. Staying cold."""
        i = self.INPUTS
        g = bs_put_greeks(i['S'], i['K'], _years(i['dte']), i['iv'])
        pnl = (i['premium'] - g['price']) * 100
        hard_override = i['premium'] * 2.0 * 100

        assert pnl < 0
        assert abs(pnl) < hard_override
        assert abs(pnl + 1563) < 5, f"Expected loss ~$-1,563, got ${pnl}"

    def test_iv_improvement_to_80pct_cuts_loss(self):
        """If IV drops to 80%, loss ~$473. Below the 2.0x override."""
        i = self.INPUTS
        price = bs_put(i['S'], i['K'], _years(i['dte']), 0.80)
        pnl = (i['premium'] - price) * 100
        assert abs(pnl + 473) < 5

    def test_iv_improvement_to_60pct_returns_profit(self):
        """If IV drops to 60%, position is profitable. Thesis working."""
        i = self.INPUTS
        price = bs_put(i['S'], i['K'], _years(i['dte']), 0.60)
        pnl = (i['premium'] - price) * 100
        assert pnl > 0

    def test_prob_otm_remains_high(self):
        """Even at 110% HV, prob OTM > 70%. This was never about the stock."""
        i = self.INPUTS
        p = prob_otm(i['S'], i['K'], i['dte'], i['hv'])
        assert p > 0.70, f"P(OTM)={p:.3f}"


# ═══════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════

class TestConstants:
    def test_trading_days(self):
        assert TRADING_DAYS == 252
    def test_calendar_days(self):
        assert CALENDAR_DAYS == 365
    def test_risk_free_rate(self):
        assert R == 0.045
