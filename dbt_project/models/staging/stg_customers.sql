with source as (

    select * from {{ source('bronze', 'customers') }}

),

deduplicated as (

    select *
    from source
    qualify row_number() over (partition by customer_id order by _ingested_at desc) = 1

),

typed as (

    -- Explicit column list on purpose: the PII columns (first_name, last_name,
    -- email, username, device_id) are never selected, so they cannot reach silver.
    select
        try_cast(customer_id as bigint)                                    as customer_id,
        upper(trim(gender))                                                as gender,
        trim(device_type)                                                  as device_type,
        trim(device_version)                                               as device_version,
        try_cast(regexp_extract(device_version, '(\d+)', 1) as integer)    as major_os_version,
        try_cast(home_location_lat as double)                              as home_lat,
        try_cast(home_location_long as double)                             as home_long,
        trim(home_location)                                                as home_location,
        trim(home_country)                                                 as home_country,
        cast(try_cast(birthdate as timestamp) as date)                     as birthdate,
        cast(try_cast(first_join_date as timestamp) as date)               as first_join_date
    from deduplicated

),

enriched as (

    select
        *,
        date_diff('day', birthdate, date '{{ var("reference_date") }}') // 365 as age,
        date_diff('day', first_join_date, date '{{ var("reference_date") }}')  as tenure_days
    from typed

)

select
    *,
    -- The notebook dropped customers under 15. Here they are flagged instead,
    -- so their orders keep a matching customer row (referential integrity).
    coalesce(age >= 15, false) as is_age_plausible
from enriched
