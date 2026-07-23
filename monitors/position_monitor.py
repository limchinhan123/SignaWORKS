#!/usr/bin/env python3
"""
Two-Layer Trigger Monitor
- Layer 1: Underlying breaks 50-day MA -> EXIT (thesis broken)
- Layer 2: Option mid >= credit × 3 (= −200%) -> escalation trigger.
    Delta-based forward risk check determines EXIT vs WATCH.
- Priority: RED > ORANGE > YELLOW > GREEN. ORANGE is never
    downgraded by a YELLOW from Layer 2.

Reads Trade Ledger from Google Sheets. Prints alerts when triggered.
Designed for cron (15 min during US market hours).
"""

import asyncio
import json
import os
import sys
import tempfile
from datetime import date, datetime

import yfinance as yf
from tastytrade import Session, metrics as tt_metrics
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

ENV_CS = os.environ.get("TASTYTRADE_CLIENT_SECRET", "")
ENV_RT = os.environ.get("TASTYTRADE_REFRESH_TOKEN", "")
ENV_CREDS = os.environ.get("TASTYTRADE_CREDS", "")
SHEET_ID = os.environ.get("TRADE_LEDGER_SHEET_ID", "")
GOOGLE_TOKEN = os.environ.get("GOOGLE_TOKEN_FILE", "google_token.json")

# ── Risk thresholds ─────────────────────────────────────────────
CUT_LOSS_MULTIPLE = 3.0     # Escalation trigger: mid ≥ credit × 3 (= −200% P&L). Diagnose, don't auto-exit.
CONFIRMED_LOSS_MULTIPLE = 1.5  # Loss must be ≥ 1.5× for delta exit to fire (market confirms the risk)
WATCH_RESOLUTION_MULTIPLE = 2.0  # Clear 3× YELLOW only when mid drops below 2.0× credit (not 2.99×)
DELTA_HARD_EXIT   = 0.35    # Put delta ≥ 0.35 → hard exit ONLY when loss ≥ 1.5×; else YELLOW
DELTA_SOFT_WATCH  = 0.25    # Put delta ≥ 0.25 → material risk ONLY when loss ≥ 1.5×; else benign
DELTA_LOW_EXPOSURE = 0.15    # Put delta < 0.15  → low current assignment risk
MA50_PERSISTENCE_DAYS = 2     # Consecutive days below MA50 before ORANGE (not a single cross)
EQUALS = "="
WATCH_STATE_FILE = os.path.expanduser("~/.hermes/cache/watch_states.json")
MA50_STATE_FILE = os.path.expanduser("~/.hermes/cache/ma50_states.json")


def contract_key(sym, strike, expiry):
    """Stable key for a short put contract across monitor runs."""
    return f"{sym}_{strike}_{expiry}"


def load_watch_states():
    """Load persisted YELLOW watch states. Expired contracts are pruned.
    Returns empty dict on any failure (fail-YELLOW, not fail-GREEN)."""
    try:
        with open(WATCH_STATE_FILE, "r") as f:
            states = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    today = date.today()
    cleaned = {}
    for key, entry in states.items():
        try:
            expiry_str = entry.get("expiry", key.split("_")[-1])
            expiry_date = date.fromisoformat(expiry_str)
            if expiry_date < today:
                continue  # expired, drop
        except (ValueError, KeyError):
            pass  # keep if can't parse
        cleaned[key] = entry
    return cleaned


def save_watch_states(states):
    """Atomic write of watch states to file."""
    os.makedirs(os.path.dirname(WATCH_STATE_FILE), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(WATCH_STATE_FILE), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(states, f, indent=2, default=str)
        os.replace(tmp_path, WATCH_STATE_FILE)
    except Exception:
        os.unlink(tmp_path)
        raise


def load_ma50_states():
    """Load persisted MA50 breach counters. Expired contracts pruned.
    Returns empty dict on any failure."""
    try:
        with open(MA50_STATE_FILE, "r") as f:
            states = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    today = date.today()
    cleaned = {}
    for key, entry in states.items():
        try:
            expiry_str = entry.get("expiry", key.split("_")[-1])
            expiry_date = date.fromisoformat(expiry_str)
            if expiry_date < today:
                continue
        except (ValueError, KeyError):
            pass
        cleaned[key] = entry
    return cleaned


def save_ma50_states(states):
    """Atomic write of MA50 states to file."""
    os.makedirs(os.path.dirname(MA50_STATE_FILE), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(MA50_STATE_FILE), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(states, f, indent=2, default=str)
        os.replace(tmp_path, MA50_STATE_FILE)
    except Exception:
        os.unlink(tmp_path)
        raise


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
                if line.startswith(f"TASTYTRADE_CLIENT_SECRET{EQUALS}"):
                    d["client_secret"] = line.split(EQUALS, 1)[1]
                elif line.startswith(f"TASTYTRADE_REFRESH_TOKEN{EQUALS}"):
                    d["refresh_token"] = line.split(EQUALS, 1)[1]
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


def get_technicals(symbols):
    try:
        tickers = yf.Tickers(" ".join(symbols))
        result = {}
        for sym in symbols:
            try:
                t = tickers.tickers[sym]
                info = t.fast_info
                price = info.get("lastPrice") or info.get("regularMarketPreviousClose")
                hist = t.history(period="3mo")
                ma50 = float(hist["Close"].tail(50).mean()) if len(hist) >= 50 else None
                result[sym] = {
                    "price": float(price) if price else None,
                    "ma50": round(ma50, 2) if ma50 else None,
                }
            except Exception:
                result[sym] = {"price": None, "ma50": None}
        return result
    except Exception as e:
        print(f"WARNING: yfinance prices: {e}", file=sys.stderr)
        return {}


def get_option_prices(symbols, positions):
    try:
        tickers = yf.Tickers(" ".join(symbols))
        result = {}
        for pos in positions:
            sym = pos["symbol"]
            strike = pos["strike"]
            try:
                exp = pos["expiry"]
            except KeyError:
                continue
            try:
                t = tickers.tickers[sym]
                chain = t.option_chain(exp)
                df = chain.puts
                row = df[df["strike"] == float(strike)]
                if row.empty:
                    continue
                bid = row["bid"].values[0]
                ask = row["ask"].values[0]
                last = row["lastPrice"].values[0]
                mid = (bid + ask) / 2 if bid and ask else last
                iv = float(row["impliedVolatility"].values[0]) if "impliedVolatility" in row.columns else None
                result[f"{sym}_{strike}"] = {
                    "bid": bid, "ask": ask, "last": last, "mid": mid,
                    "iv": iv,
                }
            except Exception:
                pass
        return result
    except Exception as e:
        print(f"WARNING: yfinance options: {e}", file=sys.stderr)
        return {}


def _estimate_delta_monitor(price, strike, dte, iv):
    """Estimate put delta from Black-Scholes. Returns absolute value or None."""
    if not all([price, strike, dte, iv]) or dte <= 0 or iv <= 0:
        return None
    try:
        T = max(dte / 365.0, 1 / 365.0)
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from pricing import calc_put_delta
        d = calc_put_delta(price, strike, iv, T)
        return round(abs(d), 4)
    except (ValueError, ZeroDivisionError):
        return None


def evaluate(positions, technicals, iv_data, option_prices, watch_states=None, ma50_states=None):
    """Evaluate all positions. Integrates cross-tick YELLOW hysteresis and MA50 persistence.

    Args:
        watch_states: dict of {contract_key: {reason, resolution_at, started_multiple, expiry}}
        ma50_states: dict of {contract_key: {days, first_seen, expiry}}

    Returns:
        (alerts, watch_states, ma50_states) tuple. Caller must persist the states.
        alerts: list of alert dicts with symbol, signal, msg.
    """
    if ma50_states is None:
        ma50_states = {}
    alerts = []
    today = date.today()

    for pos in positions:
        sym = pos["symbol"]
        strike = pos["strike"]
        credit = pos.get("credit_received", 0)
        expiry = pos.get("expiry", "")
        if not credit:
            continue

        key = contract_key(sym, strike, expiry)

        tech = technicals.get(sym, {})
        price = tech.get("price")
        ma50 = tech.get("ma50")
        iv_info = iv_data.get(sym, {})
        iv_rank = iv_info.get("iv_rank")
        opt = option_prices.get(f"{sym}_{strike}", {})
        opt_mid = opt.get("mid")
        opt_iv = opt.get("iv")

        try:
            dte = (date.fromisoformat(expiry) - date.today()).days
        except (KeyError, ValueError):
            dte = None

        # ── Resolve delta ──
        abs_delta = _estimate_delta_monitor(price, strike, dte, opt_iv)

        # ── Tier 1: thesis — MA50 persistence check ──
        # Day 1 below MA50: YELLOW warning. Day MA50_PERSISTENCE_DAYS+: ORANGE.
        thesis_confirmed = False
        thesis_day1 = False
        if price and ma50 and price < ma50:
            if key not in (ma50_states or {}):
                (ma50_states or {})[key] = {"days": 1, "first_seen": str(today), "expiry": expiry}
                thesis_day1 = True
            else:
                entry = (ma50_states or {})[key]
                days = entry.get("days", 1) + 1
                entry["days"] = days
                if days >= MA50_PERSISTENCE_DAYS:
                    thesis_confirmed = True
                else:
                    thesis_day1 = True
        elif key in (ma50_states or {}):
            del (ma50_states or {})[key]

        # ── Tier 3: escalation (3× loss) ──
        loss_breached = False
        if credit and opt_mid:
            if opt_mid >= credit * CUT_LOSS_MULTIPLE:
                loss_breached = True

        # ── Hysteresis: persist YELLOW across ticks ──
        hysteresis_active = False
        hysteresis_reason = None
        if key in watch_states and credit and opt_mid:
            resolution_at = watch_states[key].get("resolution_at")
            if resolution_at and opt_mid >= resolution_at:
                hysteresis_active = True
                hysteresis_reason = watch_states[key].get("reason", "WATCH (persisted)")

        # ── Tier 2: forward risk via delta (gated by loss confirmation) ──
        loss_confirmed = bool(credit and opt_mid and opt_mid >= credit * CONFIRMED_LOSS_MULTIPLE)
        tier2_signal = None  # (color, label)
        if abs_delta is not None:
            if abs_delta >= DELTA_HARD_EXIT and loss_confirmed:
                tier2_signal = ("RED", f"EXIT (delta {abs_delta:.2f})")
            elif abs_delta >= DELTA_HARD_EXIT:
                tier2_signal = ("YELLOW", f"WATCH (delta {abs_delta:.2f}, unconfirmed)")
            elif abs_delta >= DELTA_SOFT_WATCH and loss_confirmed:
                tier2_signal = ("YELLOW", f"WATCH (delta {abs_delta:.2f})")

        # ── Tier 3 escalation decision ──
        tier3_signal = None
        tier3_watch_info = None
        if loss_breached:
            if abs_delta is None:
                tier3_signal = ("YELLOW", "ESCALATE (3.0x, no delta)")
            elif abs_delta < DELTA_LOW_EXPOSURE:
                tier3_signal = ("YELLOW", f"WATCH (3.0x, delta {abs_delta:.2f} low exposure)")
            elif abs_delta < DELTA_HARD_EXIT:
                tier3_signal = ("YELLOW", f"WATCH (3.0x, delta {abs_delta:.2f})")

            if tier3_signal and tier3_signal[0] == "YELLOW":
                current_multiple = round(opt_mid / credit, 2) if credit else 0
                tier3_watch_info = {
                    "reason": tier3_signal[1],
                    "resolution_at": round(credit * WATCH_RESOLUTION_MULTIPLE, 2),
                    "started_multiple": current_multiple,
                    "started_at": datetime.now().isoformat(),
                    "expiry": expiry,
                }

        # ── Combine: highest severity wins ──
        # RED > ORANGE > YELLOW > GREEN
        # Hysteresis YELLOW is overridden by any RED or ORANGE from current evaluation.
        # thesis_day1 = YELLOW (MA50 cross, day 1). thesis_confirmed = ORANGE.

        if tier2_signal and tier2_signal[0] == "RED":
            color, label = tier2_signal
            watch_states.pop(key, None)
        elif thesis_confirmed:
            if loss_breached and abs_delta and abs_delta >= DELTA_SOFT_WATCH:
                color, label = "RED", "HARD EXIT"
                watch_states.pop(key, None)
            else:
                color, label = "ORANGE", "EXIT (MA50)"
                watch_states.pop(key, None)
        elif thesis_day1:
            # Day 1 MA50 breach: YELLOW warning, persists until recovery
            color, label = "YELLOW", "WATCH (MA50 breach day 1)"
        elif tier3_signal:
            color, label = tier3_signal
            watch_states[key] = tier3_watch_info
        elif tier2_signal:
            color, label = tier2_signal
            watch_states.pop(key, None)
        elif hysteresis_active:
            color, label = "YELLOW", hysteresis_reason
        else:
            watch_states.pop(key, None)
            continue

        # ── Build alert message ──
        parts = []
        distance_str = ""
        if strike and price:
            distance_str = f" ({round((price - strike) / strike * 100, 1)}% OTM)"

        if color == "RED" and label == "HARD EXIT":
            parts.append(f"RED **{sym} {strike}P** - HARD EXIT: MA50 broken + 3× loss + elevated delta")
            parts.append(f"  Spot ${price:.2f} < 50d MA ${ma50:.2f}{distance_str}")
            parts.append(f"  Option mid ${opt_mid:.2f} >= -200% threshold ${credit * CUT_LOSS_MULTIPLE:.2f}")
            if abs_delta:
                parts.append(f"  Put delta {abs_delta:.2f}")
        elif color == "RED":
            parts.append(f"RED **{sym} {strike}P** - {label}")
            if abs_delta:
                parts.append(f"  Put delta {abs_delta:.2f}{distance_str}")
            parts.append(f"  Spot ${price:.2f}")
        elif color == "ORANGE":
            parts.append(f"ORANGE **{sym} {strike}P** - EXIT: underlying below 50-day MA")
            parts.append(f"  Spot ${price:.2f} < 50d MA ${ma50:.2f}{distance_str}")
            if loss_breached:
                parts.append(f"  Note: 3.0× loss also breached but delta is benign")
        elif color == "YELLOW":
            if thesis_day1:
                parts.append(f"YELLOW **{sym} {strike}P** - MA50 breach day 1/{MA50_PERSISTENCE_DAYS} (watch)")
                parts.append(f"  Spot ${price:.2f} < 50d MA ${ma50:.2f}{distance_str}")
            elif hysteresis_active and not loss_breached:
                parts.append(f"YELLOW **{sym} {strike}P** - {label} (persisted watch)")
                parts.append(f"  Spot ${price:.2f}{distance_str}")
                resolution_info = watch_states.get(key, {})
                parts.append(f"  Option mid ${opt_mid:.2f}" if not loss_breached else f"  Option mid ${opt_mid:.2f} >= ${credit * CUT_LOSS_MULTIPLE:.2f}")
                if resolution_info.get("resolution_at"):
                    parts.append(f"  Watch clears below ${resolution_info['resolution_at']:.2f}")
            else:
                parts.append(f"YELLOW **{sym} {strike}P** - {label}")
                parts.append(f"  Spot ${price:.2f}{distance_str}")
                if loss_breached:
                    resolution_info = watch_states.get(key, {})
                    parts.append(f"  Option mid ${opt_mid:.2f} >= ${credit * CUT_LOSS_MULTIPLE:.2f}")
                    if resolution_info.get("resolution_at"):
                        parts.append(f"  Watch clears below ${resolution_info['resolution_at']:.2f}")
            if abs_delta:
                parts.append(f"  Put delta {abs_delta:.2f}")

        iv_display = f"{iv_rank*100:.0f}%" if iv_rank else "N/A"
        if iv_info:
            iv30_display = f"{iv_info.get('iv_30d', 0):.1f}%" if iv_info.get('iv_30d') else "N/A"
            hv30_display = f"{iv_info.get('hv_30d', 0):.1f}%" if iv_info.get('hv_30d') else "N/A"
            parts.append(f"  IV Rank {iv_display} | IV30d {iv30_display} | HV30d {hv30_display}")

        alerts.append({"symbol": sym, "signal": color, "msg": "\n".join(parts)})

    return alerts, watch_states, ma50_states


async def main():
    positions = load_positions()
    if not positions:
        sys.exit(0)

    symbols = list(set(p["symbol"] for p in positions))
    creds = load_tt_creds()
    session = Session(creds["client_secret"], creds["refresh_token"])

    technicals = get_technicals(symbols)
    iv_data = await get_iv_metrics(session, symbols)
    option_prices = get_option_prices(symbols, positions)

    watch_states = load_watch_states()
    ma50_states = load_ma50_states()
    alerts, watch_states, ma50_states = evaluate(positions, technicals, iv_data, option_prices, watch_states, ma50_states)
    save_watch_states(watch_states)
    save_ma50_states(ma50_states)

    if alerts:
        for a in alerts:
            print(a["msg"])
        print()


if __name__ == "__main__":
    asyncio.run(main())
