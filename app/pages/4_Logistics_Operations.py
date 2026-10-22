import plotly.express as px
import streamlit as st
from utils import (
    CHART_COLORS,
    apply_custom_css,
    format_currency,
    render_kpi,
    run_query,
    style_plot,
)

st.set_page_config(
    page_title="Logistics & Operations | Fashion Analytics",
    page_icon="🚚",
    layout="wide",
)
apply_custom_css()

st.title("🚚 Logistics, Geography & Fulfillment SLAs")
st.markdown(
    "Decision support for warehouse placement, carrier SLA adherence, shipping pricing tiers, "
    "and provincial market prioritization."
)

st.markdown(
    """
    <span class="badge badge-blue">Question E3: Regional Revenue Drivers</span>
    <span class="badge badge-green">Question L1: Destination Shipping Fees & Order Share %</span>
    <span class="badge badge-purple">Question L2: Promised Delivery SLA Windows</span>
    <span class="badge badge-amber">Question L3: Geodesic Travel Distances (Haversine km)</span>
    """,
    unsafe_allow_html=True,
)
st.markdown("---")

# Query provincial performance
geo_df = run_query(
    """
    SELECT
        home_location as province,
        sum(total_orders) as total_orders,
        sum(active_customers) as active_customers,
        round(sum(gross_revenue), 2) as gross_revenue,
        round(sum(net_revenue), 2) as net_revenue,
        round(sum(total_shipment_fees), 2) as total_shipment_fees,
        round(avg(avg_shipment_fee), 2) as avg_shipment_fee,
        round(100.0 * sum(total_shipment_fees) / nullif(sum(gross_revenue), 0), 2) as shipping_pct_of_order_value,
        round(avg(avg_delivery_distance_km), 1) as avg_delivery_distance_km
    FROM gold.mart_geo_performance
    GROUP BY home_location
    ORDER BY net_revenue DESC
    """
)

# Query logistics SLAs & distance distributions
sla_df = run_query(
    """
    SELECT
        sla_window_tier,
        count(*) as order_count,
        round(avg(shipment_fee), 2) as avg_shipment_fee,
        round(avg(delivery_distance_km), 1) as avg_distance_km
    FROM gold.mart_logistics
    GROUP BY sla_window_tier
    ORDER BY order_count DESC
    """
)

dist_df = run_query(
    """
    SELECT
        distance_tier,
        count(*) as order_count,
        round(avg(delivery_distance_km), 1) as avg_km,
        round(avg(shipment_fee), 2) as avg_shipping_fee,
        round(avg(shipping_pct_of_order_value), 2) as avg_shipping_pct
    FROM gold.mart_logistics
    GROUP BY distance_tier
    ORDER BY order_count DESC
    """
)

# KPI Cards
k1, k2, k3, k4 = st.columns(4)
total_orders = geo_df["total_orders"].sum()
total_ship_fees = geo_df["total_shipment_fees"].sum()
overall_ship_pct = total_ship_fees / geo_df["gross_revenue"].sum() * 100
avg_distance = dist_df["avg_km"].mean()

render_kpi(k1, "Total Shipping Collected", format_currency(total_ship_fees))
render_kpi(
    k2,
    "Avg Shipping % of Order Value",
    f"{overall_ship_pct:.2f}%",
    help_text="Question L1",
)
render_kpi(
    k3,
    "Avg Delivery Distance",
    f"{avg_distance:.1f} km",
    help_text="Haversine geodesic distance (Question L3)",
)
render_kpi(
    k4,
    "Provinces Served",
    f"{len(geo_df)} Provinces",
    help_text="Indonesia nationwide coverage (Question E3)",
)

st.markdown("### 🗺️ Provincial Revenue Ranking & Shipping Burden (Questions E3 & L1)")
col_geo1, col_geo2 = st.columns([3, 2])

with col_geo1:
    fig_prov = px.bar(
        geo_df.head(15),
        x="net_revenue",
        y="province",
        orientation="h",
        color="shipping_pct_of_order_value",
        color_continuous_scale="Viridis",
        title="Top 15 Provinces by Net Revenue (Color = Shipping % of Order Value)",
        labels={
            "net_revenue": "Net Revenue (IDR)",
            "province": "Province",
            "shipping_pct_of_order_value": "Shipping %",
        },
    )
    fig_prov.update_layout(yaxis={"autorange": "reversed"})
    style_plot(fig_prov, height=450)
    st.plotly_chart(fig_prov, use_container_width=True)

with col_geo2:
    fig_scatter = px.scatter(
        geo_df,
        x="avg_delivery_distance_km",
        y="shipping_pct_of_order_value",
        size="total_orders",
        color="net_revenue",
        hover_name="province",
        title="Delivery Distance vs. Shipping Burden %",
        labels={
            "avg_delivery_distance_km": "Avg Distance (km)",
            "shipping_pct_of_order_value": "Shipping % of Value",
        },
    )
    style_plot(fig_scatter, height=450)
    st.plotly_chart(fig_scatter, use_container_width=True)

st.markdown("---")

st.markdown("### 📦 Delivery SLAs & Travel Distance Distribution (Questions L2 & L3)")
col_sla, col_dist = st.columns(2)

with col_sla:
    fig_sla = px.pie(
        sla_df,
        values="order_count",
        names="sla_window_tier",
        title="Promised Delivery Window SLA Tiers (Question L2)",
        hole=0.45,
        color="sla_window_tier",
        color_discrete_sequence=CHART_COLORS,
    )
    fig_sla.update_traces(textposition="inside", textinfo="percent+label")
    style_plot(fig_sla, height=360)
    st.plotly_chart(fig_sla, use_container_width=True)

with col_dist:
    fig_dist = px.bar(
        dist_df,
        x="distance_tier",
        y="order_count",
        color="distance_tier",
        title="Order Volume by Travel Distance Tier (Question L3)",
        labels={"distance_tier": "Distance Bracket", "order_count": "Orders"},
    )
    style_plot(fig_dist, height=360)
    st.plotly_chart(fig_dist, use_container_width=True)

with st.expander("📋 View Complete 33-Province Logistics & Revenue Table"):
    st.dataframe(
        geo_df.rename(
            columns={
                "province": "Province",
                "total_orders": "Orders",
                "active_customers": "Customers",
                "gross_revenue": "Gross Rev (IDR)",
                "net_revenue": "Net Rev (IDR)",
                "total_shipment_fees": "Shipping Fees (IDR)",
                "avg_shipment_fee": "Avg Ship Fee (IDR)",
                "shipping_pct_of_order_value": "Ship % of Value",
                "avg_delivery_distance_km": "Avg Distance (km)",
            }
        ),
        use_container_width=True,
    )
