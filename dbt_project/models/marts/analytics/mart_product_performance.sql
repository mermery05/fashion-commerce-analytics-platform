with cart_adds as (

    select
        product_id,
        count(*)                            as cart_add_events,
        count(distinct session_id)          as distinct_sessions_carted,
        sum(quantity)                       as total_cart_units
    from {{ ref('stg_clickstream') }}
    where event_name = 'ADD_TO_CART'
      and product_id is not null
    group by product_id

),

order_sales as (

    select
        product_id,
        count(distinct booking_id)          as total_orders,
        sum(quantity)                       as total_units_sold,
        round(sum(line_total), 2)           as gross_revenue,
        round(sum(line_net_total), 2)       as net_revenue,
        min(order_date)                     as first_sold_date,
        max(order_date)                     as last_sold_date
    from {{ ref('fct_orders') }}
    where payment_status = 'Success'
      and product_id is not null
    group by product_id

)

select
    p.product_id,
    p.product_display_name,
    p.master_category,
    p.sub_category,
    p.article_type,
    p.base_colour,
    p.season,
    p.year,
    p.usage,
    p.brand,
    p.velocity_tier,
    coalesce(c.cart_add_events, 0)          as cart_add_events,
    coalesce(c.distinct_sessions_carted, 0) as distinct_sessions_carted,
    coalesce(s.total_orders, 0)             as total_orders,
    coalesce(s.total_units_sold, 0)         as total_units_sold,
    coalesce(s.gross_revenue, 0.0)          as gross_revenue,
    coalesce(s.net_revenue, 0.0)            as net_revenue,
    s.first_sold_date,
    s.last_sold_date,
    round(
        100.0 * coalesce(s.total_orders, 0) / nullif(c.cart_add_events, 0),
        2
    )                                       as cart_to_order_conversion_pct,
    case
        when coalesce(c.cart_add_events, 0) >= 30 and coalesce(s.total_orders, 0) = 0
            then 'High Cart / Zero Sales (Reprice/Photograph)'
        when coalesce(s.total_units_sold, 0) >= 100
            then 'Top Seller'
        when coalesce(s.total_units_sold, 0) >= 20
            then 'Steady Mover'
        when coalesce(s.total_units_sold, 0) > 0
            then 'Slow Mover'
        else 'Unsold / Dormant'
    end as merchandising_action
from {{ ref('dim_products') }} as p
left join cart_adds as c
    on p.product_id = c.product_id
left join order_sales as s
    on p.product_id = s.product_id
