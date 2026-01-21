# -*- coding: utf-8 -*-

"""
PHASE 4 — PER-STUDENT CONSOLIDATED ACADEMIC SUMMARY
=================================================

Consumes:
- subject_analytics
- subject_summaries

Produces:
- student_consolidated_latest (UPSERT)
- student_consolidated_history (APPEND)

Guarantees:
- UTF-8 safe
- Deterministic LLM provider selection
- Hard failure if required API key missing
- Pipeline-safe (one student never breaks batch)
- Production-grade, idempotent writes
"""

import os
import json
import time
from typing import Dict, List, Optional

import pandas as pd
from dotenv import load_dotenv

from storage.google_sheets import (
    get_gs_client,
    get_spreadsheet,
    read_table,
    append_table,
    upsert_table,
)

# ============================================================
# CONFIG
# ============================================================

load_dotenv()

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 3

# ============================================================
# SYSTEM PROMPT (ASCII ONLY)
# ============================================================

SYSTEM_PROMPT = (
    "You are a senior academic advisor.\n"
    "Generate a consolidated academic assessment across subjects.\n"
    "Use ONLY provided data.\n"
    "Identify cross-subject patterns.\n"
    "Be concrete, structured, and professional.\n"
    "Return ONLY valid JSON.\n"
)

# ============================================================
# HELPERS
# ============================================================

def _require_env(var: str):
    if not os.getenv(var):
        raise RuntimeError(f"Missing required environment variable: {var}")

def normalize_for_sheets(value) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return str(value)

def safe_json_parse(text: str) -> Optional[Dict]:
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                return None
    return None

# ============================================================
# PROMPT BUILDER
# ============================================================

def build_prompt(
    student_id: str,
    grade: int,
    analytics: List[Dict],
    summaries: List[Dict],
) -> str:
    return (
        f"Student ID: {student_id}\n"
        f"Grade: {grade}\n\n"
        f"Numerical subject analytics:\n{json.dumps(analytics, indent=2)}\n\n"
        f"Subject-level AI summaries:\n{json.dumps(summaries, indent=2)}\n\n"
        "Return JSON ONLY in this exact schema:\n"
        "{\n"
        '  "overall_summary": "...",\n'
        '  "key_strengths": "...",\n'
        '  "areas_to_improve": "...",\n'
        '  "recommended_next_steps": "...",\n'
        '  "confidence_note": "high | medium | low"\n'
        "}"
    )

# ============================================================
# LLM BACKENDS (STRICT)
# ============================================================

def call_ollama(prompt: str) -> str:
    import ollama
    r = ollama.chat(
        model=os.getenv("OLLAMA_MODEL", "mistral"),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    return r["message"]["content"]

def call_openai(prompt: str) -> str:
    _require_env("OPENAI_API_KEY")
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    r = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )
    return r.choices[0].message.content

def call_claude(prompt: str) -> str:
    _require_env("ANTHROPIC_API_KEY")
    from anthropic import Anthropic
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    r = client.messages.create(
        model=os.getenv("CLAUDE_MODEL", "claude-3-haiku-20240307"),
        max_tokens=700,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return r.content[0].text

def call_gemini(prompt: str) -> str:
    _require_env("GEMINI_API_KEY")
    import google.generativeai as genai
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel(
        model_name=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
        system_instruction=SYSTEM_PROMPT,
    )
    return model.generate_content(prompt).text

def call_deepseek(prompt: str) -> str:
    _require_env("DEEPSEEK_API_KEY")
    from openai import OpenAI
    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
    )
    r = client.chat.completions.create(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )
    return r.choices[0].message.content

LLM_BACKENDS = {
    "ollama": call_ollama,
    "openai": call_openai,
    "claude": call_claude,
    "gemini": call_gemini,
    "deepseek": call_deepseek,
}

# ============================================================
# CORE ENGINE
# ============================================================

def generate_consolidated_summary(
    student_id: str,
    grade: int,
    analytics: List[Dict],
    summaries: List[Dict],
    llm_provider: str,
) -> Dict:

    if llm_provider not in LLM_BACKENDS:
        raise ValueError(f"Unsupported LLM provider: {llm_provider}")

    prompt = build_prompt(student_id, grade, analytics, summaries)

    for _ in range(MAX_RETRIES):
        raw = LLM_BACKENDS[llm_provider](prompt)
        parsed = safe_json_parse(raw)
        if parsed:
            return parsed
        time.sleep(RETRY_DELAY_SECONDS)

    raise RuntimeError("LLM failed to produce valid JSON")

# ============================================================
# PIPELINE ENTRY (SAFE, IDEMPOTENT)
# ============================================================

def run_student_consolidation(student_id: str) -> None:
    llm_provider = os.getenv("LLM_PROVIDER", "ollama").lower()

    client = get_gs_client()
    spreadsheet = get_spreadsheet(client)

    analytics_df = read_table(spreadsheet, "subject_analytics")
    summaries_df = read_table(spreadsheet, "subject_summaries")

    a = analytics_df[analytics_df["student_id"] == student_id]
    s = summaries_df[summaries_df["student_id"] == student_id]

    if a.empty or s.empty:
        print(f"SKIPPED | No data for student_id={student_id}")
        return

    grade = int(a.iloc[0]["grade"])

    consolidated = generate_consolidated_summary(
        student_id=student_id,
        grade=grade,
        analytics=a.to_dict("records"),
        summaries=s.to_dict("records"),
        llm_provider=llm_provider,
    )

    output_df = pd.DataFrame([{
        "student_id": student_id,
        "grade": grade,
        **{k: normalize_for_sheets(v) for k, v in consolidated.items()},
        "llm_provider": llm_provider,
    }])

    append_table(
        spreadsheet=spreadsheet,
        table_name="student_consolidated_history",
        df=output_df,
    )

    upsert_table(
        spreadsheet=spreadsheet,
        table_name="student_consolidated_latest",
        df=output_df,
        key_columns=["student_id"],
    )

    print(f"Student consolidation complete | {student_id} | LLM={llm_provider}")

# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":
    run_student_consolidation("S001")
