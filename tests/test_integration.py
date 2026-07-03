"""Integration tests: every consumer of pricing.py must work at runtime.

These tests import and call the actual consumer modules, proving that
the refactoring didn't break them. If these fail but test_pricing.py passes,
the refactoring silently broke a consumer (the dict-unpack bug class).
"""
import sys
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

WDC = dict(spot=537, strike=450, dte=28, iv=1.06, T=28/365, rate=0.045)


def test_bs_greeks_wrapper_round_trip():
    """position_review.bs_greeks returns properly rounded dict."""
    from review.position_review import bs_greeks
    g = bs_greeks(WDC['spot'], WDC['strike'], WDC['dte'], WDC['iv'])
    assert isinstance(g, dict)
    assert g['delta'] == -0.2235
    assert g['gamma'] == 0.0019
    assert g['vega'] == 0.44
    assert g['theta'] == -1.19
    assert g['iv_absolute'] == 106.0


def test_bs_price_matches_pricing_module():
    """position_review.bs_price matches pricing.bs_put."""
    from review.position_review import bs_price
    from pricing import bs_put

    p = bs_price(WDC['spot'], WDC['strike'], WDC['T'], WDC['iv'], WDC['rate'])
    expected = bs_put(WDC['spot'], WDC['strike'], WDC['T'], WDC['iv'], WDC['rate'])
    assert abs(p - expected) < 0.005


def test_calc_put_delta_via_wrapper():
    """position_review uses calc_put_delta from pricing directly."""
    from review.position_review import calc_put_delta
    d = calc_put_delta(WDC['spot'], WDC['strike'], WDC['iv'], WDC['T'])
    assert d is not None
    assert abs(d - (-0.2235)) < 0.001


def test_csp_scanner_imports():
    """scanner/csp_scanner.py imports cleanly and constants are defined."""
    from scanner.csp_scanner import (
        find_target_strike, STALENESS_HOURS, MAX_BID_ASK_SPREAD_PCT
    )
    assert STALENESS_HOURS == 24
    assert MAX_BID_ASK_SPREAD_PCT == 0.25


def test_earnings_gate_dte7():
    """DTE ≤ 7 always triggers regardless of earnings."""
    from review.position_review import check_earnings_gate
    risk, note = check_earnings_gate(7)
    assert risk is True
    assert "gamma dominates" in note


def test_earnings_gate_inside_window():
    """Earnings inside DTE window triggers binary risk flag."""
    from review.position_review import check_earnings_gate
    from datetime import date, timedelta
    earnings = date.today() + timedelta(days=10)
    risk, note = check_earnings_gate(30, earnings)
    assert risk is True
    assert "Earnings in 10d" in note


def test_earnings_gate_outside_window():
    """Earnings beyond DTE is no flag."""
    from review.position_review import check_earnings_gate
    from datetime import date, timedelta
    earnings = date.today() + timedelta(days=60)
    risk, _ = check_earnings_gate(30, earnings)
    assert risk is False


def test_earnings_gate_no_earnings():
    """No earnings date, no flag."""
    from review.position_review import check_earnings_gate
    risk, _ = check_earnings_gate(30, None)
    assert risk is False


def test_loss_breached_is_always_red():
    """>3× premium (= −200%) returns RED regardless of IV. No escape hatch."""
    from review.position_review import trigger_status
    status, label = trigger_status(price=500, ma50=450, credit=1.0, opt_mid=5.0)
    assert status == "RED", f"Expected RED, got {status}"
    assert "EXIT" in label


def test_loss_not_breached_returns_green():
    """Below threshold is OK."""
    from review.position_review import trigger_status
    status, label = trigger_status(price=500, ma50=450, credit=10.0, opt_mid=15.0)
    assert status == "GREEN"
    assert "OK" in label


def test_wdc_cut_loss_boundary():
    """Sold $0.50 put → mid $1.51 (= 3.02×, −202%) → EXIT. Boundary: $1.49 (= 2.98×, −198%) → safe.
    The constant is 3.0; the business rule is −200%."""
    from review.position_review import trigger_status

    # $0.50 × 3.0 = $1.50 threshold. $1.51 is breached.
    status, label = trigger_status(price=500, ma50=450, credit=0.50, opt_mid=1.51)
    assert status == "RED", f"Expected RED for 3.02×, got {status}"
    assert "EXIT" in label

    # $1.49 is below threshold — not breached.
    status, label = trigger_status(price=500, ma50=450, credit=0.50, opt_mid=1.49)
    assert status == "GREEN", f"Expected GREEN for 2.98×, got {status}"


def test_loss_breached_plus_thesis_returns_hard_exit():
    """Both conditions fire → HARD EXIT."""
    from review.position_review import trigger_status
    status, label = trigger_status(price=400, ma50=500, credit=1.0, opt_mid=5.0)
    assert status == "RED"
    assert label == "HARD EXIT"


# ═══════════════════════════════════════════════════════════
# Edge-case and dangerous-path tests
# ═══════════════════════════════════════════════════════════

def test_find_target_strike_rejects_stale_option():
    """Option with last trade > 24h ago is rejected. Returns None."""
    import pandas as pd
    from scanner.csp_scanner import find_target_strike
    from datetime import datetime, timedelta
    stale_date = datetime.now() - timedelta(hours=30)
    df = pd.DataFrame([{
        "strike": 50.0, "impliedVolatility": 0.30,
        "bid": 2.0, "ask": 2.5, "lastPrice": 2.25,
        "lastTradeDate": stale_date, "openInterest": 500,
    }])
    result = find_target_strike(df, S=55.0, T=45/365)
    assert result is None, f"Stale option should be rejected, got {result}"


def test_find_target_strike_rejects_wide_spread():
    """Option with bid/ask spread > 25% of mid is rejected."""
    import pandas as pd
    from scanner.csp_scanner import find_target_strike
    # 35% spread: bid=1.0, ask=2.35, mid=1.675, spread=1.35/1.675=80.6%
    df = pd.DataFrame([{
        "strike": 50.0, "impliedVolatility": 0.30,
        "bid": 1.0, "ask": 2.35, "lastPrice": 1.67,
        "openInterest": 500,
    }])
    result = find_target_strike(df, S=55.0, T=45/365)
    assert result is None, f"Wide spread should be rejected, got {result}"


def test_ma_tier_price_equals_ma200():
    """Price == 200MA: not 'red' (uses strict <), passes if above 50MA."""
    from scanner.csp_scanner import ma_tier
    # Exactly at 200MA, above 50MA → green
    assert ma_tier(100, 90, 100) == "green"
    # Exactly at 200MA, no 50MA → amber
    assert ma_tier(100, None, 100) == "amber"
    # Exactly at 200MA, below 50MA → amber
    assert ma_tier(100, 101, 100) == "amber"
    # Below 200MA → red
    assert ma_tier(99, 90, 100) == "red"


def test_trigger_status_credit_zero():
    """trigger_status with credit=0: notional check doesn't crash."""
    from review.position_review import trigger_status
    status, label = trigger_status(price=500, ma50=450, credit=0, opt_mid=5.0)
    assert status == "GREEN"
    assert "OK" in label


def test_trigger_status_opt_mid_none():
    """trigger_status with opt_mid=None: doesn't crash, loss not breached."""
    from review.position_review import trigger_status
    status, label = trigger_status(price=400, ma50=500, credit=1.0, opt_mid=None)
    # thesis broken (price < ma50), but loss not breached → ORANGE
    assert status == "ORANGE"
    assert "MA50" in label


def test_earnings_gate_dte_exactly_7():
    """DTE == 7: gamma dominates, should trigger."""
    from review.position_review import check_earnings_gate
    risk, note = check_earnings_gate(7)
    assert risk is True
    assert "gamma dominates" in note


def test_earnings_gate_dte_none():
    """DTE=None: no trigger, no crash."""
    from review.position_review import check_earnings_gate
    risk, note = check_earnings_gate(None)
    assert risk is False


def test_earnings_gate_dte_zero():
    """DTE=0 (expired): no trigger."""
    from review.position_review import check_earnings_gate
    risk, note = check_earnings_gate(0)
    assert risk is False


def test_loss_breached_exactly_at_threshold():
    """mid == credit × CUT_LOSS_MULTIPLE: >= triggers exit."""
    from review.position_review import trigger_status
    # CUT_LOSS_MULTIPLE=3.0. credit=1.0 → threshold=3.0
    status, label = trigger_status(price=500, ma50=450, credit=1.0, opt_mid=3.0)
    assert status == "RED", f"Exactly at threshold should be RED, got {status}"
    assert "EXIT" in label
