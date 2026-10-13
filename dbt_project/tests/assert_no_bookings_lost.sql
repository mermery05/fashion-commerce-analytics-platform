-- Flattening product_metadata must not drop any order. A booking whose
-- metadata cannot be parsed would silently vanish from stg_transactions.
-- Passes when the booking counts match.
with silver as (
    select count(distinct booking_id) as n from {{ ref('stg_transactions') }}
),

bronze as (
    select count(distinct booking_id) as n
    from {{ source('bronze', 'transactions') }}
)

select
    bronze.n as bronze_bookings,
    silver.n as silver_bookings
from bronze, silver
where bronze.n <> silver.n
