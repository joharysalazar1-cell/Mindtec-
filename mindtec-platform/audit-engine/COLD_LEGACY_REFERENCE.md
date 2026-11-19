# Legacy global cold-face reference

`cold_legacy_reference.py` recovers the share of each brand within the recorded global cold-face list of the legacy questionnaire. It does not allocate faces to categories and must not replace the category cold-share KPI. Zero means zero faces in the enumerated list, not independent proof of physical absence.

The calculation checks the declared number of brands, repeat indices, selected codes, duplicate codes, nonnegative integer counts, answer hashes and source-cell identities. Repeated category inventories of one visit cannot multiply the global denominator. Explicit no-cooler evidence may resolve empty exported repeat slots; a conflicting filled row remains pending. If any visit is pending, the complete-visit subset is labelled separately and the whole-cohort result remains unavailable. October and annual comparisons are not inferred.

## Reproducible custody

`cold_legacy_run.py` binds the calculation to an explicit SHA-256 of an existing retained cold result and its exact original detailed workbook. It verifies every used cell coordinate, original question header, row and value. Brand identities come from the retained cold result, not an unrelated current catalogue.

Example from the engine directory, with operator-selected paths and the actual retained result hash:

```powershell
python cold_legacy_run.py --cold-result private/input/cold-result.json --workbook private/input/detail.xlsx --expected-result-sha256 ACTUAL_SHA256 --output private/legacy-cold/run-001
python cold_legacy_run.py --verify private/legacy-cold/run-001
python -m unittest test_cold_legacy_reference test_cold_legacy_run -q
```

Custody retains the original workbook, original cold result, calculation result and all four calculation/parser modules. Verification checks all retained bytes and recomputes the result. Rehashing a fabricated output in the manifest does not make it pass replay. Existing custody is never overwritten. A failed source or workbook hash is rejected before creating output custody.

This module does not install an observer, change exclusion policy, edit answers, restart the supervisor, publish a website or send evidence over the network. Continuous scheduling must be integrated and verified separately. The original category reconstruction remains authoritative for its own scope.

The custody manifest proves internal reproducibility and source binding. It is not an external signature, a certification of field truth, or evidence of fraud. Preserve an independent copy of its hash if external anchoring is required.

## Continuous reconstruction cycle

`cold_legacy_stage.py` integrates this reference as the ninth processing stage of reconstruction-cycle/1.1.0. The existing reconstruction observer runs it from the same accepted cold and Perfect Store execution as the other stages. The stage retains the original cold result, its execution receipt, original detailed workbook and calculation bundle; `verify(runtime)` replays and checks the original cells. This adds no external data transfer, scheduled task or automatic Site publication. The category cold-share KPI is unchanged.
