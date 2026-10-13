{{ config(severity='warn') }}

-- Orders whose product_metadata could not be parsed (kept with NULL product).
-- Warn-level: reports how many orders have no usable line items.
select
    booking_id,
    created_at,
    total_amount
from {{ ref('stg_transactions') }}
where product_id is null
