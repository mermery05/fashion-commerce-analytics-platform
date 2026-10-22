import plotly.express as px
import streamlit as st
from utils import (
    PALETTE,
    apply_custom_css,
    run_query,
    style_plot,
)

st.set_page_config(
    page_title="Merchandising & Demand | Fashion Analytics",
    page_icon="🧥",
    layout="wide",
)
apply_custom_css()

st.title("🧥 Merchandising, Pricing & Demand Drivers")
st.markdown(
    "Decision support for catalog assortment planning, price-band elasticity, "
    "margin protection (gross-to-net gaps), and weather/holiday demand forecasting."
)

st.markdown(
    """
    <span class="badge badge-blue">Question I1, I2, I4: Product Velocity & Cart-to-Buy Actions</span>
    <span class="badge badge-green">Question PR3 & PR4: Category Price Bands & Margin Gaps</span>
    <span class="badge badge-purple">Question I3: Weather & Holiday Demand Drivers</span>
    """,
    unsafe_allow_html=True,
)
st.markdown("---")

tab_prod, tab_price, tab_weather = st.tabs(
    [
        "🏷️ Product Velocity & Catalog Actions (I1, I2, I4)",
        "💵 Category Price Bands & Promo Gaps (PR3, PR4)",
        "⛅ Weather & Holiday Demand Sensitivity (I3)",
    ]
)

# TAB 1: PRODUCT PERFORMANCE
with tab_prod:
    st.markdown(
        "### 🏆 Top Sellers, Velocity Tiers & Merchandising Actions (Questions I1, I2, I4)"
    )
    st.caption(
        "Identify winning SKUs and flag items with high cart intent but low purchase completion for repricing or creative updates."
    )

    # KPI summary
    tier_summary = run_query(
        """
        SELECT
            velocity_tier,
            count(*) as product_count,
            sum(total_units_sold) as total_units,
            sum(total_revenue) as total_revenue
        FROM gold.dim_products
        GROUP BY velocity_tier
        ORDER BY total_revenue DESC
        """
    )

    action_summary = run_query(
        """
        SELECT
            merchandising_action,
            count(*) as product_count,
            sum(cart_add_events) as total_cart_adds,
            sum(total_units_sold) as total_units_sold,
            sum(gross_revenue) as total_revenue
        FROM gold.mart_product_performance
        GROUP BY merchandising_action
        ORDER BY total_revenue DESC
        """
    )

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        fig_tiers = px.pie(
            tier_summary,
            values="product_count",
            names="velocity_tier",
            title="Catalog Assortment by Sales Velocity Tier",
            hole=0.45,
            color="velocity_tier",
            color_discrete_map={
                "Top Seller": PALETTE["success"],
                "Steady Mover": PALETTE["primary"],
                "Slow Mover": PALETTE["warning"],
                "Zero Sales": PALETTE["neutral"],
            },
        )
        fig_tiers.update_traces(textposition="inside", textinfo="percent+label")
        style_plot(fig_tiers, height=350)
        st.plotly_chart(fig_tiers, use_container_width=True)

    with col_t2:
        fig_actions = px.bar(
            action_summary,
            x="merchandising_action",
            y="product_count",
            color="merchandising_action",
            title="Catalog Merchandising Action Segments",
            labels={
                "product_count": "SKU Count",
                "merchandising_action": "Action Flag",
            },
        )
        style_plot(fig_actions, height=350)
        st.plotly_chart(fig_actions, use_container_width=True)

    st.markdown(
        "#### 🚨 Action Item: High Cart Intent / Zero Purchase Products (Question I2)"
    )
    high_cart_zero_buy = run_query(
        """
        SELECT
            product_id,
            product_display_name,
            master_category,
            article_type,
            base_colour,
            cart_add_events,
            distinct_sessions_carted,
            total_orders,
            merchandising_action
        FROM gold.mart_product_performance
        WHERE merchandising_action = 'High Cart / Zero Sales (Reprice/Photograph)'
        ORDER BY cart_add_events DESC
        LIMIT 15
        """
    )
    if not high_cart_zero_buy.empty:
        st.info(
            "These products attract customer interest (added to cart) but drop off before checkout. Recommended action: test price discounts or update hero photography."
        )
        st.dataframe(high_cart_zero_buy, use_container_width=True)
    else:
        st.success("No critical high-cart zero-purchase anomalies detected.")

    st.markdown("#### 🥇 Top 15 Best Selling Products (Question I1)")
    top_products = run_query(
        """
        SELECT
            product_id,
            product_display_name,
            master_category,
            article_type,
            brand,
            base_colour,
            total_orders,
            total_units_sold,
            total_revenue,
            avg_selling_price,
            velocity_tier
        FROM gold.dim_products
        ORDER BY total_revenue DESC
        LIMIT 15
        """
    )
    st.dataframe(
        top_products.rename(
            columns={
                "product_display_name": "Product Name",
                "master_category": "Category",
                "article_type": "Article",
                "brand": "Brand",
                "base_colour": "Colour",
                "total_orders": "Orders",
                "total_units_sold": "Units Sold",
                "total_revenue": "Total Revenue (IDR)",
                "avg_selling_price": "Avg Price (IDR)",
                "velocity_tier": "Velocity",
            }
        ),
        use_container_width=True,
    )

# TAB 2: PRICING & MARGIN GAP
with tab_price:
    st.markdown(
        "### 💵 Category Price Bands & Gross-to-Net Margin Gaps (Questions PR3 & PR4)"
    )
    st.caption(
        "Evaluate how promotional discounts erode margins across product categories and inspect unit volume sensitivity by price band."
    )

    pricing_df = run_query(
        """
        SELECT
            master_category,
            price_band,
            sum(total_order_lines) as total_order_lines,
            sum(total_units_sold) as total_units_sold,
            round(sum(gross_revenue), 2) as gross_revenue,
            round(sum(total_allocated_promo_cost), 2) as promo_cost,
            round(sum(net_revenue), 2) as net_revenue,
            round(100.0 * sum(total_allocated_promo_cost) / nullif(sum(gross_revenue), 0), 2) as margin_gap_pct,
            round(avg(avg_item_price), 2) as avg_price
        FROM gold.mart_pricing_by_category
        GROUP BY master_category, price_band
        ORDER BY master_category, price_band
        """
    )

    col_pr1, col_pr2 = st.columns(2)

    with col_pr1:
        # Category Margin Gap
        cat_gap = (
            pricing_df.groupby("master_category")[
                ["gross_revenue", "promo_cost", "net_revenue"]
            ]
            .sum()
            .reset_index()
        )
        cat_gap["margin_gap_pct"] = (
            cat_gap["promo_cost"] / cat_gap["gross_revenue"]
        ) * 100
        cat_gap = cat_gap.sort_values("margin_gap_pct", ascending=False)

        fig_gap = px.bar(
            cat_gap,
            x="master_category",
            y="margin_gap_pct",
            color="margin_gap_pct",
            color_continuous_scale="Reds",
            title="Gross-to-Net Revenue Gap % by Master Category (Question PR3)",
            labels={
                "margin_gap_pct": "Promo Cost % of Gross Rev",
                "master_category": "Category",
            },
            text=cat_gap["margin_gap_pct"].apply(lambda x: f"{x:.2f}%"),
        )
        fig_gap.update_traces(textposition="outside")
        style_plot(fig_gap, height=380)
        st.plotly_chart(fig_gap, use_container_width=True)

    with col_pr2:
        # Price Band Volume
        band_summary = (
            pricing_df.groupby("price_band")[["total_units_sold", "net_revenue"]]
            .sum()
            .reset_index()
        )
        fig_band = px.bar(
            band_summary,
            x="price_band",
            y="total_units_sold",
            color="price_band",
            title="Units Sold by Price Band (Question PR4)",
            labels={"total_units_sold": "Units Sold", "price_band": "Price Band"},
        )
        style_plot(fig_band, height=380)
        st.plotly_chart(fig_band, use_container_width=True)

    st.markdown("#### 📋 Category Pricing Matrix")
    st.dataframe(pricing_df, use_container_width=True)

# TAB 3: WEATHER & HOLIDAYS
with tab_weather:
    st.markdown("### ⛅ Local Weather & Holiday Demand Sensitivity (Question I3)")
    st.caption(
        "Correlates daily category sales with Open-Meteo local weather archives (temperature, rainfall) and calendar holidays across Indonesian provinces."
    )

    weather_summary = run_query(
        """
        SELECT
            weather_condition,
            count(*) as day_location_records,
            sum(total_orders) as total_orders,
            sum(total_units_sold) as total_units_sold,
            round(sum(daily_net_revenue), 2) as total_net_revenue,
            round(sum(daily_net_revenue) / nullif(sum(total_orders), 0), 2) as aov,
            round(avg(temp_mean_c), 1) as avg_temp_c,
            round(avg(precip_mm), 1) as avg_precip_mm
        FROM gold.mart_demand_drivers
        WHERE weather_condition != 'Unknown'
        GROUP BY weather_condition
        ORDER BY total_net_revenue DESC
        """
    )

    holiday_summary = run_query(
        """
        SELECT
            case when is_holiday then 'National Holiday' else 'Standard Day' end as day_type,
            case when is_weekend then 'Weekend' else 'Weekday' end as week_type,
            count(distinct order_date) as distinct_days,
            sum(total_orders) as total_orders,
            round(sum(daily_net_revenue), 2) as total_net_revenue,
            round(sum(daily_net_revenue) / nullif(count(distinct order_date), 0), 2) as avg_daily_revenue
        FROM gold.mart_demand_drivers
        GROUP BY 1, 2
        ORDER BY avg_daily_revenue DESC
        """
    )

    col_w1, col_w2 = st.columns(2)

    with col_w1:
        fig_weather = px.bar(
            weather_summary,
            x="weather_condition",
            y="total_net_revenue",
            color="weather_condition",
            title="Net Revenue by Local Weather Condition",
            labels={
                "weather_condition": "Condition",
                "total_net_revenue": "Net Revenue (IDR)",
            },
        )
        style_plot(fig_weather, height=360)
        st.plotly_chart(fig_weather, use_container_width=True)

    with col_w2:
        fig_holiday = px.bar(
            holiday_summary,
            x="day_type",
            y="avg_daily_revenue",
            color="week_type",
            barmode="group",
            title="Average Daily Revenue: Holidays vs Standard Days",
            labels={
                "avg_daily_revenue": "Avg Daily Revenue (IDR)",
                "day_type": "Day Type",
            },
        )
        style_plot(fig_holiday, height=360)
        st.plotly_chart(fig_holiday, use_container_width=True)

    st.markdown("#### 📋 Holiday vs. Standard Day Demand Metrics")
    st.dataframe(holiday_summary, use_container_width=True)
