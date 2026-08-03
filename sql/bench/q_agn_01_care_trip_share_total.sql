-- R11: agnostic benchmark query (Q_agn) — population-total care-trip share straight from the
-- fact grain; touches no sex attribute or join path, so blind and aware must return equivalent
-- values on the same engine (ADR-0004 hash check).
-- Care trip definition: WHYTO/WHYFROM code '06' = drop off / pick up someone (2017 NHTS codebook).
SELECT
    sum(CASE WHEN whyto = '06' OR whyfrom = '06' THEN wttrdfin ELSE 0 END) AS care_trip_weight,
    sum(wttrdfin) AS all_trip_weight,
    sum(CASE WHEN whyto = '06' OR whyfrom = '06' THEN wttrdfin ELSE 0 END) / sum(wttrdfin) AS care_trip_share
FROM {schema}.fact_trip;
