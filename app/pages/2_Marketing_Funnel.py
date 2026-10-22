import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from utils import (
    apply_custom_css,
    format_currency,
    format_number,
    render_kpi,
    run_query,
    style_plot,
)

st.set_page_config(
    page_title="Marketing & Funnel | Fashion Analytics",
    page_icon="🎯",
    layout="wide",
)
apply_custom_css()

st.title("🎯 Marketing & User Journey Analytics")
st.markdown(
    "Decision support for channel budget allocation (Mobile vs. Web), "
    "conversion funnel optimization, search intent gaps, cohort retention, and RFM segmentation."
)

st.markdown(
    """
    <span class="badge badge-blue">Question M1 & P1: Conversion Funnel & Drop-Offs</span>
    <span class="badge badge-green">Question M2: Search Intent & Catalog Gaps</span>
    <span class="badge badge-purple">Question M3: Cohort Retention</span>
    <span class="badge badge-amber">Question M4: RFM Segments</span>
    """,
    unsafe_allow_html=True,
)
st.markdown("---")

tab_funnel, tab_search, tab_cohort, tab_rfm = st.tabs(
    [
        "🛒 Conversion Funnel & Cart Loss (M1, P1, P3)",
        "🔍 Search Intent & Catalog Gaps (M2)",
        "📅 Cohort Retention Heatmap (M3)",
        "💎 RFM Customer Segmentation (M4)",
    ]
)

# TAB 1: FUNNEL & CART LOSS
with tab_funnel:
    st.markdown("### 📱 Conversion Funnel by Traffic Source (Mobile vs. Web)")

    funnel_summary = run_query(
        """
        SELECT
            traffic_source,
            sum(total_sessions) as total_sessions,
            sum(sessions_with_home) as sessions_with_home,
            sum(sessions_with_search) as sessions_with_search,
            sum(sessions_with_item_detail) as sessions_with_detail,
            sum(sessions_with_add_to_cart) as sessions_with_cart,
            sum(sessions_with_booking) as sessions_with_booking,
            sum(converted_sessions) as converted_sessions,
            round(100.0 * sum(sessions_with_search) / nullif(sum(sessions_with_home), 0), 1) as home_to_search_pct,
            round(100.0 * sum(sessions_with_item_detail) / nullif(sum(sessions_with_search), 0), 1) as search_to_detail_pct,
            round(100.0 * sum(sessions_with_add_to_cart) / nullif(sum(sessions_with_item_detail), 0), 1) as detail_to_cart_pct,
            round(100.0 * sum(sessions_with_booking) / nullif(sum(sessions_with_add_to_cart), 0), 1) as cart_to_booking_pct,
            round(100.0 * sum(converted_sessions) / nullif(sum(total_sessions), 0), 2) as overall_conversion_pct
        FROM gold.mart_funnel_daily
        GROUP BY traffic_source
        """
    )

    cart_loss_summary = run_query(
        """
        SELECT
            traffic_source,
            sum(sessions_with_cart) as sessions_with_cart,
            sum(sessions_converted) as sessions_converted,
            sum(sessions_abandoned) as sessions_abandoned,
            round(100.0 * sum(sessions_abandoned) / nullif(sum(sessions_with_cart), 0), 1) as avg_abandonment_rate,
            round(sum(total_cart_value), 2) as total_cart_value,
            round(sum(converted_cart_value), 2) as converted_cart_value,
            round(sum(lost_revenue_abandoned_cart), 2) as lost_cart_revenue
        FROM gold.mart_cart_abandonment
        GROUP BY traffic_source
        """
    )

    f_col1, f_col2, f_col3, f_col4 = st.columns(4)
    tot_sess = funnel_summary["total_sessions"].sum()
    tot_conv = funnel_summary["converted_sessions"].sum()
    overall_conv = tot_conv / tot_sess * 100 if tot_sess else 0
    tot_lost_cart = cart_loss_summary["lost_cart_revenue"].sum()

    render_kpi(f_col1, "Total App Sessions", format_number(tot_sess))
    render_kpi(f_col2, "Successful Purchases", format_number(tot_conv))
    render_kpi(
        f_col3,
        "Overall Conversion Rate",
        f"{overall_conv:.2f}%",
        help_text="Sessions converted to paid bookings",
    )
    render_kpi(
        f_col4,
        "Lost Cart Revenue",
        format_currency(tot_lost_cart),
        delta_positive=False,
        help_text="Estimated cart value left unpaid (Question P3)",
    )

    # Funnel visualization per source
    col_chart1, col_chart2 = st.columns(2)

    stages = [
        "1. All Sessions",
        "2. Homepage",
        "3. Search",
        "4. Item Detail",
        "5. Add to Cart",
        "6. Paid Booking",
    ]

    for idx, source in enumerate(["MOBILE", "WEB"]):
        source_row = funnel_summary[funnel_summary["traffic_source"] == source]
        target_col = col_chart1 if idx == 0 else col_chart2

        if not source_row.empty:
            r = source_row.iloc[0]
            stage_values = [
                r["total_sessions"],
                r["sessions_with_home"],
                r["sessions_with_search"],
                r["sessions_with_detail"],
                r["sessions_with_cart"],
                r["converted_sessions"],
            ]
            fig_funnel = go.Figure(
                go.Funnel(
                    y=stages,
                    x=stage_values,
                    textinfo="value+percent previous",
                    marker={
                        "color": [
                            "#3B82F6",
                            "#60A5FA",
                            "#93C5FD",
                            "#F59E0B",
                            "#10B981",
                            "#059669",
                        ]
                    },
                )
            )
            style_plot(
                fig_funnel,
                title=f"{source} Conversion Funnel (Conversion: {r['overall_conversion_pct']}%)",
                height=380,
            )
            with target_col:
                st.plotly_chart(fig_funnel, use_container_width=True)

    st.markdown("#### 🛒 Cart Abandonment Recovery Breakdown (Question P3)")
    st.dataframe(
        cart_loss_summary.rename(
            columns={
                "traffic_source": "Channel",
                "sessions_with_cart": "Sessions with Cart",
                "sessions_converted": "Converted Carts",
                "sessions_abandoned": "Abandoned Carts",
                "avg_abandonment_rate": "Abandonment Rate %",
                "total_cart_value": "Total Cart Value (IDR)",
                "converted_cart_value": "Realized Revenue (IDR)",
                "lost_cart_revenue": "Lost Abandoned Revenue (IDR)",
            }
        ),
        use_container_width=True,
    )

# TAB 2: SEARCH INTENT & CATALOG GAPS
with tab_search:
    st.markdown("### 🔍 Search Query Intent & Catalog Assortment Gaps (Question M2)")
    st.caption(
        "Detect what customers are searching for, and identify high-demand queries with "
        "0 purchases to uncover catalog assortment opportunities."
    )

    search_df = run_query(
        """
        SELECT
            search_keyword,
            total_searches,
            distinct_sessions,
            sessions_with_cart_add,
            converted_sessions,
            cart_add_rate_pct,
            conversion_rate_pct,
            is_zero_conversion,
            intent_classification
        FROM gold.mart_search_intent
        ORDER BY distinct_sessions DESC
        """
    )

    c_s1, c_s2 = st.columns([1, 1])

    with c_s1:
        # Chart top search queries
        fig_searches = px.bar(
            search_df.head(12),
            x="distinct_sessions",
            y="search_keyword",
            orientation="h",
            color="conversion_rate_pct",
            color_continuous_scale="Blues",
            title="Top Searches by Session Volume (Color = Conversion %)",
            labels={
                "distinct_sessions": "Distinct Sessions",
                "search_keyword": "Search Query",
                "conversion_rate_pct": "Conversion %",
            },
        )
        fig_searches.update_layout(yaxis={"autorange": "reversed"})
        style_plot(fig_searches, height=400)
        st.plotly_chart(fig_searches, use_container_width=True)

    with c_s2:
        # Scatter of Intent
        fig_intent = px.scatter(
            search_df,
            x="cart_add_rate_pct",
            y="conversion_rate_pct",
            size="distinct_sessions",
            color="intent_classification",
            hover_name="search_keyword",
            title="Search Intent Map: Cart Add Rate vs. Conversion Rate",
            labels={
                "cart_add_rate_pct": "Cart Add Rate (%)",
                "conversion_rate_pct": "Conversion Rate (%)",
            },
        )
        style_plot(fig_intent, height=400)
        st.plotly_chart(fig_intent, use_container_width=True)

    st.markdown("#### 📋 Catalog Assortment Gaps (Zero Conversion Queries)")
    zero_conv_df = search_df[search_df["is_zero_conversion"]]
    if not zero_conv_df.empty:
        st.warning(
            f"Found **{len(zero_conv_df)} queries** with user search demand but 0 purchase conversions. "
            "These represent catalog inventory gaps or missing product stock."
        )
        st.dataframe(
            zero_conv_df[
                [
                    "search_keyword",
                    "total_searches",
                    "distinct_sessions",
                    "sessions_with_cart_add",
                    "cart_add_rate_pct",
                    "intent_classification",
                ]
            ],
            use_container_width=True,
        )
    else:
        st.success("No high-volume zero-conversion queries detected.")

# TAB 3: COHORT RETENTION
with tab_cohort:
    st.markdown("### 📅 Monthly Customer Cohort Retention Heatmap (Question M3)")
    st.caption(
        "Measures how first-purchase customer cohorts retain over 1, 3, 6, and 12+ months. "
        "Enables lifecycle marketing and retention campaign ROI tracking."
    )

    cohort_raw = run_query(
        """
        SELECT
            cohort_month,
            cohort_size,
            month_number,
            active_customers,
            retention_rate_pct,
            cumulative_revenue_per_customer
        FROM gold.mart_cohort_retention
        WHERE month_number <= 12
        ORDER BY cohort_month ASC, month_number ASC
        """
    )

    if not cohort_raw.empty:
        cohort_raw["cohort_str"] = pd.to_datetime(
            cohort_raw["cohort_month"]
        ).dt.strftime("%Y-%m")
        # Filter for cohorts with multiple months
        recent_cohorts = cohort_raw["cohort_str"].unique()[-18:]
        cohort_filtered = cohort_raw[cohort_raw["cohort_str"].isin(recent_cohorts)]

        # Pivot for heatmap
        pivot_retention = cohort_filtered.pivot(
            index="cohort_str", columns="month_number", values="retention_rate_pct"
        )

        fig_cohort = px.imshow(
            pivot_retention,
            labels={
                "x": "Month After First Purchase",
                "y": "Cohort Month",
                "color": "Retention %",
            },
            x=[f"M+{col}" for col in pivot_retention.columns],
            y=pivot_retention.index,
            color_continuous_scale="Viridis",
            text_auto=".1f",
            aspect="auto",
        )
        style_plot(
            fig_cohort,
            title="Customer Cohort Retention Rate (%) Across Months 0 to 12",
            height=500,
        )
        st.plotly_chart(fig_cohort, use_container_width=True)

        st.markdown("#### 💰 Cumulative Revenue per Customer by Cohort")
        pivot_cum_rev = cohort_filtered.pivot(
            index="cohort_str",
            columns="month_number",
            values="cumulative_revenue_per_customer",
        )
        st.dataframe(
            pivot_cum_rev.style.format("Rp {:,.0f}", na_rep="-"),
            use_container_width=True,
        )

# TAB 4: RFM SEGMENTS
with tab_rfm:
    st.markdown(
        "### 💎 RFM Customer Segmentation & LTV Distribution (Question M4 & C3)"
    )
    st.caption(
        "Quintile-based Recency, Frequency, Monetary segmentation supporting targeted CRM campaigns."
    )

    rfm_df = run_query(
        """
        SELECT
            rfm_segment,
            sum(customer_count) as total_customers,
            sum(total_revenue) as total_revenue,
            round(avg(avg_recency_days), 1) as avg_recency_days,
            round(avg(avg_order_frequency), 1) as avg_orders,
            round(avg(avg_ltv), 2) as avg_ltv,
            round(avg(median_ltv), 2) as median_ltv,
            round(avg(p25_ltv), 2) as p25_ltv,
            round(avg(p75_ltv), 2) as p75_ltv,
            round(avg(p90_ltv), 2) as p90_ltv
        FROM gold.mart_rfm_segments
        GROUP BY rfm_segment
        ORDER BY total_revenue DESC
        """
    )

    tot_rfm_cust = rfm_df["total_customers"].sum()
    tot_rfm_rev = rfm_df["total_revenue"].sum()
    rfm_df["cust_pct"] = (rfm_df["total_customers"] / tot_rfm_cust) * 100
    rfm_df["rev_pct"] = (rfm_df["total_revenue"] / tot_rfm_rev) * 100

    col_rfm1, col_rfm2 = st.columns(2)

    with col_rfm1:
        fig_rfm_rev = px.bar(
            rfm_df,
            x="rfm_segment",
            y="rev_pct",
            color="rfm_segment",
            title="Revenue Contribution % by RFM Segment",
            text=rfm_df["rev_pct"].apply(lambda x: f"{x:.1f}%"),
            labels={"rev_pct": "Revenue Share (%)", "rfm_segment": "Segment"},
        )
        fig_rfm_rev.update_traces(textposition="outside")
        style_plot(fig_rfm_rev, height=380)
        st.plotly_chart(fig_rfm_rev, use_container_width=True)

    with col_rfm2:
        fig_rfm_cust = px.pie(
            rfm_df,
            values="total_customers",
            names="rfm_segment",
            title="Customer Base Distribution by Segment",
            hole=0.45,
        )
        fig_rfm_cust.update_traces(textposition="inside", textinfo="percent+label")
        style_plot(fig_rfm_cust, height=380)
        st.plotly_chart(fig_rfm_cust, use_container_width=True)

    st.markdown("#### 📊 Segment LTV & Recency Profile Table")
    st.dataframe(
        rfm_df[
            [
                "rfm_segment",
                "total_customers",
                "cust_pct",
                "total_revenue",
                "rev_pct",
                "avg_orders",
                "avg_recency_days",
                "avg_ltv",
                "median_ltv",
                "p90_ltv",
            ]
        ].rename(
            columns={
                "rfm_segment": "RFM Segment",
                "total_customers": "Customers",
                "cust_pct": "Customer %",
                "total_revenue": "Total Revenue (IDR)",
                "rev_pct": "Revenue %",
                "avg_orders": "Avg Orders",
                "avg_recency_days": "Avg Recency (Days)",
                "avg_ltv": "Avg LTV (IDR)",
                "median_ltv": "Median LTV (IDR)",
                "p90_ltv": "P90 LTV (IDR)",
            }
        ),
        use_container_width=True,
    )
