"""Rebuild the Storm Lead morning alert from live SPC data.

Default: yesterday's SPC convective day (12Z yesterday to 12Z today), which is what a 7am
email would cover. Pass a date (YYYY-MM-DD) to rebuild a specific day, or --latest to walk
back from yesterday to the most recent day that has any Michigan report.

    python lanes/storm-lead/refresh.py                 # yesterday
    python lanes/storm-lead/refresh.py 2026-07-18      # one day
    python lanes/storm-lead/refresh.py --latest --gate G1

Writes lanes/storm-lead/samples/storm_lead_alert.{csv,html,pdf} via core.samples (the email
attachment), and keeps the G1 web prototype in lanes/storm-lead/app/ live by writing:
    app/data/latest.json    the day the app opens on (yesterday, or the most recent storm day
                            when yesterday had no qualifying report; `is_fallback` says which)
    app/data/days.json      the last 30 convective days with every qualifying report, for the
                            replay bar (SPC daily files through the registered fetcher; a day the
                            budget or network blocks is filled from data/mi_events.csv and marked)
    app/data/warnings.json  active NWS alerts for Michigan that matter to a roofer (severe
                            thunderstorm, tornado, wind, hail, flood), with polygons when NWS gives them
    app/data/mi_state.json, mi_counties.json   copied from core/web/geo (Census TIGERweb, public domain)
Pass --no-app to skip the app files.
"""
import csv
import json
import shutil
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stormlib as sl  # noqa: E402
from core import samples  # noqa: E402
from core.fetch import BudgetExceeded, FetchError, Fetcher  # noqa: E402

HERE = Path(__file__).resolve().parent
APP_DATA = HERE / "app" / "data"
GEO_SRC = sl.ROOT / "core" / "web" / "geo"
ARCHIVE_CSV = HERE / "data" / "mi_events.csv"
DAYS_WINDOW = 30
NWS_ALERTS_URL = "https://api.weather.gov/alerts/active"
# NWS event names that matter to a roofer (substring match, case-insensitive)
WARN_KEYWORDS = ("tornado", "thunderstorm", "wind", "hail", "flood")
COLS = [("time_local", "Time (ET)"), ("kind", "Type"), ("mag_text", "Hail size / wind"), ("location", "Location"),
        ("county", "County"), ("zips", "Nearby ZIPs (approx.)"), ("comments", "NWS comments")]
WIDTHS = [48, 36, 70, 95, 62, 110, 111]


def to_local(hhmm_utc, day):
    """SPC times are UTC HHMM. Michigan is UTC-4 in summer (EDT), UTC-5 in winter (EST)."""
    try:
        h, m = int(hhmm_utc[:2]), int(hhmm_utc[2:])
    except ValueError:
        return hhmm_utc
    d = date.fromisoformat(day)
    dst = date(d.year, 3, 8 + (6 - date(d.year, 3, 8).weekday()) % 7) <= d < date(d.year, 11, 1 + (6 - date(d.year, 11, 1).weekday()) % 7)
    off = 4 if dst else 5
    lh = (h - off) % 24
    ampm = "am" if lh < 12 else "pm"
    return f"{(lh % 12) or 12}:{m:02d} {ampm}" + ("" if h >= off else " (+1d)")


def build(day, gate="refresh", out_dir=None, basename="storm_lead_alert"):
    out_dir = Path(out_dir or HERE / "samples")
    spc = sl.spc_reports_fetcher(gate)
    gaz = sl.gazetteer_fetcher(gate)
    zctas, gaz_year = sl.mi_zctas(gaz)

    events = sl.fetch_daily(spc, day, "hail") + sl.fetch_daily(spc, day, "wind")
    qual = [e for e in events if sl.qualifies(e)]
    qual.sort(key=lambda e: e["time_utc"])
    all_zips = Counter()
    for e in qual:
        e["time_local"] = to_local(e["time_utc"], e["day"])
        e["kind"] = "Hail" if e["kind"] == "hail" else "Wind"
        z = sl.nearby_zctas(e["lat"], e["lon"], zctas) if e["lat"] is not None else []
        e["zips"] = ", ".join(z)
        all_zips.update(z)

    counties = Counter(e["county"] for e in qual)
    hail = [e for e in qual if e["kind"] == "Hail"]
    wind = [e for e in qual if e["kind"] == "Wind"]
    biggest = max((e["mag"] for e in hail if e["mag"]), default=0)
    nice = day.strftime("%A %B %d, %Y").replace(" 0", " ")
    title = f"Storm Lead alert: Michigan, {nice}"
    if qual:
        subtitle = (f"{len(qual)} qualifying NWS reports: {len(hail)} hail 1in+, {len(wind)} damaging wind, "
                    f"{len(counties)} counties. Window: 8am {day.strftime('%b %d').replace(' 0', ' ')} to 8am next day (ET).")
    else:
        subtitle = "No qualifying Michigan hail (1in+) or damaging-wind reports for this storm day. No alert would be sent."
    kpis = [("qualifying reports", len(qual)), ("counties hit", len(counties)),
            ("largest hail", f"{biggest:.2f} in" if biggest else "none"), ("ZIPs to canvass", len(all_zips))]
    notes = [
        "Counties hit (most reports first): " + ", ".join(f"{c} ({n})" for c, n in counties.most_common()) if counties else "",
        "Which ZIPs to canvass (most reports first): " + ", ".join(f"{z} ({n})" for z, n in all_zips.most_common(40)) if all_zips else "",
        "Alert rule: hail 1.00 inch or larger, wind gust 58 mph or more, or an NWS wind-damage report with no measured speed.",
        f"ZIP codes are approximate: each report is a point, and we list the ZIP Code Tabulation Areas whose Census {gaz_year} "
        "centroid is within about 5 miles of it (nearest always included). Treat them as 'start here', not as a property list.",
        "Reports are preliminary local storm reports relayed by NWS offices (GRR, DTX, APX, MQT, IWX). Late reports can be "
        "added for several days; the final record is published months later in NWS Storm Data.",
    ]
    notes = [n for n in notes if n]
    paths = samples.write_all(qual, COLS, out_dir, title=title, subtitle=subtitle, notes=notes,
                              source_line="Source: NOAA Storm Prediction Center storm reports; ZIP centroids: US Census Bureau Gazetteer.",
                              basename=basename, pdf_widths=WIDTHS, kpis=kpis)
    return qual, paths, {"spc": spc.stats, "gaz": gaz.stats}


# ---------------- web prototype data (app/data/*.json) ----------------
def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fmt_day(d):
    return d.strftime("%A %B %d, %Y").replace(" 0", " ")


def severity(e):
    """Sort key for the report list: hail first (by size), then measured wind, then damage-only reports."""
    if e["kind"] == "hail":
        return 100 + (e["mag"] or 0) * 20
    return e["mag"] if e["mag"] is not None else 50


def shape(e, zctas):
    """One qualifying SPC event in the shape the web app renders."""
    zips = sl.nearby_zctas(e["lat"], e["lon"], zctas) if e["lat"] is not None else []
    return {
        "lat": e["lat"], "lon": e["lon"], "kind": e["kind"], "mag": e["mag"], "mag_text": e["mag_text"],
        "time_utc": e["time_utc"], "time_local": to_local(e["time_utc"], e["day"]),
        "location": e["location"], "county": e["county"], "zips": zips, "comments": e["comments"],
        "severity": round(severity(e), 1), "source": e.get("source", "preliminary"),
    }


def day_record(day, events, zctas, source="spc"):
    qual = sorted((e for e in events if sl.qualifies(e)), key=severity, reverse=True)
    reports = [shape(e, zctas) for e in qual]
    hail = [r["mag"] for r in reports if r["kind"] == "hail" and r["mag"]]
    wind = [r["mag"] for r in reports if r["kind"] == "wind" and r["mag"]]
    return {
        "day": day.isoformat(), "count": len(reports),
        "hail": sum(1 for r in reports if r["kind"] == "hail"), "wind": sum(1 for r in reports if r["kind"] == "wind"),
        "max_hail": max(hail, default=None), "max_wind": max(wind, default=None),
        "counties": dict(Counter(r["county"] for r in reports).most_common()),
        "zips": dict(Counter(z for r in reports for z in r["zips"]).most_common()),
        "reports": reports, "source": source,
    }


def archive_events(day):
    """Qualifying events for one day from data/mi_events.csv (the 24-month backtest), used when the live
    SPC fetch is blocked. Rows there already pass the alert rule."""
    if not ARCHIVE_CSV.exists():
        return []
    out = []
    with open(ARCHIVE_CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["day"] != day.isoformat():
                continue
            mt = r["mag_text"]
            mag = float(mt.split()[0]) if mt and mt[0].isdigit() else None
            out.append({"day": r["day"], "time_utc": r["time_utc"], "kind": r["kind"], "mag": mag, "mag_text": mt,
                        "location": r["location"], "county": r["county"], "state": "MI",
                        "lat": float(r["lat"]) if r["lat"] else None, "lon": float(r["lon"]) if r["lon"] else None,
                        "comments": r["comments"], "source": "archive"})
    return out


def build_days(spc, zctas, end, n=DAYS_WINDOW):
    """The last n convective days ending at `end`, each with its qualifying reports. Returns (days, notes)."""
    start = end - timedelta(days=n - 1)
    days, notes, blocked = [], [], 0
    for d in (start + timedelta(days=i) for i in range(n)):
        try:
            evs = sl.fetch_daily(spc, d, "hail") + sl.fetch_daily(spc, d, "wind")
            days.append(day_record(d, evs, zctas))
        except (BudgetExceeded, FetchError) as e:
            blocked += 1
            days.append(day_record(d, archive_events(d), zctas, source="archive"))
            if blocked == 1:
                notes.append(f"live SPC fetch blocked from {d}: {str(e)[:120]}; those days come from data/mi_events.csv")
    return days, notes


def fetch_warnings(gate):
    """Active NWS alerts for Michigan, filtered to events a roofer cares about."""
    out = {"as_of": _now_iso(), "source": "National Weather Service API, alerts/active?area=MI",
           "kept_events": list(WARN_KEYWORDS), "total_active": 0, "warnings": [], "error": ""}
    try:
        f = Fetcher("nws_api", lane=sl.LANE, gate=gate)
        data = f.get_json(NWS_ALERTS_URL, params={"area": "MI"}, ttl=600,
                          headers={"Accept": "application/geo+json"})
    except (BudgetExceeded, FetchError) as e:
        out["error"] = str(e)[:200]
        return out
    feats = data.get("features", [])
    out["total_active"] = len(feats)
    for ft in feats:
        p = ft.get("properties", {})
        ev = (p.get("event") or "").lower()
        if not any(k in ev for k in WARN_KEYWORDS):
            continue
        out["warnings"].append({
            "id": p.get("id") or ft.get("id"), "event": p.get("event"), "severity": p.get("severity"),
            "urgency": p.get("urgency"), "certainty": p.get("certainty"), "headline": p.get("headline"),
            "areaDesc": p.get("areaDesc"), "description": (p.get("description") or "")[:600],
            "sent": p.get("sent"), "onset": p.get("onset"), "expires": p.get("expires"), "ends": p.get("ends"),
            "sender": p.get("senderName"), "geometry": ft.get("geometry"),
            "zones": [z.rsplit("/", 1)[-1] for z in (p.get("affectedZones") or [])],
        })
    return out


def shown_label(day, requested, is_fallback):
    if not is_fallback:
        return f"Yesterday's storm day: {fmt_day(day)}" if day == sl.yesterday_convective_day() else fmt_day(day)
    return f"Most recent storm day: {fmt_day(day)} (no qualifying reports on {fmt_day(requested)})"


def write_app_data(requested, shown, shown_rec, days, warnings, notes, gaz_year):
    APP_DATA.mkdir(parents=True, exist_ok=True)
    gen = _now_iso()
    is_fallback = shown != requested
    latest = {
        "generated_at": gen, "requested_day": requested.isoformat(), "day": shown.isoformat(),
        "is_fallback": is_fallback, "label": shown_label(shown, requested, is_fallback),
        "window_note": "SPC convective day: 8am ET to 8am ET the next morning (12Z to 12Z)",
        "rule": "hail 1.00 in or larger, wind gust 58 mph or more, or an NWS wind-damage report with no measured speed",
        "zip_note": f"ZIPs are Census {gaz_year} ZCTAs whose centroid is within about 5 miles of the report point (nearest always included).",
        **{k: v for k, v in shown_rec.items() if k != "day"},
        "sources": ["NOAA Storm Prediction Center storm reports (preliminary local storm reports, public domain)",
                    "National Weather Service API active alerts (public domain)",
                    f"US Census Bureau Gazetteer {gaz_year} ZCTA centroids and TIGERweb boundaries (public domain)"],
    }
    (APP_DATA / "latest.json").write_text(json.dumps(latest, separators=(",", ":")), encoding="utf-8")
    (APP_DATA / "days.json").write_text(json.dumps({
        "generated_at": gen, "start": days[0]["day"], "end": days[-1]["day"], "notes": notes,
        "days": days}, separators=(",", ":")), encoding="utf-8")
    (APP_DATA / "warnings.json").write_text(json.dumps(warnings, separators=(",", ":")), encoding="utf-8")
    for name in ("mi_state.json", "mi_counties.json"):
        src = GEO_SRC / name
        if src.exists():
            shutil.copy(src, APP_DATA / name)
    return {k: (APP_DATA / f"{k}.json").stat().st_size for k in ("latest", "days", "warnings")}


def refresh_app(day, gate, explicit_day):
    """Write every app/data file. The 30-day window ends at the anchor (yesterday, or the explicit date).
    When the anchor has no qualifying report and no explicit date was given, the app opens on the most
    recent day that has one (first from the window, then walking back up to 120 more days)."""
    spc = sl.spc_reports_fetcher(gate)
    gaz = sl.gazetteer_fetcher(gate)
    zctas, gaz_year = sl.mi_zctas(gaz)
    anchor = day if explicit_day else sl.yesterday_convective_day()
    days, notes = build_days(spc, zctas, anchor)
    by_day = {d["day"]: d for d in days}
    shown = day
    if not explicit_day and by_day.get(anchor.isoformat(), {}).get("count", 0) == 0:
        with_reports = [d for d in days if d["count"]]
        if with_reports:
            shown = date.fromisoformat(with_reports[-1]["day"])
        else:
            older = latest_day_with_reports(gate, start=anchor - timedelta(days=DAYS_WINDOW), max_back=120)
            shown = older or anchor
            if older is None:
                notes.append("no Michigan storm day found in the last 150 days; the app opens on an empty day")
    if shown.isoformat() in by_day:
        rec = by_day[shown.isoformat()]
    else:
        try:
            rec = day_record(shown, sl.fetch_daily(spc, shown, "hail") + sl.fetch_daily(spc, shown, "wind"), zctas)
        except (BudgetExceeded, FetchError):
            rec = day_record(shown, archive_events(shown), zctas, source="archive")
    warnings = fetch_warnings(gate)
    sizes = write_app_data(anchor, shown, rec, days, warnings, notes, gaz_year)
    return shown, sizes, warnings, notes


def latest_day_with_reports(gate, start=None, max_back=400):
    spc = sl.spc_reports_fetcher(gate)
    d = start or sl.yesterday_convective_day()
    for _ in range(max_back):
        evs = sl.fetch_daily(spc, d, "hail") + sl.fetch_daily(spc, d, "wind")
        if any(sl.qualifies(e) for e in evs):
            return d
        d -= timedelta(days=1)
    return None


if __name__ == "__main__":
    gate = sys.argv[sys.argv.index("--gate") + 1] if "--gate" in sys.argv else "refresh"
    args = [a for i, a in enumerate(sys.argv[1:], 1) if not a.startswith("--") and sys.argv[i - 1] != "--gate"]
    if "--latest" in sys.argv:
        day = latest_day_with_reports(gate)
    elif args:
        day = date.fromisoformat(args[0])
    else:
        day = sl.yesterday_convective_day()
    qual, paths, stats = build(day, gate)
    print(f"day {day}: {len(qual)} qualifying MI reports")
    for k, p in paths.items():
        print(f"  {k}: {p}")
    print("  fetch stats:", stats)
    if "--no-app" not in sys.argv:
        shown, sizes, warnings, notes = refresh_app(day, gate, explicit_day=bool(args))
        print(f"app: opens on {shown}; {len(warnings['warnings'])} of {warnings['total_active']} active NWS alerts kept"
              + (f" (NWS error: {warnings['error']})" if warnings["error"] else ""))
        print("  app/data sizes (bytes):", sizes)
        for n in notes:
            print("  note:", n)
