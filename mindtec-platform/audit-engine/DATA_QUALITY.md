# Versioned technical quality indices

`data_quality.py` measures critical-field nulls, line-key uniqueness, numeric/date formats and optional code existence in an explicitly supplied catalogue. Results are separated by declared collection month and total. Out-of-scope rows remain visible in their own bucket and findings.

Critical fields are `ID SKU`, `Sticker`, `Fecha de emisión`, `Precio unitario` and a separate `Costo unitario`. An absent column is not converted into a row-level null count or a successful zero. The count of rows with any null uses only available critical columns and is explicitly partial if any required column is absent. Overlapping null fields are counted once per affected row.

Uniqueness reports missing keys, excess duplicate rows and all rows involved in duplicates separately, using `ID factura + Línea`. It does not certify that the same underlying document was never captured under another ID. Numeric controls separate empty, unparseable, zero and negative values. Date interpretation uses the supported declared date system; unknown systems are not counted as valid.

Referential controls preserve exact text codes, including leading zeros. They separate absent codes, missing codes, non-text codes and ambiguous catalogue codes. Code existence is not certification of historical SKU meaning or independent store/SKU foreign-key integrity. A missing master or code column remains explicitly unevaluable.

## Retained execution and replay

```powershell
python data_quality_run.py --invoice-runtime private/invoice-runtime --runtime private/quality-runtime --catalogue private/dated-catalogue.csv
python data_quality_run.py --runtime private/quality-runtime --verify
python -m unittest test_data_quality test_data_quality_run -q
```

Source custody must already contain a verified accepted invoice execution and its original workbook. The runner checks original worksheet headers and cells before calculation. It retains original cut bytes, workbook, source execution metadata, catalogue bytes in a valid JSON envelope and the calculation/parser implementation bundle. Verification recomputes the result and findings; merely rehashing a fabricated result cannot satisfy replay. Identical inputs and implementation reuse the accepted run.

The exact original JSON hash and its canonical-content hash are distinct. A library call without original bytes supplies only the canonical hash; it does not claim to identify the original file. The retained runner always binds the exact accepted source bytes.

Findings identify source workbook hash, worksheet, source rows, original line keys, fields and values. Monthly and total views do not create duplicate findings. Human review remains necessary; no automatic correction, person scoring, fraud decision, financial reconciliation or inventory certification is performed.

This runner does not install an observer, download sources, change invoice policies or publish results. Its integration into continuous supervision is a separate step. Catalogue existence and missing-field rates must not be relabelled as a global confidence percentage.

## Continuous observation and supervision

`data_quality_watch.py` observes accepted invoice executions and one catalogue path pinned by SHA-256. It verifies its prior acceptance on restart, rejects changed pins or source paths for an existing custody, preserves the last acceptance on failure and records rejected candidate bytes. It checks source identity and catalogue bytes again before promoting a derived run. Unchanged inputs reuse the same accepted execution. Health is explicitly stopped after a bounded test exits.

A supervisor job of kind `data_quality` requires `invoice_runtime`, `catalogue`, `catalogue_sha256`, `runtime` and an interval of 60–3,600 seconds. Its runtime must be separate from every supervised custody, and its catalogue must be outside them. Exactly one configured invoice observer must own the source. The supervisor waits for fresh health from its owned invoice process; health never authorizes killing a process. The fixed observer script has no network operation.

For a new catalogue version, prepare and verify a new pinned binding and separate custody; do not silently reinterpret the old acceptance against changed master data. A healthy observer means processing and custody succeeded, not that the source contains no anomalies.
