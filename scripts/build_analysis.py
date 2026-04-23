from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
FIG_DIR = ROOT / "outputs" / "figures"
DOCS_DIR = ROOT / "docs"
EXTERNAL_DIR = ROOT / "data" / "external"
UTILITY_NAMES = {
    3278: "AEP Texas Central Company",
    8901: "CenterPoint Energy",
    13830: "Nueces Electric Cooperative",
    20404: "AEP Texas North Company",
    40051: "Texas-New Mexico Power Co",
    44372: "Oncor Electric Delivery Company LLC",
}


def ensure_dirs() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)


def frame_block(df: pd.DataFrame) -> str:
    return "```text\n" + df.to_string(index=False) + "\n```"


def load_data() -> dict[str, pd.DataFrame]:
    data = {
        "reliability": pd.read_csv(RAW_DIR / "eia_reliability_2013_2024.csv"),
        "delivery": pd.read_csv(RAW_DIR / "eia_delivery_2020_2024.csv"),
        "service": pd.read_csv(RAW_DIR / "eia_service_territory_2023.csv"),
        "storm": pd.read_csv(RAW_DIR / "noaa_storm_events_ercot_winter_2000_2025.csv"),
        "weather": pd.read_csv(RAW_DIR / "noaa_daily_weather_ercot_2000_2025.csv"),
        "stations": pd.read_csv(RAW_DIR / "noaa_weather_stations_ercot.csv"),
    }
    for frame in data.values():
        if "utility_number" in frame.columns:
            frame["utility_name"] = frame["utility_number"].map(UTILITY_NAMES).fillna(
                frame.get("utility_name")
            )
    return data


def build_county_storm_panel(service: pd.DataFrame, storm: pd.DataFrame) -> pd.DataFrame:
    county_year = (
        storm.groupby(["year", "county"], as_index=False)
        .agg(
            winter_event_count=("EVENT_TYPE", "size"),
            event_types=("EVENT_TYPE", lambda s: ", ".join(sorted(set(s)))),
            property_damage_usd=("property_damage_usd", "sum"),
            crop_damage_usd=("crop_damage_usd", "sum"),
            direct_deaths=("DEATHS_DIRECT", "sum"),
            direct_injuries=("INJURIES_DIRECT", "sum"),
        )
    )
    merged = service.merge(county_year, on="county", how="left")
    for col in [
        "winter_event_count",
        "property_damage_usd",
        "crop_damage_usd",
        "direct_deaths",
        "direct_injuries",
    ]:
        merged[col] = merged[col].fillna(0)
    merged["year"] = merged["year_y"].fillna(merged["year_x"])
    merged = merged.drop(columns=["year_x", "year_y"])
    return merged


def build_utility_panel(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    service = data["service"]
    storm = data["storm"]
    weather = data["weather"]
    reliability = data["reliability"]
    delivery = data["delivery"]

    county_panel = build_county_storm_panel(service, storm)
    utility_storm = (
        county_panel.groupby(["utility_number", "year"], as_index=False)
        .agg(
            counties_in_territory=("county", "nunique"),
            winter_event_count=("winter_event_count", "sum"),
            storm_property_damage_usd=("property_damage_usd", "sum"),
            storm_crop_damage_usd=("crop_damage_usd", "sum"),
            direct_deaths=("direct_deaths", "sum"),
            direct_injuries=("direct_injuries", "sum"),
        )
    )
    utility_storm["utility_name"] = utility_storm["utility_number"].map(UTILITY_NAMES)

    panel = reliability.merge(
        utility_storm, on=["utility_number", "utility_name", "year"], how="left"
    ).merge(weather, on=["utility_number", "year"], how="left", suffixes=("", "_weather"))
    for col in [
        "counties_in_territory",
        "winter_event_count",
        "storm_property_damage_usd",
        "storm_crop_damage_usd",
        "direct_deaths",
        "direct_injuries",
    ]:
        panel[col] = panel[col].fillna(0)
    panel = panel.merge(
        delivery,
        on=["utility_number", "year"],
        how="left",
        suffixes=("", "_delivery"),
    )
    panel["utility_name"] = panel["utility_number"].map(UTILITY_NAMES)
    panel["avg_delivery_rate_usd_per_mwh"] = (
        panel["revenue_thousand_dollars"] * 1000 / panel["sales_mwh"]
    )
    panel["lost_revenue_estimate_usd"] = (
        panel["revenue_thousand_dollars"] * 1000 * panel["saidi_with_med_minutes"] / 525600
    )
    panel["storm_damage_millions"] = panel["storm_property_damage_usd"] / 1_000_000
    panel["delivery_rate_change_pct"] = (
        panel.sort_values(["utility_number", "year"])
        .groupby("utility_number")["avg_delivery_rate_usd_per_mwh"]
        .pct_change(fill_method=None)
        * 100
    )
    return panel.sort_values(["utility_number", "year"])


def fit_outage_model(panel: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    model_df = panel[
        [
            "utility_number",
            "utility_name",
            "year",
            "saidi_with_med_minutes",
            "winter_event_count",
            "storm_property_damage_usd",
            "freeze_days",
            "sub20f_days",
            "precip_days",
            "snow_days",
            "min_temp_c",
            "total_precip_mm",
        ]
    ].dropna()
    features = [
        "winter_event_count",
        "storm_property_damage_usd",
        "freeze_days",
        "sub20f_days",
        "precip_days",
        "snow_days",
        "min_temp_c",
        "total_precip_mm",
    ]
    X = model_df[features]
    y = model_df["saidi_with_med_minutes"]
    model = LinearRegression()
    model.fit(X, y)
    predictions = model.predict(X)
    model_df["predicted_saidi_minutes"] = predictions

    coeffs = pd.DataFrame(
        {"feature": features, "coefficient": model.coef_}
    ).sort_values("coefficient", key=np.abs, ascending=False)
    metrics = {
        "rows": int(len(model_df)),
        "r2_in_sample": float(r2_score(y, predictions)),
        "mae_minutes": float(mean_absolute_error(y, predictions)),
        "intercept": float(model.intercept_),
    }
    return model_df, {"metrics": metrics, "coefficients": coeffs}


def build_uri_scenario(panel: pd.DataFrame, model_info: dict) -> pd.DataFrame:
    coeff_frame = model_info["coefficients"].set_index("feature")
    coefficients = coeff_frame["coefficient"].to_dict()

    base = (
        panel[panel["year"] == 2024]
        .copy()
        .dropna(subset=["revenue_thousand_dollars", "sales_mwh", "freeze_days"])
    )
    uri_2021 = panel[panel["year"] == 2021][
        [
            "utility_number",
            "winter_event_count",
            "storm_property_damage_usd",
            "freeze_days",
            "sub20f_days",
            "precip_days",
            "snow_days",
            "min_temp_c",
            "total_precip_mm",
        ]
    ]
    uri_2021 = uri_2021.rename(
        columns={
            "winter_event_count": "uri_winter_event_count",
            "storm_property_damage_usd": "uri_storm_property_damage_usd",
            "freeze_days": "uri_freeze_days",
            "sub20f_days": "uri_sub20f_days",
            "precip_days": "uri_precip_days",
            "snow_days": "uri_snow_days",
            "min_temp_c": "uri_min_temp_c",
            "total_precip_mm": "uri_total_precip_mm",
        }
    )
    scenario = base.merge(uri_2021, on="utility_number", how="left")
    feature_pairs = [
        ("winter_event_count", "uri_winter_event_count"),
        ("storm_property_damage_usd", "uri_storm_property_damage_usd"),
        ("freeze_days", "uri_freeze_days"),
        ("sub20f_days", "uri_sub20f_days"),
        ("precip_days", "uri_precip_days"),
        ("snow_days", "uri_snow_days"),
        ("min_temp_c", "uri_min_temp_c"),
        ("total_precip_mm", "uri_total_precip_mm"),
    ]
    delta = np.zeros(len(scenario))
    for current_col, uri_col in feature_pairs:
        delta += coefficients[current_col] * (scenario[uri_col] - scenario[current_col])
    scenario["predicted_uri_like_saidi_minutes"] = (
        scenario["saidi_with_med_minutes"] + delta
    ).clip(lower=0)
    scenario["predicted_uri_like_lost_revenue_usd"] = (
        scenario["revenue_thousand_dollars"] * 1000 * scenario["predicted_uri_like_saidi_minutes"] / 525600
    )
    scenario["incremental_uri_like_lost_revenue_usd"] = (
        scenario["predicted_uri_like_lost_revenue_usd"] - scenario["lost_revenue_estimate_usd"]
    )
    return scenario[
        [
            "utility_number",
            "utility_name",
            "saidi_with_med_minutes",
            "predicted_uri_like_saidi_minutes",
            "lost_revenue_estimate_usd",
            "predicted_uri_like_lost_revenue_usd",
            "incremental_uri_like_lost_revenue_usd",
        ]
    ].sort_values("incremental_uri_like_lost_revenue_usd", ascending=False)


def save_processed_outputs(panel: pd.DataFrame, model_df: pd.DataFrame, scenario: pd.DataFrame) -> None:
    panel.to_csv(PROCESSED_DIR / "ercot_utility_winter_risk_panel.csv", index=False)
    model_df.to_csv(PROCESSED_DIR / "ercot_outage_model_predictions.csv", index=False)
    scenario.to_csv(PROCESSED_DIR / "ercot_uri_like_scenario_2024.csv", index=False)


def plot_county_choropleth(service: pd.DataFrame, storm: pd.DataFrame) -> None:
    county_totals = (
        storm.groupby("county", as_index=False)
        .agg(
            winter_event_count=("EVENT_TYPE", "size"),
            property_damage_usd=("property_damage_usd", "sum"),
        )
    )
    gdf = gpd.read_file(EXTERNAL_DIR / "texas_counties.geojson")
    gdf["county"] = gdf["NAME"].str.title()
    ercot_counties = service[["county"]].drop_duplicates()
    gdf = gdf.merge(ercot_counties, on="county", how="inner").merge(
        county_totals, on="county", how="left"
    )
    gdf["winter_event_count"] = gdf["winter_event_count"].fillna(0)

    fig, ax = plt.subplots(figsize=(10, 8))
    gdf.plot(
        column="winter_event_count",
        cmap="Blues",
        linewidth=0.3,
        edgecolor="white",
        legend=True,
        ax=ax,
    )
    ax.set_title("ERCOT County Winter Storm Event Counts, 2000-2025")
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "ercot_county_winter_storm_choropleth.png", dpi=200)
    plt.close(fig)


def plot_saidi_timeseries(panel: pd.DataFrame) -> None:
    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(11, 6))
    sns.lineplot(
        data=panel,
        x="year",
        y="saidi_with_med_minutes",
        hue="utility_name",
        marker="o",
        ax=ax,
    )
    ax.set_title("ERCOT Utility SAIDI With Major Event Days")
    ax.set_ylabel("Minutes per customer")
    ax.set_xlabel("")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "ercot_utility_saidi_timeseries.png", dpi=200)
    plt.close(fig)


def plot_delivery_rates(panel: pd.DataFrame) -> None:
    rate_df = panel.dropna(subset=["avg_delivery_rate_usd_per_mwh"])
    fig, ax = plt.subplots(figsize=(11, 6))
    sns.lineplot(
        data=rate_df,
        x="year",
        y="avg_delivery_rate_usd_per_mwh",
        hue="utility_name",
        marker="o",
        ax=ax,
    )
    ax.set_title("ERCOT Delivery Revenue per MWh")
    ax.set_ylabel("USD per MWh")
    ax.set_xlabel("")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "ercot_delivery_rate_timeseries.png", dpi=200)
    plt.close(fig)


def plot_model_coefficients(model_info: dict) -> None:
    coeffs = model_info["coefficients"].copy()
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.barplot(
        data=coeffs, x="coefficient", y="feature", hue="feature", dodge=False, palette="viridis", ax=ax
    )
    legend = ax.get_legend()
    if legend:
        legend.remove()
    ax.set_title("Linear Model Coefficients for SAIDI")
    ax.set_xlabel("Coefficient")
    ax.set_ylabel("")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "ercot_outage_model_coefficients.png", dpi=200)
    plt.close(fig)


def plot_uri_scenario(scenario: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(
        data=scenario,
        x="incremental_uri_like_lost_revenue_usd",
        y="utility_name",
        hue="utility_name",
        dodge=False,
        palette="magma",
        ax=ax,
    )
    legend = ax.get_legend()
    if legend:
        legend.remove()
    ax.set_title("Incremental Lost Revenue Under a URI-like 2024 Scenario")
    ax.set_xlabel("USD")
    ax.set_ylabel("")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "ercot_uri_like_lost_revenue.png", dpi=200)
    plt.close(fig)


def write_summary(panel: pd.DataFrame, model_info: dict, scenario: pd.DataFrame) -> None:
    latest_year = panel["year"].max()
    latest_rates = (
        panel[panel["year"] == latest_year]
        .dropna(subset=["avg_delivery_rate_usd_per_mwh"])
        .sort_values("avg_delivery_rate_usd_per_mwh", ascending=False)
    )
    worst_saidi = (
        panel.sort_values("saidi_with_med_minutes", ascending=False)
        .head(5)[["year", "utility_name", "saidi_with_med_minutes"]]
    )
    top_storm = (
        panel.sort_values("storm_property_damage_usd", ascending=False)
        .head(5)[["year", "utility_name", "storm_property_damage_usd"]]
    )

    lines = [
        "# ERCOT Winter Storm Outage and Financial Risk Analysis",
        "",
        "This project builds an ERCOT utility panel by combining EIA-861 delivery/reliability data, NOAA Storm Events winter-season storm records, NOAA daily station weather records, and the Aon climate report as background context.",
        "",
        "## What is in scope",
        "",
        "- Geography: ERCOT transmission and distribution utilities in Texas.",
        "- Historical storm exposure: 2000-2025.",
        "- Utility outage metrics: 2013-2024, the years available in EIA reliability files.",
        "- Delivery revenue and rate metrics: 2020-2024, the years available in EIA delivery company files.",
        "",
        "## Headline findings",
        "",
        f"- Highest in-sample outage year in the utility panel: {int(worst_saidi.iloc[0]['year'])} for {worst_saidi.iloc[0]['utility_name']} at {worst_saidi.iloc[0]['saidi_with_med_minutes']:.1f} SAIDI minutes.",
        f"- Highest 2024 delivery revenue per MWh: {latest_rates.iloc[0]['utility_name']} at ${latest_rates.iloc[0]['avg_delivery_rate_usd_per_mwh']:.2f}/MWh.",
        f"- Largest modeled URI-like incremental 2024 lost revenue: {scenario.iloc[0]['utility_name']} at ${scenario.iloc[0]['incremental_uri_like_lost_revenue_usd']:,.0f}.",
        "",
        "## Model notes",
        "",
        f"- Linear regression rows: {model_info['metrics']['rows']}",
        f"- In-sample R^2: {model_info['metrics']['r2_in_sample']:.3f}",
        f"- In-sample MAE: {model_info['metrics']['mae_minutes']:.1f} SAIDI minutes",
        "- The model is exploratory rather than causal. It uses utility-year level winter severity and storm exposure features to explain SAIDI with major event days.",
        "",
        "## Highest outage observations",
        "",
        frame_block(worst_saidi),
        "",
        "## Highest storm damage observations",
        "",
        frame_block(
            top_storm.assign(
            storm_property_damage_usd=lambda df: df["storm_property_damage_usd"].map(
                lambda x: f"${x:,.0f}"
            )
            )
        ),
        "",
        "## 2024 URI-like scenario",
        "",
        frame_block(
            scenario.assign(
                predicted_uri_like_lost_revenue_usd=lambda df: df[
                    "predicted_uri_like_lost_revenue_usd"
                ].map(lambda x: f"${x:,.0f}"),
                incremental_uri_like_lost_revenue_usd=lambda df: df[
                    "incremental_uri_like_lost_revenue_usd"
                ].map(lambda x: f"${x:,.0f}"),
            )
        ),
        "",
        "## Figures",
        "",
        "- `outputs/figures/ercot_county_winter_storm_choropleth.png`",
        "- `outputs/figures/ercot_utility_saidi_timeseries.png`",
        "- `outputs/figures/ercot_delivery_rate_timeseries.png`",
        "- `outputs/figures/ercot_outage_model_coefficients.png`",
        "- `outputs/figures/ercot_uri_like_lost_revenue.png`",
    ]
    (DOCS_DIR / "analysis_summary.md").write_text("\n".join(lines))
    (PROCESSED_DIR / "model_metrics.json").write_text(
        json.dumps(model_info["metrics"], indent=2)
    )


def main() -> None:
    ensure_dirs()
    data = load_data()
    panel = build_utility_panel(data)
    model_df, model_info = fit_outage_model(panel)
    scenario = build_uri_scenario(panel, model_info)
    save_processed_outputs(panel, model_df, scenario)
    plot_county_choropleth(data["service"], data["storm"])
    plot_saidi_timeseries(panel)
    plot_delivery_rates(panel)
    plot_model_coefficients(model_info)
    plot_uri_scenario(scenario)
    write_summary(panel, model_info, scenario)
    print("Built processed data, figures, and summary artifacts.")


if __name__ == "__main__":
    main()
