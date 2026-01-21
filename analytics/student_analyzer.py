# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np

from analytics.metrics import (
    calculate_trend,
    improvement_velocity,
    consistency_score,
    mock_vs_real_gap,
    performance_band,
    volatility_level,
    recent_average,
    risk_flag,
    data_confidence,
)

from storage.google_sheets import (
    get_gs_client,
    get_spreadsheet,
    read_table,
    write_table,
)


def analyze_students():
    """
    PHASE 1 — SUBJECT ANALYTICS (PRODUCTION-GRADE)

    - Hardens score handling (string → numeric)
    - Drops invalid attempts safely
    - Guarantees pipeline never crashes due to dirty data
    """

    # -------------------------------------------------
    # READ FROM GOOGLE SHEETS
    # -------------------------------------------------

    client = get_gs_client()
    spreadsheet = get_spreadsheet(client)

    df = read_table(spreadsheet, "validated_results")

    if df.empty:
        raise RuntimeError("Validated dataset is empty in Google Sheets")

    # -------------------------------------------------
    # HARD DATA SANITIZATION (CRITICAL FIX)
    # -------------------------------------------------

    # Dates
    df["exam_date"] = pd.to_datetime(df["exam_date"], errors="coerce")

    # Scores → numeric (THIS FIXES YOUR ERROR)
    df["score"] = pd.to_numeric(df["score"], errors="coerce")

    # Drop rows where core fields are invalid
    df = df.dropna(subset=["student_id", "subject", "score", "exam_date"])

    # Ensure chronological order for trend logic
    df = df.sort_values("exam_date")

    results = []

    # -------------------------------------------------
    # ANALYTICS LOGIC (SAFE & UNCHANGED)
    # -------------------------------------------------

    grouped = df.groupby(["student_id", "grade", "subject"], dropna=True)

    for (student_id, grade, subject), group in grouped:
        scores = group["score"].astype(float)

        # Final guard — never compute on empty or all-NaN
        if scores.empty or scores.isna().all():
            continue

        attempt_count = len(scores)

        avg_score = round(scores.mean(), 2)
        latest_score = float(scores.iloc[-1])

        trend = calculate_trend(scores)

        record = {
            # Identity
            "student_id": student_id,
            "grade": int(grade),
            "subject": subject,

            # Volume
            "attempt_count": attempt_count,

            # Core performance
            "average_score": avg_score,
            "latest_score": latest_score,
            "recent_avg_score": recent_average(scores),

            # Trend & stability
            "trend": trend,
            "improvement_velocity": improvement_velocity(scores),
            "consistency_score": consistency_score(scores),
            "volatility_level": volatility_level(scores),

            # Exam behavior
            "mock_vs_real_gap": mock_vs_real_gap(group),

            # Interpretable signals
            "performance_band": performance_band(avg_score),
            "risk_flag": risk_flag(avg_score, trend),
            "data_confidence_level": data_confidence(attempt_count),
        }

        results.append(record)

    analytics_df = pd.DataFrame(results)

    if analytics_df.empty:
        raise RuntimeError("Phase 1 produced no analytics records")

    # -------------------------------------------------
    # WRITE BACK TO GOOGLE SHEETS
    # -------------------------------------------------

    write_table(
        spreadsheet=spreadsheet,
        table_name="subject_analytics",
        df=analytics_df,
    )

    print(
        f"Phase 1 complete | "
        f"Students analyzed: {analytics_df['student_id'].nunique()} | "
        f"Records generated: {len(analytics_df)}"
    )


if __name__ == "__main__":
    analyze_students()
