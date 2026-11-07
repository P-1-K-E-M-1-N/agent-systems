# Supplier News Monitor

**Type:** revenue  |  **Queue order:** 11

Supplier news monitor from GDELT.

## Current state

(see lane.json; board regenerates ops/STATUS.md)

## G0 Data check

Source: GDELT 2.0 DOC API (registered in lanes/supplier-news/sources.json). Real requests via core.fetch.Fetcher on 2026-11-01.
- Works: no key needed, JSON, 15-minute updates, newest article seen was 7 days old at query time with a 7-14 day window, so freshness fits a daily digest.
- License: GDELT states unrestricted commercial use with citation (commercial_ok=true). Publishers own article text; we would only keep title, URL, domain, date.
- Signal: query "(plant closure OR layoffs OR bankruptcy) Michigan" returned 25 hits, including a real one ("Automotive supplier closing both locations in Auburn Hills", Oakland Press) and "Ford supplier cuts jobs in Michigan". Named-company queries are thin ("Lear Corporation" gave 1 result, a stock-ticker spam page).
- Weak spots: precision is low (about 1 in 4 results is a real supplier event; the rest is general news, tariffs, restaurants), needs company-name filtering and de-duplication. OR terms must be wrapped in parentheses. Titles are not always reliable for company extraction.
- Verdict: data check PASSES, but the product needs a watchlist of supplier names from the customer plus filtering; value vs. Google Alerts (free) is the open demand question for G2.

## G1 Sample

2026-11-02 tick: prototype built, NOT yet passed. app/ (Supplier News Monitor: event-type chips, search, Michigan-only, a device-local watchlist, hide-row, both themes, phone layout) and refresh.py are written. The first live run returned nothing: my first query wording ("(automotive supplier)" in parentheses, then a quoted "auto supplier" phrase) was rejected or empty on GDELT, and by the time I switched back to the G0-style wording GDELT answered HTTP 429 (too many requests from repeated reruns). Queries are now in the G0 style. Next tick: let refresh.py run once (about 4 minutes at ~14 s per query), check the result has real rows, run `python -m core.webapp check supplier-news`, then finish G1. Do not rerun refresh repeatedly; it is rate limited.

2026-11-03 tick: still NOT passed. Ran refresh.py twice (inside tick.py it timed out after GDELT's slow answers; run alone it got 0 articles for all 6 topic queries). Cause: GDELT is throttling this machine ('one request every 5 seconds' notice, HTTP 429), so even simple queries return the throttle text, not data; the 2026-11-02 reruns probably started it. Fixes made: removed 'ZF' from the watchlist (GDELT rejects phrases under 4 letters and that sank a whole batch) and refresh.py now refuses to overwrite app/data with an empty result. No app/data exists yet, so `webapp check` cannot pass. Next tick: run refresh.py once, early, after a quiet day; if GDELT still throttles, consider spacing queries 6+ seconds apart in the script.

## G2 Demand test

_pending_

## G3 Decision

_pending_

## Log

- 2026-11-01T11:03:56+00:00 G0 started. GDELT DOC API: works, license, freshness, signal quality for supplier news

- 2026-11-01 tick: G0 pass (GDELT usable, commercial ok, noisy). Next: G1 prototype.
- 2026-11-01T11:08:23+00:00 G0 finished: pass. GDELT DOC API live, free commercial use, 15-min updates; ~25% precision on supplier events, needs filtering
- 2026-11-01T11:08:23+00:00 status -> active. blocker: . next: G1 prototype

- 2026-11-02 tick: G1 started and prototype files written; live data run failed on query wording then GDELT 429. G1 left open for tomorrow.
- 2026-11-02T11:27:35+00:00 G1 started. prototype web app; data run pending (GDELT 429)
- 2026-11-03 tick: G1 still open; GDELT throttling gave 0 articles. refresh.py hardened (no empty overwrite, dropped 'ZF').
