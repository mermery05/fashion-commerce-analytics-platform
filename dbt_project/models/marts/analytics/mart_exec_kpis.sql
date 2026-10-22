with successful_orders as (

    select
        booking_id,
        date_trunc('month', order_date)     as order_month,
        customer_id,
        arbitrary(is_first_order)           as is_first_order,
        sum(line_total)                     as order_gross_revenue,
        arbitrary(promo_amount)             as promo_amount,
        arbitrary(shipment_fee)             as shipment_fee,
        sum(line_total) - arbitrary(promo_amount) as order_net_revenue,
        sum(quantity)                       as total_units
    from {{ ref('fct_orders') }}
    where payment_status = 'Success'
    group by booking_id, date_trunc('month', order_date), customer_id

),

monthly_aggregation as (

    select
        order_month,
        count(distinct booking_id)          as total_orders,
        sum(total_units)                    as total_units_sold,
        count(distinct customer_id)         as active_customers,
        round(sum(order_gross_revenue), 2)  as gross_revenue,
        round(sum(promo_amount), 2)         as total_promo_cost,
        round(sum(order_net_revenue), 2)    as net_revenue,
        round(sum(shipment_fee), 2)         as total_shipping_revenue,
        round(sum(order_net_revenue) + sum(shipment_fee), 2) as total_collected_revenue,
        round(
            sum(order_net_revenue) / nullif(count(distinct booking_id), 0),
            2
        )                                   as avg_order_value,
        count(distinct case when is_first_order then booking_id end) as new_customer_orders,
        count(distinct case when not is_first_order then booking_id end) as returning_customer_orders,
        round(
            sum(case when is_first_order then order_net_revenue else 0.0 end),
            2
        )                                   as new_customer_net_revenue,
        round(
            sum(case when not is_first_order then order_net_revenue else 0.0 end),
            2
        )                                   as returning_customer_net_revenue
    from successful_orders
    group by order_month

)

select
    order_month,
    total_orders,
    total_units_sold,
    active_customers,
    gross_revenue,
    total_promo_cost,
    net_revenue,
    total_shipping_revenue,
    total_collected_revenue,
    avg_order_value,
    new_customer_orders,
    returning_customer_orders,
    new_customer_net_revenue,
    returning_customer_net_revenue,
    round(
        100.0 * new_customer_net_revenue / nullif(net_revenue, 0),
        2
    ) as new_customer_rev_share_pct,
    round(
        100.0 * returning_customer_net_revenue / nullif(net_revenue, 0),
        2
    ) as returning_customer_rev_share_pct,
    round(
        100.0 * (net_revenue - lag(net_revenue, 1) over (order by order_month))
        / nullif(lag(net_revenue, 1) over (order by order_month), 0),
        2
    ) as mom_net_revenue_growth_pct,
    round(
        100.0 * (net_revenue - lag(net_revenue, 12) over (order by order_month))
        / nullif(lag(net_revenue, 12) over (order by order_month), 0),
        2
    ) as yoy_net_revenue_growth_pct,
    round(
        100.0 * (total_orders - lag(total_orders, 1) over (order by order_month))
        / nullif(lag(total_orders, 1) over (order by order_month), 0),
        2
    ) as mom_orders_growth_pct,
    round(
        100.0 * (total_orders - lag(total_orders, 12) over (order by order_month))
        / nullif(lag(total_orders, 12) over (order by order_month), 0),
        2
    ) as yoy_orders_growth_pct,
    round(
        100.0 * (active_customers - lag(active_customers, 1) over (order by order_month))
        / nullif(lag(active_customers, 1) over (order by order_month), 0),
        2
    ) as mom_active_customers_growth_pct
from monthly_aggregation
order by order_month
