from pathlib import Path

import dagster as dg
from dagster_dbt import DagsterDbtTranslator, DbtCliResource, dbt_assets

DBT_PROJECT_DIR = Path(__file__).resolve().parent.parent.parent / "dbt_project"
MANIFEST_PATH = DBT_PROJECT_DIR / "target" / "manifest.json"

dbt_resource = DbtCliResource(project_dir=str(DBT_PROJECT_DIR))

if MANIFEST_PATH.exists():
    dbt_manifest_path = MANIFEST_PATH
else:
    dbt_manifest_path = dbt_resource.cli(["parse"]).target_path.joinpath(
        "manifest.json"
    )


class CustomDagsterDbtTranslator(DagsterDbtTranslator):
    def get_asset_key(self, dbt_resource_props):
        if dbt_resource_props.get("resource_type") == "source":
            return dg.AssetKey(f"bronze_{dbt_resource_props['name']}")
        return super().get_asset_key(dbt_resource_props)

    def get_group_name(self, dbt_resource_props) -> str:
        """Map dbt models to clear Medallion architecture asset groups (silver, gold)."""
        schema = dbt_resource_props.get("schema", "")
        fqn = dbt_resource_props.get("fqn", [])
        if "staging" in fqn or schema == "silver":
            return "silver"
        if "marts" in fqn or schema == "gold":
            return "gold"
        return super().get_group_name(dbt_resource_props) or "default"


@dbt_assets(
    manifest=dbt_manifest_path,
    dagster_dbt_translator=CustomDagsterDbtTranslator(),
)
def dbt_fashion_assets(context: dg.AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()
