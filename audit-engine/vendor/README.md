# XML parser provenance

The ESM file `sax-1.6.1.mjs` wraps the unmodified `lib/sax.js` from npm `sax@1.6.1`, licensed under BlueOak-1.0.0. See `SAX-LICENSE.md`. It exports only the synchronous SAX parser; no package installation or network access is needed at runtime.

Upstream: https://github.com/isaacs/sax-js

Registry tarball integrity: `sha512-42tBVwLWnaQvW5zc4HbZrTuWccECCZfBi92FDuwtqxasH+JbPB3/FOKb1m222K42R4WxuxzzMsTswfzgtSu64Q==`.

`build_xml_vendor.py` checks the SHA-256 of both upstream source and license before adding an ESM export wrapper. To reproduce, install exactly `sax@1.6.1` into an isolated directory with npm `--ignore-scripts`, then pass its `node_modules/sax` directory to that script. It does not download code itself. Parser use is strict, namespace-aware and limited to predefined XML entities; the adapter additionally rejects DTD/SGML declarations and imposes structural limits.
