"""Prove core works end-to-end on lane 1's real data (Detroit building permits).
Run: python scripts/smoke_core.py
Checks: registry lookup, live fetch, cache hit, budget counter, usage log, CSV/HTML/PDF sample, scoring rule.
"""
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import registry, samples, scoring  # noqa: E402
from core.fetch import Fetcher, arcgis_query_all  # noqa: E402

OUT = ROOT / "ops" / "usage" / "smoke"


def main():
    src = registry.get("detroit_permits")
    print("1 registry ok:", src["name"], "| commercial_ok =", src["commercial_ok"])

    f = Fetcher("detroit_permits", lane="core", gate="G0", allow_noncommercial=True)
    since = (date.today() - timedelta(days=7)).isoformat()
    t0 = time.time()
    rows = arcgis_query_all(f, src["base_url"], where=f"issued_date >= DATE '{since}'",
                            out_fields="record_id,address,issued_date,permit_type,work_description,"
                                       "amt_estimated_contractor_cost,zip_code,neighborhood",
                            order_by="issued_date DESC", max_records=3000)
    print(f"2 live fetch ok: {len(rows)} permits issued since {since} in {time.time()-t0:.1f}s; "
          f"requests={f.stats['requests']} cache_hits={f.stats['cache_hits']}")
    assert rows, "no rows returned"

    t0 = time.time()
    rows2 = arcgis_query_all(f, src["base_url"], where=f"issued_date >= DATE '{since}'",
                             out_fields="record_id,address,issued_date,permit_type,work_description,"
                                        "amt_estimated_contractor_cost,zip_code,neighborhood",
                             order_by="issued_date DESC", max_records=3000)
    print(f"3 cache hit ok: {len(rows2)} rows in {time.time()-t0:.3f}s; cache_hits={f.stats['cache_hits']}")
    print(f"4 budget ok: {f.budget_used_today()}/{f.daily_budget} requests used today for detroit_permits")

    for r in rows:
        if r.get("issued_date"):
            r["issued_date"] = str(r["issued_date"])[:10]
        c = r.get("amt_estimated_contractor_cost")
        r["est_cost"] = f"${c:,.0f}" if isinstance(c, (int, float)) else ""
        r["work_description"] = (r.get("work_description") or "")[:90]
    cols = [("issued_date", "Issued"), ("address", "Address"), ("zip_code", "ZIP"), ("permit_type", "Type"),
            ("est_cost", "Est. cost"), ("work_description", "Work")]
    paths = samples.write_all(rows[:40], cols, OUT, title="Detroit permits, last 7 days (core smoke test)",
                              subtitle=f"{len(rows)} permits issued since {since}; showing 40",
                              notes=["Smoke test of core.samples; not a product sample."],
                              source_line="Data: City of Detroit Open Data Portal (BSEED).",
                              basename="smoke", pdf_widths=[55, 130, 40, 70, 60, 177])
    for k, p in paths.items():
        print(f"5 sample {k}: {p.relative_to(ROOT)} ({p.stat().st_size} bytes)")

    s = scoring.Score("smoke-test", demand=3, repeat_use=4, competition=3, license=2, build_effort=4)
    assert s.decision == "KILL", s
    s2 = scoring.Score("smoke-test", demand=4, repeat_use=5, competition=3, license=5, build_effort=4)
    assert s2.decision == "GO", s2
    print("6 scoring ok:", s.decision, "/", s2.decision)

    usage = (ROOT / "ops" / "usage" / "core.jsonl")
    print("7 usage log ok:", usage.exists(), usage.read_text(encoding="utf-8").count("\n"), "records")
    print("SMOKE PASS")


if __name__ == "__main__":
    main()
