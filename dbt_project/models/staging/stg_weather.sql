with source as (

    select * from {{ source('bronze', 'weather') }}

)

select
    trim(location)                          as location,
    cast("date" as date)                    as weather_date,
    try_cast(temp_mean_c as double)         as temp_mean_c,
    try_cast(precip_mm as double)           as precip_mm
from source
qualify row_number() over (
    partition by location, "date" order by _ingested_at desc
) = 1
