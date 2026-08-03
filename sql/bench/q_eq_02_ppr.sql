-- R2, R9, R11: equity benchmark query (Q_eq) — participation representation ratio by sex from the
-- deployed aware view (suppression n >= 30 inside the view, R9). Not representable on the blind
-- schema: recorded as a capability state, never executed there.
SELECT
    sex_code,
    care_share,
    population_share,
    ppr,
    persons_n,
    care_trips_n
FROM {schema}.v_ppr
ORDER BY sex_code;
