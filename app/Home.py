import pandas as pd
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

# Page configuration
st.set_page_config(
    page_title="Fashion Commerce Analytics Platform",
    page_icon="👗",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_custom_css()

# Sidebar
with st.sidebar:
    st.markdown("### 🛍️ Fashion Analytics")
    st.markdown(
        """
        **Platform Architecture:**
        - **Engine:** DuckDB OLAP
        - **Transformations:** dbt Core
        - **Orchestration:** Dagster
        - **Presentation:** Streamlit
        """
    )
    st.markdown("---")
    st.markdown(
        "💡 **Tip:** Use the pages menu above to explore department-specific deep dives."
    )

# Header
st.title("👗 Fashion Commerce Analytics Platform")
st.markdown(
    """
    <span class="badge badge-blue">Medallion Architecture</span>
    <span class="badge badge-green">DuckDB Engine</span>
    <span class="badge badge-purple">dbt Core (Gold Marts)</span>
    <span class="badge badge-amber">31 Dagster Assets Live</span>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    "Enterprise decision-support warehouse providing single-source-of-truth "
    "analytics across executive strategy, marketing funnels, pricing, merchandising, "
    "logistics, and financial operations."
)

st.markdown("---")

# Query high-level totals
try:
    totals_df = run_query(
        """
        SELECT
            sum(net_revenue) as total_net_revenue,
            sum(gross_revenue) as total_gross_revenue,
            sum(total_orders) as total_orders,
            sum(total_units_sold) as total_units_sold,
            sum(total_promo_cost) as total_promo_cost,
            sum(total_shipping_revenue) as total_shipping_revenue,
            round(sum(net_revenue) / nullif(sum(total_orders), 0), 2) as overall_aov
        FROM gold.mart_exec_kpis
        """
    )
    cust_df = run_query(
        """
        SELECT
            count(*) as total_customers,
            count(case when total_orders > 0 then 1 end) as purchasing_customers,
            round(100.0 * count(case when total_orders > 0 then 1 end) / count(*), 1) as customer_conversion_rate
        FROM gold.dim_customers
        """
    )
    prod_df = run_query(
        """
        SELECT
            count(*) as total_products,
            count(distinct master_category) as total_categories,
            count(distinct brand) as total_brands
        FROM gold.dim_products
        """
    )
    recent_kpi = run_query(
        """
        SELECT
            order_month,
            net_revenue,
            total_orders,
            active_customers,
            mom_net_revenue_growth_pct,
            yoy_net_revenue_growth_pct
        FROM gold.mart_exec_kpis
        ORDER BY order_month DESC
        LIMIT 1
        """
    )

    t = totals_df.iloc[0]
    c = cust_df.iloc[0]
    p = prod_df.iloc[0]
    r = recent_kpi.iloc[0] if not recent_kpi.empty else None

    # Top KPI Metrics Row
    kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5 = st.columns(5)
    render_kpi(
        kpi_col1,
        "Lifetime Net Revenue",
        format_currency(t["total_net_revenue"]),
        help_text="Gross merchandise value minus promotional discounts",
    )
    render_kpi(
        kpi_col2,
        "Total Orders",
        format_number(t["total_orders"]),
        help_text="Successfully paid bookings",
    )
    render_kpi(
        kpi_col3,
        "Overall AOV",
        format_currency(t["overall_aov"]),
        help_text="Average net revenue per order",
    )
    render_kpi(
        kpi_col4,
        "Total Customers",
        format_number(c["total_customers"]),
        f"{c['customer_conversion_rate']}% Active Buyers",
        delta_positive=True,
        help_text="Registered users in database",
    )
    render_kpi(
        kpi_col5,
        "Catalog Assortment",
        format_number(p["total_products"]),
        f"{p['total_categories']} Categories",
        delta_positive=True,
        help_text="Active catalog SKUs",
    )

    # Monthly Trend Overview Chart
    st.markdown("### 📈 Monthly Revenue & Order Velocity")
    trend_df = run_query(
        """
        SELECT
            order_month,
            net_revenue,
            gross_revenue,
            total_orders,
            active_customers,
            avg_order_value
        FROM gold.mart_exec_kpis
        ORDER BY order_month ASC
        """
    )
    trend_df["order_month"] = pd.to_datetime(trend_df["order_month"])

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=trend_df["order_month"],
            y=trend_df["net_revenue"],
            name="Net Revenue (IDR)",
            marker_color=PALETTE["primary"],
            opacity=0.85,
            yaxis="y1",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend_df["order_month"],
            y=trend_df["total_orders"],
            name="Total Orders",
            mode="lines+markers",
            line={"color": PALETTE["warning"], "width": 2.5},
            marker={"size": 4},
            yaxis="y2",
        )
    )

    fig.update_layout(
        yaxis={
            "title": "Net Revenue (IDR)",
            "side": "left",
            "showgrid": True,
            "gridcolor": "#F1F5F9",
        },
        yaxis2={
            "title": "Total Orders",
            "side": "right",
            "overlaying": "y",
            "showgrid": False,
        },
    )
    style_plot(
        fig, title="Monthly Net Revenue and Order Volume (2016 - 2022)", height=380
    )
    st.plotly_chart(fig, use_container_width=True)

    # Department Navigators
    st.markdown("### 🧭 Department Deep Dives & Business Questions")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.info(
            """
            **1. Executive & Strategy**
            - **Questions:** E1, E2, F3
            - **Metrics:** Revenue trends, MoM/YoY growth, AOV, new vs. returning revenue.
            """
        )
        st.info(
            """
            **2. Marketing & Conversion Funnels**
            - **Questions:** M1, M2, M3, M4, P1, P3
            - **Metrics:** Drop-offs, mobile vs web, search intent, cohort retention, RFM segments.
            """
        )
    with col_b:
        st.success(
            """
            **3. Merchandising & Inventory Planning**
            - **Questions:** I1, I2, I3, I4, PR3, PR4
            - **Metrics:** Top sellers, cart conversion, margin gaps, weather/holiday demand drivers.
            """
        )
        st.success(
            """
            **4. Logistics & Operations**
            - **Questions:** E3, L1, L2, L3
            - **Metrics:** Provincial revenue rank, shipping fee shares, delivery distances, carrier SLAs.
            """
        )
    with col_c:
        st.warning(
            """
            **5. Financial Gateways & Reliability**
            - **Questions:** F1, F2
            - **Metrics:** Payment failure rates, lost revenue, customer retry dynamics.
            """
        )
        st.warning(
            """
            **6. Customer CRM & Intelligence**
            - **Questions:** C1, C2, C3, PR1, PR2
            - **Metrics:** 180-day inactivity status, repeat purchase intervals, LTV percentiles, promo lift.
            """
        )
        st.error(
            """
            **7. Machine Learning Churn Risk**
            - **Model:** LightGBM Classifier Pipeline (ROC-AUC: 0.998)
            - **Features:** Risk tiering, audience export & real-time 'What-If' simulator.
            """
        )
        st.info(
            """
            **8. AI Data Copilot (Conversational BI)**
            - **Capability:** Natural language Text-to-SQL + DuckDB execution.
            - **Features:** Auto-visualization, read-only security & prompt library.
            """
        )

except Exception as e:  # noqa: BLE001
    st.error(f"Error loading dashboard data: {e}")
    st.info(
        "Ensure DuckDB database is populated by running: `uv run dbt build --profiles-dir .` inside `dbt_project/`"
    )
