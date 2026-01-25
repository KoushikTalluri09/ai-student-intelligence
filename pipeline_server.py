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
    version="2.4.0",
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
# NORMALIZATION
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


def df_to_records(df: pd.DataFrame):
    if df is None or df.empty:
        return []
    records = json.loads(df.to_json(orient="records"))
    return [{k: normalize(v) for k, v in row.items()} for row in records]

# =====================================================
# DATA LOADERS
# =====================================================

def load_tables():
    client = get_gs_client()
    sheet = get_spreadsheet(client)

    analytics = read_table(sheet, "subject_analytics")
    summaries = read_table(sheet, "subject_summaries")
    insights = read_table(sheet, "subject_insights")
    consolidated = read_table(sheet, "student_consolidated_latest")
    validated = read_table(sheet, "validated_results")

    if analytics.empty or summaries.empty or consolidated.empty or validated.empty:
        raise RuntimeError("One or more required sheets are empty")

    return analytics, summaries, insights, consolidated, validated


def get_student_metadata(validated: pd.DataFrame, student_id: str):
    row = validated[validated["student_id"] == student_id]
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

    a = analytics[analytics["student_id"] == student_id]
    s = summaries[summaries["student_id"] == student_id]
    i = insights[insights["student_id"] == student_id]
    c = consolidated[consolidated["student_id"] == student_id]

    if a.empty or s.empty or c.empty:
        raise ValueError(f"No cached data found for student_id={student_id}")

    meta = get_student_metadata(validated, student_id)
    row = c.iloc[0]

    explain_map = {
        r["subject"]: {
            "explanation_summary": normalize(r.get("explanation_summary")),
            "key_evidence_points": normalize(r.get("key_evidence_points")) or [],
            "confidence_in_insight": normalize(r.get("confidence_in_insight")),
        }
        for r in df_to_records(i)
    }

    subject_insights = []
    for subj in df_to_records(s):
        subject_insights.append(
            {
                **subj,
                "explainability": explain_map.get(subj["subject"], {}),
            }
        )

    return {
        "student_id": student_id,
        "student_name": meta["student_name"],
        "grade": meta["grade"],
        "overall_summary": normalize(row.get("overall_summary")),
        "recommended_next_steps": normalize(row.get("recommended_next_steps")),
        "numerical_performance": df_to_records(
            a[
                [
                    "subject",
                    "average_score",
                    "latest_score",
                    "trend",
                    "risk_flag",
                ]
            ].sort_values("subject")
        ),
        "subject_summaries": subject_insights,
        "mode": "cached",
        "llm_provider_used": row.get("llm_provider", "ollama"),
    }

# =====================================================
# ENDPOINTS
# =====================================================

@app.post("/student-summary")
def get_cached_summary(req: StudentSummaryRequest):
    try:
        return load_cached(req.student_id.strip())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/student-summary/live")
def get_live_summary(req: LiveStudentSummaryRequest):
    try:
        student_id = req.student_id.strip()
        os.environ["LLM_PROVIDER"] = req.llm_provider.lower()

        analytics, summaries, _, _, validated = load_tables()

        a = analytics[analytics["student_id"] == student_id]
        s = summaries[summaries["student_id"] == student_id]

        if a.empty or s.empty:
            raise ValueError(f"No data found for student_id={student_id}")

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

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def health():
    return {"status": "ok"}
