"""G0 probe part 2: read NHTSA's own terms/tool pages and check the bulk flat-file folder.
Run from repo root: python lanes/recall-checks/g0_terms_probe.py
Saves the page text (stripped of tags) under lanes/recall-checks/data/ for the record.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.fetch import Fetcher, FetchError  # noqa: E402

OUT = ROOT / "lanes" / "recall-checks" / "data"
OUT.mkdir(parents=True, exist_ok=True)


def strip(html):
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    return re.sub(r"\s+", " ", text).strip()


web = Fetcher("nhtsa_web", lane="recall-checks", gate="G0")
pages = {
    "datasets_apis": "https://www.nhtsa.gov/nhtsa-datasets-and-apis",
    "recalls_tool": "https://www.nhtsa.gov/recalls",
    "web_policies": "https://www.nhtsa.gov/web-policies-and-notices",
}
browser_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) IdeaFactory-G0-terms-check",
                   "Accept": "text/html,application/xhtml+xml", "Accept-Language": "en-US,en;q=0.9"}
for name, url in pages.items():
    for hdrs in ({}, browser_headers):
        try:
            t, s = web.get(url, headers=hdrs, retries=0)
            txt = strip(t)
            (OUT / f"g0_page_{name}.txt").write_text(txt, encoding="utf-8")
            print(f"OK   {name} status={s} chars={len(txt)} (headers={'browser' if hdrs else 'default'})")
            for kw in ("commercial", "VIN", "public domain", "copyright", "terms", "weekly", "manufacturer"):
                for m in re.finditer(re.escape(kw), txt, flags=re.I):
                    a, b = max(0, m.start() - 120), min(len(txt), m.end() + 160)
                    print(f"   [{kw}] ...{txt[a:b]}...")
                    break
            break
        except FetchError as e:
            print(f"FAIL {name} headers={'browser' if hdrs else 'default'}: {str(e)[:90]}")

print("== flat files folder ==")
ff = Fetcher("nhtsa_odi_flatfiles", lane="recall-checks", gate="G0")
for u in ("https://static.nhtsa.gov/odi/ffdd/rcl/RCL.txt", "https://static.nhtsa.gov/odi/ffdd/rcl/"):
    try:
        t, s = ff.get(u, retries=0)
        print("OK  ", u, s, len(t), "chars;", strip(t)[:400])
    except FetchError as e:
        print("FAIL", u, str(e)[:100])

print("== api.nhtsa.gov: is 403 just 'unknown route'? ==")
rec = Fetcher("nhtsa_recalls", lane="recall-checks", gate="G0")
for u in ("https://api.nhtsa.gov/recalls/nonexistent-route-xyz",
          "https://api.nhtsa.gov/vehicles/byVin",
          "https://api.nhtsa.gov/SafetyRatings"):
    try:
        t, s = rec.get(u, {"vin": "1FTFW1ET5DFC10312"} if "byVin" in u else None, retries=0)
        print("OK  ", u, s, t[:160].replace("\n", " "))
    except FetchError as e:
        print("FAIL", u, str(e)[:100])
