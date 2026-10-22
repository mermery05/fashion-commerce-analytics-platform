with clickstream as (

    select * from {{ ref('stg_clickstream') }}

),

session_aggregates as (

    select
        session_id,
        min(event_date)                                 as session_date,
        arbitrary(traffic_source)                       as traffic_source,
        min(event_time)                                 as session_start_time,
        max(event_time)                                 as session_end_time,
        datediff('second', min(event_time), max(event_time)) as duration_seconds,
        count(event_id)                                 as total_events,
        count(case when event_name = 'CLICK' then 1 end) as click_events,
        count(case when event_name = 'SCROLL' then 1 end) as scroll_events,
        max(case when event_name = 'HOMEPAGE' then 1 else 0 end) as has_homepage,
        max(case when event_name = 'SEARCH' then 1 else 0 end) as has_search,
        max(case when event_name = 'ITEM_DETAIL' then 1 else 0 end) as has_item_detail,
        max(case when event_name = 'ADD_TO_CART' then 1 else 0 end) as has_add_to_cart,
        max(case when event_name = 'BOOKING' then 1 else 0 end) as has_booking,
        max(case when event_name = 'BOOKING' and payment_status = 'Success' then 1 else 0 end)
            as has_successful_booking,
        coalesce(
            sum(case when event_name = 'ADD_TO_CART' then quantity else 0 end),
            0
        )                                               as cart_items_count,
        round(
            coalesce(
                sum(case when event_name = 'ADD_TO_CART' then quantity * item_price else 0.0 end),
                0.0
            ),
            2
        )                                               as cart_total_value
    from clickstream
    group by session_id

),

transactions as (

    select
        session_id,
        arbitrary(booking_id)                           as booking_id,
        arbitrary(customer_id)                          as customer_id,
        arbitrary(payment_method)                       as payment_method,
        arbitrary(payment_status)                       as payment_status,
        round(arbitrary(total_amount), 2)               as transaction_amount
    from {{ ref('stg_transactions') }}
    group by session_id

)

select
    s.session_id,
    s.session_date,
    s.traffic_source,
    s.session_start_time,
    s.session_end_time,
    s.duration_seconds,
    case
        when s.duration_seconds < 60 then '< 1 min'
        when s.duration_seconds < 300 then '1-5 mins'
        when s.duration_seconds < 900 then '5-15 mins'
        else '> 15 mins'
    end as duration_tier,
    s.total_events,
    s.click_events,
    s.scroll_events,
    s.has_homepage,
    s.has_search,
    s.has_item_detail,
    s.has_add_to_cart,
    s.has_booking,
    s.has_successful_booking,
    (s.has_homepage + s.has_search + s.has_item_detail + s.has_add_to_cart + s.has_booking) as funnel_progression_depth,
    s.cart_items_count,
    s.cart_total_value,
    (s.total_events = 1 or s.duration_seconds = 0)      as is_bounced,
    (s.has_successful_booking = 1)                      as is_converted,
    t.booking_id,
    t.customer_id,
    t.payment_method,
    t.payment_status,
    t.transaction_amount
from session_aggregates as s
left join transactions as t
    on s.session_id = t.session_id
