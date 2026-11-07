"""24-month Michigan backtest for Storm Lead (Oct 2024 - Sep 2026).

Question: on how many mornings would an alert have fired, how many qualifying reports per
month, and which counties keep showing up?

Data: final SPC yearly files for 2024 and 2025 (NWS Storm Data), daily preliminary SPC files
for 2026 (no final file exists yet). Also pulls June 2025 daily files to measure how much the
preliminary morning data differs from the final record.

Run:  python lanes/storm-lead/backtest.py
Writes lanes/storm-lead/data/backtest.csv, data/mi_events.csv, data/counties.csv,
       data/prelim_vs_final_2025-06.csv and prints a plain-language summary.
"""
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stormlib as sl  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
START, END = date(2024, 10, 1), date(2026, 9, 30)
TODAY = date.today()


def month_key(day_s):
    return day_s[:7]


def main():
    gaz = sl.gazetteer_fetcher("G0")
    names = sl.county_names(gaz)
    wcm = sl.spc_wcm_fetcher("G0")
    daily = sl.spc_reports_fetcher("G0")

    events = []
    for y in (2024, 2025):
        for k in ("hail", "wind"):
            events.extend(sl.fetch_final_year(wcm, y, k, county_names=names))
    events = [e for e in events if START.isoformat() <= e["day"] <= "2025-12-31"]
    print(f"final 2024-25 MI events in window: {len(events)}")

    # 2026: daily preliminary files, Jan 1 through yesterday (also feeds G1 sample)
    n26 = 0
    for d, evs in sl.fetch_daily_range(daily, date(2026, 1, 1), min(END, TODAY)):
        events.extend(evs)
        n26 += len(evs)
    print(f"preliminary 2026 MI events: {n26}; requests={daily.stats['requests']} cache_hits={daily.stats['cache_hits']}")

    events.sort(key=lambda e: (e["day"], e["time_utc"]))
    sl.write_csv(DATA / "mi_events.csv", events,
                 ["day", "time_utc", "kind", "mag_text", "location", "county", "lat", "lon", "comments", "source"])

    qual = [e for e in events if sl.qualifies(e)]
    days_hail = defaultdict(set)
    days_wind = defaultdict(set)
    per_month = defaultdict(lambda: Counter())
    for e in qual:
        m = month_key(e["day"])
        per_month[m][e["kind"]] += 1
        (days_hail if e["kind"] == "hail" else days_wind)[m].add(e["day"])

    rows = []
    y, mo = START.year, START.month
    while date(y, mo, 1) <= END:
        m = f"{y}-{mo:02d}"
        alert_days = days_hail[m] | days_wind[m]
        counties = Counter(e["county"] for e in qual if month_key(e["day"]) == m)
        rows.append({
            "month": m, "alert_days": len(alert_days), "hail_days": len(days_hail[m]),
            "wind_days": len(days_wind[m]), "hail_reports": per_month[m]["hail"],
            "wind_reports": per_month[m]["wind"], "total_reports": sum(per_month[m].values()),
            "top_counties": "; ".join(f"{c} ({n})" for c, n in counties.most_common(3)),
            "data": "final" if y < 2026 else "preliminary",
        })
        mo += 1
        if mo == 13:
            y, mo = y + 1, 1
    sl.write_csv(DATA / "backtest.csv", rows, list(rows[0].keys()))

    # counties that recur (distinct alert days per county)
    cdays = defaultdict(set)
    creps = Counter()
    for e in qual:
        cdays[e["county"]].add(e["day"])
        creps[e["county"]] += 1
    crow = sorted(({"county": c, "alert_days": len(ds), "reports": creps[c]} for c, ds in cdays.items()),
                  key=lambda r: (-r["alert_days"], -r["reports"]))
    sl.write_csv(DATA / "counties.csv", crow, ["county", "alert_days", "reports"])

    # preliminary vs final for June 2025 (daily files vs Storm Data)
    pre = []
    for d, evs in sl.fetch_daily_range(daily, date(2025, 6, 1), date(2025, 6, 30)):
        pre.extend(e for e in evs if sl.qualifies(e))
    fin = [e for e in qual if e["day"].startswith("2025-06") and e["source"] == "final"]
    pdays, fdays = {e["day"] for e in pre}, {e["day"] for e in fin}
    cmp_rows = [{"measure": "qualifying MI reports", "preliminary_daily": len(pre), "final_storm_data": len(fin)},
                {"measure": "alert days", "preliminary_daily": len(pdays), "final_storm_data": len(fdays)},
                {"measure": "days in both", "preliminary_daily": len(pdays & fdays), "final_storm_data": len(pdays & fdays)},
                {"measure": "days only in preliminary", "preliminary_daily": ",".join(sorted(pdays - fdays)), "final_storm_data": ""},
                {"measure": "days only in final", "preliminary_daily": "", "final_storm_data": ",".join(sorted(fdays - pdays))}]
    sl.write_csv(DATA / "prelim_vs_final_2025-06.csv", cmp_rows, ["measure", "preliminary_daily", "final_storm_data"])

    # summary
    total_days = sum(r["alert_days"] for r in rows)
    print(f"\nBACKTEST {START} .. {END}: {len(qual)} qualifying MI reports on {total_days} alert days")
    for r in rows:
        print(f"  {r['month']}  alert_days={r['alert_days']:2d}  hail={r['hail_reports']:3d} wind={r['wind_reports']:3d}  {r['top_counties']}")
    print("\nTop counties (alert days, reports):")
    for r in crow[:15]:
        print(f"  {r['county']:14s} {r['alert_days']:3d} {r['reports']:4d}")
    print("\nJune 2025 preliminary vs final:")
    for r in cmp_rows:
        print(f"  {r['measure']:28s} {r['preliminary_daily']!s:>12s} {r['final_storm_data']!s:>12s}")
    print(f"\nrequests: wcm={wcm.stats} daily={daily.stats} gaz={gaz.stats}")


if __name__ == "__main__":
    main()
