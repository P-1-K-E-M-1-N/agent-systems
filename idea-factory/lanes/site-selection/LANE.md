# Site-Selection Reports

**Type:** revenue  |  **Queue order:** 8

Reports for new shop owners from the Census API.

## Current state

(see lane.json; board regenerates ops/STATUS.md)

## G0 Data check

**Result: PASS (2026-10-26 tick), acting on FROM_NICK 2026-10-25 19:49 (entry 3de85326530d). Earlier 2026-10-25 result was BLOCKED on the missing key; history kept below.**

With Nick's CENSUS_API_KEY, real requests through core.fetch.Fetcher succeeded: ACS5 2023 ZCTA 48067 (pop 24,496, median household income $107,355), ACS5 county Oakland MI (pop 1,272,294), and County Business Patterns 2022 NAICS 7225 Oakland County (2,582 establishments, 44,856 employees). License: public domain, commercial use OK, attribution registered. Frequency: annual, fits a report product. Limits: aggregates only, annual lag, CBP suppresses small cells; no individual-level data.

(2026-10-25 note:)

`api.census.gov` is now reachable, and the metadata endpoint (`/data/2023/acs/acs5.json`) returns 200. But every data query (ACS5 ZCTA, county; CBP) is redirected to `missing_key.html` (header `X-DataWebAPI-KeyError: 1`). Keyless access is not working from this environment, so the endpoint cannot be shown to return data. Nothing fabricated.

**License:** still fine (public domain, attribution line registered). The only gap is the free API key. Signing up is Nick's job (rule 2); request is in `needs_nick.md`. Free, instant by email. Lane parked as waiting_nick; once the key is in env var `CENSUS_API_KEY` and the source gets `key_env`/`key_param=key`, G0 can be finished next tick.

## G1 Prototype

**Result: PASS (2026-10-31 tick).** Web app in `app/` (Site Check): pick one of 8 business types (restaurants, personal care, auto repair, grocery, dry cleaning, gyms, doctors, dentists) and a Michigan ZIP; get residents, median income and age for that ZIP, an estimated shop count, and a plain verdict comparing the county's residents-per-shop to the typical Michigan county. Leaflet 1.9.4 map shades all 83 counties by residents per shop; tap a county for its report; top-5 "most room" and "most crowded" lists. Phone first, both themes, installable, opens on ZIP 48067 so it is complete at rest. `refresh.py` pulls ACS 5-year 2023 (991 Michigan ZCTAs, 83 counties) and County Business Patterns 2022 (565 county-type cells) with the free key and rewrites `app/data/latest.json` plus the outreach sample `samples/site_check.{csv,html,pdf}`. `python -m core.webapp check site-selection` prints OK; headless 390px render shows no JS errors.

What the data can and cannot do: there is no shop count by ZIP in this API, so the ZIP's shop count is an estimate (its share of county residents times county shops), and the app says so. CBP is 2022, annual, and hides small cells (shown as n/a, never guessed). Residents-per-shop is a screening number only; it ignores foot traffic, rent, tourists, commuters and chains. County ZIP assignment uses ZCTA centroids. Aggregates only, no people data. Demand is untested: G2 must ask whether new-shop owners / brokers / SBDC advisors would pay for this.

## G2 Demand test

_pending_

## G3 Decision

_pending_

## Log
- 2026-10-24 tick: promoted; G0 blocked by network policy on api.census.gov. Nothing fabricated.
- 2026-10-25T11:03:58+00:00 G0 started. data check
- 2026-10-25 tick: G0 blocked, Census data calls need free API key; asked Nick.
- 2026-10-25T11:04:39+00:00 status -> waiting_nick. blocker: Nick must get a free Census API key. next: Finish G0 once key is set
- 2026-10-26T11:05:53+00:00 FROM_NICK 2026-10-25 19:49 (DONE, entry 3de85326530d): "Get a free Census API key". Box ticked: yes. Filed: from_nick/2026-10-25_1949_3de85326530d.md. Notes: Census API key obtained, activated and saved as CENSUS_API_KEY on the Default cloud environment (the one the daily tick runs in), 2026-10-25. Key not recorded anywhere in the repo. Note for the factory: the step-3 link claude.ai/code/environments is a dead page; the environment is edited from the selector under the message box on the new-session screen at claude.ai/code. Lane set back to active: no open Nick items left. Tick agent: continue this lane from these notes.
- 2026-10-26T11:06:56+00:00 G0 finished: pass. Census ACS5 + CBP return real data with free key; public domain, annual
- 2026-10-26T11:06:56+00:00 G1 started. next tick: prototype
- 2026-10-26T11:06:56+00:00 status -> active. blocker: . next: G1 prototype (web app: ZIP site report)
- 2026-10-31T11:06:16+00:00 G1 started. prototype web app
- 2026-10-31 tick: G1 prototype built (Site Check web app on live Census data), check OK; outreach sample written. Next: G2.
- 2026-10-31T11:06:16+00:00 G1 finished: pass. web app on live ACS+CBP data, county map + ZIP report, webapp check OK
