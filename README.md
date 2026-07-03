<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Data-Tastytrade-orange?logo=chartdot" alt="TastyTrade">
  <img src="https://img.shields.io/badge/Pricing-Black--Scholes-purple?logo=scipy" alt="Black-Scholes">
  <img src="https://img.shields.io/badge/Built_by-Hermes_Agent-ff66c4?logo=robotframework" alt="Hermes">
  <img src="https://img.shields.io/badge/Model-DeepSeek_4.0_Pro-4c6ef5?logo=deepin" alt="DeepSeek">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
</p>

# SignaWORKS

**A systematic options income toolkit. Precision, not gambling.**

You're selling insurance on assets you actually want to own, using a statistical edge that has nothing to do with guessing direction. Every trade survives six independent gates before it reaches your eyes. What you do with it is your decision. The toolkit only surfaces what's worth looking at.

<p align="center">
  <img src="demo/demo.gif" alt="SignaWORKS Demo" width="800">
  <br>
  <sub><i>Live scan: 21 actionable setups from a 48-ticker universe. Dracula theme courtesy of asciinema + agg.</i></sub>
</p>

---

## Philosophy

Most options trading is directional gambling dressed up as strategy. SignaWORKS starts from a different place: **only sell puts on stocks you'd be comfortable owning at the strike for > 12 months.** If the name doesn't pass that test, it never enters the universe.

From there, the toolkit applies layered filters:

- **Gate 1:** IV Rank ≥ 50% — sell premium when vol is elevated relative to its own 52-week history. Statistical edge from mean reversion.
- **Gate 2:** IV > HV — options are pricing more movement than the stock is actually making. You're getting paid for vol risk that exceeds realized vol.
- **Gate 3:** Price above 200MA — bearish trend breaks the thesis. Below 200MA means assignment risk just jumped.
- **Gate 4:** Delta ≤ 0.10 — a ~90% probability the put expires worthless, computed via Black-Scholes, not yfinance's approximation.
- **Gate 5:** Premium display — absolute dollars and return on notional. No hard floor beyond $75 (commissions eat thinner trades).
- **Gate 6 (soft):** IV direction — declining vol is the optimal entry window. Rising vol means wait or watch.

**48 tickers. 6 gates. 21 actionable. No opinions, no gut feels, no "I think the market is going to..."**

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

The framework never says "cut" or "hold." It surfaces **what's driving the P&L** and **what would need to happen** for each outcome. The decision is yours, but the calculus is the framework's.

### The Escalation Logic

| Trigger | Response |
|---------|----------|
| Stable position, clear exit rule | Phases 1-8. Framework resolves in minutes. |
| Ambiguous signals, extreme P&L | Escalate to Phases 9-11. Deep analysis answers: is this vega or delta? Where's IV going? What would recovery look like? |
| Binary event inside DTE | Immediate decision required. Phases 3 and 9b only. |

### How Phases Interact: A Real Example

**WDC $450P, -245% P&L. DTE 28. IV 111%.**

Phase 6 (combined exit rule) returned an ambiguous result: premium loss fired (condition 1), but price held above 50MA (condition 2). Framework says: don't cut yet, but this needs depth.

Phase 9 (deep analysis) revealed **the loss was vega, not delta.** The IV mean-reversion table showed recovery to near-breakeven at 60% IV with zero stock rally. Gamma was benign (0.0016). The position wouldn't spiral.

Phase 10 (forward context) showed no dealer amplification, a mixed analyst picture (one downgrade, two maintains), and 0.94 correlation with STX.

Phase 11 (IV outlook) showed **backwardation:** the term structure priced a 25-point IV decline over the next 3 months. The market itself expected vol to collapse.

**Verdict: Hold. Exit trigger: below $526 for first hour Monday, or touch $500.**

The framework didn't just say "hold." It said: *here's the recovery path, here's the confidence level, here's the line where you're wrong.* Non-binary.

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

The framework is a decision tree, not a checklist:

- **Clarity from Phases 1-8?** Stop. Deliver verdict. Don't drown the reader in data.
- **Ambiguous?** Escalate to Phases 9-11. Each phase answers one specific question. No phase is run for its own sake.
- **Vega-driven P&L?** Phase 9c (IV scenarios) and Phase 11 (IV outlook) are primary. Skip gamma profile.
- **Delta-driven P&L?** Phase 9b (risk matrix) and 9e (gamma profile) are primary. Skip IV scenarios.
- **Narrative uncertainty?** Phase 10c (analyst action) and 10d (correlations) lead.

The phases don't vote. They inform. The trader decides. But the framework ensures the decision is made with every relevant question answered and no noise.

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
This is a decision-support toolkit, not a black box. Every trade is yours to size and enter. The tools surface what's statistically worth looking at. You bring the conviction.

**What if the market is calm (low IVR)?**
Then the scanner returns mostly FAIL_G1. That's the point. You don't force trades into low-vol environments. Patience is a position.

**How does the position review framework handle extreme P&L?**
Phases 1-8 handle standard positions. When signals are ambiguous or P&L is extreme, Phases 9-11 escalate into deep analysis: Greeks breakdown, risk matrix, IV scenarios, shock tests, IV outlook. The framework distinguishes vega noise from thesis damage. Most underwater positions are vol events, not structural breakdowns. The framework prevents cutting on noise.

**How does this compare to tastytrade's built-in screener?**
Tastytrade's screener is broader. SignaWORKS adds Black-Scholes delta from yfinance chains (independent of Tastytrade's pricing), tiered MA analysis, and the ownership-first universe filter. It also integrates post-entry monitoring and the full 11-phase review framework in one pipeline.

**Can I add my own tickers?**
Edit `data/csp_universe.json`, add the symbol, ensure it passes the ownership test. Next scan picks it up.

**Weekend vs weekday data?**
Tastytrade returns Friday close data on weekends. The scanner works, but expiry dates shift. Monday morning shows fresh 45 DTE matches.

**Where can I see the framework in action?**
Read the [WDC case study](docs/case-study-wdc-450p.md) — a real position at -245% P&L where the framework prevented a reactive cut and surfaced a data-based hold decision.

---

## License

MIT — use it, modify it, trade with it. If it makes you money, buy your spouse something nice.

---

<p align="center">
  <sub>Built entirely by <a href="https://github.com/nousresearch/hermes-agent">Hermes Agent</a> on <strong>DeepSeek 4.0 Pro</strong>. Zero human code written. Every gate, every line of Black-Scholes, every script came from a conversation between Brandon and his Q.</sub>
</p>
