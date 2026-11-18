# Coherent local reconstruction cycles

`reconstruction_cycle.py` chains existing reconstruction runners against one observer-accepted Perfect Store execution. `reconstruction_watch.py` polls that accepted local source. Neither module downloads external data, sends messages, uploads evidence or publishes a Site.

Eight stages are retained: declared numeric distribution, shelf share, cold share, company availability reference, POP, cold conversion, weighted-input readiness, and the integrated projection. These are processing stages, not eight completed official KPI. Weighted distribution remains pending when official weighting rules are missing.

## Profile

The exact `mindtec-reconstruction-cycle/1` profile has `schema`, `version`, absolute `ps_runtime`, absolute `runtime`, absolute `report_dir`, and `inputs`. The profile and all inputs must remain outside output custody and reports. Source, output custody and report directories must be separate.

Each input is an object with an absolute `path` and exact `sha256`. Required input names:

- `shelf_rules`, `cold_rules`;
- `availability_scope`, `availability_definition`;
- `pop_scope`, `pop_definition`;
- `conversion_scope`, `conversion_definition`;
- `weighted_definition`, `weighted_bindings`.

Questionnaire observations referenced by the rules, including the explicit POP absence decision, are checked by hash and retained. Updating a rule means preparing and verifying a new version of the relevant input, not automatically accepting whatever changed on disk.

On Windows, use a short private custody path, for example `C:/MindTEC-private/cycle`, to leave room for context and content hashes. The profile rejects paths that would exceed the Windows object-link path limit before running stages. Keep reports in the selected project report directory.

## Run once or observe

From the audit-engine directory:

```powershell
python reconstruction_cycle.py --profile private/reconstruction-profile.json
python reconstruction_watch.py --profile private/reconstruction-profile.json --interval 60
```

For a bounded local verification:

```powershell
python reconstruction_watch.py --profile private/reconstruction-profile.json --interval 60 --iterations 2
python -m unittest test_reconstruction_cycle test_reconstruction_watch -q
```

The unbounded observer continues only while its process is running. Durable supervision/startup registration is a separate step; creating a profile or successfully running one cycle does not install a service. A bounded observer explicitly marks its health file `stopped` when it exits, preserving the last poll status and accepted result.

## Acceptance and recovery

Every stage must use the selected PS run and snapshot. The source is checked again after computation and report export. Profile or loaded-dependency changes prevent acceptance. A cycle-level lock serializes manual and observer executions; another lock prevents duplicate observers.

Stages are isolated under a hash of source execution, pinned profile and implementation. A failed or interrupted context is not promoted into a completed cycle. Existing accepted cycles remain intact. Recovery can reuse independently retained stage acceptances; a report left by an interrupted attempt is preserved rather than overwritten.

The accepted manifest retains stage results, executions, profile, implementation, source evidence references and HTML. Verification checks each exact stage execution, its custody, result bytes and the retained report. Missing stage custody is rejected without recreating it. An unchanged context reuses a verified acceptance instead of creating duplicate runs and reports.

The observer reports an incompatible source or rule as degraded and preserves its last accepted reference. It does not claim that the old result represents the new cut. Rejections retain their profile bytes and are deduplicated. Human review files, exclusion policies, original answers and official KPI requirements remain separate.

Source-bound questionnaire rules deliberately fail when a new source no longer matches them. Revalidate applicability and prepare a coherent new profile before using those rules for another cut; do not merely replace the SHA without examining the source.

## Scope

Local custody verification establishes reproducibility and provenance, not field truth, official-version equivalence, city-wide sampling confidence or fraud. A new local HTML is not automatically the published dashboard. Missing values and unresolved official rules remain visible.
