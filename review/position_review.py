#!/usr/bin/env python3
"""
Position Review with Greeks + Trigger Analysis + GEX.
Reads Trade Ledger from Google Sheets. Fetches spot, options, IV metrics, Greeks.
Prints JSON output for downstream formatting.
"""
import asyncio, os, sys, json
from datetime import date
import math
import yfinance as yf
from tastytrade import Session, metrics as tt_metrics
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

ENV_CS = os.environ.get("TASTYTRADE_CLIENT_SECRET", "")
ENV_RT = os.environ.get("TASTYTRADE_REFRESH_TOKEN", "")
ENV_CREDS = os.environ.get("TASTYTRADE_CREDS", "")
SHEET_ID = os.environ.get("TRADE_LEDGER_SHEET_ID", "")
GOOGLE_TOKEN = os.environ.get("GOOGLE_TOKEN_FILE", "google_token.json")

CUT_LOSS_MULTIPLE = 3.0   # Hard override: mid >= credit × 3 (= −200%). No exemptions.

# Shared Black-Scholes from repo-root pricing.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pricing import bs_put_greeks, bs_put, calc_put_delta, R as RISK_FREE_RATE


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
            greeks = bs_greeks(spot, strike, dte, iv_abs) if spot and dte > 0 else {}

            option_data[f"{sym}_{strike}"] = {
                "bid": bid, "ask": ask, "last": last, "mid": mid,
                "iv_absolute": round(iv_abs * 100, 1),
                "dte": dte,
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


def trigger_status(price, ma50, credit, opt_mid):
    """Return (color, label) for position trigger state.

    thesis: price below 50-day MA (bearish signal)
    loss_breached: option mid >= credit × CUT_LOSS_MULTIPLE (= −200%, hard exit trigger)

    The hard exit is unconditional — no IV noise exemption.
    """
    thesis = (price and ma50 and price < ma50)
    loss_breached = False
    if credit and opt_mid:
        threshold = credit * CUT_LOSS_MULTIPLE
        if opt_mid >= threshold:
            loss_breached = True

    if thesis and loss_breached:
        return "RED", "HARD EXIT"
    elif thesis:
        return "ORANGE", "EXIT (MA50)"
    elif loss_breached:
        return "RED", "EXIT (Loss)"
    else:
        return "GREEN", "OK"


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

        status_emoji, status_label = trigger_status(
            price, ma50, credit, opt.get("mid")
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
            "delta": opt.get("delta"),
            "gamma": opt.get("gamma"),
            "vega": opt.get("vega"),
            "theta": opt.get("theta"),
            "status_emoji": status_emoji,
            "status_label": status_label,
            "earnings_risk": earnings_risk,
            "earnings_note": earnings_note,
        }
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

    output["forward_look"] = compute_forward_look(output["positions"], output["gex"], today)

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
