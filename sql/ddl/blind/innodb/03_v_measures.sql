-- R11: blind derived measure, InnoDB foil — the care-trip share is computable only as a population
-- total; disaggregation by sex is impossible by construction, the measured contrast for R2.
CREATE DATABASE IF NOT EXISTS gdgap_blind;
DROP VIEW IF EXISTS gdgap_blind.v_care_trip_share;
CREATE VIEW gdgap_blind.v_care_trip_share AS
SELECT
    sum(CASE WHEN whyto = '06' OR whyfrom = '06' THEN wttrdfin ELSE 0 END) AS care_trip_weight,
    sum(wttrdfin) AS all_trip_weight,
    sum(CASE WHEN whyto = '06' OR whyfrom = '06' THEN wttrdfin ELSE 0 END) / sum(wttrdfin) AS care_trip_share
FROM gdgap_blind.fact_trip;
