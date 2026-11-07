"""G3 scoring for great-lakes-conditions. PROVISIONAL until data/keyword_volumes.csv is filled in.

Run from repo root: python lanes/great-lakes-conditions/g3_score.py
When Nick's volumes arrive: run load_volumes.py, set DEMAND below to its suggested score, set PROVISIONAL = False,
re-run, and finish G3 with the decision this prints.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.scoring import Score  # noqa: E402

PROVISIONAL = True
DEMAND = 3  # guess; replace with load_volumes.py suggestion

P = "provisional, pending keyword volumes. "
s = Score(
    "great-lakes-conditions",
    demand=DEMAND, repeat_use=4, competition=3, license=5, build_effort=4,
    reasons={
        "demand": P + "No volume numbers yet. Indirect signals: Holland State Park is Michigan's busiest state park; "
                  "local TV writes a wave/red-flag story every windy summer weekend; single-metric sites (lakemonster, "
                  "seatemperature.net, surf-forecast) exist because people search these phrases. Strong seasonality May-Oct.",
        "repeat_use": P + "Boaters, anglers, paddlers and beach-goers check conditions every outing, often daily in season; "
                      "water-level pages draw year-round interest. Winter traffic will be thin because buoys are out.",
        "competition": P + "Incumbents are strong domains but weak pages: NWS raw text, Wunderground/Weather Network "
                       "(no waves or water level), windy.app and surf-forecast (model only), content farms. No one combines "
                       "observed + forecast + temp vs normal + level vs normal + advisories per harbor. Ranking against "
                       "weather.gov and TV sites is the risk.",
        "license": "Everything on the page is US-government public domain (NDBC, CO-OPS, NWS, GLERL), no keys, verified "
                   "by live fetches at G0. GLOS (terms unknown) and Open-Meteo (non-commercial) are not used.",
        "build_effort": "core.fetch already pulls all five feeds; refresh.py builds one page. Remaining: a table of "
                        "~60-100 Michigan locations mapped to nearest buoy/shore station/gauge/zone, a static-site loop, "
                        "hourly scheduling, hosting. Roughly 1-2 weeks of work.",
    },
    merge_with=["river-levels"],
)
if PROVISIONAL:
    rule_decision, rule_reason = s.decide()
    s.decision = "PARK"
    s.decision_reason = (f"PROVISIONAL. By the scoring rule this would be {rule_decision} ({rule_reason}) but the demand "
                         "score is a guess until Nick runs the 40 queries through Keyword Planner. Parked as waiting_nick.")
p = s.save()
print(json.dumps(json.loads(p.read_text(encoding="utf-8")), indent=1))
