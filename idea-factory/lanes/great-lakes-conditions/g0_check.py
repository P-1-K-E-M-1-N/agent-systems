"""G0 data check for great-lakes-conditions: hit every candidate source through core.fetch
and record what works, how fresh it is, and (for NDBC) which Michigan stations are reporting
right now vs. pulled for winter.

Run from repo root:  python lanes/great-lakes-conditions/g0_check.py
Writes lanes/great-lakes-conditions/data/g0_results.json and prints a summary.
"""
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.fetch import Fetcher, FetchError  # noqa: E402

LANE = "great-lakes-conditions"
OUT = ROOT / "lanes" / LANE / "data" / "g0_results.json"
NOW = datetime.now(timezone.utc)
results = {"checked_at": NOW.isoformat(timespec="seconds"), "sources": {}}


def note(src, key, val):
    results["sources"].setdefault(src, {})[key] = val


# ---------------------------------------------------------------- NDBC
def ndbc_latest(text):
    """Parse an NDBC realtime2 .txt; return (latest_obs_dict, age_hours)."""
    lines = [l for l in text.splitlines() if l.strip()]
    if len(lines) < 3:
        return None, None
    hdr = lines[0].lstrip("#").split()
    row = lines[2].split()
    d = dict(zip(hdr, row))
    try:
        ts = datetime(int(d["YY"]), int(d["MM"]), int(d["DD"]), int(d["hh"]), int(d["mm"]), tzinfo=timezone.utc)
    except (KeyError, ValueError):
        return d, None
    d["_ts"] = ts.isoformat(timespec="minutes")
    return d, round((NOW - ts).total_seconds() / 3600, 1)


def check_ndbc():
    f = Fetcher("ndbc", lane=LANE, gate="G0")
    try:
        xml = f.get_text("https://www.ndbc.noaa.gov/activestations.xml")
    except FetchError as e:
        note("ndbc", "error", str(e))
        return
    root = ET.fromstring(xml)
    gl = []
    for st in root.iter("station"):
        lat, lon = float(st.get("lat")), float(st.get("lon"))
        # Great Lakes bounding box
        if 41.3 <= lat <= 49.1 and -92.5 <= lon <= -76.0:
            gl.append({"id": st.get("id"), "name": st.get("name"), "lat": lat, "lon": lon,
                       "owner": st.get("owner"), "type": st.get("type"), "met": st.get("met"),
                       "waves": st.get("waves")})
    note("ndbc", "active_great_lakes_stations", len(gl))
    # Michigan-relevant: Lake Michigan east half, Huron, Superior south shore, Erie west, St Clair
    mi = [s for s in gl if (-88.0 <= s["lon"] <= -82.3 and 41.6 <= s["lat"] <= 48.4)]
    note("ndbc", "michigan_waters_stations_in_active_list", len(mi))
    probe = {}
    for s in mi:
        sid = s["id"].lower()
        try:
            txt = f.get_text(f"https://www.ndbc.noaa.gov/data/realtime2/{sid.upper()}.txt")
            latest, age = ndbc_latest(txt)
            probe[s["id"]] = {"name": s["name"], "owner": s["owner"], "type": s["type"],
                              "lat": s["lat"], "lon": s["lon"],
                              "latest_obs": latest.get("_ts") if latest else None, "age_h": age,
                              "WVHT": latest.get("WVHT") if latest else None,
                              "WSPD": latest.get("WSPD") if latest else None,
                              "WTMP": latest.get("WTMP") if latest else None,
                              "status": ("reporting" if age is not None and age < 6 else
                                         "stale" if age is not None else "no data")}
        except FetchError as e:
            probe[s["id"]] = {"name": s["name"], "owner": s["owner"], "type": s["type"],
                              "lat": s["lat"], "lon": s["lon"], "status": f"no file ({str(e)[:40]})"}
    note("ndbc", "michigan_station_probe", probe)
    rep = sum(1 for p in probe.values() if p["status"] == "reporting")
    note("ndbc", "reporting_now", rep)
    note("ndbc", "stats", f.stats)


# ---------------------------------------------------------------- CO-OPS
COOPS_STATIONS = {"9075014": "Harbor Beach (Lake Huron)", "9087044": "Calumet Harbor (Lake Michigan)",
                  "9099064": "Duluth (Lake Superior)", "9087031": "Holland (Lake Michigan)",
                  "9087023": "Ludington (Lake Michigan)", "9075080": "Mackinaw City",
                  "9014090": "Mt Clemens (Lake St Clair)", "9063007": "Fermi (Lake Erie)"}


def check_coops():
    f = Fetcher("coops", lane=LANE, gate="G0")
    base = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    out = {}
    for sid, name in COOPS_STATIONS.items():
        try:
            j = f.get_json(base, {"product": "water_level", "station": sid, "date": "latest",
                                  "datum": "IGLD", "units": "english", "time_zone": "lst_ldt",
                                  "format": "json", "application": "IdeaFactory"})
            if "error" in j:
                out[sid] = {"name": name, "error": j["error"].get("message", str(j["error"]))}
                continue
            d = j["data"][0]
            out[sid] = {"name": name, "t": d["t"], "v_ft_igld85": d["v"], "lat": j["metadata"]["lat"],
                        "lon": j["metadata"]["lon"]}
        except FetchError as e:
            out[sid] = {"name": name, "error": str(e)[:120]}
    note("coops", "latest_water_level", out)
    # monthly means for long-term comparison (Harbor Beach) - one decade per call max
    try:
        j = f.get_json(base, {"product": "monthly_mean", "station": "9075014", "begin_date": "20160101",
                              "end_date": "20251231", "datum": "IGLD", "units": "english",
                              "time_zone": "lst_ldt", "format": "json", "application": "IdeaFactory"})
        rows = j.get("data", [])
        note("coops", "monthly_mean_rows_2016_2025_harbor_beach", len(rows))
        note("coops", "monthly_mean_sample", rows[-1] if rows else None)
    except FetchError as e:
        note("coops", "monthly_mean_error", str(e)[:120])
    note("coops", "stats", f.stats)


# ---------------------------------------------------------------- NWS
def check_nws():
    f = Fetcher("nws_api", lane=LANE, gate="G0")
    hdr = {"Accept": "application/geo+json"}
    try:
        j = f.get_json("https://api.weather.gov/alerts/active", {"region": "GL"}, headers=hdr)
        feats = j.get("features", [])
        note("nws_api", "active_great_lakes_marine_alerts", len(feats))
        note("nws_api", "alert_sample", [{"event": x["properties"]["event"],
                                          "areaDesc": x["properties"]["areaDesc"][:120],
                                          "ends": x["properties"].get("ends")} for x in feats[:5]])
    except FetchError as e:
        note("nws_api", "alerts_error", str(e)[:120])
    try:
        j = f.get_json("https://api.weather.gov/zones", {"type": "marine"}, headers=hdr)
        zones = [z["properties"] for z in j.get("features", [])]
        gl = [z for z in zones if z["id"][:2] in ("LM", "LH", "LS", "LE", "LC")]
        note("nws_api", "great_lakes_marine_zones", len(gl))
        note("nws_api", "zone_sample", [(z["id"], z["name"]) for z in gl if z["id"].startswith("LMZ")][:8])
    except FetchError as e:
        note("nws_api", "zones_error", str(e)[:120])
    # Nearshore marine forecast text product for Grand Rapids office (covers Holland / Grand Haven)
    try:
        j = f.get_json("https://api.weather.gov/products/types/NSH/locations/GRR", headers=hdr)
        prods = j.get("@graph", [])
        note("nws_api", "nsh_grr_products", len(prods))
        if prods:
            p = f.get_json(prods[0]["@id"], headers=hdr)
            txt = p.get("productText", "")
            note("nws_api", "nsh_grr_issued", prods[0].get("issuanceTime"))
            m = re.search(r"LMZ8\d\d-.*?\n(.*?)\n\$\$", txt, re.S)
            note("nws_api", "nsh_grr_excerpt", (m.group(0) if m else txt)[:700])
    except FetchError as e:
        note("nws_api", "nsh_error", str(e)[:120])
    note("nws_api", "stats", f.stats)


# ---------------------------------------------------------------- GLERL
def check_glerl():
    f = Fetcher("glerl", lane=LANE, gate="G0")
    base = "https://apps.glerl.noaa.gov/coastwatch/webdata/statistic/csv/"
    for lake, code in (("michigan", "m"), ("huron", "h"), ("superior", "s"), ("erie", "e")):
        try:
            txt = f.get_text(base + f"all_year_glsea_avg_{code}_F.csv")
            lines = [l for l in txt.splitlines() if l.strip()]
            note("glerl", f"glsea_daily_{lake}", {"header": lines[0][:160], "rows": len(lines) - 1,
                                                  "last": lines[-1][:160]})
        except FetchError as e:
            note("glerl", f"glsea_daily_{lake}_error", str(e)[:120])
    try:
        txt = f.get_text(base + "avgtemps-m_1995-2026_F.csv")
        lines = [l for l in txt.splitlines() if l.strip()]
        note("glerl", "glsea_longterm_michigan", {"header": lines[0][:200], "rows": len(lines) - 1,
                                                  "sample": lines[min(297, len(lines) - 1)][:200]})
    except FetchError as e:
        note("glerl", "glsea_longterm_error", str(e)[:120])
    note("glerl", "stats", f.stats)


# ---------------------------------------------------------------- GLOS (inspection only)
def check_glos():
    f = Fetcher("glos", lane=LANE, gate="G0")
    try:
        j = f.get_json("https://seagull-erddap.glos.org/erddap/info/index.json", {"page": 1, "itemsPerPage": 5})
        note("glos", "erddap_reachable_no_key", True)
        note("glos", "erddap_dataset_count_hint", j.get("table", {}).get("rows", [])[:1] and len(j["table"]["rows"]))
    except FetchError as e:
        note("glos", "erddap_error", str(e)[:160])
    try:
        t, status = f.get("https://seagull-api.glos.org/docs")
        note("glos", "api_docs_status", status)
        note("glos", "api_docs_mentions_key", bool(re.search(r"api[-_ ]?key|x-api-key|bearer", t, re.I)))
    except FetchError as e:
        note("glos", "api_docs_error", str(e)[:160])
    note("glos", "stats", f.stats)


# ---------------------------------------------------------------- Open-Meteo (evaluate only)
def check_open_meteo():
    f = Fetcher("open_meteo", lane=LANE, gate="G0", allow_noncommercial=True)
    try:
        j = f.get_json("https://marine-api.open-meteo.com/v1/marine",
                       {"latitude": 43.06, "longitude": -86.25, "current": "wave_height,wave_period,wave_direction",
                        "timezone": "America/Detroit"})
        note("open_meteo", "marine_grand_haven_current", j.get("current"))
        note("open_meteo", "marine_units", j.get("current_units"))
    except FetchError as e:
        note("open_meteo", "marine_error", str(e)[:160])
    note("open_meteo", "license_flag", "commercial_ok=false on free tier; evaluation only")
    note("open_meteo", "stats", f.stats)


if __name__ == "__main__":
    for fn in (check_ndbc, check_coops, check_nws, check_glerl, check_glos, check_open_meteo):
        try:
            fn()
        except Exception as e:  # keep going; record the failure
            note(fn.__name__.replace("check_", ""), "exception", f"{type(e).__name__}: {e}"[:200])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=1, default=str), encoding="utf-8")
    print(json.dumps(results, indent=1, default=str))
