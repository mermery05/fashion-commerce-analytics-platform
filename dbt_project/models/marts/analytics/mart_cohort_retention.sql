with customer_cohorts as (

    select
        customer_id,
        date_trunc('month', first_order_date) as cohort_month
    from {{ ref('dim_customers') }}
    where total_orders > 0
      and first_order_date is not null

),

cohort_sizes as (

    select
        cohort_month,
        count(distinct customer_id) as cohort_size
    from customer_cohorts
    group by cohort_month

),

customer_activities as (

    select
        c.cohort_month,
        datediff(
            'month',
            c.cohort_month,
            date_trunc('month', o.order_date)
        )                                   as month_number,
        o.customer_id,
        o.booking_id,
        o.line_total
    from {{ ref('fct_orders') }} as o
    inner join customer_cohorts as c
        on o.customer_id = c.customer_id
    where o.payment_status = 'Success'

),

aggregated as (

    select
        a.cohort_month,
        a.month_number,
        count(distinct a.customer_id)       as active_customers,
        count(distinct a.booking_id)        as total_orders,
        round(sum(a.line_total), 2)         as monthly_gross_revenue
    from customer_activities as a
    group by a.cohort_month, a.month_number

)

select
    agg.cohort_month,
    s.cohort_size,
    agg.month_number,
    agg.active_customers,
    agg.total_orders,
    agg.monthly_gross_revenue,
    round(
        100.0 * agg.active_customers / nullif(s.cohort_size, 0),
        2
    ) as retention_rate_pct,
    round(
        sum(agg.monthly_gross_revenue) over (
            partition by agg.cohort_month
            order by agg.month_number
            rows between unbounded preceding and current row
        ),
        2
    ) as cumulative_revenue,
    round(
        sum(agg.monthly_gross_revenue) over (
            partition by agg.cohort_month
            order by agg.month_number
            rows between unbounded preceding and current row
        ) / nullif(s.cohort_size, 0),
        2
    ) as cumulative_revenue_per_customer
from aggregated as agg
inner join cohort_sizes as s
    on agg.cohort_month = s.cohort_month
order by agg.cohort_month, agg.month_number
