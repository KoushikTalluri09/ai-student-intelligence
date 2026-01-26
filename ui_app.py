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
# GLOBAL STYLES — CLEAN WORLD-CLASS UI
# ============================================================

st.markdown(
    """
    <style>
        body {
            background-color: #f1f3f4;
            color: #000000;
        }

        .brand {
            font-size: 1.6rem;
            font-weight: 800;
            color: #1a73e8;
            margin-bottom: 2px;
        }

        .page-title h1 {
            font-size: 2.2rem;
            font-weight: 800;
            color: #000000;
            margin-bottom: 2px;
        }

        .page-title p {
            font-size: 0.95rem;
            color: #444;
            margin-top: 0px;
        }

        .card {
            background: #ffffff;
            padding: 1.4rem;
            border-radius: 14px;
            margin-bottom: 1.4rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        }

        .section-title {
            font-size: 1.2rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            color: #000000;
        }

        .metric-card {
            background: #ffffff;
            padding: 1.1rem;
            border-radius: 12px;
            border-left: 6px solid;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            text-align: center;
        }

        .metric-title {
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: 2px;
        }

        .metric-value {
            font-size: 2.4rem;
            font-weight: 800;
            margin: 2px 0;
        }

        .metric-meta {
            font-size: 0.9rem;
            color: #333;
            line-height: 1.45;
        }

        .green { border-color: #34a853; }
        .amber { border-color: #fbbc04; }
        .red { border-color: #ea4335; }

        div[data-testid="stExpander"] summary {
            font-size: 1.15rem !important;
            font-weight: 700 !important;
            padding: 0.7rem 0.9rem !important;
            background-color: #ffffff;
            border-radius: 10px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.06);
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
    mode = "cached" if llm_provider == "ollama" else "live"
    if mode == "cached":
        st.success("Fast Mode")
    else:
        st.info("Live AI Mode")

generate = st.button("Generate Academic Report", use_container_width=True)

# ============================================================
# HELPERS
# ============================================================

def score_color(score):
    try:
        score = float(score)
    except Exception:
        return "amber"
    if score >= 70:
        return "green"
    if score >= 50:
        return "amber"
    return "red"

def trend_label(trend):
    t = str(trend).lower()
    if "up" in t:
        return "Improving"
    if "down" in t:
        return "Declining"
    return "Stable"

def normalize_next_steps(value):
    if not value:
        return []
    if isinstance(value, dict):
        return [f"{k}: {v}" for k, v in value.items()]
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return [f"{k}: {v}" for k, v in parsed.items()]
            if isinstance(parsed, list):
                return parsed
        except Exception:
            return [value]
    return []

SUBJECT_ICONS = {
    "English": "📘",
    "Math": "➗",
    "Science": "🔬",
}

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

    with st.spinner("Generating report..."):
        response = requests.post(endpoint, json=payload, timeout=180)

    if response.status_code != 200:
        st.error("Backend error or student not found.")
        st.stop()

    data = response.json()

    # ========================================================
    # HEADER
    # ========================================================

    st.markdown(
        f"""
        <div style="text-align:center; margin:2.2rem 0;">
            <h1 style="font-size:2.7rem; font-weight:800;">{data.get("student_name","").upper()}</h1>
            <p>Grade {data.get("grade","")}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ========================================================
    # OVERVIEW
    # ========================================================

    st.markdown(
        f"""
        <div class="card">
            <div class="section-title">Academic Overview</div>
            <p>{data.get("overall_summary","")}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ========================================================
    # PERFORMANCE SNAPSHOT
    # ========================================================

    metrics = data.get("numerical_performance", [])
    if metrics:
        st.markdown('<div class="card"><div class="section-title">Performance Snapshot</div>', unsafe_allow_html=True)
        cols = st.columns(len(metrics))
        for col, row in zip(cols, metrics):
            with col:
                color = score_color(row.get("latest_score"))
                st.markdown(
                    f"""
                    <div class="metric-card {color}">
                        <div class="metric-title">{row['subject']}</div>
                        <div class="metric-value">{row['latest_score']}</div>
                        <div class="metric-meta">
                            Avg: {row['average_score']}<br/>
                            Trend: {trend_label(row.get("trend"))}<br/>
                            Risk: {row.get("risk_flag")}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        st.markdown("</div>", unsafe_allow_html=True)

    # ========================================================
    # SUBJECT INSIGHTS + EVIDENCE
    # ========================================================

    st.markdown('<div class="card"><div class="section-title">Subject Insights & Evidence</div>', unsafe_allow_html=True)

    for subj in data.get("subject_summaries", []):
        icon = SUBJECT_ICONS.get(subj.get("subject"), "📚")
        explain = subj.get("explainability", {}) or {}

        evidence = explain.get("key_evidence_points", [])
        if isinstance(evidence, str):
            evidence = [e for e in evidence.split("\n") if e.strip()]

        with st.expander(f"{icon} {subj.get('subject')}"):
            st.markdown("**Performance Summary**")
            st.write(subj.get("performance_summary", "—"))

            st.markdown("**Improvement Plan**")
            st.write(subj.get("improvement_plan", "—"))

            st.markdown("**Motivation Note**")
            st.write(subj.get("motivation_note", "—"))

            st.markdown("**Why This Conclusion Was Reached**")
            st.markdown(
                f"""
                <div style="
                    background:#f8f9fa;
                    padding:0.9rem;
                    border-radius:10px;
                    border-left:4px solid #1a73e8;
                ">
                <b>Insight:</b> {explain.get("explanation_summary","—")}<br/><br/>
                <b>Evidence:</b>
                <ul>
                {''.join(f'<li>{e}</li>' for e in evidence)}
                </ul>
                <b>Confidence:</b> {explain.get("confidence_in_insight","unknown").capitalize()}
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("</div>", unsafe_allow_html=True)

    # ========================================================
    # RECOMMENDED NEXT STEPS
    # ========================================================

    steps = normalize_next_steps(data.get("recommended_next_steps"))
    if steps:
        st.markdown('<div class="card"><div class="section-title">Recommended Next Steps</div>', unsafe_allow_html=True)
        for step in steps:
            st.markdown(f"- {step}")
        st.markdown("</div>", unsafe_allow_html=True)

    st.caption(f"Mode: {data.get('mode')} | Engine: {data.get('llm_provider_used')}")
