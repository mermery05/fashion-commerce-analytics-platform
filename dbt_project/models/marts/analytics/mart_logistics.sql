with order_logistics as (

    select
        booking_id,
        customer_id,
        order_date,
        date_trunc('month', order_date)     as order_month,
        home_country,
        home_location,
        arbitrary(shipment_lat)             as shipment_lat,
        arbitrary(shipment_long)            as shipment_long,
        arbitrary(home_lat)                 as home_lat,
        arbitrary(home_long)                as home_long,
        arbitrary(delivery_distance_km)     as delivery_distance_km,
        arbitrary(promised_lead_days)       as promised_lead_days,
        arbitrary(sla_window_tier)          as sla_window_tier,
        arbitrary(distance_tier)            as distance_tier,
        arbitrary(shipment_fee)             as shipment_fee,
        sum(line_total)                     as order_gross_value,
        sum(quantity)                       as total_units
    from {{ ref('fct_orders') }}
    where payment_status = 'Success'
    group by
        booking_id,
        customer_id,
        order_date,
        date_trunc('month', order_date),
        home_country,
        home_location

)

select
    booking_id,
    customer_id,
    order_date,
    order_month,
    home_country,
    home_location,
    shipment_lat,
    shipment_long,
    home_lat,
    home_long,
    delivery_distance_km,
    distance_tier,
    promised_lead_days,
    sla_window_tier,
    shipment_fee,
    order_gross_value,
    total_units,
    (shipment_fee = 0.0) as is_free_shipping,
    round(
        100.0 * shipment_fee / nullif(order_gross_value, 0),
        2
    ) as shipping_pct_of_order_value
from order_logistics
