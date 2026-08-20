# 0004: Per-country try/except must wrap the HDX upload call, not just fetch/clip/generate

## Status

Accepted — 2026-08-04

## Context

The design called for per-country failure isolation (one bad country must
not abort the whole run), but the original `__main__.py` implementation
only wrapped the fetch/clip/`generate_dataset` steps in the per-country
`try` block — `create_in_hdx()`/`update_from_yaml()` ran outside it. A real
end-to-end run hit a live `413 Request Entity Too Large` on Cameroon's
upload, which crashed the whole batch and would have silently skipped every
Data Grid country alphabetically after it.

## Decision

Move `update_from_yaml()`/`create_in_hdx()` inside the per-country `try`
block.

## Consequences

An oversized or otherwise-failing country is now cleanly logged and
skipped, not a batch-ending crash. This interacts directly with 0003's
encoding choice: countries still too large after encoding improvements
(e.g. DR Congo) fail gracefully instead of taking down the run.
