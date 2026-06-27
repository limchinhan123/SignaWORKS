#!/usr/bin/env python3
"""
SignaWORKS Demo — Offline Walkthrough

Recreates the scanner output from pre-saved data. No API keys needed.
Reads csp_candidates.json (Discovery output) and csp_universe.json,
then simulates the full 6-gate scan with pre-computed results.

Usage:
    python3 demo/demo.py
    python3 demo/demo.py --quick    (short version)
"""

import json
import os
import sys

DEMO_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(DEMO_DIR)

# ─── Pre-computed scan results (from live June 27 test) ─────────────────────────

DEMO_RESULTS = {
    "actionable": [
        {"symbol": "TSM",   "price": 432.35, "strike": 340, "prem_abs": 482, "prem_pct": 1.42, "dte": 55, "ivr": 0.81, "iv_hv": 9.0, "iv_dir": "↓0.8%", "ma_tier": "green", "oi": 3152, "beta": 1.4, "status": "READY"},
        {"symbol": "JNJ",   "price": 254.66, "strike": 220, "prem_abs": 113, "prem_pct": 0.51, "dte": 55, "ivr": 0.71, "iv_hv": 5.8, "iv_dir": "↓0.5%", "ma_tier": "green", "oi": 972,  "beta": 0.3, "status": "READY"},
        {"symbol": "GE",    "price": 369.00, "strike": 300, "prem_abs": 276, "prem_pct": 0.92, "dte": 55, "ivr": 0.51, "iv_hv": 4.5, "iv_dir": "↓1.2%", "ma_tier": "green", "oi": 579,  "beta": 1.4, "status": "READY"},
        {"symbol": "QCOM",  "price": 189.39, "strike": 135, "prem_abs": 276, "prem_pct": 2.04, "dte": 55, "ivr": 0.71, "iv_hv": 17.2,"iv_dir": "↓3.3%", "ma_tier": "amber", "oi": 837,  "beta": 1.5, "status": "READY_AMBER"},
        {"symbol": "AMD",   "price": 521.58, "strike": 370, "prem_abs": 948, "prem_pct": 2.56, "dte": 55, "ivr": 0.98, "iv_hv": 18.6,"iv_dir": "↑5.7%", "ma_tier": "green", "oi": 2704, "beta": 3.0, "status": "WATCH"},
        {"symbol": "ASML",  "price": 1794.62,"strike":1360, "prem_abs":2430, "prem_pct": 1.79, "dte": 55, "ivr": 0.87, "iv_hv": 4.1, "iv_dir": "↑2.6%", "ma_tier": "green", "oi": 43,   "beta": 1.5, "status": "WATCH"},
        {"symbol": "AMAT",  "price": 626.84, "strike": 430, "prem_abs":1155, "prem_pct": 2.69, "dte": 55, "ivr": 1.06, "iv_hv": 10.3,"iv_dir": "↑3.3%", "ma_tier": "green", "oi": 307,  "beta": 1.7, "status": "WATCH"},
        {"symbol": "LRCX",  "price": 379.09, "strike": 260, "prem_abs": 718, "prem_pct": 2.76, "dte": 55, "ivr": 1.03, "iv_hv": 8.0, "iv_dir": "↑3.1%", "ma_tier": "green", "oi": 686,  "beta": 1.9, "status": "WATCH"},
        {"symbol": "KLAC",  "price": 248.64, "strike": 170, "prem_abs": 320, "prem_pct": 1.88, "dte": 55, "ivr": 0.96, "iv_hv": 7.8, "iv_dir": "↑7.2%", "ma_tier": "green", "oi": 1651, "beta": 1.5, "status": "WATCH"},
        {"symbol": "CRWD",  "price": 701.09, "strike": 540, "prem_abs": 838, "prem_pct": 1.55, "dte": 55, "ivr": 0.52, "iv_hv": 10.9,"iv_dir": "↑4.0%", "ma_tier": "green", "oi": 1243, "beta": 1.1, "status": "WATCH"},
        {"symbol": "LLY",   "price":1208.12, "strike": 980, "prem_abs": 898, "prem_pct": 0.92, "dte": 55, "ivr": 0.61, "iv_hv": 14.1,"iv_dir": "↑1.2%", "ma_tier": "green", "oi": 296,  "beta": 0.5, "status": "WATCH"},
        {"symbol": "ABBV",  "price": 253.35, "strike": 210, "prem_abs": 114, "prem_pct": 0.54, "dte": 55, "ivr": 0.61, "iv_hv": 7.9, "iv_dir": "→",     "ma_tier": "green", "oi": 2071, "beta": 0.3, "status": "WATCH"},
        {"symbol": "QQQ",   "price": 706.52, "strike": 600, "prem_abs": 512, "prem_pct": 0.85, "dte": 55, "ivr": 0.81, "iv_hv": 6.2, "iv_dir": "↑5.4%", "ma_tier": "green", "oi": 8085, "beta": 1.2, "status": "WATCH"},
        {"symbol": "SMH",   "price": 611.61, "strike": 460, "prem_abs": 852, "prem_pct": 1.85, "dte": 55, "ivr": 0.96, "iv_hv": 5.0, "iv_dir": "↑1.7%", "ma_tier": "green", "oi": 5166, "beta": 1.7, "status": "WATCH"},
        {"symbol": "AAPL",  "price": 283.78, "strike": 240, "prem_abs": 178, "prem_pct": 0.74, "dte": 55, "ivr": 0.72, "iv_hv": 15.9,"iv_dir": "↑1.1%", "ma_tier": "amber", "oi": 7258, "beta": 1.1, "status": "WATCH_AMBER"},
        {"symbol": "GOOGL", "price": 337.39, "strike": 280, "prem_abs": 248, "prem_pct": 0.89, "dte": 55, "ivr": 0.64, "iv_hv": 15.6,"iv_dir": "↑2.9%", "ma_tier": "amber", "oi": 1879, "beta": 1.2, "status": "WATCH_AMBER"},
        {"symbol": "CAT",   "price": 997.47, "strike": 780, "prem_abs": 865, "prem_pct": 1.11, "dte": 55, "ivr": 0.81, "iv_hv": 5.0, "iv_dir": "↑1.5%", "ma_tier": "green", "oi": 1165, "beta": 1.6, "status": "WATCH"},
        {"symbol": "HON",   "price": 232.21, "strike": 195, "prem_abs": 172, "prem_pct": 0.89, "dte": 55, "ivr": 0.80, "iv_hv": 10.8,"iv_dir": "↑1.5%", "ma_tier": "green", "oi": 540,  "beta": 0.8, "status": "WATCH"},
        {"symbol": "RTX",   "price": 187.99, "strike": 155, "prem_abs": 83,  "prem_pct": 0.54, "dte": 55, "ivr": 0.65, "iv_hv": 12.2,"iv_dir": "↑4.1%", "ma_tier": "green", "oi": 5873, "beta": 0.3, "status": "WATCH"},
        {"symbol": "DE",    "price": 613.24, "strike": 500, "prem_abs": 270, "prem_pct": 0.54, "dte": 55, "ivr": 0.63, "iv_hv": 2.3, "iv_dir": "↑2.1%", "ma_tier": "green", "oi": 113,  "beta": 0.9, "status": "WATCH"},
        {"symbol": "PG",    "price": 149.02, "strike": 125, "prem_abs": 38,  "prem_pct": 0.30, "dte": 55, "ivr": 0.51, "iv_hv": 3.9, "iv_dir": "↑1.6%", "ma_tier": "green", "oi": 403,  "beta": 0.4, "status": "LOW_PREM"},
    ],
    "failed": [
        {"symbol": "MU",    "gate": "FAIL_G2", "reason": "IV-HV=-9.7 (HV > IV, no premium edge)"},
        {"symbol": "MSFT",  "gate": "FAIL_G3", "reason": "$372.97 < 200MA $447.99 (broken trend)"},
        {"symbol": "META",  "gate": "FAIL_G3", "reason": "$550.25 < 200MA $650.02"},
        {"symbol": "NVDA",  "gate": "FAIL_G1", "reason": "IVR=22% (no vol opportunity)"},
        {"symbol": "COST",  "gate": "FAIL_G1", "reason": "IVR=39%"},
        {"symbol": "BLK",   "gate": "SKIP",    "reason": "Liquidity=1 (too thin)"},
    ],
    "scan_date": "2026-06-27",
    "universe_size": 48,
    "actionable_count": 21,
}


def print_banner():
    print("""
   ▄▄▄▄▄   ▄  ▄▄█▄▄  ▄█▄   ▄▄▄▄▄        ▄  ▄▄▄▄▄▄▄  ▄▄▄▄   ▄ ▄▄  ▄▄▄▄▄
  █     ▀▄ █ █▀   ▀ █▀ ▀▄ █       ▄     ▄█  █   ▄▄▄█ █   █  █ █  █▀   ▀
 ▄  ▀▀▀▀▄  █ █      █   █ █    █▄█▄█▄█▄█ █  █   ███ █   █  █▄▀  ▀▀▀▀▄
 █ ▄▄▄▄▄ ▀ █ █      █▄ ▄█ █▄▄▄ ▄▄ ▄▄ ▄▄  █  █▄▄▄▄▄█ █▄▄▄▀▄▄█    ▄▄▄▄█▀
 █    ▀█  █ █▄   ▄ █▀ ▀█ █   ▀█   █   █  █  █▄▄▄▄▄█ █   ▀  █   █
 ▀▄▄▄▄▀▀  █  ▀▄▄▄▀ █   █  ▄▄▄▀▀█▄ █▄▄▄█  █  ▄▄▄▄▄ ▀      █    ▀▄▄▄▄▀
          █▀        █▄ ▄█     █  █   █  █                          █
                              ▀          ▀                          ▀
    """)


def print_markdown_table(results: list, scan_date: str):
    """Print a GitHub-flavored markdown table of actionable results."""

    header = "| Ticker | Price | Strike | Prem | Prem% | DTE | IVR | IV/HV | IVΔ5d | MA | OI | β | Status |"
    sep    = "|--------|-------|--------|------|-------|-----|-----|-------|-------|----|----|----|--------|"

    lines = [
        f"## Live Scan — {scan_date}",
        "",
        f"**{len(results)} actionable setups from 48-ticker universe**",
        "",
        header,
        sep,
    ]

    for r in results:
        ma_icon = {"green": "🟢", "amber": "🟡", "red": "🔴"}.get(r["ma_tier"], "?")
        oi = r["oi"]
        beta = r["beta"]
        lines.append(
            f"| {r['symbol']} | ${r['price']:.2f} | {r['strike']}P | ${r['prem_abs']:.0f} | "
            f"{r['prem_pct']:.2f}% | {r['dte']}d | {r['ivr']:.0%} | "
            f"{r['iv_hv']:+.1f} | {r['iv_dir']} | {ma_icon} | {oi} | {beta} | **{r['status']}** |"
        )

    return "\n".join(lines)


def print_failed_table(failed: list):
    lines = [
        "",
        "### Gate Failures (selected)",
        "",
        "| Ticker | Gate | Reason |",
        "|--------|------|--------|",
    ]
    for f in failed:
        lines.append(f"| {f['symbol']} | {f['gate']} | {f['reason']} |")
    return "\n".join(lines)


def main():
    args = sys.argv[1:]

    if "--quick" in args:
        print("## Quick Demo — TSM")
        r = next(r for r in DEMO_RESULTS["actionable"] if r["symbol"] == "TSM")
        print(f"Price: ${r['price']:.2f}")
        print(f"Strike (Δ≤0.10): {r['strike']}P")
        print(f"Premium: ${r['prem_abs']:.0f} ({r['prem_pct']:.2f}% on notional)")
        print(f"IV Rank: {r['ivr']:.0%} — volatility is elevated relative to its 52-week history")
        print(f"IV direction: {r['iv_dir']} — vol spike is receding (optimal entry window)")
        print(f"Status: READY — all 6 gates pass, enter at 45 DTE")
        return

    print_banner()
    print()
    print(print_markdown_table(DEMO_RESULTS["actionable"], DEMO_RESULTS["scan_date"]))
    print()
    print(print_failed_table(DEMO_RESULTS["failed"]))
    print()
    print("*Weekend data (Friday June 26 close). Nearest expiry: Aug 21 (55 DTE).*")
    print("*Monday will show fresh 45 DTE matches.*")


if __name__ == "__main__":
    main()
