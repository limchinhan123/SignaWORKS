# Position Review: Framework

## Monitoring Philosophy

CSP management is about distinguishing vega (volatility noise) from delta (thesis damage). Most P&L drawdowns are vega expansion, not structural breakdowns. Cutting on premium loss alone is cutting on noise.

## The Combined Exit Rule

Cut only when **both** conditions fire:

| Condition | Threshold |
|-----------|-----------|
| Premium loss | > 2.5x premium received |
| Underlying price | Below key support (MA50, recent swing low) |

## Vol Context

| VIX | Regime | Implication |
|-----|--------|-------------|
| < 15 | Low vol | P&L is delta. Trust price signals. |
| 15-20 | Normal | Standard framework. |
| 20-25 | Elevated | P&L is vega-heavy. Be more forgiving. |
| 25-30 | Vol event | Don't cut on premium alone. Price must confirm. |
| > 30 | Crisis | Re-evaluate all positions. |

## Name-Level IV Check

| IVR | Meaning |
|-----|---------|
| > 80th | Elevated. Good for entry. Ask *why*. |
| 50-80th | Normal. Standard framework. |
| < 20th | Low. Small premium, large vega risk if vol spikes. |

## Greeks

Delta, gamma, vega, and theta are computed via Black-Scholes for each position. Gamma risk accelerates under 14 DTE. Under 7 DTE, gamma dominates.

## GEX Context

SPY gamma exposure is computed from open interest to identify dealer positioning. Negative net GEX = dealers short gamma = amplifying mode (moves get bigger, reversals get sharper). Positive net GEX = suppressive mode (dealers fade moves, markets grind). Call walls and put walls act as magnetic levels.

## Deliverable Structure

1. **Conclusion** — one sentence verdict
2. **Vol Environment** — VIX, GEX regime
3. **Positions** — lean table with buffer, DTE, P&L, status
4. **Alerts** — positions needing attention
5. **Forward Look** — theta projections, scenarios for underwater positions
6. **Key Levels** — strike, MA50, delta-30 equivalent
