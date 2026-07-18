# nhts2017 profile summary (case description ground truth)

Generated 2026-07-18 17:21 UTC by `gdgap summarize` — a formatting pass over `results/profile/nhts2017/*.csv`.
Regenerate with `gdgap ingest nhts2017 && gdgap profile && gdgap summarize`. Source: own results.

## Structure and null shares

| file    |    rows |   columns | column types                      |   columns with nulls |   null cells | null cell share   |
|---------|---------|-----------|-----------------------------------|----------------------|--------------|-------------------|
| hhpub   | 129,696 |        58 | 41 VARCHAR · 16 BIGINT · 1 DOUBLE |                    0 |            0 | 0.0000%           |
| perpub  | 264,234 |       121 | 81 VARCHAR · 36 BIGINT · 4 DOUBLE |                    0 |            0 | 0.0000%           |
| trippub | 923,572 |       115 | 78 VARCHAR · 32 BIGINT · 5 DOUBLE |                    0 |            0 | 0.0000%           |
| vehpub  | 256,115 |        60 | 36 VARCHAR · 19 BIGINT · 5 DOUBLE |                    0 |            0 | 0.0000%           |

## Code lists for the sex variable and its imputed companion (`R_SEX`, `R_SEX_IMP`)

| variable   |   code | codebook label         |       n | share    |
|------------|--------|------------------------|---------|----------|
| R_SEX      |     -7 | I prefer not to answer |     209 | 0.0791%  |
| R_SEX      |     -8 | I don't know           |      34 | 0.0129%  |
| R_SEX      |     01 | Male                   | 124,687 | 47.1881% |
| R_SEX      |     02 | Female                 | 139,304 | 52.7199% |
| R_SEX_IMP  |     01 | Male                   | 124,805 | 47.2328% |
| R_SEX_IMP  |     02 | Female                 | 139,429 | 52.7672% |

## Sex imputation share (perpub)

|   rows total |   rows imputed | imputed share   |
|--------------|----------------|-----------------|
|      264,234 |            277 | 0.1048%         |

Imputed means the value in `R_SEX_IMP` differs from the reported `R_SEX` (reserve codes -7/-8 resolved, plus consistency edits).
