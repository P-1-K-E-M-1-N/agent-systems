# Satellite Change Alerts

**Type:** revenue  |  **Queue order:** 9

Change alerts for land owners and farmers from Copernicus Sentinel-2.

## Current state

(see lane.json; board regenerates ops/STATUS.md)

## G0 Data check

**Result: PASS (2026-10-26 tick).** Source: Element 84 Earth Search STAC (Sentinel-2 L2A COGs on AWS Open Data), no key. Real request through core.fetch.Fetcher returned the three newest scenes over Detroit (tile 17TLH): 2026-10-25 (86% cloud), 2026-10-23 (0.01%), 2026-10-20 (0.04%), with band assets (blue, green, nir, scl, etc.). Freshness: about 1-2 days; revisit about 5 days per tile, so alerts are weekly-ish, not daily.
License: Copernicus Sentinel data is free and open for any use including commercial; attribution "Contains modified Copernicus Sentinel data." Registered in sources.json.
Limits to be honest about: 10 m pixels (cannot see individual trees or small structures); cloud cover blocks many scenes in Michigan winter; change detection (NDVI differences) needs reading COG pixels, standard library only means no numpy or GeoTIFF decoder, so G1 must use pre-rendered preview/thumbnail assets or coarse overview reads. That is a real G1 risk. Parcel-level owner data would be people data and is out of scope: areas of interest are user-drawn boxes or public land/business sites only.

## G1 Sample

_pending_

## G2 Demand test

_pending_

## G3 Decision

_pending_

## Log

- 2026-10-26T11:07:14+00:00 G0 started. data check

- 2026-10-26 tick: G0 pass (Earth Search STAC, real scenes returned).
- 2026-10-26T11:07:27+00:00 G0 finished: pass. Sentinel-2 STAC returns fresh scenes keylessly; open license; 5-day revisit; stdlib pixel-read risk noted
- 2026-10-26T11:07:27+00:00 status -> active. blocker: . next: G1 prototype
