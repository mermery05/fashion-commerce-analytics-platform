{#
  event_metadata in the clickstream is a Python-style dict string, e.g.
    {'product_id': 4106, 'quantity': 2, 'item_price': 37000}
    {'search_keywords': "men's shirt"}
  Values can contain apostrophes, so converting to JSON by swapping quotes is
  unsafe. These macros pull one key out with a regex instead (\x27 = single quote).
#}

{% macro meta_num(col, key) -%}
try_cast(
    nullif(regexp_extract({{ col }}, '\x27{{ key }}\x27\s*:\s*(-?[0-9.]+)', 1), '')
    as double
)
{%- endmacro %}

{% macro meta_str(col, key) -%}
nullif(
    coalesce(
        nullif(regexp_extract({{ col }}, '\x27{{ key }}\x27\s*:\s*\x27(.*?)\x27\s*[,}]', 1), ''),
        nullif(regexp_extract({{ col }}, '\x27{{ key }}\x27\s*:\s*"(.*?)"\s*[,}]', 1), '')
    ),
    ''
)
{%- endmacro %}
