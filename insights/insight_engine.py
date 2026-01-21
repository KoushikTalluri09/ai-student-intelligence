# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np

from storage.google_sheets import (
    get_gs_client,
    get_spreadsheet,
    read_table,
    write_table,
)

# -------------------------------------------------
# REQUIRED INPUT COLUMNS
# -------------------------------------------------

REQUIRED_COLUMNS = {
    "student_id",
    "grade",
    "subject",
    "average_score",
    "trend",
    "volatility_level",
    "risk_flag",
    "data_confidence_level",
    "performance_band",
    "mock_vs_real_gap",
}

# -------------------------------------------------
# VALIDATION
# -------------------------------------------------

def _validate_input(df: pd.DataFrame):
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing required columns in analytics data: {missing}"
        )

# -------------------------------------------------
# SAFE COERCION (CRITICAL FIX)
# -------------------------------------------------

def _sanitize_analytics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensures all numeric columns are truly numeric.
    Prevents str < int crashes.
    """
    df = df.copy()

    df["average_score"] = pd.to_numeric(df["average_score"], errors="coerce")
    df["mock_vs_real_gap"] = pd.to_numeric(df["mock_vs_real_gap"], errors="coerce")

    # Drop rows that are now invalid
    df = df.dropna(subset=["average_score"])

    return df

# -------------------------------------------------
# INSIGHT LOGIC (UNCHANGED)
# -------------------------------------------------

def derive_primary_issue(avg, trend):
    avg = float(avg)

    if avg < 60 and trend == "declining":
        return (
            "Consistently low and declining performance",
            "Conceptual gaps with poor reinforcement",
            "high",
        )
    if avg < 60:
        return (
            "Low overall performance",
            "Weak foundational understanding",
            "medium",
        )
    if trend == "declining":
        return (
            "Performance regression",
            "Inconsistent preparation or focus",
            "medium",
        )
    return (
        "No major academic concern",
        "Healthy learning pattern",
        "low",
    )

def derive_secondary_issue(volatility, mock_gap):
    if volatility == "high":
        return "Highly inconsistent performance"
    if pd.notna(mock_gap) and mock_gap < -5:
        return "Exam pressure affecting real exam performance"
    return "None observed"

def derive_focus_area(urgency):
    if urgency == "high":
        return "Immediate concept revision and guided practice"
    if urgency == "medium":
        return "Structured revision and consistency building"
    return "Maintain current learning approach"

# -------------------------------------------------
# EXPLAINABILITY (TRUST LAYER)
# -------------------------------------------------

def build_explanation(row, primary_issue):
    signals = []

    signals.append(
        f"Average score is {row.average_score}, classified as {row.performance_band}"
    )

    signals.append(
        f"Score trend is '{row.trend}', indicating learning direction over time"
    )

    if row.volatility_level == "high":
        signals.append("Scores show high volatility, suggesting inconsistency")

    if pd.notna(row.mock_vs_real_gap) and row.mock_vs_real_gap < -5:
        signals.append(
            "Mock scores significantly higher than real exam scores, indicating exam pressure"
        )

    signals.append(
        f"Academic risk flagged as '{row.risk_flag}' with {row.data_confidence_level} confidence"
    )

    return {
        "explanation_summary": primary_issue,
        "key_evidence_points": signals,
        "confidence_note": row.data_confidence_level,
    }

# -------------------------------------------------
# PHASE 2 ENTRY POINT
# -------------------------------------------------

def derive_insights():
    """
    PHASE 2 — SUBJECT INSIGHTS + EXPLAINABILITY
    """

    client = get_gs_client()
    spreadsheet = get_spreadsheet(client)

    df = read_table(spreadsheet, "subject_analytics")

    if df.empty:
        raise RuntimeError("subject_analytics sheet is empty")

    _validate_input(df)
    df = _sanitize_analytics(df)

    insights = []

    for row in df.itertuples(index=False):
        primary_issue, root_cause, urgency = derive_primary_issue(
            row.average_score,
            row.trend,
        )

        secondary_issue = derive_secondary_issue(
            row.volatility_level,
            row.mock_vs_real_gap,
        )

        focus_area = derive_focus_area(urgency)

        explanation = build_explanation(row, primary_issue)

        teacher_needed = "yes" if urgency == "high" else "no"
        summary_signal = f"{row.performance_band} performer with {row.risk_flag} risk"

        insights.append(
            {
                "student_id": row.student_id,
                "grade": int(row.grade),
                "subject": row.subject,

                "primary_issue": primary_issue,
                "secondary_issue": secondary_issue,
                "root_cause_category": root_cause,

                "academic_risk_level": row.risk_flag,
                "urgency_level": urgency,

                "recommended_focus_area": focus_area,
                "teacher_intervention_needed": teacher_needed,

                # Explainability
                "explanation_summary": explanation["explanation_summary"],
                "key_evidence_points": "\n".join(
                f"- {point}" for point in explanation["key_evidence_points"]
                ),

                "confidence_in_insight": explanation["confidence_note"],

                "summary_signal": summary_signal,
            }
        )

    insight_df = pd.DataFrame(insights)

    if insight_df.empty:
        raise RuntimeError("Phase 2 failed: no insights generated")

    write_table(
        spreadsheet=spreadsheet,
        table_name="subject_insights",
        df=insight_df,
    )

    print(
        f"Phase 2 complete | "
        f"Students covered: {insight_df['student_id'].nunique()} | "
        f"Insights generated: {len(insight_df)}"
    )

# -------------------------------------------------
# MAIN
# -------------------------------------------------

if __name__ == "__main__":
    derive_insights()

