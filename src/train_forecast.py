import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

LOCAL_PACKAGES = Path(__file__).resolve().parents[1] / ".python_packages"
if LOCAL_PACKAGES.exists() and str(LOCAL_PACKAGES) not in sys.path:
    sys.path.insert(0, str(LOCAL_PACKAGES))

from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.stattools import adfuller

from .config import FORECAST_HORIZON
from .feature_engineering import make_quarterly_series
from .models import SeasonalGrowth, SeasonalNaive

warnings.filterwarnings("ignore")


SARIMA_CANDIDATES = [
    ((0, 1, 0), (0, 1, 0, 4)),
    ((1, 1, 0), (0, 1, 0, 4)),
    ((0, 1, 1), (0, 1, 0, 4)),
    ((1, 1, 1), (0, 1, 0, 4)),
    ((1, 0, 0), (0, 1, 0, 4)),
    ((0, 0, 1), (0, 1, 0, 4)),
    ((1, 1, 0), (1, 1, 0, 4)),
    ((0, 1, 1), (0, 1, 1, 4)),
    ((1, 1, 1), (1, 1, 0, 4)),
    ((1, 1, 1), (0, 1, 1, 4)),
    ((2, 1, 0), (0, 1, 0, 4)),
    ((0, 1, 2), (0, 1, 0, 4)),
]

BASELINE_MODELS = ["SeasonalNaive", "SeasonalGrowth"]


def _mape(actual, pred):
    return abs(pred - actual) / max(abs(actual), 1e-12)


def _smape(actual, pred):
    denom = (abs(actual) + abs(pred)) / 2.0
    return abs(pred - actual) / max(denom, 1e-12)


def _metric_row(actual, pred):
    error = pred - actual
    return {
        "Error": round(error, 2),
        "MAE": round(abs(error), 2),
        "RMSE": round(abs(error), 2),
        "MAPE": round(_mape(actual, pred), 4),
        "sMAPE": round(_smape(actual, pred), 4),
        "Bias": round(error, 2),
    }


def _year_quarter_to_period(value):
    year, quarter = str(value).split("-Q")
    return pd.Period(year=int(year), quarter=int(quarter), freq="Q-DEC")


def _to_series(qdf, target_col):
    ordered = qdf.sort_values("Quarter_Idx").copy()
    idx = pd.PeriodIndex([_year_quarter_to_period(v) for v in ordered["Year_Quarter"]], freq="Q-DEC")
    return pd.Series(ordered[target_col].to_numpy(dtype=float), index=idx, name=target_col)


def _safe_adf(series):
    series = pd.Series(series).dropna()
    if len(series) < 8 or series.nunique() <= 1:
        return np.nan, np.nan
    try:
        stat, pvalue, *_ = adfuller(series, autolag="AIC")
        return float(stat), float(pvalue)
    except Exception:
        return np.nan, np.nan


def stationarity_diagnostics(qdf, target_col):
    y = _to_series(qdf, target_col)
    transforms = {
        "level": y,
        "log_level": np.log1p(y),
        "diff_1": y.diff(1),
        "seasonal_diff_4": y.diff(4),
        "diff_1_and_seasonal_diff_4": y.diff(1).diff(4),
    }
    rows = []
    for name, transformed in transforms.items():
        stat, pvalue = _safe_adf(transformed)
        rows.append(
            {
                "Target": target_col,
                "Transform": name,
                "ADF_Statistic": stat,
                "ADF_PValue": pvalue,
                "Stationary_at_5pct": bool(pvalue < 0.05) if np.isfinite(pvalue) else False,
                "N_Obs": int(pd.Series(transformed).dropna().shape[0]),
            }
        )
    return pd.DataFrame(rows)


def seasonal_profile(qdf, target_col):
    d = qdf.copy()
    overall = d[target_col].mean()
    profile = (
        d.groupby("Quarter_Num", as_index=False)[target_col]
        .mean()
        .rename(columns={target_col: "Quarter_Average"})
    )
    profile["Target"] = target_col
    profile["Seasonal_Index"] = profile["Quarter_Average"] / overall if overall else np.nan
    return profile[["Target", "Quarter_Num", "Quarter_Average", "Seasonal_Index"]]


def _fit_sarima(y, order, seasonal_order):
    return SARIMAX(
        y,
        order=order,
        seasonal_order=seasonal_order,
        enforce_stationarity=False,
        enforce_invertibility=False,
        trend="n",
    ).fit(disp=False, maxiter=300)


def _predict_sarima(train_y, order, seasonal_order, steps=1):
    fit = _fit_sarima(train_y, order, seasonal_order)
    forecast = fit.get_forecast(steps=steps)
    pred = forecast.predicted_mean.to_numpy()
    conf = forecast.conf_int(alpha=0.20).to_numpy()
    return fit, pred, conf


def _baseline_predict(qdf, target_col, train_end_idx, validation_idx, model_name):
    train = qdf[qdf["Quarter_Idx"] <= train_end_idx]
    val = qdf[qdf["Quarter_Idx"] == validation_idx]
    if model_name == "SeasonalNaive":
        model = SeasonalNaive().fit(train, target_col)
        return model.predict_one(int(val["Quarter_Num"].iloc[0]))
    if model_name == "SeasonalGrowth":
        model = SeasonalGrowth().fit(train, target_col)
        return model.predict_one(validation_idx)
    raise ValueError(model_name)


def backtest_time_series_models(qdf, target_col, min_train_idx=12):
    y_full = _to_series(qdf, target_col)
    rows = []
    validation_indices = [idx for idx in sorted(qdf["Quarter_Idx"].unique()) if idx > min_train_idx]

    for validation_idx in validation_indices:
        train_end_idx = validation_idx - 1
        actual = float(qdf.loc[qdf["Quarter_Idx"] == validation_idx, target_col].iloc[0])
        validation_quarter = qdf.loc[qdf["Quarter_Idx"] == validation_idx, "Year_Quarter"].iloc[0]
        train_y = y_full.iloc[:train_end_idx]

        for model_name in BASELINE_MODELS:
            pred = max(float(_baseline_predict(qdf, target_col, train_end_idx, validation_idx, model_name)), 0)
            rows.append(
                {
                    "Target": target_col,
                    "Model": model_name,
                    "Order": "",
                    "Seasonal_Order": "",
                    "Validation_Quarter": validation_quarter,
                    "Actual": round(actual, 2),
                    "Predicted": round(pred, 2),
                    **_metric_row(actual, pred),
                    "AIC": np.nan,
                    "BIC": np.nan,
                    "Converged": True,
                }
            )

        for order, seasonal_order in SARIMA_CANDIDATES:
            try:
                fit, pred_arr, _ = _predict_sarima(train_y, order, seasonal_order, steps=1)
                pred = max(float(pred_arr[0]), 0)
                converged = bool(fit.mle_retvals.get("converged", False))
                rows.append(
                    {
                        "Target": target_col,
                        "Model": "SARIMA",
                        "Order": str(order),
                        "Seasonal_Order": str(seasonal_order),
                        "Validation_Quarter": validation_quarter,
                        "Actual": round(actual, 2),
                        "Predicted": round(pred, 2),
                        **_metric_row(actual, pred),
                        "AIC": float(fit.aic),
                        "BIC": float(fit.bic),
                        "Converged": converged,
                    }
                )
            except Exception as exc:
                rows.append(
                    {
                        "Target": target_col,
                        "Model": "SARIMA",
                        "Order": str(order),
                        "Seasonal_Order": str(seasonal_order),
                        "Validation_Quarter": validation_quarter,
                        "Actual": round(actual, 2),
                        "Predicted": np.nan,
                        "Error": np.nan,
                        "MAE": np.nan,
                        "RMSE": np.nan,
                        "MAPE": np.nan,
                        "sMAPE": np.nan,
                        "Bias": np.nan,
                        "AIC": np.nan,
                        "BIC": np.nan,
                        "Converged": False,
                        "Error": str(exc)[:160],
                    }
                )
    return pd.DataFrame(rows)


def model_comparison(backtest):
    valid = backtest.dropna(subset=["MAPE"]).copy()
    summary = (
        valid.groupby(["Target", "Model", "Order", "Seasonal_Order"], dropna=False, as_index=False)
        .agg(
            Backtest_MAE=("MAE", "mean"),
            Backtest_RMSE=("Error", lambda x: float(np.sqrt(np.mean(np.square(x))))),
            Backtest_MAPE=("MAPE", "mean"),
            Backtest_sMAPE=("sMAPE", "mean"),
            Backtest_Bias=("Bias", "mean"),
            Median_MAPE=("MAPE", "median"),
            AIC=("AIC", "mean"),
            BIC=("BIC", "mean"),
            N_Backtests=("MAPE", "count"),
            Converged_Rate=("Converged", "mean"),
        )
        .sort_values(["Target", "Backtest_MAPE", "Backtest_MAE", "AIC"], na_position="last")
        .reset_index(drop=True)
    )
    return summary


def _fit_final_model(qdf, target_col, selected):
    y = _to_series(qdf, target_col)
    if selected["Model"] == "SeasonalNaive":
        return SeasonalNaive().fit(qdf, target_col)
    if selected["Model"] == "SeasonalGrowth":
        return SeasonalGrowth().fit(qdf, target_col)
    order = eval(selected["Order"])
    seasonal_order = eval(selected["Seasonal_Order"])
    return _fit_sarima(y, order, seasonal_order)


def _build_forecast_horizon(qdf, periods=None):
    periods = periods or len(FORECAST_HORIZON)
    last = qdf.sort_values("Quarter_Idx").iloc[-1]
    last_period = _year_quarter_to_period(last["Year_Quarter"])
    last_idx = int(last["Quarter_Idx"])
    return [
        (f"{period.year}-Q{period.quarter}", last_idx + step, period.quarter)
        for step in range(1, periods + 1)
        for period in [last_period + step]
    ]


def _forecast_selected(qdf, target_col, selected, model, forecast_horizon):
    horizon = len(forecast_horizon)
    if selected["Model"] == "SeasonalNaive":
        preds = [model.predict_one(qnum) for _, _, qnum in forecast_horizon]
        return np.array(preds), None
    if selected["Model"] == "SeasonalGrowth":
        rolling = qdf.copy()
        preds = []
        for quarter, idx, qnum in forecast_horizon:
            last_year = rolling.loc[rolling["Quarter_Idx"] == idx - 4, target_col]
            if len(last_year):
                pred = float(last_year.iloc[0]) * model.avg_yoy_growth_
            else:
                pred = model.predict_one(idx)
            pred = max(pred, 0)
            preds.append(pred)
            rolling = pd.concat(
                [
                    rolling,
                    pd.DataFrame(
                        [{"Year_Quarter": quarter, "Quarter_Idx": idx, "Quarter_Num": qnum, target_col: pred}]
                    ),
                ],
                ignore_index=True,
            )
        return np.array(preds), None

    forecast = model.get_forecast(steps=horizon)
    preds = forecast.predicted_mean.to_numpy()
    conf = forecast.conf_int(alpha=0.20).to_numpy()
    return np.maximum(preds, 0), conf


def forecast_revenue_profit(fact):
    qdf = make_quarterly_series(fact)
    forecast_horizon = _build_forecast_horizon(qdf)
    diagnostics = []
    seasonality = []
    all_backtests = []
    all_comparisons = []
    selected_models = {}

    for target in ["Revenue", "Profit"]:
        diagnostics.append(stationarity_diagnostics(qdf, target))
        seasonality.append(seasonal_profile(qdf, target))
        backtest = backtest_time_series_models(qdf, target)
        comparison = model_comparison(backtest)
        selected = comparison[comparison["Target"] == target].iloc[0].to_dict()
        selected_models[target] = {
            "selected": selected,
            "model": _fit_final_model(qdf, target, selected),
        }
        all_backtests.append(backtest)
        all_comparisons.append(comparison)

    forecast_rows = []
    revenue_pred, revenue_conf = _forecast_selected(
        qdf, "Revenue", selected_models["Revenue"]["selected"], selected_models["Revenue"]["model"], forecast_horizon
    )
    profit_pred, profit_conf = _forecast_selected(
        qdf, "Profit", selected_models["Profit"]["selected"], selected_models["Profit"]["model"], forecast_horizon
    )

    for i, (quarter, idx, _) in enumerate(forecast_horizon):
        rev_band = selected_models["Revenue"]["selected"]["Backtest_MAPE"]
        prof_band = selected_models["Profit"]["selected"]["Backtest_MAPE"]
        rev_lower, rev_upper = (
            (float(revenue_conf[i][0]), float(revenue_conf[i][1]))
            if revenue_conf is not None
            else (revenue_pred[i] * (1 - rev_band), revenue_pred[i] * (1 + rev_band))
        )
        prof_lower, prof_upper = (
            (float(profit_conf[i][0]), float(profit_conf[i][1]))
            if profit_conf is not None
            else (profit_pred[i] * (1 - prof_band), profit_pred[i] * (1 + prof_band))
        )
        forecast_rows.append(
            {
                "Quarter": quarter,
                "Quarter_Idx": idx,
                "Predicted_Revenue": round(float(max(revenue_pred[i], 0)), 2),
                "Revenue_CI_Lower": round(float(max(rev_lower, 0)), 2),
                "Revenue_CI_Upper": round(float(max(rev_upper, 0)), 2),
                "Revenue_Model": _model_label(selected_models["Revenue"]["selected"]),
                "Revenue_Band_Pct": round(float(rev_band), 4),
                "Predicted_Profit": round(float(max(profit_pred[i], 0)), 2),
                "Profit_CI_Lower": round(float(max(prof_lower, 0)), 2),
                "Profit_CI_Upper": round(float(max(prof_upper, 0)), 2),
                "Profit_Model": _model_label(selected_models["Profit"]["selected"]),
                "Profit_Band_Pct": round(float(prof_band), 4),
            }
        )

    forecast = pd.DataFrame(forecast_rows)
    comparison_df = pd.concat(all_comparisons, ignore_index=True)
    backtest_df = pd.concat(all_backtests, ignore_index=True)
    diagnostics_df = pd.concat(diagnostics, ignore_index=True)
    seasonality_df = pd.concat(seasonality, ignore_index=True)
    return forecast, comparison_df, backtest_df, diagnostics_df, seasonality_df


def _model_label(selected):
    if selected["Model"] == "SARIMA":
        return f"SARIMA{selected['Order']}x{selected['Seasonal_Order']}"
    return selected["Model"]
