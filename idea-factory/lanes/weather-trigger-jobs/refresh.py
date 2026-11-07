"""Rebuild the Job-Day Alerts data from live NWS forecasts.

For 8 Michigan metro points (city-level forecast points, not people or addresses) it pulls the NWS
hourly forecast and writes the compact hourly series; the app applies the go/no-go rules per trade.

    python lanes/weather-trigger-jobs/refresh.py [--gate G1]

Writes lanes/weather-trigger-jobs/app/data/forecast.json, warnings.json, mi_state.json, mi_counties.json
and a one-page CSV/PDF sample (the outreach attachment) in lanes/weather-trigger-jobs/samples/.
"""
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core import samples  # noqa: E402
from core.fetch import BudgetExceeded, FetchError, Fetcher  # noqa: E402

LANE = "weather-trigger-jobs"
HERE = Path(__file__).resolve().parent
APP_DATA = HERE / "app" / "data"
GEO_SRC = ROOT / "core" / "web" / "geo"
UA_ACCEPT = {"Accept": "application/geo+json"}
CITIES = [
    ("Detroit", "Wayne", 42.3314, -83.0458), ("Grand Rapids", "Kent", 42.9634, -85.6681),
    ("Lansing", "Ingham", 42.7325, -84.5555), ("Flint", "Genesee", 43.0125, -83.6875),
    ("Ann Arbor", "Washtenaw", 42.2808, -83.7430), ("Kalamazoo", "Kalamazoo", 42.2917, -85.5872),
    ("Traverse City", "Grand Traverse", 44.7631, -85.6206), ("Marquette", "Marquette", 46.5436, -87.3954),
]
WARN_KEYWORDS = ("tornado", "thunderstorm", "wind", "hail", "flood", "freeze", "frost", "winter", "snow", "ice", "heat")


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def wind_mph(s):
    nums = [int(x) for x in re.findall(r"\d+", s or "")]
    return max(nums) if nums else 0


def fetch_city(f, name, county, lat, lon):
    pt = f.get_json(f"https://api.weather.gov/points/{lat},{lon}", ttl=86400, headers=UA_ACCEPT)
    url = pt["properties"]["forecastHourly"]
    fc = f.get_json(url, ttl=1800, headers=UA_ACCEPT)
    hours = []
    for p in fc["properties"]["periods"]:
        pop = (p.get("probabilityOfPrecipitation") or {}).get("value")
        hours.append({"t": p["startTime"], "temp": p["temperature"], "pop": pop or 0,
                      "wind": wind_mph(p.get("windSpeed")), "txt": p.get("shortForecast", "")})
    return {"name": name, "county": county, "lat": lat, "lon": lon,
            "office": pt["properties"].get("gridId"), "updated": fc["properties"].get("updated"), "hours": hours}


def fetch_warnings(f):
    out = {"as_of": now_iso(), "source": "National Weather Service API, alerts/active?area=MI", "total_active": 0,
           "warnings": [], "error": ""}
    try:
        data = f.get_json("https://api.weather.gov/alerts/active", params={"area": "MI"}, ttl=600, headers=UA_ACCEPT)
    except (BudgetExceeded, FetchError) as e:
        out["error"] = str(e)[:200]
        return out
    feats = data.get("features", [])
    out["total_active"] = len(feats)
    for ft in feats:
        p = ft.get("properties", {})
        if not any(k in (p.get("event") or "").lower() for k in WARN_KEYWORDS):
            continue
        out["warnings"].append({"id": p.get("id") or ft.get("id"), "event": p.get("event"), "severity": p.get("severity"),
                                "headline": p.get("headline"), "areaDesc": p.get("areaDesc"), "expires": p.get("expires"),
                                "onset": p.get("onset"), "geometry": ft.get("geometry")})
    return out


def main():
    gate = "G1"
    if "--gate" in sys.argv:
        gate = sys.argv[sys.argv.index("--gate") + 1]
    APP_DATA.mkdir(parents=True, exist_ok=True)
    f = Fetcher("nws_api", lane=LANE, gate=gate)
    cities, errors = [], []
    for c in CITIES:
        try:
            cities.append(fetch_city(f, *c))
        except (BudgetExceeded, FetchError, KeyError) as e:
            errors.append(f"{c[0]}: {str(e)[:120]}")
    if not cities:
        print("  no forecast fetched:", errors)
        return 1
    fc = {"as_of": now_iso(), "source": "National Weather Service API, gridpoints hourly forecast",
          "attribution": "Source: National Weather Service", "cities": cities, "errors": errors}
    (APP_DATA / "forecast.json").write_text(json.dumps(fc, separators=(",", ":")))
    (APP_DATA / "warnings.json").write_text(json.dumps(fetch_warnings(f), separators=(",", ":")))
    for n in ("mi_state.json", "mi_counties.json"):
        shutil.copy(GEO_SRC / n, APP_DATA / n)
    # sample: next 7 days, worst-hour rain chance and wind per city (working hours 7am-5pm local)
    rows = []
    for c in cities:
        days = {}
        for h in c["hours"]:
            hr = int(h["t"][11:13])
            if 7 <= hr < 17:
                d = days.setdefault(h["t"][:10], {"pop": 0, "wind": 0, "lo": 999})
                d["pop"] = max(d["pop"], h["pop"]); d["wind"] = max(d["wind"], h["wind"]); d["lo"] = min(d["lo"], h["temp"])
        for day, d in sorted(days.items())[:7]:
            rows.append({"city": c["name"], "day": day, "pop": f"{d['pop']}%", "wind": f"{d['wind']} mph", "low": f"{d['lo']} F"})
    cols = [("city", "City"), ("day", "Day"), ("pop", "Peak rain chance 7a-5p"), ("wind", "Peak wind"), ("low", "Coldest working hour")]
    out_dir = HERE / "samples"
    out_dir.mkdir(exist_ok=True)
    samples.write_all(rows, cols, out_dir, title="Job-Day Alerts: Michigan 7-day work-window outlook",
                      subtitle="Source: National Weather Service. Forecast, not observation.",
                      notes=["Hourly NWS forecast reduced to the 7am-5pm working window per city.",
                             "The live app applies roofing, landscaping and outdoor-venue go/no-go rules to this."],
                      source_line="Source: National Weather Service", basename="job_day_outlook",
                      pdf_widths=[110, 90, 130, 90, 110])
    print(f"  {len(cities)} cities, {len(fc['cities'][0]['hours'])} hours each, errors: {errors or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
