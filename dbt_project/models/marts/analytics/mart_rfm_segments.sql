with base_customers as (

    select
        rfm_segment,
        gender,
        home_country,
        days_since_last_order,
        total_orders,
        lifetime_spend
    from {{ ref('dim_customers') }}

),

aggregated as (

    select
        rfm_segment,
        gender,
        home_country,
        count(*)                                as customer_count,
        round(sum(lifetime_spend), 2)           as total_revenue,
        round(avg(days_since_last_order), 1)    as avg_recency_days,
        round(avg(total_orders), 1)             as avg_order_frequency,
        round(avg(lifetime_spend), 2)           as avg_ltv,
        round(median(lifetime_spend), 2)        as median_ltv,
        round(quantile_cont(lifetime_spend, 0.25), 2) as p25_ltv,
        round(quantile_cont(lifetime_spend, 0.75), 2) as p75_ltv,
        round(quantile_cont(lifetime_spend, 0.90), 2) as p90_ltv,
        round(min(lifetime_spend), 2)           as min_ltv,
        round(max(lifetime_spend), 2)           as max_ltv
    from base_customers
    group by rfm_segment, gender, home_country

)

select
    rfm_segment,
    gender,
    home_country,
    customer_count,
    round(
        100.0 * customer_count / sum(customer_count) over (),
        2
    ) as pct_of_total_customers,
    total_revenue,
    round(
        100.0 * total_revenue / nullif(sum(total_revenue) over (), 0),
        2
    ) as pct_of_total_revenue,
    avg_recency_days,
    avg_order_frequency,
    avg_ltv,
    median_ltv,
    p25_ltv,
    p75_ltv,
    p90_ltv,
    min_ltv,
    max_ltv
from aggregated
order by total_revenue desc
