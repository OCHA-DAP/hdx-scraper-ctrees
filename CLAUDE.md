# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**hdx-scraper-ctrees** publishes annual, 100m-resolution Aboveground Biomass (AGB) data from
[CTrees](https://ctrees.org), a NASA-affiliated forest-carbon monitoring organization, as one HDX
dataset per active HDX Data Grid country.

The source is CTrees' global AGB raster, mirrored as public (no-auth) Cloud-Optimized GeoTIFFs
(COGs) in an AWS Open Data S3 bucket, one file per year. For each active Data Grid country, the
pipeline looks up the country's admin1 bounding box from HDX's own `cod-ab-global` boundaries
dataset, reads a windowed slice of that year's global AGB COG (via GDAL's `/vsicurl/` streaming —
only the relevant byte ranges are fetched, never the whole ~38GB file), and uploads the clipped
slice as a per-country COG resource.

Initial build scope: latest year only (2025), AGB only (CTrees' separate Land Use Change Alerts
product is out of scope).

## Key Files

- `src/hdx/scraper/ctrees/__main__.py` — orchestration entry point (`main()`): fetches Data Grid
  countries, downloads/extracts the `cod-ab-global` boundaries once per run, then loops per country
  with explicit try/except isolation (one bad country must not abort the batch).
- `src/hdx/scraper/ctrees/pipeline.py` — `Pipeline` class: `get_data_grid_countries()`,
  `get_country_raster()` (windowed COG read + clip + write), `generate_dataset()` (HDX
  `Dataset`/`Resource` construction).
- `src/hdx/scraper/ctrees/boundaries.py` — `cod-ab-global` boundary download/extraction and
  per-country bbox lookup (`download_admin1_boundaries()`, `get_country_bbox()`). Isolated from
  `pipeline.py` since it has no HDX pipeline precedent elsewhere.
- `src/hdx/scraper/ctrees/config/project_configuration.yaml` — source COG URL template, AGB scale
  factor/fill value, `cod-ab-global` dataset/resource ids, latest year, tags.
- `src/hdx/scraper/ctrees/config/hdx_dataset_static.yaml` — static metadata applied to every
  country dataset (org/maintainer, license, notes, caveats).

## Design rationale & background

`docs/plans/2026-07-31-hdxpipe-100-ctrees-initial-build.md` is the working analysis document for
this build —
requirements, template comparison, design decisions, and a running log of implementation findings
(e.g. why the output is int16+ZSTD rather than float32, the resource/dataset-level notes about the
scale factor, and the still-open DR Congo file-size problem). Consult it for *why* something is
built the way it is, especially anything marked "interim"/"revisitable" or an open decision.

It's a point-in-time record of decisions and measurements, not a live spec — if it conflicts with
the current code or config, the code wins; treat a stale-looking claim there as a signal to update
the doc, not as ground truth to defer to.

Non-trivial design decisions and implementation plans made from here on are recorded in
`docs/decisions/` (see `docs/decisions/README.md`), rather than added to
`docs/plans/2026-07-31-hdxpipe-100-ctrees-initial-build.md`.

## Running

```bash
uv run python -m hdx.scraper.ctrees
```

Requires these files in `$HOME`:
- `.hdx_configuration.yaml` — HDX API key and site config
- `.useragents.yaml` — user agent config with key `hdx-scraper-ctrees`

Or set environment variables: `HDX_KEY`, `HDX_SITE`, `USER_AGENT`, `EXTRA_PARAMS`, `TEMP_DIR`,
`LOG_FILE_ONLY`.

Development flags (passed to `main()`):
- `save=True` — save downloaded data to `saved_data/` instead of `/tmp`
- `use_saved=True` — load from `saved_data/` instead of hitting live sources

## Testing

```bash
uv run pytest
```

Tests live in `tests/test_pipeline.py` and `tests/test_boundaries.py`, against fixtures in
`tests/fixtures/input/` (a real captured AGB slice, a synthetic boundary GeoJSON standing in for
the ~1GB real `cod-ab-global` GDB, and a saved Data Grid `group_list` response) — no live network
calls in CI.

## Code Style

- Formatted with `ruff` via pre-commit hooks. After changing any Python code, run:

```bash
pre-commit run --all-files
```

- Python ≥ 3.13

## Collaboration Style

- Be objective, not agreeable. Act as a partner, not a sycophant. Push back when you disagree, flag tradeoffs honestly, and don't sugarcoat problems.
- Keep explanations brief and to the point.
- Don't rely on recalled knowledge for facts that could be stale (API behaviour, library versions, external systems). Search or read the actual source first. If you lack verified information, say so rather than speculate.

## Scope of Changes

When fixing a bug or addressing PR feedback, change only what is necessary to resolve the specific issue. Do not refactor surrounding code, rename variables, adjust formatting, or make improvements in the same commit unless they are directly required by the fix. Unrelated changes obscure the intent of the fix and complicate review and blame.
