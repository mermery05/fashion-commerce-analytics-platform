with customer_base as (

    select
        customer_id,
        gender,
        device_type,
        home_location,
        home_country,
        first_join_date,
        tenure_days,
        total_orders,
        total_units_purchased,
        lifetime_spend,
        avg_order_value,
        first_order_date,
        last_order_date,
        days_since_last_order,
        is_repeat_buyer,
        customer_activity_status,
        rfm_segment
    from {{ ref('dim_customers') }}

)

select
    customer_id,
    gender,
    device_type,
    home_location,
    home_country,
    first_join_date,
    tenure_days,
    total_orders,
    total_units_purchased,
    lifetime_spend,
    avg_order_value,
    first_order_date,
    last_order_date,
    days_since_last_order,
    is_repeat_buyer,
    customer_activity_status,
    rfm_segment,
    case
        when total_orders <= 1 then null
        else round(
            datediff('day', first_order_date, last_order_date)
            / nullif(total_orders - 1, 0),
            1
        )
    end as avg_days_between_orders
from customer_base
