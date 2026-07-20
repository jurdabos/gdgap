-- R1, R6: ISO/IEC 5218:2022 implemented as the code list's standard core, then extended per the
-- McClure et al. (2022) engagement — extension rows are flagged as such, never squeezed into the binary.
CREATE SCHEMA IF NOT EXISTS lake.aware;
DROP TABLE IF EXISTS lake.aware.dim_sex_code;
CREATE TABLE lake.aware.dim_sex_code AS
SELECT * FROM (
    VALUES
        ('0', 'Not known', 'ISO/IEC 5218:2022', FALSE),
        ('1', 'Male', 'ISO/IEC 5218:2022', FALSE),
        ('2', 'Female', 'ISO/IEC 5218:2022', FALSE),
        ('9', 'Not applicable', 'ISO/IEC 5218:2022', FALSE),
        ('X', 'Non-binary or another gender identity', 'gdgap extension (McClure et al., 2022)', TRUE),
        ('U', 'Undisclosed - declined to state', 'gdgap extension (McClure et al., 2022)', TRUE)
) AS t(sex_code, label, source_standard, is_extension);
