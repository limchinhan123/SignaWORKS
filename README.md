<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Data-Tastytrade-orange?logo=chartdot" alt="TastyTrade">
  <img src="https://img.shields.io/badge/Pricing-Black--Scholes-purple?logo=scipy" alt="Black-Scholes">
  <img src="https://img.shields.io/badge/Built_by-Hermes_Agent-ff66c4?logo=robotframework" alt="Hermes">
  <img src="https://img.shields.io/badge/Model-DeepSeek_4.0_Pro-4c6ef5?logo=deepin" alt="DeepSeek">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
</p>

# SignaWORKS

**Know what to do when your position is at −100%. A systematic CSP toolkit where the entry scanner is table stakes and the review framework is the edge.**

Most options tools tell you what to trade. SignaWORKS tells you what to do *after* — when the position is underwater, when your instincts scream "cut," and when cutting may be the wrong move.

Many underwater CSP positions are driven by temporary fear expansion rather than permanent damage to the underlying company. SignaWORKS helps separate those cases before you act. The 6-gate entry scanner gets you into trades with a statistical edge. The 11-phase review framework gets you through them without panic-selling at the worst possible moment. That second part is what separates this from every screener on GitHub.

The framework starts from one principle: **only sell puts on stocks you'd be comfortable owning at the strike for over a year.** If the name doesn't pass that gut check, it never enters the list. This isn't about maximum premium. It's about sleep.

<p align="center">
  <img src="demo/demo.gif" alt="SignaWORKS Demo" width="800">
  <br>
  <sub><i>Live scan: 21 actionable setups from a 48-ticker universe. Dracula theme courtesy of asciinema + agg.</i></sub>
</p>

---

## How This Framework Shows Up

SignaWORKS isn't a web app. It isn't a dashboard you check. It's a **Hermes agent skill** — a set of tools, scripts, and decision frameworks that Q (Brandon's AI agent) loads and runs on demand.

The interface is conversation. You say *"scan my universe"* and Q runs the scanner, applies all six gates, and hands you a ranked table of what passed. You say *"review my positions"* and Q runs the 11-phase framework against your live portfolio. No clicking around. No dashboards to log into. Just a conversation that surfaces what matters, when it matters.

This matters because it solves the real problem: when a position is bleeding, you don't need another tool to check. You need someone who's already looking at it, who's already run the numbers, who can tell you *"the loss is fear, not structural damage — hold"* before you've even asked the question.

The code in this repo is the engine. Q is the driver. You are the decision-maker.

---

## Philosophy

Here's the thing about selling options: your brain is wired to panic. A −245% P&L feels like an emergency. Your pulse spikes. Your fingers hover over the sell button. Every instinct screams *get out.*

Often, that instinct is wrong.

Many underwater positions aren't dying. They're expensive because the **market** is scared, not because the company broke. The stock didn't fail. The thesis didn't collapse. Fear spiked, and your position's paper loss is the splash damage. Cutting here isn't discipline. It's paying someone else's panic premium.

SignaWORKS exists to put something between your instincts and your brokerage account. Not because you don't know what you're doing. Because **nobody thinks clearly when their position is bleeding.**

**48 tickers. 6 gates. 21 actionable.** No opinions, no gut feels, no "I think the market is going to..." If it doesn't pass the gates, it doesn't reach your eyes.

But entry is half the story. On the other side, two tiers of exit rules operate independently:

**Tier 1: Combined Exit Rule (standard)**
Two conditions must BOTH fire before cutting:
- Premium loss exceeds 1.5× the credit received (the market agrees something changed)
- The stock breaks below key support level (the thesis is genuinely damaged)

If only one fires, the default is hold. If both fire, cut. This two-condition rule exists precisely because most underwater positions are driven by fear expansion, not broken companies. Requiring both conditions filters out panic.

**Tier 2: Hard Override (unconditional)**
The option's mid price hits 3× the credit received (= approximately −200% unrealized P&L on premium) → EXIT. No exemptions, no "but fear is high," no escape hatches. This rule is unconditional because at 200% loss, something structural changed.

When both tiers fire simultaneously: **HARD EXIT.** No deliberation, no deep analysis. Some positions don't need thinking. They need a stop.

The gates are summarized below. But they're not the edge. The edge is what sits between entry and exit: Phases 9-11, the deep analysis that tells you *why* your position is down and whether the loss is from fear (don't cut) or from the stock actually breaking (cut).

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
| MU | FAIL_G2 | IV-HV=-9.7 — options are pricing less risk than the stock is actually showing (no premium edge) |
| MSFT | FAIL_G3 | Price below 200MA — broken trend |
| META | FAIL_G3 | Price below 200MA |
| NVDA | FAIL_G1 | IVR=22% — fear is low, no opportunity here |
| BLK | SKIP | Liquidity=1 — spreads too wide to trade efficiently |

**Status codes:** READY = all gates pass + fear declining (optimal entry) · WATCH = all gates pass + fear still rising (may get better) · _AMBER = price below 50MA (caution flag) · FAIL_GX = which gate rejected it

DTE strategy: **45 DTE entry → exit at 50% profit or 21 DTE** (whichever comes first).

---

## The 6 Entry Gates (in Plain English)

These are the pre-trade filters. Every company in the universe must pass all six before it appears as actionable.

| Gate | Rule | What It Means |
|------|------|---------------|
| **G1** | IV Rank ≥ 50% | **Is fear elevated?** "IV Rank" measures where option prices sit relative to their own 52-week history. Above 50% means fear is in the upper half of its range — you're selling when insurance is expensive. The edge comes from fear eventually fading (mean reversion). If everyone's calm, you wait. |
| **G2** | IV > HV | **Are options pricing more risk than reality?** "IV" is what options are pricing. "HV" is what the stock is actually doing. When IV exceeds HV, you're selling insurance at a markup — getting paid more than the actual risk warrants. When this spread disappears, so does your edge. |
| **G3** | Price above 200MA | **Is the trend intact?** The 200-day moving average is a long-term trend line. If the stock is below it, the trend is broken. Assignment risk — being forced to buy the stock — becomes real and asymmetric. This single gate would have kept you out of half the losing trades you'll ever see. |
| **G4** | Delta ≤ 0.10 | **Risk proxy: is the strike far enough away?** Delta is a model-derived distance measure computed using Black-Scholes math. At 0.10 or lower, the strike sits far below the current price — a conservative distance buffer. This is not a guaranteed win probability (real markets have skew, dividends, event risk, and drift that Black-Scholes doesn't capture). Think of it as a margin of safety, not a prediction. |
| **G5** | Premium ≥ $75 | **Is the paycheck worth the paperwork?** Shows actual dollars and return on the money set aside. The $75 floor exists because commissions eat thinner trades. Sometimes 0.5% on a sleepy blue chip is a better trade than 2.5% on a volatile name still surging. |
| **G6** | IV direction (soft) | **Is fear rising or falling?** Declining fear = READY (optimal entry window). Rising fear = WATCH (the spike may still be building). This is context, not a hard gate. |

These gates kept you out of NVDA when fear was at rock bottom. They kept you out of MSFT when the trend was broken. They keep you out of every trade where the premium isn't actually there.

But entry is the easy part. What happens *after* is where the money is.

---

## Architecture: Two Halves

**Left side (scanner):** 6 gates. 48 tickers → 21 actionable. What to enter.

**Right side (review):** 11 phases. Non-binary decisions. What to do when it goes wrong.

Most tools stop at the left side. SignaWORKS starts there and keeps going.

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

The decision is yours, but the math is the framework's.

### The Escalation Logic

| Trigger | Response |
|---------|----------|
| Stable position, clear exit rule | Phases 1-8. Straightforward. Resolves in minutes. |
| Ambiguous signals, extreme P&L | Escalate to Phases 9-11. Deep analysis answers: is this fear or fundamentals? Where is fear heading? What would recovery actually look like? |
| Binary event inside DTE | Immediate decision required. Phases 3 and 9b only. No time for the full framework. |

### How Phases Interact: A Real Example

**WDC $450P. -245% P&L. DTE 28. IV 111%. July 3, 2026.**

This is exactly the kind of position that makes you want to cut immediately. Your brain sees -245% and screams. The framework says: wait. Let's look first.

Phase 6 (combined exit rule) returned an ambiguous result: the premium loss trigger fired (condition 1), but the stock held above its 50-day moving average (condition 2). One condition, not both. The exit rule says hold, but the P&L says this needs more than a rule of thumb.

Phase 9 (deep analysis) revealed **the loss was fear, not fundamentals.** The stock hadn't broken. Fear had exploded, and the paper loss was the shockwave. Specifically:

- The option's sensitivity to fear (vega) was $0.446 — every 1% drop in fear would save $45 per contract. The sensitivity to stock movement (delta) was only $0.225. The loss was 2:1 fear vs fundamentals.
- A table of fear-reversion scenarios showed recovery to near-breakeven if fear dropped to 60%, **even if the stock went nowhere.** No rally required.
- Gamma — which measures how fast delta accelerates — was 0.0016. Negligible. The position wouldn't spiral into catastrophe.

Phase 10 (forward context) showed no dealer amplification, a mixed analyst picture (one downgrade, two maintains), and 0.94 correlation with peer stock STX. WDC wasn't breaking alone. It was moving with its sector.

Phase 11 (fear outlook) showed **the market had already priced in its own recovery.** The term structure was in backwardation: near-term fear at 115%, three months out at 99%. The market itself expected a 25-point fear decline. The recovery engine was already bought and paid for.

**Verdict: Hold. Exit trigger: below $526 for the first hour Monday, or touch $500.**

The framework didn't say "hold." It said: *the loss is panic premium, not structural damage. Recovery requires calm, not a rally. The market agrees fear should decline. Here's exactly where you're wrong.* Then it stepped back.

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
│   └── position_review.py    # Position review orchestrator
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
| G1 | IV Rank ≥ 50% | Selling fear at the bottom. The edge is mean reversion — fear eventually fades. |
| G2 | IV > HV | Options pricing more risk than reality. You're selling insurance at a markup. |
| G3 | Price > 200MA | Broken trend. Below the 200-day line, assignment risk jumps. |
| G4 | Delta ≤ 0.10 | Risk proxy via Black-Scholes. Delta ≤ 0.10 means the strike is far below current price — a conservative distance buffer. Not a guaranteed win probability. |
| G5 | Premium display | Absolute dollars and return on the money set aside. No hard floor below $75. |
| G6 | IV direction (soft) | Declining fear = READY. Rising fear = WATCH. Context, not a hard gate. |

**48 tickers. 6 gates. 21 actionable.** That's the entry half.

---

### Position Review: The 11 Phases (Post-Entry)

When a position is live, the framework shifts from binary (pass/fail) to **non-binary.** Each phase answers a specific question. The phases escalate based on urgency.

**Phases 1-4: Triage**

| Phase | Question Answered | What It Produces |
|:-----:|-------------------|------------------|
| 1 | What do we hold? | Position table with days to expiry, risk level, P&L, urgency tier |
| 2 | What's the fear level? | VIX (market-wide fear gauge), plus name-level fear metrics |
| 3 | Any landmines on the calendar? | Earnings, Fed meetings, regulatory events inside the expiry window |
| 4 | Any portfolio-level risk? | Sector concentration, expiry clustering, outlier positions |

**Phases 5-8: Decision**

| Phase | Question Answered | What It Produces |
|:-----:|-------------------|------------------|
| 5 | How close to the edge? | Distance to strike, how fast risk is accelerating, time urgency |
| 6 | Do both exit conditions fire? | Cut signal requires premium loss >1.5× AND price below support |
| 7 | Where are the safety nets? | Moving averages, swing lows, volume levels, round numbers |
| 8 | What's the verdict? | One-sentence conclusion with specific action triggers |

**Phases 9-11: Depth** (escalated only when Phases 1-8 return ambiguous signals)

| Phase | Question Answered | What It Produces |
|:-----:|-------------------|------------------|
| 9a | What's driving the P&L? | Risk sensitivities with plain-English interpretation |
| 9b | How does P&L evolve? | Grid of outcomes at different prices and dates, with breakeven |
| 9c | What if fear fades? | Recovery scenarios showing profit without any stock rally |
| 9d | What about a sudden gap? | 1-day shock table across ±1-5% moves |
| 9e | Will the position spiral? | How fast risk accelerates across different stock prices |
| 9f | How do we get back to flat? | Realistic combinations of price and fear that reach breakeven |
| 10a | Are big-money dealers helping or hurting? | Whether dealer hedging is amplifying or dampening the move |
| 10b | Is the market pricing correctly? | Expected daily moves vs actual recent moves |
| 10c | Is the story broken? | Analyst downgrades, price target cuts, narrative shifts |
| 10d | Is recovery company-specific? | Correlation with sector ETF and peer stocks |
| 11a | Where is fear heading? | Fear priced across all future expiration dates |
| 11b | What does history say? | Comparable fear spikes with median recovery timelines |

### How They Work Together

Running all 11 phases on a stable position with -$50 P&L is noise, not insight. The framework is a decision tree. You escalate only when you need to.

- **Clarity from Phases 1-8?** Stop. Deliver the verdict. Adding more analysis to a clear decision is performance, not thinking.
- **Ambiguous signals?** Escalate to Phases 9-11. Each phase answers one specific question. If you can't name which question you're answering, you shouldn't be running the phase.
- **Loss from fear (not fundamentals)?** Phase 9c (fear scenarios) and Phase 11 (fear outlook) are your primary tools. Skip gamma. The position doesn't need a gamma profile when the problem is fear expansion.
- **Loss from the stock actually dropping?** Phase 9b (risk matrix) leads. Phase 9e (gamma profile) if acceleration risk is real. Fear scenarios are secondary — fear isn't what's hurting you.
- **Story uncertainty?** Phase 10c (analyst action) and 10d (correlations) lead. You can't decide whether to hold if you don't know whether the story is broken.

The phases don't vote. They don't average into a score. They answer questions. You read the answers and decide. The framework's job is to make sure you asked the right ones.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `tastytrade` | Fear metrics (IV Rank, IV percentile), actual volatility, liquidity, beta |
| `yfinance` | Price, 50/200-day moving averages, option chains (free, delayed) |
| `scipy` | Black-Scholes math for probability calculations |
| `numpy` | Numerical operations for options math |

No paid APIs. Tastytrade is free with a funded account. yfinance is free via Yahoo Finance.

---

## FAQ

**Why no trade execution?**

Because black boxes are for people who don't want to understand why they lost money. This is a decision-support toolkit. Every trade is yours to size and enter. The tools surface what's statistically worth looking at. You bring the conviction. If a trade goes wrong, you'll know exactly why — because you made the call, not an algorithm.

**What if the market is calm (low IVR)?**

Then the scanner returns mostly FAIL_G1. That's not a bug. You don't force trades into low-fear environments just because you're bored. Patience is a position, and it's the hardest one to hold.

**My position is down 200%. Should I cut?**

The worst time to ask that question is when you're looking at the P&L. Your brain wants a binary answer because the discomfort is real. The framework's Phases 9-11 give you something better: *here's what's driving the loss (fear or fundamentals?), here's what recovery looks like, here's where you cut if you're wrong.* Read the [WDC case study](docs/case-study-wdc-450p.md). That position was at -245%. Phase 9 revealed the loss was panic premium, not structural damage. Phase 11 showed the market had already priced in fear declining. Verdict: hold.

**How does this compare to tastytrade's built-in screener?**

Tastytrade's screener is broader. SignaWORKS adds Black-Scholes probability from yfinance chains (independent of Tastytrade's pricing), tiered moving-average analysis, and the ownership-first universe filter. More importantly, it doesn't stop at entry. The 11-phase review framework handles what happens after the trade is on — which is where most traders make their worst decisions.

**Can I add my own tickers?**

Edit `data/csp_universe.json`, add the symbol. But ask yourself first: would you own this stock for a year at the strike you're selling? If the answer isn't an immediate yes, it doesn't belong in the universe.

**Is this an app? A dashboard? How do I actually use it?**

Neither. SignaWORKS is a **Hermes agent skill.** The code in this repo is the engine. The interface is a conversation with Q — an AI agent that loads the framework and runs it on demand. You say "scan my universe" or "review my positions" and Q runs the scanner, applies the framework, and presents the results in plain English with tables and action items. The "app" is talking to someone who's already done the work.

**Weekend vs weekday data?**

Tastytrade returns Friday close data on weekends. The scanner runs, but expiry dates shift. Monday morning shows fresh 45 DTE matches. Don't make Sunday night decisions on Friday data.

---

## License

MIT — use it, modify it, trade with it. If it makes you money, buy your spouse something nice.

---

<p align="center">
  <sub>Built entirely by <a href="https://github.com/nousresearch/hermes-agent">Hermes Agent</a> on <strong>DeepSeek 4.0 Pro</strong>. Zero human code written. Every gate, every line of Black-Scholes, every phase of the review framework came from a conversation between Brandon and his Q — an agent that doesn't tell him what he wants to hear, just what the numbers actually say.</sub>
  <br>
  <sub>Framework reviewed by <strong>Claude</strong>. Security and regression audits by <strong>Codex</strong>. Three rounds, five regressions caught before they shipped.</sub>
</p>
