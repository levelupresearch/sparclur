# Changelog

## 2026.9.9

### Added

- Python 3.10 through 3.14 support and continuous integration for the oldest
  and newest supported versions.
- Modern package metadata, wheel validation, publishing automation, and a
  `sparclur-ui` console command.
- A layered, user-editable YAML configuration API.
- Optional extras for PyMuPDF, PDFium, PDFMiner, and the Streamlit interface.
- Native HTML report generation with evidence bundles, batch triage, and a
  Pweave-compatible `SparclurReport` facade.

### Changed

- Refreshed the Streamlit interface for current Streamlit releases, including
  native PDF upload, available-parser defaults, compact parser settings, and
  manual PRC refresh.
- Modernized parser discovery and current Python adapter integrations.
- Improved PRC and Spotlight visual layouts.

### Fixed

- Repaired configuration, resource, uploaded-document, comparison-option, and
  parser-capability handling.
- Replaced the unsupported Pweave/IPython report execution flow with a native,
  structured report exporter.
