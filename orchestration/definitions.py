import dagster as dg
from orchestration.assets.bronze import (
    bronze_assets,
    bronze_weather,
    bronze_holidays,
    bronze_checks,
)

defs = dg.Definitions(
    assets=[*bronze_assets, bronze_weather, bronze_holidays],
    asset_checks=bronze_checks,
)
