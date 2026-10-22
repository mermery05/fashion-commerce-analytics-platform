"""Train Customer Churn Classifier & Customer Lifetime Value (LTV) Regressor with SHAP.

Extracts customer behavioral attributes from gold.dim_customers and gold.fct_orders,
trains dual LightGBM models (Churn Classifier + LTV Regressor), computes global SHAP
explainability summaries, exports serialized pipelines, and updates
gold.mart_churn_predictions in the DuckDB warehouse.
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import joblib
import numpy as np
import pandas as pd
import shap
from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.compose import ColumnTransformer
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
    root_mean_squared_error,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = os.getenv("DUCKDB_PATH", str(REPO_ROOT / "data" / "warehouse.duckdb"))
MODEL_DIR = REPO_ROOT / "app" / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

CHURN_MODEL_FILE = MODEL_DIR / "churn_lgbm_model.joblib"
LTV_MODEL_FILE = MODEL_DIR / "ltv_lgbm_model.joblib"
METADATA_FILE = MODEL_DIR / "model_metadata.json"
SHAP_SUMMARY_FILE = MODEL_DIR / "shap_summary.json"


def load_feature_dataset(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Extracts customer behavioral attributes, churn target, and LTV target from DuckDB."""
    query = """
    WITH cust_orders AS (
        SELECT
            customer_id,
            count(distinct booking_id) as total_orders,
            round(avg(line_total), 2) as avg_line_total,
            round(avg(delivery_distance_km), 1) as avg_distance_km,
            round(avg(shipment_fee), 2) as avg_shipment_fee,
            round(100.0 * count(distinct case when promo_code != 'NO_PROMO' then booking_id end) / nullif(count(distinct booking_id), 0), 1) as promo_orders_pct,
            mode(payment_method) as preferred_payment_method
        FROM gold.fct_orders
        WHERE payment_status = 'Success'
        GROUP BY customer_id
    )
    SELECT
        c.customer_id,
        c.gender,
        c.device_type,
        c.home_location,
        c.age,
        c.tenure_days,
        c.total_orders,
        c.total_units_purchased,
        c.lifetime_spend,
        c.avg_order_value,
        c.is_repeat_buyer,
        c.f_score,
        c.m_score,
        coalesce(o.avg_distance_km, 50.0) as avg_distance_km,
        coalesce(o.avg_shipment_fee, 0.0) as avg_shipment_fee,
        coalesce(o.promo_orders_pct, 0.0) as promo_orders_pct,
        coalesce(o.preferred_payment_method, 'Credit Card') as preferred_payment_method,
        -- Churn definition (180-day inactivity): Lapsed = 1, Active/At Risk = 0
        CASE WHEN c.customer_activity_status = 'Lapsed' THEN 1 ELSE 0 END as is_churned
    FROM gold.dim_customers c
    LEFT JOIN cust_orders o ON c.customer_id = o.customer_id
    WHERE c.total_orders > 0 AND c.lifetime_spend > 0
    """
    return con.execute(query).df()


def train_models():
    print(f"Connecting to DuckDB at {DB_PATH} (read-only)...")
    con = duckdb.connect(DB_PATH, read_only=True)

    df = load_feature_dataset(con)
    print(f"Loaded {len(df):,} customer records with {df.shape[1]} columns.")
    con.close()

    categorical_cols = [
        "gender",
        "device_type",
        "home_location",
        "preferred_payment_method",
    ]
    numerical_cols = [
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
    churn_feature_cols = categorical_cols + numerical_cols

    # Features for LTV Regressor (exclude lifetime_spend and m_score to prevent identity leakage)
    ltv_numerical_cols = [
        "age",
        "tenure_days",
        "total_orders",
        "total_units_purchased",
        "avg_order_value",
        "is_repeat_buyer",
        "f_score",
        "avg_distance_km",
        "avg_shipment_fee",
        "promo_orders_pct",
    ]
    ltv_feature_cols = categorical_cols + ltv_numerical_cols

    # -------------------------------------------------------------
    # 1. TRAIN CHURN CLASSIFIER (LightGBM)
    # -------------------------------------------------------------
    print("\n--- Training Churn Classifier ---")
    X_churn = df[churn_feature_cols]
    y_churn = df["is_churned"]

    X_train_c, X_test_c, y_train_c, y_test_c = train_test_split(
        X_churn, y_churn, test_size=0.2, random_state=42, stratify=y_churn
    )

    churn_preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), numerical_cols),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                categorical_cols,
            ),
        ]
    )

    clf = LGBMClassifier(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbosity=-1,
    )

    churn_pipeline = Pipeline(
        steps=[
            ("preprocessor", churn_preprocessor),
            ("classifier", clf),
        ]
    )
    churn_pipeline.fit(X_train_c, y_train_c)

    # Churn Metrics
    y_pred_c = churn_pipeline.predict(X_test_c)
    y_prob_c = churn_pipeline.predict_proba(X_test_c)[:, 1]

    roc_auc = float(roc_auc_score(y_test_c, y_prob_c))
    acc_c = float(accuracy_score(y_test_c, y_pred_c))
    prec_c = float(precision_score(y_test_c, y_pred_c))
    rec_c = float(recall_score(y_test_c, y_pred_c))
    f1_c = float(f1_score(y_test_c, y_pred_c))

    print(
        f"Churn Classifier: ROC-AUC={roc_auc:.4f}, Accuracy={acc_c:.4f}, "
        f"Precision={prec_c:.4f}, Recall={rec_c:.4f}, F1={f1_c:.4f}"
    )

    # -------------------------------------------------------------
    # 2. COMPUTE SHAP VALUES & GLOBAL SUMMARY
    # -------------------------------------------------------------
    print("\n--- Computing SHAP Explainability on Churn Model ---")
    encoder = churn_pipeline.named_steps["preprocessor"].named_transformers_["cat"]
    cat_feature_names = list(encoder.get_feature_names_out(categorical_cols))
    all_feature_names = numerical_cols + cat_feature_names

    fitted_clf = churn_pipeline.named_steps["classifier"]
    fitted_preprocessor = churn_pipeline.named_steps["preprocessor"]

    explainer = shap.TreeExplainer(fitted_clf)

    # Compute SHAP on a representative sample of test data (1,000 samples)
    shap_sample = X_test_c.sample(n=min(1000, len(X_test_c)), random_state=42)
    X_sample_trans = fitted_preprocessor.transform(shap_sample)
    raw_shap = explainer.shap_values(X_sample_trans)

    if isinstance(raw_shap, list):
        shap_vals_matrix = raw_shap[1]
    elif len(np.shape(raw_shap)) == 3:
        shap_vals_matrix = raw_shap[:, :, 1]
    else:
        shap_vals_matrix = raw_shap

    mean_abs_shap = np.mean(np.abs(shap_vals_matrix), axis=0)
    shap_ranking = sorted(
        zip(all_feature_names, mean_abs_shap, strict=False),
        key=lambda x: x[1],
        reverse=True,
    )

    shap_summary = [
        {"feature": feat, "mean_abs_shap": round(float(val), 4)}
        for feat, val in shap_ranking[:20]
    ]

    expected_base_value = float(
        explainer.expected_value[1]
        if isinstance(explainer.expected_value, (list, np.ndarray))
        and len(explainer.expected_value) > 1
        else (
            explainer.expected_value[0]
            if isinstance(explainer.expected_value, (list, np.ndarray))
            else explainer.expected_value
        )
    )

    shap_metadata = {
        "base_value_log_odds": round(expected_base_value, 4),
        "base_probability": round(float(1 / (1 + np.exp(-expected_base_value))), 4),
        "top_shap_features": shap_summary,
    }

    with open(SHAP_SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(shap_metadata, f, indent=2)
    print(f"SHAP summary exported to {SHAP_SUMMARY_FILE}.")

    # -------------------------------------------------------------
    # 3. TRAIN CUSTOMER LIFETIME VALUE (LTV) REGRESSOR (LightGBM)
    # -------------------------------------------------------------
    print("\n--- Training Customer Lifetime Value (LTV) Regressor ---")
    X_ltv = df[ltv_feature_cols]
    y_ltv = np.log1p(df["lifetime_spend"])

    X_train_l, X_test_l, y_train_l, y_test_l = train_test_split(
        X_ltv, y_ltv, test_size=0.2, random_state=42
    )

    ltv_preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), ltv_numerical_cols),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                categorical_cols,
            ),
        ]
    )

    reg = LGBMRegressor(
        n_estimators=250,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbosity=-1,
    )

    ltv_pipeline = Pipeline(
        steps=[
            ("preprocessor", ltv_preprocessor),
            ("regressor", reg),
        ]
    )
    ltv_pipeline.fit(X_train_l, y_train_l)

    # Evaluate LTV Regressor
    y_pred_log = ltv_pipeline.predict(X_test_l)
    y_pred_ltv = np.expm1(y_pred_log)
    y_true_ltv = np.expm1(y_test_l)

    ltv_r2 = float(r2_score(y_test_l, y_pred_log))
    ltv_mae = float(mean_absolute_error(y_true_ltv, y_pred_ltv))
    ltv_rmse = float(root_mean_squared_error(y_true_ltv, y_pred_ltv))

    print(
        f"LTV Regressor: Log R2={ltv_r2:.4f}, MAE=Rp {ltv_mae:,.0f}, RMSE=Rp {ltv_rmse:,.0f}"
    )

    # -------------------------------------------------------------
    # 4. EXPORT MODELS AND UNIFIED METADATA
    # -------------------------------------------------------------
    print(f"\nExporting Churn model to {CHURN_MODEL_FILE}...")
    joblib.dump(churn_pipeline, CHURN_MODEL_FILE)

    print(f"Exporting LTV model to {LTV_MODEL_FILE}...")
    joblib.dump(ltv_pipeline, LTV_MODEL_FILE)

    # Feature importances for metadata
    churn_importances = list(
        churn_pipeline.named_steps["classifier"].feature_importances_
    )
    churn_feat_imp = sorted(
        zip(all_feature_names, churn_importances, strict=False),
        key=lambda x: x[1],
        reverse=True,
    )

    ltv_encoder = ltv_pipeline.named_steps["preprocessor"].named_transformers_["cat"]
    ltv_cat_names = list(ltv_encoder.get_feature_names_out(categorical_cols))
    ltv_all_names = ltv_numerical_cols + ltv_cat_names
    ltv_importances = list(ltv_pipeline.named_steps["regressor"].feature_importances_)
    ltv_feat_imp = sorted(
        zip(ltv_all_names, ltv_importances, strict=False),
        key=lambda x: x[1],
        reverse=True,
    )

    metadata = {
        "churn_model": {
            "name": "LightGBM Customer Churn Classifier",
            "metrics": {
                "roc_auc": round(roc_auc, 4),
                "accuracy": round(acc_c, 4),
                "precision": round(prec_c, 4),
                "recall": round(rec_c, 4),
                "f1": round(f1_c, 4),
            },
            "top_features": [
                {"feature": f, "importance": int(imp)} for f, imp in churn_feat_imp[:15]
            ],
        },
        "ltv_model": {
            "name": "LightGBM Customer Lifetime Value Regressor",
            "metrics": {
                "r2_score": round(ltv_r2, 4),
                "mae_idr": round(ltv_mae, 2),
                "rmse_idr": round(ltv_rmse, 2),
            },
            "top_features": [
                {"feature": f, "importance": int(imp)} for f, imp in ltv_feat_imp[:15]
            ],
        },
        "trained_at": datetime.now(UTC).isoformat(),
        "dataset_rows": len(df),
        "categorical_columns": categorical_cols,
        "numerical_columns": numerical_cols,
        "ltv_numerical_columns": ltv_numerical_cols,
    }

    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"Metadata exported to {METADATA_FILE}.")

    # -------------------------------------------------------------
    # 5. GENERATE BATCH INFERENCE & PERSIST TO DUCKDB
    # -------------------------------------------------------------
    print("\nComputing batch Churn & LTV predictions for all customers...")
    df["churn_probability"] = churn_pipeline.predict_proba(df[churn_feature_cols])[:, 1]
    df["churn_risk_tier"] = pd.cut(
        df["churn_probability"],
        bins=[-0.01, 0.30, 0.70, 1.01],
        labels=["Low Risk (<30%)", "Medium Risk (30-70%)", "High Risk (>70%)"],
    )

    pred_log_ltv = ltv_pipeline.predict(df[ltv_feature_cols])
    df["predicted_ltv"] = np.round(np.expm1(pred_log_ltv), 2)

    # Risk-Adjusted Expected Net Lifetime Value: (1 - P(churn)) * predicted_ltv
    df["expected_net_value"] = np.round(
        (1.0 - df["churn_probability"]) * df["predicted_ltv"], 2
    )

    df["ltv_tier"] = pd.cut(
        df["predicted_ltv"],
        bins=[-1, 1000000, 3000000, 10000000, 1e12],
        labels=[
            "Bronze (<Rp 1M)",
            "Silver (Rp 1M-3M)",
            "Gold (Rp 3M-10M)",
            "Platinum (>Rp 10M)",
        ],
    )

    pred_table = df[
        [
            "customer_id",
            "gender",
            "device_type",
            "home_location",
            "age",
            "tenure_days",
            "total_orders",
            "lifetime_spend",
            "avg_order_value",
            "promo_orders_pct",
            "is_churned",
            "churn_probability",
            "churn_risk_tier",
            "predicted_ltv",
            "expected_net_value",
            "ltv_tier",
        ]
    ]

    parquet_path = REPO_ROOT / "data" / "mart_churn_predictions.parquet"
    pred_table.to_parquet(parquet_path, index=False)
    print(f"Persisted {len(pred_table):,} predictions to {parquet_path}.")

    # Attempt to update DuckDB table if write lock is obtainable
    try:
        write_con = duckdb.connect(DB_PATH, read_only=False)
        write_con.register("pred_table_df", pred_table)
        write_con.execute(
            "CREATE OR REPLACE TABLE gold.mart_churn_predictions AS SELECT * FROM pred_table_df"
        )
        saved_count = write_con.execute(
            "SELECT count(*) FROM gold.mart_churn_predictions"
        ).fetchone()[0]
        write_con.close()
        print(
            f"Successfully updated gold.mart_churn_predictions in DuckDB ({saved_count:,} rows)."
        )
    except Exception as e:  # noqa: BLE001
        print(
            f"Notice: DuckDB warehouse currently locked by active reader ({e}). Data safely persisted to Parquet."
        )

    print(
        "\nAll models trained, SHAP summaries computed, and predictions saved successfully!"
    )


if __name__ == "__main__":
    train_models()
