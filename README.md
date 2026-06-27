# CSP Options Toolkit

A systematic income-generation toolkit for selling cash-secured puts (CSPs). Built for precision, not gambling.

## What This Is

Five Python scripts and a documented framework that automate the entire CSP lifecycle:

1. **Discovery** — weekly pre-screening of a curated universe through volatility and liquidity gates
2. **Entry Scanning** — six-gate Black-Scholes filter that finds the optimal strike at 45 DTE
3. **Position Monitoring** — three-layer trigger system (MA50, loss threshold, IV noise)
4. **News Monitoring** — daily RSS headline check filtering for material events only
5. **Weekly Review** — full Greek analysis, GEX context, theta projections, and key levels

Plus three documented frameworks: entry strategy, position review methodology, and volatility context.

## Architecture

```
csp-options-toolkit/
├── scanner/
│   ├── csp_scanner.py          # 6-gate entry scanner (Tastytrade + yfinance)
│   └── csp_discovery.py        # Weekly pre-screener (Tastytrade-only, 100 symbols)
├── monitors/
│   ├── position_monitor.py     # 3-layer trigger monitor (Google Sheets)
│   └── position_news.py        # RSS headline filter for material events
├── review/
│   └── position_review.py      # Greeks + GEX + forward look (Tastytrade + yfinance + Google Sheets)
├── docs/
│   ├── entry-scanner-framework.md
│   ├── position-review-framework.md
│   └── volatility-framework.md
├── data/
│   └── csp_universe.json       # Curated ticker universe (sample: 60 names)
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## The Framework

### Entry: Six Gates

A trade must pass all six gates. No exceptions.

| Gate | Signal | Source |
|------|--------|--------|
| 1. IV Rank >= 50% | Vol in top half of 52-week range | Tastytrade |
| 2. IV > HV | Options pricing more risk than realized | Tastytrade |
| 3. Price > 200MA | Trend intact, assignment risk contained | yfinance |
| 4. Delta <= 0.10 | Black-Scholes delta at entry strike | yfinance + scipy |
| 5. Premium >= $75 | Minimum after commissions | yfinance |
| 6. IV Direction | Declining = optimal, rising = watch | Tastytrade |

This is not a screener that throws 50 tickers at you. The universe is deliberately curated: profitable, scaled, moated businesses. If you would not buy 100 shares at the strike and hold for 12 months, do not sell the put.

### Exit: The Combined Rule

Cut only when **both** conditions fire:

- Premium loss exceeds 2.5x credit received
- Underlying breaks below key support (MA50 or recent swing low)

Single-trigger exits are noise. The double trigger distinguishes vega expansion (vol event, thesis intact) from structural breakdown (thesis broken).

### Context: VIX + GEX

The review module self-computes SPY gamma exposure from option chain open interest. Dealer positioning determines the amplification regime:

- **Negative GEX (amplifying)**: Dealers short gamma, chasing direction. Moves get bigger.
- **Positive GEX (suppressive)**: Dealers long gamma, fading moves. Markets grind.
- **Gamma flip**: The price where regime switches. Cross it and behavior changes.

VIX futures term structure provides the vol regime backdrop: contango is favorable, backwardation is a warning.

## Technical Implementation

### Self-Computed Greeks

All Greeks are computed via Black-Scholes. No paid market data needed for delta, gamma, vega, or theta.

```python
def bs_greeks(spot, strike, dte, iv, rate=0.0425, option_type='put'):
    T = max(dte / 365.0, 1/365.0)
    d1 = (math.log(spot/strike) + (rate + iv**2/2)*T) / (iv * math.sqrt(T))
    d2 = d1 - iv * math.sqrt(T)
    delta = norm_cdf(d1) - 1  # put delta
    gamma = norm_pdf(d1) / (spot * iv * math.sqrt(T))
    vega = spot * math.sqrt(T) * norm_pdf(d1) / 100
    theta = (-spot * iv * norm_pdf(d1) / (2*math.sqrt(T))
             - rate * strike * math.exp(-rate*T) * norm_cdf(-d2)) / 365
    return delta, gamma, vega, theta
```

### Self-Computed GEX

SPY gamma exposure is computed from yfinance open interest data, not from a paid service. The code iterates over near-dated options, computes gamma per strike, multiplies by OI and spot, and accumulates the net profile. Call wall, put wall, gamma flip, and regime classification are all derived from public data.

### Materiality Filter

The news monitor uses a two-pass filter. First, skip patterns eliminate generic market wrap-up headlines ("stocks rise on...", "why X is falling..."). Second, keyword classification catches actual material events (earnings, guidance, M&A, leadership changes, regulatory actions). Result: 15 headlines that matter, not 150 that don't.

## Design Decisions

**Why Tastytrade?** The `MarketMetricInfo` endpoint returns IV Rank, IV/HV spread, five-day IV change, and liquidity rating in a single API call. These are series-level metrics that yfinance does not provide. The pre-screening step — filtering 60 tickers to a shortlist — uses only this call, zero tokens.

**Why yfinance for options?** During the discovery phase, options don't need to be priced to the penny. Black-Scholes delta with yfinance chain data is sufficient for strike selection. Tastytrade fills the gap where yfinance is weak (IV metrics); yfinance fills the gap where Tastytrade is slow (per-ticker option chains).

**Why Black-Scholes instead of a pricing library?** Zero dependencies. The math is 20 lines. For European-style index options, BS is accurate. For American-style equity puts, the delta difference is small enough that a 0.10 threshold already absorbs it.

**Why a curated universe instead of screening the entire market?** A mechanical filter on 6,000 tickers produces noise. The CSP thesis rests on owning quality businesses at prices you accept. Every name in the universe passes that test before it reaches Gate 1.

## Dependencies

```
numpy, scipy, pandas, yfinance, tastytrade
google-auth, google-api-python-client  # for Trade Ledger
requests  # for RSS
```

## Setup

```bash
cp .env.example .env
# Edit .env with your Tastytrade credentials and Google Sheet ID
pip install -r requirements.txt
```

## Usage

```bash
# Weekly pre-screen (Sunday evening)
python3 scanner/csp_discovery.py

# Full 6-gate scan
python3 scanner/csp_scanner.py

# Daily position monitoring
python3 monitors/position_monitor.py
python3 monitors/position_news.py

# Weekly review (Saturday morning)
python3 review/position_review.py
```

## Limitations

- yfinance option chain data lags 15-20 minutes during market hours
- Black-Scholes assumes European exercise; American put delta is slightly higher
- GEX from open interest is an approximation (some OI is hedged, not directional)
- News filter catches headlines, not the article body
- Tastytrade API has 2 req/s rate limit and 100 symbols per call
- No earnings awareness in the scanner (future enhancement)
- This toolkit screens and monitors; it does not execute trades or size positions

## License

MIT
