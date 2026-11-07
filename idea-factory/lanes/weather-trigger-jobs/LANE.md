# Weather-Trigger Job Alerts

**Type:** revenue  |  **Queue order:** 7

Alerts for roofers, landscapers and venues from the NWS API. May merge with Storm Lead.

## Current state

(see lane.json; board regenerates ops/STATUS.md)

## G0 Data check

**Result: PASS** (2026-10-25 tick).

Through core.fetch (source `nws_api`, already in core registry): `api.weather.gov/alerts/active?area=MI` HTTP 200, 3 active alerts, updated 2026-10-25T11:00Z. `points/42.4895,-83.1446` resolved to grid DTX/62,41 and the hourly forecast returned temperature, precipitation probability, wind, humidity, short forecast.

**License:** US Government work, public domain, commercial OK; attribution "Source: National Weather Service". Needs descriptive User-Agent (core sets it). No lane-specific source to register.

**Update frequency:** alerts real time, hourly forecast refreshed about hourly. Fits a morning "trigger" alert.

**Overlap:** storm-lead already uses NWS/SPC for roofers. Any G3 for this lane must name `--merge-with storm-lead`; the new part would be forecast triggers for landscapers/venues (e.g. rain/frost/wind thresholds), which is forecast data and less precise than observed storm reports.

## G1 Prototype

**Result: PASS** (2026-10-28 tick). Interactive app in `app/`, `python -m core.webapp check weather-trigger-jobs` prints OK.

What it is: a go / risky / hold map for Michigan. Pick a trade (roofing, landscaping, outdoor events) and one of the next 7 days; 8 city points (Detroit, Grand Rapids, Lansing, Flint, Ann Arbor, Kalamazoo, Traverse City, Marquette) turn green/amber/red from NWS hourly forecasts checked over the trade's working window (rain chance, wind, temperature/frost). Each city lists the reason it tripped; live NWS alerts sit underneath. Phone-first, both themes, installable, Leaflet 1.9.4 over inlined Census boundaries (no tile server).

`refresh.py` writes `app/data/forecast.json`, `warnings.json`, boundaries, and the CSV/HTML/PDF outlook in `samples/` (the outreach attachment), so the daily tick keeps it live.

**What the data cannot do:** it is forecast, not observation; only 8 city points, not a statewide grid or a customer's job site; thresholds are my rule-of-thumb starting values, not trade-validated (roofers/landscapers should set their own); no notifications or user thresholds yet (those are launch work). Real overlap with storm-lead (same NWS source, same roofer buyer); the new angle is forward-looking scheduling for landscapers and venues. Any G3 must name `--merge-with storm-lead`.
Browser check: headless Chromium at phone width loaded data and rendered with no JS errors; the Leaflet CDN could not be confirmed from the sandbox.

## G2 Demand test

_pending_

## G3 Decision

_pending_

## G3 final (2026-11-01)

Acted on FROM_NICK 2026-11-01 18:22 (entry 29f393640d20): Nick SKIPPED the 14-form outreach with no notes. Per CLAUDE.md rule 8 the demand evidence is treated as absent and the lane is not re-asked. Final score via `core.scoring`: demand 2 (no outreach, no replies, no volumes), repeat use 4, competition 2 (free NWS forecasts and weather apps already serve every target; trade-specific thresholds are the only wedge), license 5 (NWS public domain), build effort 4 (prototype exists). Total 17/25 -> PARK, merge candidate storm-lead: if Storm Lead reaches GO, its build plan should fold in this lane's forecast go/no-go view for roofers; the landscaper, paving and venue angle is parked until there is demand evidence.

## Log
- 2026-10-24 tick: promoted; G0 blocked by network policy on api.weather.gov. Nothing fabricated.
- 2026-10-25T11:03:58+00:00 G0 started. data check
- 2026-10-25 tick: G0 PASS (NWS alerts + hourly forecast work). Overlaps storm-lead. Next: G1.
- 2026-10-25T11:04:39+00:00 G0 finished: pass. NWS alerts and hourly forecast work, public domain
- 2026-10-28T11:05:37+00:00 G1 started. forecast-trigger web app prototype
- 2026-10-28 tick: G1 PASS. Built forecast go/no-go web app + refresh.py + sample. Next: G2 demand test (landscapers/venues; roofers overlap storm-lead).
- 2026-10-28T11:07:54+00:00 G1 finished: pass. go/risky/hold map app on live NWS hourly forecasts, 8 cities, 3 trades
- 2026-10-29T11:08:47+00:00 G2 started. outreach pack: landscapers, paving, tent/venue businesses

### G2 outreach pack (2026-10-29 tick)
14 targets from public listings (6 landscapers, 3 paving/sealcoat, 3 tent rental, 2 outdoor venues), written by `g2_outreach.py` via core.outreach; drafts in `outreach/emails.md`, send sheet in `outreach/send_sheet.md`. Honest limits: 6 of the 14 links are directory listings, not company sites, and no emails were found, so every send is a web form. Nothing sent. Weak spot of the idea: a free NWS forecast app already exists for every one of these buyers, so replies must show they would want trade-specific thresholds. Provisional G3 (merge-with storm-lead) next tick or after replies.
- 2026-10-29 tick: G2 outreach pack built (14 targets), waiting on Nick to send.
- 2026-10-29T11:09:00+00:00 G2 finished: pass. 14 targets, outreach pack and send sheet written
- 2026-10-29T11:09:00+00:00 status -> waiting_nick. blocker: Nick must send 14 outreach forms (outreach/send_sheet.md). next: tally replies, final G3 merge-with storm-lead
- 2026-11-01T23:55:34+00:00 FROM_NICK 2026-11-01 18:22 (SKIPPED, entry 29f393640d20): "Send G2 outreach". Box ticked: yes. Filed: from_nick/2026-11-01_1822_29f393640d20.md. Notes: (none) Lane set back to active: no open Nick items left. Tick agent: continue this lane from these notes.
- 2026-11-02T00:01:32+00:00 G3 finished: pass. PARK 17/25 final (demand evidence absent); merge candidate storm-lead
- 2026-11-02T00:01:32+00:00 status -> parked. blocker: . next: Parked at G3 (17/25, demand evidence absent). Fold the forecast go/no-go view into storm-lead if that lane reaches GO.
