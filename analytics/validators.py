# -*- coding: utf-8 -*-

"""
PHASE 0 — RAW DATA INGESTION & VALIDATION
========================================

Source of truth  : raw_student_scores (Google Sheets)
Validated output : validated_results (Google Sheets)

Responsibilities:
- Schema enforcement
- Type coercion
- Domain validation
- Temporal validation (UTC-safe)
- Uniqueness enforcement
- Google Sheets–safe serialization

Design principles:
- Fail fast, fail loud
- Never mutate raw source
- Deterministic, auditable output
"""

from datetime import datetime, timezone
import pandas as pd

from storage.google_sheets import (
    get_gs_client,
    get_spreadsheet,
    read_table,
    write_table,
)

# ============================================================
# SCHEMA CONTRACT
# ============================================================

REQUIRED_COLUMNS = [
    "student_id",
    "grade",
    "subject",
    "exam_id",
    "exam_type",
    "attempt_number",
    "score",
    "max_score",
    "exam_date",
]

ALLOWED_EXAM_TYPES = {"mock", "real"}

# ============================================================
# SCHEMA VALIDATION
# ============================================================

def validate_schema(df: pd.DataFrame):
    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    extra = set(df.columns) - set(REQUIRED_COLUMNS)

    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    if extra:
        raise ValueError(
            f"Unexpected columns found (schema drift): {sorted(extra)}"
        )

# ============================================================
# TYPE COERCION (CRITICAL)
# ============================================================

def coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["student_id"] = df["student_id"].astype(str)
    df["grade"] = pd.to_numeric(df["grade"], errors="coerce")
    df["attempt_number"] = pd.to_numeric(df["attempt_number"], errors="coerce")
    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    df["max_score"] = pd.to_numeric(df["max_score"], errors="coerce")
    df["exam_date"] = pd.to_datetime(df["exam_date"], errors="coerce")

    return df

# ============================================================
# ROW-LEVEL VALIDATION (UTC SAFE)
# ============================================================

def validate_rows(df: pd.DataFrame):
    errors = []
    now_utc = pd.Timestamp.now(tz=timezone.utc)

    for idx, row in df.iterrows():
        try:
            # ---- Identity ----
            if not isinstance(row["student_id"], str) or not row["student_id"].strip():
                raise ValueError("student_id missing or invalid")

            # ---- Grade ----
            if pd.isna(row["grade"]) or not (1 <= int(row["grade"]) <= 12):
                raise ValueError("grade out of range (1–12)")

            # ---- Subject ----
            if not isinstance(row["subject"], str) or not row["subject"].strip():
                raise ValueError("invalid subject")

            # ---- Exam type ----
            if row["exam_type"] not in ALLOWED_EXAM_TYPES:
                raise ValueError("invalid exam_type")

            # ---- Attempt ----
            if pd.isna(row["attempt_number"]) or int(row["attempt_number"]) < 1:
                raise ValueError("attempt_number < 1")

            # ---- Scores ----
            if pd.isna(row["max_score"]) or row["max_score"] <= 0:
                raise ValueError("max_score must be > 0")

            if pd.isna(row["score"]) or row["score"] < 0 or row["score"] > row["max_score"]:
                raise ValueError("score outside valid range")

            # ---- Exam date ----
            exam_date = row["exam_date"]
            if pd.isna(exam_date):
                raise ValueError("exam_date is invalid or missing")

            exam_date_utc = (
                exam_date.tz_convert("UTC")
                if exam_date.tzinfo is not None
                else exam_date.tz_localize("UTC")
            )

            if exam_date_utc > now_utc:
                raise ValueError("exam_date is in the future")

        except Exception as e:
            errors.append(
                {
                    "row_index": int(idx),
                    "student_id": row.get("student_id"),
                    "error": str(e),
                }
            )

    return errors

# ============================================================
# UNIQUENESS VALIDATION
# ============================================================

def validate_uniqueness(df: pd.DataFrame):
    dupes = df.duplicated(
        subset=["student_id", "exam_id", "attempt_number"]
    )
    if dupes.any():
        raise ValueError(
            "Duplicate rows detected for (student_id, exam_id, attempt_number)"
        )

# ============================================================
# PIPELINE ENTRY POINT
# ============================================================

def run_validation():
    """
    Phase 0 execution:
    - Read raw_student_scores
    - Validate & normalize
    - Write validated_results
    """

    client = get_gs_client()
    spreadsheet = get_spreadsheet(client)

    # ---- READ RAW DATA ----
    df = read_table(spreadsheet, "raw_student_scores")

    if df.empty:
        raise RuntimeError("raw_student_scores sheet is empty")

    # ---- VALIDATION ----
    validate_schema(df)
    df = coerce_types(df)

    row_errors = validate_rows(df)
    if row_errors:
        raise ValueError(f"Row validation failed. Sample errors: {row_errors[:5]}")

    validate_uniqueness(df)

    # ---- FINAL NORMALIZATION FOR GOOGLE SHEETS ----
    df["exam_date"] = df["exam_date"].dt.strftime("%Y-%m-%d")

    # ---- DETERMINISTIC ORDER ----
    df = df.sort_values(
        by=["student_id", "exam_id", "attempt_number"],
        ignore_index=True,
    )

    # ---- WRITE VALIDATED DATA ----
    write_table(
        spreadsheet=spreadsheet,
        table_name="validated_results",
        df=df,
    )

    print(f"Phase 0 complete | Rows validated: {len(df)}")

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    run_validation()
