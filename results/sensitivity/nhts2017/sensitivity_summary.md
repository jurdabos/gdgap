# nhts2017 imputation sensitivity audit

Generated 2026-08-06 13:35 UTC by `gdgap audit-imputation` — regenerate with `gdgap build --variant aware && gdgap audit-imputation`. Source: own results.

Westat completed missing sex values by random hot-deck imputation within adjustment cells (2017 NHTS Weighting Report, Appendix D). Donor assignments are not published, so individual imputations cannot be reconstructed or validated: this is an imputation sensitivity audit, not a bias detector. Published weights were raked with the completed sex, so scenario estimates are sensitivity scenarios under the published weights — never re-raked estimators.

## Scenarios (frozen definitions)

- `all_completed` — baseline: every current person, grouped by the completed code (reproduces the v_care_trip_share_by_sex / v_ppr semantics).
- `observed_only` — rows with `sex_source = 'imputed'` excluded; edited rows keep the completed code.
- `reported_values` — imputed rows excluded; edited rows grouped by `sex_code_reported`.

## Provenance split

| sex_source   |   persons_n |   persons_pct |   trips_n |   trips_pct |   trip_weight_pct |
|--------------|-------------|---------------|-----------|-------------|-------------------|
| edited       |          34 |        0.0129 |        56 |      0.0061 |            0.0105 |
| imputed      |         243 |        0.092  |       711 |      0.077  |            0.1092 |
| reported     |      263957 |       99.8952 |    922805 |     99.917  |           99.8803 |

## Non-reported rates by completed code and age band

Numerators below n = 30 are flagged unstable — statistical instability, not exposure; equity cells below n = 30 stay suppressed per R9.

| dimension          | category   |   persons_n |   imputed_n |   imputed_rate_pct | imputed_unstable   |   edited_n |   edited_rate_pct |
|--------------------|------------|-------------|-------------|--------------------|--------------------|------------|-------------------|
| completed_sex_code | 1          |      124805 |         118 |             0.0945 | False              |         17 |            0.0136 |
| completed_sex_code | 2          |      139429 |         125 |             0.0897 | False              |         17 |            0.0122 |
| completed_sex_code | TOTAL      |      264234 |         243 |             0.092  | False              |         34 |            0.0129 |
| age_band           | 0-17       |       33146 |          46 |             0.1388 | False              |         17 |            0.0513 |
| age_band           | 18-39      |       55824 |          49 |             0.0878 | False              |          4 |            0.0072 |
| age_band           | 40-64      |      101342 |          54 |             0.0533 | False              |         13 |            0.0128 |
| age_band           | 65plus     |       73426 |          17 |             0.0232 | True               |          0 |            0      |
| age_band           | reserve    |         496 |          77 |            15.5242 | False              |          0 |            0      |
| age_band           | TOTAL      |      264234 |         243 |             0.092  | False              |         34 |            0.0129 |

## Equity measures by scenario

| measure         | scenario        |   sex_code |   trips_n |   persons_n |    value |   delta_vs_all_completed |
|-----------------|-----------------|------------|-----------|-------------|----------|--------------------------|
| care_trip_share | all_completed   |          1 |    432834 |             | 0.102712 |                          |
| care_trip_share | all_completed   |          2 |    490738 |             | 0.148887 |                          |
| care_trip_share | observed_only   |          1 |    432466 |             | 0.102638 |                -7.4e-05  |
| care_trip_share | observed_only   |          2 |    490395 |             | 0.148936 |                 4.9e-05  |
| care_trip_share | reported_values |          1 |    432478 |             | 0.102628 |                -8.4e-05  |
| care_trip_share | reported_values |          2 |    490383 |             | 0.148947 |                 6e-05    |
| ppr             | all_completed   |          1 |     40661 |      124805 | 0.797477 |                          |
| ppr             | all_completed   |          2 |     64812 |      139429 | 1.19524  |                          |
| ppr             | observed_only   |          1 |     40635 |      124687 | 0.796857 |                -0.00062  |
| ppr             | observed_only   |          2 |     64774 |      139304 | 1.19575  |                 0.000504 |
| ppr             | reported_values |          1 |     40633 |      124687 | 0.796818 |                -0.00066  |
| ppr             | reported_values |          2 |     64776 |      139304 | 1.19578  |                 0.000537 |

## Scenario coverage (influence bounds)

| scenario        |   persons_excluded_n |   person_weight_excluded_pct |   trips_excluded_n |   trip_weight_excluded_pct |   persons_reclassified_n |
|-----------------|----------------------|------------------------------|--------------------|----------------------------|--------------------------|
| observed_only   |                  243 |                       0.1198 |                711 |                     0.1092 |                        0 |
| reported_values |                  243 |                       0.1198 |                711 |                     0.1092 |                       34 |

Share-type scenario deltas are bounded above by the excluded trip-weight share.
