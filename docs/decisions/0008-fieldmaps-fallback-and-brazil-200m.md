# 0008: fieldmaps COD fallback for boundaries, and Brazil at 200m

## Status

Accepted — 2026-09-30

## Context

After the switch to GHO countries (`0007`), 12 of the 55 have no admin1 rows in `cod-ab-global`:
abw, arg, bra, cub, cuw, dji, guy, jor, pry, tto, tza, ury. The per-country HDX `cod-ab-{iso3}`
datasets exist for all but jor, but they are inconsistent across countries:
- The formats differ (SHP vs GDB zips).
- Layer names differ (`arg_admbnda_adm0_unhcr2017`, `CUW_adm0`, `pry_admin0`).
- CRSs differ (ARG adm0/adm1 are EPSG:3857; BRA has no CRS).

fieldmaps (https://fieldmaps.io/data/cod/) republishes the same COD data, "automatically
extracted from the ITOS ArcGIS Server", as one GeoPackage per country.

Brazil's bbox (45.1° × 39.0°) is ~4.9x DR Congo's in pixel count, and DR Congo at 100m is already
819.7MB (`0003`).

## Decision

- If `cod-ab-global` lacks a country, take its bbox from the `{iso3}_adm0` layer of
  `https://data.fieldmaps.io/cod/originals/{iso3}.gpkg.zip`. All of these files are EPSG:4326
  and use the same layer naming.
  - The "extended" files are not used, since they are extended beyond the country's own extent.
  - `data.fieldmaps.io/cod.csv` doesn't list abw or cuw, but their originals files exist and
    have `abw_adm0`/`cuw_adm0` layers.
  - jor returns 404 and is logged and skipped by the per-country isolation (`0004`).
- Publish Brazil at 200m (`downsample_factors: {bra: 2}`). Each 2x2 block is averaged through a
  GDAL `WarpedVRT` with `src_nodata=-9999`. The source COG has no NoData tag, so without this
  -9999 would be averaged into real values.

## Consequences

- The fallback depends on a second external host (fieldmaps). Its files are CC BY-IGO,
  re-extracted from HDX's `cod-ab-{iso3}` data.
- Brazil's 200m output, measured on 2026-09-30:
  - 671.2MB, 25,392 × 21,950 pixels at 0.001778°
  - 18.4 minutes to build, peak RSS 5.0GB

  That is below DR Congo's 819.7MB but above Cameroon's rejected 375.7MB. The upload limit is
  still unknown (see `CLAUDE.md` Known Limitations). If Brazil is still rejected, raising its
  factor is a one-line config change.
- Averaging keeps Mg/ha semantics, but it smooths local extremes. The resource description
  states the 200m resampling.
