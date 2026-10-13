-- Grain: one row per order line (booking_id x product).
-- WARNING for gold: promo_amount, shipment_fee and total_amount are ORDER-level
-- values repeated on every line of the order. Never SUM them at this grain;
-- sum line_total for revenue, and take order-level amounts once per booking_id.

with source as (

    select * from {{ source('bronze', 'transactions') }}

),

deduplicated as (

    select *
    from source
    qualify row_number() over (partition by booking_id order by _ingested_at desc) = 1

),

parsed as (

    select
        booking_id,
        try_cast(customer_id as bigint)                          as customer_id,
        session_id,
        try_cast(created_at as timestamp)                        as created_at,
        nullif(trim(payment_method), '')                         as payment_method,
        nullif(trim(payment_status), '')                         as payment_status,
        coalesce(nullif(trim(promo_code), ''), 'NO_PROMO')       as promo_code,
        coalesce(try_cast(promo_amount as double), 0)            as promo_amount,
        try_cast(shipment_fee as double)                         as shipment_fee,
        try_cast(shipment_date_limit as timestamp)               as shipment_date_limit,
        try_cast(shipment_location_lat as double)                as shipment_lat,
        try_cast(shipment_location_long as double)               as shipment_long,
        try_cast(total_amount as double)                         as total_amount,

        -- product_metadata is a Python-style list of dicts using single quotes.
        -- It only holds numbers, so swapping quotes yields valid JSON.
        from_json(
            try_cast(replace(product_metadata, '''', '"') as json),
            '[{"product_id":"BIGINT","quantity":"INTEGER","item_price":"DOUBLE"}]'
        ) as items

    from deduplicated

),

exploded as (

    -- An order whose metadata cannot be parsed is kept as ONE line with NULL
    -- product fields (like pandas explode on an empty list), so no order or
    -- revenue is silently lost. assert_orders_have_parsed_items warns about them.
    select
        * exclude (items),
        unnest(
            case
                when items is null or len(items) = 0
                then [cast(null as struct(product_id bigint, quantity integer, item_price double))]
                else items
            end
        ) as item
    from parsed

)

select
    booking_id || '-' || cast(
        row_number() over (
            partition by booking_id
            order by item.product_id, item.item_price, item.quantity
        ) as varchar
    )                                           as order_line_id,
    booking_id,
    customer_id,
    session_id,
    created_at,
    cast(created_at as date)                    as order_date,
    payment_method,
    payment_status,
    promo_code,
    promo_amount,
    shipment_fee,
    shipment_date_limit,
    shipment_lat,
    shipment_long,
    total_amount,
    item.product_id                             as product_id,
    item.quantity                               as quantity,
    item.item_price                             as item_price,
    item.quantity * item.item_price             as line_total
from exploded
