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


# ═══════════════════════════════════════════════════════════
# trigger_status: delta-based with Tier 1 priority
# ═══════════════════════════════════════════════════════════

def test_delta_hard_exit_with_confirmed_loss():
    """Delta ≥ 0.35 + loss ≥ 1.5× → RED EXIT (confirmed)."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=500, ma50=600, credit=1.0, opt_mid=2.0,  # 2× loss ≥ 1.5×
        delta=0.35,
    )
    assert status == "RED", f"Expected RED for delta 0.35 + confirmed loss, got {status}"
    assert "EXIT" in label


def test_delta_hard_exit_unconfirmed_is_yellow():
    """Delta ≥ 0.35 but loss < 1.5× → YELLOW (risk exists, market hasn't confirmed)."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=500, ma50=450, credit=1.0, opt_mid=1.0,  # 1× loss < 1.5×
        delta=0.40,
    )
    assert status == "YELLOW", f"Expected YELLOW for unconfirmed delta, got {status}"
    assert "unconfirmed" in label.lower()


def test_delta_soft_watch_with_confirmed_loss():
    """Delta 0.25-0.35 + loss ≥ 1.5× → YELLOW WATCH."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=500, ma50=450, credit=1.0, opt_mid=1.8,  # 1.8× ≥ 1.5×
        delta=0.28,
    )
    assert status == "YELLOW", f"Expected YELLOW for delta 0.28 + confirmed, got {status}"
    assert "WATCH" in label


def test_delta_soft_watch_unconfirmed_is_green():
    """Delta 0.25-0.35 but loss < 1.5× → GREEN (proximity isn't risk)."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=500, ma50=450, credit=1.0, opt_mid=1.0,  # 1× loss < 1.5×
        delta=0.28,
    )
    assert status == "GREEN", f"Expected GREEN for unconfirmed soft delta, got {status}"


def test_dram_55p_scenario():
    """DRAM 55P: delta 0.37, loss 1.33× → YELLOW unconfirmed (not RED)."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=57.77, ma50=50, credit=4.14, opt_mid=5.53,  # 1.33× loss, thesis intact
        delta=0.37,
    )
    assert status == "YELLOW"
    assert "unconfirmed" in label.lower()


def test_loss_breached_no_delta_returns_yellow():
    """3× loss without delta data → YELLOW ESCALATE (diagnose, don't auto-exit)."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(price=500, ma50=450, credit=1.0, opt_mid=5.0)
    assert status == "YELLOW", f"Expected YELLOW for 3× loss no delta, got {status}"
    assert "ESCALATE" in label


def test_thesis_never_downgraded_by_yellow():
    """MA50 broken → ORANGE. A YELLOW from 3×/delta must not downgrade it.
    This is the Tier 1 priority fix — the previous framework had this bug."""
    from review.position_review import trigger_status
    # MA50 broken (400 < 500), 3× loss (5.0 ≥ 3.0), delta is low (0.10)
    status, label, _ = trigger_status(
        price=400, ma50=500, credit=1.0, opt_mid=5.0,
        delta=0.10,
    )
    assert status == "ORANGE", f"Expected ORANGE (thesis), got {status} — YELLOW must not downgrade ORANGE"
    assert "MA50" in label


def test_hard_exit_requires_thesis_plus_elevated_delta():
    """HARD EXIT only when MA50 broken + 3× loss + delta ≥ 0.25."""
    from review.position_review import trigger_status
    # All three: thesis broken, 3× breached, delta elevated → HARD EXIT
    status, label, _ = trigger_status(
        price=400, ma50=500, credit=1.0, opt_mid=5.0,
        delta=0.28,
    )
    assert status == "RED"
    assert label == "HARD EXIT"


def test_delta_hard_exit_beats_thesis():
    """Delta ≥ 0.35 (RED) beats ORANGE (thesis). RED wins."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=400, ma50=500, credit=1.0, opt_mid=2.0,  # 2× loss ≥ 1.5×
        delta=0.40,
    )
    assert status == "RED"
    assert "delta" in label


def test_delta_boundary_soft_watch():
    """Exactly at DELTA_SOFT_WATCH (0.25): ≥ triggers YELLOW."""
    from review.position_review import trigger_status, DELTA_SOFT_WATCH
    status, label, _ = trigger_status(
        price=500, ma50=450, credit=1.0, opt_mid=1.6,  # 1.6× ≥ 1.5×
        delta=DELTA_SOFT_WATCH,
    )
    assert status == "YELLOW"
    assert "WATCH" in label


def test_delta_just_below_soft_watch_is_green():
    """0.249 < 0.25 → no Tier 2 signal regardless of loss."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=500, ma50=450, credit=1.0, opt_mid=2.0,
        delta=0.249,
    )
    assert status == "GREEN"


def test_loss_not_breached_returns_green():
    """Below 3× threshold is OK."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(price=500, ma50=450, credit=10.0, opt_mid=15.0)
    assert status == "GREEN"
    assert "OK" in label


def test_wdc_cut_loss_boundary():
    """3× breach boundary test. No delta → YELLOW ESCALATE (not RED EXIT)."""
    from review.position_review import trigger_status

    # $0.50 × 3.0 = $1.50 threshold. $1.51 breached → YELLOW
    status, label, _ = trigger_status(price=500, ma50=450, credit=0.50, opt_mid=1.51)
    assert status == "YELLOW", f"Expected YELLOW for 3.02× no delta, got {status}"
    assert "ESCALATE" in label

    # $1.49 below threshold → GREEN
    status, label, _ = trigger_status(price=500, ma50=450, credit=0.50, opt_mid=1.49)
    assert status == "GREEN", f"Expected GREEN for 2.98×, got {status}"


def test_loss_breached_plus_thesis_no_delta_returns_orange():
    """MA50 broken + 3× loss but no delta → ORANGE (thesis wins)."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(price=400, ma50=500, credit=1.0, opt_mid=5.0)
    assert status == "ORANGE"
    assert "MA50" in label


def test_3x_low_exposure_delta_returns_watch():
    """3× breach with delta < DELTA_LOW_EXPOSURE → YELLOW WATCH low risk."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=520, ma50=450, credit=1.0, opt_mid=5.0,
        delta=0.08, strike=450,
    )
    assert status == "YELLOW"
    assert "low exposure" in label


def test_yellow_hysteresis_persists_above_resolution():
    """Watch active, mid still ≥ 2.0× → stays YELLOW (not GREEN)."""
    from review.position_review import trigger_status
    # Position was YELLOW at 3.5×. Now at 2.5×. Still above 2.0× threshold.
    watch_state = {
        "reason": "WATCH (3.0x, delta 0.10 low exposure)",
        "resolution_at": 2.0,  # 2.0× credit
        "started_multiple": 3.5,
    }
    status, label, wi = trigger_status(
        price=500, ma50=450, credit=1.0, opt_mid=2.5,
        watch_state=watch_state,
    )
    assert status == "YELLOW"
    assert "low exposure" in label


def test_yellow_hysteresis_clears_below_resolution():
    """Watch active, mid < 2.0× → clears. Normal signal resumes."""
    from review.position_review import trigger_status
    watch_state = {
        "reason": "WATCH (3.0x, delta 0.10 low exposure)",
        "resolution_at": 2.0,
        "started_multiple": 3.5,
    }
    # Mid 1.8 < 2.0 → clears. Normal signal: no thesis, no loss → GREEN
    status, label, wi = trigger_status(
        price=500, ma50=450, credit=1.0, opt_mid=1.8,
        watch_state=watch_state,
    )
    assert status == "GREEN"


def test_yellow_hysteresis_returns_watch_info():
    """New YELLOW → watch_info has reason, resolution_at, started_multiple."""
    from review.position_review import trigger_status
    status, label, wi = trigger_status(
        price=500, ma50=450, credit=1.0, opt_mid=3.5,
    )
    assert status == "YELLOW"
    assert wi is not None
    assert "reason" in wi
    assert wi["resolution_at"] == 2.0  # WATCH_RESOLUTION_MULTIPLE × credit
    assert wi["started_multiple"] == 3.5


def test_yellow_hysteresis_overridden_by_new_red():
    """Watch active → but current delta ≥ 0.35 → RED wins, watch cleared."""
    from review.position_review import trigger_status
    watch_state = {
        "reason": "WATCH (3.0x, delta 0.10 low exposure)",
        "resolution_at": 2.0,
        "started_multiple": 3.5,
    }
    # Hysteresis active, but delta=0.40 → RED overrides
    status, label, wi = trigger_status(
        price=500, ma50=450, credit=1.0, opt_mid=2.5,
        delta=0.40, watch_state=watch_state,
    )
    assert status == "RED"
    assert "delta" in label
    assert wi is None  # RED returns no watch_info


def test_yellow_hysteresis_overridden_by_new_orange():
    """Watch active → but MA50 broken → ORANGE wins, watch cleared."""
    from review.position_review import trigger_status
    watch_state = {
        "reason": "WATCH (3.0x, delta 0.10 low exposure)",
        "resolution_at": 2.0,
        "started_multiple": 3.5,
    }
    status, label, wi = trigger_status(
        price=400, ma50=500, credit=1.0, opt_mid=2.5,
        watch_state=watch_state,
    )
    assert status == "ORANGE"
    assert "MA50" in label
    assert wi is None


def test_yellow_hysteresis_exactly_at_resolution():
    """Mid == 2.0× (resolution_at) → still YELLOW (≥ check)."""
    from review.position_review import trigger_status
    watch_state = {
        "reason": "WATCH (3.0x, delta 0.10 low exposure)",
        "resolution_at": 2.0,
        "started_multiple": 3.5,
    }
    status, label, wi = trigger_status(
        price=500, ma50=450, credit=1.0, opt_mid=2.0,
        watch_state=watch_state,
    )
    assert status == "YELLOW"


def test_yellow_hysteresis_just_below_resolution():
    """Mid 1.99 < 2.0 → clears. Normal signal: no thesis, no loss → GREEN."""
    from review.position_review import trigger_status
    watch_state = {
        "reason": "WATCH (3.0x, delta 0.10 low exposure)",
        "resolution_at": 2.0,
        "started_multiple": 3.5,
    }
    status, label, wi = trigger_status(
        price=500, ma50=450, credit=1.0, opt_mid=1.99,
        watch_state=watch_state,
    )
    assert status == "GREEN"


def test_validate_quote_crossed_market():
    """Bid > Ask → DATA ALERT (hard rejection)."""
    from review.position_review import validate_quote
    valid, reason, warnings = validate_quote(bid=10.0, ask=8.0, mid=9.0)
    assert valid is False
    assert "crossed" in reason
    assert warnings == []


def test_validate_quote_wide_spread():
    """Spread > 100% of mid → hard rejection."""
    from review.position_review import validate_quote
    valid, reason, warnings = validate_quote(bid=1.0, ask=20.0, mid=10.5)
    assert valid is False
    assert "spread" in reason


def test_validate_quote_spread_warning():
    """Spread 20-100% of mid → valid but warns (unreliable midpoint). WDC Jul 23 was ~28%."""
    from review.position_review import validate_quote
    valid, reason, warnings = validate_quote(bid=7.15, ask=9.45, mid=8.30)
    assert valid is True
    assert reason == ""
    assert any("wide spread" in w for w in warnings)
    assert any("28" in w for w in warnings)


def test_validate_quote_spread_exactly_20pct_warns():
    """Exactly 20% spread → warning (≥ triggers)."""
    from review.position_review import validate_quote
    # bid=9.0 ask=11.0 mid=10.0, spread=2.0/10.0=20.0% exactly
    valid, reason, warnings = validate_quote(bid=9.0, ask=11.0, mid=10.0)
    assert valid is True
    assert any("wide spread" in w for w in warnings)
    assert any("20" in w for w in warnings)


def test_validate_quote_spread_exactly_100pct_warns():
    """Exactly 100% spread → warning (not rejection). >100% is hard rejection."""
    from review.position_review import validate_quote
    valid, reason, warnings = validate_quote(bid=5.0, ask=15.0, mid=10.0)
    assert valid is True
    assert any("wide spread" in w for w in warnings)
    assert any("100" in w for w in warnings)


def test_validate_quote_spread_just_above_100pct_rejected():
    """101% spread → hard rejection."""
    from review.position_review import validate_quote
    valid, reason, warnings = validate_quote(bid=4.95, ask=15.0, mid=9.975)
    assert valid is False
    assert "spread" in reason


def test_validate_quote_zero_bid():
    """Zero bid → valid (liquidity warning only, not invalid)."""
    from review.position_review import validate_quote
    valid, reason, warnings = validate_quote(bid=0.0, ask=5.0, mid=2.5)
    assert valid is True
    assert any("zero-volume" in w for w in warnings)


def test_validate_quote_valid():
    """Normal quote → valid, no warnings."""
    from review.position_review import validate_quote
    valid, reason, warnings = validate_quote(bid=9.5, ask=10.5, mid=10.0)
    assert valid is True
    assert reason == ""
    assert warnings == []


def test_validate_quote_below_warning_threshold():
    """Spread < 20% → no warning."""
    from review.position_review import validate_quote
    # 15% spread: bid=9.25 ask=10.75 mid=10.0, spread=1.5/10=15%
    valid, reason, warnings = validate_quote(bid=9.25, ask=10.75, mid=10.0)
    assert valid is True
    assert warnings == []


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
    status, label, _ = trigger_status(price=500, ma50=450, credit=0, opt_mid=5.0)
    assert status == "GREEN"
    assert "OK" in label


def test_trigger_status_opt_mid_none():
    """trigger_status with opt_mid=None: doesn't crash, loss not breached."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(price=400, ma50=500, credit=1.0, opt_mid=None)
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
    """mid == credit × CUT_LOSS_MULTIPLE: ≥ triggers escalation. No delta → YELLOW."""
    from review.position_review import trigger_status
    # CUT_LOSS_MULTIPLE=3.0. credit=1.0 → threshold=3.0
    status, label, _ = trigger_status(price=500, ma50=450, credit=1.0, opt_mid=3.0)
    assert status == "YELLOW", f"Exactly at 3× threshold no delta should be YELLOW, got {status}"
    assert "ESCALATE" in label


# ═══════════════════════════════════════════════════════════
# Edge-case & robustness tests
# ═══════════════════════════════════════════════════════════

def test_trigger_status_iv_none():
    """IV=None: delta cannot be estimated. Falls through to no-delta path."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=500, ma50=450, credit=1.0, opt_mid=5.0,
        strike=450, dte=24, iv=None,
    )
    assert status == "YELLOW"
    assert "ESCALATE" in label


def test_trigger_status_iv_zero():
    """IV=0: _estimate_delta returns None. Falls through to no-delta path."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=500, ma50=450, credit=1.0, opt_mid=5.0,
        strike=450, dte=24, iv=0.0,
    )
    assert status == "YELLOW"
    assert "ESCALATE" in label


def test_trigger_status_iv_negative():
    """IV negative: _estimate_delta returns None. No crash."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=500, ma50=450, credit=1.0, opt_mid=5.0,
        strike=450, dte=24, iv=-0.5,
    )
    assert status == "YELLOW"
    assert "ESCALATE" in label


def test_trigger_status_dte_zero():
    """DTE=0 (expired): _estimate_delta returns None."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=500, ma50=450, credit=1.0, opt_mid=5.0,
        strike=450, dte=0, iv=0.50,
    )
    assert status == "YELLOW"
    assert "ESCALATE" in label


def test_trigger_status_dte_negative():
    """DTE negative (past expiry): no crash."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=500, ma50=450, credit=1.0, opt_mid=5.0,
        strike=450, dte=-3, iv=0.50,
    )
    assert status == "YELLOW"
    assert "ESCALATE" in label


def test_trigger_status_nan_delta():
    """NaN delta in chain: abs(NaN) is NaN, which fails all comparisons."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=500, ma50=450, credit=1.0, opt_mid=5.0,
        delta=float('nan'),
    )
    assert status == "YELLOW"
    assert "ESCALATE" in label


def test_trigger_status_missing_strike():
    """No strike, no delta: falls to no-delta path."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=500, ma50=450, credit=1.0, opt_mid=5.0,
    )
    assert status == "YELLOW"
    assert "ESCALATE" in label


def test_trigger_status_negative_spot():
    """Negative spot (data error): doesn't crash. Thesis fires ORANGE."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=-100, ma50=450, credit=1.0, opt_mid=5.0,
        strike=450, dte=24, iv=0.50,
    )
    assert status == "ORANGE"


def test_trigger_status_credit_none():
    """credit=None: loss not breached. Thesis check works. No crash."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=500, ma50=600, credit=None, opt_mid=5.0,
    )
    assert status == "ORANGE"


def test_trigger_status_opt_mid_zero():
    """opt_mid=0: loss not breached. GREEN if thesis intact."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=500, ma50=450, credit=1.0, opt_mid=0.0,
    )
    assert status == "GREEN"


def test_watch_state_corrupted_keys():
    """watch_state with missing 'reason' key: doesn't crash."""
    from review.position_review import trigger_status
    bad_state = {"resolution_at": 2.0}
    try:
        status, label, _ = trigger_status(
            price=500, ma50=450, credit=1.0, opt_mid=1.5,
            watch_state=bad_state,
        )
        assert status in ("GREEN", "YELLOW")
    except KeyError:
        assert False, "watch_state with missing 'reason' key crashed"


def test_watch_state_missing_resolution():
    """watch_state with no 'resolution_at': treated as no watch."""
    from review.position_review import trigger_status
    bad_state = {"reason": "old watch"}
    status, label, _ = trigger_status(
        price=500, ma50=450, credit=1.0, opt_mid=1.5,
        watch_state=bad_state,
    )
    assert status == "GREEN"


def test_trigger_status_absurd_iv():
    """Absurdly high IV (500%) → BS math works. No crash."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=500, ma50=450, credit=1.0, opt_mid=5.0,
        strike=450, dte=24, iv=5.0,
    )
    assert status in ("YELLOW", "RED", "ORANGE")


def test_full_priority_matrix_red_wins():
    """RED (delta confirmed) > ORANGE (thesis) > YELLOW (3× escalation)."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=400, ma50=500, credit=1.0, opt_mid=2.0,
        delta=0.36,
    )
    assert status == "RED"
    assert "delta" in label


def test_full_priority_matrix_orange_over_yellow():
    """ORANGE (thesis) > YELLOW (3× with low delta)."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=400, ma50=500, credit=1.0, opt_mid=5.0,
        delta=0.10,
    )
    assert status == "ORANGE"


def test_full_priority_matrix_yellow_over_green():
    """YELLOW (3× no delta) > GREEN."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=500, ma50=450, credit=1.0, opt_mid=5.0,
    )
    assert status == "YELLOW"


def test_full_priority_matrix_hard_exit():
    """All three fire: thesis + 3× loss + elevated delta → HARD EXIT."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=400, ma50=500, credit=1.0, opt_mid=5.0,
        delta=0.28,
    )
    assert status == "RED"
    assert label == "HARD EXIT"


# ═══════════════════════════════════════════════════════════
# MA50 persistence tests
# ═══════════════════════════════════════════════════════════

def test_ma50_no_state_immediate_orange():
    """Without ma50_state: thesis broken is immediate ORANGE (backward compat)."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=400, ma50=500, credit=1.0, opt_mid=1.0,
    )
    assert status == "ORANGE"
    assert "MA50" in label


def test_ma50_day1_returns_yellow():
    """ma50_state with days=0: day 1 below MA50 → YELLOW."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=400, ma50=500, credit=1.0, opt_mid=1.0,
        ma50_state={"days": 0},
    )
    assert status == "YELLOW"
    assert "day 1" in label


def test_ma50_day2_returns_orange():
    """ma50_state with days=1: day 2 below MA50 → ORANGE."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=400, ma50=500, credit=1.0, opt_mid=1.0,
        ma50_state={"days": 1},
    )
    assert status == "ORANGE"
    assert "MA50" in label


def test_ma50_delta_red_beats_thesis_day1():
    """Day 1 MA50 YELLOW is overridden by Tier 2 RED (delta confirmed)."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=400, ma50=500, credit=1.0, opt_mid=2.0,
        delta=0.36,
        ma50_state={"days": 0},
    )
    assert status == "RED"


def test_ma50_thesis_beats_3x_yellow():
    """ORANGE (day 2 MA50) beats 3× YELLOW."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=400, ma50=500, credit=1.0, opt_mid=5.0,
        ma50_state={"days": 1},
    )
    assert status == "ORANGE"


def test_ma50_recovery_no_breach():
    """Price above MA50: no thesis signal regardless of ma50_state."""
    from review.position_review import trigger_status
    status, label, _ = trigger_status(
        price=600, ma50=500, credit=1.0, opt_mid=1.0,
        ma50_state={"days": 3},
    )
    assert status == "GREEN"
