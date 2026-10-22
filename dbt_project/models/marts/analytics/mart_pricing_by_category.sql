with order_lines as (

    select
        o.order_line_id,
        o.product_id,
        o.quantity,
        o.item_price,
        o.line_total,
        o.allocated_promo_amount,
        o.line_net_total,
        coalesce(p.master_category, 'Uncategorized') as master_category,
        coalesce(p.sub_category, 'Uncategorized')    as sub_category,
        coalesce(p.article_type, 'Uncategorized')     as article_type,
        case
            when o.item_price < 150000 then '1. Budget (< 150k)'
            when o.item_price < 250000 then '2. Mid-Low (150k-250k)'
            when o.item_price < 350000 then '3. Mid-High (250k-350k)'
            when o.item_price < 500000 then '4. Premium (350k-500k)'
            else '5. Luxury (> 500k)'
        end as price_band
    from {{ ref('fct_orders') }} as o
    left join {{ ref('dim_products') }} as p
        on o.product_id = p.product_id
    where o.payment_status = 'Success'

)

select
    master_category,
    sub_category,
    article_type,
    price_band,
    count(*)                                            as total_order_lines,
    sum(quantity)                                       as total_units_sold,
    round(sum(line_total), 2)                           as gross_revenue,
    round(sum(allocated_promo_amount), 2)               as total_allocated_promo_cost,
    round(sum(line_net_total), 2)                       as net_revenue,
    round(
        100.0 * sum(allocated_promo_amount) / nullif(sum(line_total), 0),
        2
    )                                                   as gross_to_net_gap_pct,
    round(avg(item_price), 2)                           as avg_item_price,
    round(min(item_price), 2)                           as min_item_price,
    round(max(item_price), 2)                           as max_item_price
from order_lines
group by
    master_category,
    sub_category,
    article_type,
    price_band
