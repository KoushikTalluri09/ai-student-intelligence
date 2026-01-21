import streamlit as st
import requests
import json

# ============================================================
# CONFIG
# ============================================================

BASE_API = "http://localhost:8000"
CACHED_ENDPOINT = f"{BASE_API}/student-summary"
LIVE_ENDPOINT = f"{BASE_API}/student-summary/live"

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="AI Student Intelligence",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============================================================
# GLOBAL STYLES (SAFE + FINAL)
# ============================================================

st.markdown(
    """
    <style>
        body { background-color: #0b0f19; }

        .section-card {
            background-color: #ffffff;
            padding: 1.8rem 2rem;
            border-radius: 18px;
            margin-bottom: 2rem;
            border: 1px solid #e5e7eb;
            box-shadow: 0 12px 28px rgba(0,0,0,0.08);
            color: #020617;
        }

        .section-title {
            font-size: 1.55rem;
            font-weight: 700;
            margin-bottom: 1.2rem;
            color: #020617;
        }

        .subtle {
            color: #64748b;
            font-size: 0.95rem;
        }

        .score-card {
            background-color: #ffffff;
            padding: 1.4rem;
            border-radius: 16px;
            border-left: 10px solid;
            box-shadow: 0 8px 20px rgba(0,0,0,0.08);
            text-align: center;
        }

        .score-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: #020617;
        }

        /* 🔥 FIX: force readable score color */
        .score-value {
            font-size: 2.4rem;
            font-weight: 800;
            margin: 0.3rem 0;
            color: #020617 !important;
        }

        .score-meta {
            font-size: 0.9rem;
            color: #475569;
            line-height: 1.6;
        }

        .green { border-color: #16a34a; }
        .amber { border-color: #f59e0b; }
        .red { border-color: #dc2626; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <div style="text-align:center; margin-bottom:1.5rem;">
        <h1>🎓 AI Student Intelligence</h1>
        <p class="subtle">
            Faculty-grade academic insights powered by validated data & AI reasoning
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.divider()

# ============================================================
# INPUT PANEL
# ============================================================

st.markdown("### 🔎 Student Report Configuration")

c1, c2, c3 = st.columns(3)

with c1:
    student_id = st.text_input("Student ID", placeholder="S001")

with c2:
    llm_provider = st.selectbox(
        "AI Reasoning Engine",
        ["ollama", "openai", "claude", "gemini", "deepseek"],
    )

with c3:
    st.markdown("**Execution Mode**")
    if llm_provider == "ollama":
        mode = "cached"
        st.success("⚡ Cached (Fast & Free)")
    else:
        mode = "live"
        st.warning("🤖 Live (Uses selected LLM)")

st.divider()

generate = st.button(
    "🚀 Generate Academic Report",
    type="primary",
    use_container_width=True,
)

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
    if "up" in t or "+" in t:
        return "⬆️ Improving"
    if "down" in t or "-" in t:
        return "⬇️ Declining"
    return "➖ Stable"


def normalize_evidence(value):
    if not value:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(v) for v in parsed if str(v).strip()]
        except Exception:
            return [value.strip()]
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

    with st.spinner("Generating academic report..."):
        response = requests.post(endpoint, json=payload, timeout=180)

    if response.status_code != 200:
        st.error(response.text)
        st.stop()

    data = response.json()

    # ========================================================
    # OVERALL SUMMARY
    # ========================================================

    st.markdown(
        f"""
        <div class="section-card">
            <div class="section-title">📘 Overall Academic Assessment</div>
            <p>{data.get("overall_summary","—")}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ========================================================
    # SUBJECT PERFORMANCE
    # ========================================================

    st.markdown(
        """
        <div class="section-card">
            <div class="section-title">📊 Subject Performance Snapshot</div>
        """,
        unsafe_allow_html=True,
    )

    numeric = data.get("numerical_performance", [])
    cols = st.columns(len(numeric)) if numeric else []

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
    # SUBJECT-LEVEL AI INSIGHTS
    # ========================================================

    st.markdown(
        """
        <div class="section-card">
            <div class="section-title">📚 Subject-Level AI Insights</div>
        """,
        unsafe_allow_html=True,
    )

    for subj in data.get("subject_summaries", []):
        with st.expander(f"📘 {subj['subject']}"):
            st.markdown("**Performance Summary**")
            st.write(subj.get("performance_summary",""))

            st.markdown("**Improvement Plan**")
            st.write(subj.get("improvement_plan",""))

            st.markdown("**Motivation Note**")
            st.write(subj.get("motivation_note",""))

            explain = subj.get("explainability", {})
            if explain:
                st.divider()
                st.markdown("**Why this insight?**")
                st.write(explain.get("explanation_summary",""))

                evidence = normalize_evidence(
                    explain.get("key_evidence_points")
                )
                if evidence:
                    st.markdown("**Evidence**")
                    for e in evidence:
                        st.info(e)

    st.markdown("</div>", unsafe_allow_html=True)

    # ========================================================
    # ✅ RECOMMENDED NEXT STEPS (RESTORED)
    # ========================================================

    st.markdown(
        f"""
        <div class="section-card">
            <div class="section-title">🧭 Recommended Next Steps</div>
            <p>{data.get("recommended_next_steps","—")}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ========================================================
    # FOOTER
    # ========================================================

    st.caption(
        f"Mode: **{data.get('mode', mode)}** | "
        f"LLM Used: **{data.get('llm_provider_used', 'pipeline')}**"
    )

    st.caption(
        "Generated using validated academic data and AI-assisted reasoning. "
        "Designed to support educators, students, and parents."
    )
