-- Bootstrap: attaching the local DuckLake catalog (local by default; see docs/adr/0001-engine-and-lake.md).
-- Run from the repo root so the relative catalog/ and data/lake/ paths resolve.
INSTALL ducklake;
ATTACH 'ducklake:catalog/gdgap.ducklake' AS lake (DATA_PATH 'data/lake/');
USE lake;
