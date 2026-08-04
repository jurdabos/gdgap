-- R2: person-grain facts join the sex dimension on (houseid, personid), keeping every person
-- measure disaggregable by sex without schema change.
CREATE SCHEMA IF NOT EXISTS lake.aware;
DROP TABLE IF EXISTS lake.aware.fact_person;
CREATE TABLE lake.aware.fact_person AS
SELECT
    HOUSEID AS houseid,
    PERSONID AS personid,
    R_AGE AS r_age,
    WTPERFIN AS wtperfin
FROM lake.nhts2017.perpub;
