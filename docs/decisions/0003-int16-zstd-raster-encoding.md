# 0003: Ship raster output as int16 + ZSTD, not float32 or LERC

## Status

Accepted — 2026-08-06

## Context

The initial float32 (real Mg/ha values), plain-LZW encoding produced files
too large to upload for some countries (Cameroon's 375.7MB triggered a 413
from HDX's API; DR Congo measured 1.71GB). Both dtype (float32 vs int16, the
source's native ×10-scaled representation) and codec (LZW, DEFLATE, ZSTD,
LERC) were tested empirically against live data. LERC gave the smallest
lossless sizes but was found to be unreliably supported outside
GIS-specialist tooling (absent from Ubuntu ≤22.04's system GDAL,
historically broken in OSGeo4W/QGIS-on-Windows builds, unsupported by
CRAN's frozen Windows GDAL binary, unreadable by plain Pillow/tifffile
without extras) — meaningfully less portable than ZSTD across the same
tools. int16 halves file size versus float32 with zero precision loss (the
source's finest resolvable unit is already 0.1 Mg/ha), but pushes a "value
×10" interpretation gotcha onto any consumer reading raw array values
without applying the GeoTIFF's Scale tag.

## Decision

Encode output as int16 (undivided, ×10-scaled) with `COMPRESS=ZSTD`,
`PREDICTOR=STANDARD`, `level=9`. Mitigate the scale-factor gotcha by writing
standard GDAL per-band `Scale`/`Offset` tags, and by stating the ×10 scaling
explicitly in both the resource description and the dataset-level
`caveats`/`notes` fields.

## Consequences

DR Congo (the largest country) drops from 1.71GB to 819.7MB — real progress
(~52% smaller) but still very likely over whatever limit rejected the
original file; the remaining gap is an open, unresolved problem (see
`docs/analysis/HDXPIPE-100-ctrees.md` §5.6's options: find the actual upload
limit, tile large countries into multiple resources, or accept per-country
skip via the failure-isolation fix in 0004). A GDAL-aware tool (QGIS
Identify, etc.) shows the real Mg/ha value automatically via the Scale tag;
a plain `rasterio.open(f).read(1)` or bare `gdal.Open()/ReadAsArray()` does
not.
