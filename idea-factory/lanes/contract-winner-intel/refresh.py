"""Contract Winners: rebuilds the prototype data and the outreach sample from live USAspending.gov data.

Run from repo root:  python lanes/contract-winner-intel/refresh.py
Output: app/data/latest.json and latest.js (the awards, county totals, agency and recipient roll-ups),
        samples/winners_digest.{csv,html,pdf} (the outreach attachment).

What it does: pulls federal contract awards (types A-D) with place of performance in Michigan whose
action date is in the last 90 days, newest modification first, two pages of 100. Splits them into NEW
awards (first obligated inside the window) and MODIFICATIONS (older awards that got new money).
Maps each award to a county from its ZIP's Census ZCTA centroid.

Honest limits: "Award Amount" is the total obligated on the award to date, not the new action.
Agency submissions lag days to months. Place of performance ZIPs are sometimes a vendor's office, not
the work site (one early row was a Charleston, SC ship repair coded to a Michigan ZIP). Business
recipients only; rows whose recipient name looks like an individual are dropped (rule 4).
"""
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.fetch import Fetcher  # noqa: E402
from core.samples import write_all  # noqa: E402

LANE = "contract-winner-intel"
HERE = ROOT / "lanes" / LANE
APP = HERE / "app" / "data"
GEO = ROOT / "core" / "web" / "geo"
WINDOW_DAYS = 90
BIZ = re.compile(r"\b(INC|LLC|L\.L\.C|CORP|CO|COMPANY|LTD|LP|LLP|PC|PLLC|UNIVERSITY|COLLEGE|SYSTEMS?|SERVICES?|GROUP|ASSOCIATES|"
                 r"INDUSTRIES|ENTERPRISES?|SOLUTIONS|TECHNOLOG\w*|CONSTRUCTION|ENGINEERING|HOSPITAL|HEALTH\w*|FOUNDATION|"
                 r"AUTHORITY|DISTRICT|CITY|COUNTY|STATE|TRUST|PARTNERS|MOTORS?|ELECTRIC|SUPPLY|INTERNATIONAL|MANUFACTURING|"
                 r"CONTRACTING|CONSULTING|LABS?|LABORATORIES|SCHOOLS?|ASSOCIATION|AUTOMOTIVE|ENERGY|FOODS?|PRODUCTS)\b", re.I)


def nice(name):
    t = re.sub(r"\b(Llc|Pllc|Llp|Lp|Pc|Usa|Us)\b", lambda m: m.group(1).upper(), name.title())
    t = re.sub(r"\bInc\b\.?", "Inc.", t)
    return re.sub(r"\bCorp\b\.?", "Corp.", t)


def ring_has(pt, ring):
    x, y = pt
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][:2]
        xj, yj = ring[j][:2]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def polys(geom):
    return [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]


def zip_county():
    counties = json.load(open(GEO / "mi_counties.json"))["features"]
    out = {}
    for z in json.load(open(GEO / "mi_zctas.json"))["features"]:
        pts = [p for poly in polys(z["geometry"]) for p in poly[0]]
        c = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
        for cf in counties:
            if any(ring_has(c, poly[0]) for poly in polys(cf["geometry"])):
                out[z["properties"]["ZCTA5"]] = (cf["properties"]["GEOID"], cf["properties"]["NAME"])
                break
    return out


def fetch_awards(f, start, end):
    fields = ["Award ID", "Recipient Name", "Award Amount", "Awarding Agency", "Awarding Sub Agency", "Start Date",
              "Description", "Place of Performance Zip5", "Last Modified Date", "Base Obligation Date"]
    rows = []
    for page in (1, 2):
        body = {"filters": {"award_type_codes": ["A", "B", "C", "D"],
                            "time_period": [{"start_date": start, "end_date": end, "date_type": "action_date"}],
                            "place_of_performance_locations": [{"country": "USA", "state": "MI"}]},
                "fields": fields, "sort": "Last Modified Date", "order": "desc", "limit": 100, "page": page}
        r = f.get_json("https://api.usaspending.gov/api/v2/search/spending_by_award/", method="POST",
                       body=json.dumps(body), headers={"Content-Type": "application/json"})
        rows += r.get("results", [])
        if not r.get("page_metadata", {}).get("hasNext"):
            break
    return rows


def main():
    now = datetime.now(timezone.utc)
    end = date.today()
    start = end - timedelta(days=WINDOW_DAYS)
    f = Fetcher("usaspending", lane=LANE, gate="G1")
    zc = zip_county()
    awards, dropped = [], 0
    for r in fetch_awards(f, start.isoformat(), end.isoformat()):
        name = (r.get("Recipient Name") or "").strip()
        z = (r.get("Place of Performance Zip5") or "")[:5]
        if not name or not BIZ.search(name) or z not in zc:
            dropped += 1
            continue
        base = r.get("Base Obligation Date") or r.get("Start Date") or ""
        awards.append({"id": r["Award ID"], "recipient": nice(name),
                       "amount": r.get("Award Amount") or 0, "agency": r.get("Awarding Agency") or "",
                       "sub": r.get("Awarding Sub Agency") or "", "start": r.get("Start Date") or "", "base": base,
                       "kind": "new" if base >= start.isoformat() else "mod", "desc": (r.get("Description") or "").strip()[:220],
                       "zip": z, "county": zc[z][1], "fips": zc[z][0], "modified": (r.get("Last Modified Date") or "")[:10]})
    counties, agencies, recips = {}, {}, {}
    for a in awards:
        c = counties.setdefault(a["fips"], {"name": a["county"], "n": 0, "amount": 0})
        c["n"] += 1; c["amount"] += a["amount"]
        g = agencies.setdefault(a["agency"], {"n": 0, "amount": 0}); g["n"] += 1; g["amount"] += a["amount"]
        p = recips.setdefault(a["recipient"], {"n": 0, "amount": 0}); p["n"] += 1; p["amount"] += a["amount"]
    top = lambda d, k=15: [dict(name=n, **v) for n, v in sorted(d.items(), key=lambda kv: -kv[1]["amount"])[:k]]
    out = {"generated": now.isoformat(timespec="seconds"), "window": {"start": start.isoformat(), "end": end.isoformat()},
           "n": len(awards), "dropped": dropped, "new": sum(a["kind"] == "new" for a in awards),
           "total": sum(a["amount"] for a in awards), "counties": counties, "agencies": top(agencies, 20),
           "recipients": top(recips), "awards": awards,
           "source": "Source: USAspending.gov (US Treasury, Bureau of the Fiscal Service), public domain.",
           "limits": ["Award amount is the total obligated on the award to date, not the new action.",
                      "Agencies report with a lag of days to months; this is who won, not breaking news.",
                      "Place of performance ZIP is sometimes the vendor's office, not the job site. County is taken from the ZIP's Census ZCTA centroid.",
                      "Businesses and institutions only; recipient names that do not look like organizations are left out."]}
    APP.mkdir(parents=True, exist_ok=True)
    (APP / "latest.json").write_text(json.dumps(out, separators=(",", ":")))
    (APP / "latest.js").write_text("window.__LATEST__=" + json.dumps(out, separators=(",", ":")) + ";")
    rows = sorted(awards, key=lambda a: -a["amount"])
    cols = [("recipient", "Winner"), ("agency", "Agency"), ("amount", "Total on award ($)"), ("county", "County"),
            ("kind", "New/Mod"), ("start", "Start"), ("desc", "What for")]
    write_all(rows, cols, HERE / "samples", "Michigan federal contract winners, last 90 days",
              subtitle=f"{len(awards)} awards as of {end}", notes=out["limits"], source_line=out["source"], basename="winners_digest")
    print(f"awards={len(awards)} new={out['new']} dropped={dropped} total=${out['total']:,.0f}")


if __name__ == "__main__":
    main()
