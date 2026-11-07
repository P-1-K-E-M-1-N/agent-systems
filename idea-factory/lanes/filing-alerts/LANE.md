# Filing Alerts (SEC EDGAR)

**Type:** revenue  |  **Queue order:** 10

Niche filing alerts, e.g. Michigan companies' 8-Ks.

## Current state

(see lane.json; board regenerates ops/STATUS.md)

## G0 Data check

**Result: PASS (2026-10-30).** Source `sec_edgar` registered in `lanes/filing-alerts/sources.json` before fetching.

- License: US Government work / public record; no reuse restriction. Fair-access rules: declared User-Agent with contact, max 10 req/s (we run ~3/s). commercial_ok = true.
- Real requests through `core.fetch.Fetcher`: (1) `browse-edgar?action=getcurrent&type=8-K&output=atom` returned the live 8-K feed stamped the same morning; (2) `data.sec.gov/submissions/CIK0000037996.json` (Ford) returned name, SIC code, state, addresses, tickers and recent filings; (3) `browse-edgar?action=getcompany&State=MI&type=8-K&output=atom` returned the list of Michigan-based registrants (CIK + state).
- Freshness: filings appear within minutes; fits a daily or even hourly alert.
- What the data can do: filter registrants by state/SIC, list new 8-Ks (and other forms) per company, link to the filing. Company data only, no people data (we ignore insider/Form 4 names).
- What it cannot do: the company-search atom feed gives CIKs but garbled names (needs the submissions API per CIK to get names, SIC, city), so building a Michigan list means one call per CIK, paged 100 at a time; fine within budget but the first build takes a few hundred calls. 8-K item codes (e.g. 1.01, 5.02) are in the submissions JSON, so event-type filtering is possible.
- Competition risk to check at G2: SEC offers free email/RSS alerts per company and many paid tools exist (sec-api, Seeking Alpha, etc.). The niche (regional/industry slice, plain-language summary) is the only wedge. Not yet evaluated.
- Time: about 10 minutes.

## G1 Prototype

**Blocked (2026-10-31 tick), nothing fabricated.** Real request to `data.sec.gov/submissions/CIK0000037996.json` through core.fetch returned HTTP 403 with SEC's page "Undeclared Automated Tool": the factory User-Agent has no contact email, which SEC's fair-access policy requires. (`www.sec.gov` atom feeds do answer 200 when the header carries a contact.) Fix is a per-source User-Agent with a real contact address; that is Nick's call (needs_nick.md). G0's earlier pass stands on the feed evidence; the submissions API needs the contact header. Then G1 = Michigan 8-K feed web app.

**G1 PASS (2026-11-04 tick).** Built `app/` (index.html, app.js on the shared tokens; both themes, phone-first, installable) and `refresh.py`. The app is a Michigan 8-K feed: filings grouped by day, plain-words translation of SEC item codes, filters (Deals, Money, Leadership, Earnings, Trouble), search, and a device-local Follow list. Each card links to the filing on sec.gov. `refresh.py` also writes `samples/michigan_8k_digest.{csv,html,pdf}` (the outreach attachment). `python -m core.webapp check filing-alerts` prints OK; screenshots at 390px and 1000px dark rendered with no script errors. No map: a filings feed does not need one.

Real data: 13 Michigan companies, 22 8-Ks in the last 45 days (e.g. GM, Cooper-Standard, Workhorse, Rockwell Medical).

What the data can and cannot do:
- EDGAR's plain Michigan list is mostly LLC shells and funds, so discovery scans Michigan by industry code (SIC) instead. Only 70 of 177 industry codes and 165 companies were covered this run: the 400/day SEC request budget ran out (earlier probing used part of it). `data/registry.json` caches per-company results, and the daily refresh tops up the rest, so coverage grows over the next ticks; the app states coverage in its "What this is" box.
- Item codes are translated into plain words; that is not a summary of the document.
- SEC already offers free per-company email/RSS alerts; the wedge is the Michigan-wide, plain-language view. Competition is still unevaluated (G2).
- Company data only; no insider or individual names.

## G2 Demand test

**Started 2026-11-05 tick; target list is the blocker, nothing fabricated.** Searched public listings for who would pay for a Michigan-wide plain-language 8-K feed. Findings: (a) Michigan securities lawyers in FindLaw/LawInfo are mostly investor-side (fraud recovery), not buyers; the one issuer-side firm surfaced was Bodman PLC (Detroit/Ann Arbor/Troy/Grand Rapids). (b) Michigan investment firms with a small-cap angle: Seizert Capital Partners (Birmingham), Monument MicroCap Partners (Bloomfield Hills), Quarton Capital Partners (Birmingham), Schechter Investment Advisors (Birmingham); their needs are unconfirmed. (c) No Michigan-based investor-relations firm for small caps turned up; the IR firms found are out of state. That is 5 plausible names, not 10-20, and none has a verified contact page. Competition note: SEC's own free per-company email/RSS alerts plus paid tools already exist, so the wedge is only the Michigan-wide plain-language view. Not enough to draft outreach honestly; asked Nick who the buyer should be (needs_nick.md). Traffic angle (keyword test) is the alternative if no paying buyer is credible.

## G3 Decision

_pending_

## SEC access fixed (2026-11-01)

Acted on FROM_NICK 2026-11-01 18:22 (entry cbbb5455dd46): Nick chose `nickolasrlektzian+ideafactory@gmail.com` as the contact address for SEC requests. `core/fetch.py` now honours a per-source `user_agent` field (small, general change; the global User-Agent is unchanged for every other source) and `lanes/filing-alerts/sources.json` sets it for `sec_edgar` with that address. Verified: `data.sec.gov/submissions/CIK0000037996.json` returned HTTP 200 (160 KB) through `core.fetch` where it returned 403 on Oct 31. Lane back to active; next tick builds the G1 prototype (Michigan 8-K feed web app).

## Log

- 2026-10-30T11:06:32+00:00 G0 started. SEC EDGAR data check
- 2026-10-30: G0 pass. SEC EDGAR live and free; Michigan list via State=MI works. Next: G1 prototype.
- 2026-10-30T11:06:57+00:00 G0 finished: pass. SEC EDGAR live, public domain, MI state filter + submissions API work
- 2026-10-30T11:06:58+00:00 status -> active. blocker: . next: G1 prototype (web app: Michigan 8-K feed)
- 2026-10-31T11:06:16+00:00 status -> waiting_nick. blocker: SEC blocks our requests (403 'Undeclared Automated Tool'): needs a contact email in the User-Agent. Nick picks the address.. next: Add contact to SEC User-Agent, then build G1 prototype
- 2026-10-31 tick: G1 blocked on SEC User-Agent contact; set waiting_nick, asked Nick for a contact email. Tick time went to site-selection G1.
- 2026-11-01T23:55:34+00:00 FROM_NICK 2026-11-01 18:22 (SKIPPED, entry cbbb5455dd46): "Choose a contact email for SEC requests". Box ticked: yes. Filed: from_nick/2026-11-01_1822_cbbb5455dd46.md. Notes: (none) Lane set back to active: no open Nick items left. Tick agent: continue this lane from these notes.
- 2026-11-02T00:01:04+00:00 status -> active. blocker: . next: G1 prototype: Michigan 8-K feed web app (SEC access confirmed with contact User-Agent 2026-11-01)
- 2026-11-02T00:01:31+00:00 status -> active. blocker: . next: G1 prototype: Michigan 8-K feed web app (SEC access confirmed with contact User-Agent 2026-11-01)
- 2026-11-04T11:17:02+00:00 G1 started. Michigan 8-K feed web app

- 2026-11-04 tick: G1 built and passed (no FROM_NICK entries to act on today). Next: G2 demand test (needs a verified list of Michigan target businesses).
- 2026-11-04T11:25:52+00:00 G1 finished: pass. Michigan 8-K feed web app on live SEC data; 13 companies/22 filings, coverage still growing; webapp check OK

- 2026-11-05 tick: G2 started; only 5 plausible unverified targets found, no outreach drafted. Asked Nick to pick the buyer or switch to a keyword test. No FROM_NICK entries to act on.
- 2026-11-05T11:16:57+00:00 G2 started. demand test: find buyers
- 2026-11-05T11:16:57+00:00 status -> waiting_nick. blocker: Nick to pick the buyer segment for Michigan 8-K alerts (no verified target list). next: Draft outreach or run keyword test per Nick's answer
