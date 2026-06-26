# -*- coding: utf-8 -*-

from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
import os
import json
import threading
import uuid as _uuid
import pandas as pd
from typing import Any, Optional

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

# In-memory pipeline job registry
_pipeline_jobs: dict = {}

# =====================================================
# REQUEST SCHEMAS
# =====================================================

class StudentSummaryRequest(BaseModel):
    student_id: str


class LiveStudentSummaryRequest(BaseModel):
    student_id: str
    llm_provider: str = "ollama"


class PipelineRunRequest(BaseModel):
    student_id: str = ""
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
    grade_raw = r.get("grade")
    try:
        grade_val = int(grade_raw)
    except (TypeError, ValueError):
        grade_val = ""
    return {
        "student_name": normalize(r.get("Name", "")),
        "grade": grade_val,
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
            "explanation_summary":   normalize(r.get("explanation_summary")),
            "key_evidence_points":   normalize(r.get("key_evidence_points")) or [],
            "confidence_in_insight": normalize(r.get("confidence_in_insight")),
            "recommended_focus_area": normalize(r.get("recommended_focus_area")),
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

@app.get("/student/exists/{student_id}")
def check_student_exists(student_id: str):
    """Check whether a student exists in validated_results and/or subject_analytics."""
    try:
        client = get_gs_client()
        sheet = get_spreadsheet(client)
        validated = normalize_student_id(read_table(sheet, "validated_results"))
        analytics = normalize_student_id(read_table(sheet, "subject_analytics"))
        sid = student_id.strip()
        in_validated = (
            not validated.empty
            and "student_id" in validated.columns
            and sid in validated["student_id"].values
        )
        in_analytics = (
            not analytics.empty
            and "student_id" in analytics.columns
            and sid in analytics["student_id"].values
        )
        return {
            "student_id": sid,
            "in_validated_results": in_validated,
            "in_subject_analytics": in_analytics,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def _start_pipeline_job(student_id: str = "", llm_provider: str = "ollama") -> str:
    """Shared helper: register a job, launch background thread, return job_id."""
    job_id = str(_uuid.uuid4())
    _pipeline_jobs[job_id] = {"status": "running", "error": ""}
    sid = student_id.strip()
    provider = llm_provider or "ollama"

    def _worker():
        try:
            from pipeline_runner import run_full_pipeline, run_pipeline_for_student
            if sid:
                run_pipeline_for_student(sid, provider)
            else:
                run_full_pipeline(provider, 999)
            _pipeline_jobs[job_id]["status"] = "done"
        except Exception as exc:
            _pipeline_jobs[job_id]["status"] = "failed"
            _pipeline_jobs[job_id]["error"] = str(exc)

    threading.Thread(target=_worker, daemon=True).start()
    return job_id


@app.post("/pipeline/run")
def start_pipeline(req: PipelineRunRequest):
    """Start a pipeline run in the background. Filters to one student when student_id is set."""
    job_id = _start_pipeline_job(req.student_id, req.llm_provider)
    return {"job_id": job_id, "status": "running"}


@app.post("/run-pipeline")
def run_pipeline_endpoint(req: Optional[PipelineRunRequest] = Body(default=None)):
    """Cloud-compatible pipeline trigger. Accepts optional student_id filter."""
    if req is None:
        req = PipelineRunRequest()
    job_id = _start_pipeline_job(req.student_id, req.llm_provider)
    return {"job_id": job_id, "status": "running"}


@app.get("/pipeline/status/{job_id}")
def get_pipeline_status(job_id: str):
    """Poll the status of a pipeline job."""
    if job_id not in _pipeline_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return _pipeline_jobs[job_id]


@app.get("/debug/env")
def debug_env():
    return {
        "GOOGLE_CREDENTIALS_BASE64_present": bool(os.getenv("GOOGLE_CREDENTIALS_BASE64")),
        "GOOGLE_SHEETS_CREDENTIALS_present": bool(os.getenv("GOOGLE_SHEETS_CREDENTIALS")),
        "all_env_keys": sorted(list(os.environ.keys()))
    }



@app.get("/")
def health():
    return {"status": "ok"}
