{#
  Use the custom schema name as-is ("silver", "gold") instead of dbt's default
  "<target_schema>_<custom>" (which would produce "main_silver").
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
