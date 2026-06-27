# CSP Entry Scanner: Framework

## Philosophy

Only sell CSPs on stocks you are comfortable owning at the strike price in the worst case. That means: profitable, scalable, moated businesses with manageable valuation. Every ticker in the universe must pass this ownership test *before* it ever hits a gate.

If you would not buy 100 shares at the strike and hold for 12 months, do not sell the put.

## The Six Gates

All six must pass for a trade to be flagged as actionable.

### Gate 1: IV Rank >= 50%

**Data source**: Tastytrade `MarketMetricInfo.implied_volatility_index_rank`

IVR >= 50 means current IV sits in the top half of its 52-week range. This is the statistical edge: selling premium when vol is elevated relative to its own history gives mean-reversion tailwind.

### Gate 2: IV > HV (Implied > Realized)

**Data source**: Tastytrade `MarketMetricInfo.iv_hv_30_day_difference`

Precomputed as IV30d minus HV30d. Pass if > 0. Positive means options are pricing more movement than the stock is actually making — you are getting paid for volatility risk that exceeds actual volatility.

### Gate 3: Price Above 200MA

**Data source**: yfinance (price history)

| Tier | Condition | Signal |
|------|-----------|--------|
| Green | Price > 50MA AND Price > 200MA | Uptrend intact |
| Amber | Price > 200MA only | Neutral, proceed with caution |
| Red | Price < 200MA | Skip, broken trend |

### Gate 4: Delta <= 0.10 Strike Exists

**Data source**: yfinance (option chain) + Black-Scholes calculation

Find the nearest expiration in the 30-55 day range (target: 45 DTE). For each put option, calculate delta using Black-Scholes and find the first strike where delta <= 0.10. This is the recommended entry strike.

### Gate 5: Premium Check

At the 0.10 delta strike, display both absolute premium (bid * 100) and return on notional (bid / strike * 100). $75 minimum floor.

### Gate 6 (Soft): IV Direction

Context from Tastytrade's 5-day IV change. Declining IV = optimal entry window. Rising IV = vol still building, may want to wait.

## DTE Strategy

- **Entry**: 45 DTE (or closest in 30-55 day range)
- **Exit**: 50% profit OR 21 DTE, whichever comes first

## Output Format

| Ticker | Price | Strike (d<=0.10) | Prem | Prem% | DTE | IVR | IV/HV | IVd5d | MA | Status |
|--------|-------|-------------------|------|-------|-----|-----|-------|-------|----|--------|

Status codes: READY (all gates pass + IV declining), WATCH (all gates pass + IV rising), FAIL_G1/G2/G3/G4, SKIP, LOW_PREM.
