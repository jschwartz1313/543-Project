from __future__ import annotations

import gzip
import io
import re
import time
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import geopandas as gpd
import requests


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
EXTERNAL_DIR = ROOT / "data" / "external"

EIA_BASE = "https://www.eia.gov/electricity/data/eia861"
NOAA_STORM_INDEX = "https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/"
NOAA_GHCN_BASE = "https://www.ncei.noaa.gov/pub/data/ghcn/daily"
AON_REPORT_URL = (
    "https://assets.aon.com/-/media/files/aon/reports/2025/"
    "2025-climate-catastrophe-insight.pdf"
)
CENSUS_COUNTY_URL = (
    "https://www2.census.gov/geo/tiger/TIGER2023/COUNTY/tl_2023_us_county.zip"
)

HEADERS = {"User-Agent": "codex-ercot-project/1.0"}
NOAA_INDEX_CACHE: str | None = None

ERCOT_UTILITIES = {
    3278: "AEP Texas Central Company",
    8901: "CenterPoint Energy",
    13830: "Nueces Electric Cooperative",
    20404: "AEP Texas North Company",
    40051: "Texas-New Mexico Power Co",
    44372: "Oncor Electric Delivery Company LLC",
}

UTILITY_STATIONS = {
    3278: {"station_id": "USW00012924", "station_name": "Corpus Christi"},
    8901: {"station_id": "USW00012918", "station_name": "Houston Hobby"},
    13830: {"station_id": "USW00012926", "station_name": "Alice"},
    20404: {"station_id": "USW00013962", "station_name": "Abilene"},
    40051: {"station_id": "USW00003904", "station_name": "College Station"},
    44372: {"station_id": "USW00013960", "station_name": "Dallas Love Field"},
}

WINTER_EVENT_TYPES = {
    "Winter Storm",
    "Ice Storm",
    "Winter Weather",
    "Cold/Wind Chill",
    "Extreme Cold/Wind Chill",
    "Heavy Snow",
    "Sleet",
    "Frost/Freeze",
    "Freezing Fog",
    "Blizzard",
    "High Wind",
    "Strong Wind",
}


def ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    EXTERNAL_DIR.mkdir(parents=True, exist_ok=True)


def fetch_bytes(url: str) -> bytes:
    last_error = None
    for attempt in range(3):
        try:
            response = requests.get(url, headers=HEADERS, timeout=180)
            response.raise_for_status()
            return response.content
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(2 * (attempt + 1))
    raise last_error


def eia_zip_url(year: int) -> str:
    if year == 2024:
        return f"{EIA_BASE}/zip/f861{year}.zip"
    return f"{EIA_BASE}/archive/zip/f861{year}.zip"


def clean_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.replace(".", pd.NA), errors="coerce")


def first_numeric(row: pd.Series, columns: list[str]) -> float | pd.NA:
    for column in columns:
        if column in row.index:
            value = pd.to_numeric(pd.Series([row[column]]).replace(".", pd.NA), errors="coerce").iloc[0]
            if pd.notna(value):
                return value
    return pd.NA


def latest_storm_file(year: int) -> str:
    global NOAA_INDEX_CACHE
    if NOAA_INDEX_CACHE is None:
        NOAA_INDEX_CACHE = requests.get(
            NOAA_STORM_INDEX, headers=HEADERS, timeout=180
        ).text
    html = NOAA_INDEX_CACHE
    pattern = rf"(StormEvents_details-ftp_v1\.0_d{year}_c\d+\.csv\.gz)"
    matches = re.findall(pattern, html)
    if not matches:
        raise RuntimeError(f"Could not find NOAA Storm Events file for {year}")
    return f"{NOAA_STORM_INDEX}{sorted(matches)[-1]}"


def damage_to_float(value: object) -> float:
    if pd.isna(value):
        return 0.0
    text = str(value).strip()
    if not text or text == "0.00K":
        return 0.0
    suffix = text[-1].upper()
    multipliers = {"K": 1_000.0, "M": 1_000_000.0, "B": 1_000_000_000.0}
    if suffix in multipliers:
        return float(text[:-1]) * multipliers[suffix]
    return float(text)


def extract_eia() -> None:
    reliability_rows: list[dict] = []
    delivery_rows: list[dict] = []
    service_frames: list[pd.DataFrame] = []

    for year in range(2013, 2025):
        data = fetch_bytes(eia_zip_url(year))
        archive = ZipFile(io.BytesIO(data))

        reliability_header = 2 if year >= 2021 else 1
        reliability = pd.read_excel(
            io.BytesIO(archive.read(f"Reliability_{year}.xlsx")),
            sheet_name="Reliability_States",
            header=reliability_header,
        )
        reliability = reliability[reliability["Utility Number"].isin(ERCOT_UTILITIES)]
        for _, row in reliability.iterrows():
            saidi_with_med = first_numeric(
                row, ["SAIDI With MED", "SAIDI (minutes per year)", "SAIDI (minutes per year).3"]
            )
            saifi_with_med = first_numeric(
                row, ["SAIFI With MED", "SAIFI (times per year)", "SAIFI (times per year).3"]
            )
            saidi_without_med = first_numeric(
                row,
                [
                    "SAIDI Without MED",
                    "SAIDI (minutes per year).1",
                    "SAIDI (minutes per year).4",
                ],
            )
            saifi_without_med = first_numeric(
                row,
                [
                    "SAIFI Without MED",
                    "SAIFI (times per year).1",
                    "SAIFI (times per year).4",
                ],
            )
            customer_value = first_numeric(row, ["Number of Customers", "Number of Customers.1"])
            reliability_rows.append(
                {
                    "year": year,
                    "utility_number": int(row["Utility Number"]),
                    "utility_name": row["Utility Name"],
                    "state": row["State"],
                    "saidi_with_med_minutes": saidi_with_med,
                    "saifi_with_med": saifi_with_med,
                    "saidi_without_med_minutes": saidi_without_med,
                    "saifi_without_med": saifi_without_med,
                    "customers": customer_value,
                }
            )

        if year >= 2020:
            delivery = pd.read_excel(
                io.BytesIO(archive.read(f"Delivery_Companies_{year}.xlsx")),
                header=2,
            )
            delivery = delivery[
                (delivery["Utility Number"].isin(ERCOT_UTILITIES))
                & (delivery["State"] == "TX")
                & (delivery["BA Code"] == "ERCO")
            ].copy()
            delivery = delivery.rename(
                columns={
                    "Thousand Dollars.4": "revenue_thousand_dollars",
                    "Megawatthours.4": "sales_mwh",
                    "Count.4": "customers",
                }
            )
            delivery["year"] = year
            delivery_rows.extend(
                delivery[
                    [
                        "year",
                        "Utility Number",
                        "Utility Name",
                        "revenue_thousand_dollars",
                        "sales_mwh",
                        "customers",
                    ]
                ]
                .rename(
                    columns={
                        "Utility Number": "utility_number",
                        "Utility Name": "utility_name",
                    }
                )
                .to_dict("records")
            )

        if year == 2023:
            service = pd.read_excel(
                io.BytesIO(archive.read("Service_Territory_2023.xlsx")),
                sheet_name="Counties_States",
            )
            service = service[service["Utility Number"].isin(ERCOT_UTILITIES)].copy()
            service["county"] = service["County"].str.strip().str.title()
            service_frames.append(
                service[
                    ["Data Year", "Utility Number", "Utility Name", "State", "county"]
                ].rename(
                    columns={
                        "Data Year": "year",
                        "Utility Number": "utility_number",
                        "Utility Name": "utility_name",
                        "State": "state",
                    }
                )
            )

    pd.DataFrame(reliability_rows).sort_values(
        ["utility_number", "year"]
    ).to_csv(RAW_DIR / "eia_reliability_2013_2024.csv", index=False)
    pd.DataFrame(delivery_rows).sort_values(
        ["utility_number", "year"]
    ).to_csv(RAW_DIR / "eia_delivery_2020_2024.csv", index=False)
    pd.concat(service_frames, ignore_index=True).sort_values(
        ["utility_number", "county"]
    ).to_csv(RAW_DIR / "eia_service_territory_2023.csv", index=False)


def extract_storm_events() -> None:
    service = pd.read_csv(RAW_DIR / "eia_service_territory_2023.csv")
    ercot_counties = set(service["county"].unique())
    frames: list[pd.DataFrame] = []

    for year in range(2000, 2026):
        url = latest_storm_file(year)
        compressed = fetch_bytes(url)
        with gzip.open(io.BytesIO(compressed), mode="rt", encoding="utf-8", errors="ignore") as handle:
            df = pd.read_csv(handle, low_memory=False)
        df = df[
            (df["STATE"] == "TEXAS")
            & (df["CZ_TYPE"] == "C")
            & (df["MONTH_NAME"].isin(["January", "February", "December"]))
        ].copy()
        df["county"] = (
            df["CZ_NAME"]
            .astype(str)
            .str.replace(" County", "", regex=False)
            .str.replace(r"\s+\(.*\)$", "", regex=True)
            .str.strip()
            .str.title()
        )
        df = df[df["county"].isin(ercot_counties)].copy()
        if df.empty:
            continue
        df["is_explicit_winter_event"] = df["EVENT_TYPE"].isin(WINTER_EVENT_TYPES)
        df["property_damage_usd"] = df["DAMAGE_PROPERTY"].map(damage_to_float)
        df["crop_damage_usd"] = df["DAMAGE_CROPS"].map(damage_to_float)
        frames.append(
            df[
                [
                    "YEAR",
                    "STATE",
                    "county",
                    "EVENT_TYPE",
                    "BEGIN_DATE_TIME",
                    "END_DATE_TIME",
                    "is_explicit_winter_event",
                    "MAGNITUDE",
                    "MAGNITUDE_TYPE",
                    "DEATHS_DIRECT",
                    "INJURIES_DIRECT",
                    "property_damage_usd",
                    "crop_damage_usd",
                    "EPISODE_NARRATIVE",
                    "EVENT_NARRATIVE",
                ]
            ].rename(columns={"YEAR": "year", "STATE": "state"})
        )

    storm = pd.concat(frames, ignore_index=True)
    storm.sort_values(["year", "county", "EVENT_TYPE"]).to_csv(
        RAW_DIR / "noaa_storm_events_ercot_winter_2000_2025.csv", index=False
    )


def parse_dly_line(line: str, station_id: str) -> list[dict]:
    year = int(line[11:15])
    month = int(line[15:17])
    element = line[17:21]
    if element not in {"TMIN", "TMAX", "PRCP", "SNOW", "SNWD"}:
        return []

    records = []
    for day in range(1, 32):
        base = 21 + (day - 1) * 8
        value = line[base : base + 5]
        try:
            numeric_value = int(value)
        except ValueError:
            continue
        if numeric_value == -9999:
            continue
        records.append(
            {
                "station_id": station_id,
                "year": year,
                "month": month,
                "day": day,
                "element": element,
                "value": numeric_value,
            }
        )
    return records


def extract_weather() -> None:
    stations_meta = []
    weather_rows: list[dict] = []

    stations_txt = fetch_bytes(f"{NOAA_GHCN_BASE}/ghcnd-stations.txt").decode("utf-8", "ignore")
    station_lookup = {}
    for line in stations_txt.splitlines():
        station_id = line[0:11].strip()
        if station_id in {v["station_id"] for v in UTILITY_STATIONS.values()}:
            station_lookup[station_id] = {
                "latitude": float(line[12:20]),
                "longitude": float(line[21:30]),
                "elevation_m": float(line[31:37]),
                "station_name": line[41:71].strip(),
            }

    for utility_number, station in UTILITY_STATIONS.items():
        station_id = station["station_id"]
        raw = fetch_bytes(f"{NOAA_GHCN_BASE}/all/{station_id}.dly").decode("utf-8", "ignore")
        station_records = []
        for line in raw.splitlines():
            station_records.extend(parse_dly_line(line, station_id))
        df = pd.DataFrame(station_records)
        df = df[df["year"].between(2000, 2025)].copy()
        pivot = (
            df.pivot_table(
                index=["station_id", "year", "month", "day"],
                columns="element",
                values="value",
                aggfunc="first",
            )
            .reset_index()
            .rename_axis(None, axis=1)
        )
        pivot = pivot[pivot["month"].isin([1, 2, 12])].copy()
        pivot["freeze_day"] = (pivot["TMIN"] <= 0).fillna(False)
        pivot["sub20f_day"] = (pivot["TMIN"] <= -67).fillna(False)
        pivot["precip_day"] = (pivot["PRCP"] >= 10).fillna(False)
        pivot["snow_day"] = (pivot.get("SNOW", pd.Series(dtype=float)).fillna(0) > 0)
        annual = (
            pivot.groupby("year")
            .agg(
                freeze_days=("freeze_day", "sum"),
                sub20f_days=("sub20f_day", "sum"),
                precip_days=("precip_day", "sum"),
                snow_days=("snow_day", "sum"),
                min_tmin_tenths_c=("TMIN", "min"),
                total_prcp_tenths_mm=("PRCP", "sum"),
            )
            .reset_index()
        )
        annual["utility_number"] = utility_number
        annual["utility_name"] = ERCOT_UTILITIES[utility_number]
        annual["station_id"] = station_id
        annual["station_name"] = station["station_name"]
        annual["min_temp_c"] = annual["min_tmin_tenths_c"] / 10.0
        annual["total_precip_mm"] = annual["total_prcp_tenths_mm"] / 10.0
        weather_rows.extend(
            annual[
                [
                    "year",
                    "utility_number",
                    "utility_name",
                    "station_id",
                    "station_name",
                    "freeze_days",
                    "sub20f_days",
                    "precip_days",
                    "snow_days",
                    "min_temp_c",
                    "total_precip_mm",
                ]
            ].to_dict("records")
        )
        stations_meta.append(
            {
                "utility_number": utility_number,
                "utility_name": ERCOT_UTILITIES[utility_number],
                "station_id": station_id,
                "requested_station_name": station["station_name"],
                **station_lookup.get(station_id, {}),
            }
        )

    pd.DataFrame(weather_rows).sort_values(
        ["utility_number", "year"]
    ).to_csv(RAW_DIR / "noaa_daily_weather_ercot_2000_2025.csv", index=False)
    pd.DataFrame(stations_meta).sort_values(
        ["utility_number"]
    ).to_csv(RAW_DIR / "noaa_weather_stations_ercot.csv", index=False)


def download_external_assets() -> None:
    report_path = EXTERNAL_DIR / "aon_2025_climate_and_catastrophe_insight.pdf"
    if not report_path.exists():
        report_path.write_bytes(fetch_bytes(AON_REPORT_URL))

    counties_geojson = EXTERNAL_DIR / "texas_counties.geojson"
    if not counties_geojson.exists():
        county_zip = EXTERNAL_DIR / "tl_2023_us_county.zip"
        county_zip.write_bytes(fetch_bytes(CENSUS_COUNTY_URL))
        counties = gpd.read_file(county_zip)
        counties = counties[counties["STATEFP"] == "48"].copy()
        counties.to_file(counties_geojson, driver="GeoJSON")
        county_zip.unlink(missing_ok=True)


def main() -> None:
    ensure_dirs()
    extract_eia()
    extract_storm_events()
    extract_weather()
    download_external_assets()
    print("Saved project-scoped raw datasets to", RAW_DIR)


if __name__ == "__main__":
    main()
