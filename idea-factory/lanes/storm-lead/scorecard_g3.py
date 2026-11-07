"""PROVISIONAL G3 score for Storm Lead, written before any outreach replies exist.
Re-run after Nick tallies replies in outreach/replies.md and adjust `demand`.

    python lanes/storm-lead/scorecard_g3.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.scoring import Score  # noqa: E402

P = "provisional, pending replies: "
s = Score(
    "storm-lead",
    demand=3,
    repeat_use=3,
    competition=2,
    license=5,
    build_effort=5,
    reasons={
        "demand": P + "no replies yet (0 of 20 emails sent). Roofers demonstrably pay for storm data (HailWatch "
                      "$65-119/mo, Hail Drive $30/mo, GAF WeatherHub $349-649/yr, AnythingWeather $179-189 per storm "
                      "map), so the category has demand; whether a plain SPC-report digest earns $50-100/mo is unproven.",
        "repeat_use": P + "the backtest says alerts fire about 5-14 mornings a month in Mar-Sep and essentially never "
                          "Nov-Feb. A monthly subscription has to survive 4 silent months; season pricing or an annual "
                          "plan would fit better than a flat monthly fee.",
        "competition": P + "crowded. HailTrace, Interactive Hail Maps/Hail Recon, CoreLogic, GAF WeatherHub, Beacon Storm+ "
                           "(free for PRO+ customers), HailWatch, Hail Drive, plus free apps (Hail Yeah) and free state "
                           "swath emails (LiveHailReports) that already plot the same SPC reports. Incumbents also sell "
                           "radar-derived swaths and address-level reports, which this product cannot match from public data. "
                           "Only edge: Michigan-only focus, ZIP list in the inbox, low price.",
        "license": "NOAA SPC reports, NWS API, OpenFEMA and Census gazetteer are all US Government public domain; "
                   "commercial use is clearly fine with attribution.",
        "build_effort": "refresh.py already produces the alert from live data in one call; shipping is a daily scheduled "
                        "run plus email delivery and a Stripe page. Days, not weeks.",
    },
    merge_with=["weather-trigger-jobs"],
    decision="PARK",
    decision_reason="PROVISIONAL. On paper 18/25 would be GO, but the demand score is a placeholder until Nick sends "
                    "the 20 outreach emails and tallies replies, and the market is crowded with free lookalikes. "
                    "Re-score then; consider merging with weather-trigger-jobs (lane 7).",
)
print(s.save(), s.total, s.decision, s.decision_reason)
