"""G0 part 2 for permit-radar: Detroit portal license text (Hub page items), trades/demolition layer
freshness, and contractor-field fill rates. Run from repo root: python lanes/permit-radar/g0_check2.py
Saves lanes/permit-radar/data/g0_summary2.json.
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

AGO = "https://www.arcgis.com/sharing/rest/content/items/"
PAGES = {"disclaimer": "3d3439cc799c424aa009af63efdc7ab1", "about": "e055d4ab2ee440798e0682f3d9ce0ef0",
         "user_faq": "05389654d3aa4516940ec6978745489b"}
ITEMS = {"building_permits": "86d47e86062e4beeb19344eb125b75d2", "trades_permits": "f77e9fd44b7e44089b41d3f8161631fa",
         "demolition_permits": "56b20af695134bd1b4ab65e1876ae79b"}


def ts(v):
    return datetime.fromtimestamp(v / 1000, timezone.utc).isoformat() if isinstance(v, (int, float)) else v


def strip(html):
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html or "", flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def walk_text(o, acc):
    if isinstance(o, dict):
        for v in o.values():
            walk_text(v, acc)
    elif isinstance(o, list):
        for v in o:
            walk_text(v, acc)
    elif isinstance(o, str) and len(o) > 40:
        acc.append(strip(o))


def main():
    out = {}
    f = Fetcher("detroit_permits", lane="permit-radar", gate="G0")

    # 1. Hub page items (the portal's disclaimer / about / FAQ) and dataset item licenseInfo
    for k, iid in PAGES.items():
        data = f.get_json(AGO + iid + "/data", params={"f": "json"}, ttl=86400)
        acc = []
        walk_text(data, acc)
        out[f"page_{k}"] = " || ".join(acc)[:6000]
    for k, iid in ITEMS.items():
        info = f.get_json(AGO + iid, params={"f": "json"}, ttl=86400)
        out[f"item_{k}"] = {"title": info.get("title"), "licenseInfo": strip(info.get("licenseInfo")),
                            "accessInformation": info.get("accessInformation"),
                            "description": strip(info.get("description"))[:1500],
                            "modified": ts(info.get("modified")), "access": info.get("access")}

    # 2. trades + demolition layers: freshness and contractor fill rates (no people fields requested)
    for sid, biz_field in (("detroit_trades_permits", "contact_business_name"),
                           ("detroit_demolition_permits", "demolition_contractor")):
        g = Fetcher(sid, lane="permit-radar", gate="G0")
        base = registry.get(sid)["base_url"]
        meta = g.get_json(base, params={"f": "json"}, ttl=86400)
        rec = {"fields": [fl["name"] for fl in meta.get("fields", [])],
               "editingInfo": {k: ts(v) for k, v in meta.get("editingInfo", {}).items()}}

        def count(where):
            d = g.get_json(base + "/query", params={"where": where, "returnCountOnly": "true", "f": "json"}, ttl=3600)
            return d.get("count", d)
        rec["count_total"] = count("1=1")
        rec["count_issued_30d"] = count("issued_date >= CURRENT_TIMESTAMP - INTERVAL '30' DAY")
        rec["count_issued_7d"] = count("issued_date >= CURRENT_TIMESTAMP - INTERVAL '7' DAY")
        rec["count_30d_with_contractor"] = count(
            f"issued_date >= CURRENT_TIMESTAMP - INTERVAL '30' DAY AND {biz_field} IS NOT NULL AND {biz_field} <> ''")
        st = g.get_json(base + "/query", params={"where": "1=1", "f": "json", "outStatistics": json.dumps(
            [{"statisticType": "max", "onStatisticField": "issued_date", "outStatisticFieldName": "max_issued"}])}, ttl=3600)
        rec["max_issued"] = ts((st.get("features") or [{}])[0].get("attributes", {}).get("max_issued"))
        if sid == "detroit_trades_permits":
            pt = g.get_json(base + "/query", params={
                "where": "issued_date >= CURRENT_TIMESTAMP - INTERVAL '30' DAY", "f": "json",
                "groupByFieldsForStatistics": "permit_type", "outStatistics": json.dumps(
                    [{"statisticType": "count", "onStatisticField": "record_id", "outStatisticFieldName": "n"}])}, ttl=3600)
            rec["permit_types_30d"] = {a["attributes"]["permit_type"]: a["attributes"]["n"] for a in pt.get("features", [])}
            smp = g.get_json(base + "/query", params={
                "where": "issued_date >= CURRENT_TIMESTAMP - INTERVAL '7' DAY", "f": "json", "returnGeometry": "false",
                "outFields": "record_id,issued_date,permit_type,work_description,contact_business_name,zip_code",
                "resultRecordCount": 5, "orderByFields": "issued_date DESC"}, ttl=3600)
            rec["sample_rows"] = [a["attributes"] for a in smp.get("features", [])]
        rec["fetch_stats"] = g.stats
        out[sid] = rec

    out["today"] = date.today().isoformat()
    out["fetch_stats_detroit_permits"] = f.stats
    (ROOT / "lanes/permit-radar/data/g0_summary2.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
