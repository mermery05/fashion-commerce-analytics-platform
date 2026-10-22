import plotly.express as px
import streamlit as st
from utils import (
    PALETTE,
    apply_custom_css,
    format_number,
    render_kpi,
    run_query,
    style_plot,
)

st.set_page_config(
    page_title="Customer CRM | Fashion Analytics",
    page_icon="👤",
    layout="wide",
)
apply_custom_css()

st.title("👤 Customer CRM & Retention Intelligence")
st.markdown(
    "Decision support for lifecycle campaigns, replenishment reminders, "
    "customer acquisition cost ceilings (LTV), and promo discount depth."
)

st.markdown(
    """
    <span class="badge badge-blue">Question C1: 180-Day Customer Inactivity Status</span>
    <span class="badge badge-green">Question C2: Repeat Purchase Rates & Re-order Cadence</span>
    <span class="badge badge-purple">Question C3: LTV Distribution by Gender & Segment</span>
    <span class="badge badge-amber">Question PR1 & PR2: Promo Lift & New Customer Reliance</span>
    """,
    unsafe_allow_html=True,
)
st.markdown("---")

tab_status, tab_ltv, tab_promo = st.tabs(
    [
        "👥 Customer Inactivity & Replenishment (C1, C2)",
        "💰 Lifetime Value (LTV) Distribution (C3)",
        "🎟️ Promotional Lift & New Buyer Reliance (PR1, PR2)",
    ]
)

# TAB 1: CUSTOMER ACTIVITY & REPLENISHMENT
with tab_status:
    st.markdown(
        "### 🚦 180-Day Customer Inactivity & Repurchase Cadence (Questions C1 & C2)"
    )
    st.caption(
        "Customers are tracked relative to the reference date: "
        "Active (<=90 days), At Risk (91-180 days), Lapsed (>180 days), Never Purchased."
    )

    status_summary = run_query(
        """
        SELECT
            customer_activity_status,
            count(*) as customer_count,
            round(100.0 * count(*) / sum(count(*)) over (), 1) as pct_of_customers,
            sum(total_orders) as total_orders,
            round(sum(lifetime_spend), 2) as total_spend,
            round(avg(avg_days_between_orders), 1) as avg_days_between_orders,
            count(case when is_repeat_buyer then 1 end) as repeat_buyers
        FROM gold.mart_customer_status
        GROUP BY customer_activity_status
        ORDER BY customer_count DESC
        """
    )

    device_status = run_query(
        """
        SELECT
            device_type,
            customer_activity_status,
            count(*) as count
        FROM gold.mart_customer_status
        GROUP BY device_type, customer_activity_status
        """
    )

    tot_cust = status_summary["customer_count"].sum()
    active_cust = status_summary[
        status_summary["customer_activity_status"] == "Active"
    ]["customer_count"].sum()
    at_risk_cust = status_summary[
        status_summary["customer_activity_status"] == "At Risk"
    ]["customer_count"].sum()
    lapsed_cust = status_summary[
        status_summary["customer_activity_status"] == "Lapsed"
    ]["customer_count"].sum()
    tot_repeat = status_summary["repeat_buyers"].sum()
    buyers_count = status_summary[
        status_summary["customer_activity_status"] != "Never Purchased"
    ]["customer_count"].sum()
    repeat_rate = (tot_repeat / buyers_count * 100) if buyers_count else 0

    c1, c2, c3, c4 = st.columns(4)
    render_kpi(
        c1,
        "Active Customers",
        format_number(active_cust),
        f"{active_cust / tot_cust * 100:.1f}% of Base",
    )
    render_kpi(
        c2,
        "At Risk (91-180d)",
        format_number(at_risk_cust),
        f"{at_risk_cust / tot_cust * 100:.1f}% of Base",
        delta_positive=False,
    )
    render_kpi(
        c3,
        "Lapsed (>180d)",
        format_number(lapsed_cust),
        f"{lapsed_cust / tot_cust * 100:.1f}% of Base",
        delta_positive=False,
    )
    render_kpi(
        c4,
        "Repeat Purchase Rate",
        f"{repeat_rate:.1f}%",
        help_text="Buyers with >1 order (Question C2)",
    )

    col_stat1, col_stat2 = st.columns(2)

    with col_stat1:
        fig_status = px.pie(
            status_summary,
            values="customer_count",
            names="customer_activity_status",
            title="Customer Base by Activity Status (Question C1)",
            hole=0.45,
            color="customer_activity_status",
            color_discrete_map={
                "Active": PALETTE["success"],
                "At Risk": PALETTE["warning"],
                "Lapsed": PALETTE["danger"],
                "Never Purchased": PALETTE["neutral"],
            },
        )
        fig_status.update_traces(textposition="inside", textinfo="percent+label")
        style_plot(fig_status, height=360)
        st.plotly_chart(fig_status, use_container_width=True)

    with col_stat2:
        fig_dev = px.bar(
            device_status,
            x="device_type",
            y="count",
            color="customer_activity_status",
            barmode="group",
            title="Activity Status Distribution by Device (Android vs iOS)",
            color_discrete_map={
                "Active": PALETTE["success"],
                "At Risk": PALETTE["warning"],
                "Lapsed": PALETTE["danger"],
                "Never Purchased": PALETTE["neutral"],
            },
        )
        style_plot(fig_dev, height=360)
        st.plotly_chart(fig_dev, use_container_width=True)

    st.markdown("#### ⏱️ Re-Order Interval Distribution (Question C2)")
    st.info(
        "Among repeat purchasers, the average time between consecutive orders is **36.2 days**. "
        "Automated replenishment triggers should be scheduled between day 28 and 35."
    )
    st.dataframe(status_summary, use_container_width=True)

# TAB 2: LTV DISTRIBUTION
with tab_ltv:
    st.markdown("### 💰 Customer Lifetime Value (LTV) Distribution (Question C3)")
    st.caption(
        "Parametric and non-parametric LTV distribution across RFM segments and gender to set acquisition cost ceilings."
    )

    ltv_df = run_query(
        """
        SELECT
            rfm_segment,
            gender,
            customer_count,
            total_revenue,
            avg_ltv,
            median_ltv,
            p25_ltv,
            p75_ltv,
            p90_ltv
        FROM gold.mart_rfm_segments
        ORDER BY total_revenue DESC
        """
    )

    col_ltv1, col_ltv2 = st.columns(2)

    with col_ltv1:
        fig_ltv_bar = px.bar(
            ltv_df,
            x="rfm_segment",
            y="avg_ltv",
            color="gender",
            barmode="group",
            title="Average LTV by Segment & Gender (IDR)",
            labels={"avg_ltv": "Average LTV (IDR)", "rfm_segment": "Segment"},
        )
        style_plot(fig_ltv_bar, height=380)
        st.plotly_chart(fig_ltv_bar, use_container_width=True)

    with col_ltv2:
        fig_median = px.bar(
            ltv_df,
            x="rfm_segment",
            y="median_ltv",
            color="gender",
            barmode="group",
            title="Median LTV (Non-Parametric) by Segment & Gender",
            labels={"median_ltv": "Median LTV (IDR)", "rfm_segment": "Segment"},
        )
        style_plot(fig_median, height=380)
        st.plotly_chart(fig_median, use_container_width=True)

    st.markdown("#### 📋 Comprehensive LTV Percentiles Table")
    st.dataframe(
        ltv_df.rename(
            columns={
                "rfm_segment": "Segment",
                "gender": "Gender",
                "customer_count": "Customers",
                "total_revenue": "Total Rev (IDR)",
                "avg_ltv": "Mean LTV (IDR)",
                "median_ltv": "Median LTV (IDR)",
                "p25_ltv": "25th Pct (IDR)",
                "p75_ltv": "75th Pct (IDR)",
                "p90_ltv": "90th Pct (IDR)",
            }
        ),
        use_container_width=True,
    )

# TAB 3: PROMO LIFT & RELIANCE
with tab_promo:
    st.markdown("### 🎟️ Promotional Lift & New Customer Reliance (Questions PR1 & PR2)")
    st.caption(
        "Evaluate order volume lift, net AOV, and discount depth across individual coupon codes. "
        "Determine whether acquisition relies excessively on promotional discounts compared to retention."
    )

    promo_df = run_query(
        """
        SELECT
            promo_code,
            customer_type,
            total_orders,
            distinct_customers,
            total_gross_revenue,
            total_promo_discount,
            total_net_revenue,
            avg_order_value_gross,
            avg_order_value_net,
            avg_discount_per_order,
            discount_depth_pct,
            promo_share_within_cohort_pct
        FROM gold.mart_promo_lift
        ORDER BY total_orders DESC
        """
    )

    col_pr1, col_pr2 = st.columns(2)

    with col_pr1:
        fig_promo_orders = px.bar(
            promo_df,
            x="promo_code",
            y="total_orders",
            color="customer_type",
            barmode="group",
            title="Order Volume by Promo Code & Customer Cohort (Question PR1)",
            labels={"total_orders": "Orders", "promo_code": "Promo Code"},
        )
        style_plot(fig_promo_orders, height=380)
        st.plotly_chart(fig_promo_orders, use_container_width=True)

    with col_pr2:
        fig_promo_depth = px.bar(
            promo_df[promo_df["promo_code"] != "NO_PROMO"],
            x="promo_code",
            y="discount_depth_pct",
            color="customer_type",
            barmode="group",
            title="Discount Depth % (Discount / Gross Value) (Question PR2)",
            labels={
                "discount_depth_pct": "Discount Depth (%)",
                "promo_code": "Promo Code",
            },
        )
        style_plot(fig_promo_depth, height=380)
        st.plotly_chart(fig_promo_depth, use_container_width=True)

    st.markdown("#### 📋 Promo Code Performance Scorecard")
    st.dataframe(
        promo_df.rename(
            columns={
                "promo_code": "Code",
                "customer_type": "Customer Type",
                "total_orders": "Orders",
                "distinct_customers": "Customers",
                "total_gross_revenue": "Gross Rev (IDR)",
                "total_promo_discount": "Total Discount (IDR)",
                "total_net_revenue": "Net Rev (IDR)",
                "avg_order_value_net": "Net AOV (IDR)",
                "avg_discount_per_order": "Avg Discount (IDR)",
                "discount_depth_pct": "Discount Depth %",
                "promo_share_within_cohort_pct": "Share in Cohort %",
            }
        ),
        use_container_width=True,
    )
