# Position Review: Framework

## Monitoring Philosophy

CSP management is about distinguishing vega (volatility noise) from delta (thesis damage). Most P&L drawdowns are vega expansion, not structural breakdowns. Cutting on premium loss alone is cutting on noise.

This framework covers the full lifecycle: extraction → triage → exit decisions → deep analysis → forward-looking context → IV outlook.

---

## Phase 1: Extract & Structure

From screenshots or manual entry, build a position table:

| Ticker | Strike | Expiry | DTE | Delta | Beta | Premium Est. | U-P&L | U-P&L% | Urgency |
|--------|--------|--------|-----|-------|------|-------------|--------|--------|---------|

**Urgency tiers:**
- **Critical:** DTE ≤ 7, or U-P&L% > 70% with DTE ≤ 14
- **Watch:** DTE ≤ 14, or U-P&L% > 50%
- **Stable:** Everything else

---

## Phase 2: Vol Environment

| VIX | Regime | Implication |
|-----|--------|-------------|
| <15 | Low vol | P&L is delta. Trust price signals. |
| 15-20 | Normal | Standard framework. Mixed vega/delta. |
| 20-25 | Elevated | P&L is vega-heavy. Be more forgiving of premium losses. |
| 25-30 | Vol event | DO NOT cut on premium loss alone. Price must confirm. |
| >30 | Crisis | Short-vol thesis challenged. Re-evaluate all. |

**Name-level IV:** For Watch/Critical positions, check IV Rank and IV/HV spread. IV/HV inverted (IV < HV by 5+ points) = underpriced risk. IV >> HV = edge intact.

---

## Phase 3: Earnings & Event Risk

Flag any binary event (earnings, FOMC, regulatory) inside the DTE window. DTE ≤ 7 regardless of events: gamma dominates, decide today.

---

## Phase 4: Portfolio-Level Check

Sector concentration (>60% in one sector), expiry clustering (>50% same week), outlier betas (>3.0), position sizing discrepancies.

---

## Phase 5: Position-Level Analysis

For each position in urgency order: distance to strike, delta check (> -0.25 = gamma waking, > -0.40 = delta trade, not vol trade), DTE urgency.

---

## Phase 6: The Combined Exit Rule

| Condition | Threshold |
|-----------|-----------|
| Premium loss | > 2.0x premium received |
| Underlying price | Below key support |

**Cut only when BOTH fire.**

---

## Phase 7: Research Support Levels

Key moving averages (50MA, 200MA), recent swing lows, volume profile, round numbers. Minimum 5% buffer above strike.

---

## Phase 8: Deliverable

Lead with conclusion. Structure: Conclusion → Vol snapshot → Position table → Portfolio flags → Action items → One question.

---

## Phase 9: Deep Analysis (Critical Positions Only)

Six quantified components deployed when the framework gives ambiguous results or P&L is extreme:

**9a. Greeks Breakdown** with plain-English interpretation table. Shows whether P&L is delta or vega.

**9b. Risk Matrix** (P&L at various prices × DTE). 6-8 row grid. Breakeven at expiry. Probability of OTM.

**9c. IV Mean-Reversion Scenarios** — the most important analysis for vega-dominated positions. Shows recovery path requiring calm, not a rally.

**9d. 1-Day Shock Scenarios** — delta + gamma P&L for ±1-5% moves. Shows asymmetry.

**9e. Gamma Profile** — maps gamma at different spots to show where acceleration becomes dangerous.

**9f. Breakeven Paths** — realistic spot/IV combinations that get back to cost basis.

---

## Phase 10: Forward-Looking Context

**10a. Dealer Positioning / GEX** — zero gamma flip point, call/put walls. Where are dealer flows amplifying vs dampening?

**10b. Expected Move vs Actual** — is the options market underpricing or overpricing risk?

**10c. Analyst Action / Narrative Shift** — downgrades, price target cuts. Structural repricing or noise?

**10d. Correlation Check** — with sector ETF and peer names. Is recovery name-specific or sector-dependent?

---

## Phase 11: IV Outlook

For vega-heavy positions: where is IV going?

**11a. IV Term Structure** — IV across all expiries. Backwardation (near > far) = market expects vol to collapse. Contango = no relief priced in.

**11b. Historical IV Analogs** — when IV last hit this level, median time to revert. Data-based timeline.

**Verdict:** "IV outlook: improving/worsening/stable over next X days."

---

## Deliverable Format

**Conclusion and action first. Always.** Verdict → Action → One-paragraph summary → Then the detailed phases.

The reader should know what to do in the first 5 lines.

---

## Companion Tools

All computational functions live in `pricing.py` (repo root). The single shared module covers Black-Scholes Greeks, risk matrices, IV scenarios, shock analysis, gamma profiles, breakeven analysis, IV term structure, historical analogs, and correlation — imported by both `csp_scanner.py` and `position_review.py`.
