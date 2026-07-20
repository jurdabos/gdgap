-- R2, R7: trip-grain facts with raw purpose/mode reserve codes preserved verbatim (R7);
-- disaggregation by sex arrives via the dimension join, not via a copied column (R2).
CREATE SCHEMA IF NOT EXISTS lake.aware;
DROP TABLE IF EXISTS lake.aware.fact_trip;
CREATE TABLE lake.aware.fact_trip AS
SELECT
    HOUSEID AS houseid,
    PERSONID AS personid,
    TDTRPNUM AS tdtrpnum,
    TRPTRANS AS trptrans,
    WHYTO AS whyto,
    WHYFROM AS whyfrom,
    TRIPPURP AS trippurp,
    TRPMILES AS trpmiles,
    WTTRDFIN AS wttrdfin
FROM lake.nhts2017.trippub;
