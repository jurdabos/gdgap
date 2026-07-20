-- R2, R11: blind baseline, InnoDB foil — same person facts as the lake variant in row-oriented
-- storage with an explicit primary key; data is copied from the built lake variant by the build.
CREATE DATABASE IF NOT EXISTS gdgap_blind;
DROP TABLE IF EXISTS gdgap_blind.fact_person;
CREATE TABLE gdgap_blind.fact_person (
    houseid BIGINT NOT NULL,
    personid VARCHAR(4) NOT NULL,
    r_age BIGINT,
    wtperfin DOUBLE,
    PRIMARY KEY (houseid, personid)
) ENGINE=InnoDB;
