#!/usr/bin/env python3
"""
Position News Monitor — daily material headline check.
Fetches Yahoo Finance RSS headlines for each ticker.
Filters for material news (guidance, M&A, restructuring, etc.).
Silent when nothing material. Prints to stdout when news matters.

Usage:
    python3 position_news.py                              # read data/news_tickers.json
    python3 position_news.py --config path/to/config.json  # custom config
    python3 position_news.py --json                        # output JSON instead of markdown
"""

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests

HOME = os.path.expanduser("~")
CONFIG_FILE = os.environ.get(
    "NEWS_TICKERS_CONFIG",
    os.path.join(HOME, ".hermes", "data", "news_tickers.json"),
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; CSPnewsBot/1.0)",
}
TIMEOUT = 15
SGT = timezone.utc  # For timestamp only; script runs in SGT

# Keywords that indicate material news worth flagging.
# Order matters: first match wins for categorization.
KEYWORDS = [
    ("earnings", "Earnings"),
    ("guidance", "Guidance"),
    ("cuts forecast", "Guidance"),
    ("raises forecast", "Guidance"),
    ("revenue miss", "Earnings"),
    ("revenue beat", "Earnings"),
    ("earnings miss", "Earnings"),
    ("earnings beat", "Earnings"),
    ("downgrade", "Analyst"),
    ("upgrade", "Analyst"),
    ("price target", "Analyst"),
    ("initiates coverage", "Analyst"),
    ("acquisition", "M&A"),
    ("merger", "M&A"),
    ("takeover", "M&A"),
    ("bid", "M&A"),
    ("spin-?off", "Restructuring"),
    ("divest", "Restructuring"),
    ("layoff", "Restructuring"),
    ("job cut", "Restructuring"),
    ("CEOs?", "Leadership"),
    ("CFOs?", "Leadership"),
    ("appoints", "Leadership"),
    ("resigns", "Leadership"),
    ("departure", "Leadership"),
    ("SEC", "Regulatory"),
    ("DOJ", "Regulatory"),
    ("lawsuit", "Legal"),
    ("investigation", "Regulatory"),
    ("tariff", "Regulatory"),
    ("ban", "Regulatory"),
    ("subsidy", "Regulatory"),
    ("supply", "Operations"),
    ("shortage", "Operations"),
    ("recall", "Operations"),
    ("factory", "Operations"),
    ("chip", "Sector"),
    ("semiconductor", "Sector"),
    ("AI", "Sector"),
    ("surge", "Price Move"),
    ("plunge", "Price Move"),
    ("sell-?off", "Price Move"),
]

SKIP_PATTERNS = [
    r"(?i)here.?s why",
    r"(?i)why .+ is (rising|falling|moving|trading)",
    r"(?i)what.?s (moving|happening)",
    r"(?i)top (stories|news|headlines)",
    r"(?i)stock market today",
    r"(?i)markets today",
    r"(?i)weekly (recap|wrap|review)",
    r"(?i)after hours",
    r"(?i)pre.?market (movers|stocks)",
    r"(?i)midday (movers|stocks)",
    r"(?i)closing bell",
    r"(?i)market (wrap|summary|digest|update)",
    r"(?i)wall street (wrap|today|update|digest)",
    r"(?i)stocks (rise|fall|gain|drop|slide|edge|slip|climb)",
    r"(?i)nasdaq (rises|falls|gains|drops)",
    r"(?i)s&p 500 (rises|falls|gains|drops)",
    r"(?i)dow (rises|falls|gains|drops|futures)",
    r"(?i)trading session",
    r"(?i)us stocks",
    r"(?i)live updates",
    r"(?i)market watch",
]


def load_json(path):
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def fetch_headlines(ticker):
    """Fetch RSS headlines for a ticker from Yahoo Finance."""
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        root = ET.fromstring(r.text)
        items = []
        for item in root.findall(".//item"):
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            if title and link:
                items.append({"title": title, "link": link})
        return items
    except Exception:
        return []


def is_skip(title):
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, title):
            return True
    return False


def classify(title):
    title_lower = title.lower()
    for keyword, category in KEYWORDS:
        if re.search(keyword, title_lower):
            return category
    return None


def main():
    config = load_json(CONFIG_FILE)
    all_tickers = config.get("tickers", []) + config.get("future_holdings", [])
    if not all_tickers:
        return

    hits = []
    for ticker in all_tickers:
        headlines = fetch_headlines(ticker)
        for h in headlines:
            if is_skip(h["title"]):
                continue
            category = classify(h["title"])
            if category:
                hits.append({
                    "ticker": ticker,
                    "title": h["title"],
                    "link": h["link"],
                    "category": category,
                })

    if not hits:
        return

    seen = set()
    unique = []
    for h in hits:
        key = h["title"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(h)

    limited = []
    per_ticker = {}
    for h in sorted(unique, key=lambda x: (x["ticker"], x["title"])):
        ticker = h["ticker"]
        if per_ticker.get(ticker, 0) >= 3:
            continue
        per_ticker[ticker] = per_ticker.get(ticker, 0) + 1
        limited.append(h)
        if len(limited) >= 15:
            break

    if "--json" in sys.argv:
        print(json.dumps(limited, indent=2))
        return

    now = datetime.now(timezone.utc)
    lines = [f"**Position News** {now.strftime('%a %d %b %H:%M SGT')}", ""]
    current_ticker = None
    for h in limited:
        if h["ticker"] != current_ticker:
            current_ticker = h["ticker"]
            lines.append(f"**{current_ticker}**")
        lines.append(f"[_{h['category']}_] [{h['title']}]({h['link']})")

    lines.append("")
    lines.append("_Filtered for material news only. Add/remove tickers in news_tickers.json_")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
