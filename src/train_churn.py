import sys
from pathlib import Path

import numpy as np
import pandas as pd

from .feature_engineering import CHURN_FEATURES, build_churn_snapshot
from .models import LogisticRegressionGD, auc_roc, binary_metrics, lift_at_k


LOCAL_PACKAGES = Path(__file__).resolve().parents[1] / ".python_packages"
if LOCAL_PACKAGES.exists() and str(LOCAL_PACKAGES) not in sys.path:
    sys.path.insert(0, str(LOCAL_PACKAGES))

try:
    import xgboost as xgb
except Exception:  # pragma: no cover - xgboost is optional at runtime
    xgb = None


class XGBoostNativeBinary:
    def __init__(self, params, num_boost_round):
        self.params = params
        self.num_boost_round = num_boost_round

    def fit(self, x, y):
        self.feature_names_ = CHURN_FEATURES
        dtrain = xgb.DMatrix(x, label=y, feature_names=self.feature_names_)
        self.booster_ = xgb.train(
            self.params,
            dtrain,
            num_boost_round=self.num_boost_round,
            verbose_eval=False,
        )
        return self

    def predict_proba(self, x):
        dtest = xgb.DMatrix(x, feature_names=self.feature_names_)
        p = self.booster_.predict(dtest)
        return np.column_stack([1 - p, p])

    @property
    def feature_importances_(self):
        score = self.booster_.get_score(importance_type="gain")
        return np.array([score.get(feature, 0.0) for feature in self.feature_names_], dtype=float)


def build_training_windows(fact, customers, snapshots=range(8, 16), horizon=2):
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


def _candidate_specs():
    specs = [
        {
            "name": "Logistic_Balanced",
            "type": "logistic",
            "params": {"lr": 0.10, "epochs": 450, "l2": 0.05, "class_weight": True},
        },
        {
            "name": "Logistic_StrongL2",
            "type": "logistic",
            "params": {"lr": 0.08, "epochs": 450, "l2": 0.30, "class_weight": True},
        },
        {
            "name": "Logistic_Unweighted",
            "type": "logistic",
            "params": {"lr": 0.08, "epochs": 450, "l2": 0.05, "class_weight": False},
        },
    ]
    if xgb is not None:
        specs.extend(
            [
                {
                    "name": "XGBoost_Balanced",
                    "type": "xgboost",
                    "params": {
                        "n_estimators": 180,
                        "max_depth": 3,
                        "learning_rate": 0.05,
                        "subsample": 0.85,
                        "colsample_bytree": 0.85,
                        "reg_lambda": 3.0,
                        "min_child_weight": 8,
                        "balance_classes": True,
                    },
                },
                {
                    "name": "XGBoost_Regularized",
                    "type": "xgboost",
                    "params": {
                        "n_estimators": 120,
                        "max_depth": 2,
                        "learning_rate": 0.06,
                        "subsample": 0.90,
                        "colsample_bytree": 0.90,
                        "reg_lambda": 6.0,
                        "min_child_weight": 12,
                        "balance_classes": True,
                    },
                },
            ]
        )
    return specs


def _fit_candidate(spec, x_train, y_train):
    if spec["type"] == "logistic":
        model = LogisticRegressionGD(**spec["params"])
        return model.fit(x_train, y_train)

    pos = max(float((y_train == 1).sum()), 1.0)
    neg = max(float((y_train == 0).sum()), 1.0)
    params = {
        k: v
        for k, v in spec["params"].items()
        if k not in {"balance_classes", "n_estimators"}
    }
    if spec["params"].get("balance_classes", False):
        params["scale_pos_weight"] = neg / pos
    params.update(
        {
            "objective": "binary:logistic",
            "eval_metric": "logloss",
            "tree_method": "hist",
            "seed": 42,
            "nthread": 1,
        }
    )
    model = XGBoostNativeBinary(params=params, num_boost_round=spec["params"]["n_estimators"])
    return model.fit(x_train, y_train)


def _predict_score(model, x):
    return model.predict_proba(x)[:, 1]


def _best_threshold(y_true, y_score):
    candidates = np.unique(
        np.concatenate(
            [
                np.linspace(0.05, 0.95, 19),
                np.quantile(y_score, np.linspace(0.05, 0.95, 19)),
            ]
        )
    )
    best = None
    for threshold in candidates:
        metrics = binary_metrics(y_true, y_score, threshold=float(threshold))
        class_balance_floor = min(metrics["recall"], metrics["specificity"])
        objective = metrics["balanced_accuracy"] + 3.0 * metrics["macro_f1"] + class_balance_floor
        row = (
            objective,
            class_balance_floor,
            metrics["balanced_accuracy"],
            metrics["macro_f1"],
            -metrics["brier"],
            threshold,
        )
        if best is None or row > best[0]:
            best = (row, float(threshold), metrics)
    return best[1]


def _operating_threshold(y_true, y_score):
    # A small conservative buffer reduces false positive churn flags for CSKH lists
    # while keeping the churn recall close to the validation optimum.
    return min(0.95, _best_threshold(y_true, y_score) + 0.003)


def _evaluate_scores(y_true, y_score, threshold):
    metrics = binary_metrics(y_true, y_score, threshold=threshold)
    metrics.update(
        {
            "auc_roc": auc_roc(y_true, y_score),
            "lift_top_10pct": lift_at_k(y_true, y_score, k=0.10),
        }
    )
    return metrics


def compare_churn_models(dataset, validation_snapshots=(12, 13, 14, 15)):
    rows = []
    for validation_snapshot in validation_snapshots:
        train = dataset[dataset["Snapshot_Idx"] < validation_snapshot].copy()
        validation = dataset[dataset["Snapshot_Idx"] == validation_snapshot].copy()
        if train.empty or validation.empty:
            continue

        x_train = train[CHURN_FEATURES].to_numpy(dtype=float)
        y_train = train["Y_Churn_Next_2Q"].to_numpy(dtype=int)
        x_val = validation[CHURN_FEATURES].to_numpy(dtype=float)
        y_val = validation["Y_Churn_Next_2Q"].to_numpy(dtype=int)

        for spec in _candidate_specs():
            model = _fit_candidate(spec, x_train, y_train)
            train_score = _predict_score(model, x_train)
            val_score = _predict_score(model, x_val)
            threshold = _operating_threshold(y_train, train_score)
            metrics = _evaluate_scores(y_val, val_score, threshold)
            rows.append(
                {
                    "Validation_Snapshot": validation_snapshot,
                    "Model": spec["name"],
                    "Train_Rows": len(train),
                    "Validation_Rows": len(validation),
                    "Train_Churn_Rate": float(y_train.mean()),
                    "Validation_Churn_Rate": float(y_val.mean()),
                    **metrics,
                }
            )

    backtest = pd.DataFrame(rows)
    metric_cols = [
        "accuracy",
        "balanced_accuracy",
        "macro_f1",
        "f1",
        "f1_no_churn",
        "precision",
        "recall",
        "specificity",
        "npv",
        "auc_roc",
        "lift_top_10pct",
        "brier",
        "threshold",
    ]
    comparison = (
        backtest.groupby("Model", as_index=False)
        .agg({col: "mean" for col in metric_cols} | {"Validation_Snapshot": "count"})
        .rename(columns={"Validation_Snapshot": "N_Backtests"})
    )
    comparison["class_balance_floor"] = comparison[["recall", "specificity"]].min(axis=1)
    comparison["eligible_for_champion"] = (comparison["recall"] >= 0.60) & (comparison["specificity"] >= 0.20)
    comparison = comparison.sort_values(
        ["eligible_for_champion", "macro_f1", "balanced_accuracy", "class_balance_floor"],
        ascending=False,
    ).reset_index(drop=True)
    return comparison, backtest


def _fit_selected_model(dataset, selected_model_name, validation_snapshot=15):
    train = dataset[dataset["Snapshot_Idx"] < validation_snapshot].copy()
    validation = dataset[dataset["Snapshot_Idx"] == validation_snapshot].copy()
    spec = next(spec for spec in _candidate_specs() if spec["name"] == selected_model_name)

    x_train = train[CHURN_FEATURES].to_numpy(dtype=float)
    y_train = train["Y_Churn_Next_2Q"].to_numpy(dtype=int)
    x_val = validation[CHURN_FEATURES].to_numpy(dtype=float)
    y_val = validation["Y_Churn_Next_2Q"].to_numpy(dtype=int)

    model = _fit_candidate(spec, x_train, y_train)
    train_score = _predict_score(model, x_train)
    val_score = _predict_score(model, x_val)
    threshold = _operating_threshold(y_train, train_score)
    metrics = _evaluate_scores(y_val, val_score, threshold)
    metrics.update(
        {
            "train_rows": len(train),
            "validation_rows": len(validation),
            "train_churn_rate": float(y_train.mean()),
            "validation_churn_rate": float(y_val.mean()),
            "validation_snapshot": validation_snapshot,
            "target": "No purchase in next 2 quarters",
            "model": selected_model_name,
        }
    )
    return model, train, validation, val_score, threshold, metrics


def _risk_segment(score, threshold):
    if score >= min(0.98, threshold + 0.20):
        return "Critical"
    if score >= threshold:
        return "High Risk"
    if score >= max(0.35, threshold * 0.75):
        return "Medium Risk"
    if score >= max(0.20, threshold * 0.50):
        return "Low Risk"
    return "Healthy"


def _recommended_action(segment):
    return {
        "Healthy": "Duy tri loyalty reward, uu tien upsell/cross-sell.",
        "Low Risk": "Gui uu dai nhe hoac goi san pham lien quan.",
        "Medium Risk": "Win-back campaign co muc tieu, coupon 10-15%.",
        "High Risk": "CSKH lien he ca nhan hoa, uu dai manh kem survey ly do giam mua.",
        "Critical": "CSKH uu tien cao: goi/nhan tin truc tiep, voucher tai kich hoat va theo doi rieng.",
    }[segment]


def _action_owner(segment):
    if segment in {"Critical", "High Risk"}:
        return "CSKH"
    if segment == "Medium Risk":
        return "CRM/Marketing"
    return "CRM Automation"


def _action_reason(row):
    reasons = []
    if row["Recency"] >= 4:
        reasons.append("lau chua mua")
    if row["Rev_L4Q"] <= 0:
        reasons.append("khong co doanh thu 4 quy gan nhat")
    if row["CLV"] >= row.get("CLV_Median", 0):
        reasons.append("CLV cao")
    if row["Active_Quarters"] <= 1:
        reasons.append("lich su mua mong")
    return ", ".join(reasons[:3]) if reasons else "rui ro theo diem model"


def _format_scored_customers(scoring, score, threshold):
    scored = scoring.copy()
    scored["Churn_Probability_Next_2Q"] = score
    scored["Predicted_Churn"] = (score >= threshold).astype(int)
    scored["Churn_Risk_Segment"] = scored["Churn_Probability_Next_2Q"].apply(lambda p: _risk_segment(p, threshold))
    scored["Recommended_Action"] = scored["Churn_Risk_Segment"].map(_recommended_action)
    scored["Action_Owner"] = scored["Churn_Risk_Segment"].map(_action_owner)
    scored["Expected_Revenue_At_Risk"] = scored["Churn_Probability_Next_2Q"] * scored["Total_Revenue"]
    scored["Retention_Priority_Score"] = scored["Churn_Probability_Next_2Q"] * np.log1p(scored["CLV"].clip(lower=0))
    scored["CLV_Median"] = scored["CLV"].median()
    scored["Action_Reason"] = scored.apply(_action_reason, axis=1)

    output_cols = [
        "Customer_ID",
        "Full_Name",
        "Snapshot_Idx",
        "LoyaltyStatus",
        "Loyalty_Rank",
        "CLV",
        "CLV_Segment",
        "Income_Bucket",
        "Tenure_Bucket",
        "Recency",
        "Tenure",
        "Active_Quarters",
        "Total_Orders",
        "Total_Revenue",
        "Total_Profit",
        "Rev_L4Q",
        "Freq_L4Q",
        "Churn_Probability_Next_2Q",
        "Predicted_Churn",
        "Churn_Risk_Segment",
        "Expected_Revenue_At_Risk",
        "Retention_Priority_Score",
        "Action_Owner",
        "Recommended_Action",
        "Action_Reason",
    ]
    return scored[output_cols].sort_values(
        ["Predicted_Churn", "Retention_Priority_Score", "Churn_Probability_Next_2Q"],
        ascending=[False, False, False],
    )


def _feature_importance(model, model_name):
    if hasattr(model, "coef_"):
        values = model.coef_[1:]
        col = "Coefficient"
    elif hasattr(model, "feature_importances_"):
        values = model.feature_importances_
        col = "Importance"
    else:
        values = np.zeros(len(CHURN_FEATURES))
        col = "Importance"
    importance = pd.DataFrame({"Feature": CHURN_FEATURES, col: values})
    importance["Abs_Importance"] = np.abs(values)
    importance["Model"] = model_name
    return importance.sort_values("Abs_Importance", ascending=False).reset_index(drop=True)


def train_churn_model(fact, customers):
    dataset = build_training_windows(fact, customers)
    model_comparison, backtest = compare_churn_models(dataset)
    selected_model = str(model_comparison.iloc[0]["Model"])

    model, train, validation, val_score, threshold, metrics = _fit_selected_model(dataset, selected_model)
    y_val = validation["Y_Churn_Next_2Q"].to_numpy(dtype=int)
    y_pred = (val_score >= threshold).astype(int)

    confusion_matrix = pd.DataFrame(
        [
            [metrics["tn"], metrics["fp"]],
            [metrics["fn"], metrics["tp"]],
        ],
        index=["Actual 0", "Actual 1"],
        columns=["Predicted 0", "Predicted 1"],
    )

    scored_validation = validation[
        [
            "Customer_ID",
            "Full_Name",
            "Snapshot_Idx",
            "Y_Churn_Next_2Q",
            "Recency",
            "Active_Quarters",
            "Total_Revenue",
            "CLV",
            "LoyaltyStatus",
        ]
    ].copy()
    scored_validation["Churn_Probability_Next_2Q"] = val_score.round(6)
    scored_validation["Predicted_Churn"] = y_pred

    latest_snapshot = int(fact["Quarter_Idx"].max())
    scoring = build_churn_snapshot(fact, customers, latest_snapshot, horizon=2, scoring_only=True)
    scoring_score = _predict_score(model, scoring[CHURN_FEATURES].to_numpy(dtype=float))
    scored_customers = _format_scored_customers(scoring, scoring_score, threshold)

    importance = _feature_importance(model, selected_model)
    metrics_df = pd.DataFrame([metrics])
    metrics_df["threshold"] = threshold
    metrics_df["selected_by"] = "highest rolling-backtest balanced_accuracy, then macro_f1"

    return (
        model,
        metrics_df,
        confusion_matrix,
        scored_validation,
        scored_customers,
        importance,
        model_comparison,
        backtest,
    )
