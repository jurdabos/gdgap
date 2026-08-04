-- R7: every NHTS raw sex code — including the reserve codes — maps to an explicit code-list row;
-- nothing is coerced to NULL, and refusal (-7) stays distinguishable from ignorance (-8/-9).
CREATE SCHEMA IF NOT EXISTS lake.aware;
DROP TABLE IF EXISTS lake.aware.map_nhts_sex;
CREATE TABLE lake.aware.map_nhts_sex AS
SELECT * FROM (
    VALUES
        ('01', '1', 'reported male'),
        ('02', '2', 'reported female'),
        ('-7', 'U', 'I prefer not to answer - refusal preserved as undisclosed'),
        ('-8', '0', 'I do not know - not known'),
        ('-9', '0', 'Not ascertained - not known')
) AS t(nhts_code, sex_code, note);
