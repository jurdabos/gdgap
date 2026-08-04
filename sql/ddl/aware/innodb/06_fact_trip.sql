-- R2, R7: trip-grain facts, InnoDB foil — raw reserve codes preserved verbatim (R7), sex arrives
-- via the dimension join (R2); structure only, data copied from the built lake variant by the build.
CREATE DATABASE IF NOT EXISTS gdgap_aware;
DROP TABLE IF EXISTS gdgap_aware.fact_trip;
CREATE TABLE gdgap_aware.fact_trip (
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
