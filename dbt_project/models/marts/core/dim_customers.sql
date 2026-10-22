with customers as (

    select * from {{ ref('stg_customers') }}

),

customer_orders as (

    select
        customer_id,
        count(distinct booking_id)          as total_orders,
        sum(quantity)                       as total_units_purchased,
        round(sum(line_total), 2)           as lifetime_spend,
        min(order_date)                     as first_order_date,
        max(order_date)                     as last_order_date
    from {{ ref('stg_transactions') }}
    where payment_status = 'Success'
    group by customer_id

),

joined as (

    select
        c.customer_id,
        c.gender,
        c.device_type,
        c.home_location,
        c.home_country,
        c.home_lat,
        c.home_long,
        c.birthdate,
        c.first_join_date,
        c.age,
        c.tenure_days,
        c.is_age_plausible,
        coalesce(o.total_orders, 0)          as total_orders,
        coalesce(o.total_units_purchased, 0) as total_units_purchased,
        coalesce(o.lifetime_spend, 0.0)      as lifetime_spend,
        round(
            coalesce(o.lifetime_spend, 0.0) / nullif(coalesce(o.total_orders, 0), 0),
            2
        )                                   as avg_order_value,
        o.first_order_date,
        o.last_order_date,
        datediff(
            'day',
            o.last_order_date,
            date '{{ var("reference_date") }}'
        )                                   as days_since_last_order,
        coalesce(o.total_orders > 1, false) as is_repeat_buyer
    from customers as c
    left join customer_orders as o
        on c.customer_id = o.customer_id

),

scored as (

    select
        *,
        case
            when total_orders = 0 then 0
            else ntile(5) over (
                partition by (total_orders > 0)
                order by days_since_last_order desc
            )
        end as r_score,
        case
            when total_orders = 0 then 0
            else ntile(5) over (
                partition by (total_orders > 0)
                order by total_orders asc
            )
        end as f_score,
        case
            when total_orders = 0 then 0
            else ntile(5) over (
                partition by (total_orders > 0)
                order by lifetime_spend asc
            )
        end as m_score
    from joined

)

select
    customer_id,
    gender,
    device_type,
    home_location,
    home_country,
    home_lat,
    home_long,
    birthdate,
    first_join_date,
    age,
    tenure_days,
    is_age_plausible,
    total_orders,
    total_units_purchased,
    lifetime_spend,
    avg_order_value,
    first_order_date,
    last_order_date,
    days_since_last_order,
    is_repeat_buyer,
    case
        when total_orders = 0 then 'Never Purchased'
        when days_since_last_order <= 90 then 'Active'
        when days_since_last_order <= 180 then 'At Risk'
        else 'Lapsed'
    end as customer_activity_status,
    r_score,
    f_score,
    m_score,
    case
        when total_orders = 0 then 'Never Purchased'
        when r_score >= 4 and f_score >= 4 then 'Champions'
        when r_score >= 3 and f_score >= 3 then 'Loyal Customers'
        when r_score >= 4 and f_score <= 2 then 'Potential Loyalists'
        when r_score = 3 and f_score <= 2 then 'Promising'
        when r_score <= 2 and f_score >= 4 then 'At Risk High Value'
        when r_score <= 2 and f_score between 2 and 3 then 'At Risk Regular'
        when r_score <= 2 and f_score = 1 then 'Hibernating / Lost'
        else 'Needs Attention'
    end as rfm_segment
from scored
