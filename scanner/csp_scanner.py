#!/usr/bin/env python3
"""
CSP Entry Scanner — 6-Gate Pre-Flight Checklist

Usage:
    python3 csp_scanner.py --tickers AAPL MSFT GOOGL
    python3 csp_scanner.py --universe
    python3 csp_scanner.py --file data/csp_candidates.json
    python3 csp_scanner.py --tickers MU TSM --format md

Gates:
    1. IVR >= 50% (Tastytrade)
    2. IV > HV (Tastytrade, precomputed difference)
    3. Price > 200MA (yfinance) — tiered with 50MA
    4. Delta <= 0.10 strike exists (yfinance + Black-Scholes)
    5. Premium display (absolute + return on notional)
    6. IV direction (soft context)
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal

import numpy as np
from scipy.stats import norm

ENV_CREDS = os.environ.get("TASTYTRADE_CREDS")
if ENV_CREDS:
    CLIENT_SECRET, REFRESH_TOKEN = ENV_CREDS.split(":", 1)
else:
    CLIENT_SECRET = os.environ.get("TASTYTRADE_CLIENT_SECRET", "")
    REFRESH_TOKEN = os.environ.get("TASTYTRADE_REFRESH_TOKEN", "")

UNIVERSE_FILE = os.environ.get("CSP_UNIVERSE_FILE", "data/csp_universe.json")
RISK_FREE_RATE = 0.05  # 5% fixed (approximate T-bill rate)


# --- Tastytrade helpers -----------------------------------------------------------

def load_tastytrade_creds():
    if CLIENT_SECRET and REFRESH_TOKEN:
        return {"cs": CLIENT_SECRET, "rt": REFRESH_TOKEN}
    # Fallback: read from creds file (legacy)
    creds_file = os.environ.get("TASTYTRADE_CREDS_FILE", "")
    if not creds_file or not os.path.exists(creds_file):
        sys.exit("FATAL: Set TASTYTRADE_CLIENT_SECRET + TASTYTRADE_REFRESH_TOKEN, "
                 "or TASTYTRADE_CREDS=cs:rt, or TASTYTRADE_CREDS_FILE path")
    creds = {}
    with open(creds_file) as f:
        for line in f:
            line = line.strip()
            if line.startswith("TASTYTRADE_CLIENT_SECRET="):
                creds["cs"] = line.split("=", 1)[1]
            elif line.startswith("TASTYTRADE_REFRESH_TOKEN="):
                creds["rt"] = line.split("=", 1)[1]
    return creds


async def fetch_tastytrade_metrics(symbols):
    """Fetch MarketMetricInfo for a list of symbols. Returns list of dicts."""
    from tastytrade import Session
    from tastytrade import metrics as tt_metrics

    creds = load_tastytrade_creds()
    session = Session(creds["cs"], creds["rt"])
    try:
        data = await tt_metrics.get_market_metrics(session, symbols)
        results = []
        for item in data:
            results.append({
                "symbol": item.symbol,
                "ivr": float(item.implied_volatility_index_rank) if item.implied_volatility_index_rank else None,
                "iv_percentile": float(item.implied_volatility_percentile) if item.implied_volatility_percentile else None,
                "iv_30d": float(item.implied_volatility_30_day) if item.implied_volatility_30_day else None,
                "hv_30d": float(item.historical_volatility_30_day) if item.historical_volatility_30_day else None,
                "iv_hv_diff": float(item.iv_hv_30_day_difference) if item.iv_hv_30_day_difference else None,
                "iv_5d_change": float(item.implied_volatility_index_5_day_change) if item.implied_volatility_index_5_day_change else None,
                "liquidity_rating": item.liquidity_rating,
                "beta": float(item.beta) if item.beta else None,
                "market_cap": float(item.market_cap) if item.market_cap else None,
            })
        return results
    finally:
        try:
            await session._client.aclose()
        except Exception:
            pass


# --- Black-Scholes delta ---------------------------------------------------------

def calc_put_delta(S, K, sigma, T, r=RISK_FREE_RATE):
    """Black-Scholes delta for a European put."""
    if sigma <= 0 or T <= 0:
        return None
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    return -norm.cdf(-d1)


def find_target_strike(puts_df, S, T):
    """
    Given a DataFrame of put options, find the strike closest to ATM (highest strike
    still OTM) with delta <= 0.10 and premium > minimum.

    Strategy: filter OTM puts only (strike <= S), sort by strike descending (closest to
    ATM first), walk down until delta <= 0.10 AND premium > $0.05 bid.
    """
    puts = puts_df.copy()
    puts = puts[puts["strike"] <= S]
    puts = puts.sort_values("strike", ascending=False)

    for _, row in puts.iterrows():
        sigma = row.get("impliedVolatility", None)
        if sigma is None or sigma <= 0:
            continue
        delta = calc_put_delta(S, row["strike"], sigma, T)
        if delta is None:
            continue

        bid = row.get("bid", 0) or 0
        if abs(delta) <= 0.10 and bid > 0.05:
            ask = row.get("ask", 0) or 0
            mid = (bid + ask) / 2 if bid and ask else (row.get("lastPrice", 0) or 0)
            return {
                "strike": float(row["strike"]),
                "delta": round(delta, 4),
                "bid": float(bid),
                "ask": float(ask),
                "mid": float(mid),
                "iv": float(sigma),
                "open_interest": int(row.get("openInterest", 0) or 0),
            }
    return None


# --- yfinance helpers ------------------------------------------------------------

def fetch_price_and_mas(symbol):
    """Return (price, ma50, ma200) or (None, None, None) on failure."""
    import yfinance as yf

    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        price = info.get("regularMarketPrice") or info.get("currentPrice")
        if not price:
            hist = ticker.history(period="5d")
            if not hist.empty:
                price = hist["Close"].iloc[-1]

        ma50 = info.get("fiftyDayAverage")
        ma200 = info.get("twoHundredDayAverage")

        if not ma50 or not ma200:
            hist = ticker.history(period="1y")
            if not hist.empty and len(hist) >= 50:
                ma50 = float(hist["Close"].rolling(50).mean().iloc[-1]) if not ma50 else ma50
            if not hist.empty and len(hist) >= 200:
                ma200 = float(hist["Close"].rolling(200).mean().iloc[-1]) if not ma200 else ma200

        return price, ma50, ma200
    except Exception:
        return None, None, None


def fetch_option_chain(symbol, target_dte=45):
    """Get the option chain closest to target DTE. Returns (expiry_date, dte_days, puts_df) or None."""
    import yfinance as yf

    try:
        ticker = yf.Ticker(symbol)
        expirations = ticker.options
        if not expirations:
            return None

        today = date.today()
        best_exp = None
        best_diff = 999

        for exp_str in expirations:
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
            dte = (exp_date - today).days
            if 30 <= dte <= 55:
                diff = abs(dte - target_dte)
                if diff < best_diff:
                    best_diff = diff
                    best_exp = (exp_str, dte, exp_date)

        if not best_exp:
            return None

        exp_str, dte, exp_date = best_exp
        chain = ticker.option_chain(exp_str)
        return exp_str, dte, chain.puts
    except Exception:
        return None


# --- Tier helper -----------------------------------------------------------------

def ma_tier(price, ma50, ma200):
    """Return ('green', 'amber', 'red') based on MA relationship."""
    if not price or not ma200:
        return "unknown"
    if price < ma200:
        return "red"
    if not ma50:
        return "amber"
    if price > ma50:
        return "green"
    return "amber"


def iv_direction_label(change):
    """Human label for 5-day IV change."""
    if change is None:
        return "?"
    if change < -0.005:
        return f"\u2193{abs(change)*100:.1f}%"
    elif change > 0.005:
        return f"\u2191{change*100:.1f}%"
    else:
        return "\u2192"


# --- Main scan -------------------------------------------------------------------

async def scan_tickers(symbols):
    """Run all 6 gates on a list of tickers. Returns list of result dicts."""
    print(f"[1/5] Fetching Tastytrade metrics for {len(symbols)} tickers...", file=sys.stderr)
    tastydata = await fetch_tastytrade_metrics(symbols)
    tt_lookup = {d["symbol"]: d for d in tastydata}

    results = []

    for sym in symbols:
        tt = tt_lookup.get(sym)

        # Liquidity gate
        if tt and tt["liquidity_rating"] is not None and tt["liquidity_rating"] < 2:
            results.append({"symbol": sym, "status": "SKIP", "reason": f"Liquidity={tt['liquidity_rating']}"})
            continue

        # Gate 1: IVR
        if not tt or tt["ivr"] is None or tt["ivr"] < 0.50:
            reason = "NO_DATA" if not tt else f"IVR={tt['ivr']:.0%}"
            results.append({"symbol": sym, "status": "FAIL_G1", "reason": reason})
            continue

        # Gate 2: IV/HV
        if tt["iv_hv_diff"] is None or tt["iv_hv_diff"] <= 0:
            reason = f"IV-HV={tt['iv_hv_diff']:.1f}" if tt["iv_hv_diff"] is not None else "NO_DATA"
            results.append({"symbol": sym, "status": "FAIL_G2", "reason": reason})
            continue

        print(f"[2/5] {sym}: passed G1+G2 (IVR={tt['ivr']:.0%}, IV-HV={tt['iv_hv_diff']:.1f})", file=sys.stderr)

        price, ma50, ma200 = fetch_price_and_mas(sym)
        if not price:
            results.append({"symbol": sym, "status": "FAIL", "reason": "yfinance price fetch failed"})
            continue

        # Gate 3: MAs
        tier = ma_tier(price, ma50, ma200)
        if tier == "red":
            results.append({
                "symbol": sym, "status": "FAIL_G3", "reason": f"${price:.2f} < 200MA ${ma200:.2f}",
                "ivr": tt["ivr"], "iv_hv_diff": tt["iv_hv_diff"], "price": price, "ma_tier": tier,
            })
            continue

        # Gate 4: delta <= 0.10
        chain_data = fetch_option_chain(sym, target_dte=45)
        if not chain_data:
            results.append({
                "symbol": sym, "status": "FAIL_G4", "reason": "No option chain in 30-55d range",
                "ivr": tt["ivr"], "iv_hv_diff": tt["iv_hv_diff"], "price": price, "ma_tier": tier,
            })
            continue

        exp_str, dte, puts_df = chain_data
        T = dte / 365.0
        strike_data = find_target_strike(puts_df, price, T)

        if not strike_data:
            results.append({
                "symbol": sym, "status": "FAIL_G4", "reason": f"No put with delta <=0.10 at {dte}d expiry",
                "ivr": tt["ivr"], "iv_hv_diff": tt["iv_hv_diff"], "price": price, "ma_tier": tier,
            })
            continue

        # Gate 5: premium
        premium_abs = strike_data["mid"] * 100
        premium_pct = (strike_data["mid"] / strike_data["strike"]) * 100

        if premium_abs < 75:
            status = "LOW_PREM"
        else:
            status = "READY" if tt["iv_5d_change"] is not None and tt["iv_5d_change"] <= 0 else "WATCH"

        if tier == "amber" and status in ("READY", "WATCH"):
            status = f"{status}_AMBER"

        results.append({
            "symbol": sym,
            "status": status,
            "ivr": tt["ivr"],
            "iv_percentile": tt["iv_percentile"],
            "iv_hv_diff": tt["iv_hv_diff"],
            "iv_30d": tt["iv_30d"],
            "hv_30d": tt["hv_30d"],
            "iv_5d_change": tt["iv_5d_change"],
            "iv_direction": iv_direction_label(tt["iv_5d_change"]),
            "liquidity": tt["liquidity_rating"],
            "beta": tt["beta"],
            "price": round(price, 2),
            "ma50": round(ma50, 2) if ma50 else None,
            "ma200": round(ma200, 2) if ma200 else None,
            "ma_tier": tier,
            "strike": strike_data["strike"],
            "delta": strike_data["delta"],
            "premium_bid": round(strike_data["bid"], 2),
            "premium_mid": round(strike_data["mid"], 2),
            "premium_abs": round(premium_abs, 0),
            "premium_pct": round(premium_pct, 3),
            "dte": dte,
            "expiry": exp_str,
            "oi": strike_data["open_interest"],
            "put_iv": round(strike_data["iv"], 4),
        })

    return results


# --- Output formatters -----------------------------------------------------------

def format_markdown(results):
    """Format results as a markdown table with grouping."""
    lines = []
    lines.append("## CSP Entry Scanner")
    lines.append(f"_{len(results)} tickers scanned_")
    lines.append("")

    actionable = [r for r in results if r["status"] in ("READY", "WATCH", "READY_AMBER", "WATCH_AMBER", "LOW_PREM")]
    if actionable:
        lines.append("### Actionable")
        lines.append("")
        lines.append("| Ticker | Price | Strike (delta<=0.10) | Prem | Prem% | DTE | IVR | IV/HV | IVd5d | MA | OI | Beta | Status |")
        lines.append("|--------|-------|----------------------|------|-------|-----|-----|-------|-------|----|----|------|--------|")
        for r in sorted(actionable, key=lambda x: x["status"]):
            ma_icon = {"green": "G", "amber": "A", "red": "R", "unknown": "?"}.get(r["ma_tier"], "?")
            iv_dir = r["iv_direction"]
            oi = r.get("oi", 0) or 0
            beta = f"{r['beta']:.1f}" if r["beta"] else "?"
            lines.append(
                f"| {r['symbol']} | ${r['price']:.2f} | {r['strike']}P | ${r['premium_abs']:.0f} | "
                f"{r['premium_pct']:.2f}% | {r['dte']}d | {r['ivr']:.0%} | "
                f"{r['iv_hv_diff']:+.1f} | {iv_dir} | {ma_icon} | {oi} | {beta} | "
                f"**{r['status']}** |"
            )
        lines.append("")

    failed = [r for r in results if r["status"].startswith("FAIL_") or r["status"] in ("SKIP", "FAIL", "NO_DATA")]
    if failed:
        lines.append("### Skipped / Failed")
        lines.append("")
        lines.append("| Ticker | Gate | Reason |")
        lines.append("|--------|------|--------|")
        for r in sorted(failed, key=lambda x: x["status"]):
            lines.append(f"| {r['symbol']} | {r['status']} | {r.get('reason', '?')} |")
        lines.append("")

    lines.append(
        "**Status**: READY=all gates pass+IV declining, WATCH=all gates pass+IV rising, "
        "_AMBER=price below 50MA, LOW_PREM=<$75, "
        "FAIL_G1/G2/G3/G4=which gate failed, SKIP=liquidity/no data"
    )
    lines.append("")
    lines.append("DTE strategy: 45 DTE entry -> 50% profit or 21 DTE exit (whichever first)")
    return "\n".join(lines)


def format_json(results):
    return json.dumps(results, indent=2, default=str)


# --- CLI -------------------------------------------------------------------------

def load_universe(path):
    with open(path) as f:
        data = json.load(f)
    return data.get("tickers", [])


async def main():
    parser = argparse.ArgumentParser(description="CSP Entry Scanner")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--tickers", nargs="+", help="List of tickers")
    group.add_argument("--universe", action="store_true", help="Read from csp_universe.json")
    group.add_argument("--file", help="Read tickers from a JSON file")
    parser.add_argument("--format", choices=["md", "json", "both"], default="md")
    args = parser.parse_args()

    if args.universe:
        symbols = load_universe(UNIVERSE_FILE)
    elif args.file:
        symbols = load_universe(args.file)
    else:
        symbols = args.tickers

    if not symbols:
        print("No tickers provided.", file=sys.stderr)
        sys.exit(1)

    results = await scan_tickers(symbols)

    if args.format == "md":
        print(format_markdown(results))
    elif args.format == "json":
        print(format_json(results))
    else:
        print(format_markdown(results))
        print("")
        print(format_json(results))


if __name__ == "__main__":
    asyncio.run(main())
