<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Data-Tastytrade-orange?logo=chartdot" alt="TastyTrade">
  <img src="https://img.shields.io/badge/Pricing-Black--Scholes-purple?logo=scipy" alt="Black-Scholes">
  <img src="https://img.shields.io/badge/Built_by-Hermes_Agent-ff66c4?logo=robotframework" alt="Hermes">
  <img src="https://img.shields.io/badge/Model-DeepSeek_4.0_Pro-4c6ef5?logo=deepin" alt="DeepSeek">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
</p>

# SignaWORKS

**A systematic options income toolkit. Precision, not gambling. A framework for people who want to trade based on system, not emotion**

You're selling insurance on assets you actually want to own, using a statistical edge that has nothing to do with guessing direction. Every trade survives six independent gates before it reaches your eyes. What you do with it is your decision. The toolkit only surfaces what's worth looking at. When things go wrong — and they will — it gives you something better than a sell button: it shows you what's actually happening under the P&L and recommend best course of actions. 

<p align="center">
  <img src="demo/demo.gif" alt="SignaWORKS Demo" width="800">
  <br>
  <sub><i>Live scan: 21 actionable setups from a 48-ticker universe. Dracula theme courtesy of asciinema + agg.</i></sub>
</p>

---

## Philosophy

Here's the thing about options: your brain is wired to panic. A -245% P&L feels like an emergency. Your pulse spikes. Your fingers hover over the sell button. Every instinct screams *get out.*

Most of the time, that instinct is wrong.

Most underwater positions aren't dying. They're just expensive because the market is scared. The stock didn't break. The thesis didn't fail. The vol market had a panic attack and your position's P&L is the collateral damage. Cutting here isn't discipline. It's paying someone else's panic premium.

SignaWORKS exists to put something between your instincts and your brokerage account. Not because you don't know what you're doing, but because nobody thinks clearly when their position is bleeding.

The framework starts from one principle: **only sell puts on stocks you'd be comfortable owning at the strike for > 12 months.** If the name doesn't pass that test, it never enters the universe. This isn't a screener for maximum premium. It's a filter for sleep.

From there:

- **Gate 1:** IV Rank ≥ 50% — sell premium when vol is elevated relative to its own 52-week history. Statistical edge from mean reversion. If everyone's calm, so are you. Wait.
- **Gate 2:** IV > HV — options are pricing more movement than the stock is actually making. You're selling insurance at a markup. When the markup disappears, you don't sell.
- **Gate 3:** Price above 200MA — bearish trend breaks the thesis. Below 200MA, assignment risk is asymmetric. This gate alone would have kept you out of half the losing trades you'll ever see.
- **Gate 4:** Delta ≤ 0.10 — ~90% probability the put expires worthless, computed via Black-Scholes, not yfinance's approximation. You're not guessing direction. You're selling time and probability.
- **Gate 5:** Premium display — absolute dollars and return on notional. No hard floor beyond $75 (commissions eat thinner trades). Sometimes 0.5% on a sleepy name with declining vol is better than 2.5% on a volatile name still surging.
- **Gate 6 (soft):** IV direction — declining vol is the optimal entry window. Rising vol means the spike is still building. READY vs WATCH.

**48 tickers. 6 gates. 21 actionable. No opinions, no gut feels, no "I think the market is going to..."** If it doesn't pass the gates, it doesn't reach your eyes.

---

## Live Demo

Run the offline demo (no API keys needed):

```bash
python3 demo/demo.py         # Full scan with results table
python3 demo/demo.py --quick # Single-ticker walkthrough (TSM)
```

**What you'll see — real output from June 27 scan:**

### Actionable Setups (21 of 48 tickers)

| Ticker | Price | Strike | Prem | Prem% | DTE | IVR | IV/HV | IVΔ5d | MA | OI | β | Status |
|--------|-------|--------|------|-------|-----|-----|-------|-------|----|----|----|--------|
| TSM | $432.35 | 340P | $482 | 1.42% | 55d | 81% | +9.0 | ↓0.8% | 🟢 | 3152 | 1.4 | **READY** |
| JNJ | $254.66 | 220P | $113 | 0.51% | 55d | 71% | +5.8 | ↓0.5% | 🟢 | 972 | 0.3 | **READY** |
| GE | $369.00 | 300P | $276 | 0.92% | 55d | 51% | +4.5 | ↓1.2% | 🟢 | 579 | 1.4 | **READY** |
| AMD | $521.58 | 370P | $948 | 2.56% | 55d | 98% | +18.6 | ↑5.7% | 🟢 | 2704 | 3.0 | **WATCH** |
| AMAT | $626.84 | 430P | $1155 | 2.69% | 55d | 106% | +10.3 | ↑3.3% | 🟢 | 307 | 1.7 | **WATCH** |
| LRCX | $379.09 | 260P | $718 | 2.76% | 55d | 103% | +8.0 | ↑3.1% | 🟢 | 686 | 1.9 | **WATCH** |
| QQQ | $706.52 | 600P | $512 | 0.85% | 55d | 81% | +6.2 | ↑5.4% | 🟢 | 8085 | 1.2 | **WATCH** |
| LLY | $1208.12 | 980P | $898 | 0.92% | 55d | 61% | +14.1 | ↑1.2% | 🟢 | 296 | 0.5 | **WATCH** |
| SMH | $611.61 | 460P | $852 | 1.85% | 55d | 96% | +5.0 | ↑1.7% | 🟢 | 5166 | 1.7 | **WATCH** |
| AAPL | $283.78 | 240P | $178 | 0.74% | 55d | 72% | +15.9 | ↑1.1% | 🟡 | 7258 | 1.1 | **WATCH_AMBER** |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

### Gate Failures (selected)

| Ticker | Gate | Reason |
|--------|------|--------|
| MU | FAIL_G2 | IV-HV=-9.7 — realized vol exceeds implied (no premium edge) |
| MSFT | FAIL_G3 | Price below 200MA — broken trend |
| META | FAIL_G3 | Price below 200MA |
| NVDA | FAIL_G1 | IVR=22% — no vol opportunity here |
| BLK | SKIP | Liquidity=1 — spreads too wide |

**Status codes:** READY = all gates pass + IV declining (optimal) · WATCH = all gates pass + IV still rising (may improve) · _AMBER = price below 50MA (caution) · FAIL_GX = which gate rejected it

DTE strategy: **45 DTE entry → 50% profit or 21 DTE exit** (whichever first).

---

## Architecture

```
                              ┌──────────────────────────┐
                              │     csp_universe.json     │
                              │  48 quality tickers,      │
                              │  8 sectors, 5 ETFs        │
                              └────────────┬─────────────┘
                                           │
                          ┌────────────────┴────────────────┐
                          │                                  │
                          ▼                                  ▼
           ┌──────────────────────────┐      ┌──────────────────────────┐
           │    csp_discovery.py      │      │     csp_scanner.py       │
           │    Weekly Pre-Screen     │      │     On-Demand 6-Gate     │
           │                          │      │                          │
           │  • Tastytrade API        │      │  • Tastytrade (G1,G2)    │
           │  • Liquidity ≥ 2         │      │  • yfinance (G3, price)   │
           │  • IVR ≥ 50%             │      │  • Black-Scholes (G4)    │
           │  • IV/HV > 0             │      │  • Premium display (G5)  │
           │                          │      │  • IV direction (G6)     │
           └───────────┬──────────────┘      └───────────┬──────────────┘
                       │                                  │
                       ▼                                  ▼
           ┌──────────────────────────┐      ┌──────────────────────────┐
           │   csp_candidates.json    │      │    Markdown Table        │
           │   Surviving tickers      │─────▶│    + JSON Output         │
           │   for detailed scan      │      │                          │
           └──────────────────────────┘      └──────────────────────────┘
```

```
 ╔═══════════════════════════════════════════════════════════════════════╗
 ║                    POSITION REVIEW FRAMEWORK                          ║
 ║                    11 Phases · Non-Binary Decisions                   ║
 ╠═══════════════════════════════════════════════════════════════════════╣
 ║                                                                       ║
 ║  ┌──────────────────────┐    ┌──────────────────────┐                ║
 ║  │ PHASES 1-4: TRIAGE   │    │ PHASES 5-8: DECISION │                ║
 ║  │                      │    │                      │                ║
 ║  │ 1. Extract positions │    │ 5. Position analysis │                ║
 ║  │ 2. Vol environment   │───▶│ 6. Combined exit rule│───▶ ACTION     ║
 ║  │ 3. Event risk scan   │    │ 7. Support levels    │                ║
 ║  │ 4. Portfolio check   │    │ 8. Deliver verdict   │                ║
 ║  └──────────────────────┘    └──────────────────────┘                ║
 ║            │                          │                               ║
 ║            │                          │ AMBIGUOUS?                    ║
 ║            │                          ▼                               ║
 ║            │              ┌──────────────────────┐                   ║
 ║            │              │ PHASES 9-11: DEPTH   │                   ║
 ║            │              │                      │                   ║
 ║            │              │ 9.  Deep analysis    │                   ║
 ║            │              │     Greeks breakdown │                   ║
 ║            │              │     Risk matrix      │                   ║
 ║            │              │     IV scenarios     │                   ║
 ║            │              │     Shock tests      │                   ║
 ║            │              │     Gamma profile    │                   ║
 ║            │              │     Breakeven paths  │                   ║
 ║            │              │                      │                   ║
 ║            │              │ 10. Forward context  │───▶ INFORMED      ║
 ║            │              │     Dealer flows     │     DECISION      ║
 ║            │              │     Expected move    │                   ║
 ║            │              │     Analyst actions  │                   ║
 ║            │              │     Correlations     │                   ║
 ║            │              │                      │                   ║
 ║            │              │ 11. IV outlook       │                   ║
 ║            │              │     Term structure   │                   ║
 ║            │              │     Historical analogs│                  ║
 ║            └──────────────┴──────────────────────┘                   ║
 ║                                                                       ║
 ╚═══════════════════════════════════════════════════════════════════════╝
```

**Three-tier workflow:** Pre-entry screening (6 gates) → **Entry execution (your decision)** → Post-entry monitoring and exit management (11 phases).

---

## How the Framework Makes Non-Binary Decisions

Here's the trap most traders fall into: they want a yes or no. Cut or hold. The framework refuses to give you one, and that's the point.

A binary answer to a complex position is just guessing with extra steps. What you actually need is: *what's driving this P&L, what would recovery look like, and where exactly am I wrong?*

The framework surfaces those three things and then steps back.

The decision is yours, but the calculus is the framework's.

### The Escalation Logic

| Trigger | Response |
|---------|----------|
| Stable position, clear exit rule | Phases 1-8. Straightforward. Resolves in minutes. |
| Ambiguous signals, extreme P&L | Escalate to Phases 9-11. Deep analysis answers: is this vega or delta? Where's IV going? What would recovery actually look like? |
| Binary event inside DTE | Immediate decision required. Phases 3 and 9b only. No time for the full framework. |

### How Phases Interact: A Real Example

**WDC $450P. -245% P&L. DTE 28. IV 111%. July 3, 2026.**

This is exactly the kind of position that makes you want to cut immediately. Your brain sees -245% and screams. The framework says: wait. Let's look first.

Phase 6 (combined exit rule) returned an ambiguous result: premium loss fired (condition 1), but price held above 50MA (condition 2). One condition. Not both. The exit rule says hold, but the P&L says this needs more than a rule-of-thumb.

Phase 9 (deep analysis) revealed **the loss was vega, not delta.** The IV mean-reversion table showed recovery to near-breakeven at 60% IV with zero stock rally. Gamma was 0.0016 — benign across the entire spot range. This position wouldn't spiral. The panic was in the vol market, not in the stock.

Phase 10 (forward context) showed no dealer amplification, a mixed analyst picture (one downgrade, two maintains), and 0.94 correlation with STX. WDC wasn't breaking alone. It was moving with its sector.

Phase 11 (IV outlook) showed **backwardation in the term structure.** Jul 10 IV at 115%, Sep 18 at 101%, Oct 16 at 99%. The market itself had already priced a 25-point IV decline over the next three months. The recovery engine had already been bought and paid for.

**Verdict: Hold. Exit trigger: below $526 for first hour Monday, or touch $500.**

The framework didn't say "hold." It said: *the loss is panic premium, not structural damage. Recovery requires calm, not a rally. The market agrees IV should decline. Here's exactly where you're wrong.* Then it stepped back.

---

## Project Structure

```
SignaWORKS/
├── scanner/
│   ├── csp_scanner.py        # 6-gate entry engine (on-demand)
│   └── csp_discovery.py      # Weekly Tastytrade pre-screening
├── monitors/
│   ├── position_monitor.py   # 3-layer trigger system (post-entry)
│   └── position_news.py      # Material news filter
├── review/
│   ├── position_review.py    # Position review orchestrator
│   └── deep_analysis.py      # Greeks, risk matrix, IV outlook, correlations
├── demo/
│   └── demo.py               # Offline walkthrough (no API keys)
├── docs/
│   ├── entry-scanner-framework.md
│   ├── position-review-framework.md    # Full 11-phase framework
│   ├── volatility-framework.md
│   └── case-study-wdc-450p.md         # Real-world showcase
├── data/
│   └── csp_universe.json     # Curated ticker universe
├── .env.example              # Environment variable template
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Quick Start

### 1. Clone

```bash
git clone https://github.com/limchinhan123/SignaWORKS.git
cd SignaWORKS
```

### 2. Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```bash
TASTYTRADE_CLIENT_SECRET=your_client_secret
TASTYTRADE_REFRESH_TOKEN=your_refresh_token
NEWS_TICKERS_CONFIG=/path/to/news_config.json
GOOGLE_SHEET_ID=your_sheet_id
```

**Never commit `.env`** — it's in `.gitignore`.

### 4. Run

```bash
# Offline demo (no API keys)
python3 demo/demo.py

# Weekly pre-screening (filter universe through Tastytrade gates)
python3 scanner/csp_discovery.py

# Full 6-gate scan on surviving candidates
python3 scanner/csp_scanner.py --file data/csp_candidates.json

# Scan specific tickers
python3 scanner/csp_scanner.py --tickers AAPL MSFT QQQ --format md
```

---

## The Framework in Full

### Entry: The Six Gates (Pre-Trade)

| Gate | Condition | What It Protects Against |
|:----:|-----------|--------------------------|
| G1 | IV Rank ≥ 50% | Selling vol at the bottom. Mean-reversion is the edge. |
| G2 | IV > HV | Options pricing more risk than reality. You're selling markup. |
| G3 | Price > 200MA | Bearish trend. Assignment risk jumps below 200MA. |
| G4 | Delta ≤ 0.10 | ~90% probability OTM. Computed via Black-Scholes. |
| G5 | Premium display | Absolute $ and return on notional. No hard floor below $75. |
| G6 | IV direction (soft) | Declining = READY. Rising = WATCH. Context, not a gate. |

**48 tickers. 6 gates. 21 actionable.** That's the entry half.

---

### Position Review: The 11 Phases (Post-Entry)

When a position is live, the framework shifts from binary (pass/fail) to **non-binary.** Each phase answers a specific question. The phases escalate based on urgency.

**Phases 1-4: Triage**

| Phase | Question Answered | What It Produces |
|:-----:|-------------------|------------------|
| 1 | What do we hold? | Position table with DTE, delta, P&L, urgency tier |
| 2 | What's the vol regime? | VIX level, name-level IVR and IV/HV spread |
| 3 | Any binary events? | Earnings, FOMC, regulatory inside DTE window |
| 4 | Any portfolio risk? | Sector concentration, expiry clustering, outlier betas |

**Phases 5-8: Decision**

| Phase | Question Answered | What It Produces |
|:-----:|-------------------|------------------|
| 5 | How close to the edge? | Distance to strike, delta acceleration, DTE urgency |
| 6 | Do both exit conditions fire? | Cut signal requires premium loss >1.5x AND price below support |
| 7 | Where are the supports? | MAs, swing lows, volume profile, round numbers |
| 8 | What's the verdict? | One-sentence conclusion with specific action triggers |

**Phases 9-11: Depth** (escalated only when Phases 1-8 return ambiguous signals)

| Phase | Question Answered | What It Produces |
|:-----:|-------------------|------------------|
| 9a | What's driving the P&L? | Greeks table with plain-English interpretation |
| 9b | How does P&L evolve? | Risk matrix: price × DTE grid with breakeven |
| 9c | What if vol mean-reverts? | IV scenarios showing recovery without stock rally |
| 9d | What about a gap? | 1-day shock table (±1-5% moves) |
| 9e | Does gamma bite? | Gamma profile across spot range |
| 9f | How do we get to flat? | Realistic spot/IV breakeven paths |
| 10a | Are dealers helping or hurting? | Gamma exposure, put/call walls, zero-gamma flip |
| 10b | Is the market pricing correctly? | Expected move vs actual realized moves |
| 10c | Is the story broken? | Analyst downgrades, target cuts, narrative shift |
| 10d | Is recovery name-specific? | Correlation with sector ETF and peer stocks |
| 11a | Where is IV heading? | Term structure across all expiries |
| 11b | What does history say? | IV spike analogs with median recovery timelines |

### How They Work Together

Running all 11 phases on a stable position with -$50 P&L is noise, not insight. The framework is a decision tree. You escalate only when you need to.

- **Clarity from Phases 1-8?** Stop. Deliver the verdict. Adding more analysis to a clear decision is performance, not thinking.
- **Ambiguous signals?** Escalate to Phases 9-11. Each phase answers one specific question. If you can't name which question you're answering, you shouldn't be running the phase.
- **Vega-driven P&L?** Phase 9c (IV scenarios) and Phase 11 (IV outlook) are your primary tools. Skip gamma. The position doesn't need a gamma profile when the problem is vol expansion.
- **Delta-driven P&L?** Phase 9b (risk matrix) leads. Phase 9e (gamma profile) if acceleration risk is real. IV scenarios are secondary — vol isn't what's hurting you.
- **Narrative uncertainty?** Phase 10c (analyst action) and 10d (correlations) lead. You can't decide whether to hold if you don't know whether the story is broken.

The phases don't vote. They don't average into a score. They answer questions. You read the answers and decide. The framework's job is to make sure you asked the right ones.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `tastytrade` | IV Rank, IV percentile, IV30d, HV30d, liquidity, beta |
| `yfinance` | Price, 50/200 MA, option chains (free, delayed) |
| `scipy` | Black-Scholes delta calculation (norm.cdf) |
| `numpy` | Numerical operations for options math |

No paid APIs. Tastytrade is free with a funded account. yfinance is free with Yahoo Finance.

---

## FAQ

**Why no trade execution?**
Because black boxes are for people who don't want to understand why they lost money. This is a decision-support toolkit. Every trade is yours to size and enter. The tools surface what's statistically worth looking at. You bring the conviction. If a trade goes wrong, you'll know exactly why — because you made the call, not an algorithm.

**What if the market is calm (low IVR)?**
Then the scanner returns mostly FAIL_G1. That's not a bug. You don't force trades into low-vol environments just because you're bored. Patience is a position, and it's the hardest one to hold.

**My position is down 200%. Should I cut?**
The worst time to ask that question is when you're looking at the P&L. Your brain wants a binary answer because the discomfort is real. The framework gives you something better: *here's what's driving the loss, here's what recovery looks like, here's where you cut if you're wrong.* Read the [WDC case study](docs/case-study-wdc-450p.md). That position was at -245%. Turned out the loss was vol panic, not thesis damage.

**How does this compare to tastytrade's built-in screener?**
Tastytrade's screener is broader. SignaWORKS adds Black-Scholes delta from yfinance chains (independent of Tastytrade's pricing), tiered MA analysis, and the ownership-first universe filter. More importantly, it doesn't stop at entry. The 11-phase review framework handles what happens after the trade is on — which is where most traders make their worst decisions.

**Can I add my own tickers?**
Edit `data/csp_universe.json`, add the symbol. But ask yourself first: would you own this stock for a year at the strike you're selling? If the answer isn't an immediate yes, it doesn't belong in the universe.

**Weekend vs weekday data?**
Tastytrade returns Friday close data on weekends. The scanner runs, but expiry dates shift. Monday morning shows fresh 45 DTE matches. Don't make Sunday night decisions on Friday data.

---

## License

MIT — use it, modify it, trade with it. If it makes you money, buy your spouse something nice.

---

<p align="center">
  <sub>Built entirely by <a href="https://github.com/nousresearch/hermes-agent">Hermes Agent</a> on <strong>DeepSeek 4.0 Pro</strong>. Zero human code written. Every gate, every line of Black-Scholes, every phase of the review framework came from a conversation between Brandon and his Q — an agent that doesn't tell him what he wants to hear, just what the numbers actually say.</sub>
</p>
