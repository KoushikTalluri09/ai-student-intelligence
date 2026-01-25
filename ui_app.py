import streamlit as st
import requests
import json

# ============================================================
# CONFIG
# ============================================================

BASE_API = "https://student-api.onrender.com"

CACHED_ENDPOINT = f"{BASE_API}/student-summary"
LIVE_ENDPOINT = f"{BASE_API}/student-summary/live"

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="STEM Globe | Student Intelligence",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============================================================
# GLOBAL STYLES — ENTERPRISE / FLUENT UI
# ============================================================

st.markdown(
    """
    <style>
        body {
            background-color: #eef2f7;
            color: #0f172a;
        }

        /* ---------- Brand ---------- */
        .brand {
            font-size: 2rem;
            font-weight: 900;
            color: #0b1f44;
            letter-spacing: 0.4px;
        }

        /* ---------- Page Title ---------- */
        .page-title h1 {
            font-size: 2.7rem;
            font-weight: 900;
            margin-bottom: 0.4rem;
        }

        .page-title p {
            color: #475569;
            font-size: 1.05rem;
        }

        /* ---------- Section Containers ---------- */
        .section-card {
            background: linear-gradient(180deg, #f8fafc, #eef2ff);
            padding: 2.5rem;
            border-radius: 24px;
            margin-bottom: 3rem;
            border-left: 6px solid #2563eb;
            box-shadow: 0 14px 32px rgba(15,23,42,0.10);
        }

        .section-title {
            font-size: 1.7rem;
            font-weight: 900;
            margin-bottom: 1.8rem;
            color: #0f172a;
        }

        /* ---------- Student Summary Header ---------- */
        .student-summary-title {
            text-align: center;
            font-size: 2.4rem;
            font-weight: 900;
            color: #2563eb;
            margin: 3.5rem 0 2.8rem 0;
        }

        /* ---------- Score Cards ---------- */
        .score-card {
            background-color: #ffffff;
            padding: 2rem 1.6rem;
            border-radius: 22px;
            border-left: 8px solid;
            box-shadow: 0 12px 26px rgba(15,23,42,0.12);
            text-align: center;
        }

        .score-title {
            font-size: 1.2rem;
            font-weight: 800;
            margin-bottom: 0.6rem;
        }

        .score-value {
            font-size: 3rem;
            font-weight: 900;
            margin-bottom: 0.4rem;
        }

        .score-meta {
            font-size: 0.95rem;
            color: #475569;
            line-height: 1.7;
        }

        .green { border-color: #16a34a; }
        .amber { border-color: #f59e0b; }
        .red { border-color: #dc2626; }

        /* ---------- SUBJECT EXPANDERS ---------- */
        div[data-testid="stExpander"] summary {
            font-size: 1.2rem !important;
            font-weight: 800 !important;
            color: #0f172a !important;
            padding: 1.1rem 1.3rem !important;
            border-radius: 16px;
            background-color: #f1f5f9;
        }

        div[data-testid="stExpander"] summary:hover {
            background-color: #e0e7ff;
        }

        div[data-testid="stExpander"] div {
            font-size: 1rem;
            color: #1e293b;
        }

        /* ---------- Inputs ---------- */
        input, select {
            border-radius: 12px !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# TOP BAR
# ============================================================

l, c, r = st.columns([1.2, 2.6, 1.2])

with l:
    st.markdown('<div class="brand">STEM Globe</div>', unsafe_allow_html=True)

with c:
    st.markdown(
        """
        <div class="page-title" style="text-align:center;">
            <h1>Student Intelligence Dashboard</h1>
            <p>Clear academic insights for students, parents, and educators</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with r:
    st.text_input("Username", placeholder="demo_user", label_visibility="collapsed")
    st.text_input("Password", type="password", placeholder="••••••", label_visibility="collapsed")
    st.button("Login")

st.divider()

# ============================================================
# STUDENT WORKSPACE
# ============================================================

st.markdown("## 🎯 Student Workspace")

c1, c2, c3 = st.columns(3)

with c1:
    student_id = st.text_input("Student ID", placeholder="S001")

with c2:
    llm_provider = st.selectbox(
        "Reasoning Engine",
        ["ollama", "openai", "claude", "gemini", "deepseek"],
    )

with c3:
    if llm_provider == "ollama":
        mode = "cached"
        st.success("⚡ Fast Mode")
    else:
        mode = "live"
        st.warning("🤖 Live AI Mode")

generate = st.button("🚀 Generate Academic Report", use_container_width=True)

# ============================================================
# HELPERS
# ============================================================

def score_color(score):
    try:
        score = float(score)
    except Exception:
        return "amber", "⚪"
    if score >= 70:
        return "green", "🟢"
    if score >= 50:
        return "amber", "🟠"
    return "red", "🔴"

def trend_icon(trend):
    t = str(trend).lower()
    if "up" in t:
        return "⬆️ Improving"
    if "down" in t:
        return "⬇️ Declining"
    return "➖ Stable"

def normalize_evidence(value):
    if not value:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else [value]
        except Exception:
            return [value]
    return []

# ============================================================
# ACTION
# ============================================================

if generate:
    if not student_id.strip():
        st.error("Student ID is required")
        st.stop()

    endpoint = CACHED_ENDPOINT if mode == "cached" else LIVE_ENDPOINT
    payload = {"student_id": student_id.strip()}
    if mode == "live":
        payload["llm_provider"] = llm_provider

    with st.spinner("Preparing student report..."):
        response = requests.post(endpoint, json=payload, timeout=180)

    if response.status_code != 200:
        st.error(response.text)
        st.stop()

    data = response.json()

    # ========================================================
    # STUDENT HEADER
    # ========================================================

    name = data.get("student_name", "").strip()
    grade = data.get("grade", "")

    if name:
        st.markdown(
            f"""
            <div style="text-align:center; margin:3.8rem 0 2rem 0;">
                <h1 style="font-size:3.3rem; font-weight:900;">{name.upper()}</h1>
                <p style="color:#475569; font-size:1.1rem;">Grade {grade}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="student-summary-title">Student Academic Summary</div>',
            unsafe_allow_html=True,
        )

    # ========================================================
    # ACADEMIC OVERVIEW
    # ========================================================

    if data.get("overall_summary"):
        st.markdown(
            f"""
            <div class="section-card">
                <div class="section-title">📘 Academic Overview</div>
                <p>{data["overall_summary"]}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ========================================================
    # PERFORMANCE AT A GLANCE
    # ========================================================

    numeric = data.get("numerical_performance", [])
    if numeric:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">📊 Performance at a Glance</div>', unsafe_allow_html=True)

        cols = st.columns(len(numeric))
        for col, row in zip(cols, numeric):
            with col:
                color, dot = score_color(row.get("latest_score", 0))
                st.markdown(
                    f"""
                    <div class="score-card {color}">
                        <div class="score-title">{dot} {row['subject']}</div>
                        <div class="score-value">{row['latest_score']}</div>
                        <div class="score-meta">
                            Average: {row['average_score']}<br/>
                            {trend_icon(row.get('trend'))}<br/>
                            Risk Level: {row['risk_flag']}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown("</div>", unsafe_allow_html=True)

    # ========================================================
    # SUBJECT INSIGHTS — ICONS + BOLD
    # ========================================================

    subject_icons = {
        "English": "📘",
        "Math": "➗",
        "Science": "🔬",
    }

    subjects = data.get("subject_summaries", [])
    if subjects:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">📚 Subject Insights & Guidance</div>', unsafe_allow_html=True)

        for subj in subjects:
            icon = subject_icons.get(subj["subject"], "📖")
            label = f"{icon}  {subj['subject']}"

            with st.expander(label, expanded=False):
                st.markdown("**Current Performance**")
                st.write(subj.get("performance_summary",""))

                st.markdown("**Improvement Plan**")
                st.write(subj.get("improvement_plan",""))

                st.markdown("**Encouragement**")
                st.write(subj.get("motivation_note",""))

                explain = subj.get("explainability", {})
                if explain:
                    st.divider()
                    st.markdown("**Why this matters**")
                    st.write(explain.get("explanation_summary",""))
                    for e in normalize_evidence(explain.get("key_evidence_points")):
                        st.info(e)

        st.markdown("</div>", unsafe_allow_html=True)

    # ========================================================
    # NEXT STEPS
    # ========================================================

    if data.get("recommended_next_steps"):
        st.markdown(
            f"""
            <div class="section-card">
                <div class="section-title">🧭 What to Focus on Next</div>
                <p>{data["recommended_next_steps"]}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.caption(
        f"Mode: {data.get('mode', mode)} | Engine: {data.get('llm_provider_used','pipeline')}"
    )
