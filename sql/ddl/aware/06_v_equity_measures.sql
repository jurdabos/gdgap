-- R2, R3, R9, R11: derived equity measures — imputation-share visibility (R3), care-trip share by
-- sex and the PPR representation ratio as derived measures (R2), small-cell suppression at n >= 30
-- (R9), and benefit/cost numbers flowing from the same views for symmetric reporting (R11).
-- Care trip definition: WHYTO/WHYFROM code '06' = drop off / pick up someone (2017 NHTS codebook).
CREATE SCHEMA IF NOT EXISTS lake.aware;
DROP VIEW IF EXISTS lake.aware.v_sex_imputation_share;
CREATE VIEW lake.aware.v_sex_imputation_share AS
SELECT
    sex_source,
    count(*) AS persons,
    count(*) * 100.0 / sum(count(*)) OVER () AS share_pct
FROM lake.aware.dim_person_sex
WHERE is_current
GROUP BY sex_source;

DROP VIEW IF EXISTS lake.aware.v_care_trip_share_by_sex;
CREATE VIEW lake.aware.v_care_trip_share_by_sex AS
SELECT
    d.sex_code,
    count(*) AS trips_n,
    sum(CASE WHEN f.whyto = '06' OR f.whyfrom = '06' THEN f.wttrdfin ELSE 0 END) AS care_trip_weight,
    sum(f.wttrdfin) AS all_trip_weight,
    sum(CASE WHEN f.whyto = '06' OR f.whyfrom = '06' THEN f.wttrdfin ELSE 0 END) / sum(f.wttrdfin) AS care_trip_share
FROM lake.aware.fact_trip AS f
JOIN lake.aware.dim_person_sex AS d
    ON d.houseid = f.houseid AND d.personid = f.personid AND d.is_current
GROUP BY d.sex_code
HAVING count(*) >= 30;

DROP VIEW IF EXISTS lake.aware.v_ppr;
CREATE VIEW lake.aware.v_ppr AS
WITH care AS (
    SELECT
        d.sex_code,
        sum(f.wttrdfin) AS care_weight,
        count(*) AS care_n
    FROM lake.aware.fact_trip AS f
    JOIN lake.aware.dim_person_sex AS d
        ON d.houseid = f.houseid AND d.personid = f.personid AND d.is_current
    WHERE f.whyto = '06' OR f.whyfrom = '06'
    GROUP BY d.sex_code
),
population AS (
    SELECT
        d.sex_code,
        sum(p.wtperfin) AS person_weight,
        count(*) AS person_n
    FROM lake.aware.fact_person AS p
    JOIN lake.aware.dim_person_sex AS d
        ON d.houseid = p.houseid AND d.personid = p.personid AND d.is_current
    GROUP BY d.sex_code
)
SELECT
    population.sex_code,
    care.care_weight / sum(care.care_weight) OVER () AS care_share,
    population.person_weight / sum(population.person_weight) OVER () AS population_share,
    (care.care_weight / sum(care.care_weight) OVER ())
        / (population.person_weight / sum(population.person_weight) OVER ()) AS ppr,
    population.person_n AS persons_n,
    care.care_n AS care_trips_n
FROM population
JOIN care ON care.sex_code = population.sex_code
WHERE population.person_n >= 30 AND care.care_n >= 30;
