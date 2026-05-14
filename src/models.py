import numpy as np


class Standardizer:
    def fit(self, x):
        x = np.asarray(x, dtype=float)
        self.mean_ = x.mean(axis=0)
        self.std_ = x.std(axis=0)
        self.std_[self.std_ == 0] = 1.0
        return self

    def transform(self, x):
        return (np.asarray(x, dtype=float) - self.mean_) / self.std_

    def fit_transform(self, x):
        return self.fit(x).transform(x)


class RidgeRegressor:
    """Small dependency-free ridge regression using a closed-form solution."""

    def __init__(self, alpha=1.0, scale=True):
        self.alpha = alpha
        self.scale = scale

    def fit(self, x, y):
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        if self.scale:
            self.scaler_ = Standardizer()
            x = self.scaler_.fit_transform(x)
        else:
            self.scaler_ = None

        x_aug = np.column_stack([np.ones(len(x)), x])
        penalty = np.eye(x_aug.shape[1]) * self.alpha
        penalty[0, 0] = 0.0
        self.coef_ = np.linalg.pinv(x_aug.T @ x_aug + penalty) @ x_aug.T @ y
        return self

    def predict(self, x):
        x = np.asarray(x, dtype=float)
        if self.scaler_ is not None:
            x = self.scaler_.transform(x)
        x_aug = np.column_stack([np.ones(len(x)), x])
        return x_aug @ self.coef_


class LogisticRegressionGD:
    """L2 logistic regression trained with batch gradient descent."""

    def __init__(self, lr=0.08, epochs=500, l2=0.01, class_weight=True):
        self.lr = lr
        self.epochs = epochs
        self.l2 = l2
        self.class_weight = class_weight

    @staticmethod
    def _sigmoid(z):
        z = np.clip(z, -35, 35)
        return 1.0 / (1.0 + np.exp(-z))

    def fit(self, x, y):
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        self.scaler_ = Standardizer()
        x = self.scaler_.fit_transform(x)
        x_aug = np.column_stack([np.ones(len(x)), x])
        self.coef_ = np.zeros(x_aug.shape[1])

        if self.class_weight:
            pos = max(float((y == 1).sum()), 1.0)
            neg = max(float((y == 0).sum()), 1.0)
            w_pos = len(y) / (2.0 * pos)
            w_neg = len(y) / (2.0 * neg)
            weights = np.where(y == 1, w_pos, w_neg)
        else:
            weights = np.ones(len(y))

        for _ in range(self.epochs):
            p = self._sigmoid(x_aug @ self.coef_)
            error = (p - y) * weights
            grad = (x_aug.T @ error) / len(y)
            grad[1:] += self.l2 * self.coef_[1:] / len(y)
            self.coef_ -= self.lr * grad
        return self

    def predict_proba(self, x):
        x = np.asarray(x, dtype=float)
        x = self.scaler_.transform(x)
        x_aug = np.column_stack([np.ones(len(x)), x])
        p = self._sigmoid(x_aug @ self.coef_)
        return np.column_stack([1 - p, p])


class SeasonalNaive:
    def fit(self, df, target_col):
        self.target_col = target_col
        self.by_quarter_ = df.groupby("Quarter_Num")[target_col].mean().to_dict()
        self.global_mean_ = float(df[target_col].mean())
        return self

    def predict_one(self, quarter_num):
        return float(self.by_quarter_.get(quarter_num, self.global_mean_))


class SeasonalGrowth:
    def fit(self, df, target_col):
        self.target_col = target_col
        ordered = df.sort_values("Quarter_Idx").copy()
        ordered["prev_year"] = ordered[target_col].shift(4)
        growth = ordered[target_col] / ordered["prev_year"].replace(0, np.nan)
        self.avg_yoy_growth_ = float(growth.replace([np.inf, -np.inf], np.nan).dropna().median())
        if not np.isfinite(self.avg_yoy_growth_):
            self.avg_yoy_growth_ = 1.0
        self.history_ = ordered.set_index("Quarter_Idx")[target_col].to_dict()
        self.fallback_ = float(ordered[target_col].tail(4).mean())
        return self

    def predict_one(self, quarter_idx):
        last_year = self.history_.get(quarter_idx - 4)
        if last_year is None:
            return self.fallback_
        return float(last_year * self.avg_yoy_growth_)


def binary_metrics(y_true, y_score, threshold=0.5):
    y_true = np.asarray(y_true).astype(int)
    y_score = np.asarray(y_score).astype(float)
    y_pred = (y_score >= threshold).astype(int)
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    accuracy = (tp + tn) / max(len(y_true), 1)
    brier = float(np.mean((y_score - y_true) ** 2))
    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "brier": brier,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
    }


def lift_at_k(y_true, y_score, k=0.1):
    y_true = np.asarray(y_true).astype(int)
    y_score = np.asarray(y_score).astype(float)
    n = max(int(np.ceil(len(y_true) * k)), 1)
    order = np.argsort(-y_score)
    top_rate = y_true[order[:n]].mean()
    base_rate = y_true.mean()
    return float(top_rate / max(base_rate, 1e-12))


def auc_roc(y_true, y_score):
    """Mann-Whitney AUC implementation without sklearn."""
    y_true = np.asarray(y_true).astype(int)
    y_score = np.asarray(y_score).astype(float)
    pos = y_score[y_true == 1]
    neg = y_score[y_true == 0]
    if len(pos) == 0 or len(neg) == 0:
        return np.nan
    order = np.argsort(y_score)
    ranks = np.empty(len(y_score), dtype=float)
    ranks[order] = np.arange(1, len(y_score) + 1)
    pos_ranks = ranks[y_true == 1].sum()
    auc = (pos_ranks - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))
    return float(auc)

