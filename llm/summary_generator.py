# -*- coding: utf-8 -*-

import os
import json
import time
import pandas as pd
from typing import Dict, Optional

from dotenv import load_dotenv

from storage.google_sheets import (
    get_gs_client,
    get_spreadsheet,
    read_table,
    write_table,
)

# ============================================================
# ENV & GLOBAL CONFIG
# ============================================================

load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 3

# ============================================================
# SYSTEM PROMPT (WORLD-CLASS, UI-READY)
# ============================================================

SYSTEM_PROMPT = (
    "You are a senior academic mentor writing faculty-grade feedback.\n"
    "Your tone must be calm, encouraging, and constructive.\n"
    "Write in complete, well-structured paragraphs.\n"
    "Explain performance clearly without inventing data.\n"
    "Avoid short or robotic sentences.\n"
    "Assume the output will be read by students, parents, and teachers.\n"
    "Return ONLY valid JSON.\n"
)

# ============================================================
# SAFE JSON PARSER
# ============================================================

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

def build_prompt(row: Dict) -> str:
    return f"""
Student Academic Context
------------------------
Grade: {row['grade']}
Subject: {row['subject']}

Interpretable Insights
---------------------
Primary issue: {row['primary_issue']}
Secondary issue: {row['secondary_issue']}
Root cause category: {row['root_cause_category']}
Academic risk level: {row['academic_risk_level']}
Urgency level: {row['urgency_level']}
Recommended focus area: {row['recommended_focus_area']}
Teacher intervention needed: {row['teacher_intervention_needed']}

Instructions
------------
Write a detailed but readable academic summary.

Return ONLY valid JSON in the following structure:
{{
  "performance_summary": "2–4 sentences explaining current performance and pattern",
  "improvement_plan": "Concrete, actionable steps written as guidance, not commands",
  "motivation_note": "Encouraging message focused on confidence and growth mindset",
  "confidence_note": "high | medium | low"
}}
"""

# ============================================================
# LLM BACKENDS
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
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    r = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
    )
    return r.choices[0].message.content

def call_claude(prompt: str) -> str:
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
    import google.generativeai as genai
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel(
        model_name=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
        system_instruction=SYSTEM_PROMPT,
    )
    return model.generate_content(prompt).text

def call_deepseek(prompt: str) -> str:
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
        temperature=0.4,
    )
    return r.choices[0].message.content

def call_llm(prompt: str) -> str:
    if LLM_PROVIDER == "ollama":
        return call_ollama(prompt)
    if LLM_PROVIDER == "openai":
        return call_openai(prompt)
    if LLM_PROVIDER == "claude":
        return call_claude(prompt)
    if LLM_PROVIDER == "gemini":
        return call_gemini(prompt)
    if LLM_PROVIDER == "deepseek":
        return call_deepseek(prompt)
    raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}")

# ============================================================
# SUMMARY GENERATION
# ============================================================

def generate_summary(row: Dict) -> Dict:
    prompt = build_prompt(row)

    for _ in range(MAX_RETRIES):
        raw = call_llm(prompt)
        parsed = safe_json_parse(raw)
        if parsed:
            return parsed
        time.sleep(RETRY_DELAY_SECONDS)

    return {
        "performance_summary": (
            "Based on the available academic signals, the student's performance "
            "pattern has been analyzed, though a detailed AI narrative could not "
            "be generated at this time."
        ),
        "improvement_plan": (
            "Continue reviewing core concepts regularly and seek clarification "
            "on challenging topics to strengthen understanding."
        ),
        "motivation_note": (
            "Progress is built through consistency. With steady effort and support, "
            "meaningful improvement is achievable."
        ),
        "confidence_note": "low",
    }

# ============================================================
# PHASE 3 ENTRY POINT (FULL OVERWRITE)
# ============================================================

def run_llm():
    client = get_gs_client()
    spreadsheet = get_spreadsheet(client)

    df = read_table(spreadsheet, "subject_insights")
    df=df.head(20)

    if df.empty:
        raise RuntimeError("subject_insights sheet is empty")

    summaries = []

    for row in df.to_dict(orient="records"):
        summary = generate_summary(row)

        summaries.append({
            "student_id": row["student_id"],
            "grade": row["grade"],
            "subject": row["subject"],
            "performance_summary": summary["performance_summary"],
            "improvement_plan": summary["improvement_plan"],
            "motivation_note": summary["motivation_note"],
            "confidence_note": summary["confidence_note"],
            "llm_provider": LLM_PROVIDER,
        })

    output_df = pd.DataFrame(summaries)

    if output_df.empty:
        raise RuntimeError("Phase 3 produced no summaries")

    # FULL OVERWRITE — SAFE & DETERMINISTIC
    write_table(
        spreadsheet=spreadsheet,
        table_name="subject_summaries",
        df=output_df,
    )

    print(
        f"Phase 3 complete | "
        f"LLM provider: {LLM_PROVIDER} | "
        f"Summaries generated: {len(output_df)}"
    )

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    run_llm()
