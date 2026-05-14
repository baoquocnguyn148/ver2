import numpy as np
import pandas as pd


FORECAST_FEATURES = [
    "lag1",
    "lag4",
    "lag5",
    "roll4_mean",
    "roll4_std",
    "yoy_growth",
    "trend",
    "trend_sq",
    "q_sin",
    "q_cos",
    "is_q4",
    "is_q1",
]


CHURN_FEATURES = [
    "Recency",
    "Tenure",
    "Active_Quarters",
    "Active_Rate",
    "Avg_Gap",
    "Total_Orders",
    "Total_Revenue",
    "Total_Profit",
    "Avg_Revenue",
    "Profit_Margin",
    "Freq_L1Q",
    "Freq_L2Q",
    "Freq_L4Q",
    "Rev_L1Q",
    "Rev_L2Q",
    "Rev_L4Q",
    "Profit_L4Q",
    "Revenue_Trend_2Q",
    "Num_Products",
    "Coupon_Diversity",
    "Avg_Unit_Price",
    "Avg_Quantity",
    "Loyalty_Rank",
    "CLV",
    "Income_Imputed",
    "Months_As_Member",
    "Education_Rank",
    "Gender_Male",
]


def make_quarterly_series(fact):
    return (
        fact.groupby(["Year_Quarter", "Quarter_Idx", "Quarter_Num"], as_index=False)
        .agg(Revenue=("Revenue", "sum"), Profit=("Profit", "sum"))
        .sort_values("Quarter_Idx")
        .reset_index(drop=True)
    )


def make_forecast_features(qdf, target_col):
    d = qdf[["Year_Quarter", "Quarter_Idx", "Quarter_Num", target_col]].copy()
    d = d.sort_values("Quarter_Idx").reset_index(drop=True)
    d["lag1"] = d[target_col].shift(1)
    d["lag4"] = d[target_col].shift(4)
    d["lag5"] = d[target_col].shift(5)
    d["roll4_mean"] = d[target_col].shift(1).rolling(4).mean()
    d["roll4_std"] = d[target_col].shift(1).rolling(4).std().fillna(0)
    d["yoy_growth"] = d[target_col].shift(1) / d[target_col].shift(5).replace(0, np.nan)
    d["trend"] = d["Quarter_Idx"]
    d["trend_sq"] = d["Quarter_Idx"] ** 2
    d["q_sin"] = np.sin(2 * np.pi * d["Quarter_Num"] / 4)
    d["q_cos"] = np.cos(2 * np.pi * d["Quarter_Num"] / 4)
    d["is_q4"] = (d["Quarter_Num"] == 4).astype(int)
    d["is_q1"] = (d["Quarter_Num"] == 1).astype(int)
    return d


def make_next_forecast_row(history, target_col, quarter, quarter_idx, quarter_num):
    hist = history.sort_values("Quarter_Idx").copy()
    values = hist[target_col].to_numpy(dtype=float)

    def get_lag(n):
        row = hist[hist["Quarter_Idx"] == quarter_idx - n]
        if len(row):
            return float(row[target_col].iloc[0])
        return float(np.mean(values[-4:]))

    lag1 = float(values[-1])
    lag4 = get_lag(4)
    lag5 = get_lag(5)
    roll4 = values[-4:]
    yoy_growth = lag1 / lag5 if lag5 else 1.0
    row = {
        "Year_Quarter": quarter,
        "Quarter_Idx": quarter_idx,
        "Quarter_Num": quarter_num,
        "lag1": lag1,
        "lag4": lag4,
        "lag5": lag5,
        "roll4_mean": float(np.mean(roll4)),
        "roll4_std": float(np.std(roll4, ddof=1)) if len(roll4) > 1 else 0.0,
        "yoy_growth": yoy_growth,
        "trend": quarter_idx,
        "trend_sq": quarter_idx**2,
        "q_sin": np.sin(2 * np.pi * quarter_num / 4),
        "q_cos": np.cos(2 * np.pi * quarter_num / 4),
        "is_q4": int(quarter_num == 4),
        "is_q1": int(quarter_num == 1),
    }
    return pd.DataFrame([row])


def _purchase_gap(values):
    unique = sorted(set(values))
    if len(unique) <= 1:
        return 0.0
    return float(np.diff(unique).mean())


def build_churn_snapshot(fact, customers, snapshot_idx, horizon=2, scoring_only=False):
    history = fact[fact["Quarter_Idx"] <= snapshot_idx].copy()
    target_period = list(range(snapshot_idx + 1, snapshot_idx + horizon + 1))
    target = fact[fact["Quarter_Idx"].isin(target_period)].copy()

    grp = history.groupby("Customer_ID")
    features = grp.agg(
        Total_Orders=("Order_Count", "sum"),
        Total_Revenue=("Revenue", "sum"),
        Total_Profit=("Profit", "sum"),
        Active_Quarters=("Quarter_Idx", "nunique"),
        First_Qtr=("Quarter_Idx", "min"),
        Last_Qtr=("Quarter_Idx", "max"),
        Avg_Revenue=("Revenue", "mean"),
        Num_Products=("Product_Line", "nunique"),
        Coupon_Diversity=("Coupon_Num", "nunique"),
        Avg_Unit_Price=("Unit_Sale_Price", "mean"),
        Avg_Quantity=("Quantity_Sold", "mean"),
        Quarter_List=("Quarter_Idx", lambda x: tuple(x)),
    ).reset_index()

    features["Recency"] = snapshot_idx - features["Last_Qtr"]
    features["Tenure"] = snapshot_idx - features["First_Qtr"] + 1
    features["Active_Rate"] = features["Active_Quarters"] / features["Tenure"].replace(0, np.nan)
    features["Avg_Gap"] = features["Quarter_List"].apply(_purchase_gap)
    features["Profit_Margin"] = features["Total_Profit"] / features["Total_Revenue"].replace(0, np.nan)

    for width in [1, 2, 4]:
        recent = history[history["Quarter_Idx"] >= snapshot_idx - width + 1]
        recent_agg = recent.groupby("Customer_ID").agg(
            **{
                f"Freq_L{width}Q": ("Order_Count", "sum"),
                f"Rev_L{width}Q": ("Revenue", "sum"),
            }
        )
        features = features.merge(recent_agg, on="Customer_ID", how="left")

    profit_l4 = (
        history[history["Quarter_Idx"] >= snapshot_idx - 3]
        .groupby("Customer_ID")["Profit"]
        .sum()
        .rename("Profit_L4Q")
    )
    features = features.merge(profit_l4, on="Customer_ID", how="left")

    recent_2q = (
        history[history["Quarter_Idx"].isin([snapshot_idx - 1, snapshot_idx])]
        .groupby("Customer_ID")["Revenue"]
        .sum()
        .rename("Rev_Recent_2Q")
    )
    prev_2q = (
        history[history["Quarter_Idx"].isin([snapshot_idx - 3, snapshot_idx - 2])]
        .groupby("Customer_ID")["Revenue"]
        .sum()
        .rename("Rev_Previous_2Q")
    )
    features = features.merge(recent_2q, on="Customer_ID", how="left")
    features = features.merge(prev_2q, on="Customer_ID", how="left")
    features["Revenue_Trend_2Q"] = features["Rev_Recent_2Q"].fillna(0) - features["Rev_Previous_2Q"].fillna(0)

    demo_cols = [
        "Customer_ID",
        "Full_Name",
        "Gender",
        "Education",
        "Education_Rank",
        "Income",
        "Income_Bucket",
        "Months_As_Member",
        "Tenure_Bucket",
        "LoyaltyStatus",
        "Loyalty_Rank",
        "CLV",
        "CLV_Segment",
    ]
    features = features.merge(customers[demo_cols], on="Customer_ID", how="left")
    median_income = customers.loc[customers["Income"] > 0, "Income"].median()
    features["Income_Imputed"] = np.where(features["Income"].fillna(0) <= 0, median_income, features["Income"])
    features["Gender_Male"] = (features["Gender"].astype(str).str.lower() == "male").astype(int)
    features["Snapshot_Idx"] = snapshot_idx
    features["Target_Window"] = f"{snapshot_idx + 1}-{snapshot_idx + horizon}"

    if not scoring_only:
        bought_future = set(target["Customer_ID"].unique())
        features["Y_Churn_Next_2Q"] = (~features["Customer_ID"].isin(bought_future)).astype(int)

    features[CHURN_FEATURES] = features[CHURN_FEATURES].replace([np.inf, -np.inf], np.nan).fillna(0)
    return features


def assign_churn_segment(row):
    p = row["Churn_Probability_Next_2Q"]
    recency = row["Recency"]
    if p >= 0.80 or recency >= 8:
        return "Critical"
    if p >= 0.65:
        return "High Risk"
    if p >= 0.45:
        return "Medium Risk"
    if p >= 0.25:
        return "Low Risk"
    return "Healthy"


def recommended_action(segment):
    return {
        "Healthy": "Duy tri loyalty reward, uu tien upsell/cross-sell.",
        "Low Risk": "Gui uu dai nhe hoac goi san pham lien quan.",
        "Medium Risk": "Win-back campaign co muc tieu, coupon 10-15%.",
        "High Risk": "Lien he ca nhan hoa, uu dai manh kem survey ly do giam mua.",
        "Critical": "Tai kich hoat chi phi thap hoac dua vao nhom theo doi rieng.",
    }[segment]
