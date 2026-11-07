# Needs Nick

**Open items: 4**

_Rolled up from lanes/*/needs_nick.md plus ops/needs_nick_global.md by `python -m core.board`. Tick a box in the lane file when done; this file is regenerated._

## Factory-wide

- [x] **Approve the two scheduled jobs' cost model** (2026-10-24): both jobs run as Claude Code cloud routines on your plan (no new paid service). If you would rather run them locally, see ops/AUTOMATIONS.md for the Windows Task Scheduler alternative. _(DONE via FROM_NICK 2026-10-24 07:25)_
- [x] **Set up a free factory mailbox so outreach is one sitting, not 60 hand-typed emails** (2026-10-24). Done by Nick on 2026-10-24: mailbox nick.aiadigital@gmail.com (company AIA Digital Services), Thunderbird installed and connected. No Mail Merge add-on needed: `python -m core.mailmerge <slug> --eml <folder>` writes finished .eml drafts (HTML layout, PDF attached) that open in Thunderbird as unsent messages; Nick clicks Send. _(DONE, recorded by Claude from Nick's session 2026-10-24)_
- [x] **Open network access for the cloud tick, or no lane can pass G0** (2026-10-24). The first 7:00 am tick promoted lanes 5-8 (Contract-Winner Intel, Benchmarking backend, Weather-trigger jobs, Site-selection) but every data request from the cloud sandbox was refused by its proxy with a 403: api.usaspending.gov, api.census.gov, portfoliomanager.energystar.gov, api.weather.gov, www.spc.noaa.gov. The agent registered the sources and stopped; nothing was invented. Fix (5 minutes): open https://claude.ai/code/environments, pick the "Default" environment, find the network / internet access setting, and allow outbound traffic (all hosts is simplest; otherwise add the five above plus data.detroitmi.gov, services2.arcgis.com, www.ndbc.noaa.gov, api.tidesandcurrents.noaa.gov, coastwatch.glerl.noaa.gov, vpic.nhtsa.dot.gov, api.nhtsa.gov, static.nhtsa.gov). If the setting is not offered on your plan, tell Claude Code "run the Idea Factory tick locally" and the gate work happens from this PC instead; the cloud tick keeps doing the bookkeeping. _(DONE via FROM_NICK 2026-10-24 09:13)_

- [x] **Storm Lead on Android: three yes/no decisions before anything can be built** (2026-10-25). You asked for an Android app for Storm Lead. The web prototype in `lanes/storm-lead/app/` is already an installable PWA (Chrome on Android offers "Install app"). Turning it into a Google Play listing is a wrapper around that web app (a Trusted Web Activity), which needs three things the factory cannot do on its own: _(DONE via FROM_NICK 2026-10-25 19:31)_
  1. **Hosting on a real address.** The app must live at an https URL you control. Free option: a public GitHub repository with GitHub Pages (the Idea Factory repo is private, and Pages on private repos needs GitHub Pro at USD 4/month). Say "yes, public repo" and the factory creates `P-1-K-E-M-1-N/stormlead` containing only the app folder (no lane notes, no outreach), or "yes, GitHub Pro" if you would rather pay.
  2. **Build tools on this PC.** Java JDK 17 and the Android command-line tools (both free, about 2 GB) so `bubblewrap` (Node is already installed) can build the APK/AAB. Say "yes, install" and the factory installs them under C:\MrC	ools and documents the removal steps.
  3. **Google Play developer account.** USD 25 one time, identity verification, you sign up yourself at play.google.com/console; the factory never signs up for you. Only needed when you want it in the store; sideloading the APK onto your own phone for review needs nothing.
  Reply with the yes/no for each in the Done notes. Until then the Android build waits; the web version is unaffected.

- [x] **Review the three prototypes and say what is wrong** (2026-10-25). Open https://claude.ai/artifact/G8E7GAG8Zev9D3gJg1p2Zh and click "Open the app" under Storm Lead, Permit Radar and Recall Checks. Try each on your phone too (same link; Chrome offers "Install app"). For each one write in the Done notes what looks wrong, what is missing, and what you would change before showing it to a customer, lane by lane. The next tick treats your notes as design feedback and fixes the apps. If one is good as is, say "ship it" for that lane. _(SKIPPED via FROM_NICK 2026-11-01 18:22)_

## benchmarking-backend

- [x] **Request ENERGY STAR Portfolio Manager web-services provider access** (2026-10-25): The web services are account-gated (401 without it). Draft below; review, then send via the web-services page https://portfoliomanager.energystar.gov/webservices/home (or the contact link there). Free. Paste EPA's answer when you get it. _(SKIPPED via FROM_NICK 2026-11-01 18:20)_

  > Subject: Request for Portfolio Manager web services provider access
  >
  > Hi, I'm Nick Lektzian, an independent developer in Royal Oak, Michigan. I'm exploring a small tool that helps building owners in cities with benchmarking ordinances (Detroit, Ann Arbor, Grand Rapids) collect their Portfolio Manager data and prepare their annual compliance submission. I'd like to know how to request a web-services provider account, what the terms are for a commercial service, and whether a test environment is available. Thank you, Nick

- [ ] **Create the free Portfolio Manager TEST account (about 5 minutes), or say park** (2026-11-01): Your notes settled the license question (the API terms allow a paid service) and showed there is nothing to request yet: EPA's process is a self-service test account first, live approval later. The factory cannot create accounts, so this one is yours. Steps: go to https://portfoliomanager.energystar.gov/pmtest, "Create a New Account" with business details only (AIA Digital Services), then Account Settings > Software Development > "Yes" to testing web services > "Start Using the Test Environment" > pick all meter types > Submit (approval is immediate). Then add the username and password as environment secrets named `PM_TEST_USER` and `PM_TEST_PASS` in the tick's cloud environment (https://claude.ai/code/environments), the same way as `CENSUS_API_KEY`. Paste nothing here. Say Done and the next tick passes G0 and builds the prototype against the test API. If you would rather not, write "park" in the Done notes and the lane parks.

## filing-alerts

- [x] **Choose a contact email for SEC requests** (2026-10-31): SEC EDGAR now returns 403 "Your Request Originates from an Undeclared Automated Tool" to data.sec.gov because our User-Agent has no contact address (their fair-access rule requires one; a real address, not a made-up one). Tell me which email you are happy to have in the header, e.g. a project address (not your personal one unless you want it). Free, no sign-up. Until then the lane cannot fetch and I will not guess an address. _(SKIPPED via FROM_NICK 2026-11-01 18:22)_

- [ ] **Pick the buyer for Michigan 8-K alerts** (2026-11-05): I could not find 10-20 real Michigan buyers in public listings (only 5 weak guesses: Bodman PLC, Seizert Capital, Monument MicroCap, Quarton Capital, Schechter Investment Advisors). Tell me who you think would pay (small-cap investors, issuer law firms, local business press, suppliers to Michigan public companies), or say Skip and I will test it as a traffic lane with keyword volumes instead.

## great-lakes-conditions

- [x] **Run the 40 queries through Google Keyword Planner** (about 15 minutes, free, no campaign or card needed). _(DONE via FROM_NICK 2026-10-24 08:01)_
  Exact steps and the paste-ready list are in `g2_keywords.md` section (b). Save the export to
  `data/keyword_volumes.csv`, run `python lanes/great-lakes-conditions/load_volumes.py`, and the lane can finish G3.
  This is the only blocker for a real GO/PARK decision.
- [x] Optional 10-minute sanity check: open an incognito window and Google 3-4 of the queries yourself (e.g. _(DONE via FROM_NICK 2026-10-24 08:29)_
  "holland michigan lake conditions today"). Confirm the top results really are undated news and spam, as the
  agent's search tool showed. If a strong incumbent exists that I missed, note it in LANE.md.
- [x] **Open-Meteo: decide only if we ever want it.** Its free tier is non-commercial (`commercial_ok=false`), so the _(DONE via FROM_NICK 2026-10-24 08:26)_
  lane does not use it. The page works entirely on NOAA/NWS public-domain data. A paid Open-Meteo plan (roughly
  EUR 29/month at last check; verify) would add a point wave *model* for places with no buoy, which the NWS zone
  forecast covers more coarsely. Default recommendation: do not pay.
- [x] **GLOS Seagull: no action needed.** Its public ERDDAP needs no key and mostly re-serves buoys NDBC already _(DONE via FROM_NICK 2026-10-24 08:22)_
  publishes. Its terms page (glos.org/terms-of-use) is a 404 and glos.org/legal does not mention commercial use. If we
  ever want a GLOS-only buoy (e.g. the Superior Watershed Partnership buoys near Marquette/Munising), email
  support@glos.org to ask whether commercial redistribution is OK before requesting a key. Draft question:
  "We publish a free, ad-supported conditions page for Michigan harbors. May we display current readings from
  Seagull buoys with attribution, and is an API key required?"

## permit-radar

- [x] **Send G2 outreach** (2026-10-24): 20 roofers/electricians/HVAC/plumbers/demo contractors, none with a published email, all web contact forms. Template rewritten in Nick's voice 2026-10-24 (same as Recall Checks). Work down `lanes/permit-radar/outreach/send_sheet.md`: each entry has the form link and the text to paste (the form text offers the sample on request, since forms take no attachment). If a contact gives an email, add it to the `email` column in `outreach/targets.csv` and rerun `python -m core.mailmerge permit-radar --eml <folder>` for a finished draft with `samples/lead_sheet.pdf` attached. Mark Done with how many were sent; paste replies here. _(SKIPPED via FROM_NICK 2026-11-01 18:22)_
- [x] **Confirm commercial use with Detroit Open Data** (2026-10-24): the portal About page allows business reuse/redistribution but detroitmi.gov/Privacy (linked from the portal footer) prohibits commercial use without written permission. Ask via the portal "Contact Us" feedback form whether a paid weekly permit digest built from the BSEED permit layers is OK. License score stays 3/5 until answered. _(DONE via FROM_NICK 2026-10-25 17:33)_

- [ ] **Permit Radar checked end to end; send the outreach when you are satisfied** (2026-11-01): You asked to confirm everything works before outreach. Checked tonight: the data refresh pulled 426 live Detroit permits for Oct 26 to Nov 1 and rebuilt `samples/lead_sheet.pdf` and the web app data; the prototype passed `core.webapp check`; the send sheet regenerated with 7 email targets and 13 web-form targets. Nothing failed and nothing has been sent. To send: open `lanes/permit-radar/outreach/send_sheet.md` and work down it (for the 7 email targets, `python -m core.mailmerge permit-radar --eml <folder>` writes Thunderbird drafts with the PDF attached). Mark Done with how many were sent and paste replies here. If you want something else confirmed first (open the app in `lanes/permit-radar/app/`, read the PDF, change the wording), write what in the Done notes and skip the send; the next tick acts on it. Still waiting on Detroit's commercial-use answer; license stays 3/5 until it arrives.

## recall-checks

- [x] **Send G2 outreach** (2026-10-24): 19 dealers, template approved by Nick 2026-10-24 (HTML card, free 6-month trial, no prices). (a) 4 with email: finished drafts on the Desktop in `Outreach to send _(DONE via FROM_NICK 2026-10-25 17:33)_
ecall-checks` (Top Auto Sale, Grand Auto Sales Lot, Gear One, Affordable Auto Sales of Michigan). Double-click `OPEN THESE 4 IN THUNDERBIRD.cmd`, check each, click Send. (b) 14 with a web contact form: `lanes/recall-checks/outreach/send_sheet.md` has the link and the form text per dealer (copy, click, paste; about 2 minutes each). (c) Victory Motors (Royal Oak) is walk-in or phone only. When done, mark this Done with who was sent and when; paste replies here as they arrive (they go to outreach/replies.md).
- [x] **Decide on the smaller product** (2026-10-24): NHTSA has no public VIN-level "is this recall still open" API; only year/make/model exposure is possible for free. The sheet and emails already say so. If you want true open/closed status, that means a paid data deal (Carfax/AutoCheck/Recall Masters-class) and the lane should be re-scored, not built on the free data. _(DONE via FROM_NICK 2026-10-24 07:45)_
- [x] **Half of the targets have no dealer website** (2026-10-24): 9 of 20 contact URLs are CarEdge/KBB/BBB/lender listing pages. Nick must find the dealer's own contact form or walk in; several are on Dixie Hwy in Waterford, a 25-minute loop from Royal Oak. _(DONE via FROM_NICK 2026-10-24 08:17)_

## site-selection

- [x] **Get a free Census API key** (2026-10-25): Census data queries now require a key (keyless returns "Missing Key"). Sign up (free, emailed instantly) at https://api.census.gov/data/key_signup.html, then add it as an environment secret named `CENSUS_API_KEY` for the tick environment. Paste the key nowhere else. Say Done when set; the next tick finishes G0. _(DONE via FROM_NICK 2026-10-25 19:49)_

## storm-lead

- [x] **Send G2 outreach** (2026-10-24): 20 roofers and storm-restoration contractors, none with a published email, all web contact forms. Template rewritten in Nick's voice 2026-10-24. Work down `lanes/storm-lead/outreach/send_sheet.md` (form link + text per company). If a contact gives an email, add it to `outreach/targets.csv` and rerun `python -m core.mailmerge storm-lead --eml <folder>`; attach both `samples/storm_lead_alert.pdf` and `samples/storm_lead_alert_example_big_day.pdf` when you reply with the sample. Mark Done with how many were sent; paste replies here. _(SKIPPED via FROM_NICK 2026-11-01 18:22)_
- [x] **Also attach** `lanes/storm-lead/samples/storm_lead_alert_example_big_day.pdf` (Sep 3, 2026: 46 reports, 15 counties). Folded into the Send G2 outreach item: all 20 targets are web forms with no attachment box, so the sample goes out only when a contact replies with an email, and then both PDFs go together. _(folded into Send G2 outreach 2026-10-24)_

- [ ] **Storm Lead checked end to end; send the outreach when you are satisfied** (2026-11-01): You asked to confirm everything works before outreach. Checked tonight: the data refresh ran clean (no Michigan storms on Oct 31, so the alert correctly shows the latest storm day, Oct 7), the live NWS warnings feed answered, the prototype passed `core.webapp check`, and the send sheet regenerated with 20 web-form targets. Nothing failed and nothing has been sent. One fact to weigh: the two-year backtest shows no qualifying Michigan storms from November to February, so a free trial started now sends nothing until about March; the outreach still tells us who is interested. To send: work down `lanes/storm-lead/outreach/send_sheet.md`; when a contact replies with an email, attach both `samples/storm_lead_alert.pdf` and `samples/storm_lead_alert_example_big_day.pdf`. Mark Done with how many were sent and paste replies here. If you would rather wait for spring or check something else first, say so in the Done notes and skip.

## weather-trigger-jobs

- [x] **Send G2 outreach** (2026-10-29): 14 landscapers, paving/sealcoat firms, tent rental companies and outdoor venues (roofers left out, they overlap storm-lead). None has a published email, so work down `lanes/weather-trigger-jobs/outreach/send_sheet.md`: each entry has a link (several are directory listings, so find the company's own contact form) and the text to paste. If a contact gives an email, add it to `email` in `outreach/targets.csv` and run `python -m core.mailmerge weather-trigger-jobs --eml <folder>` for a draft with `samples/job_day_outlook.pdf` attached. Mark Done with how many were sent; paste replies here. _(SKIPPED via FROM_NICK 2026-11-01 18:22)_

