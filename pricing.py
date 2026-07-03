#!/usr/bin/env python3
"""
Shared Pricing Module — single source of truth for options-position-review.

Imported by csp_scanner.py (entry scanner) and deep_analysis.py (position review).
One Black-Scholes implementation. One set of constants. No duplication.

Constants:
    R = 0.045              risk-free rate (4.5%)
    TRADING_DAYS = 252     trading days/year (theta daily conversion)
    CALENDAR_DAYS = 365    calendar days/year (DTE→years for T in BS)

All Greeks are per-share. Multiply by 100 for per-contract.
"""

import math
from typing import Optional

import numpy as np
from scipy.stats import norm

# ---- Constants ----

R = 0.045
TRADING_DAYS = 252
CALENDAR_DAYS = 365


def _years(dte: int) -> float:
    """Convert DTE to years (calendar basis for Black-Scholes T)."""
    return dte / CALENDAR_DAYS


# ---- Black-Scholes Core (scipy.stats.norm, no hand-rolled CDF) ----

def bs_put(S: float, K: float, T: float, sigma: float, r: float = R) -> float:
    """Black-Scholes European put price. S=spot, K=strike, T=years, sigma=decimal."""
    if T <= 0:
        return max(K - S, 0.0)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def bs_put_greeks(S: float, K: float, T: float, sigma: float, r: float = R) -> dict:
    """
    All five Greeks for a European put option.

    Returns dict:
        delta, gamma, theta, vega, rho, price

    delta/gamma/theta/vega/rho are per-share.
    theta: per trading day (annual ÷ 252)
    vega:  P&L per 1% IV change
    rho:   P&L per 1% interest rate change
    """
    if T <= 0:
        itm = 1.0 if K > S else 0.0
        return {
            "delta": -itm,
            "gamma": 0.0,
            "theta": 0.0,
            "vega": 0.0,
            "rho": 0.0,
            "price": max(K - S, 0.0),
        }

    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    delta = -norm.cdf(-d1)
    gamma = norm.pdf(d1) / (S * sigma * math.sqrt(T))
    theta_term1 = -(S * norm.pdf(d1) * sigma) / (2.0 * math.sqrt(T))
    theta_term2 = r * K * math.exp(-r * T) * norm.cdf(-d2)
    theta = (theta_term1 + theta_term2) / TRADING_DAYS  # per trading day
    vega_per_pct = S * norm.pdf(d1) * math.sqrt(T) / 100.0  # per 1% IV change
    rho_per_pct = -K * T * math.exp(-r * T) * norm.cdf(-d2) / 100.0  # per 1% rate change
    price = bs_put(S, K, T, sigma, r)

    return {
        "delta": float(delta),
        "gamma": float(gamma),
        "theta": float(theta),
        "vega": float(vega_per_pct),
        "rho": float(rho_per_pct),
        "price": float(price),
    }


def calc_put_delta(S: float, K: float, sigma: float, T: float, r: float = R) -> Optional[float]:
    """
    Black-Scholes delta for a European put. Single-value convenience for the scanner.
    Returns None if inputs are invalid (zero/negative sigma or T).
    """
    if sigma <= 0 or T <= 0:
        return None
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    return float(-norm.cdf(-d1))


# ---- Phase 9: Deep Analysis Tools ----

def risk_matrix(
    spot: float,
    strike: float,
    dte: int,
    iv: float,
    premium: float,
    price_points: Optional[list] = None,
    dte_points: Optional[list] = None,
) -> list[dict]:
    """
    Phase 9b: P&L grid at various spot prices × DTE checkpoints.
    iv = decimal (e.g. 0.60 for 60%), premium = per-share premium received.
    Returns list of rows: {spot, dte_X: pnl, ...}
    """
    if price_points is None:
        pct_step = 0.05
        points = []
        p = strike
        while p <= spot * 1.2:
            points.append(round(p, 2))
            p += spot * pct_step
        if spot not in points:
            points.append(spot)
        price_points = sorted(set(points))

    if dte_points is None:
        dte_points = [dte, 21, 14, 7, 0]
        dte_points = sorted([d for d in dte_points if 0 <= d <= dte], reverse=True)

    rows = []
    for sp in price_points:
        row = {"spot": sp}
        for d in dte_points:
            if d == 0:
                pnl = max(strike - sp, 0.0) * -100  # intrinsic at expiry
            else:
                T = _years(d)
                option_mid = bs_put(sp, strike, T, iv)
                pnl = (premium - option_mid) * 100
            row[f"dte_{d}"] = round(pnl, 0)
        rows.append(row)
    return rows


def iv_scenarios(
    spot: float,
    strike: float,
    dte: int,
    premium: float,
    iv_levels: Optional[list] = None,
) -> list[dict]:
    """
    Phase 9c: Option value and P&L at different IV levels (spot held constant).
    premium = per-share premium received.
    Returns list of {iv_pct, option_price, pnl}.
    """
    if iv_levels is None:
        iv_levels = [0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00, 1.10, 1.20]
    T = _years(dte)
    rows = []
    for iv in iv_levels:
        option_price = bs_put(spot, strike, T, iv)
        pnl = (premium - option_price) * 100
        rows.append({
            "iv_pct": round(iv * 100, 1),
            "option_price": round(option_price, 2),
            "pnl": round(pnl, 0),
        })
    return rows


def one_day_shocks(
    spot: float,
    strike: float,
    dte: int,
    iv: float,
    premium: float,
    shock_pcts: Optional[list] = None,
) -> list[dict]:
    """
    Phase 9d: Delta + gamma P&L for 1-day moves. IV held constant.
    shock_pcts: e.g. [-0.05, -0.02, 0, 0.02, 0.05] for ±5%, ±2%, 0%.
    Returns list of {move_pct, spot, pnl_change}.
    """
    if shock_pcts is None:
        shock_pcts = [-0.05, -0.03, -0.02, -0.01, 0, 0.01, 0.02, 0.03, 0.05]

    T = _years(dte)
    base_price = bs_put(spot, strike, T, iv)
    base_pnl = (premium - base_price) * 100

    rows = []
    for shock in shock_pcts:
        new_spot = spot * (1 + shock)
        T_after = _years(dte - 1) if dte > 1 else 0.003  # ~1 trading day
        new_price = bs_put(new_spot, strike, T_after, iv)
        new_pnl = (premium - new_price) * 100
        rows.append({
            "move_pct": round(shock * 100, 1),
            "spot": round(new_spot, 2),
            "pnl_change": round(new_pnl - base_pnl, 0),
        })
    return rows


def gamma_profile(
    spot: float,
    strike: float,
    dte: int,
    iv: float,
    price_points: Optional[list] = None,
) -> list[dict]:
    """
    Phase 9e: Delta, gamma, and $ per $1 move at different spot prices.
    Returns list of {spot, delta, gamma, dollar_per_dollar}.
    """
    if price_points is None:
        points = []
        p = strike
        while p <= spot * 1.2:
            points.append(round(p))
            p += spot * 0.10
        price_points = sorted(set(points + [round(spot, 2)]))

    T = _years(dte)
    rows = []
    for sp in price_points:
        greeks = bs_put_greeks(sp, strike, T, iv)
        dollar_move = (greeks["delta"] + 0.5 * greeks["gamma"]) * 100
        rows.append({
            "spot": sp,
            "delta": round(greeks["delta"], 4),
            "gamma": round(greeks["gamma"], 6),
            "dollar_per_dollar": round(abs(dollar_move), 2),
        })
    return rows


def breakeven_analysis(
    spot: float,
    strike: float,
    dte: int,
    iv: float,
    premium: float,
    r: float = R,
) -> dict:
    """
    Phase 9f: Breakeven IV at current spot, breakeven spot at current IV,
    and 2-3 realistic recovery paths.
    premium = per-share premium received.
    """
    # Breakeven IV at current spot (binary search)
    def pnl_at_iv(sigma):
        return premium - bs_put(spot, strike, _years(dte), sigma, r)

    lo, hi = 0.01, 5.0
    for _ in range(50):
        mid = (lo + hi) / 2
        if pnl_at_iv(mid) >= 0:
            lo = mid
        else:
            hi = mid
    be_iv = lo

    # Breakeven spot at current IV (binary search)
    # For a put, price falls as spot rises. BE spot is above current spot.
    def pnl_at_spot(S):
        return premium - bs_put(S, strike, _years(dte), iv, r)

    lo, hi = spot, spot * 3
    for _ in range(50):
        mid = (lo + hi) / 2
        if pnl_at_spot(mid) >= 0:
            lo = mid
        else:
            hi = mid
    be_spot = lo

    # Recovery paths
    paths = []
    for iv_target, spot_target, label in [
        (iv - 0.10, spot, "IV -10pts, spot flat"),
        (iv * 0.7, spot, "IV 70% of current, spot flat"),
        (0.60, spot * 1.05, "IV 60%, spot +5%"),
    ]:
        if iv_target < 0.05:
            continue
        opt_price = bs_put(spot_target, strike, _years(dte), max(iv_target, 0.05), r)
        pnl = (premium - opt_price) * 100
        paths.append({
            "label": label,
            "iv_pct": round(iv_target * 100, 1),
            "spot": round(spot_target, 2),
            "option_price": round(opt_price, 2),
            "pnl": round(pnl, 0),
        })

    # Downside path
    downside_price = bs_put(spot * 0.93, strike, _years(dte), iv, r)
    downside_pnl = (premium - downside_price) * 100
    paths.append({
        "label": "IV stays, spot -7%",
        "iv_pct": round(iv * 100, 1),
        "spot": round(spot * 0.93, 2),
        "option_price": round(downside_price, 2),
        "pnl": round(downside_pnl, 0),
    })

    return {
        "be_iv_pct": round(be_iv * 100, 1),
        "be_spot": round(be_spot, 2),
        "paths": paths,
    }


def prob_otm(spot: float, strike: float, dte: int, hv: float) -> float:
    """
    Simple normal approximation: probability of expiring OTM.
    spot=current price, strike=put strike, dte=days to expiry, hv=decimal (e.g. 0.50).
    Uses log(spot/strike): for a put, OTM means spot > strike at expiry.
    Uses calendar-day T convention (dte/365) matching Black-Scholes engine.
    """
    T = _years(dte)
    sigma_T = hv * math.sqrt(T)
    z = math.log(spot / strike) / sigma_T if sigma_T > 0 else (1.0 if spot > strike else -1.0)
    return float(norm.cdf(z))


# ---- Phase 10: Forward-Looking Context ----

def expected_vs_actual(atm_straddle_price: float, spot: float, daily_returns: list[float]) -> dict:
    """
    Phase 10b: Compare option-implied daily move to recent actual moves.
    daily_returns: list of decimal returns (e.g. [0.02, -0.015, ...])
    Returns {expected_move_pct, actual_median_abs, days_over_expected, verdict}
    """
    expected_move_pct = atm_straddle_price / spot
    actual_abs = [abs(r) for r in daily_returns]
    actual_median = np.median(actual_abs) if actual_abs else 0
    days_over = sum(1 for r in actual_abs if r > expected_move_pct)
    total = len(actual_abs)

    if total == 0:
        verdict = "insufficient_data"
    elif days_over > total / 2:
        verdict = "underpricing_risk"
    elif days_over < total / 3:
        verdict = "overpricing_edge"
    else:
        verdict = "fairly_priced"

    return {
        "expected_move_pct": round(expected_move_pct * 100, 2),
        "actual_median_abs_pct": round(actual_median * 100, 2),
        "days_over_expected": days_over,
        "total_days": total,
        "verdict": verdict,
    }


def correlation_check(prices_a: list[float], prices_b: list[float]) -> Optional[float]:
    """
    Phase 10d: Daily returns correlation.
    Returns Pearson r, or None if insufficient data.
    """
    if len(prices_a) < 10 or len(prices_b) < 10:
        return None
    rets_a = [math.log(prices_a[i] / prices_a[i - 1]) for i in range(1, len(prices_a))]
    rets_b = [math.log(prices_b[i] / prices_b[i - 1]) for i in range(1, len(prices_b))]
    min_len = min(len(rets_a), len(rets_b))
    rets_a = rets_a[-min_len:]
    rets_b = rets_b[-min_len:]
    if min_len < 5:
        return None
    return float(np.corrcoef(rets_a, rets_b)[0, 1])


# ---- Phase 11: IV Outlook ----

def iv_term_structure(ticker_data: dict) -> dict:
    """
    Phase 11a: Analyze IV across different expiries.
    ticker_data: {expiry_label: {"dte": int, "iv": float}, ...}
    Returns {shape, verdict, expiries: [{label, dte, iv}]}
    """
    expiries = sorted(ticker_data.values(), key=lambda x: x["dte"])
    if len(expiries) < 2:
        return {"shape": "insufficient_data", "verdict": "unknown", "expiries": []}

    near = expiries[0]["iv"]
    far = expiries[-1]["iv"]
    ratio = near / far if far > 0 else 1.0

    if ratio > 1.10:
        shape = "backwardation"
        verdict = "improving"
    elif ratio < 0.90:
        shape = "contango"
        verdict = "worsening"
    else:
        shape = "flat"
        verdict = "unchanged"

    entries = [
        {"label": e["label"], "dte": e["dte"], "iv": round(e["iv"] * 100, 1)}
        for e in expiries
    ]
    return {"shape": shape, "verdict": verdict, "expiries": entries}


def iv_analogs(
    ticker: str,
    current_iv: float,
    median_iv: float,
    iv_history: list[dict],
) -> dict:
    """
    Phase 11b: Find historical IV spike episodes and their recovery timelines.
    iv_history: list of {date, iv} from yfinance over 2-3 years.
    Returns {episodes: [...], median_days_to_median, median_days_to_50pct}
    """
    episodes = []
    in_spike = False
    spike_start = None
    spike_peak = 0

    threshold = current_iv * 0.8  # crossings above 80% of current level

    for entry in iv_history:
        iv_val = entry["iv"]
        if iv_val >= threshold and not in_spike:
            in_spike = True
            spike_start = entry["date"]
            spike_peak = iv_val
        elif in_spike:
            if iv_val > spike_peak:
                spike_peak = iv_val
            if iv_val < median_iv:
                # Find 50% retrace
                retrace_target = (spike_peak + median_iv) / 2
                days_to_median = (entry["date"] - spike_start).days
                # Find when it crossed the retrace
                days_50 = days_to_median
                for e2 in iv_history:
                    if e2["date"] > spike_start and e2["iv"] <= retrace_target:
                        days_50 = (e2["date"] - spike_start).days
                        break
                episodes.append({
                    "date": str(spike_start),
                    "peak_iv_pct": round(spike_peak * 100, 1),
                    "days_to_median": days_to_median,
                    "days_to_50pct": days_50,
                })
                in_spike = False
                spike_peak = 0

    if not episodes:
        return {"episodes": [], "median_days_to_median": None, "median_days_to_50pct": None}

    days_med = [e["days_to_median"] for e in episodes]
    days_50 = [e["days_to_50pct"] for e in episodes]

    return {
        "episodes": sorted(episodes, key=lambda x: x["date"], reverse=True)[:5],
        "median_days_to_median": int(np.median(days_med)),
        "median_days_to_50pct": int(np.median(days_50)),
    }


def iv_outlook(
    ticker: str,
    strike: float,
    current_iv: float,
    ticker_data: Optional[dict] = None,
    iv_history: Optional[list] = None,
    median_iv: Optional[float] = None,
) -> dict:
    """
    Combined Phase 11 verdict: IV outlook for a position.
    Returns {verdict, term_structure, analogs, summary}
    """
    result = {"verdict": "unknown", "term_structure": None, "analogs": None, "summary": ""}

    if ticker_data:
        ts = iv_term_structure(ticker_data)
        result["term_structure"] = ts

    if iv_history and median_iv is not None:
        analogs = iv_analogs(ticker, current_iv, median_iv, iv_history)
        result["analogs"] = analogs

    # Synthesize verdict
    ts_verdict = result.get("term_structure", {}).get("verdict", "unknown") if result.get("term_structure") else "unknown"
    an_median = result.get("analogs", {}).get("median_days_to_median") if result.get("analogs") else None

    if ts_verdict == "improving":
        result["verdict"] = "improving"
        result["summary"] = f"Term structure in backwardation — market expects IV decline."
    elif ts_verdict == "worsening":
        result["verdict"] = "worsening"
        result["summary"] = f"Term structure in contango — market expects IV to stay elevated."
    else:
        result["verdict"] = "unchanged"
        result["summary"] = "Term structure flat — no IV relief signal."

    if an_median is not None:
        result["summary"] += f" Historically, {ticker} IV spikes above this level revert to median in ~{an_median} trading days."

    return result
