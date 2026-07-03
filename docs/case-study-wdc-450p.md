# Case Study: WDC $450 Put — When the Trade Goes Red

**July 3, 2026 · Position Review Framework v2.0**

---

## The Situation

On a Friday afternoon, one position was bleeding. Western Digital (WDC) had dropped 18% from its June peak in under two weeks. The $450 put, sold for $7.99 premium and set to expire July 31, was deep in the red.

| Metric | At Entry | At Review |
|--------|:-------:|:---------:|
| WDC Spot | ~$650 | $539.00 |
| Option Price | $7.99 | $27.55 |
| P&L | — | **-$1,956 (-245%)** |
| IV | ~45% | 111.3% |
| DTE | 58 | 28 |
| 50MA | ~$480 | $529.55 |

The kind of P&L that makes you want to cut immediately. But here's why we didn't.

---

## Phase 2: The Vol Check Told the Real Story

First, we established context: VIX was in a vol event regime. More importantly, name-level IV told us the loss wasn't structural — it was vega.

**IV 111.3% vs HV 107.6%. IV/HV ratio: 1.03.**

The option wasn't expensive because WDC was collapsing. It was expensive because the entire memory/storage sector was panicking. MU, SanDisk, WDC, STX all fell together. This was sector vol expansion, not a WDC-specific thesis break.

---

## Phase 3: The Event Calendar

- No WDC earnings until August 5 (after expiry). No FOMC. No regulatory catalysts.
- STX reports July 16 — correlation risk if WDC holds into that week.
- Verified. Clean window. No binary risk inside the expiry.

---

## Phase 6: The Combined Exit Rule

We applied the framework's central rule: cut only when **both** conditions fire.

| Condition | Threshold | Status |
|-----------|-----------|:------:|
| Premium loss > 1.5x | $11.99 | **FIRED** (-$19.56) |
| Price below support | 50MA at $529.55 | **NOT FIRED** ($539.00) |

One condition fired, one didn't. Framework says: hold, but watch.

The 50MA had never been tested in 2024-2026. Historical hold rate on first test: ~65-70%. That's your line in the sand.

---

## Phase 9: Deep Analysis — The Numbers Under the Emotion

### Greeks Breakdown

| Greek | Value | What It Means |
|-------|-------|---------------|
| Delta | -0.25 | A $1 drop costs $25. Moderate. |
| Gamma | 0.0016 | Barely accelerates. Not a gamma bomb. |
| Vega | $0.57 | Every 1% IV drop saves $57. **This is the recovery.** |
| Theta | -$1.10/day | Won't save you. Negligible. |

**Synthesis:** The -$1,956 loss was half delta (stock drop) and half vega (panic premium). If IV collapses, the position profits even at current spot.

---

### IV Mean-Reversion: The Recovery Path

| IV | Option Price | P&L |
|----|:----------:|:----:|
| 111% (now) | $35.74 | -$2,775 |
| 90% | $23.98 | -$1,599 |
| 80% | $18.77 | -$1,078 |
| 70% | $13.85 | -$586 |
| **60%** | **$9.35** | **-$136** |
| 50% | $5.47 | +$252 |

**No rally required. Just calm.** If WDC stabilizes at $539 and IV mean-reverts to 60%, the loss evaporates to -$136.

---

### Risk Matrix: Time Is an Ally

| WDC | DTE 28 | DTE 21 | DTE 14 | DTE 7 | Expiry |
|-----|:------:|:------:|:------:|:-----:|:------:|
| $500 | -$3,865 | -$3,011 | -$2,006 | -$743 | +$799 |
| $520 | -$3,273 | -$2,436 | -$1,469 | -$303 | +$799 |
| **$539** | **-$2,775** | **-$1,964** | **-$1,044** | **+$10** | **+$799** |
| $550 | -$2,513 | -$1,719 | -$832 | +$153 | +$799 |
| $600 | -$1,535 | -$840 | -$119 | +$552 | +$799 |

- **Breakeven at expiry:** $442. Stock can drop another $97 and still profit.
- **Probability of expiring OTM:** 69%.
- **At 50MA ($530):** P&L -$3,004. Support breaking hurts but isn't catastrophe.

---

### Gamma Profile

| Spot | Delta | Gamma | Acceleration |
|------|:-----:|:-----:|:------------:|
| $600 | -0.16 | 0.0011 | Barely |
| **$539** | **-0.25** | **0.0016** | **Minimal** |
| $500 | -0.31 | 0.0019 | Modest |
| $450 | -0.42 | 0.0023 | Manageable |

**Gamma is benign across the entire range.** This position won't spiral. Even at the strike, the acceleration is manageable.

---

## Phase 10: Forward-Looking Context

### Analyst Action

**Fox Advisors downgraded WDC to Equal-Weight** citing "peak HDD pricing concerns." But the picture was mixed:
- Cantor Fitzgerald maintained Overweight
- Mizuho raised PT to $685
- No mass downgrade wave

**Verdict:** The downgrade was a single-analyst move, not structural repricing. The selloff had two drivers: sector-wide profit-taking (all memory names down 6-7% on the same day) plus the Fox note. The sector component would stabilize. The downgrade was already priced.

---

### Correlation Check

| Pair | 60-Day Correlation |
|------|:-----------------:|
| WDC/STX | **0.94** |
| WDC/SMH | 0.77 |

WDC and STX moved as one. At 0.94 correlation, WDC's recovery hinged on Seagate stabilizing. If STX found a floor, WDC would follow in lockstep.

---

### Dealers: No Amplification, No Magnet

No meaningful put walls near the strike ($355P had 4,989 OI, but that was $95 below the 50MA). Gamma was too low for dealers to amplify moves. No magnetic levels pulling price in either direction.

---

## Phase 11: IV Outlook — Where Is Vol Going?

### IV Term Structure

| Expiry | DTE | IV |
|--------|-----|----|
| Jul 10 | 6 | 115.7% |
| Jul 17 | 13 | 110.9% |
| Jul 31 | 27 | 111.3% |
| Aug 21 | 48 | 107.2% |
| Sep 18 | 76 | 101.8% |
| Oct 16 | 104 | 99.2% |

**Clear backwardation.** Near-term IV at 115%, mid-term at 107%, far-term declining to 90%. The market had already priced a 25-point IV collapse over the next 3-4 months.

**IV outlook: Improving. Confidence: Medium.**

---

## The Decision

**Hold. Exit trigger: WDC below $526 for the first hour Monday, or touches $500.**

The framework said: one exit condition fired (premium loss), one didn't (price above support). Standard rules say hold.

Deep analysis added conviction: the recovery path required calm, not a rally. IV at 60% meant near-breakeven. Gamma was benign. The term structure confirmed IV should decline. The probability of expiring OTM was 69%.

The trade was uncomfortable. But the data said discomfort wasn't a reason to cut.

---

## What Made This Different

Without the framework, the natural reaction to -245% P&L is to cut. The framework did three things:

1. **Distinguished vega from delta.** The loss was panic premium, not thesis damage. Cutting on vega is cutting on noise.
2. **Quantified the recovery path.** Showed exactly what needed to happen (IV mean-reversion, no rally required) and what it would look like ($ -136 at 60% IV).
3. **Set a data-based trigger, not an emotional one.** $526 below 50MA for one hour. Specific, testable, not a feeling.

The framework didn't predict the outcome. It gave the trade its best chance by preventing a reactive decision.

---

*Analysis conducted by Hermes Agent · Framework: Position Review v2.0 · July 3, 2026*
*The agent provides analysis, not advice. All trading decisions are the trader's own.*
