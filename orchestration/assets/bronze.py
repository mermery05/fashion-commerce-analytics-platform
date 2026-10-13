import time
import dagster as dg
import duckdb
import json
import re
from pathlib import Path
import pandas as pd

from src.ingest import csv_to_bronze
from src.weather import fetch_daily_weather
from src.calendar_data import holiday_rows

SOURCES = {
    "customers": "customer.csv",
    "products": "product.csv",
    "transactions": "transactions.csv",
    "clickstream": "click_stream.csv",
}


def _write_parquet(rows: list[dict], table: str) -> None:
    out_dir = Path(f"data/bronze/{table}")
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df["_ingested_at"] = pd.Timestamp.now()
    con = duckdb.connect()
    con.register("df", df)
    con.execute(f"COPY df TO '{out_dir}/part.parquet' (FORMAT PARQUET)")


def make_bronze_asset(table: str, filename: str):
    @dg.asset(name=f"bronze_{table}", group_name="bronze")
    def _asset(context: dg.AssetExecutionContext):
        meta = csv_to_bronze(f"data/raw/{filename}", table)
        context.add_output_metadata(meta)

    return _asset


bronze_assets = [make_bronze_asset(t, f) for t, f in SOURCES.items()]
CACHE = Path("data/bronze/_cache/weather")


@dg.asset(group_name="bronze", deps=["bronze_customers", "bronze_transactions"])
def bronze_weather(context: dg.AssetExecutionContext):
    CACHE.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    locs = con.execute("""
        SELECT home_location, avg(cast(home_location_lat AS double)),
               avg(cast(home_location_long AS double))
        FROM 'data/bronze/customers/*.parquet'
        WHERE home_location IS NOT NULL
        GROUP BY 1
    """).fetchall()
    start, end = con.execute("""
        SELECT min(cast(created_at AS timestamp))::date::varchar,
               max(cast(created_at AS timestamp))::date::varchar
        FROM 'data/bronze/transactions/*.parquet'
    """).fetchone()

    rows, fetched, from_cache = [], 0, 0
    for name, lat, lon in locs:
        cache_file = CACHE / f"{re.sub(r'\W+', '_', name)}.json"
        if cache_file.exists():
            data = json.loads(cache_file.read_text())
            from_cache += 1
        else:
            data = fetch_daily_weather(lat, lon, start, end)
            cache_file.write_text(json.dumps(data))
            fetched += 1
            time.sleep(5)  # stay well under the limit
        rows.extend({"location": name, **r} for r in data)

    _write_parquet(rows, "weather")
    context.add_output_metadata(
        {
            "locations": len(locs),
            "rows": len(rows),
            "fetched_from_api": fetched,
            "loaded_from_cache": from_cache,
        }
    )


@dg.asset(group_name="bronze", deps=["bronze_transactions"])
def bronze_holidays(context: dg.AssetExecutionContext):
    con = duckdb.connect()
    y0, y1 = con.execute("""
        SELECT year(min(cast(created_at AS timestamp))), year(max(cast(created_at AS timestamp)))
        FROM 'data/bronze/transactions/*.parquet'
    """).fetchone()
    rows = holiday_rows("ID", y0, y1)  # change the country code if needed
    _write_parquet(rows, "holidays")
    context.add_output_metadata({"rows": len(rows)})


def _make_check(table: str):
    @dg.asset_check(asset=f"bronze_{table}", name=f"{table}_not_empty")
    def _check():
        n = duckdb.sql(
            f"SELECT count(*) FROM 'data/bronze/{table}/*.parquet'"
        ).fetchone()[0]
        return dg.AssetCheckResult(passed=n > 0, metadata={"rows": n})

    return _check


bronze_checks = [_make_check(t) for t in [*SOURCES, "weather", "holidays"]]
