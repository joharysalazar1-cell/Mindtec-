# Inputs for weighted distribution

`weighted_inputs_run.py` audits inputs from compatible, retained shelf and cold-conversion executions. It does not reconstruct the official weighted-distribution percentage.

The observed-size candidate is category shelf faces plus four times the number of cooling doors across reported equipment. A known subtotal is not a complete total. Positive operation of one cooler does not establish complete equipment or door enumeration. The category applicability of equipment must still be fixed before using the candidate as an official weight.

Company purchase amounts and frequencies remain original tokens. The module does not invent range midpoints, monthly frequency factors, company-to-category allocations or normalization between purchase and size weights. Official weights remain null until those rules are supplied and verified.

## Execute

Run from the audit-engine directory. Inputs must be outside the output custody, and source runtimes must be distinct from it.

```powershell
python weighted_inputs_run.py --help
python -m unittest test_purchase_binding test_weighted_inputs test_weighted_inputs_run -q
```

Required arguments are `--shelf-runtime`, `--conversion-runtime`, `--runtime`, `--definition-evidence` and `--definition-sha256`. The definition digest must match the original evidence bytes. Executions retain source results, original workbooks, exclusion policy, implementation and evidence in the hash-verified ledger. The runner checks that the admitted cohort and source executions agree.

## Optional purchase header aliases

`--purchase-bindings` accepts a versioned `mindtec-purchase-header-binding/1` configuration. It pins `source_sha256`, exact historical form identity, repetition `rep_empresa_compra`, field `monto_compra_empresa`, and an exact export-header template containing `{index}`. It also requires per-form observation records with absolute file paths and SHA-256 digests. Observation bytes and the configuration are retained.

Aliases address a question-label change between the retained historical schema and a shared export header. They apply only within their declared source and form. Existing conflicting, ambiguous or unresolved mapped routes cannot be silently overridden. A missing cell remains unknown; no historical answer value replaces it.

The recovered row records the alias version, original route state and source coordinate. The original missing-route evidence and physical export cell are both preserved. The shared historical schema and original answers are never edited. A reconstruction alias is not a certification of the official calculation or a human review decision.

## Outputs and review

The snapshot includes `equipment`, `purchase_declarations`, `category_stores`, `monthly_readiness`, original `cells` and `answer_evidence`. `purchase_header_bindings` identifies the optional reconstruction configuration. Inspect the execution's retained source result when reproducing an earlier version rather than assuming the latest execution is identical.

Keep manual review files separate from snapshots and source workbooks. Link observations by visit ID, month and source coordinate. Leave the human review state pending until a person records the decision and evidence. This module neither uploads data nor changes survey answers, review decisions or other KPI.
