with transactions as (

    select * from {{ ref('stg_transactions') }}

),

customers as (

    select
        customer_id,
        home_location,
        home_country,
        home_lat,
        home_long
    from {{ ref('stg_customers') }}

),

enriched as (

    select
        t.order_line_id,
        t.booking_id,
        t.customer_id,
        t.session_id,
        t.product_id,
        t.order_date,
        t.created_at,
        t.payment_method,
        t.payment_status,
        coalesce(t.promo_code, 'NO_PROMO') as promo_code,
        coalesce(t.promo_amount, 0.0)      as promo_amount,
        coalesce(t.shipment_fee, 0.0)      as shipment_fee,
        t.shipment_date_limit,
        t.shipment_lat,
        t.shipment_long,
        c.home_location,
        c.home_country,
        c.home_lat,
        c.home_long,
        t.quantity,
        t.item_price,
        t.line_total,
        t.total_amount                     as order_total_amount,
        sum(t.line_total) over (
            partition by t.booking_id
        )                                  as order_gross_value,
        dense_rank() over (
            partition by t.customer_id
            order by t.created_at, t.booking_id
        )                                  as customer_order_seq,
        datediff(
            'day',
            cast(t.created_at as date),
            cast(t.shipment_date_limit as date)
        )                                  as promised_lead_days,
        round(
            2 * 6371 * asin(
                sqrt(
                    power(sin(radians(t.shipment_lat - c.home_lat) / 2), 2)
                    + cos(radians(c.home_lat)) * cos(radians(t.shipment_lat))
                    * power(sin(radians(t.shipment_long - c.home_long) / 2), 2)
                )
            ),
            2
        )                                  as delivery_distance_km
    from transactions as t
    left join customers as c
        on t.customer_id = c.customer_id

)

select
    order_line_id,
    booking_id,
    customer_id,
    session_id,
    product_id,
    order_date,
    created_at,
    payment_method,
    payment_status,
    promo_code,
    promo_amount,
    shipment_fee,
    shipment_date_limit,
    shipment_lat,
    shipment_long,
    home_location,
    home_country,
    home_lat,
    home_long,
    delivery_distance_km,
    promised_lead_days,
    case
        when promised_lead_days < 3 then '< 3 days'
        when promised_lead_days <= 5 then '3-5 days'
        when promised_lead_days <= 7 then '6-7 days'
        else '> 7 days'
    end as sla_window_tier,
    case
        when delivery_distance_km < 50 then '< 50 km (Local)'
        when delivery_distance_km < 250 then '50-250 km (Regional)'
        when delivery_distance_km < 1000 then '250-1000 km (Inter-city)'
        else '> 1000 km (Long Haul)'
    end as distance_tier,
    customer_order_seq,
    customer_order_seq = 1 as is_first_order,
    quantity,
    item_price,
    line_total,
    order_gross_value,
    round(
        line_total / nullif(order_gross_value, 0) * promo_amount,
        2
    ) as allocated_promo_amount,
    round(
        line_total - (line_total / nullif(order_gross_value, 0) * promo_amount),
        2
    ) as line_net_total,
    order_total_amount
from enriched
