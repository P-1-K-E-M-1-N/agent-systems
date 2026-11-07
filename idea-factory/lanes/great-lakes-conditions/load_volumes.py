"""Summarise Nick's Keyword Planner export for the final G3 decision.

Run: python lanes/great-lakes-conditions/load_volumes.py [path]
Accepts either our template header (query,avg_monthly_searches,...) or Google's raw export
(columns starting "Keyword" and "Avg. monthly searches"; Google's file is UTF-16 with a 2-line preamble).
"""
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
path = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "data" / "keyword_volumes.csv"


def read_rows(p):
    raw = p.read_bytes()
    text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig")
    lines = text.splitlines()
    # Google's export starts with a title line and a date-range line; the real header begins "Keyword<tab>".
    start = next((i for i, l in enumerate(lines) if l.startswith(("Keyword\t", "Keyword,", "query"))), 0)
    dialect = "excel-tab" if "\t" in lines[start] else "excel"
    rows = list(csv.DictReader(lines[start:], dialect=dialect))
    kcol = next(c for c in rows[0] if c.lower().startswith(("keyword", "query")))
    return [r for r in rows if (r.get(kcol) or "").strip()]  # drop the All/United States/Michigan segment rows


def to_int(v):
    v = (v or "").replace(",", "").strip()
    if "-" in v and v[0].isdigit():       # range like "1K-10K": use the low end
        v = v.split("-")[0]
    v = v.upper().replace("K", "000").replace("M", "000000")
    try:
        return int(float(v))
    except ValueError:
        return 0


rows = read_rows(path)
if not rows:
    print(f"{path} has no data rows yet. Nick must run the Keyword Planner steps in g2_keywords.md.")
    sys.exit(1)
kcol = next(c for c in rows[0] if c.lower().startswith(("keyword", "query")))
vcol = next(c for c in rows[0] if c.lower().startswith(("avg", "avg. monthly")))
vals = sorted(((to_int(r[vcol]), r[kcol]) for r in rows), reverse=True)
total = sum(v for v, _ in vals)
print(f"{len(vals)} queries, total {total:,} searches/month (Michigan). Top 10:")
for v, k in vals[:10]:
    print(f"  {v:>7,}  {k}")
verdict = "weak" if total < 5000 else "viable niche" if total < 30000 else "strong"
print(f"Yardstick from g2_keywords.md: {verdict}. Suggested demand score: "
      f"{1 if total < 1000 else 2 if total < 5000 else 3 if total < 15000 else 4 if total < 30000 else 5}/5")
