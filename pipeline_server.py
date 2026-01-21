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
    version="2.3.0",
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
# HARD NORMALIZER (CRITICAL)
# =====================================================

def normalize(value: Any):
    """
    Absolute normalization:
    - JSON string → parsed
    - Python literal string → parsed
    - list/dict → untouched
    - None / NaN → empty
    - plain string → string
    """

    if value is None:
        return ""

    if isinstance(value, float) and pd.isna(value):
        return ""

    if isinstance(value, (list, dict)):
        return value

    if isinstance(value, str):
        v = value.strip()

        # Attempt JSON parse
        try:
            parsed = json.loads(v)
            return parsed
        except Exception:
            pass

        # Attempt Python literal list/dict
        if (v.startswith("[") and v.endswith("]")) or (v.startswith("{") and v.endswith("}")):
            try:
                return json.loads(v.replace("'", '"'))
            except Exception:
                pass

        return v

    return value


def df_to_records(df: pd.DataFrame):
    if df is None or df.empty:
        return []

    records = json.loads(df.to_json(orient="records"))

    return [
        {k: normalize(v) for k, v in row.items()}
        for row in records
    ]

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

    if analytics.empty or summaries.empty or consolidated.empty:
        raise RuntimeError("One or more required sheets are empty")

    return analytics, summaries, insights, consolidated


def load_cached(student_id: str):
    analytics, summaries, insights, consolidated = load_tables()

    a = analytics[analytics["student_id"] == student_id]
    s = summaries[summaries["student_id"] == student_id]
    i = insights[insights["student_id"] == student_id]
    c = consolidated[consolidated["student_id"] == student_id]

    if a.empty or s.empty or c.empty:
        raise ValueError(f"No cached data found for student_id={student_id}")

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
        "grade": int(row["grade"]),
        "overall_summary": normalize(row.get("overall_summary")),
        "key_strengths": normalize(row.get("key_strengths")),
        "areas_to_improve": normalize(row.get("areas_to_improve")),
        "recommended_next_steps": normalize(row.get("recommended_next_steps")),
        "confidence_note": normalize(row.get("confidence_note")),
        "numerical_performance": df_to_records(
            a[
                [
                    "subject",
                    "average_score",
                    "latest_score",
                    "trend",
                    "performance_band",
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
        student_id = req.student_id.strip()
        if not student_id:
            raise HTTPException(status_code=400, detail="student_id required")

        return load_cached(student_id)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/student-summary/live")
def get_live_summary(req: LiveStudentSummaryRequest):
    try:
        student_id = req.student_id.strip()
        if not student_id:
            raise HTTPException(status_code=400, detail="student_id required")

        llm_provider = req.llm_provider.lower()
        os.environ["LLM_PROVIDER"] = llm_provider

        analytics, summaries, _, _ = load_tables()

        a = analytics[analytics["student_id"] == student_id]
        s = summaries[summaries["student_id"] == student_id]

        if a.empty or s.empty:
            raise ValueError(f"No data found for student_id={student_id}")

        grade = int(a.iloc[0]["grade"])

        consolidated = generate_consolidated_summary(
            student_id=student_id,
            grade=grade,
            analytics=df_to_records(a),
            summaries=df_to_records(s),
            llm_provider=llm_provider,
        )

        return {
            **consolidated,
            "student_id": student_id,
            "grade": grade,
            "mode": "live",
            "llm_provider_used": llm_provider,
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def health():
    return {
        "status": "ok",
        "service": "AI Student Intelligence",
        "mode": "hybrid",
    }
