-- R11: blind derived measure — the care-trip share is computable only as a population total here;
-- disaggregation by sex is impossible by construction, which is the measured contrast for R2.
-- Care trip definition: WHYTO/WHYFROM code '06' = drop off / pick up someone (2017 NHTS codebook).
CREATE SCHEMA IF NOT EXISTS lake.blind;
DROP VIEW IF EXISTS lake.blind.v_care_trip_share;
CREATE VIEW lake.blind.v_care_trip_share AS
SELECT
    sum(CASE WHEN whyto = '06' OR whyfrom = '06' THEN wttrdfin ELSE 0 END) AS care_trip_weight,
    sum(wttrdfin) AS all_trip_weight,
    sum(CASE WHEN whyto = '06' OR whyfrom = '06' THEN wttrdfin ELSE 0 END) / sum(wttrdfin) AS care_trip_share
FROM lake.blind.fact_trip;
