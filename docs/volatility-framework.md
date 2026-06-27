# Volatility Analysis: Framework

## Core Signals

### VIX Level

| VIX Range | Signal for Put Selling |
|-----------|----------------------|
| < 15 | Premiums too cheap, wait |
| 15 - 20 | Collecting premium, neutral |
| 20 - 30 | Rich premiums, good if trending down |
| > 35 | Huge premiums but spike risk is real |

### Term Structure (VIX Futures Curve)

**Contango (VX2 > VX1):** Favorable. Vol sellers earn roll-down. Spread > 0.50 points is healthy.

**Backwardation (VX2 < VX1):** Dangerous. Market prices immediate risk higher than future. Stay out.

### 5-Day Rate of Change

- Negative = volatility subsiding = good entry window
- Flat = neutral
- Positive = fear still building

### Composite Verdict

| Signal | Favorable | Neutral | Unfavorable |
|--------|-----------|---------|-------------|
| VIX Level | 20 - 35 | 15 - 20 | < 15 or > 35 |
| Term Structure | Contango > 0.50 | Contango < 0.50 | Backwardation |
| 5d Change | Negative | Flat | Positive |

- **Favorable**: 3+ green, no red
- **Neutral**: Mixed
- **Unfavorable**: Any backwardation, or 2+ red
