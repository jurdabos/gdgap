-- R1, R6: ISO/IEC 5218:2022 sex code list, InnoDB foil — structure only; the standard core plus the
-- 'U' application extension are copied from the built lake variant; gender identity has its own domain (R1).
CREATE DATABASE IF NOT EXISTS gdgap_aware;
DROP TABLE IF EXISTS gdgap_aware.dim_sex_code;
CREATE TABLE gdgap_aware.dim_sex_code (
    sex_code VARCHAR(4) NOT NULL,
    label VARCHAR(80) NOT NULL,
    source_standard VARCHAR(64) NOT NULL,
    is_extension BOOLEAN NOT NULL,
    PRIMARY KEY (sex_code)
) ENGINE=InnoDB;
