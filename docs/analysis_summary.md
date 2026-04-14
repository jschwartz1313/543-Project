# ERCOT Winter Storm Outage and Financial Risk Analysis

This project builds an ERCOT utility panel by combining EIA-861 delivery/reliability data, NOAA Storm Events winter-season storm records, NOAA daily station weather records, and the Aon climate report as background context.

## What is in scope

- Geography: ERCOT transmission and distribution utilities in Texas.
- Historical storm exposure: 2000-2025.
- Utility outage metrics: 2013-2024, the years available in EIA reliability files.
- Delivery revenue and rate metrics: 2020-2024, the years available in EIA delivery company files.

## Headline findings

- Highest in-sample outage year in the utility panel: 2024 for CenterPoint Energy at 4315.8 SAIDI minutes.
- Highest 2024 delivery revenue per MWh: AEP Texas Central Company at $36.07/MWh.
- Largest modeled URI-like incremental 2024 lost revenue: Oncor Electric Delivery Company LLC at $1,423,255.

## Model notes

- Linear regression rows: 48
- In-sample R^2: 0.184
- In-sample MAE: 441.6 SAIDI minutes
- The model is exploratory rather than causal. It uses utility-year level winter severity and storm exposure features to explain SAIDI with major event days.

## Highest outage observations

```text
 year              utility_name  saidi_with_med_minutes
 2024        CenterPoint Energy                4315.811
 2021        CenterPoint Energy                2365.551
 2017 AEP Texas Central Company                2050.900
 2024 Texas-New Mexico Power Co                1946.110
 2021 AEP Texas Central Company                1901.100
```

## Highest storm damage observations

```text
 year                        utility_name storm_property_damage_usd
 2015 Oncor Electric Delivery Company LLC               $41,223,500
 2015           Texas-New Mexico Power Co               $33,258,500
 2023                  CenterPoint Energy                $6,870,000
 2017                  CenterPoint Energy                $3,382,000
 2017           Texas-New Mexico Power Co                $2,688,000
```

## 2024 URI-like scenario

```text
 utility_number                        utility_name  saidi_with_med_minutes  predicted_uri_like_saidi_minutes  lost_revenue_estimate_usd predicted_uri_like_lost_revenue_usd incremental_uri_like_lost_revenue_usd
          44372 Oncor Electric Delivery Company LLC                 532.480                        684.917181               4.971587e+06                          $6,394,842                            $1,423,255
           3278           AEP Texas Central Company                 228.500                        265.265797               4.889191e+05                            $567,586                               $78,667
          20404             AEP Texas North Company                 108.000                        253.832210               4.809542e+04                            $113,039                               $64,943
          40051           Texas-New Mexico Power Co                1946.110                       1892.392723               1.536579e+06                          $1,494,166                              $-42,413
           8901                  CenterPoint Energy                4315.811                       4100.344810               2.624168e+07                         $24,931,569                           $-1,310,112
          13830         Nueces Electric Cooperative                 437.147                               NaN               5.107284e+03                                $nan                                  $nan
```

## Figures

- `outputs/figures/ercot_county_winter_storm_choropleth.png`
- `outputs/figures/ercot_utility_saidi_timeseries.png`
- `outputs/figures/ercot_delivery_rate_timeseries.png`
- `outputs/figures/ercot_outage_model_coefficients.png`
- `outputs/figures/ercot_uri_like_lost_revenue.png`
