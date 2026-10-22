with order_level as (

    select
        booking_id,
        date_trunc('month', order_date)     as order_month,
        customer_id,
        home_country,
        home_location,
        arbitrary(delivery_distance_km)     as delivery_distance_km,
        sum(line_total)                     as order_gross_revenue,
        arbitrary(promo_amount)             as promo_amount,
        arbitrary(shipment_fee)             as shipment_fee,
        sum(line_total) - arbitrary(promo_amount) as order_net_revenue
    from {{ ref('fct_orders') }}
    where payment_status = 'Success'
    group by
        booking_id,
        date_trunc('month', order_date),
        customer_id,
        home_country,
        home_location

)

select
    order_month,
    home_country,
    home_location,
    count(distinct booking_id)              as total_orders,
    count(distinct customer_id)             as active_customers,
    round(sum(order_gross_revenue), 2)      as gross_revenue,
    round(sum(promo_amount), 2)             as total_promo_cost,
    round(sum(order_net_revenue), 2)        as net_revenue,
    round(sum(shipment_fee), 2)             as total_shipment_fees,
    round(avg(shipment_fee), 2)             as avg_shipment_fee,
    round(
        100.0 * sum(shipment_fee) / nullif(sum(order_gross_revenue), 0),
        2
    )                                       as shipping_pct_of_order_value,
    round(
        sum(order_net_revenue) / nullif(count(distinct booking_id), 0),
        2
    )                                       as avg_order_value,
    round(avg(delivery_distance_km), 2)     as avg_delivery_distance_km,
    rank() over (
        partition by order_month
        order by sum(order_net_revenue) desc
    )                                       as monthly_region_revenue_rank
from order_level
group by order_month, home_country, home_location
