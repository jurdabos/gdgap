-- R1, R6: gender identity as a separately governed code domain, distinct from the ISO/IEC 5218 sex
-- codes (R1). Category core follows the Stats NZ gender standard; 'U' and 'NC' are gdgap application
-- extensions (never additional standard codes). 'NC' marks non-collection by the source instrument:
-- NHTS 2017 asks sex, not gender identity, and the schema makes that absence queryable (ADR-0006).
CREATE SCHEMA IF NOT EXISTS lake.aware;
DROP TABLE IF EXISTS lake.aware.dim_gender_identity_code;
CREATE TABLE lake.aware.dim_gender_identity_code AS
SELECT * FROM (
    VALUES
        ('1', 'Male', 'Stats NZ gender standard (2024)', FALSE),
        ('2', 'Female', 'Stats NZ gender standard (2024)', FALSE),
        ('3', 'Another gender', 'Stats NZ gender standard (2024)', FALSE),
        ('U', 'Undisclosed - declined to state', 'gdgap application extension', TRUE),
        ('NC', 'Not collected by source instrument', 'gdgap application extension', TRUE)
) AS t(gender_identity_code, label, source_standard, is_extension);
