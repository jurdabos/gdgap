-- R1, R3, R8: sex/gender as a first-class Type-2-style (validity-interval) dimension; the sex_source
-- provenance column records reported-vs-imputed (R3), sex_code_reported keeps the pre-imputation state
-- exhibitable, and validity intervals make the attribute time-variant (R8). Initial load opens the
-- interval at the survey period start; a change of recorded gender would close it and append a new row.
-- Facts carry no dimension-version key; analytical views join the natural key plus is_current, so
-- reporting is by current recorded identity — a deliberate choice recorded in ADR-0005.
CREATE SCHEMA IF NOT EXISTS lake.aware;
DROP TABLE IF EXISTS lake.aware.dim_person_sex;
CREATE TABLE lake.aware.dim_person_sex AS
SELECT
    p.HOUSEID AS houseid,
    p.PERSONID AS personid,
    analysis.sex_code AS sex_code,
    reported.sex_code AS sex_code_reported,
    CASE
        WHEN p.R_SEX IN ('-7', '-8', '-9') THEN 'imputed'
        WHEN p.R_SEX <> p.R_SEX_IMP THEN 'edited'
        ELSE 'reported'
    END AS sex_source,
    DATE '2016-04-01' AS valid_from,
    CAST(NULL AS DATE) AS valid_to,
    TRUE AS is_current
FROM lake.nhts2017.perpub AS p
JOIN lake.aware.map_nhts_sex AS analysis
    ON analysis.nhts_code = p.R_SEX_IMP
JOIN lake.aware.map_nhts_sex AS reported
    ON reported.nhts_code = p.R_SEX;
