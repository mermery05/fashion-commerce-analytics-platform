select
    session_date,
    traffic_source,
    count(*)                                            as sessions_with_cart,
    sum(case when is_converted then 1 else 0 end)       as sessions_converted,
    sum(case when not is_converted then 1 else 0 end)   as sessions_abandoned,
    round(
        100.0 * sum(case when is_converted then 1 else 0 end) / nullif(count(*), 0),
        2
    )                                                   as cart_to_paid_rate_pct,
    round(
        100.0 * sum(case when not is_converted then 1 else 0 end) / nullif(count(*), 0),
        2
    )                                                   as cart_abandonment_rate_pct,
    round(sum(cart_total_value), 2)                     as total_cart_value,
    round(
        sum(case when is_converted then cart_total_value else 0.0 end),
        2
    )                                                   as converted_cart_value,
    round(
        sum(case when not is_converted then cart_total_value else 0.0 end),
        2
    )                                                   as lost_revenue_abandoned_cart,
    round(
        sum(case when not is_converted then cart_total_value else 0.0 end)
        / nullif(sum(case when not is_converted then 1 else 0 end), 0),
        2
    )                                                   as avg_abandoned_cart_value
from {{ ref('fct_sessions') }}
where has_add_to_cart = 1
group by session_date, traffic_source
