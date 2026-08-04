-- R1, R6: gender identity code domain, InnoDB foil — structure only; separately governed from the
-- ISO sex codes (R1), rows copied from the built lake variant by the build.
CREATE DATABASE IF NOT EXISTS gdgap_aware;
DROP TABLE IF EXISTS gdgap_aware.dim_gender_identity_code;
CREATE TABLE gdgap_aware.dim_gender_identity_code (
    gender_identity_code VARCHAR(4) NOT NULL,
    label VARCHAR(80) NOT NULL,
    source_standard VARCHAR(64) NOT NULL,
    is_extension BOOLEAN NOT NULL,
    PRIMARY KEY (gender_identity_code)
) ENGINE=InnoDB;
