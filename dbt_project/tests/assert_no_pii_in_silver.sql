-- depends_on: {{ ref('stg_customers') }}
-- depends_on: {{ ref('stg_products') }}
-- depends_on: {{ ref('stg_transactions') }}
-- depends_on: {{ ref('stg_clickstream') }}

-- PII policy: no personal-data column may exist anywhere in the silver schema.
-- The test passes when this query returns zero rows.
select
    table_name,
    column_name
from information_schema.columns
where table_schema = 'silver'
  and lower(column_name) in ('first_name', 'last_name', 'email', 'username', 'device_id')
