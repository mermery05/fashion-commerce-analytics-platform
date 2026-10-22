import os
import re
import time

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from utils import (
    apply_custom_css,
    run_query,
    style_plot,
)

st.set_page_config(
    page_title="AI Data Copilot | Fashion Analytics",
    page_icon="💬",
    layout="wide",
)
apply_custom_css()

st.title("💬 Conversational BI & AI Data Copilot")
st.markdown(
    "Ask natural-language questions about our fashion commerce data warehouse. "
    "The copilot translates your inquiry into DuckDB SQL, executes it against the Gold marts, "
    "and returns both interactive visualizations and business insights."
)

st.markdown(
    """
    <span class="badge badge-purple">Text-to-SQL Engine</span>
    <span class="badge badge-blue">Gold Schema Aware</span>
    <span class="badge badge-green">Read-Only Guardrails</span>
    """,
    unsafe_allow_html=True,
)
st.markdown("---")

# Warehouse Schema Context provided to the AI
SCHEMA_CONTEXT = """
You are an expert Data Analyst and SQL Engineer for a Fashion Commerce Analytics Platform using DuckDB.
Your database schema contains the following verified tables in schema 'gold':

1. gold.mart_exec_kpis:
   Columns: order_month (DATE), total_orders (BIGINT), total_units_sold (BIGINT), active_customers (BIGINT),
   gross_revenue (DOUBLE), total_promo_cost (DOUBLE), net_revenue (DOUBLE), total_shipping_revenue (DOUBLE),
   avg_order_value (DOUBLE), new_customer_rev_share_pct (DOUBLE), mom_net_revenue_growth_pct (DOUBLE), yoy_net_revenue_growth_pct (DOUBLE)

2. gold.mart_geo_performance:
   Columns: order_month (DATE), home_country (VARCHAR), home_location (VARCHAR: Indonesian province name e.g. 'Jakarta Raya', 'Jawa Barat'),
   total_orders (BIGINT), active_customers (BIGINT), gross_revenue (DOUBLE), net_revenue (DOUBLE), total_shipment_fees (DOUBLE),
   shipping_pct_of_order_value (DOUBLE), avg_delivery_distance_km (DOUBLE)

3. gold.mart_funnel_daily:
   Columns: session_date (DATE), traffic_source ('MOBILE', 'WEB'), total_sessions (BIGINT), sessions_with_home (BIGINT),
   sessions_with_search (BIGINT), sessions_with_item_detail (BIGINT), sessions_with_add_to_cart (BIGINT), sessions_with_booking (BIGINT),
   converted_sessions (BIGINT), home_to_search_pct (DOUBLE), search_to_detail_pct (DOUBLE), detail_to_cart_pct (DOUBLE),
   cart_to_booking_pct (DOUBLE), overall_conversion_rate_pct (DOUBLE)

4. gold.mart_search_intent:
   Columns: search_keyword (VARCHAR), total_searches (BIGINT), distinct_sessions (BIGINT), sessions_with_cart_add (BIGINT),
   converted_sessions (BIGINT), cart_add_rate_pct (DOUBLE), conversion_rate_pct (DOUBLE), is_zero_conversion (BOOLEAN), intent_classification (VARCHAR)

5. gold.mart_cohort_retention:
   Columns: cohort_month (DATE), cohort_size (BIGINT), month_number (INTEGER: 0, 1, 2... 12), active_customers (BIGINT),
   retention_rate_pct (DOUBLE), cumulative_revenue (DOUBLE), cumulative_revenue_per_customer (DOUBLE)

6. gold.mart_rfm_segments:
   Columns: rfm_segment ('Champions', 'Loyal Customers', 'Potential Loyalists', 'At Risk High Value', etc.),
   gender ('M', 'F'), home_country (VARCHAR), customer_count (BIGINT), pct_of_total_customers (DOUBLE),
   total_revenue (DOUBLE), pct_of_total_revenue (DOUBLE), avg_recency_days (DOUBLE), avg_order_frequency (DOUBLE), avg_ltv (DOUBLE), median_ltv (DOUBLE)

7. gold.mart_cart_abandonment:
   Columns: session_date (DATE), traffic_source ('MOBILE', 'WEB'), sessions_with_cart (BIGINT), sessions_converted (BIGINT),
   sessions_abandoned (BIGINT), cart_to_paid_rate_pct (DOUBLE), cart_abandonment_rate_pct (DOUBLE), total_cart_value (DOUBLE),
   converted_cart_value (DOUBLE), lost_revenue_abandoned_cart (DOUBLE)

8. gold.mart_promo_lift:
   Columns: promo_code (VARCHAR: 'AZ2022', 'BUYMORE', 'NO_PROMO', etc.), customer_type ('New Customer', 'Returning Customer'),
   total_orders (BIGINT), distinct_customers (BIGINT), total_gross_revenue (DOUBLE), total_promo_discount (DOUBLE),
   total_net_revenue (DOUBLE), avg_order_value_net (DOUBLE), avg_discount_per_order (DOUBLE), discount_depth_pct (DOUBLE)

9. gold.mart_pricing_by_category:
   Columns: master_category (VARCHAR: 'Apparel', 'Footwear', 'Accessories', etc.), price_band (VARCHAR), total_order_lines (BIGINT),
   total_units_sold (BIGINT), gross_revenue (DOUBLE), total_allocated_promo_cost (DOUBLE), net_revenue (DOUBLE), gross_to_net_gap_pct (DOUBLE), avg_item_price (DOUBLE)

10. gold.mart_product_performance:
    Columns: product_id (BIGINT), product_display_name (VARCHAR), master_category (VARCHAR), article_type (VARCHAR),
    base_colour (VARCHAR), brand (VARCHAR), velocity_tier ('Top Seller', 'Steady Mover', 'Slow Mover', 'Zero Sales'),
    cart_add_events (BIGINT), total_orders (BIGINT), total_units_sold (BIGINT), gross_revenue (DOUBLE), net_revenue (DOUBLE),
    cart_to_order_conversion_pct (DOUBLE), merchandising_action (VARCHAR)

11. gold.mart_demand_drivers:
    Columns: order_date (DATE), home_location (VARCHAR), master_category (VARCHAR), total_orders (BIGINT), total_units_sold (BIGINT),
    daily_net_revenue (DOUBLE), temp_mean_c (DOUBLE), precip_mm (DOUBLE), weather_condition ('Rainy', 'Hot', 'Mild'), is_holiday (BOOLEAN), holiday_name (VARCHAR)

12. gold.mart_logistics:
    Columns: booking_id (VARCHAR), customer_id (BIGINT), order_date (DATE), order_month (DATE), home_location (VARCHAR),
    delivery_distance_km (DOUBLE), distance_tier ('< 50 km (Local)', '50-250 km (Regional)', '250-1000 km (Inter-city)', '> 1000 km (Long Haul)'),
    promised_lead_days (INTEGER), sla_window_tier ('< 3 days', '3-5 days', '6-7 days'), shipment_fee (DOUBLE), order_gross_value (DOUBLE), shipping_pct_of_order_value (DOUBLE)

13. gold.mart_payments:
    Columns: order_month (DATE), payment_method ('Credit Card', 'Debit Card', 'Gopay', 'OVO', 'LinkAja'), total_payment_attempts (BIGINT),
    successful_attempts (BIGINT), failed_attempts (BIGINT), success_rate_pct (DOUBLE), failure_rate_pct (DOUBLE), successful_revenue (DOUBLE),
    lost_revenue_failed (DOUBLE), retry_rate_pct (DOUBLE), retry_success_rate_pct (DOUBLE)

14. gold.mart_customer_status:
    Columns: customer_id (BIGINT), gender ('M', 'F'), device_type ('Android', 'iOS'), home_location (VARCHAR), total_orders (BIGINT),
    lifetime_spend (DOUBLE), avg_order_value (DOUBLE), days_since_last_order (INTEGER), is_repeat_buyer (BOOLEAN),
    customer_activity_status ('Active', 'At Risk', 'Lapsed', 'Never Purchased'), rfm_segment (VARCHAR), avg_days_between_orders (DOUBLE)

15. gold.mart_churn_predictions:
    Columns: customer_id (BIGINT), tenure_days (INTEGER), total_orders (BIGINT), lifetime_spend (DOUBLE), avg_order_value (DOUBLE),
    is_churned (INTEGER), churn_probability (DOUBLE), churn_risk_tier ('Low Risk (<30%)', 'Medium Risk (30-70%)', 'High Risk (>70%)')

RULES:
- Return ONLY valid DuckDB SQL enclosed in ```sql ... ``` code block.
- Only SELECT queries are permitted. Never use DROP, DELETE, INSERT, UPDATE, ALTER.
- Use explicit column names, aggregations, and LIMIT clauses when appropriate.
"""


def is_safe_sql(query: str) -> bool:
    """Ensures SQL query is strictly read-only."""
    clean = re.sub(r"--.*", "", query)
    clean = re.sub(r"/\*.*?\*/", "", clean, flags=re.DOTALL)
    clean = clean.strip()
    if not (clean.upper().startswith("SELECT") or clean.upper().startswith("WITH")):
        return False
    forbidden = [
        r"\bDROP\b",
        r"\bDELETE\b",
        r"\bINSERT\b",
        r"\bUPDATE\b",
        r"\bALTER\b",
        r"\bTRUNCATE\b",
        r"\bCREATE\b",
        r"\bATTACH\b",
        r"\bCOPY\b",
        r"\bPRAGMA\b",
    ]
    for pattern in forbidden:
        if re.search(pattern, clean, re.IGNORECASE):
            return False
    return True


def smart_fallback_nlp_to_sql(question: str) -> tuple[str, str]:
    """Offline Rule-based and Semantic Pattern Matcher providing zero-API-key execution."""
    q = question.lower().strip()

    # Province / Geo revenue
    if any(k in q for k in ["province", "region", "location", "geograph"]) and any(
        k in q for k in ["revenue", "top", "sales", "highest"]
    ):
        sql = """
        SELECT
            home_location as province,
            round(sum(net_revenue), 2) as net_revenue,
            sum(total_orders) as total_orders,
            round(avg(avg_delivery_distance_km), 1) as avg_distance_km
        FROM gold.mart_geo_performance
        GROUP BY home_location
        ORDER BY net_revenue DESC
        LIMIT 10;
        """
        explanation = "Here are the top 10 Indonesian provinces ranked by total net revenue, orders, and delivery distances."
        return sql, explanation

    # Mobile vs Web / Funnel
    if (
        "mobile" in q
        or "web" in q
        or "conversion" in q
        or "funnel" in q
        or "traffic" in q
    ):
        sql = """
        SELECT
            traffic_source,
            sum(total_sessions) as total_sessions,
            sum(sessions_with_add_to_cart) as sessions_with_cart,
            sum(converted_sessions) as converted_sessions,
            round(100.0 * sum(converted_sessions) / nullif(sum(total_sessions), 0), 2) as conversion_rate_pct,
            round(avg(avg_duration_seconds), 1) as avg_duration_seconds
        FROM gold.mart_funnel_daily
        GROUP BY traffic_source;
        """
        explanation = "Here is the comparison between Mobile and Web traffic conversion rates and session durations."
        return sql, explanation

    # Cart abandonment
    if "abandon" in q or "lost cart" in q or "cart recovery" in q:
        sql = """
        SELECT
            traffic_source,
            sum(sessions_with_cart) as sessions_with_cart,
            sum(sessions_abandoned) as sessions_abandoned,
            round(100.0 * sum(sessions_abandoned) / nullif(sum(sessions_with_cart), 0), 2) as abandonment_rate_pct,
            round(sum(lost_revenue_abandoned_cart), 2) as lost_cart_revenue
        FROM gold.mart_cart_abandonment
        GROUP BY traffic_source;
        """
        explanation = "Here is the cart abandonment analysis showing abandoned sessions and estimated lost revenue."
        return sql, explanation

    # Payment gateways
    if (
        "payment" in q
        or "gateway" in q
        or "failure" in q
        or "failed" in q
        or "retry" in q
    ):
        sql = """
        SELECT
            payment_method,
            sum(total_payment_attempts) as attempts,
            sum(successful_attempts) as successful,
            sum(failed_attempts) as failed,
            round(100.0 * sum(successful_attempts) / nullif(sum(total_payment_attempts), 0), 2) as success_rate_pct,
            round(sum(lost_revenue_failed), 2) as lost_revenue
        FROM gold.mart_payments
        GROUP BY payment_method
        ORDER BY attempts DESC;
        """
        explanation = "Here is the payment gateway reliability breakdown showing authorization success rates and lost revenue."
        return sql, explanation

    # Promo codes
    if "promo" in q or "coupon" in q or "discount" in q:
        sql = """
        SELECT
            promo_code,
            sum(total_orders) as total_orders,
            round(sum(total_net_revenue), 2) as net_revenue,
            round(avg(avg_discount_per_order), 2) as avg_discount,
            round(avg(discount_depth_pct), 2) as avg_discount_depth_pct
        FROM gold.mart_promo_lift
        GROUP BY promo_code
        ORDER BY total_orders DESC;
        """
        explanation = "Here is the promotional code performance scorecard comparing order counts, revenue, and discount depth."
        return sql, explanation

    # Churn / Risk
    if "churn" in q or "at risk" in q or "lapsed" in q or "retention" in q:
        sql = """
        SELECT
            churn_risk_tier,
            count(*) as customer_count,
            round(avg(churn_probability) * 100, 1) as avg_churn_pct,
            round(sum(lifetime_spend), 2) as total_spend
        FROM gold.mart_churn_predictions
        GROUP BY churn_risk_tier
        ORDER BY avg_churn_pct DESC;
        """
        explanation = "Here is the customer churn risk breakdown generated by our LightGBM model pipeline."
        return sql, explanation

    # Search queries / catalog gaps
    if "search" in q or "gap" in q or "keyword" in q:
        sql = """
        SELECT
            search_keyword,
            total_searches,
            distinct_sessions,
            converted_sessions,
            conversion_rate_pct,
            intent_classification
        FROM gold.mart_search_intent
        ORDER BY distinct_sessions DESC
        LIMIT 10;
        """
        explanation = (
            "Here are the top user search keywords and their conversion intent."
        )
        return sql, explanation

    # Top products / velocity
    if "product" in q or "seller" in q or "sku" in q or "category" in q or "items" in q:
        sql = """
        SELECT
            product_display_name,
            master_category,
            article_type,
            total_orders,
            total_units_sold,
            round(total_revenue, 2) as total_revenue,
            velocity_tier
        FROM gold.dim_products
        ORDER BY total_revenue DESC
        LIMIT 10;
        """
        explanation = "Here are the top 10 best-selling fashion products ranked by lifetime revenue."
        return sql, explanation

    # Executive monthly revenue
    sql = """
    SELECT
        order_month,
        net_revenue,
        total_orders,
        active_customers,
        avg_order_value,
        new_customer_rev_share_pct
    FROM gold.mart_exec_kpis
    ORDER BY order_month DESC
    LIMIT 12;
    """
    explanation = "Here is the executive monthly performance summary over the most recent 12 months."
    return sql, explanation


def call_llm_text_to_sql(
    question: str, api_key: str, model_name: str = "gpt-4o-mini"
) -> tuple[str, str]:
    """Generates SQL via OpenAI-compatible REST endpoint."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": SCHEMA_CONTEXT},
            {
                "role": "user",
                "content": f"Generate a DuckDB SQL query to answer: {question}",
            },
        ],
        "temperature": 0.1,
    }

    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        raw_text = data["choices"][0]["message"]["content"]

        # Extract SQL code block
        sql_match = re.search(r"```sql\s*(.*?)\s*```", raw_text, re.DOTALL)
        if sql_match:
            sql = sql_match.group(1).strip()
        else:
            sql = raw_text.strip()

        # Clean any trailing explanation from raw_text
        explanation = re.sub(r"```sql.*?```", "", raw_text, flags=re.DOTALL).strip()
        if not explanation:
            explanation = "Executed custom SQL generated by AI Copilot."
        return sql, explanation
    except Exception as e:  # noqa: BLE001
        st.warning(
            f"LLM API request failed: {e}. Falling back to semantic query engine."
        )
        return smart_fallback_nlp_to_sql(question)


def render_smart_chart(df: pd.DataFrame):
    """Automatically renders the most appropriate Plotly chart based on query results."""
    if df.empty or len(df.columns) < 2:
        return

    cols = df.columns
    # Check if first column is date or string, second is numeric
    first_col = cols[0]
    num_cols = [c for c in cols[1:] if pd.api.types.is_numeric_dtype(df[c])]

    if not num_cols:
        return

    target_num = num_cols[0]

    # Time series line chart
    if "date" in first_col.lower() or "month" in first_col.lower():
        df_sorted = df.sort_values(first_col)
        fig = px.line(
            df_sorted,
            x=first_col,
            y=target_num,
            markers=True,
            title=f"{target_num.replace('_', ' ').title()} over {first_col.replace('_', ' ').title()}",
        )
        style_plot(fig, height=360)
        st.plotly_chart(fig, use_container_width=True)

    # Categorical bar chart (<= 15 items)
    elif len(df) <= 15:
        fig = px.bar(
            df,
            x=first_col,
            y=target_num,
            color=first_col,
            title=f"{target_num.replace('_', ' ').title()} by {first_col.replace('_', ' ').title()}",
        )
        style_plot(fig, height=360)
        st.plotly_chart(fig, use_container_width=True)


# Sidebar Configuration
with st.sidebar:
    st.markdown("### ⚙️ AI Engine Settings")
    api_key_env = os.getenv("OPENAI_API_KEY", "")
    api_key = st.text_input(
        "OpenAI API Key (Optional)",
        type="password",
        value=api_key_env,
        help="Optional: Enter an API key for live GPT-4o Text-to-SQL. If left blank, the copilot uses the built-in semantic query engine.",
    )
    llm_model = st.selectbox("LLM Model", options=["gpt-4o-mini", "gpt-4o"], index=0)

    st.markdown("---")
    st.markdown("### 💡 Sample Prompts Library")
    st.caption("Click any question below to test:")

    sample_questions = [
        "What are the top 5 revenue-generating provinces?",
        "Compare conversion rate and cart abandonment between Mobile and Web",
        "Which promo codes have the highest discount depth?",
        "Show customer churn risk distribution from the ML model",
        "What is the payment success and failure rate by gateway?",
        "Which search queries have zero conversions (catalog gaps)?",
        "What are the top 10 best-selling fashion products?",
        "Show monthly revenue and AOV trends over the last year",
    ]

    selected_sample = None
    for q_text in sample_questions:
        if st.button(f"👉 {q_text}", key=f"btn_{q_text[:20]}"):
            selected_sample = q_text

# Initialize Chat History
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "👋 Hello! I am your **Fashion Commerce Data Copilot**. Ask me any question about our revenue, marketing funnels, customer churn risk, logistics, or merchandising catalog!",
        }
    ]

# Display Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "sql" in msg:
            with st.expander("🔍 View Generated SQL Query"):
                st.code(msg["sql"], language="sql")
        if "df" in msg:
            st.dataframe(msg["df"], use_container_width=True)
            render_smart_chart(msg["df"])

# Handle Input
user_input = st.chat_input(
    "Ask a question about the data warehouse (e.g. 'What is our net revenue by province?')..."
)
if selected_sample:
    user_input = selected_sample

if user_input:
    # Append User Message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Process Assistant Response
    with (
        st.chat_message("assistant"),
        st.spinner("Analyzing question & constructing SQL query..."),
    ):
        t0 = time.time()
        if api_key:
            sql, explanation = call_llm_text_to_sql(user_input, api_key, llm_model)
        else:
            sql, explanation = smart_fallback_nlp_to_sql(user_input)

        if not is_safe_sql(sql):
            st.error(
                "🚨 Security Guardrail: The generated query contains non-read-only commands and was blocked."
            )
            st.stop()

        try:
            result_df = run_query(sql)
            elapsed_ms = (time.time() - t0) * 1000

            st.markdown(explanation)
            st.caption(
                f"⚡ Executed in {elapsed_ms:.1f}ms against `data/warehouse.duckdb`"
            )

            with st.expander("🔍 View Generated SQL Query", expanded=False):
                st.code(sql, language="sql")

            st.dataframe(result_df, use_container_width=True)
            render_smart_chart(result_df)

            # Append Assistant Message to state
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": explanation,
                    "sql": sql,
                    "df": result_df,
                }
            )

        except Exception as e:  # noqa: BLE001
            st.error(f"SQL execution error: {e}")
            st.code(sql, language="sql")
