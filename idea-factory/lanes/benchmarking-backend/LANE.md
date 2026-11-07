# Benchmarking Compliance Backend

**Type:** revenue  |  **Queue order:** 6

ENERGY STAR Portfolio Manager web services; access requires approval, so draft the request for Nick.

## Current state

(see lane.json; board regenerates ops/STATUS.md)

## G0 Data check

**Result: license PASS, access still blocked on an account (updated 2026-11-01).**

- 2026-10-25 tick: `portfoliomanager.energystar.gov` reachable; `/ws/account` returns 401 unauthenticated; no public data exists to fetch without a web-services account.
- 2026-11-01 (FROM_NICK entry 60be9f3aaedc, SKIPPED with notes): the Web Services API Terms of Use (Sept 2026) were read on Oct 28. The API is free for organizations exchanging building data with Portfolio Manager, including on behalf of customers, and nothing bans a paid service. Obligations: build in the test environment first, respect rate limits, follow the ENERGY STAR brand book. `sources.json` now records `commercial_ok = true` with the terms PDF. There is no request form or email to send, so the drafted request is withdrawn.
- What remains: EPA's process is self-service. A free TEST account at https://portfoliomanager.energystar.gov/pmtest (Account Settings > Software Development > enable web-services testing) is approved instantly and gives a test API at `/wstest/`. Live provider access is requested from inside the live account after testing. The factory may not create accounts (CLAUDE.md rule 2), so this is Nick's five-minute step, or the lane parks.
- G0 passes the moment test credentials exist as environment secrets for the tick; G1 is then a prototype against the test API with sample buildings.

## G1 Sample

_pending_

## G2 Demand test

_pending_

## G3 Decision

_pending_

## Log
- 2026-10-24 tick: promoted; G0 blocked by network policy on portfoliomanager.energystar.gov. Nothing fabricated.
- 2026-10-25T11:03:58+00:00 G0 started. data check
- 2026-10-25 tick: G0 blocked, PM web services 401 until EPA approval; drafted request for Nick.
- 2026-10-25T11:04:39+00:00 status -> waiting_nick. blocker: Nick must request EPA Portfolio Manager provider access. next: Wait for EPA answer, then re-check G0 license
- 2026-11-01T23:55:34+00:00 FROM_NICK 2026-11-01 18:20 (SKIPPED, entry 60be9f3aaedc): "Request ENERGY STAR Portfolio Manager web-services provider access". Box ticked: yes. Filed: from_nick/2026-11-01_1820_60be9f3aaedc.md. Notes: 2026-10-28 (factory read EPA docs): Web Services API Terms of Use say the API is a free application for organizations exchanging building data with Portfolio Manager, including on behalf of customers; no restriction on commercial/paid services found. Test environment is self-service: create account at https://portfoliomanager.energystar.gov/pmtest, enable API under Account Settings > Software Development; test API base https://portfoliomanager.energystar.gov/wstest/. LIVE approval is requested later via the online form on the same tab in the live account. Terms PDF: https://portfoliomanager.energystar.gov/pdf/reference/Web%20Services%20API%20Terms%20of%20Use.pdf Lane set back to active: no open Nick items left. Tick agent: continue this lane from these notes.
- 2026-11-02T00:01:04+00:00 status -> waiting_nick. blocker: Nick to create the free Portfolio Manager TEST account and store test credentials as environment secrets (or park). License resolved 2026-11-01: commercial use OK.. next: On Done: pass G0 with a real test-API call, then G1 prototype against /wstest/
- 2026-11-02T00:01:32+00:00 status -> waiting_nick. blocker: Nick to create the free Portfolio Manager TEST account and store test credentials as environment secrets (or park). License resolved 2026-11-01: commercial use OK.. next: On Done: pass G0 with a real test-API call, then G1 prototype against /wstest/
