import numpy as np
import pandas as pd

from .feature_engineering import (
    CHURN_FEATURES,
    assign_churn_segment,
    build_churn_snapshot,
    recommended_action,
)
from .models import LogisticRegressionGD, auc_roc, binary_metrics, lift_at_k


def build_training_windows(fact, customers, snapshots=(12, 13, 14, 15), horizon=2):
    frames = []
    max_idx = int(fact["Quarter_Idx"].max())
    for snapshot_idx in snapshots:
        if snapshot_idx + horizon > max_idx:
            continue
        frame = build_churn_snapshot(fact, customers, snapshot_idx, horizon=horizon)
        frames.append(frame)
    if not frames:
        raise ValueError("No valid churn training windows available.")
    return pd.concat(frames, ignore_index=True)


def train_churn_model(fact, customers):
    dataset = build_training_windows(fact, customers)
    train = dataset[dataset["Snapshot_Idx"] < dataset["Snapshot_Idx"].max()].copy()
    validation = dataset[dataset["Snapshot_Idx"] == dataset["Snapshot_Idx"].max()].copy()

    x_train = train[CHURN_FEATURES].to_numpy(dtype=float)
    y_train = train["Y_Churn_Next_2Q"].to_numpy(dtype=int)
    x_val = validation[CHURN_FEATURES].to_numpy(dtype=float)
    y_val = validation["Y_Churn_Next_2Q"].to_numpy(dtype=int)

    model = LogisticRegressionGD(lr=0.10, epochs=300, l2=0.05, class_weight=True)
    model.fit(x_train, y_train)
    val_score = model.predict_proba(x_val)[:, 1]

    metrics = binary_metrics(y_val, val_score)
    confusion_matrix = pd.DataFrame(
        [
            [metrics["tn"], metrics["fp"]],
            [metrics["fn"], metrics["tp"]],
        ],
        index=["Actual 0", "Actual 1"],
        columns=["Predicted 0", "Predicted 1"],
    )
    metrics.update(
        {
            "auc_roc": auc_roc(y_val, val_score),
            "lift_top_10pct": lift_at_k(y_val, val_score, k=0.10),
            "train_rows": len(train),
            "validation_rows": len(validation),
            "train_churn_rate": float(y_train.mean()),
            "validation_churn_rate": float(y_val.mean()),
            "validation_snapshot": int(validation["Snapshot_Idx"].iloc[0]),
            "target": "No purchase in next 2 quarters",
            "model": "LogisticRegressionGD",
        }
    )

    scored_validation = validation[
        ["Customer_ID", "Snapshot_Idx", "Y_Churn_Next_2Q", "Recency", "Total_Revenue", "CLV"]
    ].copy()
    scored_validation["Churn_Probability_Next_2Q"] = val_score.round(6)

    latest_snapshot = int(fact["Quarter_Idx"].max())
    scoring = build_churn_snapshot(fact, customers, latest_snapshot, horizon=2, scoring_only=True)
    scoring_score = model.predict_proba(scoring[CHURN_FEATURES].to_numpy(dtype=float))[:, 1]
    scoring["Churn_Probability_Next_2Q"] = scoring_score
    scoring["Churn_Risk_Segment"] = scoring.apply(assign_churn_segment, axis=1)
    scoring["Recommended_Action"] = scoring["Churn_Risk_Segment"].map(recommended_action)

    output_cols = [
        "Customer_ID",
        "Snapshot_Idx",
        "Recency",
        "Tenure",
        "Active_Quarters",
        "Total_Revenue",
        "Total_Profit",
        "CLV",
        "Loyalty_Rank",
        "Income_Imputed",
        "Churn_Probability_Next_2Q",
        "Churn_Risk_Segment",
        "Recommended_Action",
    ]
    scored_customers = scoring[output_cols].sort_values("Churn_Probability_Next_2Q", ascending=False)

    coef = model.coef_[1:]
    importance = (
        pd.DataFrame({"Feature": CHURN_FEATURES, "Coefficient": coef, "Abs_Coefficient": np.abs(coef)})
        .sort_values("Abs_Coefficient", ascending=False)
        .reset_index(drop=True)
    )

    metrics_df = pd.DataFrame([metrics])
    return model, metrics_df, confusion_matrix, scored_validation, scored_customers, importance
