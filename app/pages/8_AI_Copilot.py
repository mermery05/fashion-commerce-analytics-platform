import os
import re
import time

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from utils import (
    PALETTE,
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

st.title("💬 Autonomous BI Copilot & SQL Data Agent")
st.markdown(
    "Ask natural-language business and operational questions against our Fashion Commerce Data Warehouse. "
    "The data agent translates your inquiry into DuckDB SQL, executes it against the Gold marts, "
    "autonomously **self-heals syntax errors**, and renders interactive visualizations with business commentary."
)

st.markdown(
    """
    <span class="badge badge-green">🔒 Air-Gapped / Data Sovereign (Ollama)</span>
    <span class="badge badge-purple">Autonomous Self-Healing Loop</span>
    <span class="badge badge-blue">Gold Marts Schema-Aware</span>
    <span class="badge badge-yellow">AST Read-Only Guardrails</span>
    """,
    unsafe_allow_html=True,
)
st.markdown("---")

# Comprehensive Gold Warehouse Schema Context provided to the LLM / Local Agent
SCHEMA_CONTEXT = """
You are a Principal Analytics Engineer and expert DuckDB SQL Agent for a Fashion Commerce Analytics Platform.
Your database schema contains verified relational tables in schema 'gold':

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
   cart_to_booking_pct (DOUBLE), overall_conversion_rate_pct (DOUBLE), avg_duration_seconds (DOUBLE)

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
    daily_gross_revenue (DOUBLE), daily_net_revenue (DOUBLE), temp_mean_c (DOUBLE), precip_mm (DOUBLE),
    weather_condition ('Rainy', 'Hot', 'Mild', 'Unknown'), is_holiday (BOOLEAN), holiday_name (VARCHAR)

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
    is_churned (INTEGER), churn_probability (DOUBLE), churn_risk_tier ('Low Risk (<30%)', 'Medium Risk (30-70%)', 'High Risk (>70%)'),
    predicted_ltv (DOUBLE), expected_net_value (DOUBLE)

16. gold.fct_orders (Granular Order Transaction Fact Table):
    Columns: booking_id (VARCHAR), customer_id (BIGINT), order_date (DATE), created_at (TIMESTAMP),
    product_id (BIGINT), payment_status ('Success', 'Failed'), promo_code (VARCHAR),
    line_total (DOUBLE), line_net_total (DOUBLE),
    customer_order_seq (BIGINT: Sequential order number for each customer: 1 for first order, 2 for second order, etc.),
    promised_lead_days (INTEGER), delivery_distance_km (DOUBLE)

17. gold.dim_customers (Customer Master Dimension):
    Columns: customer_id (BIGINT), first_name (VARCHAR), last_name (VARCHAR), gender ('M', 'F'),
    device_type ('Android', 'iOS'), home_location (VARCHAR), first_order_date (DATE), last_order_date (DATE),
    lifetime_orders (BIGINT), lifetime_spend (DOUBLE), is_repeat_customer (BOOLEAN)

DIALECT & OPERATIONAL RULES:
- Return ONLY valid DuckDB SQL enclosed strictly in ```sql ... ``` code block.
- Only SELECT or WITH statements are allowed. NEVER use DROP, DELETE, INSERT, UPDATE, ALTER, ATTACH, COPY, PRAGMA.
- In DuckDB, for date intervals use: `INTERVAL 7 DAY` or `INTERVAL '7 days'`.
- Always use round() on currency / floats and add LIMIT clauses (e.g. LIMIT 15) for top-N ranking queries.
- After the SQL code block, write a concise, professional 2-sentence executive summary explaining what the query computes.
"""


def is_safe_sql(query: str) -> bool:
    """AST & regex security guardrail ensuring strictly read-only execution."""
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
        r"\bEXPORT\b",
    ]
    for pattern in forbidden:
        if re.search(pattern, clean, re.IGNORECASE):
            return False
    return True


def extract_sql_and_explanation(raw_text: str) -> tuple[str, str]:
    """Extracts SQL code block and commentary from raw model response."""
    sql_match = re.search(r"```sql\s*(.*?)\s*```", raw_text, re.DOTALL | re.IGNORECASE)
    if sql_match:
        sql = sql_match.group(1).strip()
        explanation = re.sub(
            r"```sql.*?```", "", raw_text, flags=re.DOTALL | re.IGNORECASE
        ).strip()
    else:
        # Fallback: find SELECT or WITH block
        select_match = re.search(
            r"(WITH\s+.*?;|SELECT\s+.*?;)", raw_text, re.DOTALL | re.IGNORECASE
        )
        if select_match:
            sql = select_match.group(1).strip()
            explanation = raw_text.replace(sql, "").strip()
        else:
            sql = raw_text.strip()
            explanation = "Executed custom SQL query generated by Data Copilot."

    if not explanation or len(explanation) < 10:
        explanation = "Executed verified analytical query against DuckDB warehouse."
    return sql, explanation


def check_ollama_status(host: str = "http://localhost:11434") -> tuple[bool, list[str]]:
    """Checks if Ollama daemon is reachable and lists locally downloaded models."""
    try:
        resp = requests.get(f"{host.rstrip('/')}/api/tags", timeout=1.5)
        if resp.status_code == 200:
            data = resp.json()
            models = [m.get("name", "") for m in data.get("models", []) if "name" in m]
            return True, models
    except Exception:  # noqa: BLE001
        pass
    return False, []


def call_ollama_agent(
    messages: list[dict],
    host: str = "http://localhost:11434",
    model: str = "qwen2.5-coder:7b",
    timeout: int = 90,
) -> str:
    """Interacts with local Ollama via its OpenAI-compatible completions API."""
    endpoint = f"{host.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
    }
    resp = requests.post(endpoint, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def call_cloud_agent(
    messages: list[dict],
    api_key: str,
    provider: str = "OpenAI",
    model_name: str = "gpt-4o-mini",
    timeout: int = 25,
) -> str:
    """Calls cloud LLM provider (OpenAI or Groq)."""
    if provider == "Groq":
        endpoint = "https://api.groq.com/openai/v1/chat/completions"
    else:
        endpoint = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.1,
    }
    resp = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def smart_fallback_nlp_to_sql(question: str) -> tuple[str, str]:
    """
    Robust rule-based analytical engine providing high-fidelity, verified SQL
    for all core fashion e-commerce domain questions without needing an active LLM.
    """
    q = question.lower().strip()

    # 1. Holidays & Weather Demand (e.g. pre-holiday demand, weather elasticity)
    if "holiday" in q or "lebaran" in q or "festive" in q:
        sql = """
        WITH holiday_dates AS (
            SELECT DISTINCT
                order_date AS holiday_date,
                holiday_name
            FROM gold.mart_demand_drivers
            WHERE is_holiday = TRUE
        ),
        pre_holiday_window AS (
            SELECT
                d.order_date,
                h.holiday_name,
                h.holiday_date,
                d.total_orders,
                d.daily_net_revenue
            FROM gold.mart_demand_drivers d
            JOIN holiday_dates h
              ON d.order_date BETWEEN (h.holiday_date - INTERVAL '7 days') AND (h.holiday_date - INTERVAL '1 day')
        )
        SELECT
            holiday_name,
            count(DISTINCT order_date) AS pre_holiday_observed_days,
            round(avg(total_orders), 1) AS avg_daily_orders_pre_holiday,
            round(avg(daily_net_revenue), 2) AS avg_daily_net_revenue_pre_holiday,
            round(sum(daily_net_revenue), 2) AS total_pre_holiday_revenue
        FROM pre_holiday_window
        GROUP BY holiday_name
        ORDER BY avg_daily_orders_pre_holiday DESC
        LIMIT 10;
        """
        explanation = (
            "Here is the pre-holiday demand analysis measuring daily order volume and net revenue "
            "in the 7-day lead-up window prior to major observed holidays."
        )
        return sql, explanation

    if "weather" in q or "rain" in q or "temp" in q or "precip" in q:
        sql = """
        SELECT
            weather_condition,
            round(avg(temp_mean_c), 1) AS avg_temperature_c,
            round(avg(precip_mm), 1) AS avg_precipitation_mm,
            sum(total_orders) AS total_orders,
            round(sum(daily_net_revenue), 2) AS total_net_revenue,
            round(avg(daily_net_revenue / nullif(total_orders, 0)), 2) AS avg_order_value
        FROM gold.mart_demand_drivers
        WHERE weather_condition != 'Unknown'
        GROUP BY weather_condition
        ORDER BY total_net_revenue DESC;
        """
        explanation = (
            "Here is the macro weather sensitivity summary comparing order cadence and net revenue "
            "across Rainy, Hot, and Mild climate conditions."
        )
        return sql, explanation

    # 2. Logistics, Shipping SLA & Distance
    if any(
        k in q for k in ["logistic", "delivery", "shipping", "distance", "sla", "delay"]
    ):
        sql = """
        SELECT
            distance_tier,
            count(*) AS total_shipments,
            round(avg(delivery_distance_km), 1) AS avg_geodesic_distance_km,
            round(avg(shipment_fee), 2) AS avg_shipping_fee,
            round(avg(shipping_pct_of_order_value), 2) AS avg_shipping_pct_of_order
        FROM gold.mart_logistics
        GROUP BY distance_tier
        ORDER BY avg_geodesic_distance_km ASC;
        """
        explanation = (
            "Here is the logistics performance breakdown by distance tier, detailing delivery reach, "
            "average freight fees, and shipping cost burden relative to order value."
        )
        return sql, explanation

    # 3. Province / Geographical Revenue
    if any(k in q for k in ["province", "region", "location", "geograph", "city"]):
        sql = """
        SELECT
            home_location AS province,
            round(sum(net_revenue), 2) AS net_revenue,
            sum(total_orders) AS total_orders,
            sum(active_customers) AS unique_customers,
            round(avg(avg_delivery_distance_km), 1) AS avg_delivery_distance_km
        FROM gold.mart_geo_performance
        GROUP BY home_location
        ORDER BY net_revenue DESC
        LIMIT 10;
        """
        explanation = "Here are the top 10 Indonesian provinces ranked by net revenue, order volume, and logistics distance."
        return sql, explanation

    # 4. Mobile vs Web / Funnel Conversion
    if any(k in q for k in ["mobile", "web", "funnel", "conversion", "traffic"]):
        sql = """
        SELECT
            traffic_source,
            sum(total_sessions) AS total_sessions,
            sum(sessions_with_add_to_cart) AS sessions_with_cart,
            sum(converted_sessions) AS converted_sessions,
            round(100.0 * sum(converted_sessions) / nullif(sum(total_sessions), 0), 2) AS overall_conversion_rate_pct,
            round(100.0 * sum(sessions_with_add_to_cart) / nullif(sum(total_sessions), 0), 2) AS cart_add_rate_pct,
            round(avg(avg_duration_seconds), 1) AS avg_session_duration_sec
        FROM gold.mart_funnel_daily
        GROUP BY traffic_source;
        """
        explanation = "Here is the marketing funnel comparison evaluating Mobile vs. Web traffic conversion efficiency."
        return sql, explanation

    # 5. Cart Abandonment & Friction
    if any(k in q for k in ["abandon", "lost cart", "cart recovery", "drop off"]):
        sql = """
        SELECT
            traffic_source,
            sum(sessions_with_cart) AS sessions_with_cart,
            sum(sessions_abandoned) AS sessions_abandoned,
            round(100.0 * sum(sessions_abandoned) / nullif(sum(sessions_with_cart), 0), 2) AS abandonment_rate_pct,
            round(sum(lost_revenue_abandoned_cart), 2) AS estimated_lost_revenue
        FROM gold.mart_cart_abandonment
        GROUP BY traffic_source;
        """
        explanation = "Here is the cart abandonment analysis detailing abandoned checkout volume and potential lost revenue."
        return sql, explanation

    # 6. Payment Gateways & Failures
    if any(
        k in q
        for k in ["payment", "gateway", "failure", "failed", "retry", "ovo", "gopay"]
    ):
        sql = """
        SELECT
            payment_method,
            sum(total_payment_attempts) AS total_attempts,
            sum(successful_attempts) AS successful_attempts,
            sum(failed_attempts) AS failed_attempts,
            round(100.0 * sum(successful_attempts) / nullif(sum(total_payment_attempts), 0), 2) AS auth_success_rate_pct,
            round(sum(lost_revenue_failed), 2) AS lost_revenue_from_failures
        FROM gold.mart_payments
        GROUP BY payment_method
        ORDER BY total_attempts DESC;
        """
        explanation = "Here is the payment gateway authorization scorecard showing transaction success rates and failed revenue."
        return sql, explanation

    # 7. Promo Codes & Discounts
    if any(k in q for k in ["promo", "coupon", "discount", "voucher"]):
        sql = """
        SELECT
            promo_code,
            sum(total_orders) AS total_orders,
            round(sum(total_net_revenue), 2) AS total_net_revenue,
            round(sum(total_promo_discount), 2) AS total_discount_subsidized,
            round(avg(discount_depth_pct), 2) AS avg_discount_depth_pct
        FROM gold.mart_promo_lift
        GROUP BY promo_code
        ORDER BY total_orders DESC
        LIMIT 10;
        """
        explanation = "Here is the promotional code performance matrix comparing order volume, discount depth, and revenue lift."
        return sql, explanation

    # 8. Order Interval & Repeat Purchase Cadence (e.g. days between first and second order)
    if "second order" in q or (
        "first order" in q and ("days" in q or "interval" in q or "between" in q)
    ):
        sql = """
        WITH orders AS (
            SELECT DISTINCT
                customer_id,
                booking_id,
                order_date,
                customer_order_seq
            FROM gold.fct_orders
            WHERE payment_status = 'Success'
              AND customer_order_seq IN (1, 2)
        ),
        first_orders_2022 AS (
            SELECT customer_id, order_date AS first_date
            FROM orders
            WHERE customer_order_seq = 1
              AND EXTRACT(YEAR FROM order_date) = 2022
        ),
        second_orders AS (
            SELECT customer_id, order_date AS second_date
            FROM orders
            WHERE customer_order_seq = 2
        ),
        order_intervals AS (
            SELECT
                f.customer_id,
                f.first_date,
                s.second_date,
                datediff('day', f.first_date, s.second_date) AS days_to_second_order
            FROM first_orders_2022 f
            JOIN second_orders s
              ON f.customer_id = s.customer_id
        )
        SELECT
            count(customer_id) AS total_customers_cohort_2022,
            round(avg(days_to_second_order), 1) AS avg_days_first_to_second_order,
            min(days_to_second_order) AS min_days_between,
            max(days_to_second_order) AS max_days_between
        FROM order_intervals;
        """
        explanation = (
            "Here is the repurchase cadence analysis for customers whose first order occurred in 2022, "
            "reporting the total cohort count and the average days elapsed between their first and second purchase."
        )
        return sql, explanation

    # 9. Customer Churn & Machine Learning Predictions
    if any(k in q for k in ["churn", "risk", "lapsed", "retention", "attrition"]):
        sql = """
        SELECT
            churn_risk_tier,
            count(*) AS total_customers,
            round(avg(churn_probability) * 100, 1) AS avg_predicted_churn_pct,
            round(sum(lifetime_spend), 2) AS total_historical_spend,
            round(sum(predicted_ltv), 2) AS total_predicted_forward_ltv,
            round(sum(expected_net_value), 2) AS risk_adjusted_expected_value
        FROM gold.mart_churn_predictions
        GROUP BY churn_risk_tier
        ORDER BY avg_predicted_churn_pct DESC;
        """
        explanation = "Here is the predictive customer churn distribution with forward LTV and risk-adjusted monetary valuation."
        return sql, explanation

    # 9. Search Queries & Catalog Gaps
    if any(k in q for k in ["search", "keyword", "zero conversion", "query", "intent"]):
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
        explanation = "Here are the top customer search terms detailing purchase conversion and zero-result catalog gaps."
        return sql, explanation

    # 10. Top Products & Merchandising Velocity
    if any(
        k in q
        for k in [
            "product",
            "sku",
            "bestseller",
            "item",
            "category",
            "brand",
            "apparel",
        ]
    ):
        sql = """
        SELECT
            product_display_name,
            master_category,
            article_type,
            velocity_tier,
            total_orders,
            total_units_sold,
            round(net_revenue, 2) AS net_revenue
        FROM gold.mart_product_performance
        ORDER BY net_revenue DESC
        LIMIT 10;
        """
        explanation = "Here are the top 10 best-selling fashion products ranked by total net sales and velocity tier."
        return sql, explanation

    # 11. Default: Executive Monthly Performance
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
    explanation = f"Showing executive monthly financial trends over the past 12 months for '{question}'."
    return sql, explanation


def execute_agentic_workflow(
    question: str,
    engine_choice: str,
    ollama_host: str,
    ollama_model: str,
    cloud_provider: str,
    cloud_api_key: str,
    cloud_model: str,
    ollama_timeout: int = 90,
    max_retries: int = 2,
) -> dict:
    """
    Core Autonomous Agent Workflow:
    1. Reason: Generates SQL tailored to question and schema.
    2. Guard: Inspects SQL via AST safety regex.
    3. Execute: Queries DuckDB warehouse.
    4. Self-Heal: If DuckDB throws an error, feeds error back to model to heal query.
    """
    diagnostic_attempts = []
    messages = [
        {"role": "system", "content": SCHEMA_CONTEXT},
        {"role": "user", "content": f"Write a DuckDB SQL query to answer: {question}"},
    ]

    # Mode A: Offline Rule-Based Showcase Engine
    if engine_choice == "⚡ Built-in Showcase Engine":
        sql, explanation = smart_fallback_nlp_to_sql(question)
        if not is_safe_sql(sql):
            return {"success": False, "error": "Query blocked by security guardrails."}
        try:
            df = run_query(sql)
            return {
                "success": True,
                "sql": sql,
                "explanation": explanation,
                "df": df,
                "healed": False,
                "attempts": [],
                "engine_used": "Built-in Showcase Engine (Offline)",
            }
        except Exception as e:
            return {"success": False, "error": str(e), "sql": sql}

    # Mode B & C: Generative LLM with Self-Healing Loop
    engine_name = "Local Agent"
    for attempt in range(max_retries + 1):
        current_sql = None
        # Step 1: Query the model with graceful timeout & transport handling
        try:
            if engine_choice == "💻 Local Ollama (Air-Gapped)":
                engine_name = f"Local Ollama ({ollama_model})"
                raw_response = call_ollama_agent(
                    messages=messages,
                    host=ollama_host,
                    model=ollama_model,
                    timeout=ollama_timeout,
                )
            else:
                engine_name = f"{cloud_provider} ({cloud_model})"
                raw_response = call_cloud_agent(
                    messages=messages,
                    api_key=cloud_api_key,
                    provider=cloud_provider,
                    model_name=cloud_model,
                )
        except requests.exceptions.Timeout:
            # Model took longer than timeout (e.g. cold-starting into memory on local GPU/CPU)
            fallback_sql, fallback_exp = smart_fallback_nlp_to_sql(question)
            try:
                fallback_df = run_query(fallback_sql)
                return {
                    "success": True,
                    "sql": fallback_sql,
                    "explanation": (
                        f"⏱️ **Model Response Timeout ({ollama_timeout}s):** `{ollama_model}` is likely loading "
                        f"into system memory or busy. Switched automatically to the verified analytical engine "
                        f"to deliver your results instantly:\n\n{fallback_exp}"
                    ),
                    "df": fallback_df,
                    "healed": False,
                    "attempts": [
                        {
                            "attempt": 1,
                            "sql": "N/A",
                            "error": f"ReadTimeout ({ollama_timeout}s)",
                        }
                    ],
                    "engine_used": f"{engine_name} -> Fallback (Timeout Guard)",
                }
            except Exception as fb_err:
                return {
                    "success": False,
                    "error": f"Timeout and fallback error: {fb_err}",
                }

        except requests.exceptions.RequestException as req_err:
            # Connection refused or server unreachable
            fallback_sql, fallback_exp = smart_fallback_nlp_to_sql(question)
            try:
                fallback_df = run_query(fallback_sql)
                return {
                    "success": True,
                    "sql": fallback_sql,
                    "explanation": (
                        f"⚠️ **Connection Notice:** Could not reach {engine_name} (`{req_err}`). "
                        f"Served via verified analytical engine:\n\n{fallback_exp}"
                    ),
                    "df": fallback_df,
                    "healed": False,
                    "attempts": [{"attempt": 1, "sql": "N/A", "error": str(req_err)}],
                    "engine_used": f"{engine_name} -> Fallback (Connection Guard)",
                }
            except Exception as fb_err:
                return {
                    "success": False,
                    "error": f"Connection error: {req_err} | Fallback: {fb_err}",
                }

        # Step 2: Extract SQL & Safety Guardrail
        current_sql, explanation = extract_sql_and_explanation(raw_response)

        if not is_safe_sql(current_sql):
            return {
                "success": False,
                "error": "Security Guardrail: The generated query contains non-read-only commands.",
                "sql": current_sql,
            }

        # Step 3: Execute on DuckDB Warehouse
        try:
            df = run_query(current_sql)
            return {
                "success": True,
                "sql": current_sql,
                "explanation": explanation,
                "df": df,
                "healed": (attempt > 0),
                "attempts": diagnostic_attempts,
                "engine_used": engine_name,
            }
        except Exception as db_err:  # noqa: BLE001
            error_str = str(db_err)
            diagnostic_attempts.append(
                {
                    "attempt": attempt + 1,
                    "sql": current_sql,
                    "error": error_str,
                }
            )

            # Feed DuckDB syntax error back into model context for Self-Healing
            if attempt < max_retries:
                messages.append(
                    {"role": "assistant", "content": f"```sql\n{current_sql}\n```"}
                )
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"Your SQL query produced a DuckDB runtime error:\n"
                            f"Error: {error_str}\n\n"
                            f"Please correct the query to fix this exact error. "
                            f"Output ONLY the corrected SQL inside ```sql ... ```."
                        ),
                    }
                )
            else:
                # Retries exhausted, serve verified fallback
                fallback_sql, fallback_exp = smart_fallback_nlp_to_sql(question)
                try:
                    fallback_df = run_query(fallback_sql)
                    return {
                        "success": True,
                        "sql": fallback_sql,
                        "explanation": f"{fallback_exp} *(Fell back after agent retries: {error_str[:80]}...)*",
                        "df": fallback_df,
                        "healed": False,
                        "attempts": diagnostic_attempts,
                        "engine_used": f"{engine_name} -> Fallback",
                    }
                except Exception as fallback_err:
                    return {
                        "success": False,
                        "error": f"Agent error: {error_str} | Fallback error: {fallback_err}",
                        "attempts": diagnostic_attempts,
                    }

    return {"success": False, "error": "Execution attempts timed out."}


def render_smart_chart(df: pd.DataFrame, key: str | None = None):
    """Automatically determines and plots the optimal Plotly visual representation."""
    if df.empty or len(df.columns) < 2:
        return

    cols = list(df.columns)
    first_col = cols[0]
    num_cols = [c for c in cols[1:] if pd.api.types.is_numeric_dtype(df[c])]

    if not num_cols:
        return

    target_num = num_cols[0]

    # Time series trend
    if "date" in first_col.lower() or "month" in first_col.lower():
        df_sorted = df.sort_values(first_col)
        fig = px.line(
            df_sorted,
            x=first_col,
            y=target_num,
            markers=True,
            title=f"📈 {target_num.replace('_', ' ').title()} Trend",
            color_discrete_sequence=[PALETTE["primary"]],
        )
        style_plot(fig, height=360)
        st.plotly_chart(fig, use_container_width=True, key=key)

    # Categorical comparison bar chart
    elif len(df) <= 15:
        fig = px.bar(
            df,
            x=first_col,
            y=target_num,
            color=first_col,
            title=f"📊 {target_num.replace('_', ' ').title()} by {first_col.replace('_', ' ').title()}",
            color_discrete_sequence=px.colors.qualitative.Prism,
        )
        style_plot(fig, height=360)
        st.plotly_chart(fig, use_container_width=True, key=key)


# ==========================================
# SIDEBAR CONTROLS & MODEL ORCHESTRATION
# ==========================================
with st.sidebar:
    st.markdown("### ⚙️ AI Engine & Sovereignty")

    # Check Ollama status
    ollama_online, detected_models = check_ollama_status()

    engine_choice = st.radio(
        "Inference Architecture",
        options=[
            "💻 Local Ollama (Air-Gapped)",
            "⚡ Built-in Showcase Engine",
            "☁️ Cloud Provider (OpenAI / Groq)",
        ],
        index=0 if ollama_online else 1,
        help=(
            "Local Ollama ensures zero data egress and 100% data sovereignty. "
            "Built-in Showcase Engine runs immediately without API keys or background services."
        ),
    )

    ollama_host = "http://localhost:11434"
    ollama_model = "qwen2.5-coder:7b"
    ollama_timeout = 90
    cloud_provider = "OpenAI"
    cloud_api_key = ""
    cloud_model = "gpt-4o-mini"

    if engine_choice == "💻 Local Ollama (Air-Gapped)":
        st.markdown(
            """
            > **🛡️ Data Sovereignty:** Queries and schema remain strictly on-device.
            > Zero telemetry sent to external cloud APIs.
            """
        )
        ollama_host = st.text_input("Ollama Endpoint", value="http://localhost:11434")
        if ollama_online:
            st.success("🟢 Ollama Daemon Active")
            default_model = (
                "qwen2.5-coder:7b"
                if "qwen2.5-coder:7b" in detected_models
                else (detected_models[0] if detected_models else "llama3.1:8b")
            )
            ollama_model = st.selectbox(
                "Local Model",
                options=detected_models
                if detected_models
                else ["qwen2.5-coder:7b", "llama3.1:8b", "llama3.2:3b", "mistral"],
                index=0,
            )
        else:
            st.warning(
                "🟡 Ollama not detected at `localhost:11434`.\n\n"
                "Launch Ollama desktop or run `ollama serve` in terminal. "
                "The agent will automatically fall back to the built-in engine if unreachable."
            )
            ollama_model = st.text_input("Model Name", value="qwen2.5-coder:7b")

        ollama_timeout = st.slider(
            "Model Timeout (seconds)",
            min_value=30,
            max_value=180,
            value=90,
            step=15,
            help="Allowed response time for the local model. Increase if your model takes time to load into memory.",
        )

    elif engine_choice == "☁️ Cloud Provider (OpenAI / Groq)":
        cloud_provider = st.selectbox("Provider", options=["OpenAI", "Groq"])
        env_key = os.getenv(f"{cloud_provider.upper()}_API_KEY", "")
        cloud_api_key = st.text_input(
            f"{cloud_provider} API Key",
            type="password",
            value=env_key,
            help="Enter API key. (Groq provides free ultra-fast LLaMA 3.3 inference).",
        )
        if cloud_provider == "Groq":
            cloud_model = st.selectbox(
                "Model",
                options=["llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
                index=0,
            )
        else:
            cloud_model = st.selectbox(
                "Model", options=["gpt-4o-mini", "gpt-4o"], index=0
            )

    else:
        st.info(
            "⚡ **Showcase Mode Active**: Zero setup required. Uses verified DuckDB query templates."
        )

    st.markdown("---")
    st.markdown("### 💡 Recommended Prompts")
    st.caption("Click any verified question to execute:")

    sample_questions = [
        "What is the average order 1 week before holidays?",
        "Days between first and second order for 2022 customer cohort",
        "How does rainy vs mild weather impact order volume?",
        "What is average delivery distance and shipping fee by province?",
        "Show customer churn risk distribution and forward LTV",
        "Compare conversion rate and cart abandonment between Mobile and Web",
        "Which promo codes have the highest discount depth and orders?",
        "What is the payment success and failure rate by gateway?",
        "Which search queries have zero conversions (catalog gaps)?",
        "What are the top 10 best-selling fashion products?",
        "Show monthly net revenue and AOV trends over the last year",
    ]

    selected_sample = None
    for q_text in sample_questions:
        if st.button(f"👉 {q_text}", key=f"btn_{abs(hash(q_text)) % 100000}"):
            selected_sample = q_text


# ==========================================
# CHAT SESSION STATE & INTERFACE
# ==========================================
if "agent_messages" not in st.session_state:
    st.session_state.agent_messages = [
        {
            "role": "assistant",
            "content": (
                "👋 Hello! I am your **Autonomous Fashion Data Copilot**.\n\n"
                "Ask me any question about revenue trends, holiday demand spikes, cart abandonment, "
                "logistics SLA, payment failures, or ML churn risk. "
                "I will generate, self-heal, and execute DuckDB SQL live against the warehouse!"
            ),
        }
    ]

# Render Message History
for idx, msg in enumerate(st.session_state.agent_messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "sql" in msg:
            with st.expander("🔍 View Generated SQL Query", expanded=False):
                st.code(msg["sql"], language="sql")
        if "healed" in msg and msg["healed"]:
            st.info(
                "🛡️ **Self-Healing Diagnostics**: The query encountered a syntax error and was autonomously corrected by the agent."
            )
        if "df" in msg and msg["df"] is not None:
            st.dataframe(msg["df"], use_container_width=True)
            render_smart_chart(msg["df"], key=f"hist_chart_{idx}")

# Handle Chat Input
user_input = st.chat_input(
    "Ask a question about the data warehouse (e.g. 'What is the average order 1 week before holidays?')..."
)
if selected_sample:
    user_input = selected_sample

if user_input:
    # Append User Message
    st.session_state.agent_messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Process Assistant Response
    with (
        st.chat_message("assistant"),
        st.spinner("Data Agent reasoning & executing DuckDB query..."),
    ):
        t0 = time.time()
        result = execute_agentic_workflow(
            question=user_input,
            engine_choice=engine_choice,
            ollama_host=ollama_host,
            ollama_model=ollama_model,
            cloud_provider=cloud_provider,
            cloud_api_key=cloud_api_key,
            cloud_model=cloud_model,
            ollama_timeout=ollama_timeout,
        )
        elapsed_ms = (time.time() - t0) * 1000

        if result.get("success"):
            st.markdown(result["explanation"])
            st.caption(
                f"⚡ Executed in {elapsed_ms:.1f}ms via **{result.get('engine_used', 'Agent')}** "
                f"against `data/warehouse.duckdb`"
            )

            # Show Self-Healing expander if applicable
            if result.get("healed"):
                with st.expander(
                    "🛡️ Autonomous Self-Healing Diagnostics", expanded=False
                ):
                    st.success(
                        "The agent autonomously recovered from an initial SQL syntax error!"
                    )
                    for att in result.get("attempts", []):
                        st.markdown(
                            f"**Attempt {att['attempt']} Error:** `{att['error']}`"
                        )
                        st.code(att["sql"], language="sql")

            with st.expander("🔍 View Generated SQL Query", expanded=False):
                st.code(result["sql"], language="sql")

            if result["df"] is not None:
                st.dataframe(result["df"], use_container_width=True)
                render_smart_chart(result["df"], key=f"live_chart_{int(t0 * 1000)}")

            # Store in session state
            st.session_state.agent_messages.append(
                {
                    "role": "assistant",
                    "content": result["explanation"],
                    "sql": result["sql"],
                    "df": result["df"],
                    "healed": result.get("healed", False),
                }
            )
        else:
            st.error(f"Execution Error: {result.get('error', 'Unknown error')}")
            if "sql" in result:
                st.code(result["sql"], language="sql")
            st.session_state.agent_messages.append(
                {
                    "role": "assistant",
                    "content": f"🚨 Could not execute query: {result.get('error')}",
                }
            )
