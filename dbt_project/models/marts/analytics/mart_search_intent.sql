with search_events as (

    select
        lower(trim(search_keywords)) as search_keyword,
        session_id
    from {{ ref('stg_clickstream') }}
    where event_name = 'SEARCH'
      and search_keywords is not null

),

sessions as (

    select
        session_id,
        has_add_to_cart,
        has_booking,
        is_converted
    from {{ ref('fct_sessions') }}

),

aggregated as (

    select
        e.search_keyword,
        count(*)                                        as total_searches,
        count(distinct e.session_id)                    as distinct_sessions,
        count(distinct case when s.has_add_to_cart = 1 then e.session_id end) as sessions_with_cart_add,
        count(distinct case when s.has_booking = 1 then e.session_id end)     as sessions_with_booking,
        count(distinct case when s.is_converted then e.session_id end)        as converted_sessions
    from search_events as e
    left join sessions as s
        on e.session_id = s.session_id
    group by e.search_keyword

)

select
    search_keyword,
    total_searches,
    distinct_sessions,
    sessions_with_cart_add,
    sessions_with_booking,
    converted_sessions,
    round(
        100.0 * sessions_with_cart_add / nullif(distinct_sessions, 0),
        2
    ) as cart_add_rate_pct,
    round(
        100.0 * converted_sessions / nullif(distinct_sessions, 0),
        2
    ) as conversion_rate_pct,
    (converted_sessions = 0) as is_zero_conversion,
    case
        when distinct_sessions >= 1000 and converted_sessions = 0 then 'Catalog Gap (High Search, Zero Conversion)'
        when round(100.0 * converted_sessions / nullif(distinct_sessions, 0), 2) >= 60.0 then 'High Converting Intent'
        when round(100.0 * sessions_with_cart_add / nullif(distinct_sessions, 0), 2) >= 50.0
         and round(100.0 * converted_sessions / nullif(distinct_sessions, 0), 2) < 30.0
         then 'High Cart Add / Low Conversion (Friction)'
        else 'Standard Intent'
    end as intent_classification
from aggregated
