# -*- coding: utf-8 -*-

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import json
import pandas as pd
from typing import Any

from storage.google_sheets import (
    get_gs_client,
    get_spreadsheet,
    read_table,
)

from insights.student_consolidator import generate_consolidated_summary

# =====================================================
# FASTAPI APP
# =====================================================

app = FastAPI(
    title="AI Student Intelligence API",
    description="Production-grade hybrid academic intelligence service",
    version="2.5.1",
)

# =====================================================
# REQUEST SCHEMAS
# =====================================================

class StudentSummaryRequest(BaseModel):
    student_id: str


class LiveStudentSummaryRequest(BaseModel):
    student_id: str
    llm_provider: str = "ollama"

# =====================================================
# NORMALIZATION HELPERS
# =====================================================

def normalize(value: Any):
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        v = value.strip()
        try:
            return json.loads(v)
        except Exception:
            return v
    return value


def normalize_student_id(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or "student_id" not in df.columns:
        return df
    df = df.copy()
    df["student_id"] = df["student_id"].astype(str).str.strip()
    return df


def df_to_records(df: pd.DataFrame):
    if df is None or df.empty:
        return []
    records = json.loads(df.to_json(orient="records"))
    return [{k: normalize(v) for k, v in row.items()} for row in records]

# =====================================================
# DATA LOADERS (SAFE)
# =====================================================

def load_tables():
    client = get_gs_client()
    sheet = get_spreadsheet(client)

    analytics = normalize_student_id(read_table(sheet, "subject_analytics"))
    summaries = normalize_student_id(read_table(sheet, "subject_summaries"))
    insights = normalize_student_id(read_table(sheet, "subject_insights"))
    consolidated = normalize_student_id(read_table(sheet, "student_consolidated_latest"))
    validated = normalize_student_id(read_table(sheet, "validated_results"))

    return analytics, summaries, insights, consolidated, validated


def get_student_metadata(validated: pd.DataFrame, student_id: str):
    sid = student_id.strip()

    if validated is None or validated.empty:
        return {"student_name": "", "grade": ""}

    row = validated[validated["student_id"] == sid]
    if row.empty:
        return {"student_name": "", "grade": ""}

    r = row.iloc[0]
    return {
        "student_name": normalize(r.get("Name", "")),
        "grade": int(r.get("grade")),
    }

# =====================================================
# CACHED FLOW
# =====================================================

def load_cached(student_id: str):
    analytics, summaries, insights, consolidated, validated = load_tables()
    sid = student_id.strip()

    if analytics.empty or summaries.empty or validated.empty:
        raise HTTPException(
            status_code=404,
            detail="Base academic data not available. Run pipeline first.",
        )

    a = analytics[analytics["student_id"] == sid]
    s = summaries[summaries["student_id"] == sid]
    i = insights[insights["student_id"] == sid]
    c = consolidated[consolidated["student_id"] == sid]

    if a.empty or s.empty or c.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No cached data found for student_id={sid}",
        )

    meta = get_student_metadata(validated, sid)
    row = c.iloc[0]

    explain_map = {
        r["subject"]: {
            "explanation_summary": normalize(r.get("explanation_summary")),
            "key_evidence_points": normalize(r.get("key_evidence_points")) or [],
            "confidence_in_insight": normalize(r.get("confidence_in_insight")),
        }
        for r in df_to_records(i)
    }

    subject_insights = [
        {**subj, "explainability": explain_map.get(subj["subject"], {})}
        for subj in df_to_records(s)
    ]

    return {
        "student_id": sid,
        "student_name": meta["student_name"],
        "grade": meta["grade"],
        "overall_summary": normalize(row.get("overall_summary")),
        "recommended_next_steps": normalize(row.get("recommended_next_steps")),
        "numerical_performance": df_to_records(
            a[
                ["subject", "average_score", "latest_score", "trend", "risk_flag"]
            ].sort_values("subject")
        ),
        "subject_summaries": subject_insights,
        "mode": "cached",
        "llm_provider_used": row.get("llm_provider", "ollama"),
    }

# =====================================================
# API ENDPOINTS
# =====================================================

@app.post("/student-summary")
def get_cached_summary(req: StudentSummaryRequest):
    student_id = req.student_id.strip()
    if not student_id:
        raise HTTPException(status_code=400, detail="student_id is required")
    return load_cached(student_id)


@app.post("/student-summary/live")
def get_live_summary(req: LiveStudentSummaryRequest):
    student_id = req.student_id.strip()
    if not student_id:
        raise HTTPException(status_code=400, detail="student_id is required")

    os.environ["LLM_PROVIDER"] = req.llm_provider.lower()

    analytics, summaries, _, _, validated = load_tables()

    a = analytics[analytics["student_id"] == student_id]
    s = summaries[summaries["student_id"] == student_id]

    if a.empty or s.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No base data found for student_id={student_id}",
        )

    meta = get_student_metadata(validated, student_id)

    consolidated = generate_consolidated_summary(
        student_id=student_id,
        grade=meta["grade"],
        analytics=df_to_records(a),
        summaries=df_to_records(s),
        llm_provider=req.llm_provider,
    )

    return {
        **consolidated,
        "student_id": student_id,
        "student_name": meta["student_name"],
        "grade": meta["grade"],
        "mode": "live",
        "llm_provider_used": req.llm_provider,
    }


@app.get("/")
def health():
    return {"status": "ok"}
