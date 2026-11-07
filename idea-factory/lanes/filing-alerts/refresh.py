"""Filing Alerts: Michigan 8-K feed, rebuilt from live SEC EDGAR data.

Run from repo root:  python lanes/filing-alerts/refresh.py
Writes: app/data/latest.json + latest.js (the web prototype), samples/michigan_8k_digest.{csv,html,pdf}
        data/registry.json (per-company cache so later ticks only top up the missing companies).

Plain language:
  1. Lists registrants whose business address is in Michigan (EDGAR company search, paged 100 at a time).
  2. For each one, reads the submissions API: name, industry (SIC), city, tickers, recent filings.
  3. Keeps the 8-Ks from the last WINDOW_DAYS days, with their item codes translated to plain words.
  4. Writes the app data and the CSV/HTML/PDF sample (the outreach attachment).
Company data only. No insider names, no people data. Per-run request budget: MAX_NEW_CIKS new companies + refresh of known active ones.
Honest limit: EDGAR's state list includes funds, trusts and shells; we drop those with no 8-K in the window. The list is
built up over several ticks (MAX_NEW_CIKS per run) so early snapshots may miss some Michigan companies; the app says how many were checked.
"""
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.fetch import Fetcher, FetchError  # noqa: E402
from core.samples import write_all  # noqa: E402

LANE = "filing-alerts"
HERE = ROOT / "lanes" / LANE
APP = HERE / "app"
WINDOW_DAYS = 45
MAX_PAGES = 12
MAX_NEW_CIKS = 170
MAX_REFRESH = 100

ITEMS = {
    "1.01": ("Signed a major agreement", "deal"), "1.02": ("Ended a major agreement", "deal"),
    "1.03": ("Bankruptcy or receivership", "distress"), "1.05": ("Cybersecurity incident", "risk"),
    "2.01": ("Completed an acquisition or sale", "deal"), "2.02": ("Reported earnings", "earnings"),
    "2.03": ("Took on new debt", "money"), "2.04": ("Debt accelerated or triggered", "distress"),
    "2.05": ("Restructuring or exit costs", "distress"), "2.06": ("Asset write-down (impairment)", "distress"),
    "3.01": ("Stock exchange delisting notice", "distress"), "3.02": ("Sold unregistered shares", "money"),
    "3.03": ("Changed shareholder rights", "other"), "4.01": ("Changed auditors", "governance"),
    "4.02": ("Past financials can no longer be relied on", "distress"),
    "5.01": ("Change of control", "deal"), "5.02": ("Executive or director change", "leadership"),
    "5.03": ("Bylaws or charter amended", "governance"), "5.07": ("Shareholder vote results", "governance"),
    "7.01": ("Regulation FD disclosure", "other"), "8.01": ("Other events", "other"),
    "9.01": ("Exhibits attached", "other"),
}
SKIP_ONLY = {"9.01"}  # not interesting on its own
SKIP_SIC = {"6189", "6726", "6770"}  # asset-backed trusts, closed-end funds, blank-check shells
CACHE_REGISTRY = HERE / "data" / "registry.json"


def utcnow():
    return datetime.now(timezone.utc)


# Operating-company industry codes to scan (EDGAR's plain Michigan list is mostly LLC shells and funds, so we
# search Michigan by industry instead). Broad on purpose: autos and suppliers, machinery, medical, banks, utilities, retail.
SIC_SCAN = ["0100", "1000", "1311", "1531", "1600", "1700", "2000", "2011", "2040", "2060", "2080", "2300", "2400", "2510", "2521",
            "2531", "2670", "2700", "2800", "2810", "2820", "2834", "2835", "2836", "2860", "2890", "2891", "2911", "3011", "3050",
            "3060", "3080", "3220", "3260", "3310", "3350", "3360", "3411", "3420", "3430", "3440", "3452", "3460", "3490", "3510",
            "3523", "3530", "3550", "3559", "3560", "3569", "3570", "3585", "3590", "3600", "3612", "3620", "3630", "3661", "3670",
            "3672", "3674", "3690", "3711", "3713", "3714", "3715", "3716", "3720", "3728", "3790", "3812", "3823", "3825", "3826",
            "3829", "3841", "3842", "3844", "3845", "3860", "3990", "4011", "4213", "4400", "4512", "4813", "4911", "4922", "4923",
            "4924", "4931", "4941", "5000", "5045", "5065", "5090", "5120", "5130", "5140", "5200", "5311", "5331", "5400", "5500",
            "5531", "5600", "5700", "5812", "5900", "5990", "6021", "6022", "6035", "6036", "6141", "6153", "6199", "6211", "6282",
            "6311", "6321", "6331", "6351", "6411", "6500", "6510", "6512", "6519", "6770", "6798", "7011", "7200", "7310", "7320",
            "7340", "7350", "7359", "7361", "7363", "7370", "7371", "7372", "7373", "7374", "7380", "7389", "7510", "7600", "7812",
            "7990", "8000", "8011", "8050", "8062", "8071", "8090", "8200", "8711", "8731", "8742", "8744", "8900"]
SIC_BUDGET = 70  # scan this many industry codes per run (rotating), the rest on later ticks


def list_michigan_ciks(f, rotation):
    ciks, scanned = [], 0
    codes = SIC_SCAN[rotation:] + SIC_SCAN[:rotation]
    for sic in codes[:SIC_BUDGET]:
        t = f.get_text("https://www.sec.gov/cgi-bin/browse-edgar", ttl=24 * 3600,
                       params={"action": "getcompany", "State": "MI", "SIC": sic, "owner": "include",
                               "count": "100", "output": "atom"})
        ciks += [c for c in re.findall(r"<cik>(\d+)</cik>", t) if c not in ciks]
        scanned += 1
    return ciks, scanned


def summarize(j, cutoff):
    biz = (j.get("addresses") or {}).get("business") or {}
    r = (j.get("filings") or {}).get("recent") or {}
    cik = str(int(j["cik"]))
    out = {"cik": cik, "name": (j.get("name") or "").title() if (j.get("name") or "").isupper() else j.get("name"),
           "sic": j.get("sic") or "", "industry": j.get("sicDescription") or "", "city": (biz.get("city") or "").title(),
           "state": biz.get("stateOrCountry") or "", "tickers": j.get("tickers") or [], "exchanges": j.get("exchanges") or [],
           "website": j.get("website") or "", "fetched": utcnow().isoformat(timespec="seconds"), "filings": []}
    for i, form in enumerate(r.get("form", [])):
        if not form.startswith("8-K"):
            continue
        d = r["filingDate"][i]
        if d < cutoff:
            continue
        items = [x.strip() for x in (r["items"][i] or "").split(",") if x.strip()]
        acc = r["accessionNumber"][i]
        out["filings"].append({
            "form": form, "date": d, "accepted": r["acceptanceDateTime"][i], "accession": acc, "items": items,
            "url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{r['primaryDocument'][i]}",
            "index": f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{acc}-index.htm"})
    return out


def main():
    f = Fetcher("sec_edgar", lane=LANE, gate="G1")
    cutoff = (date.today() - timedelta(days=WINDOW_DAYS)).isoformat()
    reg = json.loads(CACHE_REGISTRY.read_text()) if CACHE_REGISTRY.exists() else {"companies": {}}
    comp = reg["companies"]
    rotation = reg.get("rotation", 0)
    ciks, scanned = list_michigan_ciks(f, rotation)
    reg["rotation"] = (rotation + scanned) % len(SIC_SCAN)
    reg.setdefault("listed", {})
    for c in ciks:
        reg["listed"][str(int(c))] = 1
    complete = len(reg.get("covered", [])) >= len(SIC_SCAN)
    reg["covered"] = sorted(set(reg.get("covered", [])) | set(SIC_SCAN[rotation:rotation + scanned] + (SIC_SCAN[:rotation + scanned - len(SIC_SCAN)] if rotation + scanned > len(SIC_SCAN) else [])))
    complete = len(reg["covered"]) >= len(SIC_SCAN)
    ciks = list(reg["listed"])
    print(f"Michigan operating registrants listed: {len(ciks)} (all industries scanned={complete}); cached: {len(comp)}")
    new = [c for c in ciks if str(int(c)) not in comp][:MAX_NEW_CIKS]
    active = sorted((c for c in comp.values() if c["filings"]), key=lambda c: c["fetched"])[:MAX_REFRESH]
    fails = 0
    for cik in new + [c["cik"] for c in active]:
        try:
            j = f.get_json(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", ttl=3600)
            comp[str(int(cik))] = summarize(j, cutoff)
        except (FetchError, Exception) as e:  # keep going; one bad company must not stop the run
            fails += 1
            print("fail", cik, str(e)[:80])
    if not comp:
        raise SystemExit("no data fetched; keeping previous output")
    reg["updated"] = utcnow().isoformat(timespec="seconds")
    CACHE_REGISTRY.write_text(json.dumps(reg, indent=0))

    rows, companies = [], []
    for c in comp.values():
        c["filings"] = [x for x in c["filings"] if x["date"] >= cutoff]
        if c["sic"] in SKIP_SIC or not c["filings"] or c["state"] != "MI":
            continue
        for x in c["filings"]:
            labels = [ITEMS[i][0] for i in x["items"] if i in ITEMS and i not in SKIP_ONLY] or ["Exhibits / other"]
            cats = [ITEMS[i][1] for i in x["items"] if i in ITEMS and i not in SKIP_ONLY] or ["other"]
            x["labels"], x["cats"] = labels, sorted(set(cats))
        companies.append(c)
        for x in c["filings"]:
            rows.append({"date": x["date"], "company": c["name"], "ticker": (c["tickers"] or [""])[0], "city": c["city"],
                         "industry": c["industry"], "what_happened": "; ".join(x["labels"]),
                         "items": ",".join(x["items"]), "link": x["index"]})
    companies.sort(key=lambda c: max(x["accepted"] for x in c["filings"]), reverse=True)
    rows.sort(key=lambda r: r["date"], reverse=True)
    n_filings = sum(len(c["filings"]) for c in companies)
    stamp = utcnow().isoformat(timespec="seconds")
    data = {"generated": stamp, "window_days": WINDOW_DAYS, "since": cutoff,
            "listed": len(ciks), "list_complete": complete, "industries_scanned": len(reg["covered"]), "industries_total": len(SIC_SCAN), "checked": len(comp), "companies": companies,
            "n_companies": len(companies), "n_filings": n_filings,
            "items": {k: {"label": v[0], "cat": v[1]} for k, v in ITEMS.items()},
            "source": "U.S. Securities and Exchange Commission EDGAR"}
    APP.joinpath("data").mkdir(parents=True, exist_ok=True)
    (APP / "data" / "latest.json").write_text(json.dumps(data, indent=1))
    (APP / "data" / "latest.js").write_text("window.FILINGS_SNAPSHOT = " + json.dumps(data) + ";\n")

    cols = [("date", "Filed"), ("company", "Company"), ("ticker", "Ticker"), ("city", "City"),
            ("industry", "Industry (SIC)"), ("what_happened", "What it reports"), ("items", "8-K items"), ("link", "Filing")]
    write_all(rows[:60], cols, HERE / "samples", "Michigan 8-K digest",
              subtitle=f"Michigan-based public companies, 8-Ks filed since {cutoff}. Built {stamp[:10]}.",
              notes=["Source: SEC EDGAR (public record). Company filings only; no individuals are tracked.",
                     f"{len(comp)} Michigan registrants checked so far; {len(companies)} filed an 8-K in the last {WINDOW_DAYS} days.",
                     "'What it reports' is a plain-words translation of the 8-K item codes, not a summary of the document."],
              source_line="Source: U.S. Securities and Exchange Commission EDGAR", basename="michigan_8k_digest")
    print(f"companies with 8-Ks: {len(companies)}, filings: {n_filings}, fetch failures: {fails}")


if __name__ == "__main__":
    main()
