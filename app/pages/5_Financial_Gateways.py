import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from utils import (
    PALETTE,
    apply_custom_css,
    format_currency,
    format_number,
    render_kpi,
    run_query,
    style_plot,
)

st.set_page_config(
    page_title="Financial Gateways | Fashion Analytics",
    page_icon="💳",
    layout="wide",
)
apply_custom_css()

st.title("💳 Payment Gateway Reliability & Retry Recovery")
st.markdown(
    "Decision support for payment provider negotiation, gateway redundancy, "
    "failure root cause analysis, and customer retry recovery flows."
)

st.markdown(
    """
    <span class="badge badge-blue">Question F1: Success vs. Failure Rate by Payment Method</span>
    <span class="badge badge-green">Question F2: Lost Revenue & Customer Retry Success Rates</span>
    """,
    unsafe_allow_html=True,
)
st.markdown("---")

# Query payments mart
pay_df = run_query(
    """
    SELECT
        payment_method,
        sum(total_payment_attempts) as total_attempts,
        sum(successful_attempts) as successful_attempts,
        sum(failed_attempts) as failed_attempts,
        round(100.0 * sum(successful_attempts) / nullif(sum(total_payment_attempts), 0), 2) as success_rate_pct,
        round(100.0 * sum(failed_attempts) / nullif(sum(total_payment_attempts), 0), 2) as failure_rate_pct,
        round(sum(successful_revenue), 2) as successful_revenue,
        round(sum(lost_revenue_failed), 2) as lost_revenue_failed,
        sum(failed_attempts_retried) as failed_retried,
        sum(failed_attempts_retry_succeeded) as retry_succeeded,
        round(100.0 * sum(failed_attempts_retried) / nullif(sum(failed_attempts), 0), 2) as retry_rate_pct,
        round(100.0 * sum(failed_attempts_retry_succeeded) / nullif(sum(failed_attempts_retried), 0), 2) as retry_success_rate_pct
    FROM gold.mart_payments
    GROUP BY payment_method
    ORDER BY total_attempts DESC
    """
)

# Top KPI row
k1, k2, k3, k4, k5 = st.columns(5)
tot_attempts = pay_df["total_attempts"].sum()
tot_success = pay_df["successful_attempts"].sum()
tot_failed = pay_df["failed_attempts"].sum()
tot_lost = pay_df["lost_revenue_failed"].sum()
overall_success_rate = tot_success / tot_attempts * 100
tot_retried = pay_df["failed_retried"].sum()
tot_retry_succ = pay_df["retry_succeeded"].sum()
retry_rate = tot_retried / tot_failed * 100 if tot_failed else 0
retry_succ_rate = tot_retry_succ / tot_retried * 100 if tot_retried else 0

render_kpi(k1, "Payment Attempts", format_number(tot_attempts))
render_kpi(
    k2, "Overall Success Rate", f"{overall_success_rate:.2f}%", help_text="Question F1"
)
render_kpi(
    k3,
    "Lost Revenue to Fails",
    format_currency(tot_lost),
    delta_positive=False,
    help_text="Question F2",
)
render_kpi(
    k4,
    "Customer Retry Rate",
    f"{retry_rate:.1f}%",
    help_text="Failed customers who tried again",
)
render_kpi(
    k5,
    "Retry Recovery Rate",
    f"{retry_succ_rate:.1f}%",
    help_text="Retries that succeeded",
)

st.markdown("### 📊 Authorization Success & Failure Rates by Provider (Question F1)")
col_p1, col_p2 = st.columns(2)

with col_p1:
    fig_rate = go.Figure()
    fig_rate.add_trace(
        go.Bar(
            x=pay_df["payment_method"],
            y=pay_df["success_rate_pct"],
            name="Success Rate %",
            marker_color=PALETTE["success"],
            text=pay_df["success_rate_pct"].apply(lambda x: f"{x:.1f}%"),
            textposition="auto",
        )
    )
    fig_rate.add_trace(
        go.Bar(
            x=pay_df["payment_method"],
            y=pay_df["failure_rate_pct"],
            name="Failure Rate %",
            marker_color=PALETTE["danger"],
            text=pay_df["failure_rate_pct"].apply(lambda x: f"{x:.1f}%"),
            textposition="auto",
        )
    )
    fig_rate.update_layout(
        barmode="group", yaxis={"title": "Rate (%)", "range": [0, 105]}
    )
    style_plot(fig_rate, title="Provider Authorization Success vs. Failure Rate")
    st.plotly_chart(fig_rate, use_container_width=True)

with col_p2:
    fig_rev_loss = px.bar(
        pay_df,
        x="payment_method",
        y="lost_revenue_failed",
        color="payment_method",
        title="Unrecovered Revenue Lost to Failed Payments (IDR)",
        labels={
            "lost_revenue_failed": "Lost Revenue (IDR)",
            "payment_method": "Gateway",
        },
    )
    style_plot(fig_rev_loss)
    st.plotly_chart(fig_rev_loss, use_container_width=True)

st.markdown("---")

st.markdown("### 🔄 Customer Retry Recovery Dynamics (Question F2)")
st.caption(
    "When payment fails, does the customer abandon the purchase, or do they retry with the same or another method? "
    "High retry rates indicate resilient purchase intent; low rates indicate critical drop-off friction."
)

col_retry1, col_retry2 = st.columns([1, 1])

with col_retry1:
    fig_funnel_retry = go.Figure(
        go.Funnel(
            y=["1. Failed Payments", "2. Customers Retried", "3. Eventual Success"],
            x=[tot_failed, tot_retried, tot_retry_succ],
            textinfo="value+percent initial",
            marker={"color": ["#EF4444", "#F59E0B", "#10B981"]},
        )
    )
    style_plot(fig_funnel_retry, title="Payment Failure Recovery Funnel")
    st.plotly_chart(fig_funnel_retry, use_container_width=True)

with col_retry2:
    # Monthly failure rate trends
    monthly_fail = run_query(
        """
        SELECT
            order_month,
            payment_method,
            round(100.0 * failed_attempts / nullif(total_payment_attempts, 0), 2) as failure_rate_pct
        FROM gold.mart_payments
        ORDER BY order_month ASC
        """
    )
    monthly_fail["order_month"] = pd.to_datetime(monthly_fail["order_month"])
    fig_month_fail = px.line(
        monthly_fail,
        x="order_month",
        y="failure_rate_pct",
        color="payment_method",
        title="Monthly Failure Rate Trajectory by Gateway",
        labels={"failure_rate_pct": "Failure Rate (%)", "order_month": "Month"},
    )
    style_plot(fig_month_fail)
    st.plotly_chart(fig_month_fail, use_container_width=True)

with st.expander("📋 View Complete Gateway Performance Metrics Table"):
    st.dataframe(
        pay_df.rename(
            columns={
                "payment_method": "Payment Method",
                "total_attempts": "Total Attempts",
                "successful_attempts": "Successful",
                "failed_attempts": "Failed",
                "success_rate_pct": "Success %",
                "failure_rate_pct": "Failure %",
                "successful_revenue": "Success Rev (IDR)",
                "lost_revenue_failed": "Lost Rev (IDR)",
                "failed_retried": "Retried Attempts",
                "retry_succeeded": "Retry Succeeded",
                "retry_rate_pct": "Retry Rate %",
                "retry_success_rate_pct": "Retry Success %",
            }
        ),
        use_container_width=True,
    )
