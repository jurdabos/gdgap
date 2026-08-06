# Datasheet: 2017 National Household Travel Survey (NHTS), public-use files

Datasheet after Gebru et al., "Datasheets for Datasets" (CACM 64(12), 2021; the seven question sections are instantiated below and answered for the 2017 NHTS from the FHWA documentation).

Primary sources: 2017 NHTS Data User Guide (Westat for FHWA, March 2018, revised April 2019; https://nhts.ornl.gov/assets/2017UsersGuide.pdf), Codebook v1.2 (https://nhts.ornl.gov/assets/codebook_v1.2.pdf), 2017 NHTS Weighting Report (Westat; https://nhts.ornl.gov/assets/2017%20NHTS%20Weighting%20Report.pdf), Sample Design Plan (Task C deliverable, Westat, 2015; https://nhts.ornl.gov/assets/Task_C_Sample_Design_20151231.pdf), and https://nhts.ornl.gov. Local acquisition facts come from `manifest.json` and `checksums.txt` in this directory. We are dataset consumers, not creators; answers describe the upstream dataset, with repo-specific notes marked "Local".

## Motivation

- **For what purpose was the dataset created?** To provide the authoritative national inventory of daily travel by the civilian, non-institutionalized population of the United States: trip rates, person/vehicle miles of travel, mode, purpose, and temporal patterns, linked to household demographics. It supports federal reporting to Congress, state/MPO travel demand modeling, and research in safety, public health, energy, and environment. The 2017 NHTS is the eighth survey in a series (NPTS 1969, 1977, 1983, 1990, 1995; NHTS 2001, 2009, 2017), designed to track how US travel behavior changes over time.
- **Who created the dataset and on behalf of which entity?** The Federal Highway Administration (FHWA), US Department of Transportation. Data collection, editing, and weighting were performed by Westat under contract to FHWA.
- **Who funded the creation of the dataset?** FHWA, with add-on partners (state DOTs and regional/metropolitan planning organizations) purchasing additional samples in their areas. OMB cleared the survey in November 2015 under clearance number 2125-0545.
- **Any other comments?** None.

## Composition

- **What do the instances represent?** Four linked instance types: households, persons, household vehicles, and travel-day trips. Each trip row is one segment of travel by one person on the household's assigned travel day.
- **How many instances are there in total?** Public-use v1.2 counts, verified against our local copies:
  - `hhpub.csv` — 129,696 households, 58 variables
  - `perpub.csv` — 264,234 persons, 121 variables
  - `vehpub.csv` — 256,115 vehicles, 60 variables
  - `trippub.csv` — 923,572 trips, 115 variables
  Weighted, the household file represents 118,208,251 US households.
- **Does the dataset contain all possible instances or is it a sample?** A sample. The target population is the civilian, non-institutionalized population of the United States (50 states and DC) living in residential housing units with at least one adult; people in medical institutions, prisons, military barracks, dormitories, and fraternity/sorority houses are excluded (User Guide ch. 2). The sample is a stratified address-based probability sample — stratified by state, with the 13 add-on samples embedded in one unified selection and oversampled — drawn from a monthly-updated, vendor-enhanced frame originating in the USPS Computerized Delivery Sequence file (Sample Design Plan §§1–2). National representativeness is achieved through the supplied weights, not the raw counts. Local: the gdgap warehouse variants and the q_agn/q_eq query catalogue are query-time restrictions of the full weighted person/trip files under the published weights — a derived analysis subset, never a re-sample or a re-weighting (`results/sensitivity/nhts2017/sensitivity_summary.md` records the no-re-raking caveat).
- **What does each instance consist of?** Edited categorical and numeric survey responses plus derived variables (e.g. urbanicity `HBHUR`, block-group density categories, trip purpose aggregates). No free text, no raw geographies below coarsened categories.
- **Is there a label or target associated with each instance?** No; this is a general-purpose survey dataset, not a labeled ML corpus.
- **Is any information missing from individual instances?** Yes, item nonresponse is encoded with special codes: `-9` not ascertained, `-8` don't know, `-7` prefer not to answer, `-1` appropriate skip. Some variables exist only for eligible subsets (e.g. workers, drivers).
- **Are relationships between individual instances made explicit?** Yes: `HOUSEID` links all files; `HOUSEID`+`PERSONID` links persons to trips; `HOUSEID`+`VEHID` links vehicles to trips. Merge patterns are documented in User Guide ch. 7.15–7.16.
- **Are there recommended data splits?** No. Analyses use the full files with final weights (`WTHHFIN`, `WTPERFIN`, `WTTRDFIN`) and 98 jackknife replicate weights for variance estimation.
- **Are there any errors, sources of noise, or redundancies?** Self-reported travel is subject to trip underreporting and rounding of times/distances; nonresponse bias is addressed via weighting; several variables are repeated across files for convenience (User Guide table 6-4). Methodological changes vs. 2009 (recruitment mode, distance derivation, purpose/mode recodes) affect trend comparability (ch. 3).
- **Is the dataset self-contained, or does it rely on external resources?** Self-contained CSVs; documentation (codebook, user guide) is external at https://nhts.ornl.gov.
- **Does the dataset contain confidential data?** No. The public-use files are de-identified: no names, addresses, or coordinates; geography is limited to state, census division/region, and categorical block-group densities.
- **Might any data be offensive or cause anxiety?** No; content is travel behavior and demographics.
- **Does the dataset identify subpopulations?** Yes, by design: age, sex, race, ethnicity, household income (`HHFAMINC`, 11 bands), worker/driver status, medical conditions affecting travel, etc.
- **Is it possible to identify individuals?** Not intended to be: FHWA applies disclosure avoidance (suppression/coarsening of geography and extreme values) before release. Residual re-identification risk in combination with external data is the standard, low, public-use-file risk.
- **Does the dataset contain sensitive data?** Categorical race/ethnicity, income, and a travel-relevant medical-condition indicator are present; no religion, politics, biometrics, or precise locations.
- **Any other comments?** None.

## Collection

- **How was the data acquired?** Directly reported by household members: a recruitment survey followed by a retrieval survey covering a pre-assigned 24-hour travel day, supported by a mailed travel log. Proxy responses were allowed for children and unavailable members. Data were validated through in-instrument checks and post-hoc editing (ch. 2.9).
- **What mechanisms or procedures were used?** Mail-out recruitment with web and CATI (computer-assisted telephone interviewing) response modes; retrieval by web or telephone; Spanish-language option. Instruments were pretested, and cognitive/usability tests were conducted under the OMB clearance.
- **What was the sampling strategy?** A stratified address-based probability sample — not convenience, snowball, or volunteer-panel recruitment. The frame is a monthly-updated, vendor-enhanced list built on the USPS Computerized Delivery Sequence file; stratification is by state, with the 13 add-on partners' oversamples embedded in a single unified selection; travel days are assigned across all days of a full year, including holidays, to capture seasonality (Sample Design Plan §2). Participation is voluntary, as in any household survey; unit nonresponse is compensated by the nonresponse adjustments and raking to ACS control totals (Weighting Report ch. 3–4).
- **Who was involved in collection and how were they compensated?** Westat professional field/CATI staff. Respondent participation was voluntary — which does not make this volunteer sampling; recruitment stayed probability-based — with a $2 cash pre-incentive in the recruitment mailing (User Guide ch. 2.2) and further incentives documented in the survey materials rather than the public files.
- **Over what timeframe was the data collected?** April 2016 through May 2017; each record refers to the household's assigned travel day within that window.
- **Were any ethical review processes conducted?** Federal survey review under the Paperwork Reduction Act: OMB clearance 2125-0545, covering burden, necessity, sensitivity, and methodology.
- **Was the data collected directly from the individuals?** Yes, with proxy interviews as noted; participation was voluntary, with confidentiality assurances given at recruitment (notification and consent are inherent to the interview process; no ongoing revocation mechanism applies to the anonymized public files).
- **Any other comments?** Weighting compensates for unit nonresponse using ACS control totals (2015 1-year and 2011–2015 5-year); response-rate details are in User Guide ch. 4, the full procedure in the Weighting Report.

## Preprocessing

- **Was any preprocessing/cleaning/labeling done?** Yes: consistency editing, coding of open responses (e.g. occupation, vehicle make/model), derivation of variables (trip purpose hierarchies, urbanicity, density categories), disclosure-avoidance coarsening, and computation of final and replicate weights — including item imputation of the raking variables by random hot deck within imputation cells (each record needing a value, a "beggar", is randomly assigned a "donor" with the item nonmissing; Weighting Report App. D). The completed sex value `R_SEX_IMP` arises there; donor assignments are not published. Local: the aware build keeps reported-vs-completed provenance first-class (`sex_source`, `sex_code_reported`, `r_sex_raw`), and `gdgap audit-imputation` quantifies the completions' influence on the equity measures under frozen scenarios (`results/sensitivity/nhts2017/`).
- **Was the raw data saved in addition to the preprocessed data?** The unedited microdata are retained by FHWA/Westat and are not public; only the edited, de-identified public-use files are released.
- **Is the preprocessing software available?** No. Procedures are described in the User Guide, but the editing/weighting code is not published.
- **Any other comments?** Local: we store the four CSVs read-only under `data/raw/nhts2017/` and do all typing/coercion downstream in DuckDB, so upstream bytes stay pristine.

## Uses

- **Has the dataset been used for any tasks already?** Extensively: FHWA's Summary of Travel Trends, federal performance reporting, state/MPO travel demand model estimation and calibration, and research in public health, energy, and safety.
- **Is there a repository of papers/systems using the dataset?** Yes, FHWA maintains a compendium of NHTS-based publications at https://nhts.ornl.gov.
- **What (other) tasks could the dataset be used for?** Local: in gdgap, benchmark workloads over a DuckDB/DuckLake instance — schema-blind vs. schema-aware DDL (`sql/ddl/blind`, `sql/ddl/aware`), profiling and query-plan comparisons recorded under `results/`.
- **Is there anything that might impact future uses?** Weights are mandatory for population statements; special codes must be handled before numeric aggregation (they are valid category labels, not NULLs); 2017 methodology changes break naive trend comparisons with earlier survey waves.
- **Are there tasks for which the dataset should not be used?** Sub-state or small-area estimation outside add-on areas; longitudinal/panel inference (households are not followed over time); any attempt at re-identification.
- **Any other comments?** None.

## Distribution

- **Will/how is the dataset distributed?** Public download from https://nhts.ornl.gov (our copy: `https://nhts.ornl.gov/media/2016/download/csv.zip`, retrieved 2026-07 per `manifest.json`). No DOI is assigned.
- **Under what license/terms of use?** A public US DOT dataset (US federal government work); attribution to FHWA/NHTS is expected. Local: per repo policy the data plane is gitignored and the CSVs are not redistributed through this repository; integrity is pinned by SHA-256 in `checksums.txt` and `manifest.json`.
- **Have third parties imposed IP or other restrictions? Export controls?** None known.
- **Any other comments?** None.

## Maintenance

- **Who supports/hosts/maintains the dataset?** FHWA, with the data portal hosted by Oak Ridge National Laboratory (ORNL).
- **How can the owner be contacted?** Via the contact channels on https://nhts.ornl.gov (FHWA Office of Policy Information).
- **Is there an erratum? Will the dataset be updated?** Versioned releases with release notes; v1.2 (2019) is current for 2017 and is what we hold. Subsequent survey waves (e.g. 2022 NHTS) are published as separate datasets, not updates to 2017.
- **Are there retention limits?** Not applicable to the anonymized public files.
- **Will older versions continue to be supported?** Prior survey waves (1969–2009) and their documentation remain available on the portal.
- **Is there a mechanism to extend/build on the dataset?** No formal contribution mechanism; derived work happens downstream (here: DuckLake tables built from the raw CSVs, reproducible from `sql/` DDL).
- **Any other comments?** Local re-verification: `sha256sum -c datasets/nhts2017/checksums.txt` from the repo root.
