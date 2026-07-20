-- R2: person-grain facts, InnoDB foil — join the sex dimension on (houseid, personid); structure
-- only, data copied from the built lake variant by the build.
CREATE DATABASE IF NOT EXISTS gdgap_aware;
DROP TABLE IF EXISTS gdgap_aware.fact_person;
CREATE TABLE gdgap_aware.fact_person (
    houseid BIGINT NOT NULL,
    personid VARCHAR(4) NOT NULL,
    r_age BIGINT,
    wtperfin DOUBLE,
    PRIMARY KEY (houseid, personid)
) ENGINE=InnoDB;
