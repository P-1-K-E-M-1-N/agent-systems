"""Supplier News Monitor: rebuilds the web prototype's data and the outreach sample from live GDELT.

Run from repo root:  python lanes/supplier-news/refresh.py
Output: app/data/latest.json + latest.js (the app reads latest.js before first paint),
        samples/supplier_digest.{csv,html,pdf} (the outreach attachment).

Plain language: runs ~12 GDELT DOC searches (6 event topics, 6 watchlist batches), keeps only
title/url/domain/date (publishers own the text), tags each hit with an event type by keyword rules,
matches it to a watchlist company by name, drops duplicate headlines and obvious noise (stock-ticker
spam, restaurants, sports), and ranks it. Honest limit (LANE.md G0): GDELT is a news index, not a
supplier database; precision is modest, so the page shows the matched company and event type and
lets the user hide what is not relevant.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.fetch import Fetcher, FetchError  # noqa: E402
from core.samples import write_all  # noqa: E402

LANE = "supplier-news"
HERE = ROOT / "lanes" / LANE
URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# Public companies / well-known auto-industry suppliers (organizations only).
WATCHLIST = ["Lear", "Magna", "BorgWarner", "Dana Incorporated", "Adient", "Visteon", "American Axle", "Gentherm",
             "Tenneco", "Aptiv", "Cooper Standard", "Superior Industries", "Stoneridge", "Shiloh Industries",
             "Gestamp", "Forvia", "Faurecia", "Hyundai Mobis", "Continental", "Bosch", "Denso", "Valeo",
             "Nexteer", "Flex-N-Gate", "Benteler", "Martinrea", "Linamar", "Lakeland", "Detroit Manufacturing Systems"]
TOPICS = [  # style that worked at G0: one OR group in parentheses, plain words after it
    ("closure", "(plant closure OR layoffs OR \"WARN notice\") automotive supplier Michigan"),
    ("bankruptcy", "(bankruptcy OR \"chapter 11\" OR insolvency) automotive supplier"),
    ("disruption", "(\"production halt\" OR shortage OR recall OR fire) automotive supplier Michigan"),
    ("expansion", "(expansion OR \"new plant\" OR hiring) automotive supplier Michigan"),
    ("labor", "(strike OR walkout OR UAW) automotive supplier Michigan"),
    ("deal", "(acquires OR acquisition OR merger) automotive supplier"),
]
RULES = [  # (type, regex, weight) first strongest
    ("Closure / layoffs", r"clos(e|es|ing|ure)|layoff|lay off|laid off|cuts? (\d+ )?jobs|job cuts|wind down|shutter|WARN notice|idle", 5),
    ("Bankruptcy", r"bankrupt|chapter 11|insolven|receivership|default", 5),
    ("Disruption", r"shortage|production halt|halts? production|fire at|explosion|recall|cyberattack|outage|supply chain", 4),
    ("Labor", r"strike|walkout|union|UAW|picket|contract talks", 3),
    ("Deal", r"acquir|acquisition|merger|merge|divest|sells? (its )?|buyout|takeover", 3),
    ("Growth", r"expan|new plant|invest|hiring|add(s|ing)? \d+ jobs|opens|groundbreaking|contract win|wins", 2),
]
NOISE = re.compile(r"restaurant|nfl|nba|mlb|ncaa|football|basketball|stock price|shares of|price target|"
                   r"\binstitutional\b|holdings (llc|lp)|13f|marketbeat|etf|earnings call|dividend|horoscope|recipe", re.I)
AUTO = re.compile(r"auto|supplier|vehicle|parts|plant|manufactur|oem|ford|gm|general motors|stellantis|chrysler|"
                  r"tier ?1|tier ?2|axle|wiring|seating|michigan|detroit", re.I)


def gdelt(f, q, n=60, span="7d"):
    params = {"query": f"{q} sourcelang:english", "mode": "artlist", "format": "json", "maxrecords": n,
              "timespan": span, "sort": "datedesc"}
    try:
        text, st = f.get(URL, params=params)
        if not text.strip().startswith("{"):
            print("  gdelt said:", text.strip()[:80])
        return json.loads(text).get("articles", []) if text.strip().startswith("{") else []
    except (FetchError, ValueError) as e:
        print("  query failed:", str(e)[:100])
        return []


def when(s):  # 20261101T123000Z -> iso
    try:
        return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat()
    except Exception:
        return ""


def classify(title):
    best, w = None, 0
    for name, rx, wt in RULES:
        if re.search(rx, title, re.I) and wt > w:
            best, w = name, wt
    return best, w


def main():
    f = Fetcher("gdelt_doc", lane=LANE, gate="G1")
    hits = {}
    queries = [("topic:" + k, q) for k, q in TOPICS]
    for i in range(0, len(WATCHLIST), 5):
        names = " OR ".join(f'"{n}"' for n in WATCHLIST[i:i + 5])
        queries.append((f"watch{i // 5}", f"({names}) (supplier OR plant OR jobs OR layoffs)"))
    for tag, q in queries:
        arts = gdelt(f, q)
        print(f"{tag}: {len(arts)} articles")
        for a in arts:
            t = re.sub(r"\s+", " ", a.get("title", "")).strip()
            if not t or a.get("url") in hits:
                continue
            hits[a["url"]] = dict(title=t, url=a["url"], domain=a.get("domain", ""), seen=when(a.get("seendate", "")),
                                  query=tag)
    if not hits:  # GDELT rate-limited or empty: keep the last good data instead of writing an empty page
        print("no articles returned; leaving existing app/data untouched")
        sys.exit(1)
    items, seen_titles = [], set()
    for h in hits.values():
        key = re.sub(r"\W+", "", h["title"].lower())[:60]
        if key in seen_titles or NOISE.search(h["title"]) or not AUTO.search(h["title"]):
            continue
        seen_titles.add(key)
        etype, w = classify(h["title"])
        comp = next((n for n in WATCHLIST if re.search(r"\b" + re.escape(n) + r"\b", h["title"], re.I)), "")
        if not etype and not comp:
            continue
        mi = bool(re.search(r"michigan|detroit|auburn hills|troy|warren|lansing|grand rapids|flint|livonia|southfield", h["title"], re.I))
        score = w * 2 + (6 if comp else 0) + (2 if mi else 0)
        items.append(dict(h, type=etype or "Mention", company=comp, michigan=mi, score=score))
    items.sort(key=lambda x: (x["score"], x["seen"]), reverse=True)
    items = items[:120]
    now = datetime.now(timezone.utc).isoformat()
    counts = {}
    for it in items:
        counts[it["type"]] = counts.get(it["type"], 0) + 1
    data = dict(generated=now, window="last 7 days", source="The GDELT Project (titles, links, dates only)",
                watchlist=WATCHLIST, types=counts, n_raw=len(hits), items=items)
    (HERE / "app" / "data").mkdir(parents=True, exist_ok=True)
    js = json.dumps(data, ensure_ascii=False, indent=1)
    (HERE / "app/data/latest.json").write_text(js, encoding="utf-8")
    (HERE / "app/data/latest.js").write_text("window.SUPPLIER_SNAPSHOT = " + js + ";\n", encoding="utf-8")
    rows = [dict(date=i["seen"][:10], type=i["type"], company=i["company"] or "-", headline=i["title"],
                 source=i["domain"], link=i["url"]) for i in items[:40]]
    write_all(rows, [("date", "Date"), ("type", "Event"), ("company", "Watchlist match"), ("headline", "Headline"),
                     ("source", "Source")], HERE / "samples", title="Supplier News Digest",
              subtitle=f"Michigan auto-supplier news, last 7 days, {now[:10]}",
              notes=["Headlines and links only; articles belong to their publishers.",
                     "Event type and company match are keyword rules, so some rows are noise. A paid version would take your own supplier list."],
              source_line="Source: The GDELT Project", basename="supplier_digest")
    print(f"kept {len(items)} of {len(hits)} unique articles; types {counts}")


if __name__ == "__main__":
    main()
