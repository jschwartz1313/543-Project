# ERCOT Winter Storm Outage Risk

This repository builds an ERCOT-focused utility analysis on winter storm outage risk and financial exposure. The project combines official EIA utility schedules, NOAA storm and weather data, and an Aon climate report to create a reproducible first-pass research workflow.

## Research question

How much can winter storm conditions in ERCOT help explain utility outages, and what do those outages imply for delivery-rate pressure and lost revenue risk?

## Scope

- Geography: ERCOT transmission and distribution utilities in Texas.
- Utility unit: service territories for the main ERCOT delivery utilities.
- Historical winter storm exposure: 2000-2025.
- Utility outage metrics: 2013-2024, based on EIA-861 reliability files.
- Delivery revenue and rate metrics: 2020-2024, based on EIA-861 delivery company files.

## Data sources

- EIA Form 861 detailed data files:
  - Reliability
  - Service Territory
  - Delivery Companies
- NOAA Storm Events Database
- NOAA GHCN Daily station data
- Aon 2025 Climate and Catastrophe Insight report

All project-scoped raw extracts are saved under [data/raw](/Users/jakeschwartz/543-Project/data/raw), with merged outputs under [data/processed](/Users/jakeschwartz/543-Project/data/processed).

## Repository layout

- [scripts/download_data.py](/Users/jakeschwartz/543-Project/scripts/download_data.py): downloads and filters the official datasets into ERCOT-scoped raw CSVs.
- [scripts/build_analysis.py](/Users/jakeschwartz/543-Project/scripts/build_analysis.py): creates the merged utility panel, figures, and summary artifacts.
- [docs/analysis_summary.md](/Users/jakeschwartz/543-Project/docs/analysis_summary.md): concise write-up of the current findings.
- [outputs/figures](/Users/jakeschwartz/543-Project/outputs/figures): generated plots.

## How to run

```bash
python3 scripts/download_data.py
python3 scripts/build_analysis.py
```

## Current outputs

- [ercot_utility_winter_risk_panel.csv](/Users/jakeschwartz/543-Project/data/processed/ercot_utility_winter_risk_panel.csv)
- [ercot_outage_model_predictions.csv](/Users/jakeschwartz/543-Project/data/processed/ercot_outage_model_predictions.csv)
- [ercot_uri_like_scenario_2024.csv](/Users/jakeschwartz/543-Project/data/processed/ercot_uri_like_scenario_2024.csv)
- [analysis_summary.md](/Users/jakeschwartz/543-Project/docs/analysis_summary.md)
- [ercot_county_winter_storm_choropleth.png](/Users/jakeschwartz/543-Project/outputs/figures/ercot_county_winter_storm_choropleth.png)
- [ercot_utility_saidi_timeseries.png](/Users/jakeschwartz/543-Project/outputs/figures/ercot_utility_saidi_timeseries.png)
- [ercot_delivery_rate_timeseries.png](/Users/jakeschwartz/543-Project/outputs/figures/ercot_delivery_rate_timeseries.png)
- [ercot_outage_model_coefficients.png](/Users/jakeschwartz/543-Project/outputs/figures/ercot_outage_model_coefficients.png)
- [ercot_uri_like_lost_revenue.png](/Users/jakeschwartz/543-Project/outputs/figures/ercot_uri_like_lost_revenue.png)

## Important limitations

- The outage model is exploratory. It uses a small utility-year panel and should not be treated as causal.
- NOAA Storm Events in Texas do not always classify winter hazards the way ERCOT practitioners would discuss them, so the repo currently uses winter-season storm records rather than only explicit winter-hazard labels.
- Weather severity is represented with one NOAA station per utility territory, which is a pragmatic proxy rather than a full spatial weather surface.
- Lost revenue is an estimate derived from delivery revenue and outage duration, not a filed accounting number from each utility.
