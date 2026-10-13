with source as (

    select * from {{ source('bronze', 'clickstream') }}

),

deduplicated as (

    select *
    from source
    qualify row_number() over (partition by event_id order by _ingested_at desc) = 1

),

typed as (

    select
        event_id,
        session_id,
        upper(trim(event_name))                       as event_name,
        try_cast(event_time as timestamp)             as event_time,
        upper(trim(traffic_source))                   as traffic_source,
        event_metadata
    from deduplicated

)

-- Metadata by event type:
--   SEARCH                    -> search_keywords
--   ITEM_DETAIL, ADD_TO_CART  -> product_id, quantity, item_price
--   BOOKING                   -> payment_status (+ promo_code, promo_amount)
--   everything else           -> none
select
    event_id,
    session_id,
    event_name,
    event_time,
    cast(event_time as date)                                                as event_date,
    hour(event_time)                                                        as event_hour,
    traffic_source,
    cast({{ meta_num('event_metadata', 'product_id') }} as bigint)          as product_id,
    cast({{ meta_num('event_metadata', 'quantity') }} as integer)           as quantity,
    {{ meta_num('event_metadata', 'item_price') }}                          as item_price,
    lower(trim({{ meta_str('event_metadata', 'search_keywords') }}))        as search_keywords,
    {{ meta_str('event_metadata', 'payment_status') }}                      as payment_status,
    coalesce({{ meta_str('event_metadata', 'promo_code') }}, 'NO_PROMO')    as promo_code,
    {{ meta_num('event_metadata', 'promo_amount') }}                        as promo_amount
from typed
