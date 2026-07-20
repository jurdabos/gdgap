-- R7, R11: blind baseline — trip-grain facts from the identical Parquet source, raw purpose/mode
-- reserve codes preserved verbatim (R7); no sex join path exists in this variant by design (R11).
CREATE SCHEMA IF NOT EXISTS lake.blind;
DROP TABLE IF EXISTS lake.blind.fact_trip;
CREATE TABLE lake.blind.fact_trip AS
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
