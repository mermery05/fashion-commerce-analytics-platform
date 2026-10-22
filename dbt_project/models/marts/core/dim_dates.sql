with date_spine as (

    select cast(range as date) as date_day
    from range(date '2016-01-01', date '2023-01-01', interval '1 day')

),

holidays as (

    select
        holiday_date,
        holiday_name
    from {{ ref('stg_holidays') }}

)

select
    d.date_day,
    year(d.date_day)                                as year,
    quarter(d.date_day)                             as quarter,
    month(d.date_day)                               as month,
    monthname(d.date_day)                           as month_name,
    week(d.date_day)                                as week_of_year,
    day(d.date_day)                                 as day_of_month,
    dayofweek(d.date_day)                           as day_of_week,
    dayname(d.date_day)                             as day_name,
    coalesce(dayofweek(d.date_day) in (0, 6), false)                                             as is_weekend,
    coalesce(h.holiday_name is not null, false)     as is_holiday,
    h.holiday_name
from date_spine as d
left join holidays as h
    on d.date_day = h.holiday_date
