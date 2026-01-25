# -*- coding: utf-8 -*-

"""
PHASE 0 — RAW DATA INGESTION & VALIDATION
========================================

Source of truth  : raw_student_scores (Google Sheets)
Validated output : validated_results (Google Sheets)
"""

from datetime import timezone
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
    "Name",               # ✅ ADDED (metadata passthrough)
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
# TYPE COERCION
# ============================================================

def coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["student_id"] = df["student_id"].astype(str)
    df["Name"] = df["Name"].astype(str)          # ✅ SAFE PASS-THROUGH
    df["grade"] = pd.to_numeric(df["grade"], errors="coerce")
    df["attempt_number"] = pd.to_numeric(df["attempt_number"], errors="coerce")
    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    df["max_score"] = pd.to_numeric(df["max_score"], errors="coerce")
    df["exam_date"] = pd.to_datetime(df["exam_date"], errors="coerce")

    return df

# ============================================================
# ROW-LEVEL VALIDATION
# ============================================================

def validate_rows(df: pd.DataFrame):
    errors = []
    now_utc = pd.Timestamp.now(tz=timezone.utc)

    for idx, row in df.iterrows():
        try:
            if not row["student_id"].strip():
                raise ValueError("student_id missing")

            if pd.isna(row["grade"]) or not (1 <= int(row["grade"]) <= 12):
                raise ValueError("grade out of range")

            if not row["subject"].strip():
                raise ValueError("invalid subject")

            if row["exam_type"] not in ALLOWED_EXAM_TYPES:
                raise ValueError("invalid exam_type")

            if pd.isna(row["attempt_number"]) or int(row["attempt_number"]) < 1:
                raise ValueError("invalid attempt_number")

            if pd.isna(row["max_score"]) or row["max_score"] <= 0:
                raise ValueError("invalid max_score")

            if pd.isna(row["score"]) or row["score"] < 0 or row["score"] > row["max_score"]:
                raise ValueError("score out of range")

            exam_date = row["exam_date"]
            if pd.isna(exam_date):
                raise ValueError("invalid exam_date")

            exam_date_utc = (
                exam_date.tz_convert("UTC")
                if exam_date.tzinfo is not None
                else exam_date.tz_localize("UTC")
            )

            if exam_date_utc > now_utc:
                raise ValueError("exam_date in future")

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
# UNIQUENESS
# ============================================================

def validate_uniqueness(df: pd.DataFrame):
    dupes = df.duplicated(
        subset=["student_id", "exam_id", "attempt_number"]
    )
    if dupes.any():
        raise ValueError("Duplicate exam attempts detected")

# ============================================================
# PIPELINE ENTRY POINT
# ============================================================

def run_validation():
    client = get_gs_client()
    spreadsheet = get_spreadsheet(client)

    df = read_table(spreadsheet, "raw_student_scores")

    if df.empty:
        raise RuntimeError("raw_student_scores is empty")

    validate_schema(df)
    df = coerce_types(df)

    row_errors = validate_rows(df)
    if row_errors:
        raise ValueError(f"Row validation failed: {row_errors[:5]}")

    validate_uniqueness(df)

    df["exam_date"] = df["exam_date"].dt.strftime("%Y-%m-%d")

    df = df.sort_values(
        by=["student_id", "exam_id", "attempt_number"],
        ignore_index=True,
    )

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
