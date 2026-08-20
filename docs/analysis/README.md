# docs/analysis/

One running document per Jira-driven pipeline build, produced by the
`pipeline-builder` skill: requirements summary, template analysis, design,
implementation plan, and a log of implementation findings — the full
narrative record of how and why the pipeline was built.

Named `<TICKET>-<partner>.md` (e.g. `HDXPIPE-100-ctrees.md`). Updated in
place as the build progresses, not replaced per stage.

Settled architecture/design decisions get a distilled, durable copy in
`../decisions/` (see `../decisions/README.md`) — this folder stays the full
point-in-time investigation; `decisions/` is what to check first for *why*
something is built the way it is.
