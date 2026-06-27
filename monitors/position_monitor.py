#!/usr/bin/env python3
"""
Three-Layer Trigger Monitor
- Layer 1: Underlying breaks 50-day MA -> EXIT (thesis broken)
- Layer 2: Option hits -150% AND IV Rank > 80% -> WATCH (likely vol artifact)
- Layer 3: Option hits -150% AND IV Rank < 80% -> EXIT (real damage, not noise)
- Combined: Both fire -> HARD EXIT (no ambiguity)

Reads Trade Ledger from Google Sheets. Prints alerts when triggered.
Designed for cron (15 min during US market hours).
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import date

import yfinance as yf
from tastytrade import Session, metrics as tt_metrics
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

ENV_CS = os.environ.get("TASTYTRADE_CLIENT_SECRET", "")
ENV_RT = os.environ.get("TASTYTRADE_REFRESH_TOKEN", "")
ENV_CREDS = os.environ.get("TASTYTRADE_CREDS", "")
SHEET_ID = os.environ.get("TRADE_LEDGER_SHEET_ID", "")
GOOGLE_TOKEN = os.environ.get("GOOGLE_TOKEN_FILE", "google_token.json")

CUT_LOSS_MULTIPLE = 2.5
IV_NOISE_THRESHOLD = 0.80

EQUALS = "="


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
                result[f"{sym}_{strike}"] = {"bid": bid, "ask": ask, "last": last, "mid": mid}
            except Exception:
                pass
        return result
    except Exception as e:
        print(f"WARNING: yfinance options: {e}", file=sys.stderr)
        return {}


def evaluate(positions, technicals, iv_data, option_prices):
    alerts = []

    for pos in positions:
        sym = pos["symbol"]
        strike = pos["strike"]
        credit = pos.get("credit_received", 0)
        if not credit:
            continue

        tech = technicals.get(sym, {})
        price = tech.get("price")
        ma50 = tech.get("ma50")
        iv = iv_data.get(sym, {})
        iv_rank = iv.get("iv_rank")
        opt = option_prices.get(f"{sym}_{strike}", {})
        opt_mid = opt.get("mid")

        try:
            dte = (date.fromisoformat(pos["expiry"]) - date.today()).days
        except (KeyError, ValueError):
            dte = None

        thesis_broken = (price and ma50 and price < ma50)
        loss_breached = False
        iv_noise = False

        if credit and opt_mid:
            threshold = credit * CUT_LOSS_MULTIPLE
            if opt_mid >= threshold:
                loss_breached = True
                if iv_rank and iv_rank > IV_NOISE_THRESHOLD:
                    iv_noise = True

        if not thesis_broken and not loss_breached:
            continue

        parts = []

        if thesis_broken and loss_breached:
            parts.append(
                f"RED **{sym} {strike}P** - HARD EXIT: both triggers fired"
            )
            parts.append(f"  Underlying ${price:.2f} < 50d MA ${ma50:.2f}")
            parts.append(
                f"  Option mid ${opt_mid:.2f} >= -150% threshold "
                f"${credit * CUT_LOSS_MULTIPLE:.2f}"
            )
        elif thesis_broken:
            parts.append(
                f"ORANGE **{sym} {strike}P** - EXIT: underlying below 50-day MA"
            )
            parts.append(f"  Spot ${price:.2f} < 50d MA ${ma50:.2f}")
        elif loss_breached and iv_noise:
            iv_display = f"{iv_rank*100:.0f}%" if iv_rank else "N/A"
            parts.append(
                f"YELLOW **{sym} {strike}P** - WATCH: -150% hit but likely vol artifact"
            )
            parts.append(
                f"  Option mid ${opt_mid:.2f} >= ${credit * CUT_LOSS_MULTIPLE:.2f}"
                f" | IV Rank {iv_display}"
            )
            if price and ma50:
                buf_pct = (price - ma50) / price * 100
                parts.append(
                    f"  Underlying ${price:.2f} | 50d MA ${ma50:.2f}"
                    f" | Buffer {buf_pct:.1f}%"
                )
            if dte:
                parts.append(f"  DTE: {dte}d remaining")
        elif loss_breached and not iv_noise:
            iv_display = f"{iv_rank*100:.0f}%" if iv_rank else "N/A"
            parts.append(
                f"RED **{sym} {strike}P** - EXIT: -150% loss at IV Rank"
                f" {iv_display} (not vol artifact)"
            )
            parts.append(
                f"  Option mid ${opt_mid:.2f} >= ${credit * CUT_LOSS_MULTIPLE:.2f}"
            )

        if iv:
            iv_display = f"{iv_rank*100:.0f}%" if iv_rank else "N/A"
            iv30_display = f"{iv.get('iv_30d', 0):.1f}%" if iv.get('iv_30d') else "N/A"
            hv30_display = f"{iv.get('hv_30d', 0):.1f}%" if iv.get('hv_30d') else "N/A"
            parts.append(
                f"  IV Rank {iv_display} | IV30d {iv30_display}"
                f" | HV30d {hv30_display}"
            )

        if parts:
            alerts.append("\n".join(parts))

    return alerts


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

    alerts = evaluate(positions, technicals, iv_data, option_prices)
    if alerts:
        print("\n\n".join(alerts))


if __name__ == "__main__":
    asyncio.run(main())
