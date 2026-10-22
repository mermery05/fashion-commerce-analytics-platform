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
    page_title="Executive KPIs | Fashion Analytics",
    page_icon="📊",
    layout="wide",
)
apply_custom_css()

st.title("📊 Executive & Strategy Performance")
st.markdown(
    "Decision support for quarterly board targets, revenue trajectory, "
    "AOV expansion, and customer acquisition vs. retention investment."
)

st.markdown(
    """
    <span class="badge badge-blue">Question E1: Revenue, Orders, AOV & Active Customers</span>
    <span class="badge badge-green">Question E2: New vs. Returning Revenue Share</span>
    <span class="badge badge-purple">Question F3: Net Revenue, Promo Cost & Shipping</span>
    """,
    unsafe_allow_html=True,
)
st.markdown("---")

# Load executive KPIs
df = run_query(
    """
    SELECT
        order_month,
        total_orders,
        total_units_sold,
        active_customers,
        gross_revenue,
        total_promo_cost,
        net_revenue,
        total_shipping_revenue,
        total_collected_revenue,
        avg_order_value,
        new_customer_orders,
        returning_customer_orders,
        new_customer_net_revenue,
        returning_customer_net_revenue,
        new_customer_rev_share_pct,
        returning_customer_rev_share_pct,
        mom_net_revenue_growth_pct,
        yoy_net_revenue_growth_pct,
        mom_orders_growth_pct,
        yoy_orders_growth_pct,
        mom_active_customers_growth_pct
    FROM gold.mart_exec_kpis
    ORDER BY order_month ASC
    """
)
df["order_month"] = pd.to_datetime(df["order_month"])
df["year"] = df["order_month"].dt.year

# Year filter
years = sorted(df["year"].unique())
selected_years = st.sidebar.multiselect(
    "Filter Years", options=years, default=years, help="Filter data by calendar year"
)

filtered_df = df[df["year"].isin(selected_years)] if selected_years else df

if filtered_df.empty:
    st.warning("No data found for the selected years.")
    st.stop()

# Aggregate summary metrics
total_net_rev = filtered_df["net_revenue"].sum()
total_gross_rev = filtered_df["gross_revenue"].sum()
total_promo = filtered_df["total_promo_cost"].sum()
total_orders = filtered_df["total_orders"].sum()
overall_aov = total_net_rev / total_orders if total_orders else 0
total_active_cust = filtered_df["active_customers"].sum()

latest_row = filtered_df.iloc[-1]
mom_rev_growth = latest_row["mom_net_revenue_growth_pct"]
yoy_rev_growth = latest_row["yoy_net_revenue_growth_pct"]

# Top Row KPI Cards
c1, c2, c3, c4, c5 = st.columns(5)
render_kpi(
    c1,
    "Net Revenue",
    format_currency(total_net_rev),
    f"{mom_rev_growth:+.1f}% MoM" if pd.notna(mom_rev_growth) else None,
    delta_positive=(mom_rev_growth >= 0) if pd.notna(mom_rev_growth) else True,
    help_text="Gross revenue minus discounts for selected period",
)
render_kpi(
    c2,
    "Total Orders",
    format_number(total_orders),
    f"{latest_row['mom_orders_growth_pct']:+.1f}% MoM"
    if pd.notna(latest_row["mom_orders_growth_pct"])
    else None,
    delta_positive=(latest_row["mom_orders_growth_pct"] >= 0)
    if pd.notna(latest_row["mom_orders_growth_pct"])
    else True,
    help_text="Successfully paid bookings",
)
render_kpi(
    c3,
    "Average Order Value",
    format_currency(overall_aov),
    help_text="Net revenue per order",
)
render_kpi(
    c4,
    "Promo Discount Cost",
    format_currency(total_promo),
    f"{total_promo / total_gross_rev * 100:.1f}% of Gross" if total_gross_rev else None,
    delta_positive=False,
    help_text="Total promotional subsidies applied",
)
render_kpi(
    c5,
    "Shipping Collected",
    format_currency(filtered_df["total_shipping_revenue"].sum()),
    help_text="Shipping fees collected from customers",
)

st.markdown("### 📈 Revenue & Growth Trajectory (Questions E1 & F3)")
tab1, tab2, tab3 = st.tabs(
    [
        "Revenue & AOV Trend",
        "MoM / YoY Growth Rates",
        "Gross vs. Net vs. Shipping Breakdown",
    ]
)

with tab1:
    fig1 = go.Figure()
    fig1.add_trace(
        go.Bar(
            x=filtered_df["order_month"],
            y=filtered_df["net_revenue"],
            name="Net Revenue",
            marker_color=PALETTE["primary"],
            yaxis="y1",
        )
    )
    fig1.add_trace(
        go.Scatter(
            x=filtered_df["order_month"],
            y=filtered_df["avg_order_value"],
            name="AOV (IDR)",
            mode="lines+markers",
            line={"color": PALETTE["warning"], "width": 2.5},
            yaxis="y2",
        )
    )
    fig1.update_layout(
        yaxis={"title": "Net Revenue (IDR)", "side": "left", "showgrid": True},
        yaxis2={
            "title": "AOV (IDR)",
            "side": "right",
            "overlaying": "y",
            "showgrid": False,
        },
    )
    style_plot(fig1, title="Monthly Net Revenue and Average Order Value")
    st.plotly_chart(fig1, use_container_width=True)

with tab2:
    fig2 = go.Figure()
    fig2.add_trace(
        go.Bar(
            x=filtered_df["order_month"],
            y=filtered_df["mom_net_revenue_growth_pct"],
            name="MoM Growth %",
            marker_color=[
                PALETTE["success"] if val >= 0 else PALETTE["danger"]
                for val in filtered_df["mom_net_revenue_growth_pct"].fillna(0)
            ],
        )
    )
    fig2.add_trace(
        go.Scatter(
            x=filtered_df["order_month"],
            y=filtered_df["yoy_net_revenue_growth_pct"],
            name="YoY Growth %",
            mode="lines",
            line={"color": PALETTE["secondary"], "width": 2, "dash": "dash"},
        )
    )
    fig2.update_layout(yaxis={"title": "Growth Percentage (%)", "showgrid": True})
    style_plot(fig2, title="Month-over-Month & Year-over-Year Revenue Growth %")
    st.plotly_chart(fig2, use_container_width=True)

with tab3:
    fig3 = go.Figure()
    fig3.add_trace(
        go.Scatter(
            x=filtered_df["order_month"],
            y=filtered_df["gross_revenue"],
            name="Gross Revenue",
            mode="lines",
            line={"color": PALETTE["neutral"], "width": 2},
        )
    )
    fig3.add_trace(
        go.Scatter(
            x=filtered_df["order_month"],
            y=filtered_df["net_revenue"],
            name="Net Revenue",
            mode="lines",
            fill="tonexty",
            line={"color": PALETTE["primary"], "width": 2},
        )
    )
    fig3.add_trace(
        go.Bar(
            x=filtered_df["order_month"],
            y=filtered_df["total_promo_cost"],
            name="Promo Cost",
            marker_color=PALETTE["danger"],
            opacity=0.7,
        )
    )
    fig3.add_trace(
        go.Bar(
            x=filtered_df["order_month"],
            y=filtered_df["total_shipping_revenue"],
            name="Shipping Revenue",
            marker_color=PALETTE["accent2"],
            opacity=0.7,
        )
    )
    fig3.update_layout(barmode="stack", yaxis={"title": "IDR", "showgrid": True})
    style_plot(
        fig3,
        title="Financial Close: Gross Revenue, Net Revenue, Promo Subsidies & Shipping",
    )
    st.plotly_chart(fig3, use_container_width=True)

st.markdown("---")

st.markdown("### 👥 New vs. Returning Customer Revenue Share (Question E2)")
st.caption(
    "Strategic decision support: Balance acquisition budget against customer retention investment."
)

col_rev1, col_rev2 = st.columns([2, 1])

with col_rev1:
    fig_share = go.Figure()
    fig_share.add_trace(
        go.Scatter(
            x=filtered_df["order_month"],
            y=filtered_df["new_customer_rev_share_pct"],
            name="New Customer Revenue %",
            stackgroup="one",
            mode="none",
            fillcolor="#93C5FD",
        )
    )
    fig_share.add_trace(
        go.Scatter(
            x=filtered_df["order_month"],
            y=filtered_df["returning_customer_rev_share_pct"],
            name="Returning Customer Revenue %",
            stackgroup="one",
            mode="none",
            fillcolor="#3B82F6",
        )
    )
    fig_share.update_layout(
        yaxis={"title": "Revenue Share (%)", "range": [0, 100], "showgrid": True}
    )
    style_plot(
        fig_share, title="Monthly Revenue Contribution: New vs. Returning Customers"
    )
    st.plotly_chart(fig_share, use_container_width=True)

with col_rev2:
    total_new_rev = filtered_df["new_customer_net_revenue"].sum()
    total_ret_rev = filtered_df["returning_customer_net_revenue"].sum()
    fig_pie = px.pie(
        values=[total_new_rev, total_ret_rev],
        names=["New Customers", "Returning Customers"],
        color_discrete_sequence=["#93C5FD", "#3B82F6"],
        hole=0.55,
    )
    fig_pie.update_traces(textposition="inside", textinfo="percent+label")
    style_plot(fig_pie, title="Cumulative Split for Selected Period", height=380)
    st.plotly_chart(fig_pie, use_container_width=True)

# Historical monthly table
with st.expander("📋 View Detailed Monthly Executive Performance Table"):
    display_df = filtered_df.copy()
    display_df["order_month"] = display_df["order_month"].dt.strftime("%Y-%m")
    display_cols = [
        "order_month",
        "total_orders",
        "active_customers",
        "gross_revenue",
        "total_promo_cost",
        "net_revenue",
        "total_shipping_revenue",
        "avg_order_value",
        "new_customer_rev_share_pct",
        "mom_net_revenue_growth_pct",
        "yoy_net_revenue_growth_pct",
    ]
    st.dataframe(
        display_df[display_cols].rename(
            columns={
                "order_month": "Month",
                "total_orders": "Orders",
                "active_customers": "Active Customers",
                "gross_revenue": "Gross Rev (IDR)",
                "total_promo_cost": "Promo Cost (IDR)",
                "net_revenue": "Net Rev (IDR)",
                "total_shipping_revenue": "Shipping (IDR)",
                "avg_order_value": "AOV (IDR)",
                "new_customer_rev_share_pct": "New Rev %",
                "mom_net_revenue_growth_pct": "MoM Growth %",
                "yoy_net_revenue_growth_pct": "YoY Growth %",
            }
        ),
        use_container_width=True,
    )
