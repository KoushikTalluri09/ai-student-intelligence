import numpy as np
import pandas as pd


# ---------- CORE METRICS ----------

def calculate_trend(scores):
    if len(scores) < 2:
        return "insufficient_data"

    diff = scores.iloc[-1] - scores.iloc[0]

    if diff > 5:
        return "improving"
    elif diff < -5:
        return "declining"
    else:
        return "stable"


def improvement_velocity(scores):
    if len(scores) < 2:
        return 0.0
    return round((scores.iloc[-1] - scores.iloc[0]) / len(scores), 2)


def consistency_score(scores):
    if len(scores) < 2:
        return 1.0
    return round(1 / (1 + np.std(scores)), 3)


def mock_vs_real_gap(df):
    mock_avg = df[df["exam_type"] == "mock"]["score"].mean()
    real_avg = df[df["exam_type"] == "real"]["score"].mean()

    if pd.isna(mock_avg) or pd.isna(real_avg):
        return None

    return round(real_avg - mock_avg, 2)


# ---------- ADVANCED INTERPRETABLE METRICS ----------

def performance_band(avg_score):
    if avg_score < 60:
        return "low"
    elif avg_score < 80:
        return "medium"
    else:
        return "high"


def volatility_level(scores):
    if len(scores) < 2:
        return "unknown"

    std = np.std(scores)

    if std < 5:
        return "low"
    elif std < 10:
        return "medium"
    else:
        return "high"


def recent_average(scores, window=2):
    if len(scores) < window:
        return round(scores.mean(), 2)
    return round(scores.iloc[-window:].mean(), 2)


def risk_flag(avg_score, trend):
    if avg_score < 60 and trend == "declining":
        return "high"
    elif avg_score < 60 or trend == "declining":
        return "medium"
    else:
        return "low"


def data_confidence(attempt_count):
    if attempt_count >= 5:
        return "high"
    elif attempt_count >= 3:
        return "medium"
    else:
        return "low"
