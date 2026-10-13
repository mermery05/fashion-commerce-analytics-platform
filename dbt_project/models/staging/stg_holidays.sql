with source as (

    select * from {{ source('bronze', 'holidays') }}

)

select
    cast("date" as date)        as holiday_date,
    trim(holiday_name)          as holiday_name
from source
qualify row_number() over (
    partition by "date", holiday_name order by _ingested_at desc
) = 1
