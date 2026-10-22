with booking_attempts as (

    select
        booking_id,
        customer_id,
        created_at,
        date_trunc('month', order_date)     as order_month,
        payment_method,
        payment_status,
        arbitrary(order_total_amount)       as order_total_amount,
        lead(payment_status) over (
            partition by customer_id
            order by created_at, booking_id
        )                                   as next_payment_status
    from {{ ref('fct_orders') }}
    group by
        booking_id,
        customer_id,
        created_at,
        date_trunc('month', order_date),
        payment_method,
        payment_status

),

monthly_aggregates as (

    select
        order_month,
        payment_method,
        count(*)                            as total_payment_attempts,
        count(case when payment_status = 'Success' then 1 end) as successful_attempts,
        count(case when payment_status = 'Failed' then 1 end)  as failed_attempts,
        round(
            sum(case when payment_status = 'Success' then order_total_amount else 0.0 end),
            2
        )                                   as successful_revenue,
        round(
            sum(case when payment_status = 'Failed' then order_total_amount else 0.0 end),
            2
        )                                   as lost_revenue_failed,
        count(
            case
                when payment_status = 'Failed' and next_payment_status is not null
                then 1
            end
        )                                   as failed_attempts_retried,
        count(
            case
                when payment_status = 'Failed' and next_payment_status = 'Success'
                then 1
            end
        )                                   as failed_attempts_retry_succeeded
    from booking_attempts
    group by order_month, payment_method

)

select
    order_month,
    payment_method,
    total_payment_attempts,
    successful_attempts,
    failed_attempts,
    round(
        100.0 * successful_attempts / nullif(total_payment_attempts, 0),
        2
    ) as success_rate_pct,
    round(
        100.0 * failed_attempts / nullif(total_payment_attempts, 0),
        2
    ) as failure_rate_pct,
    successful_revenue,
    lost_revenue_failed,
    failed_attempts_retried,
    failed_attempts_retry_succeeded,
    round(
        100.0 * failed_attempts_retried / nullif(failed_attempts, 0),
        2
    ) as retry_rate_pct,
    round(
        100.0 * failed_attempts_retry_succeeded / nullif(failed_attempts_retried, 0),
        2
    ) as retry_success_rate_pct
from monthly_aggregates
order by order_month, payment_method
