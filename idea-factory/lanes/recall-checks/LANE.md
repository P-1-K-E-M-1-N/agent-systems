# Recall Checks for Used-Car Dealers

**Type:** revenue  |  **Queue order:** 4

Open-recall checks on dealer inventory via NHTSA vPIC + recalls API.

## Current state

(see lane.json; board regenerates ops/STATUS.md)

**Short version (2026-10-24):** G0, G1 and G2 passed. The product had to shrink. NHTSA's free public API tells you which
safety recalls *apply to a year/make/model*; it cannot tell you whether a specific car's recall is *still open*. That
VIN-level answer lives only in NHTSA's consumer web tool (fed weekly by manufacturers) and in paid dealer products
(Carfax, AutoCheck, Recall Masters, AutoAp). So the sellable thing is a weekly **Recall Exposure Sheet**: "these 12 of
your 40 cars have recalls that apply, here is the worst one, go confirm these VINs." Nick confirmed that smaller
product on 2026-10-24 (no paid VIN-level data deal). Provisional G3 says **PARK (18/25)**: the total clears the GO bar,
but demand is scored 2 (a guess) until the 19 outreach drafts go out and replies come back. Status: `waiting_nick`.

## G0 Data check

**Result: PASS, with the product shrunk.** Took about 5 minutes of wall-clock; 22 live requests through `core.fetch`
(`g0_probe.py`, `g0_terms_probe.py`), all logged in `usage.jsonl`.

What works, verified with real requests:

| Source | Endpoint tried | Result |
|---|---|---|
| `nhtsa_vpic` | `GET vehicles/DecodeVinValues/<VIN>?format=json` | 200, decodes make/model/year/body; 333 ms |
| `nhtsa_vpic` | `POST vehicles/DecodeVINValuesBatch/` (form body `format=json&data=VIN;VIN`) | 200, 3 VINs in one call, max 50 per POST; partial VINs with `*` accepted |
| `nhtsa_recalls` | `GET recalls/recallsByVehicle?make=ford&model=f-150&modelYear=2013` | 200, 3 campaigns with campaign number, component, summary, consequence, remedy, `parkIt`, `parkOutSide`, `overTheAirUpdate` flags |
| `nhtsa_recalls` | `products/vehicle/modelYears|makes|models?issueType=r` | 200, the official 3-step lookup chain |
| `nhtsa_recalls` | `recalls/campaignNumber?campaignNumber=23V123000` | 200, adds `PotentialNumberofUnitsAffected` |
| `nhtsa_odi_flatfiles` | `static.nhtsa.gov/odi/ffdd/rcl/RCL.txt` | 200; the datasets page lists `FLAT_RCL_POST_2010.zip` (14 MB) regenerated nightly at 03:05 ET |
| `nhtsa_web` | `nhtsa.gov/nhtsa-datasets-and-apis`, `nhtsa.gov/recalls` | 403 to a generic User-Agent, 200 with a browser-style UA; text saved in `data/g0_page_*.txt` |

**The VIN-level question (the important one).** There is no public VIN-level open-recall API.
- NHTSA's datasets-and-APIs page documents only "Approach A: get by Model Year, Make, Model" and "Approach B" (the
  modelYears -> makes -> models chain). Nothing by VIN. Guessed routes (`recalls/recallsByVin`, `vehicles/byVin`,
  `safercar/vin`, the old `webapi/api/Recalls/vehicle/vin/`) all return HTTP 403, and so does a nonsense route, so 403
  there just means "no such endpoint".
- NHTSA's VIN tool (nhtsa.gov/recalls, formerly vinrcl.safercar.gov) is a consumer web form. Its own text: results show
  "an unrepaired recall for a vehicle from certain manufacturers"; it does NOT show repaired recalls, recalls over 15
  years old, small-manufacturer recalls, or non-safety campaigns; "recall information provided through this VIN lookup
  tool is provided by the manufacturer conducting the recall"; manufacturers must update at least weekly. It also says
  "You can search up to 100 VINs to see if any vehicle has an open recall", i.e. a dealer can already batch-check a
  whole small lot by hand for free.
- We will not scrape that tool. It is a manufacturer-fed consumer form behind a WAF, and scraping it is the one thing
  that could draw a complaint. The honest product is year/make/model exposure plus "confirm these VINs".

**License.** vPIC, the Recalls API and the ODI flat files are US Government works (public domain). No API key, no
registration, no terms page restricting commercial use found anywhere on nhtsa.gov or vpic.nhtsa.dot.gov (the
`/web-policies-and-notices` URL is now a 404). The vPIC page says only that traffic is "controlled by an automated
traffic rate control mechanism"; no numbers. `commercial_ok=true` for all three stands. Attribution "Source: NHTSA"
and a "not affiliated with NHTSA" line go on every sheet.

**Update frequency.** Recall campaigns are posted as manufacturers file them (daily); the flat file regenerates nightly;
vPIC changes a few times a year (v4.10, last code change 2026-10-17). A weekly sheet is well within that.

**Rate limits / quirks found.**
- No published limits; our registry caps at 1000/day per source with 0.3 s spacing; the whole 20-car sample used 70
  live calls (one vPIC batch + ~3 recall calls per vehicle). A 100-car lot refreshed weekly is trivially within budget;
  the flat file removes the per-vehicle calls entirely.
- Reproducible HTTP 400 from `recallsByVehicle` for some valid combinations (2017 Chevrolet Equinox fails every time;
  2016 and 2018 work). A product must fall back to the flat file for those rows.
- The API's own model spellings are odd (`F-150 SUPERCAB`, `X3 XDRIVE28I`) but plain names (`f-150`, `X3`) work, so
  query plain first, variants second (`refresh.py` does this).
- Dates come back `DD/MM/YYYY`.

**Other checks asked for.**
- Michigan Secretary of State does not publish dealer inventories, and its dealer-license records are sold only through
  a bulk-records program whose terms forbid marketing use. Dealer inventory has to come from the dealer. Fine: that is
  the product's input anyway.
- Michigan has no law requiring used-car dealers to disclose or fix open recalls (federal law doesn't either; a Senate
  bill was reintroduced Sept 2025). Pressure comes from state AG settlements (CarMax multistate; ~104 NY dealers), not
  from Michigan statute. That weakens "you must do this" and leaves "protect yourself and your customer".
- People data: none. VINs identify vehicles. We never ask for or store owner, buyer or plate data. The sheet
  deliberately uses stock numbers.

New sources registered in `lanes/recall-checks/sources.json`: `nhtsa_web` (terms reading only) and
`nhtsa_odi_flatfiles` (bulk fallback).

## G1 Sample

**Result: PASS.** About 5 minutes. Artifact: `samples/recall_exposure_sheet.{csv,html,pdf}`, rebuilt by
`python lanes/recall-checks/refresh.py` (one vPIC batch POST + recall lookups per vehicle, all through `core.fetch`).

Inventory: 20 vehicles typical of a Metro Detroit lot. Six carry public example VINs (NHTSA docs partials `5UXWX7C5*BA`
and `5YJSA3DS*EF`, plus long-standing textbook VINs for a 2013 F-150, 2018 Malibu, 2003 Accord, 2011 BMW 5-series; three
of those fail the check digit, which the sheet flags). The other 14 are year/make/model only, which is what most small
lots will actually hand over: Silverado 1500, Equinox, Escape, Grand Cherokee, Fusion, CR-V, Camry, RAV4, Explorer,
Ram 1500, Cruze, Focus, Grand Caravan, Cherokee.

What the sheet shows per vehicle: stock #, year/make/model, VIN (or "year/make/model only"), number of applicable
campaigns, NHTSA park-it / park-outside flags, the most serious campaign (component, NHTSA's summary, remedy), every
campaign number, newest campaign date, and an "Open/closed?" column that honestly says "verify per VIN at
nhtsa.gov/recalls (free, 100 VINs at a time)".

Numbers from the live pull on 2026-10-24: 19 of 20 vehicles have at least one applicable safety recall, 170 campaigns in
total, 3 vehicles carry NHTSA do-not-drive / park-outside advisories (2016 Silverado 1500 front control arm; 2014 Focus
steering gear; 2016 Jeep Cherokee power-liftgate fire risk). Five vehicles have campaigns filed in 2026, which is the
"refresh weekly" argument. The 2017 Equinox row shows the API-400 quirk and says so.

Known weaknesses of the sample: counts include equipment campaigns (tires, child seats) the API associates with a model,
e.g. the 2003 Accord's 24; several recalls apply only to a build-date window, so the true count for a given car is
usually lower. Both are reasons the sheet is an *exposure* report.

## G1 prototype (2026-10-25)

**Rule 1 changed today: the G1 artifact is the product as a customer opens it, not a sheet.** Nick's words on the CSV/HTML/PDF:
"these aren't products... it's just an excel sheet. I want to see these as super nice web designs." So Recall Checks is now a
static web app in `app/` (plain HTML/CSS/JS on the `core.webapp` shell, no build step, installable), built for a small
used-car dealer standing on the lot with a phone. The PDF sheet stays: it is what 19 dealers were emailed on Oct 24-25,
and the app shows exactly the same promise (year/make/model exposure from free NHTSA data, honest that VIN-level
"already fixed" status is not free). About 2 hours of agent time, mostly front end.

**What the app shows (top to bottom).**
1. Lot header: "Example lot" with an "example stock" tag, "20 vehicles, checked Oct 25, 2026 against NHTSA"; four KPIs
   (vehicles; with an open campaign; campaigns to confirm; vehicles flagged critical, with the count of NHTSA
   do-not-drive / park-outside advisories under it); a stacked severity strip of all campaigns (critical / serious /
   moderate) with direct labels, so colour is never the only cue.
2. Honesty block, one sentence, collapsible: "NHTSA's free data says a campaign exists for this year, make and model; it
   cannot say whether this exact car was already repaired. Confirm at the dealer portal or safercar.gov with the VIN
   before sale." Opens to the build-date caveat, the free 100-VIN tool, and the severity rule.
3. "What to do this week", generated from the data: NHTSA-advisory vehicles first (A107 Silverado control arm, A118
   Focus steering gear, A120 Cherokee liftgate fire), then campaigns filed in the last 120 days, then vehicles with 5+
   critical campaigns, then the failed Equinox lookup; plus a tip counting vehicles on file without a full VIN.
4. Vehicle cards, most serious first (advisory, then worst category, then number of critical campaigns): stock number,
   severity pill, DO NOT DRIVE / PARK OUTSIDE badge, campaign count, year make model trim, VIN in a monospace block
   with Copy (or "year, make and model only"), the worst campaign's component, what is wrong and the fix in plain words,
   campaign chips linking to `nhtsa.gov/recalls?nhtsaId=<id>` (new tab), "show all" for the full list with per-campaign
   severity dot, date, defect and fix; newest campaign date and the filing manufacturer. Filters all / with campaigns /
   critical / clean (each with its count) and a search over stock, VIN, year, make, model, trim.
5. Check a vehicle: VIN, or year + make + model. Order: VIN on the lot -> snapshot by `year|make|model` -> live NHTSA
   (vPIC decode, then recallsByVehicle) when reachable. Live results are categorised in the browser with the same rule.
   When live is blocked (the review sandbox) the result card says "From this week's snapshot" and the status line says
   "live lookup works when the app is installed from its own address"; when neither has it, it says so plainly.
6. Footer: NHTSA vPIC and Recalls API, public domain, not affiliated; no owner or buyer data; refreshed time; Install.
   Light and dark themes from the shared tokens with a toggle; Recall Checks' own look is asphalt + petrol blue, amber
   for the lot tag, safety red reserved for the critical tier and the NHTSA advisory badge.

**Data files and how `refresh.py` keeps them live.** One run (`python lanes/recall-checks/refresh.py`, all HTTP through
`core.fetch.Fetcher`: 1 vPIC batch POST + ~2 recall calls per vehicle, cached 1-7 days) now writes, besides the
CSV/HTML/landscape PDF in `samples/` and the raw `data/recalls_by_vehicle.json`:
- `app/data/latest.json` (265 KB): lot label and note, `checked_at`, `generated_at`, cadence, source line, the
  limitation sentence, the severity rule in words, totals (vehicles, with_campaigns, campaigns, critical_vehicles,
  lookup_failed, by_severity) and `vehicles[]`, each with stock, year, make, model, trim (from vPIC when a VIN exists),
  vin, vin_note, lookup_failed, flags, newest, worst, n, lookup_key and `campaigns[]` (id, component in plain words,
  component_raw, defect, fix, full summary/consequence/remedy, manufacturer, report_date ISO, severity, park_it,
  park_outside, ota). Sorted most serious first so the page needs no sorting.
- `app/data/latest.js` (242 KB): the same object as `window.RECALL_SNAPSHOT`, loaded by a classic `<script>` before
  `app.js`, so the first frame already has the lot and its numbers (and the page works from `file://`). `app.js` then
  fetches `latest.json` and re-renders only if `generated_at` differs.
- `app/data/campaigns.json` (261 KB): every campaign the lot touched, de-duplicated, keyed `"year|make|model"` (lower
  case) with the API's own model spelling, for the offline "Check a vehicle". If it fails to load the app derives the
  same index from `latest.json`.
A weekly scheduled run of `refresh.py` is all the "live" the prototype needs; the service worker is network-first for
`data/` so an installed phone picks up the new week on open.

**Severity rule** (`refresh.py category()`, mirrored in `app.js categorize()`): **critical** = NHTSA `parkIt` or
`parkOutSide`, or the component text matches air bag / inflator / brake / steering / fuel, or NHTSA's consequence
sentence says fire, loss of steering or braking, unable to stop or steer; **serious** = component matches seat belt,
restraint, child seat, wheel, tire, axle, suspension, control arm, hood, latch, structure, frame, power train,
transmission, engine, visibility, exterior lighting, or the consequence says stall, rollaway, loss of power, detach,
separate, unintended; **moderate** = the rest. On today's pull: 77 critical, 75 serious, 18 moderate campaigns; 19 of 19
vehicles with campaigns have at least one critical one (real cars with 3+ campaigns almost always do: a brake, air-bag
or fuel campaign is the norm), which is why the cards also carry the NHTSA advisory badge and the critical count, and
"this week" ranks by those rather than by the pill. A first version that also matched "fire" and "crash" anywhere in the
consequence text put 87 campaigns in critical and 1 in moderate; too loose to be useful, so component text leads.

**Optional, and why.** Live NHTSA calls from the browser (`api.nhtsa.gov`, `vpic.nhtsa.dot.gov`) are optional because
the review page is a claude.ai artifact that blocks fetches to other hosts; everything renders from `app/data/*.json`
and the live path is tried only on a "Check a vehicle" submit, with a 7 s timeout and the snapshot as fallback.
Install button appears only when the browser offers `beforeinstallprompt` (installed from its own address). Theme
toggle is remembered per device in localStorage only.

**Decisions.** Kept the lot as example stock (public example VINs, stock numbers, no owner data) and say so in the header
tag and footer. No alerts, prompts, print, mailto, accounts, payments or tracking. Did not scrape NHTSA's VIN tool (G0
decision stands). Used the shared `.page` layout, no map. Severity colours validated with the dataviz palette checker in
light mode (all checks pass); in dark mode red and amber sit close under deuteranopia, so every coloured mark carries a
text label or count.

**Checks.** `node --check app/app.js` clean; `python -m core.webapp check recall-checks` prints OK (12 files, 821 KB; the
external hosts it lists are the optional live calls, NHTSA link targets, and URLs inside NHTSA's own remedy text).
A node smoke test with a fake DOM rendered 20 cards, 6 this-week items, the filters (20/19/19/0), the search, the
snapshot lookup (2016 Ford Fusion -> 13 campaigns from the snapshot with the "live not reachable" line), the "not in
this week's snapshot" case, and the VIN-on-lot case. No real-browser screenshot this session (the browser tool needed a
device choice I could not ask for); Nick should open it on his phone.

**Not yet real.** Intake (a dealer's own stock list) is still the Python `INVENTORY` constant; the app has no upload or
edit, by design (validate, never build). The weekly schedule is a manual `refresh.py` run. The flat-file fallback for the
Equinox-style API 400 is still not written, so that row stays "lookup failed". Core gaps found: none blocking; a small
`core.webapp` nicety would be a `check` note that distinguishes link targets from fetch targets.

## G2 Demand test

**Result: PASS (drafts written; nothing sent).** Under a minute of compute after ~12 web searches for targets.
Files: `outreach/targets.csv` (20 dealers), `outreach/emails.md` (20 drafts + 3-question survey), `outreach/replies.md`
(empty tally), and the entry in `needs_nick.md`. Built by `build_outreach.py` via `core.outreach.write_outreach_pack`.

Product as pitched: **Recall Check Weekly**: every Monday a one-page sheet of the whole lot showing which cars have NHTSA
safety recalls that apply, the most serious one in plain English, campaign numbers. Price in the email: $39/month for up
to 50 vehicles ($29 under 20). Attachment: `samples/recall_exposure_sheet.pdf`.

Targets: 20 independent used-car dealers from public listings (dealer websites, CarEdge/KBB dealer pages, a BBB
category page, lender dealer-finder pages). Business name, city and public contact URL only; no people. Royal Oak (2),
Madison Heights (2), Waterford (7), Pontiac (2), Southfield (1), Oak Park (2), Farmington Hills (3), plus one Sterling
Heights lot as a Macomb control. Franchise stores were excluded on purpose: they get recall data from the OEM.

Blocker: Nick must send the emails. Status set to `waiting_nick`.

**Follow-up from Nick, 2026-10-24 (FROM_NICK 2026-10-24 08:17, entry 110dad8a00af).** Nine of the twenty targets had
only a CarEdge/KBB/BBB/lender listing as their contact URL. Nick looked each one up and found the dealer's own site for
nine of ten: `targets.csv` now carries those URLs in `contact_url`, a new `email` column with the four business
addresses he found (Top Auto Sale, Grand Auto Sales Lot, Gear One, Affordable Auto Sales of Michigan), and a `source`
note saying the old listing URL was replaced. "Nitro Auto Sales" is really Nitro Truck and Auto Accessories (3059 Dixie
Hwy), renamed. All American Auto Sales (Pontiac) was dropped: no website, phone or social page exists, only a bare BBB
category entry. The pack is now **19 targets / 19 drafts**; `emails.md` has the matching contact pages and emails.
Nick's decision on the Waterford loop: **no drive needed**. Every Waterford lot has a working online contact form, so the
drafts go out online. Victory Motors on Main Street in Royal Oak is the only true walk-in (its site has no form or
email, just a newsletter box; phone is the alternative). Phone numbers on listing sites disagreed with the dealers' own
sites, so Nick's numbers come from the dealer sites and are kept in his entry, not in `targets.csv` (public business
numbers only, and the emails go through forms anyway).

Also from his 07:45 entry: the sample PDF was cutting off after the "NHTSA campaign #s" column because the portrait
page is 532pt wide and the column widths added up to 635pt. Fixed before outreach by adding a general `landscape`
option to `core.pdfmini.Pdf` / `core.samples.write_pdf` / `write_all` (default off, so no other lane changes) and
having `refresh.py` write a landscape Letter page with widths that sum to the 712pt usable width. Rebuilt from live data
2026-10-24; the PDF's content stream now carries all twelve headers through "Newest", "Open/closed?" and "Note" on one
page. The HTML and CSV are unchanged in layout. Narrow columns still truncate long text with "~" (the HTML carries
the full text), which is the trade-off Nick chose over dropping columns.

## G3 Decision

**Nick's product decision, 2026-10-24 (FROM_NICK 2026-10-24 07:45, entry 881601993108).** The lane asked him to pick
between (a) the smaller Recall Exposure Sheet on free NHTSA data and (b) buying VIN-level open/closed status from a
Carfax/AutoCheck/Recall Masters-class vendor and re-scoring. He chose **(a): keep the smaller exposure sheet, no paid
data deal.** In plain language: the product is exactly what `refresh.py` already builds, a weekly year/make/model
exposure sheet that tells a dealer which cars are worth a minute on NHTSA's free VIN tool. We will not license anyone's
data, so cost of goods stays at zero and the license column stays public domain. His positioning note: "we can make it
free and better than their software", i.e. aim at the small independent lot that Carfax/AutoAp price for franchise
stores, keep it simpler than their dashboards, and be willing to give it away free if that is what gets the first lots
using it. That is a price-and-simplicity edge, not a data edge, so competition stays scored 2.

**PROVISIONAL: PARK, 18/25** (`scorecard.json`, re-scored 2026-10-24 with `python -m core.scoring ... --provisional`
after Nick's decision; the earlier 17/25 came from `g3_score.py`, now updated to the same numbers). The total clears
the GO bar (18 or more, safe license, no weak dimension), but the rule also wants measured demand of 3 or more, and
demand is 2 because nothing has been sent; `--provisional` says the same thing. So: PARK until replies. After the reply
tally, re-run the scoring CLI without `--provisional` and with the real demand number, then
`python -m core.lane recall-checks finish G3 <go|park|kill>`. With 3+ yes/maybe out of 19, demand 3 makes this 19/25 GO.

- demand 2: no replies yet; pain is documented (AG settlements, federal bill) but Michigan imposes no duty, and NHTSA's
  free 100-VIN batch lookup already serves a patient dealer. Goes to 3-4 if 3+ of 19 say yes/maybe.
- repeat_use 4: weekly, inventory turns, new campaigns daily. Genuinely subscription-shaped.
- competition 2 (crowded): Carfax recall monitoring for its dealer subscribers, AutoCheck Open Recall Inventory Check,
  Recall Masters and AutoAp (daily VIN-level recall management, priced for franchise stores, pricing undisclosed), DMS
  recall features, and NHTSA's free tool. All of the paid ones have the VIN-level open/closed answer we are not buying.
  Our edges, per Nick: free or $39 vs. "call for pricing", no contract, simpler than Carfax/AutoAp, works from a
  year/make/model list.
- license 5: public domain, verified live; no third-party data license now that the paid-deal option is closed.
- build_effort 5 (was 4): the product is fixed at the sheet `refresh.py` already produces (CSV/HTML/landscape PDF);
  remaining work is intake, flat-file fallback, scheduling, delivery. A few days. The point taken off before was for
  a possible VIN-level integration, which is now off the table.

Honest read: this is a nice free-or-$39 utility, not a moat. It only becomes a business if independents say the free
NHTSA tool is too fiddly and the Carfax bundle too expensive. The outreach is the whole test. No overlapping lanes
(`merge_with` empty).

## Log

- 2026-10-24T05:32:36+00:00 G0 started. NHTSA vPIC + recalls API: live requests, license, update frequency, VIN-level open-recall question
- 2026-10-24T05:36:58+00:00 G0 finished: pass. vPIC decode (single+batch) and recallsByVehicle both live, public domain, daily flat file; NO public VIN-level open-recall API (web tool only), product shrinks to recall exposure report
- 2026-10-24T05:36:58+00:00 G1 started. 20-vehicle Michigan lot: decode VINs, pull recalls per year/make/model, build Recall Exposure Sheet
- 2026-10-24T05:41:36+00:00 G1 finished: pass. recall_exposure_sheet.csv/html/pdf from 20 vehicles, 170 NHTSA campaigns, 3 park-it/park-outside flags; refresh.py rebuilds
- 2026-10-24T05:41:36+00:00 G2 started. 20 Oakland County / Metro Detroit independent used-car dealers from public listings; outreach pack
- 2026-10-24T05:41:36+00:00 G2 finished: pass. 20 targets + 20 draft emails + 3-question survey in outreach/; nothing sent
- 2026-10-24T05:41:36+00:00 G3 started. provisional score before replies
- 2026-10-24T05:41:37+00:00 status -> waiting_nick. blocker: Nick must send outreach emails. next: tally replies, then final G3
- Gate durations (lane.json): G0 ~4 min, G1 ~5 min, G2 <1 min compute (the ~12 target web searches ran alongside G0/G1). G3 left open on purpose until replies. Usage: 92 live requests (G0 22, G1 70), 63 cache hits, 7 logged errors (4 deliberate VIN-route probes, 3 the Equinox API quirk). Blockers: nhtsa.gov 403s to generic User-Agents (worked around with a browser-style UA for the terms read only); no VIN-level API (not solvable, product reshaped).
- 2026-10-24T12:31:20+00:00 FROM_NICK 2026-10-24 07:45 (DONE, entry 881601993108): "Decide on the smaller product". Box ticked: yes. Filed: from_nick/2026-10-24_0745_881601993108.md. Notes: Sample PDF cuts off after the "NHTSA campaign #s" column (Newest, Open/closed?, 
  Note are missing). Fix before outreach: landscape or drop columns. HTML version  is fine. for the lane.md - we can make it free and better then their softare. Tick agent: continue this lane from these notes.
- 2026-10-24T12:31:20+00:00 FROM_NICK 2026-10-24 08:17 (DONE, entry 110dad8a00af): "Half of the targets have no dealer website". Box ticked: yes. Filed: from_nick/2026-10-24_0817_110dad8a00af.md. Notes: (none) Tick agent: continue this lane from these notes.
- 2026-10-24T12:40:17+00:00 Acted on FROM_NICK 2026-10-24 07:45 (entry 881601993108, 'Decide on the smaller product'): Nick keeps the free-NHTSA Recall Exposure Sheet, no paid VIN-level data deal; positioning 'free and better than their software' recorded under G3 in LANE.md. Fixed his PDF complaint: added landscape=False option to core.pdfmini.Pdf, threaded through core.samples.write_pdf/write_all; refresh.py now writes landscape Letter with 12 widths summing to 712pt; rebuilt from live data and verified all headers through Newest/Open-closed?/Note are in the PDF stream on one page. HTML/CSV layout unchanged. Re-scored via core.scoring CLI with --provisional: demand 2, repeat 4, competition 2, license 5, build_effort 5 (was 4) = 18/25 PARK (provisional; rule needs demand>=3 for GO). g3_score.py updated to match.
- 2026-10-24T12:40:17+00:00 Acted on FROM_NICK 2026-10-24 08:17 (entry 110dad8a00af, 'Half of the targets have no dealer website'): targets.csv gained an email column; 9 directory-listing contact_urls replaced with the dealers' own contact pages Nick found; 4 business emails filled (Top Auto Sale, Grand Auto Sales Lot, Gear One, Affordable Auto Sales of Michigan); Nitro Auto Sales renamed Nitro Truck and Auto Accessories with its URL; All American Auto Sales dropped (no site/phone/page). emails.md: matching Contact page lines updated, Nitro section renamed, All American section removed, now 19 drafts. Nick's decision noted under G2: no Waterford drive, all lots have online forms, Victory Motors (Royal Oak) is the only walk-in. Status stays waiting_nick (Send G2 outreach still open; count in needs_nick.md corrected to 19).
- 2026-10-24T19:13:36+00:00 Nick reviewed the first email draft and sample PDF before sending (2026-10-24 ~10:30): email read like a bot with a spam-looking subject; PDF columns overlapped and some cells did not match. Fixed in core (not the lane): core.pdfmini now measures real Helvetica widths and wraps table cells (rows grow, header repeats per page, cells capped with '...' at a word boundary); core.outreach template rewritten in plain first person with a question subject, company and factory mailbox in the signature; core.mailmerge --eml writes ready-to-send .eml drafts with the PDF attached. Lane: refresh.py sheet redesigned to 9 columns (component + defect sentence in plain English, the fix, 2 campaign numbers + count, newest date; repeated 'Open/closed?' column moved to the notes; failed Equinox lookup shown as '?' with an honest note; check-digit noise dropped). build_outreach.py targets synced with Nick's contacts (19, emails for 4). Regenerated: samples/*, outreach/emails.md, targets.csv, mailmerge.csv, send_sheet.md, 4 .eml drafts on Nick's Desktop. Still waiting on Nick to send; nothing sent.
- 2026-10-25T21:37:08+00:00 FROM_NICK 2026-10-25 17:33 (DONE, entry f5696fca618d): "Send G2 outreach". Box ticked: yes. Filed: from_nick/2026-10-25_1733_f5696fca618d.md. Notes: Outreach sent to 19 of 20 dealers.
  Email with PDF attached, Oct 24: Affordable Auto Sales, Gear One, Grand Auto   
  Sales Lot, Top Auto Sale (10:22 pm); A & R Auto Sale, A Plus Motor Sales,      
  Farmington Financial, Spectrum Autoworks, Telegraph Motors (11:44 pm). Five of 
  those addresses came from the dealers' own sites, not targets.csv.
  Web form, Oct 25: H.C. Motors, Lookin-nu, Mack's, Madison Motor Sales, Oak Park
  Auto Sales, RJ Auto of Farmington Hills, Waterford Auto Sales, Western Auto    
  Sales, Nitro Truck and Auto (typo fixed). Form messages offer the sample on    
  reply. Lane set back to active: no open Nick items left. Tick agent: continue this lane from these notes.
- 2026-10-25T21:37:08+00:00 status -> waiting_nick. blocker: Outreach sent to 19 of 20 dealers (Oct 24-25). Waiting for replies; re-score G3 with real demand once replies are tallied or after 10 days of silence (Nov 4).. next: resume from FROM_NICK 2026-10-25 17:33 (DONE): Send G2 outreach
- 2026-10-25T21:37:08+00:00 Acted on FROM_NICK 2026-10-25 17:33 (DONE): Nick sent outreach to 19 of 20 dealers (9 by email with PDF, 9 by web form offering the sample on reply; 5 email addresses found on dealer sites). G2 is now live. Next: tally replies in outreach/replies.md and re-score G3 without --provisional by Nov 4; no replies by then means demand stays at 2 and the lane parks for real.
- 2026-10-25T22:16:35+00:00 G1 prototype (rule 1 change): Recall Checks web app in app/ on the core.webapp shell; refresh.py now also writes app/data/latest.json, latest.js and campaigns.json from live NHTSA (20 vehicles, 170 campaigns: 77 critical / 75 serious / 18 moderate, 3 NHTSA advisories). node --check and core.webapp check OK. lane.json gates.G1.note updated; status unchanged (waiting_nick for dealer replies). CSV/HTML/PDF sheet kept as the email attachment.
