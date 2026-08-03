-- R7, R11: agnostic benchmark query (Q_agn) — weighted mode share over all trips, grouped by the
-- raw TRPTRANS code so reserve codes stay first-class rows (R7); no sex involvement anywhere.
SELECT
    trptrans,
    count(*) AS trips_n,
    sum(wttrdfin) AS mode_weight,
    sum(wttrdfin) / sum(sum(wttrdfin)) OVER () AS mode_share
FROM {schema}.fact_trip
GROUP BY trptrans
ORDER BY trptrans;
