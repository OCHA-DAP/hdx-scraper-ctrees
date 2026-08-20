# 0002: Source country bounding boxes from HDX's own cod-ab-global dataset

## Status

Accepted — 2026-08-03

## Context

Country-level clipping needs a bounding box per country. The closest
existing HDX pipeline precedent, `hdx-floodscan`, gets country shapefiles
from an internal Azure blob store ("stratus") that this pipeline has no
access to — no other HDX pipeline convention was found for sourcing country
boundaries from outside OCHA-DAP-internal storage.

## Decision

Fetch HDX's own `cod-ab-global` dataset (`package_show`, org `hdx`, license
`cc-by-igo`), download the `global_admin_boundaries_matched_latest.gdb.zip`
resource once per run, extract it into a manually-named `*.gdb` directory
(its zip has no wrapping `.gdb`-suffixed folder, which GDAL's OpenFileGDB
driver requires to recognize it), open the `admin1` layer (no `admin0`
layer exists in this file), filter by ISO3, and take `total_bounds` of the
matching rows.

## Consequences

No existing pattern-catalog precedent for this approach — isolated into its
own `boundaries.py` module so it's independently testable and reusable by
future pipelines needing the same country-bbox source. Downloaded once per
run and filtered locally for all countries (not per-country), since the
file (~1-1.3GB) is global. A bounding-box (not exact-polygon) clip can
inflate a country's effective extent when its admin1 set includes distant
offshore territory (e.g. Colombia's San Andrés archipelago, ~700km from the
mainland) — a known, structurally fixable source of oversized output for a
handful of countries.
