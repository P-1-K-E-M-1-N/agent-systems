"""Permit Radar weekly refresh: rebuilds lanes/permit-radar/samples/ (CSV/HTML/PDF lead sheet, the PDF is
the email attachment) and the web prototype's data files in lanes/permit-radar/app/data/ from live Detroit data.
Run from repo root (the daily tick does this): python lanes/permit-radar/refresh.py [--days 7] [--weeks 8] [--gate G1]

Sources (all registered in lanes/permit-radar/sources.json): Detroit BSEED building permits,
trades permits (electrical / mechanical / plumbing), demolition permits.
People-data rule: owner_name and contact_name are never requested. Contractor of record is a
business name (contact_business_name / demolition_contractor) only.

One fetch pass pulls `weeks` x 7 days from each layer (about 7 paged requests; 6 h cache); the lead sheet and
app/data/latest.json take the last `days` days of that, app/data/weeks.json buckets all of it by 7-day week.

Outputs:
  samples/lead_sheet.{csv,html,pdf}, samples/by_trade/<trade>.csv, data/lead_sheet_stats.json
  app/data/latest.json         last 7 days, one object per permit (lat/lon from the layer's own point geometry)
  app/data/weeks.json          8 weeks of permit counts per trade tag (and per tag combination, for multi-select)
  app/data/detroit_zctas.json  482xx ZCTA polygons (subset of core/web/geo/mi_zctas.json) with centroids
  app/data/wayne_county.json   Wayne County outline (from core/web/geo/mi_counties.json)
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core import registry, samples  # noqa: E402
from core.fetch import Fetcher, arcgis_query_all  # noqa: E402

LANE = ROOT / "lanes" / "permit-radar"
SAMPLES = LANE / "samples"
DATA = LANE / "data"
APP_DATA = LANE / "app" / "data"
GEO = ROOT / "core" / "web" / "geo"

# trade tag -> regex on permit_type + work_description (case-insensitive)
TRADE_RULES = [
    ("roofing", r"\b(?:re-?roof\w*|roof\w*|shingle\w*|tear[- ]?off|membrane)"),
    ("electrical", r"\b(?:electric\w*|wiring|rewir\w*|panel upgrade|service upgrade|lighting|ev charger|solar)"),
    ("hvac", r"\b(?:hvac|mechanical permit|furnace\w*|a/c\b|ac unit|air[- ]?cond\w*|boiler\w*|duct\w*|heat pump|rooftop unit|rtu\b|ventilat\w*|exhaust)"),
    ("plumbing", r"\b(?:plumb\w*|water heater|sewer\w*|drain\w*|backflow|back ?water valve|bwv\b|gas line|gas piping|water service|re-?pipe\w*)"),
    ("demolition", r"\b(?:demo\b|demolition|demolish\w*|wreck\w*|tear[- ]?down|razing|raze\b)"),
    ("demolition_dumpster", r"\b(?:demo\b|demolition|demolish\w*|wreck\w*|tear[- ]?down|gut\b|gutted|interior alteration\w*|renovat\w*|remodel\w*|rehab\w*|addition\b|new construction|new build\w*|build[- ]?out)"),
]
TRADE_ORDER = ["roofing", "electrical", "hvac", "plumbing", "demolition", "demolition_dumpster", "general"]
TRADE_LABELS = {"roofing": "Roofing", "electrical": "Electrical", "hvac": "HVAC", "plumbing": "Plumbing",
                "demolition": "Demolition", "demolition_dumpster": "Dumpster-relevant", "general": "General building"}
# utility / city programme work that is not a sales lead for a private trade
UTILITY_RE = re.compile(r"\b(DWSD|LSLR|lead service line|lead service replacement)\b", re.I)
SOURCES = {"Building": "detroit_permits", "Trades": "detroit_trades_permits", "Demolition": "detroit_demolition_permits"}


def tag(permit_type, work):
    text = f"{permit_type or ''} {work or ''}"
    tags = [name for name, pat in TRADE_RULES if re.search(pat, text, re.I)]
    return tags or ["general"]


def day(v):
    """ArcGIS returns DateOnly fields as 'YYYY-MM-DD' strings and Date fields as epoch ms; accept both."""
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(v / 1000, timezone.utc).date().isoformat()
    return str(v)[:10] if v else ""


def money(v):
    return f"${v:,.0f}" if isinstance(v, (int, float)) and v > 0 else ""


def num(v):
    return float(v) if isinstance(v, (int, float)) and v > 0 else None


def coord(a):
    """The three layers are point layers and also expose longitude/latitude attributes; use those."""
    lat, lon = a.get("latitude"), a.get("longitude")
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and 41 < lat < 43.5 and -84.5 < lon < -82:
        return round(lat, 6), round(lon, 6)
    return None, None


def record_url(source, record_id):
    """The layers expose no portal URL. The building layer carries no people fields, so its ArcGIS record view
    (the city's own open-data service, HTML) is a safe deep link. Trades and demolition records include owner_name
    on the service side, so no link for those (people-data rule)."""
    if source != "Building" or not record_id:
        return None
    base = registry.get(SOURCES[source])["base_url"].rstrip("/")
    rid = str(record_id).replace("'", "")
    return f"{base}/query?where=record_id%3D%27{rid}%27&outFields=record_id,address,issued_date,permit_type,work_description,amt_estimated_contractor_cost,zip_code,neighborhood&f=html"


def fetch(since, gate):
    where = f"issued_date >= DATE '{since}'"
    rows, stats = [], {}

    f = Fetcher("detroit_permits", lane="permit-radar", gate=gate)
    for a in arcgis_query_all(f, registry.get("detroit_permits")["base_url"], where=where, order_by="issued_date DESC",
                              max_records=20000,
                              out_fields="record_id,address,issued_date,permit_type,construction_type,work_description,"
                                         "amt_estimated_contractor_cost,zip_code,neighborhood,council_district,longitude,latitude"):
        lat, lon = coord(a)
        rows.append({"source": "Building", "record_id": a.get("record_id"), "issued": day(a.get("issued_date")),
                     "address": a.get("address"), "zip": a.get("zip_code"), "neighborhood": a.get("neighborhood"),
                     "permit_type": a.get("permit_type"), "construction_type": a.get("construction_type"),
                     "est_cost_num": a.get("amt_estimated_contractor_cost"), "work": a.get("work_description"),
                     "contractor": "", "lat": lat, "lon": lon})
    stats["building"] = dict(f.stats)

    g = Fetcher("detroit_trades_permits", lane="permit-radar", gate=gate)
    for a in arcgis_query_all(g, registry.get("detroit_trades_permits")["base_url"], where=where, order_by="issued_date DESC",
                              max_records=20000,
                              out_fields="record_id,address,issued_date,permit_type,work_description,"
                                         "contact_business_name,zip_code,neighborhood,council_district,longitude,latitude"):
        lat, lon = coord(a)
        rows.append({"source": "Trades", "record_id": a.get("record_id"), "issued": day(a.get("issued_date")),
                     "address": a.get("address"), "zip": a.get("zip_code"), "neighborhood": a.get("neighborhood"),
                     "permit_type": a.get("permit_type"), "construction_type": "", "est_cost_num": None,
                     "work": a.get("work_description"), "contractor": a.get("contact_business_name") or "",
                     "lat": lat, "lon": lon})
    stats["trades"] = dict(g.stats)

    h = Fetcher("detroit_demolition_permits", lane="permit-radar", gate=gate)
    for a in arcgis_query_all(h, registry.get("detroit_demolition_permits")["base_url"], where=where, order_by="issued_date DESC",
                              max_records=20000,
                              out_fields="record_id,address,issued_date,work_description,demolition_contractor,"
                                         "zip_code,neighborhood,council_district,longitude,latitude"):
        lat, lon = coord(a)
        rows.append({"source": "Demolition", "record_id": a.get("record_id"), "issued": day(a.get("issued_date")),
                     "address": a.get("address"), "zip": a.get("zip_code"), "neighborhood": a.get("neighborhood"),
                     "permit_type": "Demolition Permit", "construction_type": "", "est_cost_num": None,
                     "work": a.get("work_description"), "contractor": a.get("demolition_contractor") or "",
                     "lat": lat, "lon": lon})
    stats["demolition"] = dict(h.stats)
    return rows, stats


def clean(raw):
    """Drop utility rows, tag trades, normalise text. Returns (rows, utility_count)."""
    rows, utility = [], 0
    for r in raw:
        if UTILITY_RE.search(r.get("work") or "") or UTILITY_RE.search(r.get("contractor") or ""):
            utility += 1
            continue
        tags = tag(r["permit_type"], r["work"])
        if r["source"] == "Demolition":
            tags = ["demolition", "demolition_dumpster"] + [t for t in tags if t not in ("general", "demolition", "demolition_dumpster")]
        r["tag_list"] = [t for t in TRADE_ORDER if t in tags]
        r["trades"] = ", ".join(r["tag_list"])
        r["est_cost_val"] = num(r.pop("est_cost_num"))
        r["est_cost"] = money(r["est_cost_val"])
        r["work_summary"] = re.sub(r"\s+", " ", (r.get("work") or "")).strip()[:140]
        z = str(r["zip"] or "").strip()[:5]
        r["zip"] = z if re.fullmatch(r"\d{5}", z) else ""
        rows.append(r)
    rows.sort(key=lambda r: (r["issued"], r["source"]), reverse=True)
    return rows, utility


# ---------- geography ----------
def _poly_centroid(rings):
    """Area-weighted centroid of a polygon's outer ring (lon, lat)."""
    ring = rings[0]
    a = cx = cy = 0.0
    for i in range(len(ring) - 1):
        x0, y0 = ring[i]
        x1, y1 = ring[i + 1]
        cross = x0 * y1 - x1 * y0
        a += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if abs(a) < 1e-12:
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        return sum(xs) / len(xs), sum(ys) / len(ys)
    a *= 0.5
    return cx / (6 * a), cy / (6 * a)


def centroid(geom):
    if geom["type"] == "Polygon":
        return _poly_centroid(geom["coordinates"])
    # MultiPolygon: centroid of the largest part
    best = max(geom["coordinates"], key=lambda rings: abs(_ring_area(rings[0])))
    return _poly_centroid(best)


def _ring_area(ring):
    return sum(ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1] for i in range(len(ring) - 1)) / 2


def write_geo():
    """482xx ZCTAs (Detroit and its inner ring) and the Wayne County outline, from the shared Census files."""
    zctas = json.loads((GEO / "mi_zctas.json").read_text(encoding="utf-8"))
    feats = []
    for ft in zctas["features"]:
        z = str(ft["properties"].get("ZCTA5", ""))
        if z.startswith("482"):
            lon, lat = centroid(ft["geometry"])
            feats.append({"type": "Feature", "properties": {"ZCTA5": z, "cx": round(lon, 5), "cy": round(lat, 5)},
                          "geometry": ft["geometry"]})
    feats.sort(key=lambda f: f["properties"]["ZCTA5"])
    APP_DATA.mkdir(parents=True, exist_ok=True)
    (APP_DATA / "detroit_zctas.json").write_text(json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")),
                                                 encoding="utf-8")
    counties = json.loads((GEO / "mi_counties.json").read_text(encoding="utf-8"))
    wayne = [ft for ft in counties["features"] if ft["properties"].get("GEOID") == "26163"]
    (APP_DATA / "wayne_county.json").write_text(json.dumps({"type": "FeatureCollection", "features": wayne}, separators=(",", ":")),
                                                encoding="utf-8")
    return {f["properties"]["ZCTA5"]: (f["properties"]["cy"], f["properties"]["cx"]) for f in feats}


def label(start, end):
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    if s.month == e.month:
        return f"{s.strftime('%b')} {s.day} to {e.day}"
    return f"{s.strftime('%b')} {s.day} to {e.strftime('%b')} {e.day}"


# ---------- app data ----------
def write_latest(rows, since, today, zip_centroids, generated):
    permits, zip_fallback = [], 0
    for r in rows:
        lat, lon, geo = r["lat"], r["lon"], "point"
        if lat is None and r["zip"] in zip_centroids:
            lat, lon = zip_centroids[r["zip"]]
            geo, zip_fallback = "zip", zip_fallback + 1
        permits.append({"id": r["record_id"], "issued": r["issued"], "trades": r["tag_list"], "source": r["source"],
                        "address": r["address"] or "", "zip": r["zip"], "neighborhood": r["neighborhood"] or "",
                        "permit_type": r["permit_type"] or "", "est_cost": r["est_cost_val"],
                        "work_summary": r["work_summary"], "contractor": r["contractor"] or "",
                        "lat": lat, "lon": lon, "geo": geo if lat is not None else None,
                        "record_url": record_url(r["source"], r["record_id"])})
    permits.sort(key=lambda p: (-(p["est_cost"] or 0), p["issued"]), reverse=False)
    out = {"generated_at": generated, "week": {"start": since, "end": today, "label": label(since, today)},
           "trades": [{"key": t, "label": TRADE_LABELS[t]} for t in TRADE_ORDER],
           "geometry_note": f"{len(permits) - zip_fallback} of {len(permits)} permits placed at the point the city publishes"
                            + (f"; {zip_fallback} had no point and sit at their ZIP centroid" if zip_fallback else ""),
           "sources": {"Building": "BSEED building permits", "Trades": "BSEED trades permits (electrical, mechanical, plumbing)",
                       "Demolition": "BSEED demolition permits"},
           "permits": permits}
    (APP_DATA / "latest.json").write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    return len(permits), zip_fallback


def write_weeks(rows, today, weeks, generated):
    """7-day buckets ending today (bucket 0 = the same window as latest.json). counts per tag, plus counts per
    exact tag combination so the page can count a multi-trade selection without double counting."""
    buckets = [{"start": (today - timedelta(days=7 * (k + 1) - 1)).isoformat(), "end": (today - timedelta(days=7 * k)).isoformat(),
                "counts": Counter(), "combos": Counter(), "total": 0} for k in range(weeks)]
    for r in rows:
        try:
            diff = (today - date.fromisoformat(r["issued"])).days
        except ValueError:
            continue
        k = diff // 7
        if 0 <= k < weeks:
            b = buckets[k]
            b["total"] += 1
            for t in r["tag_list"]:
                b["counts"][t] += 1
            b["combos"]["|".join(r["tag_list"])] += 1
    out = {"generated_at": generated, "weeks": [
        {"start": b["start"], "end": b["end"], "label": label(b["start"], b["end"]), "total": b["total"],
         "counts": dict(b["counts"]), "combos": dict(b["combos"])} for b in reversed(buckets)]}
    (APP_DATA / "weeks.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    return [b["total"] for b in reversed(buckets)]


def build(days=7, weeks=8, gate="G1"):
    today = date.today()
    since = (today - timedelta(days=days - 1)).isoformat()          # 7 calendar days incl. today
    since_all = (today - timedelta(days=7 * weeks - 1)).isoformat()  # 8 weeks for the trend, one fetch pass
    raw, fetch_stats = fetch(since_all, gate)
    all_rows, utility_all = clean(raw)
    rows = [r for r in all_rows if r["issued"] >= since]
    utility = sum(1 for r in raw if r["issued"] >= since and (UTILITY_RE.search(r.get("work") or "") or UTILITY_RE.search(r.get("contractor") or "")))
    today_s = today.isoformat()

    per_trade = Counter(t for r in rows for t in r["tag_list"])
    per_source = Counter(r["source"] for r in rows)
    with_contractor = sum(1 for r in rows if r["contractor"])

    cols = [("issued", "Issued"), ("trades", "Trade tags"), ("source", "Source"), ("address", "Address"),
            ("zip", "ZIP"), ("neighborhood", "Neighborhood"), ("permit_type", "Permit type"),
            ("est_cost", "Est. cost"), ("work_summary", "Work summary"), ("contractor", "Contractor of record")]
    pdf_cols = [("issued", "Issued"), ("trades", "Trade"), ("address", "Address"), ("zip", "ZIP"),
                ("permit_type", "Permit type"), ("est_cost", "Est. cost"), ("work_summary", "Work"),
                ("contractor", "Contractor of record")]
    kpis = [(TRADE_LABELS[t], per_trade.get(t, 0)) for t in TRADE_ORDER if t != "demolition"]
    notes = [
        f"{len(rows)} permits issued {since} to {today_s} across Detroit building ({per_source.get('Building', 0)}), "
        f"trades ({per_source.get('Trades', 0)}) and demolition ({per_source.get('Demolition', 0)}) permits. "
        f"{utility} DWSD lead-service-line utility permits were removed because they are city programme work, not leads.",
        "Trade tags come from keywords in the permit type and work description; a permit can carry several tags. "
        "'general' means a building permit (renovation, addition, new build) with no trade keyword: a subcontract lead for every trade.",
        f"Contractor of record is the licensed business that pulled the permit ({with_contractor} of {len(rows)} rows). "
        "Building permits do not list a contractor in the city data. No owner or individual names are included, by design.",
        "How a roofer reads this: roofing rows show who is already pulling roof permits near you (competitor map), "
        "general and demolition rows are jobs that will need a roof, trades or a dumpster next.",
    ]
    SAMPLES.mkdir(parents=True, exist_ok=True)
    paths = samples.write_all(
        rows, cols, SAMPLES, title=f"Permit Radar: Detroit lead sheet, week of {today_s}",
        subtitle=f"{len(rows)} permits issued {since} to {today_s}; tagged by trade. $30/month, delivered every Monday.",
        notes=notes, source_line="Data: City of Detroit Open Data Portal (BSEED building, trades and demolition permits), AS-IS.",
        basename="lead_sheet", kpis=kpis)
    # PDF with narrower columns (US Letter, 532pt usable)
    paths["pdf"] = samples.write_pdf(rows, pdf_cols, SAMPLES / "lead_sheet.pdf",
                                     title=f"Permit Radar: Detroit lead sheet, week of {today_s}",
                                     subtitle=f"{len(rows)} permits issued {since} to {today_s}; first 60 rows, full list in CSV.",
                                     notes=notes, source_line="Data: City of Detroit Open Data Portal (BSEED), AS-IS.",
                                     widths=[50, 58, 112, 30, 70, 44, 98, 70])
    by_trade = SAMPLES / "by_trade"
    for t in TRADE_ORDER:
        sub = [r for r in rows if t in r["tag_list"]]
        samples.write_csv(sub, cols, by_trade / f"{t}.csv")

    # web prototype data
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    zip_centroids = write_geo()
    n_latest, zip_fallback = write_latest(rows, since, today_s, zip_centroids, generated)
    week_totals = write_weeks(all_rows, today, weeks, generated)

    stats = {"built": generated, "since": since, "days": days, "weeks": weeks, "since_all": since_all,
             "rows": len(rows), "utility_rows_removed": utility, "rows_8w": len(all_rows), "utility_rows_removed_8w": utility_all,
             "per_trade": dict(per_trade), "per_source": dict(per_source), "with_contractor": with_contractor,
             "with_point": sum(1 for r in rows if r["lat"] is not None), "zip_centroid_fallback": zip_fallback,
             "week_totals_oldest_first": week_totals, "fetch": fetch_stats,
             "files": {k: str(p.relative_to(ROOT)) for k, p in paths.items()},
             "app_data": {p.name: p.stat().st_size for p in sorted(APP_DATA.glob("*.json"))}}
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "lead_sheet_stats.json").write_text(json.dumps(stats, indent=1), encoding="utf-8")
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--weeks", type=int, default=8)
    ap.add_argument("--gate", default="G1")
    a = ap.parse_args()
    print(json.dumps(build(a.days, a.weeks, a.gate), indent=1))
