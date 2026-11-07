"""Site Check: rebuilds the prototype data and the outreach sample from the Census Bureau API.

Run from repo root:  python lanes/site-selection/refresh.py
Output: app/data/latest.json + latest.js (county and ZIP tables), samples/site_check.{csv,html,pdf}.

Data: ACS 5-year 2023 (population, median household income, median age) for every Michigan ZCTA and
county; County Business Patterns 2022 (establishments, employees) per county for 8 business types.
Aggregates only, no individuals (rule 4). Needs env CENSUS_API_KEY (free key, set by Nick).

Honest limits: CBP is annual (2022 is the latest year) and suppresses small cells (those counties show
"n/a", never a guess). ZIP numbers are residents, not shops: CBP has no ZIP data in this API, so a ZIP's
shop count is an ESTIMATE (its share of county residents times county shops). Residents-per-shop is a
screening number, not a verdict: it ignores traffic, rent, tourism, commuters and chains.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.fetch import Fetcher  # noqa: E402
from core.samples import write_all  # noqa: E402

LANE = "site-selection"
HERE = ROOT / "lanes" / LANE
APP = HERE / "app" / "data"
GEO = ROOT / "core" / "web" / "geo"
ACS = "https://api.census.gov/data/2023/acs/acs5"
CBP = "https://api.census.gov/data/2022/cbp"
TYPES = [("7225", "Restaurants and bars"), ("8121", "Hair, nail and personal care"), ("8111", "Auto repair"),
         ("4451", "Grocery stores"), ("8123", "Dry cleaning and laundry"), ("7139", "Gyms and recreation"),
         ("6211", "Doctors' offices"), ("6212", "Dentists' offices")]
ACS_VARS = "NAME,B01003_001E,B19013_001E,B01002_001E"


def num(v):
    try:
        n = float(v)
        return None if n < 0 else n   # Census uses large negatives for "not available"
    except (TypeError, ValueError):
        return None


def ring_has(pt, ring):
    x, y = pt
    inside, j = False, len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][:2]; xj, yj = ring[j][:2]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def polys(g):
    return [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]


def zip_county():
    counties = json.load(open(GEO / "mi_counties.json"))["features"]
    out = {}
    for z in json.load(open(GEO / "mi_zctas.json"))["features"]:
        pts = [p for poly in polys(z["geometry"]) for p in poly[0]]
        c = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
        for cf in counties:
            if any(ring_has(c, poly[0]) for poly in polys(cf["geometry"])):
                out[z["properties"]["ZCTA5"]] = cf["properties"]["GEOID"]
                break
    return out


def main():
    f = Fetcher("census_api", lane=LANE, gate="G1")
    zc = zip_county()
    # counties
    rows = f.get_json(ACS, params={"get": ACS_VARS, "for": "county:*", "in": "state:26"})
    counties = {}
    for r in rows[1:]:  # NAME, pop, income, age, state, county
        counties[r[4] + r[5]] = {"name": r[0].replace(" County, Michigan", ""), "pop": num(r[1]),
                                 "income": num(r[2]), "age": num(r[3]), "biz": {}}
    # business counts (CBP)
    for code, label in TYPES:
        try:
            rr = f.get_json(CBP, params={"get": "NAME,ESTAB,EMP", "for": "county:*", "in": "state:26", "NAICS2017": code})
        except Exception as e:  # keep going; a missing type is reported, not faked
            print(f"CBP {code} failed: {e}")
            continue
        for r in rr[1:]:
            fips = "26" + r[5]
            if fips in counties:
                est, emp = num(r[1]), num(r[2])
                if est is not None:
                    counties[fips]["biz"][code] = {"est": int(est), "emp": int(emp) if emp is not None else None}
    # state median residents per shop, per type (for the "room for more" estimate)
    state = {}
    for code, label in TYPES:
        ratios = sorted(c["pop"] / c["biz"][code]["est"] for c in counties.values()
                        if code in c["biz"] and c["biz"][code]["est"] >= 5 and c["pop"])
        state[code] = {"label": label, "median_ratio": ratios[len(ratios) // 2] if ratios else None,
                       "counties": len(ratios)}
    for c in counties.values():
        for code, b in c["biz"].items():
            m = state[code]["median_ratio"]
            b["per"] = round(c["pop"] / b["est"]) if c["pop"] and b["est"] else None
            b["gap"] = round(c["pop"] / m - b["est"]) if m and c["pop"] else None  # + = fewer shops than a typical county
    # ZIPs
    zr = f.get_json(ACS, params={"get": ACS_VARS, "for": "zip code tabulation area:*"})
    zips = {}
    for r in zr[1:]:
        z = r[4]
        if z in zc:
            zips[z] = {"pop": num(r[1]), "income": num(r[2]), "age": num(r[3]), "fips": zc[z]}
    now = datetime.now(timezone.utc)
    out = {"generated": now.isoformat(timespec="seconds"), "acs_year": 2023, "cbp_year": 2022,
           "types": [{"code": c, "label": l} for c, l in TYPES], "state": state, "counties": counties, "zips": zips,
           "source": "Source: U.S. Census Bureau, ACS 5-year 2023 and County Business Patterns 2022. This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau.",
           "limits": ["County Business Patterns is annual; the latest year is 2022. Counties with too few shops are hidden by the Census Bureau and show n/a.",
                      "There is no shop count by ZIP here. A ZIP's shop count is an estimate: its share of county residents times the county's shops.",
                      "Residents per shop is a screening number, not a verdict. It ignores foot traffic, tourists, commuters, rent and chains.",
                      "Aggregates only. No individual people or households are in this data."]}
    APP.mkdir(parents=True, exist_ok=True)
    (APP / "latest.json").write_text(json.dumps(out, separators=(",", ":")))
    (APP / "latest.js").write_text("window.__LATEST__=" + json.dumps(out, separators=(",", ":")) + ";")
    # outreach sample: county table for restaurants + personal care
    srows = []
    for fips, c in sorted(counties.items(), key=lambda kv: kv[1]["name"]):
        row = {"county": c["name"], "pop": f"{int(c['pop']):,}" if c["pop"] else "", "income": f"${int(c['income']):,}" if c["income"] else "n/a"}
        for code in ("7225", "8121", "8111"):
            b = c["biz"].get(code)
            row[code] = f"{b['est']} shops, {b['per']:,} residents each" if b and b["per"] else "n/a"
        srows.append(row)
    cols = [("county", "County"), ("pop", "Residents"), ("income", "Median household income"),
            ("7225", "Restaurants and bars"), ("8121", "Hair, nail and personal care"), ("8111", "Auto repair")]
    write_all(srows, cols, HERE / "samples", "Michigan site check: residents per existing shop",
              subtitle=f"83 counties, ACS {out['acs_year']} and CBP {out['cbp_year']}", notes=out["limits"],
              source_line=out["source"], basename="site_check")
    nb = sum(len(c["biz"]) for c in counties.values())
    print(f"counties={len(counties)} zips={len(zips)} county-type cells={nb}")


if __name__ == "__main__":
    main()
