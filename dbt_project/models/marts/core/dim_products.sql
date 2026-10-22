with products as (

    select * from {{ ref('stg_products') }}

),

sales as (

    select
        product_id,
        count(distinct booking_id)              as total_orders,
        sum(quantity)                           as total_units_sold,
        round(sum(line_total), 2)               as total_revenue
    from {{ ref('stg_transactions') }}
    where payment_status = 'Success'
      and product_id is not null
    group by product_id

)

select
    p.product_id,
    p.gender,
    p.master_category,
    p.sub_category,
    p.article_type,
    p.base_colour,
    p.season,
    p.year,
    p.usage,
    p.brand,
    p.product_display_name,
    p.metadata_status,
    coalesce(s.total_orders, 0)                 as total_orders,
    coalesce(s.total_units_sold, 0)             as total_units_sold,
    coalesce(s.total_revenue, 0.0)              as total_revenue,
    round(
        coalesce(s.total_revenue, 0.0) / nullif(coalesce(s.total_units_sold, 0), 0),
        2
    )                                           as avg_selling_price,
    case
        when coalesce(s.total_units_sold, 0) = 0 then 'Zero Sales'
        when s.total_units_sold >= 100 then 'Top Seller'
        when s.total_units_sold >= 20 then 'Steady Mover'
        else 'Slow Mover'
    end                                         as velocity_tier
from products as p
left join sales as s
    on p.product_id = s.product_id
