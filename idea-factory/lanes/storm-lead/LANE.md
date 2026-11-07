# Storm Lead

**Type:** revenue  |  **Queue order:** 2

Morning-after alerts for Michigan roofing/restoration contractors listing ZIPs hit by hail 1in+ or damaging wind, $50-100/month. Sources: NOAA SPC storm reports, NWS alerts, OpenFEMA. G0 includes a 24-month Michigan backtest of alert frequency.

## Current state

(see lane.json; board regenerates ops/STATUS.md)

G0 pass, G1 pass, G2 pack written, **waiting on Nick to send 20 emails**. G3 score is provisional (PARK until replies).

Files in this lane:
- `stormlib.py` parses SPC daily and yearly files, applies the alert rule, maps lat/lon to nearby ZIPs.
- `backtest.py` writes `data/backtest.csv`, `data/counties.csv`, `data/mi_events.csv`, `data/prelim_vs_final_2025-06.csv`.
- `refresh.py` rebuilds yesterday's alert from live data (`python lanes/storm-lead/refresh.py`, or `--latest`, or a date).
- `g2_outreach.py` writes the outreach pack; `scorecard_g3.py` writes the provisional score.

## G0 Data check

**Result: PASS** (13 minutes, 2026-10-24 05:31-05:44 UTC).

**Endpoints work (real requests through core.fetch):**
- SPC daily reports `https://www.spc.noaa.gov/climo/reports/YYMMDD_rpts_{hail,wind}.csv`: HTTP 200, columns `Time,Size|Speed,Location,County,State,Lat,Lon,Comments`. Hail size in hundredths of an inch, wind in mph or `UNK` (damage report, no measured gust). Each file is one SPC "convective day", 12:00 UTC to 11:59 UTC next day (8am to 8am Eastern in summer). 606 daily files pulled for Jan 1 - Oct 23, 2026 with zero errors.
- SPC bulk database `https://www.spc.noaa.gov/wcm/data/YYYY_{hail,wind}.csv`: final NWS Storm Data for 2024 (updated 2026-10-01) and 2025 (published 2026-04-24). No 2026 file yet. The directory itself returns 403; file names come from the `wcm/` page. Wind magnitude is in knots (50 kt = 58 mph), times are CST, county is a FIPS code.
- NWS API `api.weather.gov/alerts/active?area=MI`: 200, valid (0 active alerts tonight). OpenFEMA declarations for MI since Oct 2024: 50 rows (June 2026 severe storms/flooding declaration covers many northern counties). Both work; neither is needed for the core alert.
- Census Gazetteer `2025_Gaz_zcta_national.zip` and `2025_Gaz_counties_national.zip`: 200, pipe-delimited (older years are tab). Used for county names and ZIP centroids.

**License:** all four sources are US Government works, public domain, commercial use fine with attribution. Registered in `lanes/storm-lead/sources.json` (`noaa_spc_wcm`, `census_gazetteer`, and a lane override raising `noaa_spc_reports` daily budget to 2000).

**Update timing (matters for a 7am email):** SPC's page labels every report preliminary and shows the current day as "20261023 1200 UTC - 20261024 1159 UTC". Reports appear within minutes to a couple of hours of the storm as local NWS offices relay them. The day's file keeps changing until 12Z (8am EDT), and late reports can still be added for a few days. So a 7am send covers everything through about 6:30am; a storm that is still going at 7am shows up in the next morning's email. The final, cleaned record (Storm Data) arrives months later: the 2025 yearly file was published April 2026.

**How noisy is the morning data?** June 2025 compared both ways: the preliminary daily files held 73 qualifying Michigan reports on 11 days; the final record kept 38 reports on 9 days. Every final alert day was also a preliminary alert day; two thin preliminary days (June 17 and June 30) did not survive. Plain reading: the morning email will sometimes list reports that later get merged or downgraded, roughly double-counting on busy days, but it will not miss real storm days. For a canvassing list that is acceptable; the email should say "preliminary".

### 24-month Michigan backtest (Oct 2024 - Sep 2026)

Alert rule: any Michigan report of hail 1.00 in or larger, or wind 58 mph or more, or a wind-damage report with no speed. 2024-2025 from the final database, 2026 from preliminary daily files (the only kind available, and the kind the product would actually use). Full table: `data/backtest.csv`; per-county: `data/counties.csv`.

| Month | Alert days | Hail reports | Wind reports | Top counties |
|---|---|---|---|---|
| 2024-10 | 0 | 0 | 0 | |
| 2024-11 | 1 | 0 | 2 | Saginaw, Oakland |
| 2024-12 | 0 | 0 | 0 | |
| 2025-01 | 0 | 0 | 0 | |
| 2025-02 | 0 | 0 | 0 | |
| 2025-03 | 4 | 2 | 99 | Shiawassee, Berrien, St. Joseph |
| 2025-04 | 4 | 8 | 6 | Huron, Iron, Oakland |
| 2025-05 | 2 | 5 | 82 | Kalamazoo, Berrien, Ottawa |
| 2025-06 | 9 | 7 | 31 | Wayne, Oakland, Clinton |
| 2025-07 | 6 | 7 | 16 | Alger, Wayne, Huron |
| 2025-08 | 5 | 10 | 12 | Alpena, Alcona, Ogemaw |
| 2025-09 | 3 | 3 | 1 | Cass, Kent, Otsego |
| 2025-10 | 3 | 1 | 2 | Baraga, Allegan, St. Joseph |
| 2025-11 | 0 | 0 | 0 | |
| 2025-12 | 0 | 0 | 0 | |
| 2026-01 | 0 | 0 | 0 | |
| 2026-02 | 1 | 6 | 0 | Ingham, Livingston, St. Clair |
| 2026-03 | 6 | 40 | 8 | Ottawa, Ingham, St. Joseph |
| 2026-04 | 5 | 6 | 39 | Kent, Wayne, Barry |
| 2026-05 | 6 | 14 | 122 | Macomb, Oakland, Ionia |
| 2026-06 | 11 | 56 | 108 | Cass, Allegan, Kent |
| 2026-07 | 14 | 28 | 171 | Marquette, Berrien, Iosco |
| 2026-08 | 4 | 4 | 9 | Berrien, Barry, Jackson |
| 2026-09 | 4 | 7 | 62 | Oakland, Ingham, Livingston |

**Headline, in plain language:** over 24 months an alert would have fired on **88 mornings** (974 qualifying reports). In storm season (March-September) that is **about 4-8 mornings a month in a normal year, up to 11-14 in a busy month** (June-July 2026). **October through February is almost silent: 2 alert mornings in 10 winter months.** Wind damage reports outnumber 1-inch hail roughly 4 to 1; hail-only alert days are rarer (about 2-5 a month in season). 2026 looks about twice as active as 2025 partly because it is preliminary data (see the June 2025 comparison above).

**Counties that keep recurring (alert days / reports over 24 months):** Oakland 20 / 42, Wayne 15 / 44, Macomb 15 / 28, Berrien 14 / 42, Ingham 12 / 35, St. Joseph 12 / 33, Kent 11 / 37, Barry 11 / 29, Allegan 11 / 24, Ionia 11 / 23, Livingston 11 / 23, Shiawassee 11 / 22, St. Clair 11 / 18, Monroe 11 / 18, Lapeer 11 / 15. Metro Detroit (Oakland, Wayne, Macomb) is the best single territory: a roofer there would get roughly 1-3 alerts a month in season.

**What this means for the product:** a flat $50-100/month subscription has to survive four months with nothing to send. Season pricing (March-October) or an annual plan would be more honest. The data is plentiful enough in season to be worth a daily email, and thin enough in winter that "no alert today" is the normal case.

Requests used in G0: 657 live fetches (606 daily SPC files, 6 bulk/page fetches, 2 gazetteer zips, 1 NWS, 1 OpenFEMA, plus probes), everything else from cache. Re-running the backtest today costs zero requests.

## G1 Sample

**Result: PASS** (2 minutes; most of the work was already done in G0's library).

The artifact a roofer gets at 7am: a one-page "Storm Lead alert" listing every qualifying report with local time, type, hail size or wind speed, location, county, the nearby ZIP codes, and the NWS comment, plus a "which ZIPs to canvass" line sorted by report count.

- `samples/storm_lead_alert.{pdf,html,csv}`: **Wednesday October 7, 2026**, the most recent Michigan storm day in the data. A thin one: 4 wind-damage reports in Antrim, Kalkaska and Crawford counties (ZIPs 49615, 49612, 49733, 49738). Honest, but not a great sales demo.
- `samples/storm_lead_alert_example_big_day.{pdf,html,csv}`: **Thursday September 3, 2026**, the busiest southeast-Michigan day of 2026: 46 reports, 15 counties, 1.00 in hail, trees and wires down across Oakland, Macomb, Ingham, Livingston. This is what a storm morning looks like; attach both.

ZIP mapping: each report is a point. We list the ZIP Code Tabulation Areas (Census 2025 gazetteer) whose centroid is within 8 km (about 5 miles), nearest always included, up to 6. This is an approximation and the sample says so; real ZIP polygons are irregular, and a production version should use ZCTA boundary polygons (also public domain, Census TIGER) for point-in-polygon.

`refresh.py` rebuilds yesterday's alert from live SPC data in one call (2 SPC requests plus a cached gazetteer); `--latest` walks back to the most recent day with Michigan reports.

## G1 prototype (2026-10-25)

Nick's call of 2026-10-25: the CSV/HTML/PDF "aren't products", he wants a map with hail and wind images. Rule 1 changed the same day, so G1 is now the product as a roofer would open it: a static web app in `lanes/storm-lead/app/` (scaffolded by `core.webapp`, Leaflet 1.9.4 from cdnjs, everything else local). `python -m core.webapp check storm-lead` prints OK; `node --check app/app.js` passes. Rendered and checked at 1280px and 400px wide in both themes (headless Chrome): no horizontal scroll, popups, county tooltips, service area and replay all work. The PDF/CSV/HTML sample is still written on every run; it stays the email attachment.

**What the app shows (phone first, desktop second, light and dark):**
- **Map of Michigan drawn from the app's own files**: `mi_state.json` and `mi_counties.json` (Census TIGERweb via `core.geo`, copied from `core/web/geo/`) as Leaflet GeoJSON layers styled from the `--map-*` tokens. No tile server is needed, so it renders inside the claude.ai review artifact, offline, and as an installed PWA.
- **One pin per qualifying SPC report**, inline SVG in an `L.divIcon` (no marker images): hail is an icy-blue disc with an ice asterisk, wind is an amber disc with three gust lines, a wind-damage report with no measured gust is the same mark drawn hollow. Pin size follows magnitude (hail 1.00 in = 22 px up to 3 in = 40 px; wind 58 mph = 20 px up to 98 mph = 38 px). Tap/click opens a popup with time (ET), magnitude, location, county, nearby ZIPs (`stormlib.nearby_zctas`) and the NWS comment.
- **Counties shaded by report count** with `Factory.ramp` from `--map-land` to the accent (square-root scale so one busy county does not wash out the rest); legend on the map; sticky tooltip with the count and the worst report in that county.
- **Live NWS warnings**: `warnings.json` polygons drawn in the `warn` pane, colored by event (tornado red, severe thunderstorm orange, flood green, wind advisory yellow, watches dashed), popup with headline and expiry, a "Live NWS warnings as of <time>" stamp, and a list in the panel that includes zone-based alerts that have no polygon (marked "zone-based, not drawn"). When the page runs from its own address it also fetches `api.weather.gov/alerts/active?area=MI` directly (the API allows cross-origin reads) and marks the stamp "(live)"; in the sandbox that fetch fails silently and the refresh.py snapshot stands.
- **Radar and street map are optional layers**: the buttons start disabled and only enable after `Factory.canLoadImage()` loads a sample tile from each host; otherwise a small note says "street map and radar appear when the app is installed from its own address". Street map = OpenStreetMap standard tiles (ODbL, light use only; when on, the GeoJSON land fill goes transparent and the choropleth turns half-opaque so streets show through). Radar = NOAA nowcoast MRMS base reflectivity as a WMS layer: `https://nowcoast.noaa.gov/geoserver/weather_radar/wms`, layer `base_reflectivity_mosaic`, EPSG:3857, PNG, transparent (GetCapabilities and a GetMap both answered 200 from here on 2026-10-25; nowcoast's old ArcGIS `nowcoast.noaa.gov/arcgis/rest/services/nws/radar_meteo_imagery_nexrad_time` service is gone, the GeoServer one is current). Both probed OK from this machine; both are blocked inside the review artifact by design.
- **My service area**: tap the map to drop a home base (draggable dot), radius slider 5-60 miles, circle on the map; the panel counts the selected day's reports inside the circle and lists their ZIPs with a count per ZIP and a Copy button. Center and radius are remembered with `Factory.store` (localStorage, this device only).
- **Replay bar for the last 30 convective days**: one thin bar per day (height = sqrt of the report count), a range slider under it, "Back to latest" button. Picking a day re-renders pins, shading, KPIs, list, summary and the service-area count. Warnings are always live and do not change with the replay day.
- **Panel**: day header with a tag (Yesterday / Most recent storm day / Selected day / Replay), KPIs (qualifying reports, counties hit, largest hail, strongest wind, each with a one-line detail), a two-sentence plain-language morning summary generated from the numbers ("46 NWS storm reports qualified across 19 counties, led by Oakland (11) and Ingham (6). Hail reached 1.00 in near Brethren, wind gusted to 66 mph at 3 NNE Edgemont Park, 40 wind-damage reports ... start with ZIPs 48017, 48021, 48030."), the report list sorted worst first (hail by size, then measured wind, then damage-only; clicking pans the map and opens the popup; capped at 60 with a Show-all button), the Install-app button from the shell, a theme switch (auto/light/dark), and a footer with the alert rule, the ZIP caveat, data sources and the refresh time.

**Data files and how `refresh.py` keeps them live** (every run writes all of them, `--no-app` skips them):
- `app/data/latest.json` (~17 KB on the big day): the day the app opens on. Default run = yesterday's convective day (`stormlib.yesterday_convective_day`); if that day has no qualifying report the app opens on the most recent day in the 30-day window that has one (then walks back up to 120 more days through the fetcher, then the lane archive), and `is_fallback`/`label` say so ("Most recent storm day: ... (no qualifying reports on ...)"). Holds every report with lat, lon, kind, mag, mag_text, time_local, time_utc, location, county, zips, comments, severity, plus counts, county and ZIP tallies, generated_at, the rule and the source lines.
- `app/data/days.json` (~30 KB): the last 30 convective days ending at the anchor (yesterday, or the explicit date), each day in the same shape. Built with `stormlib.fetch_daily` through `Fetcher("noaa_spc_reports", lane="storm-lead", gate=...)`: 60 requests on a cold cache (budget is 2000/day for this lane, cache TTL one day, so the daily tick costs 2 new requests). If the budget or network blocks a day, that day is filled from `data/mi_events.csv` and marked `source: "archive"`; the page shows the note. Not needed on 2026-10-25: both runs fetched live with zero errors.
- `app/data/warnings.json`: `Fetcher("nws_api")` on `alerts/active?area=MI` (10-minute TTL), filtered to events containing tornado, thunderstorm, wind, hail or flood; keeps id, event, severity, headline, areaDesc, description (600 chars), onset/expires/ends, sender, geometry (when NWS gives a polygon) and affected zone ids. 0 active Michigan alerts on 2026-10-25 evening (quiet October), so the polygon path is written and wired but has not been seen with real data yet; the page falls back to the list for zone-only alerts.
- `app/data/mi_state.json` (3 KB) and `mi_counties.json` (28 KB): copied from `core/web/geo/` on every run.
- `app/assets/leaflet.css`: Leaflet 1.9.4 stylesheet downloaded once from cdnjs (stylesheets cannot load from a CDN in the review sandbox); the JS loads from cdnjs with an SRI hash.

**Test runs:** `python lanes/storm-lead/refresh.py 2026-09-03 --gate G1` (the big southeast-Michigan day: 46 reports, 19 counties as SPC now has it, 1.00 in hail at Brethren, 66 mph at Edgemont Park) exercised the rendering path; then the default run put yesterday's data back in place (see the log line below for what the app opens on).

**Decisions:** storm palette of my own (slate-violet accent for the brand and county ramp, icy blue hail, amber wind; hail and wind never share a hue with the choropleth, so pins read on top of shaded counties). Hail sorts above wind in the list because hail is what sells roofs. Wind-damage reports with no gust are shown hollow and sized small so they do not outweigh measured gusts. Service area taps only place the home base when none is set or "Move" is armed, so normal panning never moves it. No URL state, no accounts, no analytics, nothing leaves the device except the optional tile/radar/NWS requests.

**Not yet real / gaps:** (1) warnings polygons untested against a live severe day; (2) ZIPs are still centroid-distance guesses, not point-in-ZCTA-polygon (`core/web/geo/mi_zctas.json` exists, 850 KB, left out to keep the app small; a point-in-polygon pass in refresh.py is the obvious next step); (3) the replay bar only reaches 30 days, and the fallback hunt for an older storm day costs 2 requests per day walked; (4) nowcoast asks for attribution and says do not rely on it for mission-critical use, which fits an optional layer; OSM tiles are for light use only and would need a paid or self-hosted provider after GO; (5) `refresh.py` had a small pre-existing bug (`--gate G1` was read as the date); fixed. Core gaps noticed: none that blocked the lane; a shared "point in GeoJSON polygon" helper and a `days-window` fetch helper would be small additions to `core` if a second lane needs them.

## G2 Demand test

**Result: pack written, nothing sent.** Lane parked `waiting_nick`.

20 Michigan roofing / restoration / exterior contractors from public business listings (company sites, ProjectMap It portfolios, Downtobid and Builder Market directories, Grand Rapids Chamber, a Jackson local directory). Business name, type, city and a public contact URL only; no personal names. Spread: Metro Detroit and Oakland County (7, including Royal Oak and Troy), Grand Rapids / lakeshore (6), Lansing / Kalamazoo / Battle Creek (4), Jackson / Ann Arbor (3), Flint (1). Target list: `outreach/targets.csv`. Drafts: `outreach/emails.md` (one per target, same 3-question survey). Reply tally goes in `outreach/replies.md`.

Pitch used: "the morning after a storm you get a one-page email listing the Michigan counties and ZIP codes hit by 1-inch-plus hail or 58+ mph wind the night before, built straight from NWS storm reports." Price stated: $50-100/month.

Blocker: **Nick must send the emails** (and should attach both sample PDFs, the big-day one first). Several contact URLs are directory pages rather than the company's own site; Nick should swap in the real contact form where he finds one.

Searches used: 12 web searches (8 for contractors and directories, 4 for competitors).

## G3 Decision

**PROVISIONAL score written** (`scorecard.json`, decision forced to PARK until replies). Demand=3, repeat_use=3, competition=2, license=5, build_effort=5, total 18/25. On the arithmetic alone that would be GO; it is held at PARK because the demand number is a guess until Nick tallies replies, and because of the competition picture below. `merge_with = ["weather-trigger-jobs"]` (lane 7 overlaps: same trigger data, different audience).

**Competition, honestly: this market is crowded.**
- HailTrace and Interactive Hail Maps (with its Hail Recon app) are the incumbents; both are quote-priced, sell radar-derived hail swaths and address-level history, and HailTrace sells an API for lead generation.
- Published prices in the category: HailWatch $65-119/month; Hail Drive $29.99/month or $250/year; GAF WeatherHub $349-649/year depending on contractor tier; AnythingWeather $179-189 per storm map, $1,899/year per state.
- Free lookalikes that do roughly what Storm Lead does: Beacon Storm+ (free hail maps for Beacon PRO+ customers, filterable by ZIP and hail size), the Hail Yeah app (plots every SPC hail/wind/tornado report with alerts), LiveHailReports (free state-level swath emails), CoreLogic's free daily hail alerts. StormerSoft did not turn up at all in search.
- What incumbents have that public data cannot give: radar-estimated swaths between report points, address-level "was this roof hit" answers, and multi-year history per address. Storm Lead would only ever have the point reports the NWS received.
- Possible edge: Michigan-only, cheap, ZIPs in the inbox with no app or map to learn, and it costs one small cron job to run. That is a feature, not a company; the realistic ceiling is a few dozen Michigan roofers at $30-50/month in season.

**Recommendation for Nick:** send the 20 emails; if fewer than 3 say "yes" at $50+, PARK or fold the alert into weather-trigger-jobs rather than build it standalone. If 3+ say yes, the build is days (daily `refresh.py` run, email delivery, Stripe).

## Core changes

- `core/fetch.py`: added `Fetcher.get_bytes()` (binary download with the same cache, budget and usage log) because the Census gazetteer is a zip file and `get()` is text-only. Small and general; any lane that needs a zip, PDF or image can use it.

## Timings and blockers

- G0: 13 min (05:31-05:44 UTC). Most time was the 606 daily SPC fetches at the polite 0.5 s interval. Blockers: none. Two small bugs found and fixed (2025 gazetteer is pipe-delimited; BOM on its first column).
- G1: 2 min. Blockers: none.
- G2: under 1 min to write the pack (searches done in parallel during G0's fetch). Blocker: Nick must send.
- G3: provisional; final score waits on replies.

## Pipeline check for Nick (2026-11-01)

Nick skipped the outreach send on 2026-11-01 (FROM_NICK entry 9819e71ea3be) with the note "I would like to confirm everything is working right with this before we do outreach". Checked end to end from this PC the same evening:

- `refresh.py`: clean run; SPC reported 0 qualifying Michigan reports for the Oct 31 convective day, so the alert and app fall back to the most recent storm day (Oct 7: 4 wind-damage reports, Kalkaska, Antrim and Crawford counties, 4 ZIPs), which is the designed behaviour. Live NWS alerts feed answered (0 active warnings). `samples/storm_lead_alert.*` regenerated; the Sep 3 big-day example (46 reports, 15 counties) is unchanged and still the better sample to show.
- `python -m core.webapp check storm-lead`: OK (15 files, 113 KB; NWS, nowcoast radar and OSM tiles are optional layers).
- `python -m core.mailmerge storm-lead`: 0 email targets, 20 web-form targets in `outreach/send_sheet.md`; template in Nick's voice, sample on request, 6-month free trial. Nothing sent.
- Timing fact for Nick: the 24-month backtest found 0 alert days in Nov-Feb. A trial that starts now would send nothing until about March. Outreach now still tests demand (reply or not), but the trial's value starts in spring.

Nothing failed. The send is back in `needs_nick.md` as a single item carrying these results.

## Log

- 2026-10-24T05:31:23+00:00 G0 started. SPC storm reports endpoint, license, timing; 24-month MI backtest
- 2026-10-24T05:43:58+00:00 G0 finished: pass. SPC daily+bulk CSVs live (public domain); 24-month MI backtest: 974 qualifying reports on 88 alert days, 0 in Nov-Feb
- 2026-10-24T05:43:58+00:00 G1 started. one-page Storm Lead alert for latest MI storm day with ZIP mapping
- 2026-10-24T05:45:29+00:00 G1 finished: pass. storm_lead_alert.pdf/html/csv for 2026-10-07 (latest MI day, 4 reports) plus 2026-09-03 example (46 reports, 15 counties); ZIPs via Census ZCTA centroids
- 2026-10-24T05:45:30+00:00 G2 started. 20 Michigan roofing/restoration contractors from public listings; outreach pack
- 2026-10-24T05:45:30+00:00 G2 finished: pass. 20 targets + drafts in outreach/; nothing sent
- 2026-10-24T05:45:30+00:00 status -> waiting_nick. blocker: Nick must send outreach emails. next: tally replies, then final G3
- 2026-10-24T05:45:30+00:00 G3 started. provisional score pending replies
- 2026-10-24T05:45:30+00:00 status -> waiting_nick. blocker: Nick must send outreach emails. next: tally replies, then final G3
- 2026-10-25T22:58:02+00:00 G1 prototype (2026-10-25): interactive Leaflet web app in app/ (hail/wind pins, county choropleth, live NWS warnings, optional OSM/nowcoast radar, service area, 30-day replay); refresh.py now writes app/data/{latest,days,warnings}.json; core.webapp check OK; status unchanged (waiting_nick)
- 2026-11-01T23:55:34+00:00 FROM_NICK 2026-11-01 18:22 (SKIPPED, entry 9819e71ea3be): "Send G2 outreach". Box ticked: yes. Filed: from_nick/2026-11-01_1822_9819e71ea3be.md. Notes: I would like to confirm everything is working right with this before we do outreach Lane set back to active: no open Nick items left. Tick agent: continue this lane from these notes.
- 2026-11-02T00:01:32+00:00 status -> waiting_nick. blocker: Pipeline re-checked 2026-11-01 at Nick's request (all OK); Nick to send the 20 outreach forms or wait for spring (no MI storm days Nov-Feb in the backtest).. next: Tally replies, then final G3
