-- R2, R9, R11: equity benchmark query (Q_eq) — care-trip share disaggregated by sex through the
-- deployed aware view, so small-cell suppression (n >= 30, R9) stays inside the measured schema.
-- Not representable on the blind schema: recorded as a capability state, never executed there.
SELECT
    sex_code,
    trips_n,
    care_trip_weight,
    all_trip_weight,
    care_trip_share
FROM {schema}.v_care_trip_share_by_sex
ORDER BY sex_code;
