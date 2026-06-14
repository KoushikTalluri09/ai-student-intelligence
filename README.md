# STEM Globe — AI Student Intelligence Platform

A production-grade, explainable academic intelligence platform that transforms raw exam scores into faculty-level insights, AI-generated summaries, and a polished role-based dashboard — built for students, parents, and teachers.

**Live app:** [https://ai-student-intelligence.onrender.com](https://ai-student-intelligence.onrender.com)

---

## Screenshot

![Dashboard](docs/screenshot.png)

*(Add your own screenshot to `docs/screenshot.png`)*

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| Backend API | FastAPI + Uvicorn (Render) |
| Database | Google Sheets (gspread) |
| Analytics | Pandas, NumPy |
| Charts | Plotly |
| LLMs | Ollama · OpenAI · Anthropic Claude · Gemini · DeepSeek |
| Secrets (cloud) | Streamlit Secrets / st.secrets |
| Secrets (local) | python-dotenv |

---

## How to Run Locally

### 1. Clone and install dependencies

```bash
git clone https://github.com/KoushikTalluri09/ai-student-intelligence.git
cd ai-student-intelligence
pip install -r requirements.txt
```

### 2. Add Google credentials

Place your Google service account JSON at `config/google_service_account.json`.

Create a `.env` file in the project root:

```env
GOOGLE_SHEETS_CREDENTIALS=config/google_service_account.json
GOOGLE_SHEETS_DB_NAME=AI_Student_Intelligence_DB

# Optional — only needed for cloud LLM providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=your-key
```

### 3. (Optional) Start the pipeline server

Required only if you want to run the analytics pipeline locally. The Streamlit app
can call the hosted Render backend without this step.

```bash
uvicorn pipeline_server:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Launch the Streamlit app

```bash
streamlit run ui_app.py
```

Open [http://localhost:8501](http://localhost:8501).

**Demo credentials:**
| Email | Password | Role |
|---|---|---|
| `demo@stemglobe.io` | `demo1234` | Student |
| `admin@school.com` | `Admin@123` | Admin |

---

## Project Description

AI Student Intelligence is a full-stack academic intelligence system that runs a five-phase pipeline on raw exam data:

| Phase | File | Output |
|---|---|---|
| 0 — Validation | `analytics/validators.py` | `validated_results` |
| 1 — Subject Analytics | `analytics/student_analyzer.py` | `subject_analytics` |
| 2 — Insights + Explainability | `insights/insight_engine.py` | `subject_insights` |
| 3 — LLM Summaries | `llm/summary_generator.py` | `subject_summaries` |
| 4 — Student Consolidation | `insights/student_consolidator.py` | `student_consolidated_latest` |

### Why Google Sheets as the database?

Transparent, shareable, auditable, and accessible to non-technical stakeholders without a separate database server. All pipeline outputs are written to named worksheets in a single Google Spreadsheet.

### Cached vs Live AI

- **Cached mode (default):** Reads pre-computed AI summaries. Fast, free, deterministic.
- **Live mode:** Calls the selected LLM (OpenAI, Claude, Gemini, DeepSeek) in real-time.

### Explainability layer

Every AI output is backed by explicit evidence points, numeric signals, confidence level, and human-readable reasoning — no black-box outputs.

---

## Folder Structure

```
ui_app.py               # Streamlit frontend (entry point for Streamlit Cloud)
pipeline_server.py      # FastAPI backend (deployed on Render)
pipeline_runner.py      # Full pipeline orchestrator
analytics/              # Phase 0-1: validation, scoring, metrics
insights/               # Phase 2 & 4: insight engine + student consolidator
llm/                    # Phase 3: multi-provider LLM summary generation
storage/                # Google Sheets read/write abstraction
config/                 # App config + score thresholds
.streamlit/             # Streamlit server config + secrets (local only)
requirements.txt
```

---

## Author

**Koushik Talluri** — MS Business Analytics, UMass Amherst  
Data Analytics · AI Systems
