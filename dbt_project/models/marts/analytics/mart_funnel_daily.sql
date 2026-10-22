select
    session_date,
    traffic_source,
    count(*)                                            as total_sessions,
    sum(has_homepage)                                   as sessions_with_home,
    sum(has_search)                                     as sessions_with_search,
    sum(has_item_detail)                                as sessions_with_item_detail,
    sum(has_add_to_cart)                                as sessions_with_add_to_cart,
    sum(has_booking)                                    as sessions_with_booking,
    sum(case when is_converted then 1 else 0 end)       as converted_sessions,
    sum(case when is_bounced then 1 else 0 end)         as bounced_sessions,
    round(
        100.0 * sum(case when is_bounced then 1 else 0 end) / nullif(count(*), 0),
        2
    )                                                   as bounce_rate_pct,
    round(avg(duration_seconds), 1)                     as avg_duration_seconds,
    round(avg(total_events), 1)                         as avg_events_per_session,
    round(
        100.0 * sum(has_search) / nullif(sum(has_homepage), 0),
        2
    )                                                   as home_to_search_pct,
    round(
        100.0 * sum(has_item_detail) / nullif(sum(has_search), 0),
        2
    )                                                   as search_to_detail_pct,
    round(
        100.0 * sum(has_add_to_cart) / nullif(sum(has_item_detail), 0),
        2
    )                                                   as detail_to_cart_pct,
    round(
        100.0 * sum(has_booking) / nullif(sum(has_add_to_cart), 0),
        2
    )                                                   as cart_to_booking_pct,
    round(
        100.0 * sum(case when is_converted then 1 else 0 end)
        / nullif(sum(has_booking), 0),
        2
    )                                                   as booking_to_paid_pct,
    round(
        100.0 * sum(has_booking) / nullif(count(*), 0),
        2
    )                                                   as session_to_booking_rate_pct,
    round(
        100.0 * sum(case when is_converted then 1 else 0 end) / nullif(count(*), 0),
        2
    )                                                   as overall_conversion_rate_pct
from {{ ref('fct_sessions') }}
group by session_date, traffic_source
