with daily_sales as (

    select
        o.order_date,
        o.home_location,
        coalesce(p.master_category, 'Uncategorized') as master_category,
        count(distinct o.booking_id)                as total_orders,
        sum(o.quantity)                             as total_units_sold,
        round(sum(o.line_total), 2)                 as daily_gross_revenue,
        round(sum(o.line_net_total), 2)             as daily_net_revenue
    from {{ ref('fct_orders') }} as o
    left join {{ ref('dim_products') }} as p
        on o.product_id = p.product_id
    where o.payment_status = 'Success'
    group by o.order_date, o.home_location, coalesce(p.master_category, 'Uncategorized')

),

weather as (

    select
        location,
        weather_date,
        temp_mean_c,
        precip_mm
    from {{ ref('stg_weather') }}

),

calendar as (

    select
        date_day,
        year,
        month,
        month_name,
        day_name,
        is_weekend,
        is_holiday,
        holiday_name
    from {{ ref('dim_dates') }}

)

select
    s.order_date,
    s.home_location,
    s.master_category,
    s.total_orders,
    s.total_units_sold,
    s.daily_gross_revenue,
    s.daily_net_revenue,
    w.temp_mean_c,
    w.precip_mm,
    case
        when w.precip_mm > 5.0 then 'Rainy'
        when w.temp_mean_c >= 28.0 then 'Hot'
        when w.temp_mean_c is not null then 'Mild'
        else 'Unknown'
    end as weather_condition,
    c.year,
    c.month,
    c.month_name,
    c.day_name,
    c.is_weekend,
    c.is_holiday,
    c.holiday_name
from daily_sales as s
left join weather as w
    on s.home_location = w.location
   and s.order_date = w.weather_date
left join calendar as c
    on s.order_date = c.date_day
