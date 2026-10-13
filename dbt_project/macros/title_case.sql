{# Title Case every word, like pandas .str.title(). Returns NULL for blank input. #}
{% macro title_case(col) -%}
nullif(
    array_to_string(
        list_transform(
            string_split(lower(trim({{ col }})), ' '),
            w -> upper(w[1]) || w[2:]
        ),
        ' '
    ),
    ''
)
{%- endmacro %}
