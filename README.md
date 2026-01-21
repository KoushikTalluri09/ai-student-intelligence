**🎓 AI Student Intelligence**

A Production-Grade, Explainable Academic Intelligence Platform
Faculty-level academic analytics and AI-driven insights built with data validation, explainability, and trust at the core.

📌 Table of Contents

- Project Overview
- Why This Project Exists
- What Problems This Solves
- High-Level Architecture
- End-to-End Pipeline Phases
- Data Model & Google Sheets as Database
- Cached vs Live AI Strategy
- Explainability & Trust Layer
- Backend API (FastAPI)
- Frontend UI (Streamlit)
- LLM Strategy & Prompt Design
- Error Handling & Production Safeguards
- Folder Structure Explained




**1️-  Project Overview**

AI Student Intelligence is a full-stack academic intelligence system that transforms raw exam scores into:

📊 Clean analytics
🧠 Explainable academic insights
✍️ AI-generated faculty-grade summaries
🎓 Student-level consolidated reports
🖥️ A polished, interactive UI



**2- Why This Project Exists**

Most “AI education projects” fail in real-world settings because:

Raw data is noisy and unvalidated
AI outputs are not explainable
Systems overwrite data silently
There is no trust layer
UI is disconnected from backend reality



**3️- What Problems This Solves For Students**

- Understand why performance is good or bad
- Get actionable improvement plans
- Avoid black-box AI feedback

For Teachers

- Identify at-risk students early
- Get interpretable signals, not raw scores
- Decide when intervention is needed

For Institutions

- Standardized academic analytics
- Audit-friendly data flow
- Reproducible AI decisions

**4️- High-Level Architecture**

Raw Exam Data 
[Phase 0] Validation
[Phase 1] Subject Analytics
[Phase 2] Insights + Explainability
[Phase 3] LLM Subject Summaries
[Phase 4] Student Consolidation
FastAPI (Cached + Live)
Streamlit UI


**5️- End-to-End Pipeline Phases**

**🔹 Phase 0 — Data Validation**

File: analytics/validators.py
Schema validation
Score range checks
Date normalization
Hard failure on bad data

Output:
validated_results

**🔹 Phase 1 — Subject Analytics**

File: analytics/student_analyzer.py

Generates per-student, per-subject metrics:
Average score
Latest score
Trend
Volatility
Risk flag
Performance band
Data confidence

Output:
subject_analytics

**🔹 Phase 2 — Insights + Explainability**

File: insights/insight_engine.py

This is the trust layer.
For each subject:
Primary academic issue
Root cause
Urgency
Recommended focus
Teacher intervention signal
Explainability evidence (human-readable)

Output:
subject_insights

**🔹 Phase 3 — AI Subject Summaries**

File: llm/summary_generator.py

Generates world-class, readable summaries:
Performance summary (multi-sentence, natural)
Improvement plan
Motivation note
Confidence level

Key rules:
Deterministic provider selection
Safe JSON parsing
No hallucinated data
Hard fallback if AI fails

Output:
subject_summaries

**🔹 Phase 4 — Student Consolidation**

File: insights/student_consolidator.py

Creates a single academic narrative per student:
Cross-subject patterns
Strengths
Areas to improve
Next steps
Confidence signal

Writes to:
student_consolidated_latest (upsert)
student_consolidated_history (audit log)

**6️- Google Sheets as a Database**

**Why Google Sheets?**
Transparent
Shareable (view-only)
Auditable
Non-technical stakeholder friendly

Sheets used:

- validated_results

- subject_analytics

- subject_insights

- subject_summaries

- student_consolidated_latest

- student_consolidated_history

**7️- Cached vs Live AI Strategy**

**- Cached Mode (Default)**

Uses precomputed summaries
Fast
Free
Deterministic
Best for demos & classrooms

**- Live Mode**

User selects LLM (OpenAI, Claude, Gemini, etc.)
Real-time generation
API-backed
Fully optional
UI automatically switches modes based on LLM selection.

**8️- Explainability & Trust Layer**

Every AI output is backed by:

Explicit evidence points
Numeric signals
Confidence level
Human-readable reasoning


**9️- Backend API (FastAPI)**

File: pipeline_server.py

Endpoints:

POST /student-summary → cached
POST /student-summary/live → live AI
GET / → health check

Features:

JSON-safe parsing
NaN-proof responses
Defensive error handling
Explainability injection

**10- Frontend UI (Streamlit)**

File: ui_app.py

Features:
Professional UI cards
Color-coded subject scores
Trend indicators
Drill-down subject insights
Evidence bullets rendered correctly
Explainability sections
Responsive layout
Designed for readability, not flash.

**11- LLM Strategy & Prompt Design**

Strict JSON contracts
Multi-sentence outputs
Faculty tone
No invented numbers
Retry logic + fallback
LLMs supported:

Ollama (local)
OpenAI
Claude
Gemini
DeepSeek

**12- Error Handling & Safeguards**

NaN sanitization everywhere
Header-safe Google Sheets writes
Append vs overwrite explicitly controlled
No silent failures
Pipeline-safe execution (one student never breaks batch)

**13- Folder Structure**

analytics/   → metrics & analytics
insights/    → insights & consolidation
llm/         → AI summaries
storage/     → Google Sheets abstraction
config/      → config files
data/        → sample datasets
ui_app.py    → Streamlit UI
pipeline_runner.py
pipeline_server.py


-



**👤 Author**

**Koushik Talluri
MS Business Analytics — UMass Amherst**


Data Analytics | AI Systems 



