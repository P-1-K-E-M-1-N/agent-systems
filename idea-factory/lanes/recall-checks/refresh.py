"""Recall Exposure Sheet: rebuilds the dealer-facing sample from live NHTSA data.

Run from repo root:  python lanes/recall-checks/refresh.py
Output: lanes/recall-checks/samples/recall_exposure_sheet.{csv,html,pdf} plus
        lanes/recall-checks/data/recalls_by_vehicle.json (raw, for the record).

What it does, in plain language:
  1. Reads the sample inventory below (VIN where a public example VIN exists,
     otherwise year/make/model, which is what most small lots can hand over).
  2. Decodes VINs in one batch POST to NHTSA vPIC (max 50 per call).
  3. Pulls every NHTSA safety recall campaign for each year/make/model.
  4. Ranks recalls by seriousness (park-it / park-outside flags, then component
     keywords like air bag, brakes, steering, fuel/fire) and summarizes the top one.
  5. Writes CSV + HTML + PDF through core.samples (the PDF is the email attachment).
  6. Writes the web prototype's data (rule 1, 2026-10-25):
        app/data/latest.json     the lot: one record per vehicle with every campaign,
                                 a severity category per campaign, lot label, timestamps
        app/data/campaigns.json  every campaign the lot touched, keyed "year|make|model",
                                 so "Check a vehicle" works offline in the review sandbox
        app/data/latest.js       latest.json as a classic script, loaded before first paint

Honest limitation (see LANE.md G0): NHTSA's public API returns campaigns that
APPLY to a year/make/model. It cannot say whether a specific VIN's recall is
still open. Each row therefore says "verify VIN at nhtsa.gov/recalls" and the
sheet is called an EXPOSURE report, not an open-recall report.
"""
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.fetch import Fetcher, FetchError  # noqa: E402
from core.samples import write_all  # noqa: E402

LANE = "recall-checks"
HERE = ROOT / "lanes" / LANE
GATE = "G1"

# --- Sample inventory --------------------------------------------------------
# VINs are PUBLIC EXAMPLE VINs from NHTSA vPIC documentation or long-standing
# textbook examples. They identify vehicles, not people. Partial VINs use '*'.
# Everything else is a year/make/model typical of a Metro Detroit used lot.
INVENTORY = [
    {"stock": "A101", "vin": "1FTFW1ET5DFC10312"},                 # 2013 Ford F-150 (common example VIN)
    {"stock": "A102", "vin": "1G1ZD5ST8JF134409"},                 # 2018 Chevrolet Malibu
    {"stock": "A103", "vin": "1HGCM82633A004352"},                 # 2003 Honda Accord (textbook example)
    {"stock": "A104", "vin": "WBAFR9C57BC270614"},                 # 2011 BMW 535i (textbook example)
    {"stock": "A105", "vin": "5UXWX7C5*BA", "model_year": 2011},  # NHTSA docs partial VIN, BMW X3
    {"stock": "A106", "vin": "5YJSA3DS*EF", "model_year": 2014},  # NHTSA docs partial VIN, Tesla Model S
    {"stock": "A107", "year": 2016, "make": "Chevrolet", "model": "Silverado 1500"},
    {"stock": "A108", "year": 2017, "make": "Chevrolet", "model": "Equinox"},
    {"stock": "A109", "year": 2015, "make": "Ford", "model": "Escape"},
    {"stock": "A110", "year": 2014, "make": "Jeep", "model": "Grand Cherokee"},
    {"stock": "A111", "year": 2016, "make": "Ford", "model": "Fusion"},
    {"stock": "A112", "year": 2018, "make": "Honda", "model": "CR-V"},
    {"stock": "A113", "year": 2015, "make": "Toyota", "model": "Camry"},
    {"stock": "A114", "year": 2017, "make": "Toyota", "model": "RAV4"},
    {"stock": "A115", "year": 2016, "make": "Ford", "model": "Explorer"},
    {"stock": "A116", "year": 2017, "make": "Ram", "model": "1500"},
    {"stock": "A117", "year": 2015, "make": "Chevrolet", "model": "Cruze"},
    {"stock": "A118", "year": 2014, "make": "Ford", "model": "Focus"},
    {"stock": "A119", "year": 2012, "make": "Dodge", "model": "Grand Caravan"},
    {"stock": "A120", "year": 2016, "make": "Jeep", "model": "Cherokee"},
]

SEVERE = [  # (regex on component+summary, weight)
    (r"air ?bag|inflator", 5), (r"fuel|fire|burn", 5), (r"steering", 4), (r"brake", 4),
    (r"roll ?away|park|transmission", 3), (r"seat ?belt|restraint", 3), (r"wheel|tire|axle|suspension", 3),
    (r"electrical|light|wiper", 1),
]


def severity(r):
    s = 0
    if r.get("parkIt"):
        s += 10
    if r.get("parkOutSide"):
        s += 10
    text = f"{r.get('Component','')} {r.get('Summary','')}".lower()
    for pat, w in SEVERE:
        if re.search(pat, text):
            s += w
    return s


# Severity category shown in the app. One of three words a dealer can act on; "critical" is the only one that
# gets safety red. Order matters: the first matching rule wins.
# The same four regexes live in app/app.js (categorize) so a live lookup in the browser gets the same answer.
CRIT_COMPONENT = r"air ?bag|inflator|brake|steering|fuel"
CRIT_CONSEQUENCE = r"\bfire\b|loss of (steering|brak)|unable to (stop|steer)|do not drive|park (it|outside)"
SERIOUS_COMPONENT = (r"seat ?belt|restraint|child seat|wheel|tire|axle|suspension|control arm|hood|latch|structure|frame|"
                     r"power train|transmission|engine|visibility|exterior lighting")
SERIOUS_CONSEQUENCE = r"stall|roll ?away|loss of (motive )?power|loss of (drive|propulsion)|detach|separate|unintended"
CATEGORY_ORDER = {"critical": 0, "serious": 1, "moderate": 2}


def category(r):
    """critical: NHTSA park-it / park-outside advisory; or the component is air bags, brakes, steering or fuel;
    or NHTSA's consequence sentence says fire, loss of steering/braking, unable to stop or steer.
    serious: seat belts, wheels/tires/suspension, hood/latch/structure, powertrain, lights; or the consequence
    says stall, rollaway, loss of power, parts detaching, unintended movement.
    moderate: everything else (electrical odds and ends, cameras, labels, seats)."""
    if r.get("parkIt") or r.get("parkOutSide"):
        return "critical"
    comp = (r.get("Component") or "").lower()
    cons = (r.get("Consequence") or "").lower()
    if re.search(CRIT_COMPONENT, comp) or re.search(CRIT_CONSEQUENCE, cons):
        return "critical"
    if re.search(SERIOUS_COMPONENT, comp) or re.search(SERIOUS_CONSEQUENCE, cons):
        return "serious"
    return "moderate"


_MOJIBAKE = {"\x91": "'", "\x92": "'", "\x93": '"', "\x94": '"', "\x96": "-", "\x97": "-", "�": "'"}


def clean_text(s):
    """NHTSA records carry Windows-1252 quote bytes; straighten them and collapse whitespace."""
    s = s or ""
    for k, v in _MOJIBAKE.items():
        s = s.replace(k, v)
    return re.sub(r"\s+", " ", s).strip()


def parse_date(d):
    # API returns DD/MM/YYYY
    try:
        dd, mm, yy = d.split("/")
        return f"{yy}-{mm}-{dd}"
    except Exception:
        return d or ""


def _sentences(text):
    text = clean_text(text)
    if text.isupper():  # older NHTSA records are shouted in caps
        text = ". ".join(s[:1].upper() + s[1:].lower() for s in text.split(". "))
    return [s.strip() for s in re.split(r"(?<=[a-z0-9\)\"])\.\s+(?=[A-Z\"])", text) if s.strip()]


def nice_component(c):
    """'AIR BAGS:FRONTAL:DRIVER SIDE:INFLATOR MODULE' -> 'Air bags / frontal / driver side / inflator module'."""
    parts = [p.strip().lower() for p in (c or "").split(":") if p.strip()]
    if not parts:
        return ""
    s = " / ".join(parts)
    return s[:1].upper() + s[1:]


def plain_defect(summary, limit=175):
    """NHTSA summaries open with 'Ford is recalling certain model year ... vehicles manufactured ...'. A dealer
    already knows that; show the sentence that says what is wrong."""
    sents = _sentences(summary)
    if not sents:
        return ""
    if len(sents) > 1 and re.search(r"\b(is|are) recalling\b", sents[0], re.I):
        sents = sents[1:]
    out = ""
    for s in sents:
        cand = (out + " " + s).strip()
        if not cand.endswith("."):
            cand += "."
        if len(cand) > limit and out:
            break
        out = cand
        if len(out) >= limit * 0.6:
            break
    return out if len(out) <= limit else out[:limit - 3].rsplit(" ", 1)[0] + "..."


def plain_fix(remedy, limit=105):
    """'GM will notify owners, and dealers will reprogram the ECM software, free of charge. The recall began...'
    -> 'Dealers will reprogram the ECM software, free of charge.'"""
    sents = _sentences(remedy)
    if not sents:
        return ""
    s = sents[0]
    s = re.sub(r"^.*?\bwill notify (the )?owners?,?\s*(and|;)?\s*", "", s, flags=re.I)
    s = s[:1].upper() + s[1:]
    if not s.endswith("."):
        s += "."
    return s if len(s) <= limit else s[:limit - 3].rsplit(" ", 1)[0] + "..."


def decode_vins(vpic, items):
    """Batch-decode (max 50/POST). Returns {stock: decoded dict}."""
    out = {}
    for i in range(0, len(items), 50):
        chunk = items[i:i + 50]
        data = ";".join(f"{it['vin']},{it['model_year']}" if it.get("model_year") else it["vin"] for it in chunk)
        res = vpic.get_json("https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVINValuesBatch/",
                            body="format=json&data=" + data, method="POST",
                            headers={"Content-Type": "application/x-www-form-urlencoded"})
        for it, r in zip(chunk, res.get("Results", [])):
            out[it["stock"]] = r
    return out


def pick_model_name(rec, year, make, model):
    """NHTSA recall API wants its own model spelling (e.g. 'SILVERADO 1500'). Match loosely."""
    try:
        lst = rec.get_json("https://api.nhtsa.gov/products/vehicle/models",
                           {"modelYear": year, "make": make, "issueType": "r"})
        names = sorted({m.get("model", "") for m in lst.get("results", [])})
    except FetchError:
        return model
    want = re.sub(r"[^a-z0-9]", "", model.lower())
    exact = [n for n in names if re.sub(r"[^a-z0-9]", "", n.lower()) == want]
    if exact:
        return exact[0]
    starts = [n for n in names if re.sub(r"[^a-z0-9]", "", n.lower()).startswith(want)]
    if starts:
        return sorted(starts, key=len)[0]
    contains = [n for n in names if want in re.sub(r"[^a-z0-9]", "", n.lower())]
    return sorted(contains, key=len)[0] if contains else model


def recalls_for(rec, year, make, model, alt_model=None):
    """Try the plain model name first (the API accepts 'f-150' even when its own model list only shows
    'F-150 SUPERCAB' variants); fall back to the matched variant. The API answers HTTP 400 for some
    combinations and intermittently, so one failure is not treated as 'no recalls'."""
    tried, last = [], None
    for m in [model] + ([alt_model] if alt_model and alt_model != model else []):
        for attempt in range(2):
            try:
                d = rec.get_json("https://api.nhtsa.gov/recalls/recallsByVehicle",
                                 {"make": make, "model": m, "modelYear": year}, force=attempt == 1)
                res = d.get("results", [])
                if res or attempt == 1:
                    return res, m
            except FetchError as e:
                last = e
                tried.append(f"{m} ({e})")
    if last:
        raise FetchError("; ".join(tried))
    return [], model


def app_campaign(r):
    """One NHTSA campaign as the web app shows it: ids, plain words, the category, the flags."""
    return {
        "id": r.get("NHTSACampaignNumber", ""),
        "component": nice_component(r.get("Component", "")),
        "component_raw": r.get("Component", ""),
        "defect": plain_defect(r.get("Summary", ""), limit=240),
        "fix": plain_fix(r.get("Remedy", ""), limit=160),
        "summary": clean_text(r.get("Summary", "")),
        "consequence": clean_text(r.get("Consequence", "")),
        "remedy": clean_text(r.get("Remedy", "")),
        "manufacturer": r.get("Manufacturer", ""),
        "report_date": parse_date(r.get("ReportReceivedDate", "")),
        "severity": category(r),
        "park_it": bool(r.get("parkIt")),
        "park_outside": bool(r.get("parkOutSide")),
        "ota": bool(r.get("overTheAirUpdate")),
    }


def lookup_key(year, make, model):
    return f"{year}|{str(make).lower().strip()}|{str(model).lower().strip()}"


def write_app_data(vehicles, raw):
    """app/data/latest.json (the lot) and app/data/campaigns.json (offline lookup by year|make|model)."""
    out = HERE / "app" / "data"
    out.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for v in vehicles:
        cats = [c["severity"] for c in v["campaigns"]]
        v["worst"] = min(cats, key=CATEGORY_ORDER.get) if cats else ("unknown" if v["lookup_failed"] else "clean")
        v["n"] = len(v["campaigns"])
        v["lookup_key"] = lookup_key(v["year"], v["make"], v["model"])
    order = {"critical": 0, "serious": 1, "moderate": 2, "unknown": 3, "clean": 4}
    # Most serious first: NHTSA advisory (park it / park outside), then worst category, then number of critical
    # campaigns, then total campaigns.
    vehicles.sort(key=lambda v: (0 if v["flags"] else 1, order[v["worst"]],
                                 -sum(1 for c in v["campaigns"] if c["severity"] == "critical"), -v["n"], v["stock"]))
    totals = {k: sum(1 for v in vehicles for c in v["campaigns"] if c["severity"] == k) for k in CATEGORY_ORDER}
    latest = {
        "lot": {"label": "Example lot", "note": "example stock with public example VINs; not a real dealer's inventory",
                "vehicles": len(vehicles)},
        "checked_at": date.today().isoformat(),
        "generated_at": now,
        "cadence": "weekly",
        "source": "NHTSA vPIC VIN decoder and NHTSA Recalls API (US Government work, public domain). Not affiliated with NHTSA.",
        "limitation": "NHTSA's free data says a campaign exists for this year, make and model; it cannot say whether this "
                      "exact car was already repaired. Confirm at the dealer portal or nhtsa.gov/recalls with the VIN before sale.",
        "severity_rule": {
            "critical": "NHTSA do-not-drive or park-outside advisory, or brakes, steering, air bags, fuel or fire",
            "serious": "seat belts, wheels/tires/suspension, stalling or rollaway, hood/latch/structure",
            "moderate": "everything else: lights, wipers, software, labels",
        },
        "totals": {
            "vehicles": len(vehicles),
            "with_campaigns": sum(1 for v in vehicles if v["n"]),
            "campaigns": sum(v["n"] for v in vehicles),
            "critical_vehicles": sum(1 for v in vehicles if v["worst"] == "critical"),
            "lookup_failed": sum(1 for v in vehicles if v["lookup_failed"]),
            "by_severity": totals,
        },
        "vehicles": vehicles,
    }
    (out / "latest.json").write_text(json.dumps(latest, indent=1), encoding="utf-8")
    # Same snapshot as a classic script: index.html loads it before first paint, so the lot and its numbers are on
    # screen in the first frame with no fetch (and the page works from file:// too). app.js falls back to the JSON.
    (out / "latest.js").write_text("window.RECALL_SNAPSHOT=" + json.dumps(latest, separators=(",", ":")) + ";\n",
                                   encoding="utf-8")

    campaigns = {}
    for v in vehicles:
        k = v["lookup_key"]
        entry = campaigns.setdefault(k, {"year": v["year"], "make": v["make"], "model": v["model"],
                                         "api_model": raw.get(v["stock"], {}).get("api_model", v["model"]),
                                         "lookup_failed": v["lookup_failed"], "campaigns": []})
        seen = {c["id"] for c in entry["campaigns"]}
        entry["campaigns"] += [c for c in v["campaigns"] if c["id"] not in seen]
    (out / "campaigns.json").write_text(json.dumps({"generated_at": now, "keys": sorted(campaigns), "by_key": campaigns},
                                                   indent=1), encoding="utf-8")
    print("app data", (out / "latest.json").stat().st_size, "bytes,", (out / "campaigns.json").stat().st_size, "bytes")


def build():
    vpic = Fetcher("nhtsa_vpic", lane=LANE, gate=GATE)
    rec = Fetcher("nhtsa_recalls", lane=LANE, gate=GATE)
    with_vin = [it for it in INVENTORY if it.get("vin")]
    decoded = decode_vins(vpic, with_vin) if with_vin else {}

    rows, raw, app_vehicles = [], {}, []
    for it in INVENTORY:
        year, make, model, vin_note, trim = it.get("year"), it.get("make"), it.get("model"), "", ""
        if it.get("vin"):
            d = decoded.get(it["stock"], {})
            year = d.get("ModelYear") or it.get("model_year") or ""
            make = (d.get("Make") or "").title()
            model = d.get("Model") or ""
            trim = (d.get("Trim") or d.get("Series") or "").strip()
            if trim and trim.lower() in model.lower():
                trim = ""
            if d.get("Series") and model and model.lower() in ("silverado", "sierra", "f-series"):
                model = f"{model} {d['Series']}"
            code = d.get("ErrorCode", "")
            # vPIC code 1 is only a check-digit mismatch (the example VINs are not real cars); anything else
            # means the VIN did not decode cleanly and the dealer should re-type it.
            if code and code.split(",")[0].strip() not in ("0", "1"):
                vin_note = "VIN did not decode cleanly, re-check the VIN"
            if "*" in it["vin"]:
                vin_note = "partial VIN, sample"
        if len(make) <= 3:
            make = make.upper()  # BMW, GMC, KIA
        api_model = pick_model_name(rec, year, make, model)
        try:
            recs, used_model = recalls_for(rec, year, make, model, api_model)
        except FetchError as e:
            recs, used_model = [], api_model
            # Reproducible for e.g. 2017 Chevrolet Equinox: NHTSA's API answers HTTP 400 for some valid
            # combinations. A real product would fall back to the daily flat file (FLAT_RCL_POST_2010.zip).
            vin_note = (vin_note + "; " if vin_note else "") + \
                "NHTSA lookup failed this run (their API, not the car); we retry next week, or search nhtsa.gov/recalls by hand"
        raw[it["stock"]] = {"year": year, "make": make, "model": model, "api_model": used_model, "recalls": recs}
        recs_sorted = sorted(recs, key=lambda r: parse_date(r.get("ReportReceivedDate", "")), reverse=True)
        recs_sorted.sort(key=severity, reverse=True)  # stable: most serious first, newest within a tie
        top = recs_sorted[0] if recs_sorted else None
        flags = []
        if any(r.get("parkIt") for r in recs):
            flags.append("DO NOT DRIVE")
        if any(r.get("parkOutSide") for r in recs):
            flags.append("PARK OUTSIDE")
        newest = max((parse_date(r.get("ReportReceivedDate", "")) for r in recs), default="")
        lookup_failed = "lookup failed" in vin_note
        if top:
            issue = nice_component(top.get("Component", ""))
            defect = plain_defect(top.get("Summary", ""))
            issue = f"{issue}. {defect}" if defect else issue
            fix = plain_fix(top.get("Remedy", ""))
        elif lookup_failed:
            issue, fix = vin_note, ""
        else:
            issue, fix = "No safety recalls on file for this year, make and model.", ""
        camp_ids = [r.get("NHTSACampaignNumber", "") for r in recs_sorted]
        campaigns = (", ".join(camp_ids) if len(camp_ids) <= 3
                     else ", ".join(camp_ids[:2]) + chr(10) + f"+{len(camp_ids) - 2} more")
        app_vehicles.append({
            "stock": it["stock"],
            "year": int(year) if str(year).isdigit() else year,
            "make": make, "model": model, "trim": trim,
            "vin": it.get("vin", ""),
            "vin_note": vin_note if not lookup_failed else "",
            "lookup_failed": lookup_failed,
            "campaigns": [app_campaign(r) for r in recs_sorted],
            "flags": flags,
            "newest": newest,
        })
        rows.append({
            "stock": it["stock"],
            "vehicle": f"{year} {make} {model}".strip(),
            "vin": (it.get("vin", "") or "year/make/model only") + (f" ({vin_note})" if vin_note and not lookup_failed else ""),
            "n_recalls": "?" if lookup_failed else len(recs),
            "flags": ", ".join(flags),
            "issue": issue,
            "fix": fix,
            "campaigns": campaigns,
            "newest": newest,
        })

    (HERE / "data").mkdir(parents=True, exist_ok=True)
    (HERE / "data" / "recalls_by_vehicle.json").write_text(json.dumps(raw, indent=1), encoding="utf-8")
    write_app_data(app_vehicles, raw)

    total = sum(r["n_recalls"] for r in rows if isinstance(r["n_recalls"], int))
    exposed = sum(1 for r in rows if isinstance(r["n_recalls"], int) and r["n_recalls"])
    flagged = sum(1 for r in rows if r["flags"])
    cols = [("stock", "Stock"), ("vehicle", "Vehicle"), ("vin", "VIN"), ("n_recalls", "Recalls"),
            ("flags", "Flags"), ("issue", "Most serious recall and what is wrong"), ("fix", "The fix"),
            ("campaigns", "NHTSA campaign numbers"), ("newest", "Newest")]
    notes = [
        "Recalls counts every NHTSA safety campaign that applies to the year, make and model. It does not confirm the "
        "recall is still open on that exact car; a previous owner may have had it fixed.",
        "Before a car goes out: paste its VIN into NHTSA's free lookup at nhtsa.gov/recalls (up to 100 VINs at a time) or "
        "the manufacturer's VIN tool to see open vs. repaired. This sheet tells you which cars are worth that minute.",
        "Flags are NHTSA's own advisories on at least one campaign: DO NOT DRIVE (park it) and PARK OUTSIDE (fire risk).",
        "Refreshed weekly from NHTSA's public recall database. New campaigns appear as NHTSA posts them.",
    ]
    paths = write_all(rows, cols, HERE / "samples", title="Recall Exposure Sheet",
                      subtitle=f"Sample 20-car used lot. {exposed} of {len(rows)} vehicles have at least one applicable "
                               f"safety recall ({total} campaigns in all); {flagged} carry a do-not-drive or park-outside "
                               f"advisory. Data pulled {date.today().isoformat()}.",
                      notes=notes, source_line="Source: NHTSA Recalls API and vPIC VIN decoder (public domain). Not affiliated with NHTSA.",
                      basename="recall_exposure_sheet",
                      # Landscape Letter, 712pt usable. Cells wrap (core.pdfmini measures real Helvetica widths), so
                      # nothing overflows a column; widths sum to 712.
                      landscape=True,
                      pdf_widths=[34, 92, 96, 38, 54, 170, 100, 76, 52],
                      pdf_max_cell_lines=3,
                      kpis=[("vehicles", len(rows)), ("with recalls", exposed), ("campaigns", total), ("flagged", flagged)])
    print(f"rows={len(rows)} exposed={exposed} campaigns={total} flagged={flagged}")
    print("vpic", vpic.stats, "| recalls", rec.stats)
    for k, p in paths.items():
        print(k, p.relative_to(ROOT), p.stat().st_size, "bytes")
    return rows


if __name__ == "__main__":
    build()
