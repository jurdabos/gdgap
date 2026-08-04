-- R1, R6: ISO/IEC 5218:2022 implemented as the sex code list's standard core; the only local row is
-- 'U' (undisclosed), a governed application extension for a nonresponse process state (per McClure et
-- al., 2022, and R7's refusal-vs-ignorance distinction) — never an additional ISO code. Gender identity
-- lives in its own separately governed domain (02_dim_gender_identity_code.sql), keeping sex and gender
-- distinct in the physical design (R1, ADR-0006).
CREATE SCHEMA IF NOT EXISTS lake.aware;
DROP TABLE IF EXISTS lake.aware.dim_sex_code;
CREATE TABLE lake.aware.dim_sex_code AS
SELECT * FROM (
    VALUES
        ('0', 'Not known', 'ISO/IEC 5218:2022', FALSE),
        ('1', 'Male', 'ISO/IEC 5218:2022', FALSE),
        ('2', 'Female', 'ISO/IEC 5218:2022', FALSE),
        ('9', 'Not applicable', 'ISO/IEC 5218:2022', FALSE),
        ('U', 'Undisclosed - declined to state', 'gdgap application extension (nonresponse process state)', TRUE)
) AS t(sex_code, label, source_standard, is_extension);
