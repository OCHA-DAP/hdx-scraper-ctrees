# 0009: Stream raster writes to stay under Jenkins' 2GB memory limit

## Status

Accepted — 2026-10-22

## Context

The Jenkins run failed with exit code 137 (SIGKILL, the OOM killer). The Jenkins memory limit is
2GB. Per-country isolation (`0004`) can't catch a SIGKILL, so the whole batch died.

`get_country_raster()` held about three full uncompressed copies of each country's raster:
- the array from `src.read()` / `vrt.read()`
- `data.astype("int16")`, which copies even though the source is already int16
- rasterio's buffer for a COG opened for writing. The COG driver has no `Create`, so rasterio
  writes to an in-memory MEM dataset and `CreateCopy`s it on close
  (`rasterio/_io.pyx`, `BufferedDatasetWriterBase`).

At int16, that is ~0.9GB per copy for DR Congo (21,509 × 21,208) and ~1.1GB for Brazil at 200m
(25,392 × 21,950).

`get_country_bbox()` also read the whole `cod-ab-global` admin1 layer, geometries included, for
every country. That peaked at 640MB.

## Decision

- Write each raster in 1024-row strips to a tiled, ZSTD level 1 temp GTiff, which supports
  incremental writes. Then `rasterio.shutil.copy` it to the final COG with the existing creation
  options. GDAL's COG `CreateCopy` reads the GTiff block by block and keeps nodata/scale/offset.
- Set `GDAL_CACHEMAX` to 256MB. GDAL's default is 5% of the host's RAM, which may not reflect a
  container's limit.
- Get bboxes from `pyogrio.read_bounds(..., where="iso3 ILIKE 'xxx'")`, which reads per-feature
  bounds without loading geometries. `ILIKE` keeps the old case-insensitive match on the data.
  `iso3` is validated as three letters first, since `ILIKE` treats `%` and `_` as wildcards.
  Features with null geometry have NaN bounds, so `np.nanmin`/`np.nanmax` skip them, as
  `total_bounds` did.

## Alternatives considered

- **VRT straight to COG, no temp GTiff.** A `.vrt` holding the window, 2×2 average, nodata
  (`vrt://...?a_nodata=-9999`, since the source has no NoData tag) and scale was
  `rasterio.shutil.copy`'d to COG. Output was identical to the strip writer at 100m, and within
  0.5 of the exact 2×2 mean for downsampling, with no strip-size dependence. It was rejected as too
  slow, measured on 2026-10-22:

  | Country | Strips | VRT |
  |---|---|---|
  | Syria (100m) | 21s, 258MB | 153s, 244MB |
  | DR Congo (100m) | 4 min, 346MB | 31.5 min, 247MB |

  The COG driver reads the remote source in small blocks, twice (overviews, then full
  resolution). Enabling `VSI_CACHE` (512MB), multi-range and 2MB curl chunks didn't help (147s
  for Syria). Neither did a plain `SimpleSource` without `vrt://` (142s).
- **Averaging VRT instead of `WarpedVRT` for downsampling.** Reading strips from the same
  `ComplexSource` average VRT made output independent of the strip size, and still within 0.5 of
  the exact 2×2 mean. It was rejected as too slow: Brazil had only written ~510MB of its temp
  GTiff after 34 min (~12.6MB/min) and was stopped, against 12.4 min end to end with `WarpedVRT`.

## Consequences

Measured on 2026-10-22 against the live source, each run under a 2GB cgroup cap
(`systemd-run --user --scope -p MemoryMax=2G -p MemorySwapMax=0`):

| Country | Peak RSS | Time | Output |
|---|---|---|---|
| DR Congo (100m) | 346MB | 4 min | 859.3MB (819.5MiB) |
| Brazil (200m) | 395MB | 12 min | 672.5MB |

The bbox lookup for DR Congo went from 640MB to 134MB peak, with an identical result.

- Both outputs have `LAYOUT=COG`, overviews 2-64, scale 0.1 and nodata -9999.
- 100m pixel values are unchanged.
- For downsampled countries (Brazil), GDAL's average resampler rounds .5 ties differently
  depending on the read window. On the LBN fixture, 1,861 of 969,441 pixels differ by 1 raw unit
  (0.1 Mg/ha) between strip and single reads. Both are within 0.5 of the exact 2×2 mean.
- Each country needs a temp GTiff on disk (deleted after the copy) alongside its output.
- The upload size limit (CLAUDE.md "Known Limitations") is unaffected.
