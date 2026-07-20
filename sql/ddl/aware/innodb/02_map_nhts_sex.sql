-- R7: NHTS raw-code mapping, InnoDB foil — every reserve code keeps its explicit row; structure
-- only, data copied from the built lake variant by the build.
CREATE DATABASE IF NOT EXISTS gdgap_aware;
DROP TABLE IF EXISTS gdgap_aware.map_nhts_sex;
CREATE TABLE gdgap_aware.map_nhts_sex (
    nhts_code VARCHAR(4) NOT NULL,
    sex_code VARCHAR(4) NOT NULL,
    note VARCHAR(80) NOT NULL,
    PRIMARY KEY (nhts_code)
) ENGINE=InnoDB;
