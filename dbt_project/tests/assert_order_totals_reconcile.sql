{{ config(severity='warn') }}

-- total_amount should equal the sum of line totals + shipment fee - promo.
-- Warn-level: mismatches are reported, not fatal. Tolerance is 1 currency unit.
select
    booking_id,
    sum(line_total) + max(shipment_fee) - max(promo_amount) as expected_total,
    max(total_amount)                                       as actual_total
from {{ ref('stg_transactions') }}
group by booking_id
having abs(expected_total - actual_total) > 1
