-- R7, R11: blind baseline, InnoDB foil — trip facts with raw reserve codes preserved verbatim (R7);
-- no sex join path exists in this variant by design (R11).
CREATE DATABASE IF NOT EXISTS gdgap_blind;
DROP TABLE IF EXISTS gdgap_blind.fact_trip;
CREATE TABLE gdgap_blind.fact_trip (
    houseid BIGINT NOT NULL,
    personid VARCHAR(4) NOT NULL,
    tdtrpnum VARCHAR(4) NOT NULL,
    trptrans VARCHAR(4),
    whyto VARCHAR(4),
    whyfrom VARCHAR(4),
    trippurp VARCHAR(8),
    trpmiles DOUBLE,
    wttrdfin DOUBLE,
    PRIMARY KEY (houseid, personid, tdtrpnum)
) ENGINE=InnoDB;
