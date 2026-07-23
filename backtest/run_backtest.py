#!/usr/bin/env python3
"""Run the framework backtest against live positions and WDC/STX historical data."""
import json
import os
import sys
from datetime import date
import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.backtest import evaluate_position, format_matrix, format_detail
from pricing import bs_put_greeks

SHEET_ID = "169luP1yFqcQHBgB8ef8cOoCiSMHCl_mYQcxzRkqhFK8"

def load_positions():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    GOOGLE_TOKEN = os.environ.get("GOOGLE_TOKEN_FILE", "/root/.hermes/google_token.json")
    creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN)
    svc = build("sheets", "v4", credentials=creds)
    result = svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range="Sheet1!A:H"
    ).execute()
    rows = result.get("values", [])
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


def main():
    today = date.today()
    results = []

    # ── Load live positions ──
    print("Loading Trade Ledger...", file=sys.stderr)
    positions = load_positions()
    symbols = list(set(p["symbol"] for p in positions))

    # ── Fetch current data ──
    print(f"Fetching data for {len(symbols)} symbols...", file=sys.stderr)
    tickers = yf.Tickers(" ".join(symbols))

    for pos in positions:
        sym = pos["symbol"]
        strike = pos["strike"]
        credit = pos.get("credit_received", 0)
        expiry = pos.get("expiry", "")

        try:
            t = tickers.tickers[sym]
            info = t.fast_info
            spot = info.get("lastPrice") or info.get("regularMarketPreviousClose")
            spot = float(spot) if spot else None

            exp_date = date.fromisoformat(expiry)
            dte = (exp_date - today).days

            chain = t.option_chain(expiry)
            row = chain.puts[chain.puts["strike"] == float(strike)]
            if row.empty:
                print(f"  {sym} {strike}P: no option data", file=sys.stderr)
                continue

            bid = float(row["bid"].values[0])
            ask = float(row["ask"].values[0])
            mid = (bid + ask) / 2 if bid and ask else float(row["lastPrice"].values[0])
            iv = float(row["impliedVolatility"].values[0])

            # Compute BS delta for cross-check
            greeks = bs_put_greeks(spot, strike, max(dte/365.0, 1/365.0), iv, 0.045)
            chain_delta = abs(greeks["delta"])

            name = f"{sym} {strike:.0f}P {expiry}"
            r = evaluate_position(
                name=name,
                credit=credit,
                spot=spot,
                strike=strike,
                dte=dte,
                iv=iv,
                opt_mid=mid,
                chain_delta=chain_delta,
                actual_pnl=f"${(credit - mid) * 100:.0f}",
                actual_action=pos.get("exit_trigger", "") or "holding",
            )
            results.append(r)
            print(f"  {name}: spot ${spot:.2f}, mid ${mid:.2f}, IV {iv*100:.0f}%, delta {chain_delta:.4f}, {r['loss_multiple']:.2f}×", file=sys.stderr)

        except Exception as e:
            print(f"  {sym} {strike}P: error — {e}", file=sys.stderr)

    # ── WDC historical: cut at Jul 7 ──
    print("Adding WDC historical...", file=sys.stderr)
    results.append(evaluate_position(
        name="WDC 450P Jul 31 [cut Jul 7]",
        credit=7.99, spot=531.0, strike=450.0, dte=24,
        iv=1.21,  # estimated from BS: mid=$27.74, spot=$531, strike=$450, DTE=24 → IV≈121%
        opt_mid=27.74,
        actual_pnl="-$1,976 (cut)",
        actual_action="CUT (3.47×, old rule)",
    ))

    # ── WDC counterfactual: if held to Jul 23 ──
    results.append(evaluate_position(
        name="WDC 450P Jul 31 [Jul 23 mark]",
        credit=7.99, spot=556.67, strike=450.0, dte=8,
        iv=2.50,  # estimated: mid=$8.30, spot=$556.67, strike=$450, DTE=8, wide spread
        opt_mid=8.30,
        actual_pnl="-$31 (counterfactual)",
        actual_action="Recovered to near-breakeven",
    ))

    # ── STX historical: cut at Jul 2 ──
    results.append(evaluate_position(
        name="STX 700P Jul 31 [cut Jul 2]",
        credit=10.12, spot=780.0, strike=700.0, dte=29,
        iv=0.95,  # estimated
        opt_mid=30.97,
        actual_pnl="-$2,085 (cut)",
        actual_action="CUT (3.06×, old rule)",
    ))

    # ── STX counterfactual: Jul 23 ──
    results.append(evaluate_position(
        name="STX 700P Jul 31 [Jul 23 mark]",
        credit=10.12, spot=908.10, strike=700.0, dte=8,
        iv=2.20,  # estimated: mid=$13.70, far OTM, wide bid/ask
        opt_mid=13.70,
        actual_pnl="-$358 (counterfactual)",
        actual_action="Still underwater but improving",
    ))

    # ── Output ──
    print("\n" + format_matrix(results))
    detail = format_detail(results)
    if detail.strip().split("\n")[-1] != "## Framework Divergences":
        print(detail)

    # Also output the key question
    print("## Assessment")
    print("")
    print("The backtest compares three frameworks at each decision point:")
    print("- **A**: Old unconditional 3× → exit (what was running when WDC/STX were cut)")
    print("- **B**: 15% distance → cut if within 15%, 48h watch if above (yesterday's intermediate)")
    print("- **C**: Delta V2 → diagnose by delta; <0.15 low exposure watch, 0.25+ material watch, 0.35+ exit")
    print("")
    print("Framework C is current. Framework B was a stepping stone. Framework A is the baseline.")
    print("")
    print("Key question for each divergence: **which framework would have produced the correct decision?**")
    print("")
    print("Limitations:")
    print("- IV values for historical cuts are estimated from Black-Scholes, not recorded.")
    print("- This tests only 2 historical incidents (WDC, STX). Cannot measure false-negative rate")
    print("  (positions where the old rule correctly cut before larger losses).")
    print("- Live position analysis is entry-point only. No 3× breach history available.")
    print("- To answer the backtest question fully, we need: a record of every position that")
    print("  ever hit 3×, what the framework would have said, and the final outcome.")


if __name__ == "__main__":
    main()
