# Contract-Winner Intel (BidRadar add-on)

**Type:** revenue  |  **Queue order:** 5

Who won what, as a BidRadar add-on. Source: USAspending API.

## Current state

(see lane.json; board regenerates ops/STATUS.md)

## G0 Data check

**Result: PASS** (2026-10-25 tick).

Real POST to `https://api.usaspending.gov/api/v2/search/spending_by_award/` (contract award types A-D, place of performance Michigan, Aug-Oct 2026 window) through core.fetch returned HTTP 200 with award ID, recipient name, amount, awarding agency, start date and description. `references/toptier_agencies/` also 200. No key needed.

**License:** US Government open data, public domain, commercial use fine; attribution "Source: USAspending.gov". Registered in `lanes/contract-winner-intel/sources.json`.

**Update frequency:** daily, but agency submissions lag (days to months), so "who won" is accurate on a lag, not same-day. Fits a weekly digest, not breaking alerts.

**Caveats found:** the date filter applies to the action date, so the first sample query still surfaced very large old awards sorted by total amount; G1 must sort by recent action date. Individual recipients are masked and must be excluded (rule 4); recipients here are businesses only.

## G1 Prototype

**Result: PASS (2026-10-26 tick).** Web app in `app/` (Contract Winners): KPIs, Michigan county map shaded by dollars (Leaflet 1.9.4 over inlined county GeoJSON, tap a county to filter), top winners and agencies bars, searchable awards list with agency/county/new-vs-modified filters, phone-first, both themes, installable. `refresh.py` pulls the last 90 days of federal contract awards (types A-D) with Michigan place of performance, 200 rows, and rewrites `app/data/latest.json` plus the outreach sample `samples/winners_digest.{csv,html,pdf}` each tick. `python -m core.webapp check contract-winner-intel` prints OK; headless phone render shows 40 award cards and no JS errors.

What the data can and cannot do: Award Amount is the total obligated to date, not the new money. Agencies report with a lag. Place-of-performance ZIP is sometimes the vendor office rather than the job site (a Coast Guard repair job in South Carolina is coded to a Michigan ZIP). Only 10 counties show awards in the 200-row cap, so the map is a sample, not the full state; paging further is the first thing to fix. All recipients were organizations; names not looking like organizations are dropped by rule 4. This is a BidRadar add-on, so the real test is whether bid-watchers want winner intel, which G2 must ask.

## G2 Demand test

**Not started (2026-10-27 tick); two blockers found, nothing fabricated.**
1. The current 200-row refresh is useless for picking targets: one vendor (Wright Tool Company) holds 195 of the 200 rows and only 4 distinct recipients appear, so there is no list of real Michigan small-business winners to approach. Next tick: page the USAspending query (and cap rows per recipient) so the app and sample show a spread of winners.
2. Target audience is bid-watching small contractors; two web searches today found no verifiable business contacts (only PTAC and SBA background pages). G2 needs 10-20 verified public business listings (company sites) before drafting via core.outreach. Candidate channel: Michigan PTAC counselors, who work with exactly these firms; Nick may know one to ask.

## G3 Decision

_pending_

## Log
- 2026-10-24 tick: promoted; G0 blocked by network policy on api.usaspending.gov. Nothing fabricated.
- 2026-10-25T11:03:58+00:00 G0 started. data check
- 2026-10-25 tick: G0 PASS (USAspending POST works, public domain). Next: G1 sample.
- 2026-10-25T11:04:39+00:00 G0 finished: pass. USAspending POST works, public domain
- 2026-10-26T11:09:38+00:00 G1 started. prototype web app

- 2026-10-26 tick: G1 prototype built and passes webapp check; outreach digest sample written.
- 2026-10-26T11:09:38+00:00 G1 finished: pass. web app on live USAspending data, map + filters, webapp check OK
- 2026-10-26T11:09:38+00:00 status -> active. blocker: . next: G2 demand test

- 2026-10-27 tick: G2 not started; data spread too thin (4 recipients) and no verified target list yet. Plan above.
- 2026-10-29 tick: G2 still blocked (refresh needs paging and a per-recipient cap; no verified target list). Not started; tick time went to weather-trigger-jobs G2.
- 2026-10-31T11:06:16+00:00 status -> active. blocker: . next: G2 demand test
- 2026-10-31 tick: refresh unchanged, but today's 200 rows now cover ~190 distinct winners (the earlier single-vendor skew is gone, so the paging fix is no longer urgent). G2 still needs a verified target list. Not advanced.
