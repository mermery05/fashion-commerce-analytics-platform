import dagster as dg

from orchestration.assets.bronze import (
    bronze_assets,
    bronze_checks,
    bronze_holidays,
    bronze_weather,
)
from orchestration.assets.dbt import dbt_fashion_assets, dbt_resource

# Define the full pipeline materialization job
daily_pipeline_job = dg.define_asset_job(
    name="daily_pipeline_job",
    selection=[*bronze_assets, bronze_weather, bronze_holidays, dbt_fashion_assets],
    description="Daily automated end-to-end pipeline: Ingests Bronze, transforms Silver staging, and updates Gold marts.",
)

# Daily automated schedule executing at 02:00 AM UTC
daily_pipeline_schedule = dg.ScheduleDefinition(
    job=daily_pipeline_job,
    cron_schedule="0 2 * * *",
    execution_timezone="UTC",
)

defs = dg.Definitions(
    assets=[*bronze_assets, bronze_weather, bronze_holidays, dbt_fashion_assets],
    asset_checks=bronze_checks,
    jobs=[daily_pipeline_job],
    schedules=[daily_pipeline_schedule],
    resources={"dbt": dbt_resource},
)
