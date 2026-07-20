-- R2, R11: blind baseline — person-grain facts carried without any sex/gender attribute; the aware
-- build's R2 disaggregation capability is measured against this deliberate omission (docs/requirements.md).
CREATE SCHEMA IF NOT EXISTS lake.blind;
DROP TABLE IF EXISTS lake.blind.fact_person;
CREATE TABLE lake.blind.fact_person AS
SELECT
    HOUSEID AS houseid,
    PERSONID AS personid,
    R_AGE AS r_age,
    WTPERFIN AS wtperfin
FROM lake.nhts2017.perpub;
