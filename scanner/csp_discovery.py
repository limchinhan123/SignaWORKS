#!/usr/bin/env python3
"""
CSP Discovery — Weekly Tastytrade Pre-Screening

Reads csp_universe.json, batches tickers through Tastytrade API,
filters for liquidity >= 2, IVR >= 50%, IV/HV > 0.
Survivors saved to csp_candidates.json for subsequent on-demand scanning.

Usage:
    python3 csp_discovery.py                     # read universe, output candidates
    python3 csp_discovery.py --output -          # print to stdout

Rate limits: 2 req/s market data, 100 symbols per request.
"""

import asyncio
import json
import os
import sys

ENV_CS = os.environ.get("TASTYTRADE_CLIENT_SECRET", "")
ENV_RT = os.environ.get("TASTYTRADE_REFRESH_TOKEN", "")
ENV_CREDS = os.environ.get("TASTYTRADE_CREDS", "")

UNIVERSE_FILE = os.environ.get("CSP_UNIVERSE_FILE", "data/csp_universe.json")
CANDIDATES_FILE = os.environ.get("CSP_CANDIDATES_FILE", "data/csp_candidates.json")
BATCH_SIZE = 100


def load_creds():
    if ENV_CREDS:
        cs, rt = ENV_CREDS.split(":", 1)
        return {"cs": cs, "rt": rt}
    if ENV_CS and ENV_RT:
        return {"cs": ENV_CS, "rt": ENV_RT}
    creds_file = os.environ.get("TASTYTRADE_CREDS_FILE", "")
    if not creds_file or not os.path.exists(creds_file):
        sys.exit(
            "FATAL: Set TASTYTRADE_CLIENT_SECRET + TASTYTRADE_REFRESH_TOKEN, "
            "or TASTYTRADE_CREDS=cs:rt, or TASTYTRADE_CREDS_FILE path"
        )
    creds = {}
    with open(creds_file) as f:
        for line in f:
            line = line.strip()
            if line.startswith("TASTYTRADE_CLIENT_SECRET="):
                creds["cs"] = line.split("=", 1)[1]
            elif line.startswith("TASTYTRADE_REFRESH_TOKEN="):
                creds["rt"] = line.split("=", 1)[1]
    return creds


def load_universe():
    try:
        with open(UNIVERSE_FILE) as f:
            data = json.load(f)
        return data.get("tickers", [])
    except FileNotFoundError:
        return []


async def fetch_batch(session, symbols):
    from tastytrade import metrics as tt_metrics
    import time
    start = time.monotonic()
    data = await tt_metrics.get_market_metrics(session, symbols)
    elapsed = time.monotonic() - start
    return data, elapsed


async def main():
    from tastytrade import Session

    tickers = load_universe()
    if not tickers:
        print(json.dumps({"error": "No tickers in universe"}))
        return

    creds = load_creds()
    session = Session(creds["cs"], creds["rt"])

    all_metrics = []
    for i in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[i : i + BATCH_SIZE]
        data, elapsed = await fetch_batch(session, batch)
        all_metrics.extend(data)
        if elapsed < 0.5:
            await asyncio.sleep(0.5 - elapsed)

    try:
        await session._client.aclose()
    except Exception:
        pass

    survivors = []
    for item in all_metrics:
        liq = item.liquidity_rating
        ivr = float(item.implied_volatility_index_rank) if item.implied_volatility_index_rank else None
        iv_hv = float(item.iv_hv_30_day_difference) if item.iv_hv_30_day_difference else None
        iv5d = float(item.implied_volatility_index_5_day_change) if item.implied_volatility_index_5_day_change else None

        if liq is None or liq < 2:
            continue
        if ivr is None or ivr < 0.50:
            continue
        if iv_hv is None or iv_hv <= 0:
            continue

        survivors.append({
            "symbol": item.symbol,
            "ivr": round(ivr, 4),
            "iv_hv_diff": round(iv_hv, 2),
            "iv_30d": round(float(item.implied_volatility_30_day), 2) if item.implied_volatility_30_day else None,
            "hv_30d": round(float(item.historical_volatility_30_day), 2) if item.historical_volatility_30_day else None,
            "iv_5d_change": round(iv5d, 4) if iv5d is not None else None,
            "liquidity": liq,
            "beta": round(float(item.beta), 2) if item.beta else None,
        })

    output = {
        "scanned": len(tickers),
        "survivors": len(survivors),
        "tickers": survivors,
        "generated_at": __import__("datetime").datetime.now().isoformat(),
    }

    if "--output" in sys.argv:
        dest = sys.argv[sys.argv.index("--output") + 1] if "--output" in sys.argv else None
    else:
        dest = CANDIDATES_FILE

    if dest == "-" or not dest:
        print(json.dumps(output, indent=2))
    else:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w") as f:
            json.dump(output, f, indent=2)
        print(f"Written {len(survivors)} candidates to {dest}")


if __name__ == "__main__":
    asyncio.run(main())
