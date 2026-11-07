# Portfolio board

_Regenerated 2026-11-06 11:13 UTC by `python -m core.board`. Slots: 4/4 active. Lanes with folders: 11. Queued without a folder: 13._

Gates: G0 data check, G1 sample, G2 demand test, G3 decision, PLAN build plan awaiting approval.

| # | Lane | Type | Gate | Status | Blocker | Next step | Last update |
|---|---|---|---|---|---|---|---|
| 1 | [Permit Radar](../lanes/permit-radar/LANE.md) | revenue | G2 | **waiting_nick** | Pipeline re-checked 2026-11-01 at Nick's request (all OK); Nick to send the 20 outreach messages or say what else to confirm. Detroit commercial-use answer still pending. | Tally replies, re-score license when Detroit answers, final G3 | 2026-11-02 00:01 |
| 2 | [Storm Lead](../lanes/storm-lead/LANE.md) | revenue | G3 | **waiting_nick** | Pipeline re-checked 2026-11-01 at Nick's request (all OK); Nick to send the 20 outreach forms or wait for spring (no MI storm days Nov-Feb in the backtest). | Tally replies, then final G3 | 2026-11-02 00:01 |
| 3 | [Great Lakes Conditions](../lanes/great-lakes-conditions/LANE.md) | traffic | G3 | **parked** |  | resume from FROM_NICK 2026-10-24 08:29 (DONE): Optional 10-minute sanity check | 2026-10-24 12:37 |
| 4 | [Recall Checks for Used-Car Dealers](../lanes/recall-checks/LANE.md) | revenue | G3 | **waiting_nick** | Outreach sent to 19 of 20 dealers (Oct 24-25). Waiting for replies; re-score G3 with real demand once replies are tallied or after 10 days of silence (Nov 4). | Wait for dealer replies (sent Oct 24-25). Re-score G3 by Nov 4 with the reply tally; silence counts as demand 1-2. | 2026-10-25 22:16 |
| 5 | [Contract-Winner Intel (BidRadar add-on)](../lanes/contract-winner-intel/LANE.md) | revenue | G2 | **active** |  | G2 demand test | 2026-10-31 11:06 |
| 6 | [Benchmarking Compliance Backend](../lanes/benchmarking-backend/LANE.md) | revenue | G0 | **waiting_nick** | Nick to create the free Portfolio Manager TEST account and store test credentials as environment secrets (or park). License resolved 2026-11-01: commercial use OK. | On Done: pass G0 with a real test-API call, then G1 prototype against /wstest/ | 2026-11-02 00:01 |
| 7 | [Weather-Trigger Job Alerts](../lanes/weather-trigger-jobs/LANE.md) | revenue | G3 | **parked** |  | Parked at G3 (17/25, demand evidence absent). Fold the forecast go/no-go view into storm-lead if that lane reaches GO. | 2026-11-02 00:01 |
| 8 | [Site-Selection Reports](../lanes/site-selection/LANE.md) | revenue | G2 | **active** |  | G2 | 2026-10-31 11:06 |
| 9 | [Satellite Change Alerts](../lanes/satellite-change/LANE.md) | revenue | G1 | **active** |  | G1 prototype | 2026-10-26 11:07 |
| 10 | [Filing Alerts (SEC EDGAR)](../lanes/filing-alerts/LANE.md) | revenue | G2 | **waiting_nick** | Nick to pick the buyer segment for Michigan 8-K alerts (no verified target list) | Draft outreach or run keyword test per Nick's answer | 2026-11-05 11:16 |
| 11 | [Supplier News Monitor](../lanes/supplier-news/LANE.md) | revenue | G1 | **active** |  | G1 prototype | 2026-11-02 11:27 |
| 12 | Energy Cost by Area Pages | traffic | - | queued | | waiting for a free slot | |
| 13 | River Levels for Paddlers | traffic | - | queued | | waiting for a free slot | |
| 14 | Air-Quality Alerts for Schools and Youth Sports | traffic | - | queued | | waiting for a free slot | |
| 15 | Food and Drug Recall Alerts | traffic | - | queued | | waiting for a free slot | |
| 16 | Rare-Bird Alerts | traffic | - | queued | | waiting for a free slot | |
| 17 | EV Road-Trip Planner | traffic | - | queued | | waiting for a free slot | |
| 18 | Next-Bus Lobby Displays | revenue | - | queued | | waiting for a free slot | |
| 19 | Michigan Spirits Price Watch | revenue | - | queued | | waiting for a free slot | |
| 20 | Michigan Site Contamination Check | revenue | - | queued | | waiting for a free slot | |
| 21 | Recall Check for Kids' Resale Shops | revenue | - | queued | | waiting for a free slot | |
| 22 | New Liquor License Leads MI | revenue | - | queued | | waiting for a free slot | |
| 23 | Michigan Road Construction Pages | traffic | - | queued | | waiting for a free slot | |
| 24 | Michigan Section 8 Rent Limits by ZIP | traffic | - | queued | | waiting for a free slot | |

## Gate timing (hours of wall-clock per gate, from lane.json)

| Lane | G0 | G1 | G2 | G3 | PLAN |
|---|---|---|---|---|---|
| permit-radar | 0.08 | 0.09 | 0.18 |  |  |
| storm-lead | 0.21 | 0.03 | 0.0 |  |  |
| great-lakes-conditions | 0.08 | 0.04 | 0.05 | 6.91 |  |
| recall-checks | 0.07 | 0.08 | 0.0 |  |  |
| contract-winner-intel | 0.01 | 0.0 |  |  |  |
| benchmarking-backend |  |  |  |  |  |
| weather-trigger-jobs | 0.01 | 0.04 | 0.0 | 0.01 |  |
| site-selection | 24.05 | 0.0 |  |  |  |
| satellite-change | 0.0 |  |  |  |  |
| filing-alerts | 0.01 | 0.15 |  |  |  |
| supplier-news | 0.07 |  |  |  |  |

## Slot rules

- At most 4 lanes `active` at once. `waiting_nick`, `parked`, `killed`, `go` do not hold a slot.
- The daily tick promotes the lowest-numbered queued lane into a free slot.
- Merge candidates are flagged at G3 (see SCORECARD.md).
