#!/usr/bin/env python3
"""Fetch configured RSS feeds and dump a normalized article list to JSON.

This only *collects* articles. Summarization / ranking / HTML generation is
done afterwards (Claude reads news_data.json, writes Japanese summaries, and
fills template into news.html). Run:  python3 fetch_news.py
"""

import html
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

import feedparser

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(OUT_DIR, "news_data.json")

# Browser-like UA: several government / media feeds reject the default one.
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)

# How far back to keep articles. Undated entries are always kept.
MAX_AGE_DAYS = 10

# (theme, source name, feed url). Verified reachable 2026-07-07 / 2026-07-08.
# 政府系はHTML記事がbot遮断でもRSS/XMLは通ることが多い（経産省は.rdfは403だがAtom版は可）。
FEEDS = [
    ("投資・株", "東洋経済オンライン", "https://toyokeizai.net/list/feed/rss"),
    ("決済・フィンテック", "ペイメントナビ", "https://paymentnavi.com/feed"),
    ("決済・フィンテック", "金融庁", "https://www.fsa.go.jp/fsaNewsListAll_rss2.xml"),
    ("決済・フィンテック", "デジタル庁", "https://www.digital.go.jp/rss/news.xml"),
    ("決済・フィンテック", "日本銀行", "https://www.boj.or.jp/rss/whatsnew.xml"),
    ("決済・フィンテック", "Finextra", "https://www.finextra.com/rss/headlines.aspx"),
    ("決済・フィンテック", "PaymentsDive", "https://www.paymentsdive.com/feeds/news/"),
    ("決済・フィンテック", "CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("Agentic Commerce", "PYMNTS", "https://www.pymnts.com/feed/"),
    ("デジタルアイデンティティ/VC", "Biometric Update", "https://www.biometricupdate.com/feed"),
    ("コンサル/政策", "総務省", "https://www.soumu.go.jp/news.rdf"),
    ("コンサル/政策", "McKinsey Insights", "https://www.mckinsey.com/insights/rss"),
]
# 注: 経産省(meti.go.jp)のRSS/Atomは間欠的にWAFが202空を返すため不採用。
# 官公庁枠は 金融庁・デジタル庁・総務省・日本銀行 でカバー。

# 横断ウォッチ軸: テーマを越えて追いたいレンズ。該当キーワードを含む記事に印を付け、
# 収集時に候補を炙り出す（採否は curated_news.json 編集時にClaudeが判断）。
WATCHES = {
    "機械が払うWeb": [
        "x402", "402 payment", "pay per crawl", "pay-per-crawl", "machine payment",
        "machine-payable", "agent-initiated", "agentic", "autonomous payment", "m2m",
        "micropayment", "stablecoin", "usdc", "crawler", "ステーブルコイン",
        "エージェント", "マイクロ決済", "自律",
    ],
}

# 1ソースあたりの最大採用件数。プールを小さく保ち、毎朝の要約(LLM)コストを抑える。
PER_SOURCE_LIMIT = 10

_TAG_RE = re.compile(r"<[^>]+>")


def fetch_feed(url):
    """Fetch a feed. Prefer curl (bypasses WAFs / 308 redirects that block
    feedparser's own HTTP client); fall back to feedparser if curl yields nothing."""
    try:
        data = subprocess.run(
            ["curl", "-sS", "-L", "--max-time", "20", "-A", UA, url],
            capture_output=True, timeout=30,
        ).stdout
        if data:
            parsed = feedparser.parse(data)
            if parsed.get("entries"):
                return parsed
    except Exception:
        pass
    return feedparser.parse(url, agent=UA)


def match_watches(text):
    """Return list of watch-axis names whose keywords appear in text (lowercased)."""
    low = text.lower()
    hits = []
    for name, keywords in WATCHES.items():
        if any(kw.lower() in low for kw in keywords):
            hits.append(name)
    return hits


def clean_text(raw, limit=400):
    """Strip HTML tags/entities and collapse whitespace."""
    if not raw:
        return ""
    text = _TAG_RE.sub(" ", raw)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[:limit].rstrip() + "…"
    return text


def entry_datetime(entry):
    """Return timezone-aware UTC datetime for an entry, or None."""
    for key in ("published_parsed", "updated_parsed"):
        parsed = entry.get(key)
        if parsed:
            return datetime.fromtimestamp(time.mktime(parsed), tz=timezone.utc)
    return None


def fetch_all():
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    articles = []
    seen = set()
    report = []

    for theme, source, url in FEEDS:
        parsed = fetch_feed(url)
        entries = parsed.get("entries", [])
        kept = 0
        for entry in entries:
            link = (entry.get("link") or "").strip()
            title = clean_text(entry.get("title"), limit=300)
            if not link or not title:
                continue
            key = link or title
            if key in seen:
                continue

            dt = entry_datetime(entry)
            if dt is not None and dt < cutoff:
                continue

            seen.add(key)
            summary = clean_text(entry.get("summary") or entry.get("description"), limit=200)
            articles.append(
                {
                    "theme": theme,
                    "source": source,
                    "title": title,
                    "link": link,
                    "published": dt.isoformat() if dt else None,
                    "summary": summary,
                    "watches": match_watches(title + " " + summary),
                }
            )
            kept += 1
            if kept >= PER_SOURCE_LIMIT:
                break

        status = "ok" if entries else f"EMPTY (bozo={parsed.get('bozo')})"
        report.append((source, len(entries), kept, status))

    # Newest first; undated entries sink to the bottom.
    articles.sort(key=lambda a: a["published"] or "", reverse=True)
    return articles, report


def main():
    articles, report = fetch_all()
    payload = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "count": len(articles),
        "articles": articles,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    print(f"収集した記事: {payload['count']} 件 -> {OUT_JSON}\n")
    print(f"{'ソース':<20} {'取得':>5} {'採用':>5}  状態")
    print("-" * 48)
    for source, got, kept, status in report:
        print(f"{source:<20} {got:>5} {kept:>5}  {status}")

    # 横断ウォッチ軸の候補を炙り出す（curated編集時の当たり付け用）
    for name in WATCHES:
        cands = [a for a in articles if name in a.get("watches", [])]
        print(f"\n🔭 ウォッチ候補『{name}』: {len(cands)}件")
        for a in cands[:12]:
            print(f"   [{a['source']}] {a['title'][:64]}")

    if payload["count"] == 0:
        print("\n[warn] 記事が0件でした。ネットワークかフィードURLを確認してください。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
