import pickle

import pandas as pd

from src.config import MODEL_DIR, OUTPUT_DIR, REPORT_DIR
from src.data_loading import add_quarter_index, load_model_tables
from src.data_validation import validate_model_tables
from src.train_churn import train_churn_model
from src.train_forecast import forecast_revenue_profit
from src.visualization import save_confusion_matrix_png


def _ensure_dirs():
    OUTPUT_DIR.mkdir(exist_ok=True)
    MODEL_DIR.mkdir(exist_ok=True)
    REPORT_DIR.mkdir(exist_ok=True)


def _write_excel_report(
    forecast,
    forecast_model_compare,
    forecast_backtest,
    forecast_selected_backtest,
    forecast_diagnostics,
    forecast_seasonality,
    churn_metrics,
    confusion_matrix,
    churn_validation,
    churn_customers,
    churn_importance,
    churn_model_comparison,
    churn_backtest,
):
    report_path = REPORT_DIR / "modular_ml_report.xlsx"
    with pd.ExcelWriter(report_path, engine="openpyxl") as writer:
        forecast.to_excel(writer, sheet_name="Forecast_Revenue_Profit", index=False)
        forecast_model_compare.to_excel(writer, sheet_name="Forecast_Model_Compare", index=False)
        forecast_backtest.to_excel(writer, sheet_name="Forecast_Backtest", index=False)
        forecast_selected_backtest.to_excel(writer, sheet_name="Forecast_Selected_BT", index=False)
        forecast_diagnostics.to_excel(writer, sheet_name="TS_Stationarity", index=False)
        forecast_seasonality.to_excel(writer, sheet_name="TS_Seasonality", index=False)
        churn_metrics.to_excel(writer, sheet_name="Churn_Metrics", index=False)
        confusion_matrix.to_excel(writer, sheet_name="Confusion_Matrix")
        churn_validation.to_excel(writer, sheet_name="Churn_Validation_Scores", index=False)
        churn_customers.head(5000).to_excel(writer, sheet_name="Churn_Top_Customers", index=False)
        churn_importance.to_excel(writer, sheet_name="Churn_Feature_Importance", index=False)
        churn_model_comparison.to_excel(writer, sheet_name="Churn_Model_Compare", index=False)
        churn_backtest.to_excel(writer, sheet_name="Churn_Backtest", index=False)
    return report_path


def _write_churn_action_report(churn_customers, churn_model_comparison, churn_backtest, churn_metrics):
    report_path = REPORT_DIR / "churn_customer_action_list.xlsx"
    high_risk = churn_customers[churn_customers["Churn_Risk_Segment"].isin(["Critical", "High Risk"])]
    with pd.ExcelWriter(report_path, engine="openpyxl") as writer:
        churn_customers.to_excel(writer, sheet_name="All_Customers", index=False)
        high_risk.to_excel(writer, sheet_name="CSKH_Priority_List", index=False)
        churn_metrics.to_excel(writer, sheet_name="Selected_Model_Metrics", index=False)
        churn_model_comparison.to_excel(writer, sheet_name="Model_Comparison", index=False)
        churn_backtest.to_excel(writer, sheet_name="Backtest_Detail", index=False)
    return report_path


def main():
    _ensure_dirs()
    print("[1/4] Loading processed data model...")
    fact, customers = load_model_tables()
    fact, quarter_order = add_quarter_index(fact)
    validation_report = validate_model_tables(fact, customers)
    validation_path = OUTPUT_DIR / "data_validation_report.csv"
    validation_report.to_csv(validation_path, index=False, encoding="utf-8-sig")
    print(f"      FACT rows: {len(fact):,} | customers: {customers['Customer_ID'].nunique():,}")
    print(f"      Quarters : {quarter_order['Year_Quarter'].min()} -> {quarter_order['Year_Quarter'].max()}")
    print(f"      Data validation report: {validation_path}")

    print("[2/4] Forecasting revenue and profit...")
    forecast, forecast_model_compare, forecast_backtest, forecast_diagnostics, forecast_seasonality = forecast_revenue_profit(fact)
    forecast_path = OUTPUT_DIR / "forecast_revenue_profit.csv"
    model_compare_path = OUTPUT_DIR / "forecast_model_comparison.csv"
    backtest_path = OUTPUT_DIR / "forecast_backtest.csv"
    selected_backtest_path = OUTPUT_DIR / "forecast_selected_model_backtest.csv"
    diagnostics_path = OUTPUT_DIR / "time_series_stationarity.csv"
    seasonality_path = OUTPUT_DIR / "time_series_seasonality.csv"
    selected_idx = forecast_model_compare.groupby("Target")["Backtest_MAPE"].idxmin()
    selected_models = forecast_model_compare.loc[
        selected_idx, ["Target", "Model", "Order", "Seasonal_Order"]
    ].copy()
    forecast_selected_backtest = forecast_backtest.merge(
        selected_models,
        on=["Target", "Model", "Order", "Seasonal_Order"],
        how="inner",
    ).sort_values(["Target", "Validation_Quarter"])
    forecast.to_csv(forecast_path, index=False, encoding="utf-8-sig")
    forecast_model_compare.to_csv(model_compare_path, index=False, encoding="utf-8-sig")
    forecast_backtest.to_csv(backtest_path, index=False, encoding="utf-8-sig")
    forecast_selected_backtest.to_csv(selected_backtest_path, index=False, encoding="utf-8-sig")
    forecast_diagnostics.to_csv(diagnostics_path, index=False, encoding="utf-8-sig")
    forecast_seasonality.to_csv(seasonality_path, index=False, encoding="utf-8-sig")
    print(f"      Saved: {forecast_path}")

    print("[3/4] Training leakage-free churn model...")
    (
        churn_model,
        churn_metrics,
        confusion_matrix,
        churn_validation,
        churn_customers,
        churn_importance,
        churn_model_comparison,
        churn_backtest,
    ) = train_churn_model(fact, customers)
    churn_metrics_path = OUTPUT_DIR / "churn_model_metrics.csv"
    churn_model_comparison_path = OUTPUT_DIR / "churn_model_comparison.csv"
    churn_backtest_path = OUTPUT_DIR / "churn_backtest.csv"
    confusion_matrix_path = OUTPUT_DIR / "churn_confusion_matrix.csv"
    confusion_matrix_img_path = OUTPUT_DIR.parent / "docs" / "images" / "confusion_matrix.png"
    churn_validation_path = OUTPUT_DIR / "churn_validation_scores.csv"
    churn_customers_path = OUTPUT_DIR / "churn_predictions_snapshot_2020Q1.csv"
    churn_importance_path = OUTPUT_DIR / "churn_feature_importance.csv"
    churn_metrics.to_csv(churn_metrics_path, index=False, encoding="utf-8-sig")
    churn_model_comparison.to_csv(churn_model_comparison_path, index=False, encoding="utf-8-sig")
    churn_backtest.to_csv(churn_backtest_path, index=False, encoding="utf-8-sig")
    confusion_matrix.to_csv(confusion_matrix_path, encoding="utf-8-sig")
    churn_validation.to_csv(churn_validation_path, index=False, encoding="utf-8-sig")
    churn_customers.to_csv(churn_customers_path, index=False, encoding="utf-8-sig")
    churn_importance.to_csv(churn_importance_path, index=False, encoding="utf-8-sig")
    churn_action_report_path = _write_churn_action_report(
        churn_customers, churn_model_comparison, churn_backtest, churn_metrics
    )
    save_confusion_matrix_png(confusion_matrix, confusion_matrix_img_path)
    model_name = str(churn_metrics["model"].iloc[0]).lower().replace(" ", "_")
    churn_model_path = MODEL_DIR / f"churn_{model_name}.pkl"
    with open(churn_model_path, "wb") as f:
        pickle.dump(churn_model, f)
    print("      Confusion matrix (validation):")
    print(confusion_matrix.to_string())
    print(f"      Saved: {churn_customers_path}")

    print("[4/4] Writing consolidated Excel report...")
    report_path = _write_excel_report(
        forecast,
        forecast_model_compare,
        forecast_backtest,
        forecast_selected_backtest,
        forecast_diagnostics,
        forecast_seasonality,
        churn_metrics,
        confusion_matrix,
        churn_validation,
        churn_customers,
        churn_importance,
        churn_model_comparison,
        churn_backtest,
    )
    print(f"      Saved: {report_path}")

    print("\nPipeline complete.")
    print("Key outputs:")
    print(f"  - {forecast_path}")
    print(f"  - {churn_customers_path}")
    print(f"  - {churn_action_report_path}")
    print(f"  - {churn_metrics_path}")
    print(f"  - {churn_model_comparison_path}")
    print(f"  - {confusion_matrix_img_path}")
    print(f"  - {report_path}")


if __name__ == "__main__":
    main()
