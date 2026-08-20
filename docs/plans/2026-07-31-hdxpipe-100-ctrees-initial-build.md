# HDXPIPE-100 — HDX Pipeline: CTrees — Stage 1-3 Analysis

Saved 2026-07-31, revised 2026-08-03 (three times). Produced by the `hdx:pipeline-builder` skill.

**Five decisions from this document have been extracted as formal decision
records in `docs/decisions/`** (0001 data source, 0002 boundary source, 0003
raster encoding, 0004 per-country failure isolation, 0005 nodata masking).
This document remains the full narrative/working-analysis record; the
`docs/decisions/` files are the distilled, durable versions of its
already-settled decisions.

**Checkpoint 1: approved 2026-08-04** ("Implement option B").
Jira ticket: https://humanitarian.atlassian.net/browse/HDXPIPE-100
Answers used in this revision: https://humanitarian.atlassian.net/browse/HDXPIPE-100?focusedCommentId=289733
(Briar Mills, 2026-07-31), plus the user's direct decisions on Checkpoint 1's questions
(2026-08-03 and 2026-08-04, in-conversation, not yet posted to Jira).

## Status

**Checkpoint 1 is approved.** All six Checkpoint-1-era questions now have decisions (org/
maintainer, metadata-form placeholders, backfill depth, output form, country-boundary source, and
now source option — see 1.3/3.3/3.8 below). Proceeding to Stage 4 (Implementation Plan).

**2026-08-03: Arraylake access verified end-to-end** using Michael Rans' personal account —
successfully read the real `aboveground_biomass` zarr group (confirmed exact array shapes,
chunking, CRS, and the true 2000-2025 time range; see 3.3, Option A).

**2026-08-03: a second source option surfaced and was verified.** CTrees confirmed the same AGB
data is also available with zero auth as annual global COGs in a public AWS Open Data S3 bucket
(`s3://ctrees-agb-100m-global/cogs/`), independently verified this session (see 3.3, Option B) —
same underlying data as Option A for the test slice, no auth/secrets story at all.

**2026-08-04: decided — Option B (public S3 COG mirror).** The user chose Option B over Option A.
This drops the `arraylake`/`zarr` dependency and the entire service-account-token/Bitwarden-secret
story from the build; see 3.3/3.6/3.8 for the resulting updates. Option A remains documented below
for historical/comparison context only — it is not the build target.

---

# Stage 1: Requirements Summary

## 1.1 Plain-English Summary

CTrees (a NASA-affiliated forest-carbon monitoring org) has a **Global Aboveground Biomass (AGB)**
dataset the team wants to bring onto HDX: an annual 100m-resolution global raster, updated yearly
from 2000 to present, served as a **Zarr array store via the Arraylake (Earthmover) marketplace**
— not a plain GeoTIFF-download REST API as originally assumed. CTrees also has a second product,
**Land Use Change Alerts (LUCA)** — deferred, out of scope for this build. The full CTrees AGB
archive is 4.26 TB, so coverage must be limited to a subset of "priority countries" — now resolved
to mean HDX's own **Data Grid** countries, obtainable programmatically (see 3.3).

The repo (`OCHA-DAP/hdx-scraper-ctrees`) already exists on GitHub, created by Briar Mills, and has
already been through `copier copy` scaffolding plus a hand-written stub `Pipeline` class that
imports `arraylake`/`zarr` and opens the CTrees Zarr store root — confirming the API choice in
code, not just in the ticket comment.

## 1.2 Extracted Requirements

**Functional**
- Ingest CTrees AGB data from the Arraylake (Earthmover) marketplace Zarr store
  (`ctrees/aboveground_biomass_100m_global_open`) for HDX's active Data Grid countries.
- Slice the global Zarr array per country (xarray bounding-box selection, not a REST per-country
  download) and write out per-country raster resource(s).
- LUCA is explicitly out of scope for this initial build.

**Non-functional**
- Must handle a very large total source dataset (4.26 TB) — Data Grid country scoping is the
  agreed mechanism for limiting this, no longer an open question.
- First run likely long-running given scale even after country filtering; subsequent annual runs
  shorter.

**Data source requirements**
- Arraylake Marketplace, listing: https://app.earthmover.io/marketplace/69e00e1c21faca8bf36879d2
  Confirmed correct by Briar Mills (2026-07-31, answer 1).
- Requires an Arraylake account with "programmatic access authorization" (exact mechanism TBD —
  `client.login()` in the existing stub, likely a device/browser auth flow or API token issued
  once the account exists). CTrees will provide sample code once an account exists. Technical
  contact: Naomi Provost (nprovost@ctrees.org).
- Not yet confirmed as actually working end-to-end — account creation/authorization is still a
  pending action, not a completed step.

**Data target requirements**
- "HDX org page to host the data: n/a" — **still explicitly unresolved**, no update in the latest
  comment thread.

**Transformation requirements**
- Confirmed: the AGB data is a global Zarr array (not pre-clipped per country, not GeoTIFF
  tiles). Country extraction = xarray bounding-box slice against the array, following the pattern
  in `hdx-floodscan`'s `clip_last90_days_files` (`floodscan.py:349-354` at commit `bea4ea4`):
  ```python
  ds_clip = ds.sel(x=slice(minx, maxx), y=slice(maxy, miny))
  ds_clip.rio.to_raster(out_file, driver="COG")
  ```
  **Gap still open:** `hdx-floodscan` gets country bounding boxes from an internal Azure blob
  store of shapefiles (OCHA-DAP-specific "stratus" infra) that this pipeline doesn't have access
  to. CTrees needs its own boundary/bbox source — no existing HDX pipeline convention was found
  for this during this pass (see Stage 2 capability gap and Checkpoint 1, question 5).
- Whether users want raw per-country GeoTIFF or a summarized/aggregated form is still unanswered
  by CTrees/DPT (Checkpoint 1, question 4).

**Scheduling requirements**
- Implied annual, matching AGB's annual update cadence — not explicitly confirmed.

**Backfill requirements**
- Still unresolved: full 2000-present history per country, or latest-year-only for initial load.
  Briar: "I think that's a question for [Anthony] and might depend on the size of the resulting
  country files" (2026-07-31) — i.e. this may only be answerable after we've actually sliced a
  sample country and measured output size.

**Monitoring/alerting requirements**
- None specified beyond the standard HDX pipeline DoD.

**Security/access requirements**
- Arraylake auth mechanism still to be confirmed once an account is created. Secrets go into
  Bitwarden once known, per DoD.

**Testing requirements**
- Standard HDX fixture-replay pattern already scaffolded (`tests/conftest.py`,
  `tests/test_pipeline.py`) but currently empty/placeholder. No real Zarr sample data captured
  yet — blocked on Arraylake account/access.

**Deployment requirements**
- Per ticket's DoD: repo on GitHub (done), DSys added as repo admin, complete README, secrets in
  Bitwarden, p-coded resources flagged if any, tests written, GH Actions + Jenkins deployment,
  running on prod, partner + Beryl (DPT) review/approval, added to pipeline directory.

## 1.3 Ambiguities and Missing Information

| # | Question | Status | Why it matters | Decision | Risk if wrong |
|---|---|---|---|---|---|
| 1 | Is this Epic greenlit for this cycle? | **Self-resolved by action** — Michael Rans picked this up 2026-07-30, superseding the pending DSci-priority check from 2026-07-28 | N/A | Proceed | Low — no code written yet if this changes |
| 2 | CTrees AGB API details | **Resolved** — Arraylake/Earthmover marketplace, Zarr format, account + auth still to be arranged | — | — | — |
| 3 | "Data grid countries" list | **Resolved** — HDX's own Data Grid, fetched via `group_list?all_fields=true&include_extras=true` filtered on `data_completeness=="active"` (22 countries as of 2026-08-03; see 3.3) | — | — | — |
| 4 | Per-country-clipped or global raster? | **Resolved (directionally)** — global Zarr array, we clip via xarray bbox slice | Determines raster-processing design | xarray bbox clip per `hdx-floodscan` pattern | — |
| 5 | Full history vs latest-year-only | **Decided** (2026-08-03, user) | 4.26 TB total source | **Latest year only to start, revisit later** — treat as an explicit interim scope, not a final answer | Low — explicitly flagged as revisitable |
| 6 | `dataset_organization` / `dataset_maintainer` | **Decided** (2026-08-03, user) | Blocks `hdx_dataset_static.yaml` | **`owner_org: hdx`, `maintainer: 196196be-6037-4488-8b71-d786adf4c081`** (Michael Rans) — explicitly interim, updatable later once CTrees/DPT confirm a permanent org | Low if changed later — reassigning org/maintainer on an existing HDX dataset is a routine metadata edit |
| 7 | HDX Metadata form completed? | **Confirmed NOT done**; **decided to proceed with placeholders** (2026-08-03, user) | Ticket's own DoD lists this as a precondition | Keep copier-default placeholders (`license_id: cc-by`, `methodology: Other`, blank `caveats`) explicitly marked interim; DoD item to complete the real form remains open at the ticket level | Low — placeholders are visibly interim, not silently wrong |
| 8 | Raw GeoTIFF or summarized/aggregated output? | **Decided** (2026-08-03, user) | Changes transformation design and dependency needs | **Start with per-country GeoTIFF**; revisit/change later if it doesn't work well | Low — explicitly flagged as revisitable |
| 9 | One global dataset vs one per country? | **Resolved (leaning)** — Briar: "file size/number may force us to only provide country level datasets" | Affects `Pipeline` structure | One dataset per country | Rework if final file sizes change this |
| 10 | Country boundary/bbox source for clipping | **Decided** (2026-08-03, user), independently verified | No HDX pipeline convention found this pass for sourcing country bounding boxes outside OCHA-DAP-internal blob storage | **HDX's own `cod-ab-global` dataset** (verified via `package_show`, org `hdx`, license cc-by-igo) — filter the `admin1` layer by ISO3, take `total_bounds` of the match as the country bbox. See 3.3 for format/size caveats. | Low — verified against live API + a working reference script (`hdx-boundaries-explorer/scripts/ocha.sh`) |

## 1.4 Assumption Register

| ID | Assumption | Evidence | Confidence | Impact if wrong |
|---|---|---|---|---|
| A1 | Initial build targets AGB only, not LUCA | Anthony Burke comment, 2026-05-28 | High | Scope change, design revisit |
| A2 | Update cadence is annual | Briar Mills comment, 2026-05-26 | Medium | Wrong `dataset_expected_update_frequency` / cron |
| A3 | Category = geospatial raster/heavy processing (catalog category 7), with a category-2-style per-country loop grafted on | Zarr array, per-country clip requirement | High | N/A — shape is clear even if scope isn't |
| A4 | Repo will NOT be nested (`hdx-scraper-ctrees` flat) since only one product is in scope now | LUCA is deferred/unapproved | Medium | If LUCA is added later, requires flat→nested migration |
| A5 | "Data grid countries" = HDX's own Data Grid (`data_completeness=="active"` country groups), not a CTrees-side or DPT-side list | Briar's comment shows DPT/DSys don't have a ready answer either — bounced the question back to us; our own CKAN research confirms this is a real, live, queryable HDX concept | High | If CTrees/DPT actually meant something else by "priority countries," coverage list is wrong |
| A6 | Repo is no longer greenfield — copier scaffold + stub `Pipeline`/`__main__.py` already exist and should be extended, not regenerated | Direct inspection of `hdx-scraper-ctrees` repo (commits "Initial commit", "Copier setup") | High | N/A |

## 1.5 Risk Register

- **Data volume risk**: 4.26 TB total source; mitigated by scoping to the 22 active Data Grid
  countries and, per the user's decision, latest-year-only for the initial load. Revisit if the
  latest-year-only per-country files still turn out to be unexpectedly large.
- **Interim dataset identity**: `owner_org: hdx` / `maintainer: <Michael Rans>` and copier-default
  `license_id`/`methodology`/`caveats` placeholders are explicit stand-ins per the user's decision,
  not CTrees-confirmed values — low risk since reassigning org/maintainer later is a routine HDX
  metadata edit, but the ticket's own DoD item (partner-completed metadata form) remains open and
  should not be considered satisfied by this interim choice.
- **Arraylake access not yet live**: account/auth still to be arranged; no real fixture data
  available yet — this is the main remaining hard dependency before real (non-synthetic) testing.
- **Country-boundary source size**: `cod-ab-global`'s geometry files are ~1-1.3GB each (global,
  admin1-4, no admin0 layer) — needs a download-once-filter-locally approach across the 22
  countries per run, not per-country downloads, and a GDB-extraction quirk (no wrapping `.gdb`
  directory in HDX's zip) needs handling, per `hdx-boundaries-explorer/scripts/ocha.sh`.
- **Output-shape risk deferred, not eliminated**: raw per-country GeoTIFF is the starting choice,
  explicitly revisitable if it doesn't work well once real data is in hand.

---

# Stage 2: Template Analysis

**Category (per `pipeline-pattern-catalog.md`): 7 — Geospatial raster/heavy processing**, with a
category-2-style per-country loop grafted on, now further narrowed to "Zarr-backed global array,
sliced via xarray per country" rather than generic GeoTIFF download+reproject.

**Repo status — revised: NOT greenfield.** `hdx-scraper-ctrees` already exists locally
(`/home/mcarans/Code/OCHA-DAP/hdx-scraper-ctrees`), pushed to
`git@github.com:OCHA-DAP/hdx-scraper-ctrees`, with two commits: "Initial commit" and "Copier
setup." The copier scaffold is done (`pyproject.toml`, `Dockerfile`, `.github/workflows/*`,
`.pre-commit-config.yaml`, `README.md`, `tests/conftest.py` all already generated and match the
current `hdx-scraper-copier` template shape). `pyproject.toml` already lists `arraylake`, `zarr`,
`hdx-python-api`, `hdx-python-country`, `hdx-python-utilities` as dependencies.

A hand-written stub already exists at `src/hdx/scraper/ctrees/pipeline.py`:
```python
class Pipeline:
    def get_data(self) -> None:
        client = Client()
        client.login()
        repo = client.get_repo(self._configuration["abg_url"])
        session = repo.readonly_session(branch="main")
        root = zarr.open_group(session.store, zarr_format=3, mode="r")

    def generate_dataset(self) -> Dataset | None:
        # all fields None, empty skeleton
```
and `config/project_configuration.yaml` already has:
```yaml
abg_url: "ctrees/aboveground_biomass_100m_global_open"
```
This confirms the Arraylake/Zarr API choice in code, independent of the ticket comment. Nothing in
the stub yet does per-country iteration, bounding-box slicing, or resource creation — all of that
remains to be designed and built.

### Primary template: `hdx-scraper-copernicus-fire` (locally inspected)
- Reusable: `Pipeline`/`__main__.py` split, config split
  (`project_configuration.yaml`/`hdx_dataset_static.yaml`), Dockerfile pattern.
- Gap: no per-country iteration, no raster clipping, no Zarr/xarray handling at all — just
  downloads and re-uploads whole GeoTIFF files.

### Secondary template: `hdx-scraper-copernicus-floods` (locally inspected)
- Multi-static-YAML-per-source pattern (`static_yaml_by_source`) — relevant if LUCA is added later
  as a second CTrees product under one pipeline.
- Anti-pattern: prefer fire's Dockerfile over floods'.

### New reference this pass: `hdx-floodscan` (remote — not checked out locally; fetched via `gh
api` at commit `bea4ea4`, per the Jira comment's link, since the repo isn't local and the skill's
rules allow remote fetch when a referenced file is only available there)
- **Relevant pattern**: `clip_last90_days_files` in `floodscan.py` — downloads country shapefiles,
  computes bounding boxes, then for each raster file does
  `ds.sel(x=slice(minx,maxx), y=slice(maxy,miny))` via `rioxarray`, writing per-country
  Cloud-Optimized GeoTIFFs (`driver="COG"`).
- **Not directly portable**: floodscan sources its country shapefiles from an OCHA-DAP-internal
  Azure blob container ("stratus" `polygon` container) that this pipeline has no access to, and
  its source data is NetCDF (`h5netcdf`), not Zarr. The bbox-slice-and-write-COG *shape* is
  reusable; the shapefile source and the NetCDF-vs-Zarr open call are not — CTrees uses
  `xr.open_zarr`-equivalent access into the Arraylake session's zarr store, plus its own boundary
  source, now resolved to HDX's own `cod-ab-global` dataset (see Stage 3.3).

### Tertiary reference: `hdx-scraper-climatetrace` (category 2, catalog description only)
- Per-country loop + failure isolation pattern, still worth inspecting properly at Stage 4.

### Capability gap (narrowed from the original pass)
No category-7 exemplar combines: (a) a per-country loop with failure isolation, (b) Zarr/
xarray-based (not GDAL/rasterio-mask-based) clipping, and (c) a portable (non-OCHA-DAP-internal)
country boundary source. (a) has category-2 precedent (climatetrace). (b) now has a *shape*
precedent (`hdx-floodscan`, imperfectly portable — different source format, non-portable boundary
source). (c) is now decided (`cod-ab-global`, see Stage 3.3) but still has **no pattern-catalog
precedent** — this pipeline will be the first to exercise it, so treat it as net-new/unverified
until it's actually working in code, not as an established pattern yet.

### Patterns to copy
- Config split, `Pipeline`/`__main__.py` separation, Dockerfile pattern — already scaffolded here.
- `hdx-floodscan`'s bbox-slice-then-`.rio.to_raster(driver="COG")` shape (adapted to a Zarr source
  and the `cod-ab-global` boundary source).
- Multi-static-YAML pattern from floods, if LUCA is added later.

### Patterns to avoid / must design net-new
- Per-country failure isolation — explicit try/except + logging (not fire/floods' silent skip).
- Country boundary/bbox sourcing — no reusable HDX pipeline convention found; do not copy
  `hdx-floodscan`'s Azure-blob approach. Use `cod-ab-global` per Stage 3.3 instead, including its
  GDB-extraction quirk (no wrapping `.gdb` directory in HDX's zip).
- Memory-bounding for large array processing — none of the inspected templates handle this.

---

# Stage 3: Design Document (all fields now have a working decision — see 3.8)

## 3.1 Proposed Pipeline Name
`hdx-scraper-ctrees` (already created), package `src/hdx/scraper/ctrees/` (flat, not nested — see
Assumption A4). `dataset_source` = "CTrees".

## 3.2 Jira Requirement Mapping
All functional/data-source requirements now map to firm design decisions (API, clip approach,
country scoping, dataset identity, backfill depth, output form, boundary source). Several are
explicitly interim/revisitable per the user's own framing (see 3.8) rather than final answers from
CTrees/DPT — that distinction is preserved throughout so it isn't lost by Stage 4.

## 3.3 Data Flow

- **Input source — decided 2026-08-04: Option B (public S3 COG mirror).** CTrees (2026-08-03)
  confirmed two access methods exist for the same AGB data; both were independently verified this
  session (not just described secondhand). Option A is kept below for context/comparison only —
  it is not being built.

  **Option A (not chosen): Earthmover/Arraylake Zarr SDK** — `ctrees/aboveground_biomass_100m_global_open`,
  accessed via `arraylake.Client`. **Access verified end-to-end 2026-08-03** using Michael Rans'
  personal Arraylake account (interactive device-code login via `Client().login(browser=False)`,
  token cached at `~/.arraylake/token.json`) — successfully opened the repo, session, and zarr
  group. Real structure, confirmed by direct inspection (not assumed):
  - Group `aboveground_biomass` contains: `agb` (data), `uncertainty` (data — a second band not
    mentioned in the ticket, decide separately whether to expose it), `x`, `y`, `time` (coords),
    `spatial_ref` (CF grid-mapping variable).
  - `agb`/`uncertainty` shape `(26, 202500, 405000)` = (time, y, x), `int16`, chunked
    `(1, 2000, 2000)` — one time-slice + a 2000×2000-pixel spatial tile per chunk, so slicing to
    one year + one country's bbox only touches intersecting chunks, not the whole global array.
    `agb` is scaled (`agb_scale_factor: 10`, `units: Mg ha-1`, `_FillValue: -9999`, `valid_min: 0`,
    `valid_max: 6000`) — divide by 10 for actual Mg/ha. **Confirmed via a real slice:**
    `agb_scale_factor` is a non-standard attribute name (not CF's `scale_factor`), so `xarray`'s
    automatic CF decoding does **not** apply it — only `_FillValue` gets auto-masked to `NaN`. The
    pipeline must divide by `agb_scale_factor` explicitly in code; relying on `xr.open_zarr`'s
    default decoding silently leaves values 10x too high.
  - `time`: exactly 26 annual steps, `2000-01-01` through `2025-01-01`. `x`: -180 to 180, `y`: 90
    to -90, pixel size ≈0.0008889° (~100m at the equator), CRS `EPSG:4326`/WGS84.
  - Ingestion, confirmed working and cleaner than the current stub: `client.get_repo(abg_url)` →
    `repo.readonly_session(branch="main")` →
    `xr.open_zarr(session.store, group="aboveground_biomass", consolidated=False)` opens the group
    directly as a labeled `xarray.Dataset`, rather than the stub's manual `zarr.open_group(...)`.
  - **Auth**: two distinct credentials, not to be conflated. The personal-login token above is for
    local dev/fixture-capture only. The deployed pipeline (GitHub Actions, headless) needs a
    **service-account API token** instead (`Client(token=...)`, string starting `ema_` or a JWT) —
    CTrees has now confirmed exactly how to generate one: Earthmover web UI → **Settings → API
    Clients → New API Client**. Not yet obtained. `pipeline.py`'s `client.login()` call will need
    to become `Client(token=os.environ[...])` for CI use. This token + the `arraylake`/`zarr`
    dependencies are the whole reason for the DoD's "secrets in Bitwarden" step under this option.
  - Per CTrees: this source "will keep the most up-to-date" — implied to be the canonical,
    freshest copy, though not quantified (see Option B's staleness caveat below).

  **Option B (chosen): Public S3 COG mirror (AWS Open Data, no-sign-request)** —
  `s3://ctrees-agb-100m-global/cogs/`. **Verified 2026-08-03**, no auth of any kind:
  - Listed via plain HTTPS (`GET https://ctrees-agb-100m-global.s3.amazonaws.com/?list-type=2&prefix=cogs/`):
    exactly 26 years (2000-2025), two files per year —
    `global_agb_100m_landsat0024_all_<year>_densenet_l1_agb_mosaic_100m_base_cd_ts.tif` (~38GB) and
    a `..._uncertainty_sem.tif` companion (~35GB) — i.e. one **giant global mosaic COG per year**,
    not pre-split by country/tile at the S3-key level.
  - **Windowed read confirmed working** via `rasterio`/GDAL against
    `/vsicurl/https://ctrees-agb-100m-global.s3.amazonaws.com/cogs/<file>.tif` — real COG (512×512
    internal tiles, full overview pyramid 2x-1025x), so GDAL only fetches the byte ranges for the
    requested window, never the full 38GB file. **Cross-validated against Option A**: same Lebanon
    bbox, same year (2025), gave an identical windowed shape `(2025, 1913)` and identical raw value
    range (`-9999` to `3870`) as the Arraylake Zarr slice — confirmed to be the same underlying
    data, not a lesser/older mirror, at least as of this check.
  - Same CRS (`EPSG:4326`) and grid shape (`202500, 405000`) as Option A.
  - **No `arraylake`/`zarr` dependency needed at all** — just `rasterio` (already pulled in via
    `rioxarray`). No API token, no Bitwarden secret, no service-account setup — removes a whole
    category of DoD work if chosen.
  - **Open risk, not confirmed either way**: CTrees' own framing of Option A as "the most
    up-to-date" implies this mirror could lag on refresh. Today's check shows 2025 data already
    present in both, so for an annual-cadence pipeline the practical staleness risk looks low, but
    CTrees hasn't quantified a lag, and there's no guarantee this AWS Open Data bucket has the same
    long-term stability/versioning commitment as a documented API. Accepted as a low-probability,
    low-severity risk for an annual-cadence pipeline; not quantifiable further without CTrees
    input, so not a blocker.
- **Country scoping**: fetch HDX's active Data Grid countries via
  `GET /api/3/action/group_list?all_fields=true&include_extras=true`, filtered to 3-letter group
  names with `data_completeness == "active"`. No auth required, single call. Verified 2026-08-03:
  22 countries — afg, bfa, caf, cmr, cod, col, hti, lbn, mli, mmr, moz, ner, nga, pse, sdn, som,
  ssd, syr, tcd, ukr, ven, yem. Treat as a live/short-TTL lookup at run time, not a value frozen
  into static config, since Data Grid membership changes over time. (This is now documented in
  `hdx-ai-hub/skills/analysis/references/hdx-concepts.md` and `ckan-api.md`, and referenced from
  `pipeline-pattern-catalog.md` category 2, so future pipelines needing the same scoping don't have
  to re-derive it.)
- **Transformation steps — revised for Option B**: the source is a single-band global COG per year
  (not a labeled Zarr/xarray array), read via GDAL's `/vsicurl/` over plain HTTPS — no `xr.open_zarr`/
  `rioxarray` needed for this step. Per Data-Grid country: open the year's COG with `rasterio.open()`,
  compute the pixel window from the country bbox via `rasterio.windows.from_bounds(*bbox,
  transform=src.transform)`, `src.read(1, window=window)`, then write the windowed array as a
  per-country GeoTIFF (`driver="COG"`) with `src.window_transform(window)` as the new transform and
  the source CRS/nodata carried over. This is a deliberate deviation from `hdx-floodscan`'s
  `ds.sel(...)`/`.rio.to_raster(...)` xarray pattern (see Stage 2) — that pattern exists to handle
  floodscan's labeled NetCDF dataset; Option B's source is a plain single-band raster, so a direct
  `rasterio` windowed read/write is simpler and avoids an xarray/rioxarray dependency entirely (see
  3.3's dependency-footprint note below). Country bounding boxes come from HDX's own `cod-ab-global`
  dataset (see "Country boundary source" below), not floodscan's Azure-blob shapefiles. Country/ISO3
  normalization via `hdx-python-country` per naming standards. Remember to divide `agb`/
  `uncertainty` pixel values by the scale factor (10, per Option A's inspection — confirm the same
  scaling applies to the S3 COG's raw values, since the cross-validation in 3.3 compared raw value
  ranges and they matched) to get true Mg/ha.
- **Country boundary source**: `GET /api/3/action/package_show?id=cod-ab-global` (verified
  2026-08-03: owner org `hdx`, license `cc-by-igo`, title "Global - Subnational Administrative
  Boundaries"). Download one geometry-variant resource (`global_admin_boundaries_matched_latest.gdb.zip`
  recommended — smallest at ~1GB and HDX's own "recommended for most use cases" default; `_original_`
  is what `hdx-boundaries-explorer/scripts/ocha.sh` uses but that's for border-fidelity mapping, not
  needed for a bare bbox). Extract into a manually-named `*.gdb` directory (HDX's zip has no
  wrapping `.gdb`-suffixed folder — GDAL's OpenFileGDB driver needs that suffix to recognize it, per
  `ocha.sh`'s comment). Open the `admin1` layer (there is no `admin0` layer in this file), filter by
  ISO3, take `total_bounds` of the matching rows as the country bbox. Download once per pipeline
  run and filter locally for each of the 22 Data Grid countries — not a per-country download, since
  the file is global.
- **Validation rules**: confirm array/raster readability before upload; confirm country count
  matches the fetched Data Grid list; sanity-check output file sizes (informs whether
  latest-year-only remains the right call once real sizes are known).
- **Output sink**: one HDX dataset **per country**, via `dataset.create_in_hdx()`.
- **Error handling**: per-country catch/log/continue — explicit, not the silent-skip pattern from
  the fire/floods precedent.
- **Retry behavior**: rely on `arraylake`/`hdx-python-utilities` defaults unless CTrees documents
  rate limits (unknown, not yet relevant until account access exists).
- **Idempotency**: standard `create_in_hdx(remove_additional_resources=True, ...)`.

**Dataset identity — interim values per the user's decision (2026-08-03), not CTrees-confirmed:**
- `dataset_organization`: `hdx`. `dataset_maintainer`: `196196be-6037-4488-8b71-d786adf4c081`
  (Michael Rans). Explicitly interim — update once CTrees/DPT confirm a permanent HDX org.
- `license_id`, `methodology`, `caveats`, `private`: keep the copier scaffold's placeholder values
  (`license_id: cc-by`, `methodology: Other`, blank `caveats`, `private: False`) as explicit
  stand-ins until CTrees completes the HDX Metadata form (still an open DoD item at the ticket
  level, independent of this pipeline's build proceeding).
- Tags/vocabulary: not yet decided — needs at least one Stage 4 pass against the approved
  vocabulary (e.g. a "climate-weather"/"forests" style tag), can be filled in without CTrees input.
- Resource format: `geotiff` (COG) — verify the exact mapped format string via
  `Resource.get_mapped_format()` once real files exist.
- Dataset shape: **one dataset per country**.
- Output form: **raw per-country GeoTIFF** to start (not summarized/zonal-stats) — explicitly
  revisitable if this doesn't work well once real data/file sizes are in hand.
- Backfill: **latest year only** to start — explicitly an interim scope, not a final answer;
  revisit once real per-country file sizes are known (a full-history backfill can be a follow-up
  ticket if warranted).
- `need_geo`: `true` — copier's `need_geo` branch adds `geopandas`/`pyarrow` (and the `gdal`/`geos`/
  `proj` system libs in the Dockerfile) for the `cod-ab-global` vector read, but does not add
  `rasterio` or a GDB-capable `pyogrio`, which must be added by hand regardless of source option
  (per `hdx-architecture-conventions.md`'s `need_geo` caveat).
  **Dependency footprint — decided (Option B): `arraylake`, `zarr`, `xarray`, `rioxarray` are all
  dropped.** Option B's transformation (see above) uses plain `rasterio` windowed reads/writes —
  `rasterio` is already present transitively (it's `rioxarray`'s own dependency, confirmed in
  `uv.lock`) and needs to become a direct dependency instead. Needed: `rasterio` (raster
  windowed read/write) + `geopandas`/`pyogrio` (GDB vector read + bbox) + `hdx-python-country`
  (ISO3 lookups). **Cleanup required in Stage 5**: `pyproject.toml`/`uv.lock` currently have
  `arraylake`, `zarr`, `xarray`, `rioxarray` (the last two added via `uv add` during Option-A/B
  fixture-capture testing, still uncommitted) — all four should be removed, `rasterio` added as a
  direct dependency, and `geopandas`+`pyogrio` added for the boundary-source read. See Stage 4.1/4.2.
- Dataset title/name/resource naming: follow `hdx-data-and-naming-standards.md` given the interim
  org, e.g. `<iso3>-ctrees-aboveground-biomass`.
- TDE: not applicable — new dataset, not a modification of an existing one.

## 3.4 Runtime and Scheduling
- Trigger: GitHub Actions cron (already scaffolded `run-python-script.yaml`, schedule block to be
  uncommented per convention).
- Frequency: likely annual, pending confirmation.
- Dependencies: **decided (Option B) — no credential dependency at all.** The S3 bucket is public/
  no-sign-request; GDAL's `/vsicurl/` reads over plain HTTPS need no AWS credentials, no
  `arraylake` service-account token, and no Bitwarden secret for data access. (The `cod-ab-global`
  boundary download is a normal unauthenticated HDX API call, unaffected either way.)
- Backfill: latest year only to start (interim, revisitable — see 3.3); confirmed to mean 2025.
- Failure/retry: standard GH Actions visibility; per-country isolation as above.

## 3.5 Observability
- Standard GH Actions logs; per-run summary of countries succeeded/failed/skipped, cross-checked
  against the live Data Grid country fetch.
- Data quality checks: array/raster readability, country count vs. fetched Data Grid list, output
  file size sanity check (also informs whether latest-year-only should change later).
- No metrics/alerting beyond default GH Actions failure notification convention.

## 3.6 Security and Compliance
- **Decided (Option B): no secrets at all for data access.** The S3 COG mirror is public/
  `--no-sign-request` — no Arraylake account, no service-account API token, no `~/.arraylake/`
  login, nothing to mint via Earthmover's dashboard, nothing to put in Bitwarden/CI secrets for
  this part of the pipeline. This drops the corresponding ticket DoD "secrets in Bitwarden" step
  entirely (nothing to add there for AGB access — `cod-ab-global` is likewise a public, unauthenticated
  HDX API/download). The Option-A credential story (personal OAuth login vs. service-account token)
  from the previous revision is kept in 3.3 for historical context only; it does not apply to the
  chosen build.
- No obvious PII; license/redistribution terms are interim placeholders pending the CTrees metadata
  form (ticket DoD item, independent of this build proceeding).

## 3.7 Test Strategy
- **Fixture captured 2026-08-03**: a real slice — Lebanon (`lbn`), 2025, approximate bbox
  (`lon 35.0-36.7`, `lat 33.0-34.8`) — sliced from the verified `agb` array via
  `xr.open_zarr(...).sel(time="2025-01-01", x=slice(...), y=slice(...))` (Option A), written as a
  Cloud-Optimized GeoTIFF via `rioxarray`. Real values, not synthetic: raw range 0-3870 (0-387.0
  Mg/ha once divided by `agb_scale_factor`), shape `(2025, 1913)` pixels, **4.5MB** file. Copied to
  `tests/fixtures/input/agb_lbn_2025.tif` — **currently uncommitted**, at the user's request, since
  the test-architecture question below isn't settled yet. The bbox used was a manual approximation
  for this exploratory capture, not the real `cod-ab-global` admin1 lookup — Stage 4 should redo
  fixture capture (or at least confirm the bbox) once that lookup is actually implemented. The same
  slice was independently re-derived via Option B (`rasterio` windowed read against the public S3
  COG) as part of verifying that option — identical shape and raw value range, so this one fixture
  file is valid evidence for either source option, not just Option A.
- **Test-architecture question — resolved by the Option B decision.** The standard HDX pattern
  (`Pipeline.generate_dataset()` via `Retrieve(save=False, use_saved=True)`, already scaffolded in
  `tests/conftest.py`/`tests/test_pipeline.py`) assumes a plain HTTP source. It fits the
  `cod-ab-global` boundary-file download directly (a normal HTTP GET). It does **not** fit the raw
  COG read directly, since `rasterio`'s `/vsicurl/` access is a GDAL-internal ranged-read protocol,
  not a single `Retrieve`-recordable HTTP call — so the plan is: keep the already-captured
  `tests/fixtures/input/agb_lbn_2025.tif` (Lebanon, 2025, cross-validated in 3.3 as identical
  between Option A and Option B for this slice) as a local file, and monkeypatch the
  windowed-COG-open call in `Pipeline` (e.g. a small seam like `Pipeline._open_cog(url)` returning
  a `rasterio` dataset handle) to open that local fixture file instead of the real `/vsicurl/` URL
  in tests — no live network, no SDK mocking needed (there is no SDK for Option B). This is
  simpler than Option A's mock-the-SDK-session plan from the previous revision, one more concrete
  benefit of the Option B choice. The Stage 3.7 guidance this added to the skill (SDK-source
  fixture mocking) remains useful for future raster/Zarr pipelines even though this one ended up
  not needing it.
- Unit tests: scaffold already present (`tests/conftest.py`, `tests/test_pipeline.py`) but still a
  bare skeleton with no real assertions; needs both the `cod-ab-global`-via-`Retrieve` path and the
  Arraylake-via-mock path above.
- New test needed (no precedent): simulate one country's clip/upload failing to verify per-country
  failure isolation.
- Also worth a unit test (no live network) for the Data Grid country-fetch helper, using a
  recorded/mocked `group_list` response rather than hitting `data.humdata.org` in CI.
- Still undecided: whether to expose the `uncertainty` band (confirmed present alongside `agb`,
  same shape/chunking — see 3.3) as a second resource or leave it out of this initial build.

## 3.8 Open Questions
All items from the previous revisions now have a decision (org/maintainer, metadata-form
placeholders, backfill depth, output form, country-boundary source, source option) — several
explicitly interim, preserved into Stage 4 rather than presented as settled fact. **No open
questions remain from Stage 1-3.** The source-option question from the previous revision is
resolved:

1. ~~Which source option should the pipeline build against?~~ **Decided 2026-08-04: Option B**
   (public S3 COG mirror, no auth). See 3.3 for the full comparison and 3.4/3.6/3.7 for the
   resulting simplifications (no credentials, no `arraylake`/`zarr`/`xarray`/`rioxarray`, simpler
   test mocking).

---

## Checkpoint 1: Please review the requirements summary, template analysis, and design.

**Approved 2026-08-04** ("Implement option B" — both answers the open source-option question and
approves Stage 1-3 to proceed to Stage 4).

Since this originated from a Jira ticket, would you like me to post a condensed version of this
revised Stage 1-3 summary as a comment on HDXPIPE-100 — including the Data Grid country-list answer
to Briar's own question from the previous comment (`group_list?all_fields=true&include_extras=true`
filtered on `data_completeness=="active"`), and the Option A vs. B decision?

---

# Stage 4: Implementation Plan

## 4.0 Scaffold Decision

**Not greenfield — no `copier copy` needed.** `hdx-scraper-ctrees` already has the full copier
scaffold (`pyproject.toml`, `Dockerfile`, `.github/workflows/*`, `.pre-commit-config.yaml`,
`README.md`, `src/hdx/scraper/ctrees/{__init__.py,__main__.py,pipeline.py,config/}`,
`tests/{conftest.py,test_pipeline.py}`) plus a hand-written stub `Pipeline` — see Stage 2. This
plan modifies that existing tree; it does not regenerate it.

**Flat package, not nested** (per Assumption A4): `src/hdx/scraper/ctrees/` stays flat since LUCA
is out of scope and only one CTrees product (AGB) is being built.

**Dockerfile currently has no geo system deps** (checked: only `git` is installed in the builder
stage) — despite `need_geo` conceptually applying here, the Dockerfile was never actually updated
for it. This plan adds the `gdal-dev`/`geos-dev`/`proj-dev` (builder) and `gdal`/`geos`/`proj`
(runtime) apk packages, following the exact pattern in `hdx-scraper-climatetrace/Dockerfile`
(inspected locally this session) rather than inventing package names.

## 4.1 Files to Create

| Path | Purpose | Template source | Key contents |
|---|---|---|---|
| `src/hdx/scraper/ctrees/boundaries.py` | Isolate the net-new, no-precedent `cod-ab-global` boundary logic from `pipeline.py`'s AGB-clip logic, so each is independently testable | None — flagged in Stage 2 as having no pattern-catalog precedent; net-new | `download_admin1_boundaries(retriever, tempdir) -> str` (downloads `global_admin_boundaries_matched_latest.gdb.zip` via `package_show`/resource URL, extracts to a manually-named `*.gdb` dir per the known GDAL `OpenFileGDB`-suffix quirk); `get_country_bbox(gdb_path, iso3) -> tuple[float,float,float,float]` (opens the `admin1` layer via `geopandas.read_file(..., layer="admin1")`, filters by ISO3 column, returns `.total_bounds`) |
| `tests/fixtures/input/cod_ab_admin1_sample.geojson` | Small synthetic vector fixture standing in for the real ~1GB `cod-ab-global` GDB (too large to commit — per the skill's oversized-fixture rule) | N/A — synthetic, flagged as such | A handful of admin1 polygons (plausible, not precise) for `afg`, `sdn`, `lbn` — matching `tests/conftest.py`'s existing `Locations.set_validlocations` — enough to exercise `get_country_bbox()`'s filter+bounds logic in any OGR-readable format; `download_admin1_boundaries()`'s real download+GDB-extraction step is exercised by manual validation only (see 4.5), not by this fixture |
| `tests/fixtures/input/agb_lbn_2025_full.tif` (rename/reuse of existing `agb_lbn_2025.tif`) | Real fixture for the windowed-COG-read code path | Already captured 2026-08-03 (see 3.7) | Real Lebanon/2025 slice, 4.5MB, cross-validated identical between Option A and B for this bbox — committed as-is; only renamed if `pipeline.py`'s fixture-loading code expects a specific name |

## 4.2 Files to Modify

| Path | Change | Reason | Risk |
|---|---|---|---|
| `pyproject.toml` | Remove `arraylake`, `zarr`, `xarray`, `rioxarray`; add `rasterio`, `geopandas`, `pyogrio` as direct dependencies | Option B decision (3.3) — no Zarr/Arraylake SDK needed; `rasterio` windowed read/write + GDB-capable vector read for boundaries | Low — `rasterio` is already present transitively via the currently-installed `rioxarray`, so the actual wheel is already in `uv.lock`'s cache; this is a lockfile/dependency-graph change, not a new untested binary |
| `uv.lock` | Regenerate via `uv lock` after the `pyproject.toml` edit | Keep lockfile consistent with declared deps | Low — mechanical |
| `Dockerfile` | Add `gdal-dev`/`geos-dev`/`proj-dev`/`build-base`/`linux-headers` to the builder-stage `apk add`, and `gdal`/`geos`/`proj` to the runtime-stage `apk add`, matching `hdx-scraper-climatetrace/Dockerfile` exactly | `rasterio`/`geopandas`/`pyogrio` need GDAL/GEOS/PROJ native libs at both build and runtime; currently absent | Medium — first time this repo's Docker image actually needs native geo libs; must verify the image still builds and the compiled wheels resolve against Alpine's `gdal-dev` (climatetrace is the working precedent for this exact base image + these exact packages) |
| `src/hdx/scraper/ctrees/config/project_configuration.yaml` | Replace `abg_url` (Arraylake repo id, Option A-only) with: `agb_cog_url_template` (the public S3 HTTPS COG URL with a `{year}` placeholder), `agb_scale_factor: 10`, `cod_ab_global_dataset_id: "cod-ab-global"`, `latest_year: 2025` | Config now points at the Option B source; scale factor and boundary-dataset id are pipeline-specific constants, not secrets | Low |
| `src/hdx/scraper/ctrees/config/hdx_dataset_static.yaml` | Fill in `owner_org: hdx`, `maintainer: 196196be-6037-4488-8b71-d786adf4c081`, `dataset_source: CTrees`, `data_update_frequency: Every year`; leave `license_id`/`methodology`/`caveats`/`private` at copier defaults (explicit interim placeholders per 3.3) | These are the interim dataset-identity decisions from Checkpoint 1 (1.3 #6/#7) | Low — all explicitly interim/revisitable, not fabricated (per skill rule, these are user-supplied, not guessed) |
| `src/hdx/scraper/ctrees/pipeline.py` | Replace the stub `get_data`/`generate_dataset` with real per-country logic: `get_data_grid_countries()` (the verified `group_list` call), `get_country_raster(iso3, bbox, year)` (open the year's S3 COG via `rasterio.open()` over `/vsicurl/`, `rasterio.windows.from_bounds()`, `src.read(1, window=...)`, divide by `agb_scale_factor`, write out `driver="COG"` to `self._tempdir`), `generate_dataset(iso3, tif_path, year)` (build the per-country `Dataset`, one `geotiff` resource, following `climatetrace`'s per-country dataset-naming/tagging shape) | Core of this build — everything upstream (Stage 1-3) points here | High — the one genuinely novel piece (raster-window-clip + this exact boundary source combo); gets the most review attention (see 4.7) |
| `src/hdx/scraper/ctrees/__main__.py` | Add the per-country loop: fetch Data Grid countries, download+extract `cod-ab-global` once via `boundaries.download_admin1_boundaries()`, then for each country: `get_country_bbox()` → `get_country_raster()` → `generate_dataset()` → `create_in_hdx()`, wrapped in an explicit `try/except`/log/continue per country (per Stage 2's "patterns to avoid" — no silent skip), using `progress_storing_folder` like `climatetrace/__main__.py` | Per-country failure isolation has no direct template precedent in this repo; climatetrace is the closest shape (per-country loop + resumable progress) but lacks the explicit try/except this design calls for | Medium — this loop is where a single bad country must not abort the whole run |
| `README.md` | Update the auto-generated placeholder description to describe the actual AGB/S3-COG/per-country-clip pipeline | Currently still copier boilerplate | Low |
| `.github/workflows/run-python-script.yaml` | Uncomment the `schedule:`/`cron:` block for annual cadence once the pipeline is verified working end-to-end (not part of this initial PR — flagged for a follow-up once a manual run succeeds) | Standard convention; but activating a live cron before a single manual/staged run has succeeded is premature | Low if deferred; flagged so it isn't forgotten nor turned on too early |

## 4.3 Code Reuse Plan

- **Config/`Pipeline`/`__main__.py` split, Dockerfile shape**: already scaffolded by copier — kept
  as-is except for the geo-dependency additions above.
- **Per-country loop + `progress_storing_folder` resumability**: mirrored from
  `hdx-scraper-climatetrace/src/hdx/scraper/climatetrace/__main__.py` (inspected locally this
  session), adapted to add explicit per-country `try/except`/logging (climatetrace itself doesn't
  have this — a deliberate improvement, not a copy, per Stage 2's "patterns to avoid").
- **Per-country dataset naming/tagging shape**: mirrored from
  `climatetrace.pipeline.Pipeline.generate_country_dataset` (dataset name `f"{iso3}-..."`,
  `Country.get_country_name_from_iso3`, `add_country_location`, resource-generation-per-country
  shape) — adapted from CSV/tabular resources to a single GeoTIFF resource.
- **Windowed raster clip + COG write**: adapted from `hdx-floodscan`'s bbox-slice-then-write-COG
  *shape* (`ds.sel(...)` → `.rio.to_raster(driver="COG")`), but implemented via plain `rasterio`
  (`rasterio.windows.from_bounds` + `dataset.read(window=...)` + `rasterio.open(..., "w",
  driver="COG", ...).write(...)`) instead of `xarray`/`rioxarray`, since Option B's source is a
  plain single-band COG, not floodscan's labeled NetCDF dataset — see 3.3's transformation-steps
  note for the full rationale.
- **`cod-ab-global` boundary read**: net-new, no direct precedent (Stage 2 capability gap) —
  isolated into `boundaries.py` per 4.1 so it can be independently unit-tested and reused if a
  future pipeline needs the same country-bbox source.
- **Data Grid country-list fetch**: the verified `group_list?all_fields=true&include_extras=true`
  call (3.3), now also documented in `hdx-ai-hub/skills/analysis/references/hdx-concepts.md`/
  `ckan-api.md` for reuse by future pipelines.

## 4.4 Step-by-Step Implementation Sequence

1. Edit `pyproject.toml`: remove `arraylake`/`zarr`/`xarray`/`rioxarray`, add `rasterio`/
   `geopandas`/`pyogrio`. Run `uv lock` to regenerate `uv.lock`.
2. Edit `Dockerfile`: add the geo apk packages to both stages (climatetrace pattern).
3. Edit `config/project_configuration.yaml` and `config/hdx_dataset_static.yaml` per 4.2.
4. Write `src/hdx/scraper/ctrees/boundaries.py` (`download_admin1_boundaries`,
   `get_country_bbox`).
5. Write the small synthetic `tests/fixtures/input/cod_ab_admin1_sample.geojson` fixture.
6. Rewrite `pipeline.py`: `get_data_grid_countries`, `get_country_raster`, `generate_dataset`.
7. Rewrite `__main__.py`'s per-country loop with explicit try/except isolation.
8. Write/extend `tests/test_pipeline.py` (and a new small test module for `boundaries.py`) against
   the fixtures from 4.1 — no live network in tests.
9. Run `uv run pytest` locally; fix until green.
10. Run `pre-commit run --all-files` (ruff lint/format, trailing-whitespace, uv-lock check).
11. Update `README.md`.
12. Manual validation (see 4.5) before touching the cron schedule.

## 4.5 Validation Plan

- **Local**: `uv run pytest` — unit tests for `boundaries.get_country_bbox()` against the synthetic
  fixture, `pipeline.get_country_raster()` against the real `agb_lbn_2025.tif` fixture (mocked
  `/vsicurl/` open), `generate_dataset()` producing a well-formed `Dataset` with one `geotiff`
  resource, and a per-country-failure-isolation test (one country's clip raises, loop continues).
  A mocked `group_list` response for the Data Grid country-fetch helper (no live `data.humdata.org`
  hit in CI).
- **CI**: `.github/workflows/run-python-tests.yaml` (already scaffolded) runs the same suite;
  confirm the Docker image with the new geo deps actually builds in `publish.yaml`.
- **Manual, before enabling the cron schedule**: one real `workflow_dispatch` (or local
  `--use-saved false`) run against a couple of real Data Grid countries (e.g. `lbn`, `afg`) hitting
  the live S3 COG and the real `cod-ab-global` download/GDB-extraction path end-to-end — this is
  the one path not exercised by the fixture-based unit tests (per 4.1's fixture note), and per
  DoD, must run clean on prod before considering the ticket done.
- **Data quality**: per-run summary of countries succeeded/failed/skipped vs. the live Data Grid
  fetch; output file size sanity check (informs whether latest-year-only should later change, per
  3.3/1.3 #5).

## 4.6 Rollback Plan

- All changes are additive/replacing-a-stub on a not-yet-deployed pipeline — nothing in production
  depends on this repo yet (no prior successful HDX run). Reverting is a plain `git revert`/branch
  discard; no HDX datasets exist yet to clean up.
- If the S3 COG mirror's staleness risk (3.3) turns out to matter in practice, switching to Option A
  is a `pipeline.py`/config/dependency change, not a data-model change — the `agb`/`uncertainty`
  scale factor, CRS, and grid shape are identical between both options (verified 3.3), so no
  downstream (dataset/resource) rework would be needed, only the ingestion method.

## 4.7 Review Notes

- **Highest-attention area**: `pipeline.py`'s windowed-clip logic (`rasterio.windows.from_bounds` +
  `window_transform` + COG write) — this is the one part of the design with no exact template to
  copy verbatim (adapted from floodscan's xarray shape, not identical to it). Worth a careful look
  at nodata/CRS handling and the `agb_scale_factor` division.
- **`boundaries.py`'s GDB-extraction quirk** (no wrapping `.gdb`-suffixed folder in HDX's zip) is
  copied from a documented workaround (`hdx-boundaries-explorer/scripts/ocha.sh`, referenced but
  not locally re-verified this session) — worth a reviewer double-check against a real download,
  not just the synthetic test fixture.
- **Not yet decided, low-risk to defer**: whether to expose the `uncertainty` band as a second
  resource (3.7) — this plan ships `agb` only for the initial build, matching Assumption A1 (AGB
  only, LUCA/other bands deferred); adding `uncertainty` later is a small, additive follow-up, not
  a redesign.
- **Interim values carried through unchanged**: `owner_org`/`maintainer`, `license_id`/
  `methodology`/`caveats` placeholders, and latest-year-only backfill — all explicitly flagged
  revisitable in Stage 1/3, not silently finalized by this plan.
- **Cron activation deliberately excluded from this PR's scope** (4.2) — flagged so it isn't
  forgotten, but also not turned on before a manual prod run succeeds.

---

## Checkpoint 2: Please review the implementation plan. I will not write or modify code until you approve.

Would you also like me to post a condensed version of this Stage 4 plan as a second Jira comment on
HDXPIPE-100 (separate from the Checkpoint 1 comment)?

**Approved 2026-08-04** ("Go ahead and implement").

---

# Stage 5: Implementation — Manual Validation Findings (2026-08-04)

Stage 4 was implemented per the approved plan (all files in 4.1/4.2 created/modified, `uv run
pytest` green, `pre-commit run --all-files` clean). Manual validation (per 4.5's "one real run
against a couple of real Data Grid countries" step) surfaced two real bugs and one significant
unresolved design/infra question, documented here since they change facts this analysis had
assumed true. **The pipeline is not yet considered done — see 5.3's open decision.**

## 5.1 Bug: source COG has no GDAL NoData tag (fixed)

Discovered while manually verifying a generated Lebanon file in QGIS/`gdalinfo`: the public S3 COG
mirror (Option B, chosen in 3.3/3.8) carries **no NoData tag of its own** (`gdalinfo` shows no
"NoData Value" line at all), even though the documented fill value is `-9999` (from the equivalent
Zarr source's `_FillValue` attribute — see 3.3). `pipeline.py`'s original `get_country_raster()`
read `src.nodata` to decide which pixels to mask, which silently evaluated to `None` against the
real source — nodata pixels (water bodies etc.) leaked through as raw `-999.9` (i.e. `-9999 ÷ 10`)
instead of being masked to `NaN`. Confirmed via a live-generated Lebanon file: `gdalinfo -stats`
showed `Minimum=-999.900` before the fix.

**Fix**: added `agb_fill_value: -9999` to `project_configuration.yaml`; `get_country_raster()` now
masks against this configured value instead of `src.nodata`.

**Why the test suite didn't catch this**: the committed fixture (`agb_lbn_2025.tif`, captured
earlier via `rioxarray`) *does* have a NoData tag baked in by `rioxarray`'s own write path — unlike
the real source. The mocked test therefore exercised a source that was "nicer" than reality and
passed either way. Fixed by rewriting `test_get_country_raster` to build an in-memory copy of the
fixture (`rasterio.io.MemoryFile`) with the NoData tag explicitly stripped before feeding it to the
mock, so the test now matches the real source's actual metadata behaviour and would fail again if
this regressed.

## 5.2 Bug: per-country failure isolation didn't cover the HDX upload step (fixed)

A real end-to-end run hit a live failure on `cmr` (Cameroon):

```
ckanapi.errors.CKANAPIError: ['.../api/action/package_revise', 413, '413 Request Entity Too Large']
```

`dataset.create_in_hdx(...)` (and `update_from_yaml(...)`) were outside the per-country
`try/except` in `__main__.py` — the design called for explicit per-country isolation (Stage
2/4.2/4.3), but the `try` block only wrapped the fetch/clip/generate steps, not the actual upload.
This single failure would have crashed the whole batch, silently skipping every Data Grid country
alphabetically after `cmr`. **Fixed** by moving `update_from_yaml`/`create_in_hdx` inside the
`try` block.

## 5.3 Open, unresolved: some countries' clipped rasters are too large to upload

The 413 above is a real infrastructure limit, not a fluke, and it doesn't go away with 5.2's fix —
it just becomes a cleanly-logged per-country skip instead of a crash. Investigated by generating
real (non-mocked) clipped rasters against the live S3 source for several countries:

**Empirical sizes, Cameroon (`cmr`), by encoding** (8785×12860 px, ~113M pixels, ~4% nodata):

| Encoding | Size |
|---|---|
| float32, LZW, no predictor (current/shipped design) | **375.7 MB** ← caused the 413 |
| float32, DEFLATE + predictor 3 | 310.7 MB |
| float32, LZW + predictor 3 | 436.1 MB (predictor made it *worse* — noisy float data) |
| int16 (×10 scaled, undivided), LZW + predictor 2 | 224.4 MB |
| int16, DEFLATE + predictor 2 | **183.8 MB** |
| int16, ZSTD + predictor 2 | 181.2 MB (marginal gain over DEFLATE; slower to write, less portable) |

**Empirical size, DR Congo (`cod`)** — measured directly (not extrapolated), current float32
encoding: **1.71 GB** (21675×21207 px, ~460M pixels, mean 121.3 Mg/ha — dense Congo Basin forest
across nearly the whole country, very little nodata to compress away).

**Estimated pixel counts for all 22 active Data Grid countries** (bounding box from OSM/Nominatim as
a stand-in for the real `cod-ab-global` admin1-union bbox, at the source's actual ~100m/px
resolution) — ranked, Cameroon included as the reference point:

| Rank | ISO3 | Country | Est. pixels | vs. Cameroon |
|---|---|---|---|---|
| 1 | cod | DR Congo | ~460M (confirmed: 1.71GB float32) | 4.1× |
| 2 | col | Colombia | ~392M | 3.5× |
| 3 | mli | Mali | ~310M | 2.7× |
| 4 | sdn | Sudan | ~291M | 2.6× |
| 5 | ven | Venezuela | ~263M | 2.3× |
| 6 | ner | Niger | ~237M | 2.1× |
| 7 | moz | Mozambique | ~228M | 2.0× |
| 8 | mmr | Myanmar | ~217M | 1.9× |
| 9 | tcd | Chad | ~213M | 1.9× |
| 10 | som | Somalia | ~188M | 1.7× |
| 11 | ukr | Ukraine | ~188M | 1.7× |
| 12 | afg | Afghanistan | ~166M | 1.5× |
| 13 | nga | Nigeria | ~149M | 1.3× |
| 14 | caf | Central African Republic | ~145M | 1.3× |
| 15 | ssd | South Sudan | ~138M | 1.2× |
| 16 | yem | Yemen | ~118M | 1.0× |
| 17 | **cmr** | **Cameroon (reference)** | **~113M** | **1×** |
| 18 | bfa | Burkina Faso | ~57M | 0.5× |
| 19 | syr | Syria | ~44M | 0.4× |
| 20 | hti | Haiti | ~11M | 0.1× |
| 21 | lbn | Lebanon | ~3.6M | 0.03× |
| 22 | pse | Palestine | (lookup failed — expected small, similar scale to Lebanon) | — |

Extrapolating Cameroon's measured int16+DEFLATE compression ratio (184MB / 113M px ≈ 1.63 bytes/px)
to DR Congo's ~460M px gives a rough **~750MB estimate** — i.e. **the int16 switch alone is very
unlikely to make DR Congo uploadable**, even though it roughly halves Cameroon's file. This is an
estimate, not a second live measurement, but DR Congo's very low nodata fraction (like Cameroon)
makes it a reasonable one.

**Compounding risk — bbox inflation from offshore territory**: Colombia's #2 ranking is partly an
artifact of clipping by *bounding box* rather than exact country polygon. Its measured bbox
(15.27°×20.28°) is larger than mainland Colombia's actual extent (~12°×17°) — very likely because
`cod-ab-global`'s admin1 set (like OSM's) includes the San Andrés archipelago, ~700km away in the
Caribbean, which drags the rectangle's western edge out substantially for almost no additional real
data. Venezuela (Los Roques, Aves Island) likely has the same issue. This means Colombia's problem
is more structurally fixable (exclude distant island admin units from the bbox calc) than DR
Congo's (which is genuine, dense, contiguous land area).

### int16 vs. float32 — full trade-off, not just file size

Switching `get_country_raster()`'s output from float32 (post-division, real Mg/ha values) to int16
(the source's own ×10-scaled representation, undivided) was evaluated as the leading size fix.
Consequences, beyond the size numbers above:

- **Precision: none lost.** The source's own finest resolvable unit is already `0.1 Mg/ha` (that's
  what `agb_scale_factor: 10` means — the source is natively int16, not continuous). A float32
  value like `152.3` round-trips exactly to int16 `1523` and back with zero rounding error. Shipping
  int16 directly (no divide-then-store) is arguably *more* faithful to the source than the current
  float32 output, not less.
- **Value range: no overflow risk.** Source valid range 0–6000 (raw) plus a `-9999` sentinel fits
  comfortably in int16 (`-32768..32767`).
- **NoData handling: no worse**, as long as the GeoTIFF's NoData tag is set explicitly either way
  (`-9999` for int16, `NaN` for float32) — both are under our control regardless of what the source
  COG does or doesn't carry (see 5.1).
- **The real cost — downstream usability.** With float32, a pixel value *is* the answer (`152.3` =
  `152.3 Mg/ha`), no interpretation needed by anyone opening the file. With int16, a value of
  `1523` is **not** the answer — a consumer must know to multiply by `0.1`. GDAL has a standard
  per-band `SetScale()`/`SetOffset()` mechanism for this, and QGIS's Identify tool does respect it
  if set — so a sophisticated GIS user is largely fine. But a plain `rasterio.open(f).read(1)` or
  `gdal.Open()/ReadAsArray()` in a basic script gets the raw scaled integers unless the caller
  specifically applies `.scales[0]`, which is not automatic on a bare array read. For HDX's
  audience (not all GIS specialists), this silently relocates the exact "10x too high" gotcha this
  analysis already flagged for our *own* internal code (3.3) onto every future downloader instead of
  solving it once in the pipeline — a real discoverability/misinterpretation risk, not just a
  documentation nicety.
- **Net**: roughly halves file size for genuinely dense/large countries, at the cost of pushing a
  scale-factor gotcha onto data consumers unless mitigated with GDAL scale/offset tags *and* very
  explicit resource-description/dataset-notes wording — and even then, it is not sufficient on its
  own to make DR Congo uploadable (see extrapolation above).

## 5.4 Follow-up: LERC compression tested (2026-08-04)

The size problem is a compression-*codec* question more than a file-*format* question — GDAL's COG
driver supports `COMPRESS=LERC`/`LERC_DEFLATE`/`LERC_ZSTD` (LERC = Limited Error Raster
Compression, originally developed by Esri, purpose-built for continuous scientific/elevation-style
rasters), still written as a completely standard `.tif`. LERC supports an optional `MAX_Z_ERROR`
creation option: a small, bounded, per-pixel error tolerance — set below the source's own native
precision floor (`0.1 Mg/ha`, from `agb_scale_factor: 10`), this is not a meaningful loss of real
information, just headroom the lossless codecs weren't using.

**Cameroon (`cmr`), extended comparison:**

| Encoding | Size |
|---|---|
| float32, plain LZW (current shipped design) | 375.7 MB |
| int16, plain DEFLATE + predictor 2 | 183.8 MB |
| int16, LERC_DEFLATE, lossless | 165.2 MB |
| int16, LERC_DEFLATE, ±1 raw unit (±0.1 Mg/ha) bounded error | 148.0 MB |
| float32, LERC_DEFLATE, lossless | 303.0 MB |
| **float32 (self-describing Mg/ha), LERC_DEFLATE, ±0.05 Mg/ha bounded error** | **167.7 MB** |

The last row is the standout: it keeps the shipped resource as **plain float32 Mg/ha values** (no
scale-factor gotcha pushed onto consumers — see 5.3's int16 trade-off) while landing within a few MB
of the best lossless int16 option. Verified readable and uncorrupted (`gdalinfo -stats`: min 0, max
600, NoData still `nan`, matching the lossless baseline).

**DR Congo (`cod`) — confirmed by direct measurement, not extrapolation** (same live source, one
window read reused across all four encodings):

| Encoding | Size |
|---|---|
| float32, plain LZW (current shipped design) | 1709.2 MB (1.71 GB) |
| float32, LERC_DEFLATE, ±0.05 Mg/ha bounded error | 816.5 MB |
| int16, LERC_DEFLATE, lossless | 804.7 MB |
| int16, LERC_DEFLATE, ±1 raw unit bounded error | 729.5 MB |

This supersedes 5.3's ~750MB *estimate* (extrapolated from Cameroon's compression ratio) — the real
number is close (729.5–816.5 MB depending on encoding), confirming LERC roughly **halves** DR
Congo's file (1.71GB → ~730-820MB) but, as anticipated, **does not get it into a plausibly-small
range** the way it does for Cameroon (375.7MB → ~150-170MB, a ~2.2-2.5× reduction that likely clears
whatever limit rejected the original 375.7MB). DR Congo's problem is genuine data volume (dense,
low-nodata land cover across ~460M pixels), not a fixable encoding inefficiency — no lossless or
near-lossless codec closes a gap that large. Verified readable: `gdalinfo -stats` on the bounded-
error float32 file reproduces the lossless baseline's exact mean (121.265) and range (0-600).

### Is LERC well supported? (revised 2026-08-06 — original claim was overstated)

The original version of this section claimed LERC support was effectively universal on any
GDAL ≥2.4 build ("vendored, no external dependency... no plugin needed on any QGIS 3.x install").
**That's wrong, or at least not reliably true**, verified this session with real sources rather
than assumption — this matters directly for *consumers downloading and opening the resource*, not
just for whether this pipeline's own build can write the file (a separate, already-resolved
question — see the `hdx-ai-hub` pipeline-builder skill update below).

- **"Vendored" is necessary but not sufficient.** GDAL's source tree does bundle LERC's codec
  source since 2.4, so a build *can* compile LERC support with zero external dependency — but a
  distro packager can still choose to link a separate system `liblerc` instead, and if the
  packaging pipeline building GDAL doesn't have that library (or the vendored path enabled) at
  build time, LERC support is simply absent from that binary, exactly like any other optional
  codec. Confirmed directly: Alpine's `gdal` apk package (this pipeline's own Docker base image)
  links against an external `libLerc.so.4`, not an internal vendored copy — it works here because
  Alpine's package also declares that library as a hard dependency, but that's a property of
  Alpine's specific packaging choice, not a guarantee that follows from "GDAL 2.4+".
- **Ubuntu's system GDAL package** (`apt install gdal-bin`/`libgdal-dev` — the default path for
  countless Linux desktop/QGIS-on-Linux/system-Python users) did **not** include LERC support
  before Ubuntu 22.10, and only gained it from 22.10/24.04 LTS onward — meaning Ubuntu 22.04 LTS
  (a very widely deployed release, supported into 2027) ships a system GDAL that cannot decode
  LERC-compressed GeoTIFFs at all, unless the user compiled GDAL themselves.
- **QGIS on Windows (OSGeo4W)**: LERC support has genuinely regressed in real, shipped builds —
  a documented OSGeo4W ticket (May 2021, GDAL 3.3.0/QGIS 3.18.2) reports LERC compression
  completely missing ("LERC compression support is not configured"), attributed to a libtiff
  linkage gap, and explicitly notes this was a *recurrence* of an earlier, separate ticket (#663).
  Not just a one-off historical bug — evidence that LERC availability in mainstream Windows GIS
  tooling has been fragile in practice, not a settled non-issue.
- **R (`sf`/`terra`) on Windows**: CRAN's Windows binaries build against `rwinlib/gdal3` (confirmed
  directly from `sf`'s own current `tools/winlibs.R` build script). That repo's bundled dependency
  list (36 libraries, GDAL 3.4.1) includes `zstd` explicitly but has **no `liblerc`/LERC package
  at all**. The repo is now archived (frozen since January 2024, stuck at that same GDAL 3.4.1
  build from March 2022) — so R users on Windows installing `sf`/`terra` from CRAN binaries are
  very likely unable to read LERC-compressed GeoTIFFs at all, while ZSTD works fine on that same
  build. (macOS/Linux R builds weren't checked — likely depend on Homebrew's/the system's GDAL,
  flagged as unverified rather than assumed either way.)
- **ArcGIS Pro**: genuinely ambiguous from documentation alone, not verified hands-on (no ArcGIS
  install available to test directly in this environment — flagged as such rather than guessed).
  Esri's own environment-setting docs list LERC prominently as a **write**/export option (expected
  — Esri originated LERC and uses it in their own native raster formats) but say nothing about
  ZSTD at all. Their separate "supported raster dataset file formats" reference, for plain
  TIFF/GeoTIFF specifically, lists only CCITT/PackBits/LZW/JPEG/None as read-supported compression
  — no mention of either LERC or ZSTD for reading an externally-produced GeoTIFF. Real-world ArcGIS
  behavior is often better than this table implies (Esri has been improving Cloud-Native raster/COG
  support), but that's a claim worth testing directly before relying on it, not one this analysis
  can confirm either way.
- **Python**: diverges by library, not just GDAL version. `rasterio` (the standard `pip install
  rasterio` wheel) bundles its own private `libzstd` *and* `libLerc` — verified directly by
  inspecting the wheel's bundled `.so` files and by a real write/read round-trip — so this specific
  path has no problem with either codec. But two other common "just open this .tif in Python"
  paths do: `Pillow` (`PIL.Image.open`) reads a ZSTD-compressed TIFF fine but cannot even identify
  a LERC_DEFLATE-compressed one as an image file at all (`UnidentifiedImageError`) — verified
  directly. `tifffile` (common in the non-GIS/numpy scientific-Python world) needs the optional
  `imagecodecs` package for LERC unconditionally; for ZSTD it works dependency-free only on Python
  ≥3.14 (via the brand-new stdlib `compression.zstd` module, PEP 784, released Oct 2025) — verified
  by reading `tifffile`'s own fallback-codec source and reproducing both the success and the
  `imagecodecs`-required failure. On any Python <3.14 without `imagecodecs` installed, ZSTD would
  fail too in `tifffile` — but ZSTD has a path to zero-dependency support that LERC entirely lacks.

**Net revised conclusion**: LERC is not "universally supported" — it's reliably available in
modern, GIS-specialist/professional-grade builds (current `rasterio` wheels, current GDAL linked
against `liblerc`, Esri's own format ecosystem) but meaningfully less available across general-
purpose, legacy, and Windows-targeted tooling (Ubuntu ≤22.04 LTS system GDAL, R via `rwinlib`,
historical OSGeo4W/QGIS builds, plain `Pillow`, `tifffile` without extras) than ZSTD is on the same
set of tools. This reinforces, rather than changes, 5.5's already-made decision to ship
**ZSTD**, not LERC, for the actual resource — the size numbers alone (5.5) already favored ZSTD for
the lossless comparison; this section's correction just removes a previously-overstated argument
that *would* have favored LERC on portability grounds, when the real evidence points the other way.
See the `hdx-ai-hub` pipeline-builder skill's pattern-catalog entry for this same finding recorded
as reusable guidance for future raster pipelines.

## 5.5 Follow-up: ZSTD compression tested (2026-08-06)

Real (not mocked/extrapolated) windowed read from the live public S3 COG, 2025, clipped to DR
Congo's actual `cod-ab-global` admin1-union bbox (`12.1957°E`–`31.3146°E`, `-13.4590°S`–`5.3923°N`
— the real boundary source, already downloaded locally from a prior run, not the OSM/Nominatim
stand-in 5.3 used) via the same `rasterio.windows.from_bounds()` path `pipeline.py` uses:
**21208×21509 px = 456,162,872 pixels, 2.20% nodata** — refines 5.3's ~460M-pixel estimate with a
real boundary-source measurement rather than an OSM approximation. Written with GDAL's `COG`
driver, `COMPRESS=ZSTD`, so these sizes include the same overview-pyramid overhead as the plain
LZW/DEFLATE/LERC figures already in 5.3/5.4 — a directly comparable like-for-like measurement, not
a stripped-down one.

For each of the two candidate dtypes already in play (5.3's float32-vs-int16 trade-off), tested the
ZSTD predictor options relevant to that dtype (`1` = none, `2` = horizontal differencing for
integers, `3` = floating-point predictor) at compression level `9` and level `15`:

**float32 (self-describing Mg/ha, no scale-factor gotcha for consumers — see 5.3):**

| Predictor | Level 9 | Level 15 |
|---|---|---|
| 1 (none) | **1248.5 MB** (18.0s) | 1239.9 MB (64.6s) |
| 3 (floating-point) | 1367.3 MB (18.9s) | 1356.6 MB (63.6s) |

Predictor 3 makes it *worse*, not better — the same pattern 5.3 already found for LZW+predictor 3
on this noisy float data (436.1MB vs 375.7MB for Cameroon); ZSTD doesn't change that. Level 15 only
buys 0.7% over level 9 (1239.9 vs 1248.5MB) for ~3.6× longer to write (64.6s vs 18.0s) — not worth
it, per the "similar → report the faster level 9" rule.

**Best float32: predictor 1, level 9 → 1248.5 MB.**

**int16 (×10-scaled, scale-factor gotcha per 5.3):**

| Predictor | Level 9 | Level 15 |
|---|---|---|
| 1 (none) | 844.2 MB (12.4s) | 842.2 MB (34.3s) |
| 2 (horizontal differencing) | **819.7 MB** (12.5s) | 818.6 MB (34.5s) |

Predictor 2 helps here, as expected for integer data. Level 15 only buys 0.13% over level 9 (818.6
vs 819.7MB) for ~2.8× longer (34.5s vs 12.5s) — not worth it, same rule.

**Best int16: predictor 2, level 9 → 819.7 MB.**

### How ZSTD compares to 5.3/5.4's other codecs (DR Congo, same source window)

| Encoding | Size |
|---|---|
| float32, plain LZW (current shipped design) | 1709.2 MB |
| float32, LERC_DEFLATE, lossless (measured to answer this directly) | 1298.2 MB |
| float32, ZSTD, predictor 1, level 9 (this test) | 1248.5 MB |
| float32, LERC_DEFLATE, ±0.05 Mg/ha bounded error | 816.5 MB |
| int16, ZSTD, predictor 2, level 9 (this test) | 819.7 MB |
| int16, LERC_DEFLATE, lossless | 804.7 MB |
| int16, LERC_DEFLATE, ±1 raw unit bounded error | 729.5 MB |

Plain lossless ZSTD closes most of the gap LZW left on the table — float32 drops 27% (1709.2 →
1248.5MB) and int16 lands within 1.9% of LERC's *lossless* number (819.7 vs 804.7MB) with no
`MAX_Z_ERROR` tuning decision needed at all. **Comparing lossless-to-lossless (the only fair
comparison), ZSTD actually beats LERC_DEFLATE for float32**: 1248.5MB vs 1298.2MB, ~3.8% smaller —
LERC only pulls ahead of ZSTD once it's allowed to drop precision (the 816.5MB bounded-error row).
For int16, LERC's lossless mode (804.7MB) edges out ZSTD's lossless mode (819.7MB) by ~1.9% instead.
Either way — like every other encoding tried so far — none of these get DR Congo into a
plausibly-uploadable range. Consistent with 5.3/5.4's conclusion: DR Congo's problem is data volume,
not a fixable encoding inefficiency; codec choice narrows the gap but doesn't close it.

### 5.6 Follow-up: what if compression weren't forced at all? (2026-08-07)

For completeness — quantifying how much work the explicit `compress=ZSTD, predictor=STANDARD,
level=9` creation options in the 5.5 decision are actually doing, versus just leaving the `COG`
driver's own defaults in place. `gdalinfo --format COG`'s `<CreationOptionList>` confirms those
defaults are `COMPRESS=LZW`, `PREDICTOR=FALSE` (no predictor) — not ZSTD, and not the predictor-2
integer differencing 5.5 found helpful for int16.

**DR Congo (`cod`), int16, plain default LZW (no predictor)** — measured directly (same live
source, same real `cod-ab-global` bbox as 5.5, 456,162,872 px): **1132.0 MB**. Verified as a valid
COG (`gdalinfo`: `COMPRESS=LZW`).

| Encoding | Size |
|---|---|
| int16, plain LZW, no predictor (GDAL `COG` driver defaults, unforced) | 1132.0 MB |
| int16, ZSTD, predictor 2, level 9 (5.5, current shipped) | 819.7 MB |
| int16, LERC_DEFLATE, lossless (5.4) | 804.7 MB |

Leaving compression at GDAL's defaults instead of forcing ZSTD+predictor would make DR Congo's file
**~38% larger** (1132.0 vs 819.7MB) — confirms the explicit creation options in the 5.5 decision are
doing real, non-marginal work, not a redundant belt-and-suspenders tweak over what `COG` would do
unprompted.

---

### Decision: int16 + ZSTD for now (2026-08-06), interim — DR Congo still unresolved

**Decided (user, 2026-08-06): switch the shipped encoding to int16 + ZSTD (`predictor=STANDARD`,
`level=9`)**, superseding an intermediate float32+ZSTD version tried first in this same session.
Per 5.5, int16+ZSTD (819.7MB on DR Congo) beats float32+ZSTD (1248.5MB) by ~34%, so once the
scale-factor usability cost (5.3) was mitigated (below) rather than avoided, int16 became the
better call. Implemented in `pipeline.py`'s `get_country_raster()`:
- Source pixels are written straight through as `int16` (still ×`agb_scale_factor`-scaled, not
  divided) — no more `astype("float32")`/divide-by-10/`nan`-remap step.
- `nodata` is set to the configured `agb_fill_value` (`-9999`) directly, rather than remapping to
  `NaN` — this is the sentinel's native representation, not a workaround.
- COG creation options: `compress=ZSTD`, `predictor="STANDARD"` (the `COG` driver's string-select
  alias for integer horizontal differencing — using the bare integer `2`, like plain `GTiff`
  expects, raised a silent `CPLE_NotSupported` warning and fell back to no predictor), `level=9`.
- **Mitigating the scale-factor usability cost**, so this isn't a silent regression from float32's
  self-describing Mg/ha values:
  - `dst.scales = (1/agb_scale_factor,)` / `dst.offsets = (0.0,)` are written into the GeoTIFF's
    standard per-band `Scale`/`Offset` metadata (visible via `gdalinfo`), so GDAL-aware tools (e.g.
    QGIS's Identify) show the real Mg/ha value automatically.
  - The per-resource `description` now explicitly states the ×10 scaling and warns that a plain
    `rasterio`/`GDAL` array read does **not** apply the `Scale` tag automatically.
  - The dataset-level `caveats` field (previously a blank placeholder, see 1.3 #7) now carries the
    same warning — `caveats` is HDX's dedicated field for exactly this kind of interpretation
    gotcha, and it renders prominently on the dataset page, not just next to the download link.
  - `notes` (previously claimed "Values are in megagrams per hectare (Mg/ha)", which would now be
    false) is corrected to describe the ×10 int16 encoding and points to `caveats`/the resource
    description for detail.
  - Put in both dataset (`caveats`/`notes`) and resource description deliberately, not just one:
    `caveats` is the structured, page-level field; the resource description is what's physically
    next to the file someone is about to open. Different audiences/moments, not redundant.
- `uv run pytest` (7 tests, updated for the new dtype/nodata/scale assertions) and
  `pre-commit run --all-files` both green after the change.

**Explicitly interim, not a full resolution**: DR Congo goes from 1.71GB (old float32+LZW) to
**819.7MB** (int16+ZSTD) — real progress (~52% smaller) but still very likely over whatever limit
produced the original 413 (5.3's Cameroon 375.7MB was already rejected, and DR Congo's
ZSTD-compressed size is still ~2.2x that). The other options from the previous revision of this
section remain open and not yet chosen among for closing that remaining gap:

1. ~~Switch to float32 + LERC_DEFLATE with a small bounded error~~ — superseded by the int16+ZSTD
   decision above; a bounded-error LERC or ZSTD variant is still on the table if DR Congo (or other
   large countries) still fails to upload after this change.
2. Find the actual nginx/CKAN upload limit from DPT/DSys before deciding whether any further
   encoding change is enough, or whether large countries need a structural fix. Still not done.
3. Tile the largest countries into multiple resources (e.g. per admin1) rather than one
   country-wide raster — a real design change, not yet scoped.
4. Keep the now-improved encoding, rely on the now-fixed per-country isolation (5.2) so countries
   still too large are cleanly skipped/logged rather than crashing the run, and treat further
   shrinkage as a follow-up ticket.

DR Congo remains the actual stress-test case before considering this resolved: confirmed at 1.71GB
under the original encoding, confirmed at 819.7MB under the new int16+ZSTD encoding — real
progress, but very likely still too large without a structural change (option 3) or a confirmed
higher limit (option 2).

---

## 5.7 `methodology_other` filled in from ctrees.org/products (2026-08-07)

Per §1.3 #7/§3.3, `methodology_other` had been left as a literal `Placeholder` pending CTrees/DPT
completing HDX's own metadata form (still outstanding). The user pasted the actual text of
ctrees.org/products (WebFetch couldn't render the JS page directly) — CTrees' own published
description of the methodology behind their "Land Carbon Map" product. That page's methodology
covers three things: (1) AGB via LiDAR (NASA ICESat/GEDI) calibrated against >1.5M ground plots,
combined with ecoregion-customized (800+ ecoregions) change-detection ML using radar/optical
imagery; (2) belowground biomass via ecological models; (3) uncertainty via error propagation
models. This pipeline ships only the AGB band — no belowground layer, no uncertainty layer (see
`pipeline.py`'s `get_country_raster`/`generate_dataset`, `config/project_configuration.yaml`'s
single `agb_cog_url_template`) — so `methodology_other` was written to describe only the
AGB-producing part of (1), explicitly note that (2)/(3) are part of CTrees' broader product but are
**not** included here, and cite the two peer-reviewed references the page links (Saatchi et al.
2011, Xu et al. 2021).

**`methodology`/`methodology_other` is no longer a bare copier-default placeholder** — it's now
populated from CTrees' own public, citable content, independent of whether the formal CTrees/DPT
HDX metadata form ever gets completed.

**2026-08-07, `license_id` confirmed:** the user directly confirmed the license is Creative Commons
Attribution 4.0 International. Checked against HDX's live `license_list` API
(`https://data.humdata.org/api/3/action/license_list`): `cc-by` maps to "Creative Commons Attribution
International (CC BY)" — i.e. the copier default already sitting in `hdx_dataset_static.yaml`
(`license_id: cc-by`) happens to be the right value. No YAML change was needed, but its status
changes from "copier-default placeholder, unconfirmed" (§1.3 #7) to "confirmed correct." `owner_org`
and `maintainer` remain the interim stand-ins described in §1.3 #6 — still pending a permanent HDX
org from CTrees/DPT.

---

## Skill improvements made as a result of this run

In addition to the two from the first pass (cross-category capability gaps; HDX intake-ticket
recognition), this pass added a third:

- **Data Grid country list, programmatically** — `hdx-ai-hub/skills/analysis/references/
  hdx-concepts.md` and `ckan-api.md` now document the verified `group_list?all_fields=true&
  include_extras=true` call filtered on `data_completeness=="active"` (22 countries as of
  2026-08-03), including the slower `group_show`-per-country and auth-gated `hdx_datagrid_show`
  alternatives. `pipeline-pattern-catalog.md` category 2 now points here whenever a ticket asks to
  scope a per-country loop to "priority"/"data grid" countries, with a note to treat it as a
  live/short-TTL lookup rather than a frozen static list.

Left for later: no pattern-catalog entry yet for "raster + per-country scoping" as its own
combination shape (deferred per user request, previous pass); no pattern-catalog entry yet for the
`cod-ab-global` country-boundary/bbox sourcing approach used here (admin1-layer filter + GDB
extraction quirk) — worth adding once this pipeline has actually exercised it end-to-end, since a
design-time decision isn't the same as a verified-in-code pattern.
