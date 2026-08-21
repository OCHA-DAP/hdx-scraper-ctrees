# 0006: Interim initial-build scope and dataset-identity choices

## Status

Accepted (interim) — 2026-08-03

## Context

Building the initial pipeline required settling several scope/identity questions with no
CTrees/DPT-confirmed final answer yet:

- The source is 4.26 TB of history across all years; building against the full history
  first would be a large, possibly unnecessary effort before any real usage pattern is
  known.
- No permanent HDX organization or maintainer for CTrees data had been confirmed.
- DPT's HDX metadata form (license, methodology, caveats) had not been completed.
- Whether to ship a raw per-country GeoTIFF or a summarized/aggregated output was open.

Blocking implementation on final answers to all four would have stalled the build
indefinitely.

## Decision

Proceed on interim values for the initial build, each explicitly flagged as revisitable:

- **Scope**: latest year only, not the full multi-year history.
- **Dataset identity**: `owner_org: hdx`, `maintainer: 196196be-6037-4488-8b71-d786adf4c081`
  (Michael Rans) — a stand-in pending a permanent CTrees/DPT-confirmed organization.
- **Metadata**: proceed with copier-default placeholders (`license_id: cc-by`,
  `methodology: Other`, blank `caveats`) rather than wait for DPT's metadata form.
- **Output shape**: per-country raw GeoTIFF, not an aggregated/summarized product.

## Consequences

Unblocked the initial build without waiting on external confirmations. Reassigning
org/maintainer later is a routine HDX metadata edit (low risk). The ticket's own
Definition-of-Done item (partner-completed metadata form) remains open at the ticket level
and is not satisfied by these placeholders. Full-history backfill and the raw-vs-aggregated
output shape remain open for revisit once real usage patterns are understood — this record
does not resolve either, only the decision to defer them.
