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

        log("PHASE 0 | Validating raw_student_scores → validated_results")
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

        if analytics_df.empty:
            raise RuntimeError("subject_analytics sheet is empty")

        student_ids = sorted(analytics_df["student_id"].unique())

        for sid in student_ids:
            run_student_consolidation(sid)

        log(f"PHASE 4 | SUCCESS | Students consolidated: {len(student_ids)}")

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
