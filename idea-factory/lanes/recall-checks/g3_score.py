"""G3 (PROVISIONAL): score the lane before outreach replies exist. Mirrors the 2026-10-24 re-score done with
`python -m core.scoring recall-checks ... --provisional` after Nick kept the smaller product (free NHTSA data,
no paid VIN-level deal; FROM_NICK 2026-10-24 07:45, entry 881601993108). Re-run with real numbers, and without
provisional=True, once Nick has tallied replies in lanes/recall-checks/outreach/replies.md.
Run from repo root: python lanes/recall-checks/g3_score.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.scoring import Score  # noqa: E402

P = "PROVISIONAL, pending replies: "

s = Score(
    "recall-checks",
    demand=2,
    repeat_use=4,
    competition=2,
    license=5,
    build_effort=5,
    provisional=True,
    reasons={
        "demand": P + "0 of 19 outreach drafts sent yet (Nick decided 2026-10-24 to keep the free NHTSA exposure sheet, "
                      "so the pitch is final). Pain is real (state AGs have forced CarMax and 100+ NY dealers to disclose "
                      "open recalls; a federal used-car recall bill was reintroduced Sept 2025) but Michigan has no "
                      "disclosure law, and NHTSA already gives dealers a free 100-VIN batch lookup, so urgency for a small "
                      "independent lot is unproven. Raise to 3-4 if 3+ of 19 reply yes/maybe.",
        "repeat_use": P + "Subscription-shaped: inventory turns every few weeks and NHTSA posts new campaigns daily, so a "
                          "weekly sheet stays useful. Capped at 4 because the free NHTSA tool covers the same need for a "
                          "patient dealer.",
        "competition": P + "Crowded and the incumbents have the better data. Carfax gives its dealer subscribers recall "
                           "monitoring on inventory; AutoCheck sells an Open Recall Inventory Check; Recall Masters and AutoAp "
                           "sell daily VIN-level recall management (true open/closed status, which free NHTSA data cannot "
                           "give); NHTSA's own site checks 100 VINs at a time for free. Nick's positioning (2026-10-24): we "
                           "are not buying VIN-level data; the product is free-data, simpler and cheaper than Carfax/AutoAp, "
                           "and can be offered free if that is what wins the first lots. That is an edge on price and "
                           "simplicity, not on data, so the score stays 2.",
        "license": "NHTSA vPIC, Recalls API and ODI flat files are US Government works (public domain), no key, no terms "
                   "restricting commercial use found on nhtsa.gov. Verified at G0 with live requests. No paid data deal, so "
                   "no third-party license enters the product.",
        "build_effort": P + "Nick fixed the product on 2026-10-24 as the smaller exposure sheet that refresh.py already "
                            "produces from core (CSV/HTML/landscape PDF). Remaining work is inventory intake (CSV/email), "
                            "flat-file ingest to dodge the API 400s, per-dealer scheduling and delivery: a few days. No "
                            "VIN-level integration to build, so this rises from 4 to 5.",
    },
    merge_with=[],
)
p = s.save()
print(s.decision, s.total, "/25 ->", p.relative_to(ROOT))
print(s.decision_reason)
