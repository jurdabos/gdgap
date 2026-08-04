-- R1, R3, R8: Type-2-style person dimension, InnoDB foil — distinct sex and gender-identity attributes
-- (R1), sex_source provenance (R3), and validity intervals (R8) in row-oriented storage with the
-- versioned grain enforced by the primary key; data copied from the lake ('NC' throughout for gender).
CREATE DATABASE IF NOT EXISTS gdgap_aware;
DROP TABLE IF EXISTS gdgap_aware.dim_person_sex;
CREATE TABLE gdgap_aware.dim_person_sex (
    houseid BIGINT NOT NULL,
    personid VARCHAR(4) NOT NULL,
    sex_code VARCHAR(4) NOT NULL,
    sex_code_reported VARCHAR(4) NOT NULL,
    sex_source VARCHAR(16) NOT NULL,
    gender_identity_code VARCHAR(4) NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE NULL,
    is_current BOOLEAN NOT NULL,
    PRIMARY KEY (houseid, personid, valid_from)
) ENGINE=InnoDB;
