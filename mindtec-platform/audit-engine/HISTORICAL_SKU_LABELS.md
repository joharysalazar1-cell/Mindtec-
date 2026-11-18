# Original versioned SKU label evidence

`kobo_label_evidence.py` reads an explicitly selected original Kobo XLSX export
with expanded label columns. It preserves cell coordinates, original Excel types,
parent IDs, repeat indices and form version identifiers. Unrelated repeated
question headers are never collapsed into a dictionary keyed only by label.

The parent sheet requires unique `_id`, `__version__` and `_index` columns.
Supported brand repeat sheets are `rep_bsa_*` and `rep_lac_*`, with their exact
brand fields, expanded SKU option headers, `_submission__id`,
`_submission___version__` and `_parent_index`. Only explicit `1` or `true` values
select an expanded option. Other nonempty, nonzero values remain invalid option
evidence. Missing or zero selections are not certified product absence.

Each child is linked using the parent ID, index and version together. A version
or index mismatch remains unresolved. Selected cells and the corresponding header
coordinates are retained so label extraction can be checked independently.

```powershell
python kobo_label_evidence.py --workbook private/input/original-labels.xlsx --output private/kobo-labels/new-cut
python -m unittest test_kobo_label_evidence test_historical_sku_contrast -v
```

The output directory must be new. It retains the original workbook, extracted
evidence, calculation modules and hashes. It performs no network calls or edits
to the source workbook or running observers.

`historical_sku_contrast.compare` links this evidence with a typed normalized
workbook cut using an explicit one-to-one internal-ID/Kobo crosswalk, subcategory
code and brand code. It rejects ambiguous candidate rows rather than selecting a
first match. Literal label-set differences are preserved separately from row
recovery. Required historical fields and parent bindings must be resolved before
a row is described as recovered.

An original historical label is independent evidence of what the export records.
It does not replace later Scan corrections, certify a universal code-to-label
mapping, establish field truth, or define the official core-SKU scoring rule.
No positional pairing between code lists and labels is performed.
