# SKU binding and dated catalog audit

These local, read-only tools identify discrepancies between normalized brand rows,
SKU codes and a dated catalog. They do not correct responses, exclude surveys,
establish fraud, or certify physical stock or historical core-SKU compliance.

`sku_binding_audit.py` retains a workbook and an explicitly observed current client
configuration. It flags unequal code/label counts and literal cross-brand prefixes.
It never pairs unequal lists positionally. Its configuration schema is
`mindtec-observed-client-core-configuration/1`; each client has a distinct `id`, a
`core_skus` string list and optional `name`. A name seen in an export is not proof
of physical presence. Historical applicability remains unestablished.

`sku_catalog_contrast.py` checks each occurrence against the dated CSV catalog.
Required semicolon-separated columns are `Código en Kobo`, `Marca` and
`Valor del catálogo`. Missing codes, ambiguous codes, missing brand evidence,
different brands and matching brands are separate states. Counts refer to code
occurrences, not unique products, visits or people. Monthly counts require valid
explicit YYYY-MM values. Current catalog matches do not certify historical labels.

Run from the engine directory, with explicitly selected local inputs:

```powershell
python sku_catalog_run.py --workbook private/input/results.xlsx --catalog private/input/catalog.csv --output private/sku-review/new-cut
python sku_catalog_run.py --verify private/sku-review/new-cut
```

The output directory must not exist. Originals, calculation code, dependencies,
result and a SHA-256 manifest are retained. Verification checks exact file bytes,
requires the retained implementation to match the verifier, and recomputes the
result from the retained originals. It rejects incomplete manifests and modified
results even when their individual hashes were updated. This is local integrity
and reproducibility evidence; it is not a digital signature or independent proof
that an original source was authentic.

The module is currently an explicit command, not an additional supervised job.
It performs no network access or automatic publishing and does not change the
running reconstruction pipeline. A historical correction requires the original
form/version choice list and an explicit version-to-submission correspondence.
Keep original code and label alongside any reviewed correspondence.

Tests:

```powershell
python -m unittest test_sku_binding_audit test_sku_catalog_contrast test_sku_catalog_run -v
```
