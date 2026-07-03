#!/usr/bin/env python3
"""
Deep Analysis Tools for Options Position Review (Phases 9, 10, 11).

Computational reference for the options-position-review skill.
All functions assume: risk-free rate = 4.5%, 252 trading days/year, 1 contract = 100 shares.

Usage from a skill session:
    python3 -c "
    import sys; sys.path.insert(0, '/root/.hermes/skills/options-position-review/references')
    from deep_analysis import bs_greeks, risk_matrix, iv_scenarios, iv_outlook
    # ... call functions, print results
    "
"""

import math
from typing import Optional

# ---- Black-Scholes Core ----

R = 0.045  # risk-free rate
TRADING_DAYS = 252


def _norm_cdf(x: float) -> float:
    """Standard normal CDF (Abramowitz & Stegun approximation)."""
    if x < -7.0:
        return 0.0
    if x > 7.0:
        return 1.0
    a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
    p = 0.3275911
    sign = 1.0 if x >= 0 else -1.0
    x_abs = abs(x) / math.sqrt(2.0)
    t = 1.0 / (1.0 + p * x_abs)
    y = 1.0 - ((((a5 * t + a4) * t + a3) * t + a2) * t + a1) * t * math.exp(-x_abs * x_abs)
    return 0.5 * (1.0 + sign * y)


def _norm_pdf(x: float) -> float:
    """Standard normal PDF."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def bs_put(S: float, K: float, T: float, sigma: float, r: float = R) -> float:
    """Black-Scholes put price. S=spot, K=strike, T=years, sigma=decimal."""
    if T <= 0:
        return max(K - S, 0.0)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)


def bs_greeks(S: float, K: float, T: float, sigma: float, r: float = R) -> dict:
    """All five Greeks for a put option. Delta/gamma/theta/vega are per-share (multiply by 100 for contract)."""
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

    delta = -_norm_cdf(-d1)
    gamma = _norm_pdf(d1) / (S * sigma * math.sqrt(T))
    theta_term1 = -(S * _norm_pdf(d1) * sigma) / (2.0 * math.sqrt(T))
    theta_term2 = r * K * math.exp(-r * T) * _norm_cdf(-d2)
    theta = (theta_term1 + theta_term2) / TRADING_DAYS  # per trading day
    vega_per_pct = S * _norm_pdf(d1) * math.sqrt(T) / 100.0  # per 1% IV change
    rho_per_pct = -K * T * math.exp(-r * T) * _norm_cdf(-d2) / 100.0  # per 1% rate change
    price = bs_put(S, K, T, sigma, r)

    return {
        "delta": float(delta),
        "gamma": float(gamma),
        "theta": float(theta),
        "vega": float(vega_per_pct),
        "rho": float(rho_per_pct),
        "price": float(price),
    }


# ---- Phase 9 Analysis Tools ----

def _years(dte: int) -> float:
    return dte / TRADING_DAYS


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
    Phase 9b: P&L grid at various spot prices x DTE checkpoints.
    iv = decimal (e.g. 0.60 for 60%), premium = per-share premium received.
    Returns list of rows: {spot, dte_X: pnl, ...}
    """
    if price_points is None:
        # Default: from strike to spot+20% in 5 increments, plus current spot
        pct_step = 0.05
        points = []
        p = strike
        while p <= spot * 1.2:
            points.append(round(p, 2))
            p += spot * pct_step
        if spot not in points:
            points.append(spot)
        points = sorted(set(points))
        price_points = points

    if dte_points is None:
        dte_points = [dte, max(21, dte - (dte - 21)), max(14, dte - (dte - 14)), max(7, dte - (dte - 7)), 0]

    T_current = _years(dte)
    iv_dec = iv

    rows = []
    for S in price_points:
        row = {"spot": S}
        for t_dte in dte_points:
            T = _years(t_dte)
            price = bs_put(S, strike, T, iv_dec)
            pnl = (premium - price) * 100
            row[f"dte_{t_dte}"] = round(pnl, 0)
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
    Phase 9c: Option price and P&L at different IV levels, spot held constant.
    iv_levels = list of decimal IVs (e.g. [0.40, 0.50, 0.60, 0.80, current_iv])
    """
    if iv_levels is None:
        iv_levels = [0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00, 1.06, 1.10, 1.20]

    T = _years(dte)
    results = []
    for iv in sorted(iv_levels, reverse=True):
        price = bs_put(spot, strike, T, iv)
        pnl = round((premium - price) * 100, 0)
        results.append({"iv": f"{iv*100:.0f}%", "option_price": round(price, 2), "pnl": pnl})
    return results


def one_day_shocks(
    spot: float,
    strike: float,
    dte: int,
    iv: float,
    premium: float,
    shock_pcts: Optional[list] = None,
) -> list[dict]:
    """
    Phase 9d: P&L impact of 1-day price shocks.
    Uses delta + gamma approximation for the move, plus one day of theta.
    """
    if shock_pcts is None:
        shock_pcts = [-5.0, -3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 5.0]

    T = _years(dte)
    g = bs_greeks(spot, strike, T, iv)

    delta = g["delta"]
    gamma = g["gamma"]
    theta = g["theta"]

    results = []
    for pct in shock_pcts:
        new_spot = spot * (1 + pct / 100)
        ds = new_spot - spot
        # Taylor approximation: delta * dS + 0.5 * gamma * dS^2 + theta
        delta_pnl = delta * ds
        gamma_pnl = 0.5 * gamma * ds * ds
        total_approx = (delta_pnl + gamma_pnl) * 100 + theta * 100

        # Compute full BS price for accuracy
        new_price = bs_put(new_spot, strike, T - 1 / TRADING_DAYS, iv)
        current_price = bs_put(spot, strike, T, iv)
        exact_pnl = (current_price - new_price) * 100

        results.append({
            "move": f"{pct:+.0f}%",
            "spot": round(new_spot, 2),
            "pnl_change": round(exact_pnl, 0),
        })

    return results


def gamma_profile(
    spot: float,
    strike: float,
    dte: int,
    iv: float,
    price_points: Optional[list] = None,
) -> list[dict]:
    """
    Phase 9e: Gamma at different spot levels.
    """
    if price_points is None:
        # Range from strike to spot+30%, in 8 steps
        step = (spot * 1.3 - strike) / 7
        price_points = [round(strike + i * step, 2) for i in range(8)]

    T = _years(dte)
    results = []
    for S in price_points:
        g = bs_greeks(S, strike, T, iv)
        results.append({
            "spot": S,
            "delta": round(g["delta"], 4),
            "gamma": round(g["gamma"], 6),
            "dollar_per_1": round(g["gamma"] * 100, 2),
        })
    return results


def breakeven_analysis(
    spot: float,
    strike: float,
    dte: int,
    iv: float,
    premium: float,
) -> dict:
    """
    Phase 9f: Find breakeven spot (at current IV) and breakeven IV (at current spot).
    Returns dict with paths.
    """
    T = _years(dte)

    # Breakeven spot at current IV (binary search)
    lo, hi = strike * 0.5, spot * 1.5
    for _ in range(40):
        mid = (lo + hi) / 2
        price = bs_put(mid, strike, T, iv)
        if price < premium:
            lo = mid
        else:
            hi = mid
    be_spot = round((lo + hi) / 2, 1)

    # Breakeven IV at current spot (binary search)
    lo, hi = 0.01, 3.0
    for _ in range(40):
        mid = (lo + hi) / 2
        price = bs_put(spot, strike, T, mid)
        if price < premium:
            lo = mid
        else:
            hi = mid
    be_iv = round((lo + hi) / 2 * 100, 1)

    # Realistic paths: 3 combinations
    paths = []
    # Path 1: IV drops 30%, spot up 10%
    iv1 = iv * 0.7
    spot1 = spot * 1.10
    paths.append({
        "label": f"IV {iv1*100:.0f}%, spot ${spot1:.0f}",
        "option_price": round(bs_put(spot1, strike, T, iv1), 2),
        "pnl": round((premium - bs_put(spot1, strike, T, iv1)) * 100, 0),
    })
    # Path 2: IV drops 20%, spot flat
    iv2 = iv * 0.8
    paths.append({
        "label": f"IV {iv2*100:.0f}%, spot ${spot:.0f}",
        "option_price": round(bs_put(spot, strike, T, iv2), 2),
        "pnl": round((premium - bs_put(spot, strike, T, iv2)) * 100, 0),
    })
    # Path 3: IV drops 40%, spot up 5%
    iv3 = iv * 0.6
    spot3 = spot * 1.05
    paths.append({
        "label": f"IV {iv3*100:.0f}%, spot ${spot3:.0f}",
        "option_price": round(bs_put(spot3, strike, T, iv3), 2),
        "pnl": round((premium - bs_put(spot3, strike, T, iv3)) * 100, 0),
    })

    return {
        "be_spot": be_spot,
        "be_iv": be_iv,
        "paths": paths,
    }


def prob_otm(spot: float, strike: float, dte: int, hv: float) -> float:
    """
    Simple probability of expiring OTM using normal approximation with HV.
    hv = decimal (e.g. 0.50 for 50%).
    """
    T = _years(dte)
    sigma_T = hv * math.sqrt(T)
    # z-score: how many sigma above strike is current spot
    z = math.log(spot / strike) / sigma_T if sigma_T > 0 else 10.0
    prob = _norm_cdf(z)
    return round(prob * 100, 1)


# ---- Phase 10 Analysis Tools ----

def expected_vs_actual(spot: float, daily_returns: list[float], atm_straddle_price: float) -> dict:
    """
    Phase 10b: Compare expected daily move to actual moves.
    daily_returns = list of daily pct changes (decimal, e.g. 0.02 for +2%)
    atm_straddle_price = ATM call + ATM put price at nearest expiry
    Returns dict with expected_move_pct, actual moves, and verdict.
    """
    expected_move_pct = (atm_straddle_price / spot) * 100

    actual_moves = [abs(r * 100) for r in daily_returns[-10:]]
    over_count = sum(1 for m in actual_moves if m > expected_move_pct)

    return {
        "expected_move_pct": round(expected_move_pct, 2),
        "actual_moves": [round(m, 2) for m in actual_moves],
        "over_count": over_count,
        "total_days": len(actual_moves),
        "verdict": "market underpricing risk" if over_count >= len(actual_moves) / 2 else "market pricing adequate risk",
    }


def correlation_check(prices_a: list, prices_b: list) -> float:
    """
    Phase 10d: Compute correlation between two price series.
    Uses daily log returns over the common window.
    """
    import math as _math
    ret_a = [_math.log(prices_a[i] / prices_a[i - 1]) for i in range(1, len(prices_a))]
    ret_b = [_math.log(prices_b[i] / prices_b[i - 1]) for i in range(1, len(prices_b))]
    n = min(len(ret_a), len(ret_b))
    ret_a = ret_a[-n:]
    ret_b = ret_b[-n:]

    mean_a = sum(ret_a) / n
    mean_b = sum(ret_b) / n

    cov = sum((a - mean_a) * (b - mean_b) for a, b in zip(ret_a, ret_b)) / (n - 1)
    std_a = (sum((a - mean_a) ** 2 for a in ret_a) / (n - 1)) ** 0.5
    std_b = (sum((b - mean_b) ** 2 for b in ret_b) / (n - 1)) ** 0.5

    if std_a == 0 or std_b == 0:
        return 0.0
    return round(cov / (std_a * std_b), 3)


# ---- Phase 11: IV Outlook ----

def iv_term_structure(ticker: str, strike: float) -> dict:
    """
    Phase 11a: Fetch IV for the given strike across all available expiries.
    Returns term structure: {expiry: {dte, iv}, ...} plus curve shape verdict.
    Uses yfinance option chains.
    """
    import yfinance as yf
    from datetime import datetime, timezone

    t = yf.Ticker(ticker)
    expiries = t.options

    now = datetime.now(timezone.utc)
    data = {}

    for exp_str in expiries:
        exp_date = datetime.strptime(exp_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        dte = (exp_date - now).days
        if dte < 1:
            continue

        try:
            chain = t.option_chain(exp_str)
            # Find closest put to target strike
            target = chain.puts[chain.puts["strike"] == strike]
            if target.empty:
                # Try nearest strike
                available = chain.puts["strike"].unique()
                nearest = min(available, key=lambda x: abs(x - strike))
                target = chain.puts[chain.puts["strike"] == nearest]

            iv = float(target["impliedVolatility"].iloc[0])
            data[exp_str] = {"dte": dte, "iv": round(iv * 100, 1), "strike_used": int(target["strike"].iloc[0])}
        except Exception:
            continue

    if not data:
        return {"error": "no option chain data available", "curve_shape": "unknown"}

    # Determine curve shape by comparing nearest vs furthest
    sorted_exp = sorted(data.items(), key=lambda x: x[1]["dte"])
    nearest_iv = sorted_exp[0][1]["iv"]
    furthest_iv = sorted_exp[-1][1]["iv"]

    if nearest_iv > furthest_iv + 5:
        shape = "backwardation"
        outlook = "improving"
        interpretation = "Market expects IV to decline. Recovery engine active."
    elif furthest_iv > nearest_iv + 5:
        shape = "contango"
        outlook = "worsening"
        interpretation = "Market expects IV to rise or stay elevated. No relief priced in."
    else:
        shape = "flat"
        outlook = "stable"
        interpretation = "No strong directional signal. IV likely sticky at current levels."

    return {
        "curve": data,
        "curve_shape": shape,
        "outlook": outlook,
        "interpretation": interpretation,
    }


def iv_analogs(
    ticker: str,
    current_iv: float,
    lookback_years: float = 2.0,
) -> dict:
    """
    Phase 11b: Find historical periods when IV reached current levels.
    current_iv = decimal (e.g. 1.10 for 110%).
    Returns analog episodes with recovery timelines.

    Uses ATM IV from yfinance as a proxy. When options data is unavailable,
    falls back to HV as a rough analog.
    """
    import yfinance as yf
    import numpy as np

    t = yf.Ticker(ticker)
    hist = t.history(period=f"{int(lookback_years * 365)}d")

    if hist.empty or len(hist) < 60:
        return {"error": "insufficient price history", "episodes": [], "median_days_to_revert": None}

    closes = hist["Close"].values
    # Compute rolling 30-day HV as IV proxy
    log_rets = np.diff(np.log(closes))
    hv_series = []

    for i in range(len(log_rets)):
        if i < 20:
            hv_series.append(np.nan)
            continue
        window = log_rets[max(0, i - 21):i + 1]
        if len(window) < 5:
            hv_series.append(np.nan)
            continue
        p5, p95 = np.percentile(window, [5, 95])
        wins = np.clip(window, p5, p95)
        hv_series.append(float(np.std(wins) * np.sqrt(252)))

    hv_array = np.array(hv_series)
    median_hv = np.nanmedian(hv_array)

    # Find episodes where HV crossed above current_iv threshold
    threshold = current_iv * 0.90  # 90% of current IV to find comparable spikes
    above = hv_array >= threshold

    episodes = []
    in_episode = False
    episode_start = None
    peak_hv = 0

    for i, (is_above, hv_val) in enumerate(zip(above, hv_array)):
        if is_above and not in_episode:
            in_episode = True
            episode_start = i
            peak_hv = hv_val
        elif is_above and in_episode:
            if not np.isnan(hv_val) and hv_val > peak_hv:
                peak_hv = hv_val
        elif not is_above and in_episode:
            in_episode = False
            if episode_start is not None and not np.isnan(peak_hv):
                # Count days to revert below median
                days_to_median = None
                for j in range(i, min(i + 60, len(hv_array))):
                    if not np.isnan(hv_array[j]) and hv_array[j] <= median_hv:
                        days_to_median = j - i
                        break

                # Count days to 50% retracement from peak to median
                half_target = peak_hv - (peak_hv - median_hv) * 0.5
                days_to_half = None
                for j in range(i, min(i + 60, len(hv_array))):
                    if not np.isnan(hv_array[j]) and hv_array[j] <= half_target:
                        days_to_half = j - i
                        break

                # Only count if peak was meaningful
                if peak_hv >= threshold:
                    episodes.append({
                        "date": str(hist.index[episode_start].date()),
                        "peak_hv": round(peak_hv * 100, 1),
                        "days_to_median": days_to_median,
                        "days_to_half": days_to_half,
                    })

    if not episodes:
        return {
            "error": None,
            "episodes": [],
            "median_days_to_revert": None,
            "message": f"No historical episodes found where HV exceeded {threshold*100:.0f}%. This IV level is rare for {ticker}.",
        }

    # Compute medians
    days_to_median_vals = [e["days_to_median"] for e in episodes if e["days_to_median"] is not None]
    days_to_half_vals = [e["days_to_half"] for e in episodes if e["days_to_half"] is not None]

    median_revert = int(np.median(days_to_median_vals)) if days_to_median_vals else None
    median_half = int(np.median(days_to_half_vals)) if days_to_half_vals else None

    return {
        "error": None,
        "median_hv": round(median_hv * 100, 1),
        "current_iv": round(current_iv * 100, 1),
        "episodes": episodes,
        "median_days_to_revert": median_revert,
        "median_days_to_half": median_half,
    }


def iv_outlook(ticker: str, strike: float, current_iv: float) -> dict:
    """
    Phase 11: Combined IV outlook verdict.
    current_iv = decimal (e.g. 1.10 for 110%).
    Returns term structure verdict + historical analogs synthesized into one outlook.
    """
    term = iv_term_structure(ticker, strike)
    analogs = iv_analogs(ticker, current_iv)

    shape = term.get("curve_shape", "unknown")
    market_outlook = term.get("outlook", "unknown")
    interpretation = term.get("interpretation", "")

    median_revert = analogs.get("median_days_to_revert")
    median_half = analogs.get("median_days_to_half")
    episodes = analogs.get("episodes", [])

    # Synthesize
    if market_outlook == "improving":
        if median_revert is not None and median_revert <= 10:
            verdict = f"improving within {median_revert} trading days"
            confidence = "high"
        elif median_revert is not None:
            verdict = f"improving within {median_revert} trading days"
            confidence = "medium"
        else:
            verdict = "improving (term structure signal, no historical analogs)"
            confidence = "medium"
    elif market_outlook == "worsening":
        verdict = "worsening or persistently elevated"
        confidence = "medium"
    else:
        if median_revert is not None and median_revert <= 10:
            verdict = f"stable-to-improving within {median_revert} days"
            confidence = "medium"
        else:
            verdict = "stable, no strong signal"
            confidence = "low"

    return {
        "verdict": f"IV outlook: {verdict} (confidence: {confidence})",
        "term_structure": {
            "curve_shape": shape,
            "market_outlook": market_outlook,
            "interpretation": interpretation,
            "curve": term.get("curve", {}),
        },
        "historical_analogs": {
            "episodes": episodes,
            "median_days_to_revert": median_revert,
            "median_days_to_half_retrace": median_half,
            "median_hv": analogs.get("median_hv"),
        },
    }
