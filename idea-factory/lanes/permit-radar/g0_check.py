"""G0 data check for permit-radar. Run from repo root: python lanes/permit-radar/g0_check.py
Fetches (via core.fetch) the Detroit terms page, the hub dataset list, the layer metadata and
the freshest issued_date, and saves a JSON summary to lanes/permit-radar/data/g0_summary.json.
"""
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core import registry  # noqa: E402
from core.fetch import Fetcher  # noqa: E402


def ts(v):
    return datetime.fromtimestamp(v / 1000, timezone.utc).isoformat() if isinstance(v, (int, float)) else v


def main():
    out = {}
    f = Fetcher("detroit_permits", lane="permit-radar", gate="G0")
    src = registry.get("detroit_permits")

    # 1. terms of use page
    terms_html = f.get_text(src["terms_url"], ttl=86400)
    txt = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", terms_html, flags=re.S)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"\s+", " ", txt)
    out["terms_len"] = len(txt)
    out["terms_excerpt"] = txt[:8000]

    # 2. hub datasets for Detroit permits
    hub = f.get_json("https://hub.arcgis.com/api/v3/datasets",
                     params={"q": "permits", "filter[source]": "City of Detroit", "page[size]": 50}, ttl=86400)
    ds = []
    for d in hub.get("data", []):
        a = d.get("attributes", {})
        ds.append({"id": d.get("id"), "name": a.get("name"), "url": a.get("url"), "modified": a.get("modified"),
                   "recordCount": a.get("recordCount"),
                   "fields": [fl.get("name") for fl in (a.get("fields") or [])][:80],
                   "license": (a.get("licenseInfo") or "")[:200], "type": a.get("type")})
    out["hub_datasets"] = ds

    # 3. layer metadata
    meta = f.get_json(src["base_url"], params={"f": "json"}, ttl=86400)
    out["layer_fields"] = [fl["name"] for fl in meta.get("fields", [])]
    ei = meta.get("editingInfo", {})
    out["layer_editingInfo"] = {k: ts(v) for k, v in ei.items()}

    # 4. counts and freshness
    def count(where):
        d = f.get_json(src["base_url"] + "/query",
                       params={"where": where, "returnCountOnly": "true", "f": "json"}, ttl=3600)
        return d.get("count", d)

    out["count_total"] = count("1=1")
    out["count_issued_30d"] = count("issued_date >= CURRENT_TIMESTAMP - INTERVAL '30' DAY")
    out["count_issued_7d"] = count("issued_date >= CURRENT_TIMESTAMP - INTERVAL '7' DAY")
    stats = f.get_json(src["base_url"] + "/query", params={
        "where": "1=1", "f": "json",
        "outStatistics": json.dumps([
            {"statisticType": "max", "onStatisticField": "issued_date", "outStatisticFieldName": "max_issued"},
            {"statisticType": "max", "onStatisticField": "submitted_date", "outStatisticFieldName": "max_submitted"},
            {"statisticType": "min", "onStatisticField": "issued_date", "outStatisticFieldName": "min_issued"}])},
        ttl=3600)
    attrs = (stats.get("features") or [{}])[0].get("attributes", {})
    out["dates"] = {k: ts(v) for k, v in attrs.items()}
    out["today"] = date.today().isoformat()
    out["fetch_stats"] = f.stats
    (ROOT / "lanes/permit-radar/data").mkdir(parents=True, exist_ok=True)
    (ROOT / "lanes/permit-radar/data/g0_summary.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "terms_excerpt"}, indent=1))
    print("TERMS:", out["terms_excerpt"][:5000])


if __name__ == "__main__":
    main()
