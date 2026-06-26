# -*- coding: utf-8 -*-

"""
AI STUDENT INTELLIGENCE — MASTER PIPELINE RUNNER
================================================

Runs ALL pipeline phases end-to-end using Google Sheets
as the system of record.

Phases:
  PHASE 0 → Raw validation
  PHASE 1 → Subject analytics
  PHASE 2 → Subject insights
  PHASE 3 → LLM subject summaries
  PHASE 4 → Per-student consolidation

Usage:
  python pipeline_runner.py <llm_provider> <llm_row_limit>

Example:
  python pipeline_runner.py ollama 5
"""

from datetime import datetime, timezone
import sys
import os
import time
import traceback

# ============================================================
# IMPORT PIPELINE PHASES (REAL FILES ONLY)
# ============================================================

from analytics.validators import run_validation
from analytics.student_analyzer import analyze_students
from insights.insight_engine import derive_insights
from llm.summary_generator import run_llm
from insights.student_consolidator import run_student_consolidation

from storage.google_sheets import (
    get_gs_client,
    get_spreadsheet,
    read_table,
)

# ============================================================
# VERSION
# ============================================================

PIPELINE_VERSION = "1.0.0"

# ============================================================
# LOGGING
# ============================================================

def log(message: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] {message}")

# ============================================================
# PIPELINE RUNNER
# ============================================================

def run_full_pipeline(llm_provider: str, llm_row_limit: int):
    """
    Executes the full AI Student Intelligence pipeline safely.
    """

    log(f"Starting AI Student Intelligence pipeline v{PIPELINE_VERSION}")
    log(f"LLM Provider: {llm_provider}")

    # --------------------------------------------------------
    # APPLY LLM PROVIDER GLOBALLY
    # --------------------------------------------------------

    os.environ["LLM_PROVIDER"] = llm_provider.lower()

    try:
        # ====================================================
        # PHASE 0 — VALIDATION
        # ====================================================

        log("PHASE 0 | Validating raw_student_scores -> validated_results")
        run_validation()
        log("PHASE 0 | SUCCESS")

        # ====================================================
        # PHASE 1 — ANALYTICS
        # ====================================================

        log("PHASE 1 | Generating subject analytics")
        analyze_students()
        log("PHASE 1 | SUCCESS")

        # ====================================================
        # PHASE 2 — INSIGHTS
        # ====================================================

        log("PHASE 2 | Generating subject insights")
        derive_insights()
        log("PHASE 2 | SUCCESS")

        # ====================================================
        # PHASE 3 — LLM SUMMARIES
        # ====================================================

        log(f"PHASE 3 | Generating LLM summaries (limit={llm_row_limit})")
        os.environ["LLM_ROW_LIMIT"] = str(llm_row_limit)
        run_llm()
        log("PHASE 3 | SUCCESS")

        # ====================================================
        # PHASE 4 — STUDENT CONSOLIDATION
        # ====================================================

        log("PHASE 4 | Consolidating per-student summaries")

        client = get_gs_client()
        spreadsheet = get_spreadsheet(client)

        analytics_df = read_table(spreadsheet, "subject_analytics")
        summaries_df = read_table(spreadsheet, "subject_summaries")

        if analytics_df.empty:
            raise RuntimeError("subject_analytics sheet is empty")

        # Only consolidate students who have BOTH analytics and LLM summaries.
        # Skipping the rest avoids one Google Sheets connection set per missing student.
        analytics_ids = set(analytics_df["student_id"].astype(str).str.strip().unique())
        summary_ids = (
            set(summaries_df["student_id"].astype(str).str.strip().unique())
            if not summaries_df.empty
            else set()
        )
        student_ids = sorted(analytics_ids & summary_ids)

        log(f"PHASE 4 | Students with summaries ready: {len(student_ids)}")

        consolidated = 0
        for sid in student_ids:
            run_student_consolidation(sid)
            consolidated += 1
            time.sleep(2)  # respect Google Sheets read-quota between students

        log(f"PHASE 4 | SUCCESS | Students consolidated: {consolidated}")

        # ====================================================
        # PIPELINE COMPLETE
        # ====================================================

        log("PIPELINE COMPLETED SUCCESSFULLY")

    except Exception as e:
        log("PIPELINE FAILED")
        log(str(e))
        traceback.print_exc()
        sys.exit(1)

# ============================================================
# PER-STUDENT ENTRY POINT
# ============================================================

def run_pipeline_for_student(student_id: str, llm_provider: str = "ollama"):
    """
    Run all five pipeline phases for a single student.

    Results are upserted into the shared Google Sheets output tabs so
    other students' rows are never overwritten.
    """
    import pandas as pd

    from analytics.validators import coerce_types, validate_schema, validate_rows
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
    from insights.insight_engine import (
        derive_primary_issue,
        derive_secondary_issue,
        derive_focus_area,
        build_explanation,
    )
    from llm.summary_generator import generate_summary
    from insights.student_consolidator import run_student_consolidation
    from storage.google_sheets import (
        get_gs_client,
        get_spreadsheet,
        read_table,
        upsert_table,
    )

    os.environ["LLM_PROVIDER"] = llm_provider.lower()
    sid = student_id.strip()
    log(f"Per-student pipeline | student={sid} | provider={llm_provider}")

    client = get_gs_client()
    spreadsheet = get_spreadsheet(client)

    # ── PHASE 0: VALIDATE ────────────────────────────────────────────
    log(f"PHASE 0 | Validating raw data for {sid}")
    raw_df = read_table(spreadsheet, "raw_student_scores")
    raw_df["student_id"] = raw_df["student_id"].astype(str).str.strip()
    student_raw = raw_df[raw_df["student_id"] == sid].copy()
    if student_raw.empty:
        raise ValueError(f"No raw data found for student {sid} in raw_student_scores")
    validate_schema(student_raw)
    student_raw = coerce_types(student_raw)
    errors = validate_rows(student_raw)
    if errors:
        raise ValueError(f"Validation errors for {sid}: {errors}")
    student_raw["exam_date"] = student_raw["exam_date"].dt.strftime("%Y-%m-%d")
    student_raw = student_raw.sort_values(
        ["student_id", "exam_id", "attempt_number"], ignore_index=True
    )
    upsert_table(
        spreadsheet, "validated_results", student_raw,
        key_columns=["student_id", "exam_id", "attempt_number"],
    )
    log(f"PHASE 0 | SUCCESS | {len(student_raw)} rows validated")

    # ── PHASE 1: ANALYTICS ───────────────────────────────────────────
    log(f"PHASE 1 | Computing analytics for {sid}")
    val_df = read_table(spreadsheet, "validated_results")
    val_df["student_id"] = val_df["student_id"].astype(str).str.strip()
    sv = val_df[val_df["student_id"] == sid].copy()
    sv["exam_date"] = pd.to_datetime(sv["exam_date"], errors="coerce")
    sv["score"] = pd.to_numeric(sv["score"], errors="coerce")
    sv = sv.dropna(subset=["student_id", "subject", "score", "exam_date"])
    sv = sv.sort_values("exam_date")

    analytics_rows = []
    for (s_id, grade, subject), grp in sv.groupby(
        ["student_id", "grade", "subject"], dropna=True
    ):
        scores = grp["score"].astype(float)
        if scores.empty or scores.isna().all():
            continue
        _trend = calculate_trend(scores)
        _avg = round(float(scores.mean()), 2)
        analytics_rows.append({
            "student_id":           s_id,
            "grade":                int(grade),
            "subject":              subject,
            "attempt_count":        len(scores),
            "average_score":        _avg,
            "latest_score":         float(scores.iloc[-1]),
            "recent_avg_score":     recent_average(scores),
            "trend":                _trend,
            "improvement_velocity": improvement_velocity(scores),
            "consistency_score":    consistency_score(scores),
            "volatility_level":     volatility_level(scores),
            "mock_vs_real_gap":     mock_vs_real_gap(grp),
            "performance_band":     performance_band(_avg),
            "risk_flag":            risk_flag(_avg, _trend),
            "data_confidence_level": data_confidence(len(scores)),
        })

    if not analytics_rows:
        raise ValueError(f"No analytics generated for {sid}")
    analytics_df = pd.DataFrame(analytics_rows)
    upsert_table(
        spreadsheet, "subject_analytics", analytics_df,
        key_columns=["student_id", "subject"],
    )
    log(f"PHASE 1 | SUCCESS | {len(analytics_df)} records")

    # ── PHASE 2: INSIGHTS ────────────────────────────────────────────
    log(f"PHASE 2 | Deriving insights for {sid}")
    analytics_df["average_score"] = pd.to_numeric(
        analytics_df["average_score"], errors="coerce"
    )
    analytics_df["mock_vs_real_gap"] = pd.to_numeric(
        analytics_df["mock_vs_real_gap"], errors="coerce"
    )
    analytics_df = analytics_df.dropna(subset=["average_score"])

    insight_rows = []
    for row in analytics_df.itertuples(index=False):
        primary_issue, root_cause, urgency = derive_primary_issue(
            row.average_score, row.trend
        )
        secondary_issue = derive_secondary_issue(row.volatility_level, row.mock_vs_real_gap)
        focus_area = derive_focus_area(urgency)
        explanation = build_explanation(row, primary_issue)
        insight_rows.append({
            "student_id":                  row.student_id,
            "grade":                       int(row.grade),
            "subject":                     row.subject,
            "primary_issue":               primary_issue,
            "secondary_issue":             secondary_issue,
            "root_cause_category":         root_cause,
            "academic_risk_level":         row.risk_flag,
            "urgency_level":               urgency,
            "recommended_focus_area":      focus_area,
            "teacher_intervention_needed": "yes" if urgency == "high" else "no",
            "explanation_summary":         explanation["explanation_summary"],
            "key_evidence_points":         "\n".join(
                f"- {p}" for p in explanation["key_evidence_points"]
            ),
            "confidence_in_insight":       explanation["confidence_note"],
            "summary_signal": (
                f"{row.performance_band} performer with {row.risk_flag} risk"
            ),
        })

    if not insight_rows:
        raise ValueError(f"No insights generated for {sid}")
    insight_df = pd.DataFrame(insight_rows)
    upsert_table(
        spreadsheet, "subject_insights", insight_df,
        key_columns=["student_id", "subject"],
    )
    log(f"PHASE 2 | SUCCESS | {len(insight_df)} records")

    # ── PHASE 3: LLM SUMMARIES ───────────────────────────────────────
    log(f"PHASE 3 | Generating LLM summaries for {sid}")
    summary_rows = []
    for row in insight_df.to_dict(orient="records"):
        summary = generate_summary(row, provider=llm_provider)
        summary_rows.append({
            "student_id":        sid,
            "grade":             row["grade"],
            "subject":           row["subject"],
            "performance_summary": summary.get("performance_summary", ""),
            "improvement_plan":  summary.get("improvement_plan", ""),
            "motivation_note":   summary.get("motivation_note", ""),
            "confidence_note":   summary.get("confidence_note", "low"),
            "llm_provider":      llm_provider,
        })

    if not summary_rows:
        raise ValueError(f"No LLM summaries generated for {sid}")
    summaries_df = pd.DataFrame(summary_rows)
    upsert_table(
        spreadsheet, "subject_summaries", summaries_df,
        key_columns=["student_id", "subject"],
    )
    log(f"PHASE 3 | SUCCESS | {len(summaries_df)} summaries")

    # ── PHASE 4: CONSOLIDATION ────────────────────────────────────────
    log(f"PHASE 4 | Consolidating report for {sid}")
    run_student_consolidation(sid)
    log(f"PHASE 4 | SUCCESS")
    log(f"Per-student pipeline COMPLETE | {sid}")

# ============================================================
# CLI ENTRY
# ============================================================

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(
            "Usage: python pipeline_runner.py <llm_provider> <llm_row_limit>\n"
            "Example: python pipeline_runner.py ollama 5"
        )
        sys.exit(1)

    provider = sys.argv[1]
    row_limit = int(sys.argv[2])

    run_full_pipeline(provider, row_limit)
