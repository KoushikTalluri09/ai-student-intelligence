import streamlit as st
import requests
import json

# ============================================================
# CONFIG
# ============================================================

BASE_API = "https://ai-student-intelligence.onrender.com"
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
# GLOBAL STYLES
# ============================================================

st.markdown(
    """
    <style>
        body { background-color: #0b0f19; color: #e5e7eb; }

        .brand {
            font-size: 1.9rem;
            font-weight: 900;
            color: #38bdf8;
        }

        .page-title h1 {
            font-size: 2.6rem;
            font-weight: 900;
            color: #ffffff;
        }

        .page-title p {
            color: #94a3b8;
            font-size: 1.05rem;
        }

        .section-card {
            background: #111827;
            padding: 2.2rem;
            border-radius: 22px;
            margin-bottom: 2.8rem;
            border-left: 6px solid #2563eb;
            box-shadow: 0 14px 32px rgba(0,0,0,0.45);
        }

        .section-title {
            font-size: 1.6rem;
            font-weight: 800;
            margin-bottom: 1.6rem;
            color: #ffffff;
        }

        .student-summary-title {
            text-align: center;
            font-size: 2.4rem;
            font-weight: 900;
            color: #60a5fa;
            margin: 3.5rem 0 2.5rem 0;
        }

        .score-card {
            background-color: #020617;
            padding: 1.9rem;
            border-radius: 20px;
            border-left: 8px solid;
            text-align: center;
            box-shadow: 0 10px 26px rgba(0,0,0,0.5);
        }

        .score-title {
            font-size: 1.15rem;
            font-weight: 800;
            margin-bottom: 0.6rem;
        }

        .score-value {
            font-size: 3rem;
            font-weight: 900;
        }

        .score-meta {
            font-size: 0.95rem;
            color: #cbd5f5;
            line-height: 1.6;
        }

        .green { border-color: #22c55e; }
        .amber { border-color: #f59e0b; }
        .red { border-color: #ef4444; }

        div[data-testid="stExpander"] summary {
            font-size: 1.15rem !important;
            font-weight: 800 !important;
            color: #ffffff !important;
            background-color: #020617;
            padding: 1.1rem 1.3rem;
            border-radius: 14px;
        }

        div[data-testid="stExpander"] summary:hover {
            background-color: #1e293b;
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
        st.error("Student not found or backend error.")
        st.stop()

    data = response.json()

    # ========================================================
    # STUDENT HEADER
    # ========================================================

    name = data.get("student_name", "")
    grade = data.get("grade", "")

    if name:
        st.markdown(
            f"""
            <div style="text-align:center; margin:3.5rem 0;">
                <h1 style="font-size:3.2rem; font-weight:900;">{name.upper()}</h1>
                <p style="color:#94a3b8;">Grade {grade}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="student-summary-title">Student Academic Summary</div>',
            unsafe_allow_html=True,
        )

    # ========================================================
    # OVERVIEW
    # ========================================================

    if data.get("overall_summary"):
        st.markdown(
            f"""
            <div class="section-card">
                <div class="section-title">📘 Academic Overview</div>
                <p>{data['overall_summary']}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ========================================================
    # PERFORMANCE
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
                            Avg: {row['average_score']}<br/>
                            {trend_icon(row.get('trend'))}<br/>
                            Risk: {row['risk_flag']}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown("</div>", unsafe_allow_html=True)

    # ========================================================
    # SUBJECT INSIGHTS
    # ========================================================

    subject_icons = {"English": "📘", "Math": "➗", "Science": "🔬"}
    subjects = data.get("subject_summaries", [])

    if subjects:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">📚 Subject Insights & Guidance</div>', unsafe_allow_html=True)

        for subj in subjects:
            icon = subject_icons.get(subj["subject"], "📖")
            with st.expander(f"{icon} {subj['subject']}"):
                st.write(subj.get("performance_summary",""))
                st.write(subj.get("improvement_plan",""))
                st.write(subj.get("motivation_note",""))

        st.markdown("</div>", unsafe_allow_html=True)

    # ========================================================
    # FOOTER
    # ========================================================

    st.caption(
        f"Mode: {data.get('mode', mode)} | Engine: {data.get('llm_provider_used','pipeline')}"
    )
