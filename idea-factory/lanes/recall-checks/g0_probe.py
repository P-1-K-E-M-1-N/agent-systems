"""G0 probe: real requests to NHTSA vPIC (VIN decode, single + batch) and the Recalls API.
Run from repo root: python lanes/recall-checks/g0_probe.py
Also tries a few guessed VIN-level recall endpoints to document that none is public.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.fetch import Fetcher, FetchError  # noqa: E402

OUT = ROOT / "lanes" / "recall-checks" / "data"
OUT.mkdir(parents=True, exist_ok=True)

# Publicly posted example VINs (NHTSA vPIC docs example + widely used test VINs)
VINS = ["5UXWX7C5*BA", "1FTFW1ET5DFC10312", "1G1ZD5ST8JF134409", "3VWFE21C04M000001"]

vpic = Fetcher("nhtsa_vpic", lane="recall-checks", gate="G0")
print("== vPIC single decode ==")
d = vpic.get_json(f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{VINS[1]}", {"format": "json"})
r = d["Results"][0]
print({k: r.get(k) for k in ("Make", "Model", "ModelYear", "BodyClass", "ErrorCode", "ErrorText")})
print("vpic single stats", vpic.stats)

print("== vPIC batch decode (POST) ==")
body = "format=json&data=" + ";".join(VINS[1:])
d = vpic.get_json("https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVINValuesBatch/", body=body, method="POST",
                  headers={"Content-Type": "application/x-www-form-urlencoded"})
for r in d["Results"]:
    print({k: r.get(k) for k in ("VIN", "Make", "Model", "ModelYear", "ErrorCode")})
print("vpic batch stats", vpic.stats)

rec = Fetcher("nhtsa_recalls", lane="recall-checks", gate="G0")
print("== recallsByVehicle ==")
d = rec.get_json("https://api.nhtsa.gov/recalls/recallsByVehicle",
                 {"make": "ford", "model": "f-150", "modelYear": "2013"})
print("Count", d.get("Count"), "keys", list(d.get("results", [{}])[0].keys()) if d.get("results") else None)
for x in d.get("results", [])[:3]:
    print(x.get("NHTSACampaignNumber"), x.get("ReportReceivedDate"), x.get("Component"), "|", (x.get("Summary") or "")[:100])
(OUT / "g0_recalls_f150_2013.json").write_text(json.dumps(d, indent=1), encoding="utf-8")

print("== recalls product list endpoints ==")
d = rec.get_json("https://api.nhtsa.gov/products/vehicle/modelYears", {"issueType": "r"})
print("modelYears Count", d.get("Count"))
d = rec.get_json("https://api.nhtsa.gov/products/vehicle/makes", {"modelYear": 2015, "issueType": "r"})
print("makes 2015 Count", d.get("Count"), [m.get("make") for m in d.get("results", [])[:8]])
d = rec.get_json("https://api.nhtsa.gov/products/vehicle/models", {"modelYear": 2015, "make": "chevrolet", "issueType": "r"})
print("chevy 2015 models Count", d.get("Count"), [m.get("model") for m in d.get("results", [])[:12]])

print("== campaign detail ==")
d = rec.get_json("https://api.nhtsa.gov/recalls/campaignNumber", {"campaignNumber": "23V123000"})
print("campaign Count", d.get("Count"), json.dumps(d.get("results", [{}])[0], indent=1)[:600])

print("== VIN-level attempts (expect failure / restricted) ==")
for url, params in [
    ("https://api.nhtsa.gov/recalls/recallsByVin", {"vin": VINS[1]}),
    ("https://api.nhtsa.gov/vehicles/byVin", {"vin": VINS[1]}),
    ("https://api.nhtsa.gov/safercar/vin", {"vin": VINS[1]}),
    ("https://www.nhtsa.gov/webapi/api/Recalls/vehicle/vin/" + VINS[1], {"format": "json"}),
]:
    try:
        t, s = rec.get(url, params, retries=0)
        print("OK", url, s, t[:200].replace("\n", " "))
    except FetchError as e:
        print("FAIL", url, str(e)[:120])
print("recalls stats", rec.stats)
