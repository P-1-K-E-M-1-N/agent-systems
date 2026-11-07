"""Storm Lead lane helpers (standard library only).

Reads NOAA SPC storm reports in two formats and normalises them into one event shape:
  * daily preliminary files  https://www.spc.noaa.gov/climo/reports/YYMMDD_rpts_{hail,wind}.csv
    (one file per SPC "convective day", 12:00 UTC to 11:59 UTC next day; hail size in
    hundredths of an inch; wind speed in mph or UNK for a damage report with no measured gust)
  * final yearly files       https://www.spc.noaa.gov/wcm/data/YYYY_{hail,wind}.csv
    (NWS Storm Data, CST timestamps, hail mag in inches, wind mag in knots, county FIPS in f1)

Alert rule (what makes a roofer's morning email fire):
  hail >= 1.00 inch, or wind gust >= 58 mph (50 knots), or a wind-damage report with no speed.

Event dict keys: day (SPC convective day, YYYY-MM-DD), time_utc (HHMM), kind (hail|wind),
mag (hail inches as float, wind mph as float, or None for UNK), mag_text, location, county,
state, lat, lon, comments, source (preliminary|final).
"""
import csv
import io
import math
import sys
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.fetch import Fetcher, FetchError  # noqa: E402

LANE = "storm-lead"
HAIL_MIN_IN = 1.00
WIND_MIN_MPH = 58.0
WIND_MIN_KT = 50.0
MI_FIPS = "26"
SPC_DAILY = "https://www.spc.noaa.gov/climo/reports/"
SPC_WCM = "https://www.spc.noaa.gov/wcm/data/"
GAZ = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"


def qualifies(ev):
    if ev["kind"] == "hail":
        return ev["mag"] is not None and ev["mag"] >= HAIL_MIN_IN
    return ev["mag"] is None or ev["mag"] >= WIND_MIN_MPH


# ---------------- daily preliminary files ----------------
def daily_url(day, kind):
    return f"{SPC_DAILY}{day.strftime('%y%m%d')}_rpts_{kind}.csv"


def fetch_daily(fetcher, day, kind, state="MI"):
    """Return normalised events for one convective day and kind, filtered to `state`."""
    txt = fetcher.get_text(daily_url(day, kind))
    out = []
    for r in csv.DictReader(io.StringIO(txt)):
        if r.get("State") != state:
            continue
        raw = (r.get("Size") or r.get("Speed") or "").strip()
        if kind == "hail":
            mag = int(raw) / 100.0 if raw.isdigit() else None
            mag_text = f"{mag:.2f} in" if mag is not None else raw
        else:
            mag = float(raw) if raw.replace(".", "", 1).isdigit() else None
            mag_text = f"{mag:.0f} mph" if mag is not None else "damage (no speed)"
        out.append({
            "day": day.isoformat(), "time_utc": (r.get("Time") or "").strip(), "kind": kind,
            "mag": mag, "mag_text": mag_text, "location": (r.get("Location") or "").strip(),
            "county": (r.get("County") or "").strip(), "state": state,
            "lat": float(r["Lat"]) if r.get("Lat") else None, "lon": float(r["Lon"]) if r.get("Lon") else None,
            "comments": (r.get("Comments") or "").strip(), "source": "preliminary",
        })
    return out


def fetch_daily_range(fetcher, start, end, state="MI", kinds=("hail", "wind")):
    """Inclusive date range of convective days; yields (day, events)."""
    d = start
    while d <= end:
        evs = []
        for k in kinds:
            evs.extend(fetch_daily(fetcher, d, k, state))
        yield d, evs
        d += timedelta(days=1)


# ---------------- final yearly files ----------------
def _conv_day(date_s, time_s, tz_code):
    """SPC database times are CST (tz=3). Convert to UTC and assign the 12Z-12Z convective day."""
    dt = datetime.strptime(f"{date_s} {time_s}", "%Y-%m-%d %H:%M:%S")
    offset = {"3": 6, "9": 0}.get(str(tz_code), 6)  # 3 = CST, 9 = GMT
    utc = dt + timedelta(hours=offset)
    day = utc.date() if utc.hour >= 12 else utc.date() - timedelta(days=1)
    return day.isoformat(), utc.strftime("%H%M")


def fetch_final_year(fetcher, year, kind, state_fips=MI_FIPS, county_names=None):
    txt = fetcher.get_text(f"{SPC_WCM}{year}_{kind}.csv")
    out = []
    county_names = county_names or {}
    for r in csv.DictReader(io.StringIO(txt)):
        if r.get("stf") != state_fips:
            continue
        day, t = _conv_day(r["date"], r["time"], r.get("tz", "3"))
        m = float(r["mag"]) if r.get("mag") else 0.0
        if kind == "hail":
            mag, mag_text = m, f"{m:.2f} in"
        else:
            mag = round(m * 1.15078, 1) if m > 0 else None
            mt = {"MG": "measured", "EG": "estimated"}.get(r.get("mt", ""), r.get("mt", ""))
            mag_text = f"{mag:.0f} mph ({mt})" if mag is not None else "damage (no speed)"
        fips = f"{int(state_fips):02d}{int(r['f1']):03d}" if r.get("f1") else ""
        out.append({
            "day": day, "time_utc": t, "kind": kind, "mag": mag, "mag_text": mag_text, "location": "",
            "county": county_names.get(fips, fips), "state": "MI" if state_fips == MI_FIPS else r.get("st", ""),
            "lat": float(r["slat"]) if r.get("slat") else None, "lon": float(r["slon"]) if r.get("slon") else None,
            "comments": "", "source": "final",
        })
    return out


# ---------------- Census gazetteer: counties and ZCTA centroids ----------------
def _gazetteer(fetcher, kind, years=(2025, 2024, 2023)):
    """Return rows (dicts) of the national gazetteer file for `kind` ('counties' or 'zcta')."""
    last = None
    for y in years:
        url = f"{GAZ}{y}_Gazetteer/{y}_Gaz_{kind}_national.zip"
        try:
            data = fetcher.get_bytes(url)
        except FetchError as e:
            last = e
            continue
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            name = [n for n in z.namelist() if n.lower().endswith(".txt")][0]
            txt = z.read(name).decode("utf-8", "replace")
        head = txt.splitlines()[0] if txt else ""
        delim = "|" if head.count("|") > head.count("\t") else "\t"  # 2025 files are pipe-delimited, older are tab
        rows = list(csv.DictReader(io.StringIO(txt), delimiter=delim))
        return [{k.strip().lstrip("﻿"): (v or "").strip() for k, v in r.items() if k} for r in rows], y
    raise last


def county_names(fetcher):
    rows, _ = _gazetteer(fetcher, "counties")
    return {r["GEOID"]: r["NAME"].replace(" County", "") for r in rows if r.get("GEOID")}


def mi_zctas(fetcher):
    """List of (zcta, lat, lon) for Michigan ZIP Code Tabulation Areas (ZIPs 48xxx and 49xxx)."""
    rows, year = _gazetteer(fetcher, "zcta")
    out = []
    for r in rows:
        z = r.get("GEOID", "")
        if z[:2] in ("48", "49"):
            out.append((z, float(r["INTPTLAT"]), float(r["INTPTLONG"])))
    return out, year


def _km(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 12742 * math.asin(math.sqrt(a))


def nearby_zctas(lat, lon, zctas, radius_km=8.0, max_n=6):
    """ZCTAs whose centroid is within radius_km of the report point (always includes the nearest).
    Approximation: a storm report is a point; real ZIP polygons are irregular, so this is a
    centroid-distance guess, good enough for a 'which ZIPs should I canvass' list."""
    scored = sorted(((_km(lat, lon, zl, zo), z) for z, zl, zo in zctas))
    out = [z for d, z in scored[:max_n] if d <= radius_km]
    return out or [scored[0][1]]


def spc_reports_fetcher(gate):
    return Fetcher("noaa_spc_reports", lane=LANE, gate=gate)


def spc_wcm_fetcher(gate):
    return Fetcher("noaa_spc_wcm", lane=LANE, gate=gate)


def gazetteer_fetcher(gate):
    return Fetcher("census_gazetteer", lane=LANE, gate=gate)


def yesterday_convective_day(now=None):
    """The convective day a 7am alert covers: the file dated yesterday (12Z yesterday - 12Z today)."""
    now = now or datetime.now(timezone.utc)
    return (now - timedelta(days=1)).date() if now.hour >= 12 else (now - timedelta(days=2)).date()


def write_csv(path, rows, cols):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([r.get(c, "") if not isinstance(r, (list, tuple)) else r[cols.index(c)] for c in cols])
