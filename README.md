# ERCOT Winter Storm Outage Risk

This repository builds an ERCOT-focused utility analysis on winter storm outage risk and financial exposure. The project combines official EIA utility schedules, NOAA storm and weather data, and an Aon climate report to create a reproducible first-pass research workflow.

The project is motivated by Winter Storm Uri and the broader question of whether ERCOT utilities face measurable outage and financial exposure from severe winter conditions. The current version is designed as a solid analytical baseline: it collects the core datasets, aligns them at the utility-year level, and produces a first set of tables, figures, and scenario outputs that can be extended in future work.

## Research question

How much can winter storm conditions in ERCOT help explain utility outages, and what do those outages imply for delivery-rate pressure and lost revenue risk?

Related sub-questions in the repo are:

- Which ERCOT utility territories have experienced the largest winter-season storm exposure since 2000?
- How do outage metrics vary across ERCOT utilities over time?
- How much delivery revenue is potentially exposed when outage duration rises?
- What would a URI-like winter severity profile imply for recent utility conditions?

## Scope

- Geography: ERCOT transmission and distribution utilities in Texas.
- Utility unit: service territories for the main ERCOT delivery utilities.
- Historical winter storm exposure: 2000-2025.
- Utility outage metrics: 2013-2024, based on EIA-861 reliability files.
- Delivery revenue and rate metrics: 2020-2024, based on EIA-861 delivery company files.

The utility focus is the core ERCOT delivery footprint represented in the EIA files:

- AEP Texas Central Company
- AEP Texas North Company
- CenterPoint Energy
- Nueces Electric Cooperative
- Oncor Electric Delivery Company LLC
- Texas-New Mexico Power Co

## Data sources

- EIA Form 861 detailed data files:
  - Reliability, for annual interruption metrics such as SAIDI and SAIFI
  - Service Territory, for county-to-utility territory mapping
  - Delivery Companies, for delivery revenue, sales, and customer counts
- NOAA Storm Events Database
  - Used to capture winter-season county storm exposure and reported damages
- NOAA GHCN Daily station data
  - Used to build annual weather severity features such as freeze days and minimum temperature
- Aon 2025 Climate and Catastrophe Insight report
  - Used as background context on catastrophe and climate risk rather than as a modeling dataset

All project-scoped raw extracts are saved under [data/raw](data/raw), with merged outputs under [data/processed](data/processed).

## Repository layout

- [scripts/download_data.py](scripts/download_data.py): downloads and filters the official datasets into ERCOT-scoped raw CSVs.
- [scripts/build_analysis.py](scripts/build_analysis.py): creates the merged utility panel, figures, and summary artifacts.
- [docs/analysis_summary.md](docs/analysis_summary.md): concise write-up of the current findings.
- [data/raw](data/raw): project-scoped intermediate extracts from the official sources.
- [data/processed](data/processed): cleaned analytical tables used by the figures and summary.
- [outputs/figures](outputs/figures): generated plots.

## Method

The current workflow follows four broad steps:

1. Build ERCOT utility geography.
   The repo uses EIA service territory data to map ERCOT delivery utilities to Texas counties.

2. Build storm and weather exposure measures.
   NOAA Storm Events provides county-level winter-season events and reported damages, while NOAA daily weather files provide annual severity features such as freeze days, sub-20F days, snowfall days, and minimum temperature for representative utility stations.

3. Join utility performance and revenue data.
   EIA reliability schedules provide annual outage metrics, and EIA delivery company schedules provide delivery revenue, megawatt-hours, and customer counts.

4. Produce explanatory outputs.
   The analysis creates a utility-year panel, fits a simple linear outage model, estimates lost revenue exposure from outage duration, and simulates a URI-like scenario using a recent baseline year.

This is intentionally a pragmatic first pass. It emphasizes reproducibility and useful structure over perfect causal identification.

## How to run

From the repo root:

```bash
python3 scripts/download_data.py
python3 scripts/build_analysis.py
```

What each command does:

- `python3 scripts/download_data.py`
  - Downloads the official source files
  - Filters them to the ERCOT/Texas project scope
  - Saves project-scoped raw files to [data/raw](data/raw)

- `python3 scripts/build_analysis.py`
  - Reads the raw extracts
  - Builds the utility-year analytical panel
  - Creates figures and scenario tables
  - Writes the summary to [docs/analysis_summary.md](docs/analysis_summary.md)

If you already have the raw data and only want to rebuild figures and outputs, you can run only:

```bash
python3 scripts/build_analysis.py
```

## What to look at first

If you are opening the repo for the first time, start here:

- [docs/analysis_summary.md](docs/analysis_summary.md) for the quick narrative version
- [data/processed/ercot_utility_winter_risk_panel.csv](data/processed/ercot_utility_winter_risk_panel.csv) for the main merged analytical dataset
- [outputs/figures/ercot_utility_saidi_timeseries.png](outputs/figures/ercot_utility_saidi_timeseries.png) for utility outage trends
- [outputs/figures/ercot_county_winter_storm_choropleth.png](outputs/figures/ercot_county_winter_storm_choropleth.png) for the geographic storm exposure view

## Current outputs

- [ercot_utility_winter_risk_panel.csv](data/processed/ercot_utility_winter_risk_panel.csv)
  - Main utility-year panel combining outage, storm, weather, and revenue variables
- [ercot_outage_model_predictions.csv](data/processed/ercot_outage_model_predictions.csv)
  - In-sample predictions from the exploratory linear outage model
- [ercot_uri_like_scenario_2024.csv](data/processed/ercot_uri_like_scenario_2024.csv)
  - Scenario table estimating recent lost-revenue exposure under URI-like winter conditions
- [analysis_summary.md](docs/analysis_summary.md)
  - Human-readable summary of findings and caveats
- [ercot_county_winter_storm_choropleth.png](outputs/figures/ercot_county_winter_storm_choropleth.png)
  - County-level map of winter-season storm event counts
- [ercot_utility_saidi_timeseries.png](outputs/figures/ercot_utility_saidi_timeseries.png)
  - Utility outage trends over time
- [ercot_delivery_rate_timeseries.png](outputs/figures/ercot_delivery_rate_timeseries.png)
  - Delivery revenue per MWh over time
- [ercot_outage_model_coefficients.png](outputs/figures/ercot_outage_model_coefficients.png)
  - Coefficients from the exploratory outage model
- [ercot_uri_like_lost_revenue.png](outputs/figures/ercot_uri_like_lost_revenue.png)
  - Utility comparison of incremental lost revenue in the URI-like scenario

## Dependencies

Install dependencies with `pip install -r requirements.txt`. The scripts require:

- `pandas`
- `numpy`
- `scikit-learn`
- `matplotlib`
- `seaborn`
- `geopandas`
- `openpyxl`
- `requests`

## Important limitations

- The outage model is exploratory. It uses a small utility-year panel and should not be treated as causal.
- NOAA Storm Events in Texas do not always classify winter hazards the way ERCOT practitioners would discuss them, so the repo currently uses winter-season storm records rather than only explicit winter-hazard labels.
- Weather severity is represented with one NOAA station per utility territory, which is a pragmatic proxy rather than a full spatial weather surface.
- Lost revenue is an estimate derived from delivery revenue and outage duration, not a filed accounting number from each utility.

## Next steps

The most valuable improvements to this repo would be:

- adding a richer outage/event source that ties more directly to utility-specific winter incidents
- replacing the one-station-per-utility weather proxy with a broader spatial weather representation
- tightening the financial model to reflect actual utility recovery, rate, or restoration mechanisms
- testing alternative model forms beyond the current linear baseline
