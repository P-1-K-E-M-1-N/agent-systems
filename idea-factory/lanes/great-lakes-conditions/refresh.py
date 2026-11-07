"""Rebuild the Holland, MI conditions sample page from live public-domain data.

Run from repo root:  python lanes/great-lakes-conditions/refresh.py [--gate G1]
Writes samples/holland_mi.html, samples/holland_mi.csv, samples/holland_mi.json.

Sources (all US-government public domain, no keys): NOAA NDBC buoy 45029 (Holland Buoy, LimnoTech,
seasonal) and shore station HLNM4 (NOS 9087031, year-round); NOAA CO-OPS 9087031 water level + monthly
means; NWS api.weather.gov marine alerts + nearshore (NSH) forecast text from WFO Grand Rapids; NOAA GLERL
GLSEA Lake Michigan daily surface temperature + 1995-2025 average.
"""
import argparse
import json
import re
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core import samples  # noqa: E402
from core.fetch import Fetcher, FetchError  # noqa: E402

LANE = "great-lakes-conditions"
HERE = ROOT / "lanes" / LANE
LOC = {"slug": "holland_mi", "name": "Holland, MI (Lake Michigan)", "buoy": "45029", "shore": "HLNM4",
       "coops": "9087031", "zone_match": "Holland", "nws_office": "GRR", "lake_code": "m", "lake_name": "Lake Michigan"}
NOW = datetime.now(timezone.utc)
MISSING = "MM"


# ---------------------------------------------------------------- helpers
def eastern(dt_utc):
    """UTC -> America/Detroit without tzdata (US DST rule: 2nd Sun Mar 2:00 to 1st Sun Nov 2:00 local)."""
    y = dt_utc.year
    def nth_sunday(month, n):
        d = datetime(y, month, 1)
        d += timedelta(days=(6 - d.weekday()) % 7 + 7 * (n - 1))
        return d
    start = nth_sunday(3, 2).replace(hour=7)   # 2:00 EST = 07:00 UTC
    end = nth_sunday(11, 1).replace(hour=6)    # 2:00 EDT = 06:00 UTC
    naive = dt_utc.replace(tzinfo=None)
    off, tag = (-4, "EDT") if start <= naive < end else (-5, "EST")
    return (naive + timedelta(hours=off)).strftime("%b %d %I:%M %p ") + tag


def age_text(dt_utc):
    m = int((NOW - dt_utc).total_seconds() // 60)
    if m < 90:
        return f"{m} min ago"
    if m < 48 * 60:
        return f"{m // 60} h ago"
    return f"{m // 1440} days ago"


def ndbc_rows(text):
    lines = [l for l in text.splitlines() if l.strip()]
    hdr = lines[0].lstrip("#").split()
    out = []
    for l in lines[2:]:
        d = dict(zip(hdr, l.split()))
        try:
            d["_ts"] = datetime(int(d["YY"]), int(d["MM"]), int(d["DD"]), int(d["hh"]), int(d["mm"]), tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
        out.append(d)
    return out


def first_valid(rows, key, max_age_h=3):
    """Newest row with a real value for key (NDBC files are newest-first)."""
    for r in rows:
        v = r.get(key, MISSING)
        if v != MISSING and (NOW - r["_ts"]).total_seconds() <= max_age_h * 3600:
            return float(v), r["_ts"]
    return None, None


def m_to_ft(m):
    return m * 3.28084


def ms_to_kt(ms):
    return ms * 1.94384


def c_to_f(c):
    return c * 9 / 5 + 32


def compass(deg):
    pts = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return pts[int((deg + 11.25) // 22.5) % 16]


# ---------------------------------------------------------------- fetchers
def get_ndbc(gate):
    f = Fetcher("ndbc", lane=LANE, gate=gate)
    out = {}
    for key, sid in (("buoy", LOC["buoy"]), ("shore", LOC["shore"])):
        try:
            out[key] = ndbc_rows(f.get_text(f"https://www.ndbc.noaa.gov/data/realtime2/{sid}.txt"))
        except FetchError as e:
            out[key] = []
            out[key + "_error"] = str(e)[:100]
    return out


def get_coops(gate):
    f = Fetcher("coops", lane=LANE, gate=gate)
    base = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    common = {"station": LOC["coops"], "datum": "IGLD", "units": "english", "time_zone": "lst_ldt",
              "format": "json", "application": "IdeaFactory"}
    latest = f.get_json(base, {**common, "product": "water_level", "date": "latest"})
    means = []
    for a, b in ((1990, 1999), (2000, 2009), (2010, 2019), (2020, NOW.year)):
        try:
            j = f.get_json(base, {**common, "product": "monthly_mean", "begin_date": f"{a}0101",
                                  "end_date": f"{b}1231"}, ttl=7 * 86400)
            means.extend(j.get("data", []))
        except FetchError as e:
            means.append({"error": str(e)[:80]})
    return latest, means


def get_nws(gate):
    f = Fetcher("nws_api", lane=LANE, gate=gate)
    hdr = {"Accept": "application/geo+json"}
    zones = f.get_json("https://api.weather.gov/zones", {"type": "marine"}, headers=hdr, ttl=7 * 86400)
    mine = [z["properties"] for z in zones["features"] if LOC["zone_match"].lower() in z["properties"]["name"].lower()
            and z["properties"]["id"].startswith("LM")]
    ids = [z["id"] for z in mine]
    alerts = f.get_json("https://api.weather.gov/alerts/active", {"zone": ",".join(ids)}, headers=hdr, ttl=900) if ids else {"features": []}
    prods = f.get_json(f"https://api.weather.gov/products/types/NSH/locations/{LOC['nws_office']}", headers=hdr, ttl=1800)
    forecast = {}
    if prods.get("@graph"):
        p = f.get_json(prods["@graph"][0]["@id"], headers=hdr, ttl=1800)
        txt = p.get("productText", "")
        forecast["issued"] = p.get("issuanceTime")
        for zid in ids:
            m = re.search(zid + r"-\d{6}-\n(.*?)\n\$\$", txt, re.S)
            if m:
                forecast[zid] = m.group(1).strip()
    return mine, alerts.get("features", []), forecast


def get_glsea(gate):
    f = Fetcher("glerl", lane=LANE, gate=gate)
    base = "https://apps.glerl.noaa.gov/coastwatch/webdata/statistic/csv/"
    daily = f.get_text(base + f"all_year_glsea_avg_{LOC['lake_code']}_F.csv")
    avg = f.get_text(base + f"avgtemps-{LOC['lake_code']}_1995-{NOW.year}_F.csv")
    hdr = daily.splitlines()[0].split(",")
    col = hdr.index(str(NOW.year)) if str(NOW.year) in hdr else None
    latest_doy, latest_val = None, None
    if col is not None:
        for line in daily.splitlines()[1:]:
            parts = line.split(",")
            if len(parts) > col and parts[col].strip():
                latest_doy, latest_val = int(parts[0]), float(parts[col])
    normal = None
    if latest_doy:
        for line in avg.splitlines()[1:]:
            parts = line.split(",")
            if parts[0].strip() == str(latest_doy) and len(parts) > 1 and parts[1].strip():
                normal = float(parts[1])
    return latest_doy, latest_val, normal


# ---------------------------------------------------------------- build
def build(gate="G1"):
    rows, kpis, notes, snap = [], [], [], {"location": LOC, "generated_utc": NOW.isoformat(timespec="seconds")}
    gaps = []

    def add(metric, value, ts, station, source, note=""):
        rows.append({"metric": metric, "value": value, "observed": (eastern(ts) + f" ({age_text(ts)})") if ts else "",
                     "station": station, "source": source, "note": note})

    # --- NDBC
    nd = get_ndbc(gate)
    buoy, shore = nd["buoy"], nd["shore"]
    wvht, t = first_valid(buoy, "WVHT")
    if wvht is not None:
        dpd, _ = first_valid(buoy, "DPD")
        mwd, _ = first_valid(buoy, "MWD")
        txt = f"{m_to_ft(wvht):.1f} ft"
        detail = (f"period {dpd:.0f} s" if dpd else "") + (f", from {compass(mwd)}" if mwd is not None else "")
        kpis.append(("Waves (observed)", txt))
        add("Wave height", txt, t, f"NDBC buoy {LOC['buoy']} (Holland Buoy, LimnoTech)", "NOAA NDBC", detail)
        snap["waves_ft"] = round(m_to_ft(wvht), 1)
    else:
        last = buoy[0]["_ts"] if buoy else None
        gaps.append(f"Buoy {LOC['buoy']} is not reporting waves" + (f" (last report {eastern(last)})" if last else " (no realtime file: pulled for the season)")
                    + ". Great Lakes buoys are removed roughly Nov-Apr; waves below come from the NWS forecast instead.")
        kpis.append(("Waves (observed)", "buoy out"))
        add("Wave height", "no buoy data", last, f"NDBC buoy {LOC['buoy']}", "NOAA NDBC", "seasonal buoy, see NWS forecast")

    wspd, t = first_valid(shore, "WSPD")
    src_station = f"NOS shore station {LOC['shore']} (Holland, year-round)"
    if wspd is None:
        wspd, t = first_valid(buoy, "WSPD")
        src_station = f"NDBC buoy {LOC['buoy']}"
    if wspd is not None:
        gst, _ = first_valid(shore if "shore" in src_station else buoy, "GST")
        wdir, _ = first_valid(shore if "shore" in src_station else buoy, "WDIR")
        txt = f"{ms_to_kt(wspd):.0f} kt {compass(wdir) if wdir is not None else ''}".strip()
        kpis.append(("Wind", txt))
        add("Wind", txt, t, src_station, "NOAA NDBC", f"gusts {ms_to_kt(gst):.0f} kt" if gst else "")
        snap["wind_kt"] = round(ms_to_kt(wspd))
    else:
        gaps.append("No wind observation in the last 3 hours from the shore station or buoy.")
        kpis.append(("Wind", "n/a"))

    wtmp, t = first_valid(buoy, "WTMP")
    wsrc = f"NDBC buoy {LOC['buoy']}"
    if wtmp is None:
        wtmp, t = first_valid(shore, "WTMP")
        wsrc = f"NOS shore station {LOC['shore']}"
    if wtmp is not None:
        txt = f"{c_to_f(wtmp):.0f} F"
        kpis.append(("Water temp (nearshore)", txt))
        add("Water temperature, nearshore", txt, t, wsrc, "NOAA NDBC")
        snap["water_temp_f"] = round(c_to_f(wtmp))
    else:
        gaps.append("No nearshore water temperature in the last 3 hours.")
    atmp, t = first_valid(shore, "ATMP")
    if atmp is not None:
        add("Air temperature", f"{c_to_f(atmp):.0f} F", t, f"NOS shore station {LOC['shore']}", "NOAA NDBC")

    # --- GLERL GLSEA lake-wide
    try:
        doy, val, normal = get_glsea(gate)
        if val is not None:
            ts = datetime(NOW.year, 1, 1, tzinfo=timezone.utc) + timedelta(days=doy - 1)
            diff = f"{val - normal:+.1f} F vs 1995-2025 average ({normal:.1f} F)" if normal else ""
            add(f"{LOC['lake_name']} average surface temperature", f"{val:.1f} F", ts, "GLSEA satellite analysis (lake-wide)", "NOAA GLERL CoastWatch", diff)
            snap["lake_avg_temp_f"] = round(val, 1)
            snap["lake_avg_temp_vs_normal_f"] = round(val - normal, 1) if normal else None
    except FetchError as e:
        gaps.append(f"GLERL GLSEA unavailable: {str(e)[:80]}")

    # --- CO-OPS water level
    try:
        latest, means = get_coops(gate)
        d = latest["data"][0]
        lvl = float(d["v"])
        t_local = d["t"]
        month_vals = [float(m["MSL"]) for m in means if m.get("month") == str(NOW.month) and m.get("MSL") and int(m["year"]) < NOW.year]
        lt_avg = statistics.mean(month_vals) if month_vals else None
        last_year = next((float(m["MSL"]) for m in means if m.get("month") == str(NOW.month) and m.get("year") == str(NOW.year - 1) and m.get("MSL")), None)
        txt = f"{lvl:.2f} ft"
        kpis.append(("Water level (IGLD85)", txt))
        detail = ""
        if lt_avg:
            detail = f"{lvl - lt_avg:+.2f} ft vs long-term {NOW.strftime('%B')} average {lt_avg:.2f} ft ({min(int(m['year']) for m in means if m.get('year'))}-{NOW.year - 1}, {len(month_vals)} yrs)"
        if last_year:
            detail += f"; {lvl - last_year:+.2f} ft vs {NOW.strftime('%B')} {NOW.year - 1}"
        rows.append({"metric": "Water level", "value": txt, "observed": f"{t_local} local (6-min gauge)",
                     "station": f"CO-OPS {LOC['coops']} Holland", "source": "NOAA CO-OPS", "note": detail})
        snap.update({"water_level_ft_igld85": lvl, "water_level_vs_longterm_ft": round(lvl - lt_avg, 2) if lt_avg else None})
    except (FetchError, KeyError, IndexError) as e:
        gaps.append(f"CO-OPS water level unavailable: {str(e)[:80]}")
        kpis.append(("Water level", "n/a"))

    # --- NWS
    try:
        zones, alerts, forecast = get_nws(gate)
        zone_txt = "; ".join(f"{z['id']} {z['name']}" for z in zones)
        if alerts:
            for a in alerts:
                p = a["properties"]
                ends = p.get("ends") or p.get("expires") or ""
                add(f"Marine advisory: {p['event']}", p.get("headline", "")[:140], None, p.get("areaDesc", "")[:80], "National Weather Service", f"until {ends[:16]}")
            kpis.append(("Advisories", f"{len(alerts)} active"))
        else:
            kpis.append(("Advisories", "none"))
            rows.append({"metric": "Marine advisories", "value": "None active", "observed": eastern(NOW) + " (checked now)",
                         "station": zone_txt, "source": "National Weather Service", "note": ""})
        snap["advisories"] = [a["properties"]["event"] for a in alerts]
        for zid in [z["id"] for z in zones]:
            if zid in forecast:
                periods = re.findall(r"^\.(\S+?)\.\.\.(.*?)(?=^\.|\Z)", forecast[zid], re.S | re.M)
                for name, body in periods[:3]:
                    body = " ".join(body.split())
                    waves = re.search(r"Waves? ([^.]*)\.", body)
                    rows.append({"metric": f"Forecast {name.title()}", "value": (waves.group(0) if waves else body[:60]),
                                 "observed": "issued " + eastern(datetime.fromisoformat(forecast["issued"].replace("Z", "+00:00"))) if forecast.get("issued") else "",
                                 "station": f"NWS nearshore zone {zid}", "source": "National Weather Service (WFO Grand Rapids)", "note": body[:220]})
                if periods and not snap.get("waves_ft"):
                    w = re.search(r"Waves? ([^.]*)\.", " ".join(periods[0][1].split()))
                    if w:
                        kpis[0] = ("Waves (NWS forecast)", w.group(1).replace(" or less", "-"))
                snap["forecast_" + zid] = forecast[zid][:600]
    except FetchError as e:
        gaps.append(f"NWS unavailable: {str(e)[:80]}")

    # --- write
    cols = [("metric", "Metric"), ("value", "Value"), ("observed", "Observed / issued"), ("station", "Station / zone"),
            ("source", "Source"), ("note", "Detail")]
    notes = ["Nearshore conditions change fast; this page is a validation sample, refreshed on demand from live NOAA feeds. "
             "Buoy readings are at the buoy, not at the beach or pier."] + gaps
    out = HERE / "samples"
    subtitle = f"Live snapshot {eastern(NOW)} for boaters, anglers, paddlers and beach-goers. All data: US government, public domain."
    html = samples.write_html(rows, cols, out / f"{LOC['slug']}.html", f"{LOC['name']}: waves, wind, water temp, water level",
                              subtitle, notes, "Sources: NOAA NDBC, NOAA CO-OPS, National Weather Service, NOAA GLERL CoastWatch.", kpis)
    csv_p = samples.write_csv(rows, cols, out / f"{LOC['slug']}.csv")
    snap["kpis"] = kpis
    snap["gaps"] = gaps
    (out / f"{LOC['slug']}.json").write_text(json.dumps(snap, indent=1, default=str), encoding="utf-8")
    return html, csv_p, kpis, gaps


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", default="G1")
    a = ap.parse_args()
    html, csv_p, kpis, gaps = build(a.gate)
    print("wrote", html, "and", csv_p)
    for k, v in kpis:
        print(f"  {k}: {v}")
    for g in gaps:
        print("  GAP:", g)
