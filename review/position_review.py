#!/usr/bin/env python3
"""
Position Review with Greeks + Trigger Analysis + GEX.
Reads Trade Ledger from Google Sheets. Fetches spot, options, IV metrics, Greeks.
Prints JSON output for downstream formatting.
"""
import asyncio, os, sys, json, tempfile
from datetime import date, timedelta
import math
import numpy as np
import yfinance as yf
from tastytrade import Session, metrics as tt_metrics
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

ENV_CS = os.environ.get("TASTYTRADE_CLIENT_SECRET", "")
ENV_RT = os.environ.get("TASTYTRADE_REFRESH_TOKEN", "")
ENV_CREDS = os.environ.get("TASTYTRADE_CREDS", "")
SHEET_ID = os.environ.get("TRADE_LEDGER_SHEET_ID", "")
GOOGLE_TOKEN = os.environ.get("GOOGLE_TOKEN_FILE", "google_token.json")
ACCOUNT_SIZE = float(os.environ.get("ACCOUNT_SIZE", 0))  # 0 = no sizing data available

# ── Risk thresholds ─────────────────────────────────────────────
CUT_LOSS_MULTIPLE = 3.0     # Escalation trigger: mid ≥ credit × 3 (= −200% P&L). Diagnose, don't auto-exit.
CONFIRMED_LOSS_MULTIPLE = 1.5  # Loss must be ≥ 1.5× for delta exit to fire (market confirms the risk)
WATCH_RESOLUTION_MULTIPLE = 2.0  # Clear 3× YELLOW only when mid drops below 2.0× credit (not 2.99×)
DELTA_HARD_EXIT   = 0.35    # Put delta ≥ 0.35 → hard exit ONLY when loss ≥ 1.5×; else YELLOW
DELTA_SOFT_WATCH  = 0.25    # Put delta ≥ 0.25 → material risk ONLY when loss ≥ 1.5×; else benign
DELTA_LOW_EXPOSURE = 0.15    # Put delta < 0.15  → low current assignment risk
MA50_PERSISTENCE_DAYS = 2     # Consecutive days below MA50 before ORANGE triggers
# Delta embeds moneyness, time, AND IV in one number.
# A stock 15% above strike at 30% IV has a very different delta than
# the same stock at 121% IV.  Distance alone cannot see this.

# Shared Black-Scholes from repo-root pricing.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pricing import bs_put_greeks, bs_put, calc_put_delta, R as RISK_FREE_RATE

# HV utilities for baseline fallback
sys.path.insert(0, os.path.expanduser("~/.hermes/scripts"))
try:
    from hv_utils import compute_hv_window
except ImportError:
    compute_hv_window = None

# ── Recovery diagnostic constants ──────────────────────────────────
RECOVERY_HORIZON_TRADING_DAYS = 2  # default horizon for recovery feasibility
IV30D_SNAPSHOT_FILE = os.path.expanduser("~/.hermes/cache/iv30d_snapshots.json")
IV30D_MIN_SNAPSHOTS = 30  # minimum snapshots before baseline is reliable (~6 weeks)


def bs_greeks(spot, strike, dte, iv, rate=RISK_FREE_RATE):
    """Compatibility wrapper around pricing.bs_put_greeks.
    Returns dict matching old interface: delta, gamma, vega, theta, iv_absolute.
    Accepts DTE in calendar days (converts to years internally)."""
    T = max(dte / 365.0, 1 / 365.0)
    g = bs_put_greeks(spot, strike, T, iv, rate)
    return {
        'delta': round(g['delta'], 4),
        'gamma': round(g['gamma'], 4),
        'vega': round(g['vega'], 2),
        'theta': round(g['theta'], 2),
        'iv_absolute': round(iv * 100, 1),
    }


EQ = "="

def load_tt_creds():
    if ENV_CREDS:
        cs, rt = ENV_CREDS.split(":", 1)
        return {"client_secret": cs, "refresh_token": rt}
    if ENV_CS and ENV_RT:
        return {"client_secret": ENV_CS, "refresh_token": ENV_RT}
    creds_file = os.environ.get("TASTYTRADE_CREDS_FILE", "")
    if creds_file and os.path.exists(creds_file):
        d = {}
        with open(creds_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"TASTYTRADE_CLIENT_SECRET{EQ}"):
                    d["client_secret"] = line.split(EQ, 1)[1]
                elif line.startswith(f"TASTYTRADE_REFRESH_TOKEN{EQ}"):
                    d["refresh_token"] = line.split(EQ, 1)[1]
        return d
    sys.exit("FATAL: Tastytrade credentials not configured")


def load_positions():
    if not SHEET_ID:
        sys.exit("FATAL: TRADE_LEDGER_SHEET_ID not set")
    creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN)
    svc = build("sheets", "v4", credentials=creds)
    result = svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range="Sheet1!A:H"
    ).execute()
    rows = result.get("values", [])
    if len(rows) < 2:
        return []
    headers = [h.lower().replace(" ", "_") for h in rows[0]]
    positions = []
    for row in rows[1:]:
        if not row or not row[0] or not row[0].strip():
            continue
        pos = {}
        for i, h in enumerate(headers):
            val = row[i].strip() if i < len(row) and row[i] else ""
            if h == "strike" and val:
                val = float(val)
            elif h == "quantity" and val:
                val = int(val)
            elif h == "credit_received" and val:
                val = float(val)
            pos[h] = val
        if pos.get("symbol") and pos.get("strike") and pos.get("expiry"):
            positions.append(pos)
    return positions


async def get_iv_metrics(session, symbols):
    try:
        data = await tt_metrics.get_market_metrics(session, symbols)
        result = {}
        for item in data:
            try:
                result[item.symbol] = {
                    "iv_rank": float(item.implied_volatility_index_rank) if item.implied_volatility_index_rank is not None else None,
                    "iv_percentile": float(item.implied_volatility_percentile) if item.implied_volatility_percentile is not None else None,
                    "iv_30d": float(item.implied_volatility_30_day) if item.implied_volatility_30_day is not None else None,
                    "hv_30d": float(item.historical_volatility_30_day) if item.historical_volatility_30_day is not None else None,
                }
            except Exception:
                pass
        return result
    except Exception as e:
        print(f"WARNING: Tastytrade metrics: {e}", file=sys.stderr)
        return {}


def get_technicals_and_options(symbols, positions):
    """Fetch spot, 50d MA, and option chain IV in one pass."""
    today = date.today()
    tickers = yf.Tickers(" ".join(symbols))
    technicals = {}
    option_data = {}

    for sym in symbols:
        try:
            t = tickers.tickers[sym]
            info = t.fast_info
            price = info.get("lastPrice") or info.get("regularMarketPreviousClose")
            hist = t.history(period="3mo")
            ma50 = float(hist["Close"].tail(50).mean()) if len(hist) >= 50 else None
            technicals[sym] = {
                "price": float(price) if price else None,
                "ma50": round(ma50, 2) if ma50 else None,
            }
        except Exception:
            technicals[sym] = {"price": None, "ma50": None}

    for pos in positions:
        sym = pos["symbol"]
        strike = pos["strike"]
        try:
            exp_str = pos["expiry"]
            exp_date = date.fromisoformat(exp_str)
            dte = (exp_date - today).days
            t = tickers.tickers[sym]
            chain = t.option_chain(exp_str)
            row = chain.puts[chain.puts["strike"] == float(strike)]
            if row.empty:
                continue
            bid = float(row["bid"].values[0])
            ask = float(row["ask"].values[0])
            last = float(row["lastPrice"].values[0])
            mid = (bid + ask) / 2 if bid and ask else last
            iv_abs = float(row["impliedVolatility"].values[0])
            spot = technicals.get(sym, {}).get("price", 0) or mid
            quote_valid, quote_reason, quote_warnings = validate_quote(bid, ask, mid, dte)
            greeks = bs_greeks(spot, strike, dte, iv_abs) if spot and dte > 0 and quote_valid else {}

            option_data[f"{sym}_{strike}"] = {
                "bid": bid, "ask": ask, "last": last, "mid": mid,
                "iv_absolute": round(iv_abs * 100, 1),
                "dte": dte,
                "quote_valid": quote_valid,
                "quote_reason": quote_reason,
                "quote_warnings": quote_warnings,
                **greeks
            }
        except Exception:
            pass

    return technicals, option_data


def _bs_gamma(spot, strike, T, iv):
    """Gamma for GEX computation. Delegates to pricing module."""
    if T < 1/365.0 or iv < 0.01 or spot <= 0 or strike <= 0:
        return 0.0
    try:
        g = bs_put_greeks(spot, strike, T, iv, RISK_FREE_RATE)
        return g['gamma']
    except (ValueError, ZeroDivisionError):
        return 0.0


async def get_gex_data(symbol="SPY"):
    """Compute SPY GEX from yfinance open interest. Self-computed, zero cost."""
    try:
        import yfinance as yf
        spy = yf.Ticker("SPY")
        spot = spy.fast_info.get("lastPrice") or spy.fast_info.get("regularMarketPreviousClose") or 0
        if not spot:
            return {"available": False, "reason": "could not get SPY spot"}

        today = date.today()
        all_exps = spy.options
        near_exps = [e for e in all_exps if 1 <= (date.fromisoformat(e) - today).days <= 45]

        gex_per_strike = {}
        for exp_str in near_exps:
            try:
                chain = spy.option_chain(exp_str)
                exp_date = date.fromisoformat(exp_str)
                T = (exp_date - today).days / 365.0

                for _, row in chain.calls.iterrows():
                    strike = float(row['strike'])
                    oi = row['openInterest']
                    iv = row['impliedVolatility']
                    if not oi or not iv or oi <= 0 or iv <= 0 or math.isnan(oi) or math.isnan(iv):
                        continue
                    gamma = _bs_gamma(spot, strike, T, iv)
                    if math.isnan(gamma) or math.isinf(gamma):
                        continue
                    gex = gamma * oi * spot * 100
                    gex_per_strike.setdefault(strike, {'call': 0, 'put': 0})
                    gex_per_strike[strike]['call'] += gex

                for _, row in chain.puts.iterrows():
                    strike = float(row['strike'])
                    oi = row['openInterest']
                    iv = row['impliedVolatility']
                    if not oi or not iv or oi <= 0 or iv <= 0 or math.isnan(oi) or math.isnan(iv):
                        continue
                    gamma = _bs_gamma(spot, strike, T, iv)
                    if math.isnan(gamma) or math.isinf(gamma):
                        continue
                    gex = gamma * oi * spot * 100
                    gex_per_strike.setdefault(strike, {'call': 0, 'put': 0})
                    gex_per_strike[strike]['put'] += gex
            except Exception:
                continue

        if not gex_per_strike:
            return {"available": False, "reason": "no OI data"}

        sorted_strikes = sorted(gex_per_strike.keys())
        cumulative = 0
        call_wall = (0, 0)
        put_wall = (0, 0)
        gamma_flip = None
        total_net = 0

        for k in sorted_strikes:
            net = gex_per_strike[k]['call'] - gex_per_strike[k]['put']
            cumulative += net
            total_net = cumulative
            if net > call_wall[1]:
                call_wall = (k, net)
            if net < put_wall[1]:
                put_wall = (k, net)
            if gamma_flip is None and cumulative > 0:
                gamma_flip = k

        top_strikes = sorted(gex_per_strike.items(), key=lambda x: abs(x[1]['call'] - x[1]['put']), reverse=True)[:5]
        top_list = []
        for k, v in top_strikes:
            net = (v['call'] - v['put']) / 1e6
            top_list.append({"strike": k, "net_gex_M": round(net, 0)})

        total_net_m = round(total_net / 1e6, 0) if not (math.isnan(total_net) or math.isinf(total_net)) else 0

        regime = "neutral"
        if total_net_m != 0:
            if gamma_flip and spot > gamma_flip:
                regime = "long (suppressive)"
            else:
                regime = "short (amplifying)"

        return {
            "available": True,
            "symbol": "SPY",
            "source": "computed",
            "spot": round(spot, 2),
            "net_gex_M": total_net_m,
            "net_gex_label": "positive" if total_net_m > 0 else "negative",
            "gamma_flip": gamma_flip,
            "call_wall": call_wall[0] if call_wall[0] else None,
            "call_wall_M": round(call_wall[1] / 1e6, 0) if call_wall[1] else None,
            "put_wall": put_wall[0] if put_wall[0] else None,
            "put_wall_M": round(put_wall[1] / 1e6, 0) if put_wall[1] else None,
            "regime": regime,
            "top_strikes": top_list,
        }
    except Exception as e:
        return {"available": False, "reason": str(e)}


def validate_quote(bid, ask, mid, dte=None):
    """Check for stale, crossed, unreliable, or illiquid quotes.

    Returns (valid: bool, reject_reason: str, warnings: list[str]).
    valid=False → DATA ALERT, do not use this quote for exit decisions.
    valid=True with warnings → quote is usable but exercise caution.

    Hard rejections: crossed market, spread > 100% of mid.
    Warnings: spread 20-100% (unreliable midpoint), zero bid/ask (illiquid).
    """
    warnings = []
    # ── Zero bid/ask: liquidity warning, skip spread check (would always fire) ──
    if bid is not None and ask is not None and (bid <= 0 or ask <= 0):
        warnings.append("zero-volume quote; illiquid")
        return True, "", warnings
    # ── Hard rejections ──
    if bid is not None and ask is not None and bid > ask:
        return False, "crossed market", []
    if bid is not None and ask is not None and mid and mid > 0:
        spread_frac = (ask - bid) / mid
        if spread_frac > 1.0:
            return False, "spread >100% of mid", []
        elif spread_frac >= 0.20:
            pct = round(spread_frac * 100, 0)
            warnings.append(f"wide spread ({pct:.0f}% of mid); midpoint unreliable")
    return True, "", warnings


# ═══════════════════════════════════════════════════════════
# IV30d Snapshot Storage — for future 60-day median baseline
# ═══════════════════════════════════════════════════════════

def _load_iv30d_snapshots():
    """Load all iv_30d snapshots. Returns {ticker: [{date, iv_30d}, ...]}."""
    try:
        with open(IV30D_SNAPSHOT_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_iv30d_snapshots(data):
    """Atomic write of iv_30d snapshots."""
    os.makedirs(os.path.dirname(IV30D_SNAPSHOT_FILE), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(IV30D_SNAPSHOT_FILE), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, default=str)
        os.replace(tmp_path, IV30D_SNAPSHOT_FILE)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def store_iv30d_snapshot(ticker, iv_30d, snapshot_date=None):
    """Record today's iv_30d for a ticker. Keeps last 120 entries (~6 months).

    iv_30d is stored as a decimal (e.g. 0.45 = 45%)."""
    if snapshot_date is None:
        snapshot_date = date.today()
    date_str = snapshot_date.isoformat()

    data = _load_iv30d_snapshots()
    if ticker not in data:
        data[ticker] = []

    # Deduplicate: replace same-date entry
    data[ticker] = [s for s in data[ticker] if s.get("date") != date_str]
    data[ticker].append({"date": date_str, "iv_30d": float(iv_30d)})
    data[ticker] = sorted(data[ticker], key=lambda x: x["date"])[-120:]
    _save_iv30d_snapshots(data)


def get_iv30d_baseline(ticker):
    """Get rolling median iv_30d and robust stats for a ticker.

    Requires at least IV30D_MIN_SNAPSHOTS entries for iv_30d median.
    Falls back to 60-day historical volatility (HV) when snapshots are
    insufficient. Returns dict with source field indicating provenance.

    Returns:
        {median, mad, count, source} where source is one of:
        "iv30d_median" | "hv_60d" | None
        median=None only when both iv_30d history AND HV are unavailable.
    """
    data = _load_iv30d_snapshots()
    entries = data.get(ticker, [])

    if len(entries) >= IV30D_MIN_SNAPSHOTS:
        values = [s["iv_30d"] for s in entries if s.get("iv_30d") is not None]
        if len(values) >= IV30D_MIN_SNAPSHOTS:
            median = float(np.median(values))
            mad = float(np.median([abs(v - median) for v in values]))
            return {"median": median, "mad": mad, "count": len(values), "source": "iv30d_median"}

    # Fallback: 60-trading-day historical volatility
    if compute_hv_window is not None:
        try:
            hv = compute_hv_window(ticker, window_trading_days=60)
            if hv is not None and hv > 0:
                return {"median": hv, "mad": None, "count": 0, "source": "hv_60d"}
        except Exception:
            pass

    return {"median": None, "mad": None, "count": len(entries), "source": None}


# ═══════════════════════════════════════════════════════════
# Recovery Feasibility Diagnostic
# ═══════════════════════════════════════════════════════════

def _trading_to_calendar_days(today_date, trading_days):
    """Convert trading days to calendar days, skipping weekends.

    e.g. Friday + 2 trading days = 4 calendar days (Mon/Tue).
    Does not account for holidays."""
    remaining = trading_days
    calendar_days = 0
    cursor = today_date
    while remaining > 0:
        cursor = cursor + timedelta(days=1)
        calendar_days += 1
        if cursor.weekday() < 5:  # Mon-Fri
            remaining -= 1
    return calendar_days


def recovery_diagnostic(current_mark, credit_received, spot, strike, delta, gamma, theta, vega,
                         current_iv, baseline_iv, dte, today_date=None,
                         reference_iv_30d=None, horizon_trading_days=RECOVERY_HORIZON_TRADING_DAYS,
                         stock_change=0.0, rate=RISK_FREE_RATE, baseline_source=None,
                         baseline_mad=None):
    """Recovery Feasibility Diagnostic for Tier 3 YELLOW positions.

    Calculates whether the option could theoretically return below
    WATCH_RESOLUTION_MULTIPLE × credit through IV normalization and theta decay.
    This is a diagnostic, not a reversal prediction. It must never downgrade
    RED/ORANGE or clear YELLOW hysteresis.

    IV convention:
        current_iv, baseline_iv = decimal (e.g. 0.84 = 84%)
        vega = $ change per 1 percentage-point IV change (matching bs_put_greeks)
        required_iv_drop_pp, headroom_pp = percentage points

    baseline_source: "iv30d_median" | "hv_60d" | None — indicates provenance of baseline_iv

    Returns:
        dict with status (PLAUSIBLE|STRETCHED|INDETERMINATE), method,
        and all intermediate values for audit/reporting.
    """
    from datetime import date as date_type

    if today_date is None:
        today_date = date_type.today()

    target_mark = credit_received * WATCH_RESOLUTION_MULTIPLE
    result = {
        "status": "INDETERMINATE",
        "method": None,
        "current_mark": round(current_mark, 2),
        "target_mark": round(target_mark, 2),
        "horizon_trading_days": horizon_trading_days,
        "stock_change": stock_change,
        "current_iv_pct": round(current_iv * 100, 1) if current_iv is not None else None,
        "baseline_iv_pct": round(baseline_iv * 100, 1) if baseline_iv is not None else None,
        "baseline_source": baseline_source,
        "required_iv_drop_pp": None,
        "iv_reversion_headroom_pp": None,
        "recovery_ratio": None,
        "scenario_mark": None,
        "scenario_mark_at_reference_iv": None,
        "iv_z": None,
        "caveats": [],
    }

    # ── Guard: Greeks must be valid ──
    greeks_ok = all(
        v is not None and not (isinstance(v, float) and math.isnan(v))
        for v in [delta, gamma, theta, vega]
    )
    if not greeks_ok or abs(vega) < 1e-12:
        greeks_ok = False
        result["caveats"].append("missing or invalid Greeks; cannot compute Greek approximation")
    if current_iv is None or current_iv <= 0:
        result["caveats"].append("current IV unavailable")
        return result
    if dte is None or dte <= 0:
        result["caveats"].append("DTE unavailable or expired")
        return result

    # ── Contextual scenario at reference IV (never produces PLAUSIBLE/STRETCHED) ──
    if reference_iv_30d is not None and strike is not None and spot is not None and spot > 0:
        cal_days = _trading_to_calendar_days(today_date, horizon_trading_days)
        sc_dte = max(dte - cal_days, 1)
        sc_spot = spot + stock_change
        try:
            sc_T = sc_dte / 365.0
            sc_price = bs_put(sc_spot, strike, sc_T, reference_iv_30d, rate)
            result["scenario_mark_at_reference_iv"] = round(sc_price, 2)
            result["caveats"].append(
                "scenario_mark_at_reference_iv uses current IV30d, not historical baseline; contextual only"
            )
        except (ValueError, ZeroDivisionError):
            pass

    # ── Baseline required for classification ──
    if baseline_iv is None:
        result["caveats"].append("historical baseline IV unavailable; insufficient snapshot history")
        return result

    # ── HV proxy caveat ──
    if baseline_source == "hv_60d":
        result["caveats"].append(
            "baseline is 60-day historical volatility (HV), not IV; "
            "HV systematically differs from IV by the vol risk premium. "
            "Upgrades to iv30d median once 30 daily snapshots accumulate."
        )

    # ── Robust IV elevation (z-score, informational only) ──
    if baseline_source == "iv30d_median" and baseline_mad is not None and baseline_mad > 0 and reference_iv_30d is not None:
        iv_z_robust = (reference_iv_30d - baseline_iv) / (1.4826 * baseline_mad)
        result["iv_z"] = round(iv_z_robust, 2)

    # ── Greek approximation ──
    # vega is per 1% IV change (per 0.01 sigma). The formula produces
    # required_iv_change in percentage points. headroom is also in pp.
    if greeks_ok:
        # Taylor expansion: Δoption ≈ delta·ΔS + ½gamma·(ΔS)² + vega·Δσ + theta·Δt
        # Solve for Δσ: Δσ = (Δoption - delta·ΔS - ½gamma·(ΔS)² - theta·Δt) / vega
        numerator = (
            target_mark
            - current_mark
            - delta * stock_change
            - 0.5 * gamma * stock_change ** 2
            - theta * horizon_trading_days
        )
        required_iv_change_pp = numerator / vega  # result in percentage points
        required_iv_drop_pp = max(0.0, -required_iv_change_pp)
        result["required_iv_drop_pp"] = round(required_iv_drop_pp, 1)

        headroom_pp = max(0.0, (current_iv - baseline_iv) * 100.0)
        result["iv_reversion_headroom_pp"] = round(headroom_pp, 1)

        if required_iv_drop_pp == 0:
            result["recovery_ratio"] = 0.0
        elif headroom_pp <= 0:
            result["recovery_ratio"] = float("inf")
        else:
            result["recovery_ratio"] = round(required_iv_drop_pp / headroom_pp, 3)

    # ── Full reprice scenario (preferred method when Greeks available) ──
    if strike is not None and spot is not None and spot > 0:
        cal_days = _trading_to_calendar_days(today_date, horizon_trading_days)
        sc_dte = max(dte - cal_days, 1)
        sc_spot = spot + stock_change
        try:
            sc_T = sc_dte / 365.0
            sc_price = bs_put(sc_spot, strike, sc_T, baseline_iv, rate)
            result["scenario_mark"] = round(sc_price, 2)
            result["method"] = "full_reprice"
        except (ValueError, ZeroDivisionError):
            if greeks_ok:
                result["method"] = "greek_approximation"

    if result["method"] is None and greeks_ok:
        result["method"] = "greek_approximation"

    # ── Classify ──
    if not greeks_ok or result.get("recovery_ratio") is None:
        result["status"] = "INDETERMINATE"
        return result

    rr = result["recovery_ratio"]
    if rr <= 1.0:
        result["status"] = "PLAUSIBLE"
    else:
        result["status"] = "STRETCHED"

    return result


def _estimate_delta(price, strike, dte, iv):
    """Estimate put delta from Black-Scholes when chain delta is unavailable."""
    if not all([price, strike, dte, iv]) or dte <= 0 or iv <= 0:
        return None
    try:
        T = max(dte / 365.0, 1 / 365.0)
        d = calc_put_delta(price, strike, iv, T)
        return round(abs(d), 4)  # return absolute value for threshold checks
    except (ValueError, ZeroDivisionError):
        return None


def trigger_status(price, ma50, credit, opt_mid, strike=None, delta=None, dte=None, iv=None, watch_state=None, ma50_state=None,
                    gamma=None, theta=None, vega=None, baseline_iv=None, reference_iv_30d=None, today_date=None,
                    baseline_source=None, quote_valid=True, quote_warnings=None, quote_reason="",
                    baseline_mad=None):
    """Return (color, label, watch_info) for position trigger state.

    Three independent risk dimensions.  The highest-severity result wins.

    1. Tier 1 (thesis): price below 50-day MA → ORANGE/EXIT (MA50 alone is
       weak; the skill layer requires confirmation with 1.5× loss before
       recommending cut).
       With ma50_state={days: N}: confirmation gate. Day 1 below MA50 is
       YELLOW. Day MA50_PERSISTENCE_DAYS+ is ORANGE.
       Without ma50_state: immediate (backward compatible, manual review mode).

    2. Tier 2 (forward risk via delta): the put's absolute delta measures
       current assignment risk, incorporating moneyness, time, and IV.
         delta ≥ DELTA_HARD_EXIT  → RED   EXIT (delta)
         delta ≥ DELTA_SOFT_WATCH → YELLOW WATCH (delta — needs thesis review)
         delta <  DELTA_SOFT_WATCH → benign

    3. Tier 3 (escalation): option mid ≥ 3.0× credit (= −200% P&L).
       This is an escalation trigger, not an exit decision.
       If forward-risk signals remain benign → YELLOW WATCH (diagnose).

    Recovery diagnostic: when Tier 3 YELLOW fires without higher-priority
    signals, a recovery_diagnostic() is run and attached to watch_info.
    This is a feasibility check, not a new exit trigger. It never
    downgrades RED/ORANGE or clears YELLOW hysteresis.

    Priority: RED > ORANGE > YELLOW > GREEN.  A YELLOW from Tier 3
    never downgrades an ORANGE from Tier 1.

    YELLOW hysteresis: once a 3× YELLOW is triggered, it persists until
    the option mid drops below WATCH_RESOLUTION_MULTIPLE × credit (= 2.0×).
    Pass watch_state (from a previous call's watch_info) to maintain state.
    Without hysteresis, a position oscillates between YELLOW and GREEN at
    the 3.0× boundary (3.01× → 2.99× → 3.01×).
    """
    # ── Tier 1: thesis broken (MA50, with optional persistence gate) ──
    thesis_broken = False
    thesis_day1 = False
    if price and ma50 and price < ma50:
        if ma50_state is None:
            thesis_broken = True
        elif ma50_state.get("days", 0) + 1 >= MA50_PERSISTENCE_DAYS:
            thesis_broken = True
        else:
            thesis_day1 = True

    # ── Tier 3: escalation (3× loss) ──
    loss_breached = False
    if credit and opt_mid:
        if opt_mid >= credit * CUT_LOSS_MULTIPLE:
            loss_breached = True

    # ── Resolve delta ──
    abs_delta = None
    if delta is not None:
        if not math.isnan(delta):
            abs_delta = abs(delta)  # chain-provided delta may be negative
    if abs_delta is None and price and strike and dte and iv:
        abs_delta = _estimate_delta(price, strike, dte, iv)

    # ── Tier 2: forward risk via delta (gated by loss confirmation) ──
    loss_confirmed = bool(credit and opt_mid and opt_mid >= credit * CONFIRMED_LOSS_MULTIPLE)
    tier2_color = None
    tier2_label = None
    if abs_delta is not None:
        if abs_delta >= DELTA_HARD_EXIT and loss_confirmed:
            tier2_color = "RED"
            tier2_label = f"EXIT (delta {abs_delta:.2f})"
        elif abs_delta >= DELTA_HARD_EXIT:
            # Delta elevated but loss < 1.5×: risk exists, market hasn't confirmed
            tier2_color = "YELLOW"
            tier2_label = f"WATCH (delta {abs_delta:.2f}, unconfirmed)"
        elif abs_delta >= DELTA_SOFT_WATCH and loss_confirmed:
            tier2_color = "YELLOW"
            tier2_label = f"WATCH (delta {abs_delta:.2f})"
        # abs_delta ≥ DELTA_SOFT_WATCH without loss → benign (proximity isn't risk)
        # abs_delta < DELTA_SOFT_WATCH → no Tier 2 signal

    # ── Tier 3 escalation decision ──
    tier3_color = None
    tier3_label = None
    tier3_watch_info = None
    if loss_breached:
        if abs_delta is None:
            tier3_color = "YELLOW"
            tier3_label = "ESCALATE (3.0x, no delta)"
        elif abs_delta < DELTA_LOW_EXPOSURE:
            tier3_color = "YELLOW"
            tier3_label = f"WATCH (3.0x, delta {abs_delta:.2f} low exposure)"
        elif abs_delta < DELTA_HARD_EXIT:
            tier3_color = "YELLOW"
            tier3_label = f"WATCH (3.0x, delta {abs_delta:.2f})"
        else:
            pass

        if tier3_color == "YELLOW":
            current_multiple = round(opt_mid / credit, 2) if credit else 0
            tier3_watch_info = {
                "reason": tier3_label,
                "resolution_at": round(credit * WATCH_RESOLUTION_MULTIPLE, 2),
                "started_multiple": current_multiple,
            }
            # ── Recovery feasibility diagnostic (Tier 3 YELLOW only, never alters priority) ──
            if iv is not None and strike is not None and dte is not None and price is not None:
                if not quote_valid:
                    # Hard-invalid quote: skip Greeks, diagnostic not reliable
                    tier3_watch_info["recovery_diagnostic"] = {
                        "status": "INDETERMINATE",
                        "method": None,
                        "caveats": [f"quote rejected: {quote_reason}"],
                    }
                else:
                    rd = recovery_diagnostic(
                        current_mark=opt_mid,
                        credit_received=credit,
                        spot=price,
                        strike=strike,
                        delta=delta if delta is not None else (-abs_delta if abs_delta is not None else None),
                        gamma=gamma,
                        theta=theta,
                        vega=vega,
                        current_iv=iv,
                        baseline_iv=baseline_iv,
                        dte=dte,
                        today_date=today_date,
                        reference_iv_30d=reference_iv_30d,
                        baseline_source=baseline_source,
                        baseline_mad=baseline_mad,
                    )
                    if quote_warnings:
                        rd["caveats"].extend(quote_warnings)
                    tier3_watch_info["recovery_diagnostic"] = rd

    # ── Combine: highest severity wins ──
    # RED > ORANGE > YELLOW > GREEN
    if tier2_color == "RED":
        return "RED", tier2_label, None
    if thesis_broken:
        if loss_breached and (abs_delta and abs_delta >= DELTA_SOFT_WATCH):
            return "RED", "HARD EXIT", None
        return "ORANGE", "EXIT (MA50)", None
    if tier3_color == "YELLOW":
        return "YELLOW", tier3_label, tier3_watch_info
    if tier2_color == "YELLOW":
        return "YELLOW", tier2_label, None
    if thesis_day1:
        return "YELLOW", f"WATCH (MA50 breach day 1/{MA50_PERSISTENCE_DAYS})", None

    # ── Hysteresis: persist YELLOW across ticks ──
    # Only applies when current evaluation would return GREEN.
    # RED or ORANGE from current evaluation always overrides hysteresis.
    if watch_state and credit and opt_mid:
        resolution_at = watch_state.get("resolution_at")
        if resolution_at and opt_mid >= resolution_at:
            return "YELLOW", watch_state.get("reason", "WATCH (persisted)"), watch_state

    return "GREEN", "OK", None


def check_earnings_gate(dte, earnings_date=None):
    """Gate 7: Flag binary events inside DTE window.

    If earnings_date is provided and falls within DTE, the position
    is exposed to binary risk. DTE ≤ 7 always triggers regardless
    of earnings (gamma dominates, no time to recover).

    Returns (risk_flag: bool, note: str).
    """
    if dte is None or dte <= 0:
        return False, ""

    # DTE ≤ 7: gamma dominates, decide today
    if dte <= 7:
        return True, "DTE ≤ 7: gamma dominates, no time to recover"

    if earnings_date is not None:
        # Convert string dates from Google Sheets (Trade Ledger)
        if isinstance(earnings_date, str):
            try:
                earnings_date = date.fromisoformat(earnings_date)
            except (ValueError, TypeError):
                pass  # unparseable string — treat as no data
        if isinstance(earnings_date, date):
            days_to_earnings = (earnings_date - date.today()).days
            if 0 <= days_to_earnings <= dte:
                return True, f"Earnings in {days_to_earnings}d (inside {dte}d window)"

    return False, ""


def bs_price(spot, strike, T, iv, rate=0.0425, option_type='put'):
    """Black-Scholes option price. Compatibility wrapper around pricing.bs_put."""
    if T <= 0 or iv <= 0 or spot <= 0 or strike <= 0:
        return 0.0
    try:
        if option_type == 'put':
            return bs_put(spot, strike, T, iv, rate)
        else:
            g = bs_put_greeks(spot, strike, T, iv, rate)
            put_price = bs_put(spot, strike, T, iv, rate)
            return put_price + spot - strike * math.exp(-rate * T)
    except (ValueError, ZeroDivisionError):
        return 0.0


def compute_forward_look(positions, gex_data, today):
    """Weekly projections: theta, scenarios, GEX roll-off, key levels."""
    fl = {}

    total_theta = 0
    for pos in positions:
        theta = pos.get("theta") or 0
        qty = pos.get("quantity", 1)
        total_theta += abs(theta) * qty * 5
    fl["theta_weekly"] = round(total_theta, 2)

    scenarios = []
    for pos in positions:
        loss = pos.get("loss_pct", 0) or 0
        if loss > 50:
            dte = pos.get("dte", 30)
            spot = pos.get("spot", 0)
            strike = pos.get("strike", 0)
            iv = pos.get("iv_absolute", 30) / 100
            credit = pos.get("credit", 0)
            mid = pos.get("option_mid", 0)

            if not spot or not strike or not iv:
                continue

            iv_revert = iv * 0.82
            proj_7d = bs_price(spot, strike, (dte - 7) / 365.0, iv_revert, RISK_FREE_RATE, 'put')
            proj_14d = bs_price(spot, strike, (dte - 14) / 365.0, iv_revert, RISK_FREE_RATE, 'put')

            scenarios.append({
                "symbol": pos["symbol"],
                "strike": strike,
                "dte_now": dte,
                "spot": spot,
                "iv_now_pct": round(iv * 100, 0),
                "iv_proj_pct": round(iv_revert * 100, 0),
                "credit": credit,
                "option_now": mid,
                "loss_now_pct": loss,
                "theta_day": round(abs(pos.get("theta", 0)), 2),
                "vega_dollar": round(pos.get("vega", 0), 2),
                "proj_7d": round(proj_7d, 2),
                "proj_14d": round(proj_14d, 2),
                "proj_unrealized_label": "profitable" if proj_14d < credit else "still underwater",
            })
    fl["scenarios"] = scenarios

    if gex_data.get("available") and gex_data.get("put_wall"):
        fl["gex_outlook"] = {
            "current_regime": gex_data.get("regime"),
            "spot": gex_data.get("spot"),
            "put_wall": gex_data.get("put_wall"),
            "call_wall": gex_data.get("call_wall"),
            "note": "Near-dated negative gamma expires Friday. If put wall decays, amplification pressure eases but remains until spot reclaims call wall."
        }

    key_levels = []
    for pos in positions:
        spot = pos.get("spot", 0)
        strike = pos.get("strike", 0)
        dte = pos.get("dte", 30)
        iv = (pos.get("iv_absolute") or 30) / 100
        sym = pos.get("symbol", "")
        ma50 = pos.get("ma50")

        if not spot or not strike or dte <= 0:
            continue

        T = dte / 365.0
        try:
            lo, hi = strike * 0.7, spot
            for _ in range(20):
                mid_spot = (lo + hi) / 2
                d = calc_put_delta(mid_spot, strike, iv, T)
                if abs(d + 0.30) < 0.005:
                    break
                if d < -0.30:
                    hi = mid_spot
                else:
                    lo = mid_spot
            delta30_level = round((lo + hi) / 2, 2)
        except Exception:
            delta30_level = None

        levels = {"symbol": sym, "strike": strike, "spot": spot}
        if ma50:
            levels["ma50"] = ma50
            levels["ma50_buffer_pct"] = round((1 - ma50 / spot) * 100, 1) if spot else None
        if delta30_level:
            levels["delta_30_spot"] = delta30_level
        if pos.get("symbol") == "QQQ" and ma50:
            levels["qqq_note"] = f"50d MA at {ma50} is the line. Below it, trend psychology shifts."

        key_levels.append(levels)
    fl["key_levels"] = key_levels

    return fl


async def main():
    positions = load_positions()
    if not positions:
        print(json.dumps({"error": "No positions in Trade Ledger"}))
        return

    creds = load_tt_creds()
    symbols = list(set(p["symbol"] for p in positions))
    session = Session(creds["client_secret"], creds["refresh_token"])
    today = date.today()

    technicals, option_data = get_technicals_and_options(symbols, positions)
    iv_data = await get_iv_metrics(session, symbols)
    gex = await get_gex_data("SPY")

    output = {
        "date": today.isoformat(),
        "vix": None,
        "gex": gex,
        "positions": [],
        "alerts": [],
        "warnings": {"high_iv": [], "low_iv": []},
    }

    try:
        vix_t = yf.Ticker("^VIX")
        vix_hist = vix_t.history(period="1mo")
        vix_close = float(vix_hist["Close"].iloc[-1]) if len(vix_hist) else None
        vix_ma20 = float(vix_hist["Close"].tail(20).mean()) if len(vix_hist) >= 20 else None
        output["vix"] = {
            "close": round(vix_close, 1) if vix_close else None,
            "ma20": round(vix_ma20, 1) if vix_ma20 else None,
        }
    except Exception:
        pass

    high_iv_seen = set()
    low_iv_seen = set()

    for pos in positions:
        sym = pos["symbol"]
        strike = pos["strike"]
        credit = pos.get("credit_received", 0)
        t = technicals.get(sym, {})
        price = t.get("price")
        ma50 = t.get("ma50")
        iv = iv_data.get(sym, {})
        iv_rank = iv.get("iv_rank")
        opt = option_data.get(f"{sym}_{strike}", {})

        try:
            dte_num = (date.fromisoformat(pos["expiry"]) - today).days
        except (KeyError, ValueError):
            dte_num = None

        buf_pct = None
        if price and strike:
            buf_pct = round((1 - strike / price) * 100, 1)

        loss_pct = None
        loss_threshold = None
        if credit and opt.get("mid"):
            loss_pct = round((opt["mid"] - credit) / credit * 100, 0)
            loss_threshold = round(credit * CUT_LOSS_MULTIPLE, 2)

        # Compute baseline_iv from IV30d snapshots (falls back to 60-day HV)
        iv30d_val = iv.get("iv_30d")
        reference_iv_30d = iv30d_val / 100.0 if iv30d_val is not None else None  # Tastytrade iv_30d is %, convert to decimal
        baseline = get_iv30d_baseline(sym)
        baseline_iv = baseline["median"]  # iv30d median or HV fallback
        baseline_source = baseline["source"]
        baseline_count = baseline["count"]

        # Store today's IV30d snapshot for future baseline computation
        if iv30d_val is not None:
            store_iv30d_snapshot(sym, iv30d_val / 100.0, snapshot_date=today)

        status_emoji, status_label, watch_info = trigger_status(
            price, ma50, credit, opt.get("mid"),
            strike=strike,
            delta=opt.get("delta"),
            dte=dte_num,
            iv=opt.get("iv_absolute") / 100 if opt.get("iv_absolute") else None,
            gamma=opt.get("gamma"),
            theta=opt.get("theta"),
            vega=opt.get("vega"),
            baseline_iv=baseline_iv,
            reference_iv_30d=reference_iv_30d,
            today_date=today,
            baseline_source=baseline_source,
            quote_valid=opt.get("quote_valid", True),
            quote_warnings=opt.get("quote_warnings"),
            quote_reason=opt.get("quote_reason", ""),
            baseline_mad=baseline.get("mad"),
        )

        # Earnings gate: flag binary risk if earnings inside DTE window
        earnings_risk, earnings_note = check_earnings_gate(
            dte_num, pos.get("earnings_date")
        )

        pos_out = {
            "symbol": sym,
            "strike": int(strike) if strike else None,
            "type": pos.get("type", "put"),
            "expiry": pos.get("expiry"),
            "dte": dte_num,
            "quantity": pos.get("quantity"),
            "credit": round(credit, 2) if credit else None,
            "spot": round(price, 2) if price else None,
            "ma50": ma50,
            "buffer_pct": buf_pct,
            "option_mid": round(opt.get("mid"), 2) if opt.get("mid") else None,
            "loss_pct": loss_pct,
            "loss_threshold": loss_threshold,
            "iv_rank": round(iv_rank * 100, 0) if iv_rank else None,
            "iv_absolute": opt.get("iv_absolute"),
            "reference_iv_30d": round(reference_iv_30d * 100, 1) if reference_iv_30d is not None else None,
            "baseline_iv_median": round(baseline_iv * 100, 1) if baseline_iv is not None else None,
            "baseline_iv_source": baseline_source,
            "baseline_iv_snapshots": baseline_count,
            "delta": opt.get("delta"),
            "gamma": opt.get("gamma"),
            "vega": opt.get("vega"),
            "theta": opt.get("theta"),
            "status_emoji": status_emoji,
            "status_label": status_label,
            "earnings_risk": earnings_risk,
            "earnings_note": earnings_note,
            "assignment_notional": round(int(pos.get("quantity", 1) or 1) * 100 * strike, 2) if strike else None,
            "position_pct": round(int(pos.get("quantity", 1) or 1) * 100 * strike / ACCOUNT_SIZE * 100, 1) if (strike and ACCOUNT_SIZE > 0) else None,
        }
        if watch_info:
            pos_out["watch_info"] = watch_info
        output["positions"].append(pos_out)

        if iv_rank and iv_rank > 0.8:
            if sym not in high_iv_seen:
                high_iv_seen.add(sym)
                output["warnings"]["high_iv"].append(sym)
        elif iv_rank is not None and iv_rank < 0.2:
            if sym not in low_iv_seen:
                low_iv_seen.add(sym)
                output["warnings"]["low_iv"].append(sym)

        if status_label != "OK":
            output["alerts"].append({
                "symbol": sym,
                "strike": int(strike) if strike else None,
                "status": status_label,
                "emoji": status_emoji,
            })

    # Position sizing summary: max assignment notional and concentration check
    notionals = [p.get("assignment_notional") for p in output["positions"] if p.get("assignment_notional")]
    sizing = {
        "total_assignment_notional": round(sum(notionals), 2) if notionals else 0,
        "max_single_position": round(max(notionals), 2) if notionals else 0,
        "position_count": len(notionals),
    }
    if ACCOUNT_SIZE > 0:
        sizing["account_size"] = ACCOUNT_SIZE
        sizing["total_deployed_pct"] = round(sum(notionals) / ACCOUNT_SIZE * 100, 1) if notionals else 0
        sizing["max_single_pct"] = round(max(notionals) / ACCOUNT_SIZE * 100, 1) if notionals else 0
        # Flag any position over 25% of account
        sizing["concentration_flag"] = any(
            n / ACCOUNT_SIZE > 0.25 for n in notionals
        ) if notionals else False
    else:
        sizing["note"] = "Set ACCOUNT_SIZE env var for position_pct calculation"
    output["position_sizing"] = sizing

    output["forward_look"] = compute_forward_look(output["positions"], output["gex"], today)

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
