# 0007: Publish for all GHO countries instead of Data Grid countries

## Status

Accepted — 2026-09-29

## Context

The initial build published one dataset per active HDX Data Grid country (22 countries,
from `Location.get_data_grid_countries()`). Coverage was requested for all locations in the
Global Humanitarian Overview (GHO).

## Decision

Take the country list from the "In GHO" column of hdx-python-country's OCHA countries feed
(`Country.countriesdata()`), giving 55 countries as of 2026-09-29. All 22 Data Grid countries
are in it.

## Consequences

- Added countries include several larger than DR Congo (e.g. Brazil, Argentina, Mexico, Iran),
  so more countries are likely to exceed the upload limit noted in `CLAUDE.md`. Per-country
  isolation (`0004`) keeps these from aborting the run.
- The list follows the OCHA countries feed, so GHO membership changes are picked up without a
  code change.
