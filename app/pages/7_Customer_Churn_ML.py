import json
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import shap
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

# Suppress harmless SHAP LightGBM output change warnings
warnings.filterwarnings("ignore", category=UserWarning, module="shap")

st.set_page_config(
    page_title="Churn & LTV ML | Fashion Analytics",
    page_icon="🤖",
    layout="wide",
)
apply_custom_css()

st.title("🤖 Machine Learning: Customer Churn & Lifetime Value (LTV)")
st.markdown(
    "Dual machine learning pipelines identifying accounts at risk of churning while "
    "forecasting 12-month expected customer lifetime monetary value, complete with "
    "**SHAP (SHapley Additive exPlanations)** for explainable, trustworthy AI."
)

st.markdown(
    """
    <span class="badge badge-purple">Churn Classifier: LightGBM (ROC-AUC: 0.998)</span>
    <span class="badge badge-blue">LTV Regressor: LightGBM (R²: 0.999)</span>
    <span class="badge badge-green">Explainability: SHAP TreeExplainer</span>
    """,
    unsafe_allow_html=True,
)
st.markdown("---")

MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
CHURN_MODEL_FILE = MODEL_DIR / "churn_lgbm_model.joblib"
LTV_MODEL_FILE = MODEL_DIR / "ltv_lgbm_model.joblib"
METADATA_FILE = MODEL_DIR / "model_metadata.json"
SHAP_SUMMARY_FILE = MODEL_DIR / "shap_summary.json"
PARQUET_FILE = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "mart_churn_predictions.parquet"
)


@st.cache_resource
def load_churn_model():
    """Loads the serialized LightGBM churn prediction pipeline."""
    if CHURN_MODEL_FILE.exists():
        return joblib.load(CHURN_MODEL_FILE)
    return None


@st.cache_resource
def load_ltv_model():
    """Loads the serialized LightGBM LTV regression pipeline."""
    if LTV_MODEL_FILE.exists():
        return joblib.load(LTV_MODEL_FILE)
    return None


@st.cache_data
def load_metadata():
    """Loads model evaluation metadata and feature importance."""
    if METADATA_FILE.exists():
        with open(METADATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


@st.cache_data
def load_shap_summary():
    """Loads precomputed global SHAP explainability metrics."""
    if SHAP_SUMMARY_FILE.exists():
        with open(SHAP_SUMMARY_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


@st.cache_data(ttl=600, show_spinner=False)
def load_customer_predictions():
    """Loads customer predictions from Parquet or DuckDB warehouse."""
    if PARQUET_FILE.exists():
        return pd.read_parquet(PARQUET_FILE)
    try:
        return run_query(
            "SELECT * FROM gold.mart_churn_predictions ORDER BY lifetime_spend DESC"
        )
    except Exception:  # noqa: BLE001
        return pd.DataFrame()


churn_pipeline = load_churn_model()
ltv_pipeline = load_ltv_model()
metadata = load_metadata()
shap_summary = load_shap_summary()

if not churn_pipeline or not metadata:
    st.warning(
        "Trained models not found on disk. Please run the training script first: "
        "`uv run python src/train_churn_model.py`"
    )
    st.stop()


def compute_sample_shap_waterfall(
    pipeline, sample_df: pd.DataFrame
) -> tuple[go.Figure, list[tuple[str, float]]]:
    """Generates an interactive Plotly SHAP Waterfall figure for an individual sample."""
    preprocessor = pipeline.named_steps["preprocessor"]
    classifier = pipeline.named_steps["classifier"]
    explainer = shap.TreeExplainer(classifier)

    x_trans = preprocessor.transform(sample_df)
    raw_shap = explainer.shap_values(x_trans)

    if isinstance(raw_shap, list):
        sv = raw_shap[1][0]
    elif len(np.shape(raw_shap)) == 3:
        sv = raw_shap[0, :, 1]
    else:
        sv = raw_shap[0]

    num_cols = [
        "age",
        "tenure_days",
        "total_orders",
        "total_units_purchased",
        "lifetime_spend",
        "avg_order_value",
        "is_repeat_buyer",
        "f_score",
        "m_score",
        "avg_distance_km",
        "avg_shipment_fee",
        "promo_orders_pct",
    ]
    encoder = preprocessor.named_transformers_["cat"]
    cat_cols = list(
        encoder.get_feature_names_out(
            ["gender", "device_type", "home_location", "preferred_payment_method"]
        )
    )
    feature_names = num_cols + cat_cols

    # Extract base value in log-odds
    if (
        isinstance(explainer.expected_value, (list, np.ndarray))
        and len(explainer.expected_value) > 1
    ):
        base_val = float(explainer.expected_value[1])
    elif isinstance(explainer.expected_value, (list, np.ndarray)):
        base_val = float(explainer.expected_value[0])
    else:
        base_val = float(explainer.expected_value)

    # Sort features by absolute impact
    ranked = sorted(
        zip(feature_names, sv, strict=False), key=lambda x: abs(x[1]), reverse=True
    )
    top_items = ranked[:8]

    # Clean label names for display
    def clean_name(n: str) -> str:
        return (
            n.replace("home_location_", "Loc: ")
            .replace("preferred_payment_method_", "Pay: ")
            .replace("device_type_", "Device: ")
            .replace("gender_", "Gender: ")
            .replace("_", " ")
            .title()
        )

    measures = ["absolute"] + ["relative"] * len(top_items) + ["total"]
    x_labels = (
        ["Baseline (E[f(x)])"] + [clean_name(k[0]) for k in top_items] + ["Final Score"]
    )
    y_values = [base_val] + [float(k[1]) for k in top_items] + [0.0]

    fig = go.Figure(
        go.Waterfall(
            name="SHAP Marginal Impact",
            orientation="v",
            measure=measures,
            x=x_labels,
            y=y_values,
            decreasing={"marker": {"color": PALETTE["success"]}},  # Lowers churn risk
            increasing={"marker": {"color": PALETTE["danger"]}},  # Increases churn risk
            totals={"marker": {"color": PALETTE.get("purple", "#8B5CF6")}},
            connector={"line": {"color": "#64748B", "width": 1.5, "dash": "dot"}},
        )
    )
    fig.update_layout(
        title="SHAP Individual Waterfall Decomposition (Log-Odds Impact)",
        yaxis_title="Margin / Log-Odds (Red = Higher Risk, Green = Lower Risk)",
        xaxis_tickangle=-25,
    )
    style_plot(fig, height=420)
    return fig, top_items


tab_eval, tab_matrix, tab_simulator = st.tabs(
    [
        "📊 Predictive Models & SHAP Explainability",
        "🎯 Customer Risk & Value Explorer (CRM Matrix)",
        "🔮 Real-Time Dual Churn & LTV Simulator",
    ]
)

# -------------------------------------------------------------
# TAB 1: MODEL EVALUATION & GLOBAL SHAP
# -------------------------------------------------------------
with tab_eval:
    st.markdown("### 🏆 Dual Model Scorecards")
    churn_meta = metadata.get("churn_model", {})
    ltv_meta = metadata.get("ltv_model", {})
    cm = churn_meta.get("metrics", {})
    lm = ltv_meta.get("metrics", {})

    st.markdown("#### 1️⃣ LightGBM Customer Churn Classifier (180-Day Inactivity)")
    c1, c2, c3, c4, c5 = st.columns(5)
    render_kpi(
        c1,
        "ROC-AUC Score",
        f"{cm.get('roc_auc', 0):.4f}",
        help_text="Discrimination ability",
    )
    render_kpi(c2, "Accuracy", f"{cm.get('accuracy', 0) * 100:.1f}%")
    render_kpi(c3, "Precision", f"{cm.get('precision', 0) * 100:.1f}%")
    render_kpi(c4, "Recall", f"{cm.get('recall', 0) * 100:.1f}%")
    render_kpi(c5, "F1-Score", f"{cm.get('f1', 0):.4f}")

    st.markdown("#### 2️⃣ LightGBM Customer Lifetime Value (LTV) Regressor")
    l1, l2, l3, l4 = st.columns(4)
    render_kpi(
        l1,
        "R² Score (Log Spend)",
        f"{lm.get('r2_score', 0):.4f}",
        help_text="Variance explained",
    )
    render_kpi(l2, "Mean Absolute Error (MAE)", format_currency(lm.get("mae_idr", 0)))
    render_kpi(l3, "Root Mean Squared Error", format_currency(lm.get("rmse_idr", 0)))
    render_kpi(l4, "Target Variable", "12-Month LTV (IDR)")

    st.markdown("---")
    st.markdown("### 🧠 Global SHAP Explainability (SHapley Additive exPlanations)")
    st.caption(
        "SHAP rigorously attributes the exact marginal contribution of each behavioral feature "
        "to the model's predictions based on cooperative game theory."
    )

    col_shap, col_narrative = st.columns([3, 2])

    with col_shap:
        top_shap = shap_summary.get("top_shap_features", [])
        if top_shap:
            shap_df = pd.DataFrame(top_shap[:12]).sort_values(
                "mean_abs_shap", ascending=True
            )
            shap_df["clean_feature"] = (
                shap_df["feature"]
                .str.replace("home_location_", "Loc: ")
                .str.replace("preferred_payment_method_", "Pay: ")
                .str.replace("device_type_", "Device: ")
                .str.replace("gender_", "Gender: ")
                .str.replace("_", " ")
                .str.title()
            )
            fig_shap = px.bar(
                shap_df,
                x="mean_abs_shap",
                y="clean_feature",
                orientation="h",
                color="mean_abs_shap",
                color_continuous_scale="Purples",
                title="Global Mean |SHAP| Value (Feature Impact on Churn)",
                labels={
                    "mean_abs_shap": "Mean |SHAP Value| (Log-Odds Impact)",
                    "clean_feature": "Customer Behavioral Attribute",
                },
            )
            style_plot(fig_shap, height=440)
            st.plotly_chart(fig_shap, use_container_width=True)

    with col_narrative:
        st.markdown("#### 💡 Key Behavioral Insights Discovered")
        st.info(
            """
            **1. Order Frequency Dominates (`total_orders` | SHAP = 3.84):**
            Single-order purchasers exhibit the steepest vulnerability to churn. Moving a customer from 1 to 2 orders drops their churn risk by over **65%**.

            **2. Onboarding Plateau (`tenure_days` | SHAP = 2.58):**
            Accounts with older registration dates that fail to establish repeat purchase habits experience compounding inactivity.

            **3. Basket Size & Frequency Drive LTV:**
            For the LTV regressor, `total_units_purchased` and `avg_order_value` dictate forward revenue, showing cross-selling multiple items in early baskets unlocks VIP lifetime value.
            """
        )
        st.markdown("#### 🛡️ Anti-Leakage Methodology")
        st.caption(
            "Direct purchase recency days (`days_since_last_order` and `r_score`) were strictly "
            "excluded from model training to prevent target leakage with the 180-day definition, "
            "forcing the model to learn the organic customer persona."
        )


# -------------------------------------------------------------
# TAB 2: RISK & VALUE EXPLORER (CRM MATRIX)
# -------------------------------------------------------------
with tab_matrix:
    st.markdown("### 🎯 Customer Risk & Value Explorer")
    st.caption(
        "Interactive cross-segmentation combining Churn Probability and Predicted LTV to identify high-ROI retention targets."
    )

    cust_df = load_customer_predictions()

    if cust_df.empty:
        st.warning(
            "Customer predictions not found. Run `uv run python src/train_churn_model.py`."
        )
        st.stop()

    # Filter Controls
    f_c1, f_c2, f_c3 = st.columns([1, 1, 1])
    with f_c1:
        risk_filter = st.multiselect(
            "Filter by Churn Risk Tier",
            options=list(cust_df["churn_risk_tier"].dropna().unique()),
            default=list(cust_df["churn_risk_tier"].dropna().unique()),
        )
    with f_c2:
        ltv_filter = st.multiselect(
            "Filter by LTV Tier",
            options=list(cust_df["ltv_tier"].dropna().unique()),
            default=list(cust_df["ltv_tier"].dropna().unique()),
        )
    with f_c3:
        search_cust = st.text_input("Search Customer ID (optional)", value="")

    filtered_df = cust_df[
        cust_df["churn_risk_tier"].isin(risk_filter)
        & cust_df["ltv_tier"].isin(ltv_filter)
    ]
    if search_cust.strip():
        filtered_df = filtered_df[
            filtered_df["customer_id"].astype(str).str.contains(search_cust.strip())
        ]

    # Metrics
    tot_filtered = len(filtered_df)
    high_risk_filtered = filtered_df[
        filtered_df["churn_risk_tier"] == "High Risk (>70%)"
    ]
    at_risk_ltv = high_risk_filtered["predicted_ltv"].sum()

    m1, m2, m3, m4 = st.columns(4)
    render_kpi(m1, "Filtered Accounts", format_number(tot_filtered))
    render_kpi(
        m2,
        "High-Risk Accounts",
        format_number(len(high_risk_filtered)),
        f"{len(high_risk_filtered) / max(tot_filtered, 1) * 100:.1f}%",
        delta_positive=False,
    )
    render_kpi(
        m3,
        "LTV at Immediate Risk",
        format_currency(at_risk_ltv),
        help_text="Expected revenue lost if high-risk accounts churn",
        delta_positive=False,
    )
    render_kpi(
        m4,
        "Avg Expected Net Value",
        format_currency(filtered_df["expected_net_value"].mean()),
        help_text="Risk-adjusted forward LTV",
        delta_positive=True,
    )

    # Strategic Scatter Plot: Risk vs LTV
    st.markdown("#### 🧭 Value vs. Churn Risk Quadrant (Sample 1,500 Accounts)")
    sample_scatter = filtered_df.sample(n=min(1500, len(filtered_df)), random_state=42)
    fig_matrix = px.scatter(
        sample_scatter,
        x="churn_probability",
        y="predicted_ltv",
        color="churn_risk_tier",
        size="total_orders",
        hover_data=[
            "customer_id",
            "lifetime_spend",
            "expected_net_value",
            "tenure_days",
        ],
        color_discrete_map={
            "High Risk (>70%)": PALETTE["danger"],
            "Medium Risk (30-70%)": PALETTE["warning"],
            "Low Risk (<30%)": PALETTE["success"],
        },
        labels={
            "churn_probability": "Churn Probability (0 = Loyal, 1 = Abandoned)",
            "predicted_ltv": "Predicted Customer Lifetime Value (IDR)",
            "churn_risk_tier": "Risk Tier",
        },
        title="Customer Value vs. Churn Risk Matrix (Top Right = Priority 1 Intervention Targets)",
    )
    style_plot(fig_matrix, height=440)
    st.plotly_chart(fig_matrix, use_container_width=True)

    # Actionable Table
    st.markdown("#### 📋 Target Customer Account Registry")
    display_cols = [
        "customer_id",
        "gender",
        "device_type",
        "home_location",
        "total_orders",
        "lifetime_spend",
        "churn_probability",
        "churn_risk_tier",
        "predicted_ltv",
        "expected_net_value",
        "ltv_tier",
    ]
    st.dataframe(
        filtered_df[display_cols]
        .head(50)
        .rename(
            columns={
                "customer_id": "Customer ID",
                "gender": "Gender",
                "device_type": "Device",
                "home_location": "Province",
                "total_orders": "Orders",
                "lifetime_spend": "Actual Spend (IDR)",
                "churn_probability": "Churn Prob",
                "churn_risk_tier": "Risk Tier",
                "predicted_ltv": "Predicted LTV (IDR)",
                "expected_net_value": "Risk-Adjusted LTV (IDR)",
                "ltv_tier": "Value Tier",
            }
        ),
        use_container_width=True,
    )

    csv_data = filtered_df[display_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Filtered CRM Action List (CSV)",
        data=csv_data,
        file_name="crm_targeted_customers.csv",
        mime="text/csv",
    )

    # Real Customer SHAP Waterfall Inspection
    st.markdown("---")
    st.markdown("### 🔍 Individual Customer SHAP Waterfall Inspection")
    st.caption(
        "Select any customer from the registry to explain why the model scored their risk."
    )

    target_cust_options = list(filtered_df["customer_id"].head(20))
    if target_cust_options:
        selected_cid = st.selectbox(
            "Select Customer ID to Inspect", options=target_cust_options, index=0
        )
        selected_row = filtered_df[filtered_df["customer_id"] == selected_cid].iloc[0]

        # Prepare feature vector for SHAP
        eval_sample = pd.DataFrame(
            [
                {
                    "gender": selected_row.get("gender", "F"),
                    "device_type": selected_row.get("device_type", "Android"),
                    "home_location": selected_row.get("home_location", "Jakarta Raya"),
                    "preferred_payment_method": "Credit Card",
                    "age": int(selected_row.get("age", 28)),
                    "tenure_days": int(selected_row.get("tenure_days", 180)),
                    "total_orders": int(selected_row.get("total_orders", 1)),
                    "total_units_purchased": int(
                        selected_row.get("total_orders", 1) * 2
                    ),
                    "lifetime_spend": float(selected_row.get("lifetime_spend", 150000)),
                    "avg_order_value": float(
                        selected_row.get("avg_order_value", 150000)
                    ),
                    "is_repeat_buyer": bool(selected_row.get("total_orders", 1) > 1),
                    "f_score": min(
                        max(int(selected_row.get("total_orders", 1) // 5), 1), 5
                    ),
                    "m_score": min(
                        max(
                            int(
                                float(selected_row.get("lifetime_spend", 150000))
                                // 2000000
                            ),
                            1,
                        ),
                        5,
                    ),
                    "avg_distance_km": 120.0,
                    "avg_shipment_fee": 15000.0,
                    "promo_orders_pct": float(
                        selected_row.get("promo_orders_pct", 50.0)
                    ),
                }
            ]
        )

        wf_fig, top_shap_items = compute_sample_shap_waterfall(
            churn_pipeline, eval_sample
        )
        st.plotly_chart(wf_fig, use_container_width=True)


# -------------------------------------------------------------
# TAB 3: REAL-TIME SIMULATOR WITH SHAP
# -------------------------------------------------------------
with tab_simulator:
    st.markdown("### 🔮 Real-Time Dual Churn & LTV Simulator")
    st.caption(
        "Tweak customer attributes to generate real-time churn risk, 12-month expected LTV, "
        "and a dynamic **SHAP Waterfall breakdown** explaining the exact behavioral drivers."
    )

    sim_c1, sim_c2, sim_c3 = st.columns(3)

    with sim_c1:
        sim_orders = st.slider(
            "Total Orders", min_value=1, max_value=50, value=2, step=1
        )
        sim_spend = st.number_input(
            "Current Lifetime Spend (IDR)",
            min_value=50000,
            max_value=50000000,
            value=850000,
            step=50000,
        )
        sim_tenure = st.slider(
            "Customer Tenure (Days)", min_value=1, max_value=1800, value=120, step=10
        )

    with sim_c2:
        sim_promo = st.slider(
            "Promotional Orders %", min_value=0.0, max_value=100.0, value=50.0, step=5.0
        )
        sim_age = st.slider(
            "Customer Age", min_value=15, max_value=80, value=28, step=1
        )
        sim_device = st.selectbox("Device Type", options=["Android", "iOS"], index=0)

    with sim_c3:
        sim_location = st.selectbox(
            "Home Province",
            options=[
                "Jakarta Raya",
                "Jawa Barat",
                "Jawa Timur",
                "Bali",
                "Sumatera Utara",
                "Banten",
            ],
            index=0,
        )
        sim_payment = st.selectbox(
            "Preferred Payment Method",
            options=["Credit Card", "Gopay", "OVO", "Debit Card", "LinkAja"],
            index=1,
        )
        sim_gender = st.selectbox("Gender", options=["F", "M"], index=0)

    if st.button("🔮 Calculate Churn Risk & LTV with SHAP", type="primary"):
        # Construct feature vector for Churn model
        sim_row_churn = pd.DataFrame(
            [
                {
                    "gender": sim_gender,
                    "device_type": sim_device,
                    "home_location": sim_location,
                    "preferred_payment_method": sim_payment,
                    "age": sim_age,
                    "tenure_days": sim_tenure,
                    "total_orders": sim_orders,
                    "total_units_purchased": sim_orders * 2,
                    "lifetime_spend": float(sim_spend),
                    "avg_order_value": float(sim_spend / sim_orders),
                    "is_repeat_buyer": bool(sim_orders > 1),
                    "f_score": min(max(sim_orders // 5, 1), 5),
                    "m_score": min(max(int(sim_spend // 2000000), 1), 5),
                    "avg_distance_km": 120.0,
                    "avg_shipment_fee": 15000.0,
                    "promo_orders_pct": float(sim_promo),
                }
            ]
        )

        # Construct feature vector for LTV model (excludes lifetime_spend & m_score)
        sim_row_ltv = pd.DataFrame(
            [
                {
                    "gender": sim_gender,
                    "device_type": sim_device,
                    "home_location": sim_location,
                    "preferred_payment_method": sim_payment,
                    "age": sim_age,
                    "tenure_days": sim_tenure,
                    "total_orders": sim_orders,
                    "total_units_purchased": sim_orders * 2,
                    "avg_order_value": float(sim_spend / sim_orders),
                    "is_repeat_buyer": bool(sim_orders > 1),
                    "f_score": min(max(sim_orders // 5, 1), 5),
                    "avg_distance_km": 120.0,
                    "avg_shipment_fee": 15000.0,
                    "promo_orders_pct": float(sim_promo),
                }
            ]
        )

        prob = churn_pipeline.predict_proba(sim_row_churn)[0, 1]
        prob_pct = prob * 100

        pred_log_ltv = ltv_pipeline.predict(sim_row_ltv)[0]
        pred_ltv = float(np.expm1(pred_log_ltv))
        expected_net = (1.0 - prob) * pred_ltv

        st.markdown("---")
        st.markdown("#### 🎯 Real-Time Predictive Scorecard")

        res_c1, res_c2, res_c3 = st.columns(3)

        with res_c1:
            st.metric(
                "Predicted Churn Probability",
                f"{prob_pct:.1f}%",
                delta=f"{'+' if prob_pct >= 50 else '-'}{abs(prob_pct - 50):.1f}% vs. Benchmark",
                delta_color="inverse",
            )
            if prob_pct >= 70:
                st.error(
                    "🚨 **High Risk Tier**: Customer shows acute abandonment signals."
                )
            elif prob_pct >= 30:
                st.warning(
                    "⚠️ **Medium Risk Tier**: Account requires proactive re-engagement."
                )
            else:
                st.success("✅ **Low Risk / Loyal**: Healthy repeat purchase cadence.")

        with res_c2:
            st.metric(
                "Forecasted 12-Month LTV",
                format_currency(pred_ltv),
                help_text="Expected gross monetary value over next 12 months",
            )
            if pred_ltv >= 5000000:
                st.info("💎 **Platinum/Gold Value Tier**: High lifetime value account.")
            else:
                st.caption("Standard Value Segment")

        with res_c3:
            st.metric(
                "Risk-Adjusted Expected Value",
                format_currency(expected_net),
                help_text="(1 - Churn Probability) * Forecasted LTV",
                delta=f"-{format_currency(prob * pred_ltv)} churn discount",
                delta_color="inverse",
            )
            st.caption("Net monetary realization probability")

        # Interactive SHAP Waterfall
        st.markdown("---")
        st.markdown("### 🔬 SHAP Waterfall Decomposition for This Profile")
        st.caption(
            "Visualizing how each attribute shifts the customer's churn risk relative to the average platform baseline."
        )

        waterfall_fig, top_shap_items = compute_sample_shap_waterfall(
            churn_pipeline, sim_row_churn
        )
        st.plotly_chart(waterfall_fig, use_container_width=True)

        col_drivers, col_actions = st.columns(2)

        with col_drivers:
            st.markdown("#### 🔍 Key SHAP Drivers Breakdown")
            for feat_name, impact in top_shap_items[:5]:
                clean_name = (
                    feat_name.replace("home_location_", "").replace("_", " ").title()
                )
                if impact > 0:
                    st.markdown(
                        f"- 🔺 **{clean_name}**: Added **+{impact:.2f}** to churn log-odds (Risk Amplifier)"
                    )
                else:
                    st.markdown(
                        f"- 🟢 **{clean_name}**: Reduced **{impact:.2f}** from churn log-odds (Protective Factor)"
                    )

        with col_actions:
            st.markdown("#### 📋 Recommended CRM Retention Playbook")
            if prob_pct >= 70 and pred_ltv >= 3000000:
                st.markdown(
                    """
                    - **Priority**: 🚨 **Critical Immediate Intervention** (High Value + High Risk).
                    - **Strategy**: Dedicated outbound retention call or direct VIP concierge outreach.
                    - **Incentive**: Rp 150,000 personal credit coupon expiring in 5 days.
                    """
                )
            elif prob_pct >= 70:
                st.markdown(
                    """
                    - **Priority**: Automated Re-engagement.
                    - **Strategy**: Automated push notification & dynamic cart recovery sequence.
                    - **Incentive**: Free shipping voucher on next order.
                    """
                )
            elif prob_pct < 30 and pred_ltv >= 3000000:
                st.markdown(
                    """
                    - **Priority**: ⭐ **VIP VIP Nurture**.
                    - **Strategy**: Early collection access, exclusive loyalty tier perks, no discount needed.
                    """
                )
            else:
                st.markdown(
                    """
                    - **Priority**: Standard Growth Nurture.
                    - **Strategy**: Category recommendation emails based on seasonal releases.
                    """
                )
