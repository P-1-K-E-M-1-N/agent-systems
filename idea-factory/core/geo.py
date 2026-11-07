"""Public-domain boundaries for prototype maps, from Census TIGERweb. No key, no tile server.

The prototypes draw their own basemap from GeoJSON shipped with the app, so they render
anywhere (including inside a claude.ai artifact, which blocks images from other hosts).

    from core import geo
    f = geo.fetcher("storm-lead", "G1")
    counties = geo.michigan_counties(f)          # FeatureCollection, props NAME, GEOID
    zctas = geo.michigan_zctas(f)                # FeatureCollection, props ZCTA5
    geo.write(counties, "lanes/storm-lead/app/data/mi_counties.json")

CLI:  python -m core.geo counties|zctas|state OUT.json [--lane slug] [--simplify 0.005]
"""
import json
import sys
from pathlib import Path

from .fetch import Fetcher

TIGERWEB = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb"
STATE_COUNTY = f"{TIGERWEB}/State_County/MapServer"
ZCTA_SERVICE = f"{TIGERWEB}/PUMA_TAD_TAZ_UGA_ZCTA/MapServer"
MI_FIPS = "26"
MI_ENVELOPE = (-90.5, 41.6, -82.1, 48.4)  # xmin, ymin, xmax, ymax (degrees)


def fetcher(lane="core", gate="G1"):
    return Fetcher("census_tigerweb", lane=lane, gate=gate)


def _layer_id(f, service_url, name_startswith):
    meta = f.get_json(service_url, params={"f": "json"})
    for layer in meta.get("layers", []):
        if layer["name"].lower().startswith(name_startswith.lower()):
            return layer["id"]
    names = [l["name"] for l in meta.get("layers", [])]
    raise LookupError(f"No layer starting with {name_startswith!r} in {service_url}: {names}")


def query_geojson(f, layer_url, where="1=1", out_fields="*", simplify_deg=None, precision=4,
                  envelope=None, page=2000):
    """Paged ArcGIS query returning one GeoJSON FeatureCollection (WGS84)."""
    feats = []
    offset = 0
    while True:
        params = {"where": where, "outFields": out_fields, "f": "geojson", "outSR": 4326,
                  "geometryPrecision": precision, "resultOffset": offset, "resultRecordCount": page,
                  "returnGeometry": "true"}
        if simplify_deg:
            params["maxAllowableOffset"] = simplify_deg
        if envelope:
            params.update({"geometry": ",".join(str(v) for v in envelope), "geometryType": "esriGeometryEnvelope",
                           "inSR": 4326, "spatialRel": "esriSpatialRelIntersects"})
        data = f.get_json(f"{layer_url}/query", params=params)
        if "error" in data:
            raise RuntimeError(f"TIGERweb error: {data['error']}")
        got = data.get("features", [])
        feats.extend(got)
        more = data.get("properties", {}).get("exceededTransferLimit") or data.get("exceededTransferLimit")
        if not got or not more:
            break
        offset += len(got)
    return {"type": "FeatureCollection", "features": feats}


def michigan_state(f, simplify_deg=0.01):
    lid = _layer_id(f, STATE_COUNTY, "States")
    return query_geojson(f, f"{STATE_COUNTY}/{lid}", where=f"STATE='{MI_FIPS}'", out_fields="NAME,GEOID",
                         simplify_deg=simplify_deg)


def michigan_counties(f, simplify_deg=0.005):
    lid = _layer_id(f, STATE_COUNTY, "Counties")
    fc = query_geojson(f, f"{STATE_COUNTY}/{lid}", where=f"STATE='{MI_FIPS}'", out_fields="NAME,GEOID",
                       simplify_deg=simplify_deg)
    for ft in fc["features"]:
        ft["properties"] = {"NAME": ft["properties"].get("NAME"), "GEOID": ft["properties"].get("GEOID")}
    return fc


def michigan_zctas(f, simplify_deg=0.003):
    """ZCTAs intersecting Michigan's bounding box, kept if the code starts 48 or 49 (Michigan's ZIP prefixes)."""
    lid = _layer_id(f, ZCTA_SERVICE, "2020 Census ZIP Code Tabulation Areas")
    fc = query_geojson(f, f"{ZCTA_SERVICE}/{lid}", out_fields="ZCTA5,GEOID", simplify_deg=simplify_deg,
                       envelope=MI_ENVELOPE)
    keep = []
    for ft in fc["features"]:
        z = ft["properties"].get("ZCTA5") or ft["properties"].get("GEOID") or ""
        if z[:2] in ("48", "49"):
            ft["properties"] = {"ZCTA5": z}
            keep.append(ft)
    fc["features"] = keep
    return fc


def bbox(fc):
    xs, ys = [], []

    def walk(c):
        if isinstance(c[0], (int, float)):
            xs.append(c[0]); ys.append(c[1])
        else:
            for sub in c:
                walk(sub)
    for ft in fc["features"]:
        walk(ft["geometry"]["coordinates"])
    return [min(xs), min(ys), max(xs), max(ys)]


def write(fc, path):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(fc, separators=(",", ":")), encoding="utf-8")
    return p


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Write Michigan boundary GeoJSON from Census TIGERweb")
    ap.add_argument("what", choices=["counties", "zctas", "state"])
    ap.add_argument("out")
    ap.add_argument("--lane", default="core")
    ap.add_argument("--simplify", type=float, default=None, help="degrees; default 0.005 counties, 0.003 zctas")
    a = ap.parse_args()
    fx = fetcher(a.lane)
    fn = {"counties": michigan_counties, "zctas": michigan_zctas, "state": michigan_state}[a.what]
    fc = fn(fx, a.simplify) if a.simplify else fn(fx)
    p = write(fc, a.out)
    print(f"{a.what}: {len(fc['features'])} features, {p.stat().st_size // 1024} KB, bbox {bbox(fc)} -> {p}")
    sys.exit(0)
