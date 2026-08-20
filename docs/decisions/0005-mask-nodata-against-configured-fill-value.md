# 0005: Mask raster nodata against a configured fill value, not the source's own nodata tag

## Status

Accepted — 2026-08-04

## Context

The chosen S3 COG source (see 0001) carries no GDAL NoData tag of its own,
even though its documented fill value is -9999 (matching the equivalent
Zarr source's `_FillValue`). The original `get_country_raster()` read
`src.nodata` to decide which pixels to mask, which silently evaluated to
`None` against the real source — nodata pixels (water bodies, etc.) leaked
through as raw `-999.9` instead of being masked. The bug went undetected by
the test suite because the committed fixture, captured earlier via
`rioxarray`, had a NoData tag baked in by `rioxarray`'s own write path — the
mock was "nicer" than the real source.

## Decision

Add `agb_fill_value: -9999` to `project_configuration.yaml`;
`get_country_raster()` masks against this configured value instead of
`src.nodata`.

## Consequences

Correct masking regardless of whether the upstream COG happens to carry its
own NoData tag. The regression test now builds an in-memory copy of the
fixture with the NoData tag explicitly stripped before feeding it to the
mock, so it matches the real source's actual metadata behavior and would
catch this again if reintroduced.
