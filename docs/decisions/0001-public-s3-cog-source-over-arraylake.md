# 0001: Use the public S3 COG mirror, not the Arraylake/Zarr SDK, as the AGB data source

## Status

Accepted — 2026-08-04

## Context

CTrees' AGB data is available two ways: (Option A) the Arraylake/Earthmover
marketplace Zarr store (`ctrees/aboveground_biomass_100m_global_open`),
requiring an Arraylake account and a service-account API token; and (Option
B) a public, no-auth AWS Open Data S3 bucket
(`s3://ctrees-agb-100m-global/cogs/`) of one global COG per year. Both were
independently verified against the same Lebanon/2025 bbox: identical
windowed shape and raw value range, confirming Option B is not a lesser/
older mirror of the same data.

## Decision

Build against Option B. Read each year's global COG via GDAL's `/vsicurl/`
streaming (plain HTTPS, no AWS credentials), windowed per country with
`rasterio.windows.from_bounds()`.

## Consequences

Drops the `arraylake`/`zarr`/`xarray`/`rioxarray` dependencies entirely — no
Arraylake account, no service-account token, no Bitwarden secret for data
access. Test mocking simplifies to monkeypatching the windowed-COG-open call
rather than mocking an SDK session, since there's no SDK to mock. Introduces
one open, unquantified risk: CTrees describes Option A as "the most
up-to-date," implying Option B could lag on refresh; accepted as
low-probability/low-severity for an annual-cadence pipeline since both
sources agreed on the 2025 data at verification time.
