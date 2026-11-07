"""PROVISIONAL G3 score for permit-radar (written 2026-10-24 before any outreach replies).
Re-run after replies are tallied in outreach/replies.md, adjusting demand (and license if Nick gets
written confirmation from the Detroit open data team). Run from repo root: python lanes/permit-radar/g3_score.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.scoring import Score  # noqa: E402

s = Score(
    "permit-radar",
    demand=3,
    repeat_use=5,
    competition=3,
    license=3,
    build_effort=5,
    reasons={
        "demand": "PROVISIONAL, pending replies (0 of 20 emails sent as of 2026-10-24). Market signals only: paid permit-lead "
                  "products exist and charge $15-$149/month (Permit Ledger $14.99, Construction Monitor ~$96/mo historic, "
                  "PermitGrab $149), so trades do pay for permit lists; Detroit alone issues ~465 trades + ~100 building permits "
                  "a week. No Detroit-specific buyer has said yes yet.",
        "repeat_use": "Weekly list is subscription-shaped by nature; permits renew every week and the sheet is only useful fresh.",
        "competition": "National players (Construction Monitor, BuildZoom, Dodge, ConstructConnect, PermitGrab, Permit Ledger, "
                       "Apify permit scrapers) cover permits generically; none found that is Detroit-specific or trade-tagged for "
                       "small shops. But the data is free and the moat is thin: anyone can rebuild it.",
        "license": "Detroit Open Data Portal policy (Exec. Order 2015-2) says data may be redistributed and re-used by business, and "
                   "the datasets are public with no per-dataset license. BUT detroitmi.gov/Privacy, linked from the portal footer, "
                   "says commercial use is prohibited without written permission. Scored 3 until Nick gets written confirmation "
                   "from the ODP team (see needs_nick.md); would be 4-5 with it, 1 without.",
        "build_effort": "refresh.py already produces the weekly CSV/HTML/PDF from core in one run; remaining work is a mailing "
                        "list, Stripe/Lemon Squeezy checkout and a Monday cron. Days, not weeks.",
    },
    merge_with=[],
)
p = s.save()
print(f"{s.decision}: {s.decision_reason} -> {p}")
