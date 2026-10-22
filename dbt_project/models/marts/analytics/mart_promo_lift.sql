with order_level as (

    select
        booking_id,
        customer_id,
        promo_code,
        is_first_order,
        arbitrary(promo_amount)             as promo_amount,
        sum(line_total)                     as order_gross_revenue,
        sum(line_total) - arbitrary(promo_amount) as order_net_revenue
    from {{ ref('fct_orders') }}
    where payment_status = 'Success'
    group by booking_id, customer_id, promo_code, is_first_order

),

aggregated as (

    select
        promo_code,
        case
            when is_first_order then 'New Customer'
            else 'Returning Customer'
        end                                 as customer_type,
        count(distinct booking_id)          as total_orders,
        count(distinct customer_id)         as distinct_customers,
        round(sum(order_gross_revenue), 2)  as total_gross_revenue,
        round(sum(promo_amount), 2)         as total_promo_discount,
        round(sum(order_net_revenue), 2)    as total_net_revenue,
        round(
            sum(order_gross_revenue) / nullif(count(distinct booking_id), 0),
            2
        )                                   as avg_order_value_gross,
        round(
            sum(order_net_revenue) / nullif(count(distinct booking_id), 0),
            2
        )                                   as avg_order_value_net,
        round(
            sum(promo_amount) / nullif(count(distinct booking_id), 0),
            2
        )                                   as avg_discount_per_order,
        round(
            100.0 * sum(promo_amount) / nullif(sum(order_gross_revenue), 0),
            2
        )                                   as discount_depth_pct
    from order_level
    group by promo_code, is_first_order

)

select
    promo_code,
    customer_type,
    total_orders,
    distinct_customers,
    total_gross_revenue,
    total_promo_discount,
    total_net_revenue,
    avg_order_value_gross,
    avg_order_value_net,
    avg_discount_per_order,
    discount_depth_pct,
    round(
        100.0 * total_orders / sum(total_orders) over (partition by customer_type),
        2
    ) as promo_share_within_cohort_pct
from aggregated
order by promo_code, customer_type
