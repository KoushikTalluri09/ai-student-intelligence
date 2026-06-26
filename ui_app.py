# -*- coding: utf-8 -*-

import os
import streamlit as st
import requests
import json
import hashlib
import uuid
import re
import time
from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
from dotenv import load_dotenv

load_dotenv()

from storage.google_sheets import (
    get_gs_client,
    get_spreadsheet,
    read_table,
    append_table,
    write_table,
    update_user_student_id,
    get_student_report_direct,
    list_worksheet_titles,
    write_student_raw_data,
)

# ============================================================
# CLOUD DETECTION
# Streamlit Cloud injects st.secrets; DEPLOYMENT=cloud is also
# set explicitly so os.getenv() works everywhere in the app.
# IS_CLOUD is True on Streamlit Cloud and also locally when
# a .streamlit/secrets.toml file is present — both paths use
# the direct Google Sheets data loader instead of FastAPI.
# ============================================================

IS_CLOUD = os.environ.get("DEPLOYMENT") == "cloud" or (
    "gcp_service_account" in st.secrets if hasattr(st, "secrets") else False
)

# ============================================================
# CONSTANTS
# ============================================================

API_BASE        = "https://ai-student-intelligence.onrender.com" if IS_CLOUD else "http://localhost:8000"
CACHED_ENDPOINT = f"{API_BASE}/student-summary"
LIVE_ENDPOINT   = f"{API_BASE}/student-summary/live"
EMAIL_RE        = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')
ROLES           = ["Teacher", "Parent", "Student", "Admin"]

DEMO_USERS = {
    "admin@stemglobe.io": "stemglobe2025",
    "demo@stemglobe.io":  "demo1234",
    "admin@school.com":   "Admin@123",
}
DEMO_META = {
    "admin@stemglobe.io": ("Admin",     "Admin"),
    "demo@stemglobe.io":  ("Demo User", "Student"),
    "admin@school.com":   ("Admin",     "Admin"),
}

NAV_ITEMS = ["Dashboard", "Students", "Reports", "Settings"]

ROLE_COLORS = {
    "Admin":   "#2979ff",
    "Teacher": "#00c8e0",
    "Parent":  "#ffab40",
    "Student": "#00e676",
}

ROLE_NAV_ACCESS = {
    "Admin":   ["Dashboard", "Students", "Reports", "Settings"],
    "Teacher": ["Dashboard", "Students", "Reports"],
    "Parent":  ["Dashboard", "Reports"],
    "Student": ["Dashboard"],
}

# ============================================================
# SVG ICON SYSTEM
# ============================================================

_SVG_PATHS = {
    "globe":     '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
    "bar-chart": '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>',
    "alert":     '<path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    "trending":  '<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>',
    "books":     '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
    "calc":      '<rect x="4" y="2" width="16" height="20" rx="2"/><line x1="8" y1="6" x2="16" y2="6"/><line x1="8" y1="10" x2="16" y2="10"/><line x1="8" y1="14" x2="10" y2="14"/><line x1="8" y1="18" x2="10" y2="18"/>',
    "flask":     '<path d="M9 3h6v1l3 7H6l3-7z"/><path d="M6 11v8a2 2 0 002 2h8a2 2 0 002-2v-8"/>',
    "target":    '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "sparkles":  '<path d="M12 3L9.5 9.5 3 12l6.5 2.5L12 21l2.5-6.5L21 12l-6.5-2.5z"/>',
    "search":    '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
    "arrow-r":   '<line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>',
    "check":     '<polyline points="20 6 9 17 4 12"/>',
    "eye":       '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>',
    "eye-off":   '<path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>',
    "clock":     '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "users":     '<path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/>',
    "file":      '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
    "sliders":   '<line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/>',
    "layout":    '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>',
    "log-out":   '<path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>',
    "dot":       '<circle cx="12" cy="12" r="4" fill="currentColor" stroke="none"/>',
    "play":      '<polygon points="5 3 19 12 5 21 5 3" fill="currentColor" stroke="none"/>',
    "user":      '<path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "wand":      '<path d="M15 4l5 5L8 21H3v-5z"/><path d="M20 7l-3-3"/>',
    "info":      '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>',
    "zap":       '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
}


def icon(name: str, color: str = "currentColor", size: int = 14, sw: float = 2.0) -> str:
    paths = _SVG_PATHS.get(name, "")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" '
        f'stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round" '
        f'style="vertical-align:middle;flex-shrink:0;display:inline-block;">'
        f'{paths}</svg>'
    )


LOGO_SVG   = icon("globe", "#2979ff", 22, 1.8)
SUBJ_ICONS = {
    "English": icon("books", "#9e9e9e", 20, 1.7),
    "Math":    icon("calc",  "#9e9e9e", 20, 1.7),
    "Science": icon("flask", "#9e9e9e", 20, 1.7),
}
_DEF_SUBJ_ICON = icon("books", "#9e9e9e", 20, 1.7)


def _nav_svg_uri(inner: str, stroke_hex: str) -> str:
    """Return CSS url() with an encoded SVG for nav icon ::before."""
    svg = (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' "
        f"viewBox='0 0 24 24' fill='none' stroke='{stroke_hex}' "
        f"stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'>"
        f"{inner}</svg>"
    )
    enc = svg.replace("<", "%3C").replace(">", "%3E").replace("#", "%23")
    return f'url("data:image/svg+xml,{enc}")'


_NAV_SVG_INNER = {
    "dashboard": "<rect x='3' y='3' width='7' height='7'/><rect x='14' y='3' width='7' height='7'/><rect x='14' y='14' width='7' height='7'/><rect x='3' y='14' width='7' height='7'/>",
    "students":  "<path d='M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2'/><circle cx='9' cy='7' r='4'/><path d='M23 21v-2a4 4 0 0 0-3-3.87'/><path d='M16 3.13a4 4 0 0 1 0 7.75'/>",
    "reports":   "<path d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z'/><polyline points='14 2 14 8 20 8'/><line x1='16' y1='13' x2='8' y2='13'/><line x1='16' y1='17' x2='8' y2='17'/>",
    "settings":  "<line x1='4' y1='21' x2='4' y2='14'/><line x1='4' y1='10' x2='4' y2='3'/><line x1='12' y1='21' x2='12' y2='12'/><line x1='12' y1='8' x2='12' y2='3'/><line x1='20' y1='21' x2='20' y2='16'/><line x1='20' y1='12' x2='20' y2='3'/><line x1='1' y1='14' x2='7' y2='14'/><line x1='9' y1='8' x2='15' y2='8'/><line x1='17' y1='16' x2='23' y2='16'/>",
}


def _build_nav_icon_css() -> str:
    css = ""
    for page in NAV_ITEMS:
        key = page.lower()
        inner = _NAV_SVG_INNER.get(key, "")
        off = _nav_svg_uri(inner, "#9e9e9e")
        on  = _nav_svg_uri(inner, "#2979ff")
        css += f"""
.nav-{key} .stButton > button {{
    padding-left: 2.75rem !important;
    position: relative !important;
}}
.nav-{key} .stButton > button::before {{
    content: "";
    position: absolute;
    left: 1.05rem;
    top: 50%;
    transform: translateY(-50%);
    width: 15px;
    height: 15px;
    background: {off} center/contain no-repeat;
}}
.nav-{key}.nav-active .stButton > button::before {{
    background: {on} center/contain no-repeat;
}}
"""
    return css


_NAV_ICON_CSS = _build_nav_icon_css()

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="STEM Globe | Student Intelligence",
    page_icon="\U0001f310",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# GLOBAL CSS
# ============================================================

GLOBAL_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ── Base ──────────────────────────────────────────────────── */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stApp"] {{
    background: #000 !important;
    color: #f0f0f0 !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}}
#MainMenu, footer, header,
[data-testid="stToolbar"],
[data-testid="stDecoration"] {{ display: none !important; visibility: hidden !important; }}

::-webkit-scrollbar            {{ width: 5px; }}
::-webkit-scrollbar-track      {{ background: #000; }}
::-webkit-scrollbar-thumb      {{ background: #1e1e1e; border-radius: 3px; }}

/* ── Sidebar ────────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
    background: #080808 !important;
    border-right: 1px solid #161616 !important;
    padding: 0 !important;
    width: 260px !important;
    min-width: 260px !important;
}}
[data-testid="stSidebar"] > div,
[data-testid="stSidebar"] section {{
    padding: 0 !important;
    background: transparent !important;
}}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
    gap: 0 !important;
    padding: 0 !important;
}}
[data-testid="stSidebarCollapseButton"] {{ display: none !important; }}

/* sidebar: base nav button reset */
[data-testid="stSidebar"] .stButton > button {{
    background: transparent !important;
    color: #666 !important;
    border: none !important;
    box-shadow: none !important;
    text-align: left !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    padding: 0.58rem 1.1rem !important;
    border-radius: 10px !important;
    width: 100% !important;
    letter-spacing: 0.01em !important;
    transition: background 0.14s ease, color 0.14s ease !important;
    justify-content: flex-start !important;
    cursor: pointer !important;
}}
[data-testid="stSidebar"] .stButton > button:hover {{
    background: #141414 !important;
    color: #c8d0e0 !important;
    box-shadow: none !important;
    transform: none !important;
}}

/* active nav item */
.nav-active .stButton > button {{
    background: rgba(41,121,255,0.13) !important;
    color: #2979ff !important;
    font-weight: 600 !important;
}}
.nav-active .stButton > button:hover {{
    background: rgba(41,121,255,0.19) !important;
    color: #2979ff !important;
}}

/* disabled nav item (role restriction) */
.nav-locked .stButton > button {{
    opacity: 0.3 !important;
    cursor: not-allowed !important;
    pointer-events: none !important;
}}

/* nav SVG icons */
{_NAV_ICON_CSS}

/* logout button */
.logout-wrap .stButton > button {{
    background: transparent !important;
    color: #555 !important;
    border: 1px solid #1e1e1e !important;
    font-size: 0.8rem !important;
    padding: 0.48rem 1rem !important;
    border-radius: 8px !important;
    margin: 0 1rem 1rem !important;
    width: calc(100% - 2rem) !important;
    text-align: center !important;
    justify-content: center !important;
    cursor: pointer !important;
}}
.logout-wrap .stButton > button:hover {{
    background: rgba(255,61,87,0.08) !important;
    border-color: rgba(255,61,87,0.25) !important;
    color: #ff3d57 !important;
    box-shadow: none !important;
    transform: none !important;
}}

/* ── Main content padding ───────────────────────────────────── */
.main .block-container {{
    padding: 1.8rem 2.4rem 2.4rem !important;
    max-width: none !important;
}}

/* ── Cards ──────────────────────────────────────────────────── */
.sg-card {{
    background: #0d0d0d;
    border: 1px solid #1a1a1a;
    border-radius: 16px;
    padding: 1.5rem 1.75rem;
    margin-bottom: 1.2rem;
    box-shadow: 0 4px 24px rgba(0,0,0,0.55);
}}
[data-testid="stVerticalBlockBorderWrapper"] {{
    background: #0d0d0d !important;
    border: 1px solid #1a1a1a !important;
    border-radius: 16px !important;
    padding: 1.4rem 1.6rem !important;
    box-shadow: 0 4px 24px rgba(0,0,0,0.5) !important;
}}

/* ── Plotly chart containers: explicit dark background ──────── */
[data-testid="stPlotlyChart"] {{
    background: #060606 !important;
    border-radius: 12px !important;
    overflow: hidden !important;
}}
[data-testid="stPlotlyChart"] > div {{
    background: transparent !important;
}}
.js-plotly-plot, .plotly {{
    background: transparent !important;
}}

/* ── Section label ──────────────────────────────────────────── */
.sg-title {{
    font-size: 0.67rem;
    font-weight: 700;
    letter-spacing: 0.13em;
    text-transform: uppercase;
    color: #686868;
    margin-bottom: 0.9rem;
}}

/* ── Badges ─────────────────────────────────────────────────── */
.sg-badge {{
    display: inline-block;
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    padding: 2px 8px;
    border-radius: 99px;
}}
.sg-badge.green {{ background:rgba(0,230,118,.10); color:#00e676; border:1px solid rgba(0,230,118,.22); }}
.sg-badge.amber {{ background:rgba(255,171,64,.10); color:#ffab40; border:1px solid rgba(255,171,64,.22); }}
.sg-badge.red   {{ background:rgba(255,61,87,.10);  color:#ff3d57; border:1px solid rgba(255,61,87,.22); }}
.sg-badge.blue  {{ background:rgba(41,121,255,.12); color:#2979ff; border:1px solid rgba(41,121,255,.25); }}

/* ── Metric cards ───────────────────────────────────────────── */
.sg-metric {{
    background: #0d0d0d;
    border: 1px solid #1a1a1a;
    border-radius: 14px;
    padding: 1.2rem 1rem;
    text-align: center;
    position: relative;
    overflow: hidden;
}}
.sg-metric::before {{ content:''; position:absolute; top:0;left:0;right:0; height:3px; }}
.sg-metric.green::before {{ background:#00e676; }}
.sg-metric.amber::before {{ background:#ffab40; }}
.sg-metric.red::before   {{ background:#ff3d57; }}
.sg-metric-label {{ font-size:.72rem; font-weight:600; color:#777; letter-spacing:.07em; text-transform:uppercase; margin-bottom:.4rem; }}
.sg-metric-value {{ font-size:2.5rem; font-weight:800; line-height:1; }}
.sg-metric-value.green {{ color:#00e676; }}
.sg-metric-value.amber {{ color:#ffab40; }}
.sg-metric-value.red   {{ color:#ff3d57; }}
.sg-metric-sub   {{ font-size:.77rem; color:#777; margin-top:.35rem; line-height:1.5; }}

/* ── Expander ───────────────────────────────────────────────── */
div[data-testid="stExpander"] {{
    background: #0d0d0d !important;
    border: 1px solid #1a1a1a !important;
    border-radius: 12px !important;
    margin-bottom:.55rem; overflow:hidden;
}}
div[data-testid="stExpander"] summary {{
    font-size:1rem !important; font-weight:600 !important;
    color:#e0e0e0 !important; padding:.82rem 1rem !important;
    background:transparent !important;
    cursor: pointer !important;
}}
div[data-testid="stExpander"] summary:hover {{ background:#0f0f0f !important; }}
div[data-testid="stExpander"] > div {{ padding:0 1rem 1rem !important; }}

/* ── Text defaults ──────────────────────────────────────────── */
p, li, .stMarkdown {{ color:#c0c8d8 !important; }}
h1,h2,h3 {{ color:#f0f0f0 !important; font-weight:800 !important; }}
.stCaption {{ color:#777 !important; }}
.stCaption p {{ color:#777 !important; }}
hr {{ border-color:#1a1a1a !important; }}
.stSpinner > div {{ border-top-color:#2979ff !important; }}

/* ── All inputs ─────────────────────────────────────────────── */
[data-testid="stTextInput"] > div > div,
[data-testid="stTextInput"] input {{
    background: #111 !important;
    border: 1px solid #242424 !important;
    border-radius: 10px !important;
    color: #f0f0f0 !important;
    font-size: 0.9rem !important;
    transition: border-color .18s ease, box-shadow .18s ease !important;
    cursor: text !important;
}}
[data-testid="stTextInput"] input:focus {{
    border-color: #2979ff !important;
    box-shadow: 0 0 0 3px rgba(41,121,255,.15) !important;
    outline: none !important;
}}
[data-testid="stTextInput"] input::placeholder {{ color:#333 !important; }}
[data-testid="stTextInput"] label {{ color:#9e9e9e !important; font-size:.82rem !important; }}

/* Search icon on student ID field */
[data-testid="stTextInput"] input[placeholder="e.g. S001"] {{
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%23444' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='11' cy='11' r='8'/%3E%3Cline x1='21' y1='21' x2='16.65' y2='16.65'/%3E%3C/svg%3E") !important;
    background-repeat: no-repeat !important;
    background-position: 0.85rem center !important;
    background-size: 15px 15px !important;
    padding-left: 2.5rem !important;
}}

/* ── Selectbox ──────────────────────────────────────────────── */
[data-testid="stSelectbox"] > div > div {{
    background: #111 !important;
    border: 1px solid #242424 !important;
    border-radius: 10px !important;
    color: #f0f0f0 !important;
    cursor: pointer !important;
}}
[data-testid="stSelectbox"] svg {{ fill: #444 !important; }}
[data-testid="stSelectbox"] > div > div:focus-within {{
    border-color: #2979ff !important;
    box-shadow: 0 0 0 3px rgba(41,121,255,.15) !important;
}}
[data-testid="stSelectbox"] label {{ color:#9e9e9e !important; font-size:.82rem !important; }}

/* ── Toggle ─────────────────────────────────────────────────── */
[data-testid="stToggle"] p {{ color:#9e9e9e !important; font-size:0.85rem !important; }}
[data-testid="stToggle"] label {{ gap:.6rem !important; cursor:pointer !important; }}
[data-testid="stToggle"] label div[data-testid="stToggleSwitch"] {{ background:#242424 !important; }}
[data-testid="stToggle"] label span[aria-checked="true"] {{ background:#2979ff !important; }}

/* ── Global button (main area) ──────────────────────────────── */
.stButton > button {{
    background: #2979ff !important;
    color: #fff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: .92rem !important;
    padding: .62rem 1.35rem !important;
    transition: background .18s ease, box-shadow .18s ease, transform .15s ease !important;
    cursor: pointer !important;
}}
.stButton > button:hover {{
    background: #1a4ecc !important;
    box-shadow: 0 0 20px rgba(41,121,255,.38) !important;
    transform: translateY(-1px) !important;
}}
.stButton > button:active {{
    transform: translateY(0) !important;
}}

/* ── Form submit buttons ────────────────────────────────────── */
[data-testid="stFormSubmitButton"] > button {{
    cursor: pointer !important;
}}

/* ── CTA gradient button ────────────────────────────────────── */
.cta-wrap .stButton > button {{
    background: linear-gradient(135deg, #1457c8 0%, #2979ff 52%, #00b4d8 100%) !important;
    border-radius: 12px !important;
    font-size: 0.96rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.025em !important;
    padding: 0.82rem 1.5rem !important;
    box-shadow: 0 4px 22px rgba(41,121,255,.38) !important;
    transition: all .22s ease !important;
}}
.cta-wrap .stButton > button:hover {{
    background: linear-gradient(135deg, #1a62d8 0%, #448aff 52%, #18d4e8 100%) !important;
    box-shadow: 0 6px 30px rgba(41,121,255,.58) !important;
    transform: translateY(-2px) !important;
}}

/* ── Ghost link button ──────────────────────────────────────── */
.ghost-btn-wrap .stButton > button {{
    background: transparent !important;
    color: #2979ff !important;
    border: none !important;
    box-shadow: none !important;
    font-size: .82rem !important;
    font-weight: 600 !important;
    padding: .2rem 0 !important;
    text-decoration: underline !important;
    text-underline-offset: 3px !important;
    transform: none !important;
}}
.ghost-btn-wrap .stButton > button:hover {{
    background: transparent !important;
    box-shadow: none !important;
    color: #5a9fff !important;
    transform: none !important;
}}

/* ── Eye toggle button (small, in form) ─────────────────────── */
.eye-btn-wrap [data-testid="stFormSubmitButton"] > button {{
    background: #111 !important;
    border: 1px solid #242424 !important;
    color: #777 !important;
    font-size: .78rem !important;
    font-weight: 600 !important;
    padding: .6rem .8rem !important;
    border-radius: 10px !important;
    letter-spacing: .04em !important;
    box-shadow: none !important;
}}
.eye-btn-wrap [data-testid="stFormSubmitButton"] > button:hover {{
    background: #1a1a1a !important;
    color: #bbb !important;
    border-color: #2979ff !important;
    box-shadow: none !important;
    transform: none !important;
}}

/* ── Auth banners ───────────────────────────────────────────── */
.auth-error {{
    background:rgba(255,61,87,.09); border:1px solid rgba(255,61,87,.28);
    border-radius:9px; color:#ff3d57; font-size:.82rem; font-weight:500;
    padding:.6rem .95rem; margin-bottom:1rem; text-align:center; line-height:1.5;
    display:flex; align-items:center; justify-content:center; gap:.45rem;
}}
.auth-success {{
    background:rgba(0,230,118,.08); border:1px solid rgba(0,230,118,.22);
    border-radius:9px; color:#00e676; font-size:.82rem; font-weight:500;
    padding:.6rem .95rem; margin-bottom:1rem; text-align:center;
    display:flex; align-items:center; justify-content:center; gap:.45rem;
}}

/* ── Role pill radio (register page) ────────────────────────── */
div[data-testid="stRadio"] > div {{
    display:flex !important; flex-direction:row !important;
    gap:.45rem !important; flex-wrap:wrap !important; align-items:center !important;
}}
div[data-testid="stRadio"] label {{
    background:#111 !important; border:1px solid #242424 !important;
    border-radius:99px !important; padding:.38rem 1.05rem !important;
    cursor:pointer !important; transition:all .16s ease !important;
    display:inline-flex !important; align-items:center !important;
}}
div[data-testid="stRadio"] label > div:first-child {{ display:none !important; }}
div[data-testid="stRadio"] label p,
div[data-testid="stRadio"] label div:last-child {{
    font-size:.83rem !important; font-weight:600 !important;
    color:#666 !important; margin:0 !important; line-height:1 !important;
}}
div[data-testid="stRadio"] label:has(input:checked) {{
    background:rgba(41,121,255,.14) !important; border-color:#2979ff !important;
}}
div[data-testid="stRadio"] label:has(input:checked) p,
div[data-testid="stRadio"] label:has(input:checked) div:last-child {{ color:#2979ff !important; }}
div[data-testid="stRadio"] label:hover {{ border-color:rgba(41,121,255,.4) !important; }}

/* ── Alert override ─────────────────────────────────────────── */
.stAlert {{ border-radius:10px !important; }}
[data-testid="stAlert"] {{ border-radius:10px !important; }}

/* ── Subject cards hover ────────────────────────────────────── */
.subj-card {{
    transition: transform .2s ease, box-shadow .2s ease;
    cursor: default;
}}
.subj-card:hover {{
    transform: translateY(-3px);
    box-shadow: 0 10px 32px rgba(0,0,0,.65) !important;
}}

/* ── Top progress bar animation ─────────────────────────────── */
@keyframes sg-topbar {{
    0%   {{ width: 0%;   opacity: 1; }}
    15%  {{ width: 35%;  opacity: 1; }}
    50%  {{ width: 72%;  opacity: 1; }}
    85%  {{ width: 90%;  opacity: 1; }}
    100% {{ width: 100%; opacity: 0; }}
}}
.sg-topbar-progress {{
    position: fixed;
    top: 0; left: 0;
    height: 3px;
    z-index: 99999;
    background: linear-gradient(90deg, #1457c8, #2979ff 50%, #00c8e0);
    box-shadow: 0 0 14px rgba(41,121,255,.7);
    animation: sg-topbar 3s cubic-bezier(0.4, 0, 0.2, 1) forwards;
    pointer-events: none;
}}

/* ── Data table ─────────────────────────────────────────────── */
[data-testid="stDataFrame"] {{
    border-radius: 12px !important;
    overflow: hidden !important;
    border: 1px solid #1a1a1a !important;
}}
</style>
"""
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ============================================================
# SESSION STATE
# ============================================================

_defaults = {
    "is_authenticated": False,
    "show_register":    False,
    "login_error":      "",
    "show_password":    False,
    "register_error":   "",
    "register_success": "",
    "user_email":       "",
    "user_name":        "",
    "user_role":        "",
    "student_id":       "",
    "nav_page":         "Dashboard",
}
for _k, _v in _defaults.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ============================================================
# AUTH HELPERS
# ============================================================

def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def _valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email.strip()))

def _password_strength(pw: str):
    if not pw:
        return 0, "", "#1a1a1a"
    score = sum([
        len(pw) >= 8,
        any(c.isupper() for c in pw),
        any(c.isdigit() for c in pw),
        any(c in r'!@#$%^&*()_+-=[]{}|;:\'",.<>?/`~\\' for c in pw),
    ])
    labels = ["Very Weak", "Weak", "Fair", "Strong"]
    colors = ["#ff3d57", "#ff7043", "#ffab40", "#00e676"]
    idx = max(score - 1, 0)
    return score, labels[idx], colors[idx]

def _strength_bar_html(pw: str) -> str:
    score, label, color = _password_strength(pw)
    segs = "".join(
        f'<div style="height:3px;flex:1;border-radius:2px;'
        f'background:{color if i < score else "#1a1a1a"};transition:background .25s"></div>'
        for i in range(4)
    )
    lbl = (
        f'<div style="font-size:.69rem;font-weight:700;color:{color};margin-top:4px;letter-spacing:.05em">{label}</div>'
        if label else '<div style="min-height:1.1rem"></div>'
    )
    return f'<div style="display:flex;gap:4px;margin-top:7px">{segs}</div>{lbl}'

def _get_initials(name: str) -> str:
    parts = name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[:2].upper() if len(name) >= 2 else name.upper()

_USERS_COLS = ["id", "full_name", "email", "password_hash", "role", "student_id",
               "created_at", "last_login", "is_active"]

def _register_user(full_name, email, pw_hash, role, student_id=""):
    try:
        client = get_gs_client()
        sp = get_spreadsheet(client)
        ex = pd.DataFrame()
        try:
            ex = read_table(sp, "users")
            if not ex.empty and "email" in ex.columns:
                if email.lower() in ex["email"].str.lower().str.strip().values:
                    return "An account with this email already exists."
        except Exception:
            pass

        new_row_data = {
            "id":            str(uuid.uuid4()),
            "full_name":     full_name.strip(),
            "email":         email.lower().strip(),
            "password_hash": pw_hash,
            "role":          role,
            "student_id":    student_id.strip() if role == "Student" else "",
            "created_at":    datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "last_login":    "",
            "is_active":     "true",
        }

        if not ex.empty:
            # Ensure every canonical column exists (adds student_id if missing)
            for col in _USERS_COLS:
                if col not in ex.columns:
                    ex[col] = ""
            extra = [c for c in ex.columns if c not in _USERS_COLS]
            ex = ex.reindex(columns=_USERS_COLS + extra, fill_value="")
            new_row = pd.DataFrame([{c: new_row_data.get(c, "") for c in ex.columns}])
            combined = pd.concat([ex, new_row], ignore_index=True)
        else:
            combined = pd.DataFrame([new_row_data]).reindex(columns=_USERS_COLS, fill_value="")

        write_table(sp, "users", combined)
        return None
    except Exception as exc:
        return f"Registration failed: {exc}"


@st.cache_resource(show_spinner=False)
def _init_users_sheet():
    """Run once per server process: ensure users sheet + seed default admin."""
    try:
        client = get_gs_client()
        sp = get_spreadsheet(client)
        try:
            users_df = read_table(sp, "users")
        except Exception:
            users_df = pd.DataFrame()

        admin_email = "admin@school.com"
        already_seeded = (
            not users_df.empty
            and "email" in users_df.columns
            and admin_email in users_df["email"].str.lower().str.strip().values
        )
        if not already_seeded:
            append_table(sp, "users", pd.DataFrame([{
                "id":            str(uuid.uuid4()),
                "full_name":     "Admin",
                "email":         admin_email,
                "password_hash": _hash("Admin@123"),
                "role":          "Admin",
                "created_at":    datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "last_login":    "",
                "is_active":     "true",
            }]))
    except Exception:
        pass


_init_users_sheet()

# ============================================================
# AUTH PAGE CSS
# ============================================================

AUTH_CSS = """
<style>
.auth-logo    { font-size:1.65rem; font-weight:800; color:#2979ff; letter-spacing:-.025em; text-align:center; margin-bottom:.25rem; display:flex; align-items:center; justify-content:center; gap:.55rem; }
.auth-tagline { font-size:.8rem; color:#777; text-align:center; margin-bottom:1.8rem; line-height:1.55; }
.auth-section-label { font-size:.68rem; font-weight:700; letter-spacing:.1em; text-transform:uppercase; color:#666; margin-bottom:.55rem; margin-top:.2rem; }
.auth-footer  { text-align:center; font-size:.78rem; color:#666; margin-top:1.3rem; }
.auth-divider { border:none; border-top:1px solid #1a1a1a; margin:1.4rem 0 1.1rem; }
.auth-hint    { font-size:.68rem; color:#444; text-align:center; margin-top:.9rem; line-height:1.55; }
.auth-hint code { color:#555; font-size:.66rem; background:#0d0d0d; padding:1px 4px; border-radius:4px; }
</style>
"""

# ============================================================
# LOGIN PAGE
# ============================================================

def show_login():
    st.markdown(AUTH_CSS, unsafe_allow_html=True)
    _, col, _ = st.columns([1, 1.35, 1])
    with col:
        st.markdown(
            f'<div class="auth-logo">{LOGO_SVG} STEM Globe</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="auth-tagline">Clear academic insights for<br>students, parents &amp; educators</div>',
            unsafe_allow_html=True,
        )

        if st.session_state.register_success:
            st.markdown(
                f'<div class="auth-success">'
                f'{icon("check", "#00e676", 14)}'
                f'&nbsp;{st.session_state.register_success}</div>',
                unsafe_allow_html=True,
            )
            st.session_state.register_success = ""

        if st.session_state.login_error:
            st.markdown(
                f'<div class="auth-error">'
                f'{icon("alert", "#ff3d57", 14)}'
                f'&nbsp;{st.session_state.login_error}</div>',
                unsafe_allow_html=True,
            )

        with st.form("login_form", clear_on_submit=False):
            email    = st.text_input("Email address", placeholder="you@example.com")
            password = st.text_input(
                "Password",
                type="text" if st.session_state.show_password else "password",
                placeholder="••••••••",
            )
            btn_c, eye_c = st.columns([3, 1])
            with btn_c:
                submitted = st.form_submit_button("Sign In", use_container_width=True)
            with eye_c:
                st.markdown('<div class="eye-btn-wrap">', unsafe_allow_html=True)
                toggle = st.form_submit_button(
                    "Hide" if st.session_state.show_password else "Show",
                    use_container_width=True,
                )
                st.markdown('</div>', unsafe_allow_html=True)

            if toggle:
                st.session_state.show_password = not st.session_state.show_password
                st.rerun()

            if submitted:
                e = email.strip().lower()
                if not e or not password:
                    st.session_state.login_error = "Please enter your email and password."
                    st.rerun()
                elif DEMO_USERS.get(e) == password:
                    u_name, u_role = DEMO_META.get(e, (e.split("@")[0].title(), "User"))
                    st.session_state.update(
                        is_authenticated=True, login_error="",
                        user_email=e, user_name=u_name, user_role=u_role,
                        show_password=False,
                    )
                    st.rerun()
                else:
                    authed = False
                    try:
                        client = get_gs_client()
                        sp = get_spreadsheet(client)
                        users_df = read_table(sp, "users")
                        if not users_df.empty and "email" in users_df.columns:
                            m = users_df[users_df["email"].str.lower().str.strip() == e]
                            if not m.empty:
                                row = m.iloc[0]
                                if row.get("password_hash", "") == _hash(password):
                                    user_role = row.get("role", "User")
                                    session_updates = dict(
                                        is_authenticated=True, login_error="",
                                        user_email=e,
                                        user_name=row.get("full_name", e.split("@")[0].title()),
                                        user_role=user_role,
                                        show_password=False,
                                    )
                                    if user_role == "Student":
                                        sid_val = str(row.get("student_id", "")).strip()
                                        if not sid_val:
                                            try:
                                                sdf = read_table(sp, "students")
                                                if not sdf.empty:
                                                    for ecol in ("email", "Email"):
                                                        if ecol in sdf.columns:
                                                            sm = sdf[sdf[ecol].str.lower().str.strip() == e]
                                                            if not sm.empty:
                                                                for scol in ("student_id", "Student ID", "StudentID", "id", "ID"):
                                                                    if scol in sm.columns:
                                                                        sid_val = str(sm.iloc[0][scol]).strip()
                                                                        break
                                                                break
                                            except Exception:
                                                pass
                                        session_updates["student_id"] = sid_val
                                    st.session_state.update(session_updates)
                                    authed = True
                                    st.rerun()
                    except Exception:
                        pass
                    if not authed:
                        st.session_state.login_error = "Invalid email or password."
                        st.rerun()

        st.markdown('<hr class="auth-divider">', unsafe_allow_html=True)
        st.markdown('<div class="auth-footer">Don\'t have an account?</div>', unsafe_allow_html=True)
        st.markdown('<div class="ghost-btn-wrap">', unsafe_allow_html=True)
        if st.button("Create an account", key="go_register"):
            st.session_state.show_register = True
            st.session_state.login_error   = ""
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="auth-hint">Demo &mdash; <code>demo@stemglobe.io</code> / <code>demo1234</code>'
            '<br>Admin &mdash; <code>admin@school.com</code> / <code>Admin@123</code></div>',
            unsafe_allow_html=True,
        )

# ============================================================
# REGISTER PAGE
# ============================================================

def show_register():
    st.markdown(AUTH_CSS, unsafe_allow_html=True)
    _, col, _ = st.columns([1, 1.35, 1])
    with col:
        st.markdown(
            f'<div class="auth-logo">{LOGO_SVG} STEM Globe</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="auth-tagline">Create your account</div>', unsafe_allow_html=True)

        if st.session_state.register_error:
            st.markdown(
                f'<div class="auth-error">'
                f'{icon("alert", "#ff3d57", 14)}'
                f'&nbsp;{st.session_state.register_error}</div>',
                unsafe_allow_html=True,
            )

        full_name = st.text_input("Full Name",        placeholder="Jane Smith",             key="reg_full_name")
        email     = st.text_input("Email address",    placeholder="you@example.com",        key="reg_email")
        password  = st.text_input("Password",         type="password",
                                  placeholder="Min 8 characters",                           key="reg_password")
        st.markdown(_strength_bar_html(password), unsafe_allow_html=True)
        confirm   = st.text_input("Confirm Password", type="password",
                                  placeholder="Re-enter password",                          key="reg_confirm")

        st.markdown('<div class="auth-section-label" style="margin-top:.9rem">I am a</div>',
                    unsafe_allow_html=True)
        role = st.radio("Role", options=ROLES, index=2, horizontal=True,
                        key="reg_role", label_visibility="collapsed")

        reg_student_id = ""
        if role == "Student":
            st.markdown("<div style='height:.3rem'></div>", unsafe_allow_html=True)
            reg_student_id = st.text_input(
                "Student ID (optional)",
                placeholder="e.g. S001 — you can also link this later",
                key="reg_student_id",
            )

        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
        create = st.button("Create Account", use_container_width=True, key="do_register")

        if create:
            err = None
            if not full_name.strip():          err = "Full name is required."
            elif not _valid_email(email):      err = "Please enter a valid email address."
            elif len(password) < 8:            err = "Password must be at least 8 characters."
            elif password != confirm:          err = "Passwords do not match."
            if err:
                st.session_state.register_error = err
                st.rerun()
            else:
                error = _register_user(full_name, email, _hash(password), role,
                                       student_id=reg_student_id)
                if error:
                    st.session_state.register_error = error
                    st.rerun()
                else:
                    st.session_state.register_error   = ""
                    st.session_state.register_success = f"Account created for {email.strip()}! Sign in below."
                    st.session_state.show_register    = False
                    for k in ("reg_full_name", "reg_email", "reg_password", "reg_confirm",
                               "reg_role", "reg_student_id"):
                        st.session_state.pop(k, None)
                    st.rerun()

        st.markdown('<hr class="auth-divider">', unsafe_allow_html=True)
        st.markdown('<div class="ghost-btn-wrap">', unsafe_allow_html=True)
        if st.button("← Back to Login", key="go_login"):
            st.session_state.show_register  = False
            st.session_state.register_error = ""
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# GATE
# ============================================================

if not st.session_state.is_authenticated:
    if st.session_state.show_register:
        show_register()
    else:
        show_login()
    st.stop()

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    # ── Logo ────────────────────────────────────────────────
    st.markdown(f"""
    <div style="padding:1.6rem 1.25rem .9rem;display:flex;align-items:center;gap:.65rem;">
        {icon("globe", "#2979ff", 24, 1.7)}
        <div>
            <div style="font-size:1.2rem;font-weight:800;color:#2979ff;letter-spacing:-.025em;line-height:1;">
                STEM Globe
            </div>
            <div style="font-size:.58rem;color:#2a2a2a;letter-spacing:.12em;text-transform:uppercase;margin-top:2px;">
                Intelligence Platform
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<hr style="border:none;border-top:1px solid #161616;margin:0 1.1rem .6rem;">', unsafe_allow_html=True)

    st.markdown("""
    <div style="font-size:.58rem;font-weight:700;color:#272727;letter-spacing:.16em;
                text-transform:uppercase;padding:.6rem 1.25rem .3rem;">
        Menu
    </div>
    """, unsafe_allow_html=True)

    # ── Nav items ────────────────────────────────────────────
    current_page = st.session_state.nav_page
    u_role       = st.session_state.user_role or ""
    allowed      = ROLE_NAV_ACCESS.get(u_role, NAV_ITEMS)

    for page in NAV_ITEMS:
        if page not in allowed:
            continue
        is_active = (page == current_page)
        cls = f"nav-{page.lower()} " + ("nav-active" if is_active else "nav-default")
        st.markdown(f'<div class="{cls}" style="padding:0 .75rem .15rem;">', unsafe_allow_html=True)
        if st.button(page, key=f"nav_{page}", use_container_width=True):
            st.session_state.nav_page = page
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div style="height:1.8rem;"></div>', unsafe_allow_html=True)
    st.markdown('<hr style="border:none;border-top:1px solid #161616;margin:0 1.1rem .75rem;">', unsafe_allow_html=True)

    # ── User info ────────────────────────────────────────────
    u_name     = st.session_state.user_name or "User"
    u_initials = _get_initials(u_name)
    r_color    = ROLE_COLORS.get(u_role, "#444")

    st.markdown(f"""
    <div style="padding:.1rem 1.1rem .8rem;display:flex;align-items:center;gap:.75rem;">
        <div style="
            width:36px;height:36px;border-radius:50%;flex-shrink:0;
            background:rgba(41,121,255,.16);border:1px solid rgba(41,121,255,.28);
            display:flex;align-items:center;justify-content:center;
            font-size:.8rem;font-weight:700;color:#2979ff;
        ">{u_initials}</div>
        <div>
            <div style="font-size:.84rem;font-weight:600;color:#ddd;line-height:1.2;">{u_name}</div>
            <div style="font-size:.65rem;font-weight:700;color:{r_color};letter-spacing:.07em;text-transform:uppercase;margin-top:2px;">{u_role}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Logout ───────────────────────────────────────────────
    st.markdown('<div class="logout-wrap">', unsafe_allow_html=True)
    if st.button("Sign Out", key="signout", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# CLOUD: DIRECT GOOGLE SHEETS DATA LOADER
# Replicates the Render /student-summary endpoint locally so
# the app works on Streamlit Cloud without a FastAPI server.
# ============================================================

def _normalize_val(value):
    """Normalize a raw Google Sheets cell value for UI display."""
    if value is None:
        return ""
    try:
        if isinstance(value, float) and pd.isna(value):
            return ""
    except Exception:
        pass
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        v = value.strip()
        try:
            return json.loads(v)
        except Exception:
            return v
    return value


def _df_to_records(df: pd.DataFrame) -> list:
    """Convert a DataFrame to a normalized list-of-dicts for the UI."""
    if df is None or df.empty:
        return []
    records = json.loads(df.to_json(orient="records"))
    return [{k: _normalize_val(v) for k, v in row.items()} for row in records]


def _load_cached_direct(student_id: str) -> dict:
    """
    Read pre-computed student data from Google Sheets directly.

    Raises:
        LookupError("NOT_FOUND:True")  – student in raw data but not yet processed
        LookupError("NOT_FOUND:False") – student not in system at all
        ValueError("NO_DATA")          – no pipeline data exists yet
    """
    client = get_gs_client()
    sheet  = get_spreadsheet(client)
    sid    = student_id.strip().upper()

    def _safe_read(name: str) -> pd.DataFrame:
        try:
            df = read_table(sheet, name)
            if not df.empty and "student_id" in df.columns:
                df = df.copy()
                df["student_id"] = df["student_id"].astype(str).str.strip().str.upper()
            return df
        except Exception:
            return pd.DataFrame()

    analytics    = _safe_read("subject_analytics")
    summaries    = _safe_read("subject_summaries")
    insights_df  = _safe_read("subject_insights")
    consolidated = _safe_read("student_consolidated_latest")
    validated    = _safe_read("validated_results")

    if analytics.empty or summaries.empty:
        raise ValueError("NO_DATA")

    a = analytics[analytics["student_id"] == sid]
    s = summaries[summaries["student_id"] == sid]
    i = insights_df[insights_df["student_id"] == sid] if not insights_df.empty else pd.DataFrame()
    c = consolidated[consolidated["student_id"] == sid] if not consolidated.empty else pd.DataFrame()

    if a.empty or s.empty or c.empty:
        in_raw = (
            not validated.empty
            and "student_id" in validated.columns
            and sid in validated["student_id"].values
        )
        raise LookupError(f"NOT_FOUND:{in_raw}")

    # Student metadata
    student_name: str   = ""
    grade:        object = ""
    if not validated.empty and "student_id" in validated.columns:
        v_row = validated[validated["student_id"] == sid]
        if not v_row.empty:
            r = v_row.iloc[0]
            student_name = _normalize_val(r.get("Name", ""))
            try:
                grade = int(r.get("grade", ""))
            except Exception:
                grade = str(r.get("grade", ""))

    cons_row = c.iloc[0]

    # Build per-subject explainability map
    explain_map: dict = {}
    for rec in _df_to_records(i):
        explain_map[rec.get("subject", "")] = {
            "explanation_summary":    _normalize_val(rec.get("explanation_summary")),
            "key_evidence_points":    _normalize_val(rec.get("key_evidence_points")) or [],
            "confidence_in_insight":  _normalize_val(rec.get("confidence_in_insight")),
            "recommended_focus_area": _normalize_val(rec.get("recommended_focus_area")),
        }

    subject_summaries_list = [
        {**subj, "explainability": explain_map.get(subj.get("subject", ""), {})}
        for subj in _df_to_records(s)
    ]

    perf_cols = [col for col in ["subject", "average_score", "latest_score", "trend", "risk_flag"]
                 if col in a.columns]
    perf_df   = a[perf_cols].sort_values("subject") if "subject" in perf_cols else a[perf_cols]

    return {
        "student_id":             sid,
        "student_name":           student_name,
        "grade":                  grade,
        "overall_summary":        _normalize_val(cons_row.get("overall_summary")),
        "recommended_next_steps": _normalize_val(cons_row.get("recommended_next_steps")),
        "numerical_performance":  _df_to_records(perf_df),
        "subject_summaries":      subject_summaries_list,
        "mode":                   "cached",
        "llm_provider_used":      _normalize_val(cons_row.get("llm_provider", "ollama")),
    }

# ============================================================
# HELPERS
# ============================================================

def score_color(score):
    try:
        s = float(score)
    except Exception:
        return "amber"
    return "green" if s >= 70 else "amber" if s >= 50 else "red"

def trend_label(trend):
    t = str(trend).lower()
    if "up" in t or "improv" in t:   return "↑ Improving"
    if "down" in t or "declin" in t: return "↓ Declining"
    return "— Stable"

def trend_color(trend):
    t = str(trend).lower()
    if "up" in t or "improv" in t:   return "green"
    if "down" in t or "declin" in t: return "red"
    return "amber"

def normalize_next_steps(value):
    if not value: return []
    if isinstance(value, dict): return [f"{k}: {v}" for k, v in value.items()]
    if isinstance(value, list): return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict): return [f"{k}: {v}" for k, v in parsed.items()]
            if isinstance(parsed, list): return parsed
        except Exception:
            return [value]
    return []

def _section_label(text: str, color: str = "#2979ff") -> str:
    return (
        f'<div style="font-size:.67rem;font-weight:700;letter-spacing:.13em;'
        f'text-transform:uppercase;color:{color};margin-bottom:.9rem;">{text}</div>'
    )

@st.cache_data(ttl=300, show_spinner=False)
def _cached_sheet(_table: str) -> list:
    """Read a Google Sheets tab and return records as a list-of-dicts, cached for 5 min."""
    _cli = get_gs_client()
    _sp = get_spreadsheet(_cli)
    _df = read_table(_sp, _table)
    return [] if _df.empty else _df.to_dict("records")

# ============================================================
# DASHBOARD PAGE
# ============================================================

def show_dashboard():
    role = st.session_state.user_role or "User"
    name = st.session_state.user_name or "User"
    is_student = (role == "Student")

    # ── Pipeline job polling ─────────────────────────────────
    _job_id = st.session_state.get("_pipeline_job_id")
    if _job_id and IS_CLOUD:
        # Pipeline jobs run on Render; clear any stale state on cloud
        st.session_state.pop("_pipeline_job_id", None)
        st.session_state.pop("_pipeline_target_sid", None)
        _job_id = None
    if _job_id:
        _target_sid = st.session_state.get("_pipeline_target_sid", "")
        try:
            _poll = requests.get(f"{API_BASE}/pipeline/status/{_job_id}", timeout=10)
            _jstate = _poll.json() if _poll.ok else {"status": "unknown"}
        except Exception:
            _jstate = {"status": "unknown"}
        _jstatus = _jstate.get("status", "unknown")
        if _jstatus == "running":
            _run_msg = (
                f"Processing <strong style='color:#e0e0e0'>{_target_sid}</strong> — "
                if _target_sid else ""
            )
            st.markdown(f"""
            <div style="background:rgba(41,121,255,.09);border:1px solid rgba(41,121,255,.28);
                        border-radius:12px;padding:1.4rem 1.6rem;margin-bottom:1.5rem;">
              <div style="font-size:.85rem;font-weight:700;color:#2979ff;margin-bottom:.35rem;">
                {_run_msg}Pipeline Running&hellip;
              </div>
              <div style="font-size:.8rem;color:#888;line-height:1.6;">
                Running all pipeline phases. This may take a few minutes.
                The page will refresh automatically.
              </div>
            </div>
            """, unsafe_allow_html=True)
            time.sleep(4)
            st.rerun()
        elif _jstatus == "done":
            st.session_state.pop("_pipeline_job_id", None)
            _done_sid = st.session_state.pop("_pipeline_target_sid", "")
            if _done_sid and not is_student:
                st.session_state["dashboard_student_id"] = _done_sid
            st.session_state["_auto_generate"] = True
            st.rerun()
        else:
            _err = _jstate.get("error", "")
            st.session_state.pop("_pipeline_job_id", None)
            st.session_state.pop("_pipeline_target_sid", None)
            st.markdown(
                f'<div class="auth-error">{icon("alert","#ff3d57",14)}&nbsp;'
                f'Pipeline failed: {_err or "Check server logs for details."}</div>',
                unsafe_allow_html=True,
            )

    # ── Preload from Students page ───────────────────────────
    _preload = st.session_state.pop("_preload_sid", None)
    if _preload and not is_student:
        st.session_state["dashboard_student_id"] = _preload
        st.session_state["_auto_generate"] = True
        st.rerun()

    role_greet = {
        "Admin":   f"Welcome, {name}. Full system access.",
        "Teacher": f"Welcome, {name}. View student reports and class insights.",
        "Parent":  f"Welcome, {name}. Track your child’s progress.",
        "Student": f"Welcome, {name}. Check your academic performance.",
    }

    st.markdown(f"""
    <div style="margin-bottom:1.6rem;padding-top:.3rem;">
        <div style="font-size:.63rem;font-weight:700;color:#666;letter-spacing:.14em;text-transform:uppercase;margin-bottom:.35rem;">
            Dashboard
        </div>
        <div style="font-size:1.75rem;font-weight:800;color:#f0f0f0;letter-spacing:-.02em;line-height:1.15;">
            Student Intelligence
        </div>
        <div style="font-size:.84rem;color:#777;margin-top:.25rem;">
            {role_greet.get(role, "AI-powered insights across every subject, student, and grade")}
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="sg-title">Generate Student Report</div>', unsafe_allow_html=True)

        if is_student:
            student_id = st.session_state.get("student_id", "").strip()

            if not student_id:
                st.markdown(
                    '<div style="background:rgba(41,121,255,.07);border:1px solid rgba(41,121,255,.22);'
                    'border-radius:12px;padding:1rem 1.25rem;margin-bottom:1rem;">'
                    f'<div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.4rem;">'
                    f'{icon("user","#2979ff",15,2)}'
                    '<span style="font-size:.84rem;font-weight:700;color:#2979ff;">Link Your Student Account</span>'
                    '</div>'
                    '<p style="font-size:.81rem;color:#888;margin:0;line-height:1.55;">'
                    'Your account is not linked to a Student ID yet. Enter your ID below to load your report.'
                    '</p></div>',
                    unsafe_allow_html=True,
                )
                _lc1, _lc2 = st.columns([2, 1])
                with _lc1:
                    _new_sid = st.text_input("Enter your Student ID", placeholder="e.g. S001",
                                             key="link_sid_input", label_visibility="visible")
                with _lc2:
                    st.markdown("<div style='height:1.9rem'></div>", unsafe_allow_html=True)
                    _link_clicked = st.button("Link My Account", key="link_account_btn",
                                              use_container_width=True)

                if _link_clicked:
                    _typed = _new_sid.strip()
                    if _typed:
                        try:
                            _lc = get_gs_client()
                            _ls = get_spreadsheet(_lc)
                            update_user_student_id(_ls, st.session_state.user_email, _typed)
                        except Exception:
                            pass
                        st.session_state.student_id = _typed
                        st.session_state["_auto_generate"] = True
                        st.rerun()
                    else:
                        st.markdown(
                            f'<div class="auth-error">{icon("alert","#ff3d57",14)}'
                            '&nbsp;Please enter a valid Student ID.</div>',
                            unsafe_allow_html=True,
                        )
                st.stop()

            fast_mode = True if IS_CLOUD else st.toggle("Fast Mode  (local Ollama)", value=True, key="fast_mode")
        else:
            r1c1, r1c2 = st.columns([1.1, 0.9])
            with r1c1:
                student_id = st.text_input("Student ID", placeholder="e.g. S001", label_visibility="visible", key="dashboard_student_id")
            with r1c2:
                fast_mode = True if IS_CLOUD else st.toggle("Fast Mode  (local Ollama)", value=True, key="fast_mode")

        _PROVIDER_OPTIONS = [
            "Claude (Anthropic)",
            "OpenAI GPT",
            "Google Gemini",
            "DeepSeek",
            "Ollama (local only)",
        ]
        _PROVIDER_KEY_MAP = {
            "Claude (Anthropic)": "claude",
            "OpenAI GPT": "openai",
            "Google Gemini": "gemini",
            "DeepSeek": "deepseek",
            "Ollama (local only)": "ollama",
        }
        _PROVIDER_SECRET_KEY = {
            "claude": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
        }

        # Default: Claude for cloud (index 0), Ollama for local (last index)
        _default_idx = 0 if IS_CLOUD else len(_PROVIDER_OPTIONS) - 1
        _ai_col, _ = st.columns([1, 1])
        with _ai_col:
            _selected_display = st.selectbox(
                "AI Provider",
                options=_PROVIDER_OPTIONS,
                index=_default_idx,
                key="llm_provider_select",
            )

        llm_provider = _PROVIDER_KEY_MAP[_selected_display]
        st.session_state.selected_provider = llm_provider

        _ollama_in_cloud = IS_CLOUD and llm_provider == "ollama"

        if IS_CLOUD:
            if llm_provider == "ollama":
                st.markdown(
                    '<div style="background:rgba(255,171,64,.10);border:1px solid rgba(255,171,64,.35);'
                    'border-radius:10px;padding:.9rem 1.1rem;margin-top:.5rem;">'
                    '<div style="display:flex;align-items:flex-start;gap:.6rem;">'
                    '<span style="font-size:1rem;line-height:1.2;">⚠️</span>'
                    '<div>'
                    '<div style="font-size:.84rem;font-weight:700;color:#ffab40;margin-bottom:.3rem;">'
                    'Ollama is not available on the live website'
                    '</div>'
                    '<div style="font-size:.81rem;color:#bbb;line-height:1.6;">'
                    'Ollama runs on your local machine only. To use the live website, '
                    'select a cloud AI provider above.<br>'
                    'To use Ollama, run the app locally with:&nbsp;'
                    '<code style="background:#1a1a1a;padding:.1rem .45rem;border-radius:4px;'
                    'font-size:.77rem;color:#90caf9;">streamlit run ui_app.py</code>'
                    '</div>'
                    '</div>'
                    '</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )
            else:
                _secret_key = _PROVIDER_SECRET_KEY.get(llm_provider, "")
                _has_key = False
                try:
                    _has_key = bool(st.secrets.get(_secret_key))
                except Exception:
                    pass
                if not _has_key and _secret_key:
                    st.info(
                        f"API key for {_selected_display} is not configured. "
                        f"Ask the admin to add {_secret_key} to Streamlit secrets."
                    )

        st.markdown("<div style='height:.3rem'></div>", unsafe_allow_html=True)
        st.markdown('<div class="cta-wrap">', unsafe_allow_html=True)
        generate = st.button(
            "Load My Report" if is_student else "Generate Academic Report",
            use_container_width=True,
            key="generate_btn",
            disabled=_ollama_in_cloud,
        )
        st.markdown('</div>', unsafe_allow_html=True)

        _auto = bool(st.session_state.get("_auto_generate", False))
        if _auto:
            try:
                del st.session_state["_auto_generate"]
            except Exception:
                pass
        generate = generate or _auto

        if IS_CLOUD and not _ollama_in_cloud:
            st.markdown(
                '<div style="font-size:.7rem;color:#444;margin-top:.4rem;text-align:center;">'
                'Reading cached reports directly from Google Sheets</div>',
                unsafe_allow_html=True,
            )
        elif not IS_CLOUD and fast_mode:
            st.markdown(
                '<div style="font-size:.7rem;color:#444;margin-top:.4rem;text-align:center;">'
                'Fast Mode: using local Ollama — instant, no API key required'
                '</div>',
                unsafe_allow_html=True,
            )

    # ── Pipeline Controls (Teacher / Admin only) ─────────────
    if role in ("Teacher", "Admin"):
        with st.container(border=True):
            st.markdown('<div class="sg-title">Pipeline Controls</div>', unsafe_allow_html=True)
            if IS_CLOUD:
                _pc1, _pc2 = st.columns([2.5, 1])
                with _pc1:
                    st.markdown(
                        '<p style="font-size:.83rem;color:#777;margin:0;line-height:1.6;">'
                        'Re-process all students via the Render backend. '
                        'Reports will refresh in Google Sheets within a few minutes.</p>',
                        unsafe_allow_html=True,
                    )
                with _pc2:
                    if st.button("Run Pipeline", key="run_pipeline_cloud_btn", use_container_width=True):
                        try:
                            _fpr = requests.post(
                                "https://ai-student-intelligence.onrender.com/run-pipeline",
                                timeout=30,
                            )
                            if _fpr.ok:
                                st.success("Pipeline triggered. Reports will update shortly.")
                            else:
                                st.error(f"Pipeline returned HTTP {_fpr.status_code}.")
                        except Exception as _fpe:
                            st.error(f"Could not reach Render backend: {_fpe}")
            else:
                _pc1, _pc2 = st.columns([2.5, 1])
                with _pc1:
                    st.markdown(
                        '<p style="font-size:.83rem;color:#777;margin:0;line-height:1.6;">'
                        'Re-process all students through the analytics pipeline to refresh '
                        'reports, insights, and summaries.</p>',
                        unsafe_allow_html=True,
                    )
                with _pc2:
                    if st.button("Run Full Pipeline", key="run_full_pipeline_btn", use_container_width=True):
                        try:
                            _fpr = requests.post(
                                f"{API_BASE}/pipeline/run",
                                json={"student_id": "", "llm_provider": llm_provider},
                                timeout=20,
                            )
                            if _fpr.ok:
                                st.session_state["_pipeline_job_id"] = _fpr.json().get("job_id")
                                st.session_state.pop("_pipeline_target_sid", None)
                                st.rerun()
                            else:
                                st.error(f"Could not start pipeline (HTTP {_fpr.status_code}).")
                        except Exception as _fpe:
                            st.error(f"Could not reach pipeline server: {_fpe}")

    if generate:
        if not student_id.strip():
            msg = (
                "No student ID is linked to your account. Contact your teacher or administrator."
                if is_student else
                "Student ID is required."
            )
            st.markdown(
                f'<div class="auth-error">{icon("alert","#ff3d57",14)}&nbsp;{msg}</div>',
                unsafe_allow_html=True,
            )
            st.stop()

        # Top progress bar
        st.markdown('<div class="sg-topbar-progress"></div>', unsafe_allow_html=True)

        if IS_CLOUD:
            # ── Cloud: read directly from Google Sheets, ZERO HTTP calls ─
            # This branch MUST NOT reach any requests.get/post. If an error
            # escapes here it is a gspread/auth error, not a Render API 404.
            with st.spinner("Loading student data…"):
                try:
                    _sid_clean = student_id.strip()
                    _raw = get_student_report_direct(_sid_clean)

                    # Nothing in any sheet → pipeline has never run
                    if not _raw["consolidated"] and not _raw["analytics"] and not _raw["summaries"]:
                        st.markdown(
                            f'<div class="auth-error">{icon("alert","#ff3d57",14)}&nbsp;'
                            f'No pipeline data found in Google Sheets. '
                            f'Run the analytics pipeline from your Render dashboard first.</div>',
                            unsafe_allow_html=True,
                        )
                        st.stop()

                    # This student specifically has no processed data
                    if not _raw["consolidated"] or not _raw["analytics"] or not _raw["summaries"]:
                        st.markdown(
                            f'<div class="auth-error">{icon("alert","#ff3d57",14)}&nbsp;'
                            f'No report found for <strong>{_sid_clean}</strong>. '
                            f'Check the student ID or ask your admin to run the pipeline for this student.</div>',
                            unsafe_allow_html=True,
                        )
                        st.stop()

                    _cons = _raw["consolidated"][0]

                    # Build explainability map from subject_insights rows
                    _explain_map: dict = {}
                    for _ins in _raw["insights"]:
                        _explain_map[_ins.get("subject", "")] = {
                            "explanation_summary":    _normalize_val(_ins.get("explanation_summary")),
                            "key_evidence_points":    _normalize_val(_ins.get("key_evidence_points")) or [],
                            "confidence_in_insight":  _normalize_val(_ins.get("confidence_in_insight")),
                            "recommended_focus_area": _normalize_val(_ins.get("recommended_focus_area")),
                        }

                    _subj_summaries = [
                        {**{k: _normalize_val(v) for k, v in _s.items()},
                         "explainability": _explain_map.get(_s.get("subject", ""), {})}
                        for _s in _raw["summaries"]
                    ]

                    data = {
                        "student_id":             _sid_clean,
                        "student_name":           _normalize_val(_cons.get("student_name", _cons.get("Name", ""))),
                        "grade":                  _normalize_val(_cons.get("grade", "")),
                        "overall_summary":        _normalize_val(_cons.get("overall_summary", "")),
                        "recommended_next_steps": _normalize_val(_cons.get("recommended_next_steps", "")),
                        "numerical_performance": [
                            {
                                "subject":       _r.get("subject", ""),
                                "average_score": _r.get("average_score", 0),
                                "latest_score":  _r.get("latest_score", 0),
                                "trend":         _r.get("trend", ""),
                                "risk_flag":     _r.get("risk_flag", "—"),
                            }
                            for _r in _raw["analytics"]
                        ],
                        "subject_summaries":      _subj_summaries,
                        "mode":                   "cached",
                        "llm_provider_used":      _normalize_val(_cons.get("llm_provider", "ollama")),
                    }
                except Exception:
                    st.error(
                        "Unable to connect to the database. Please try again in a few seconds."
                    )
                    st.stop()

        elif fast_mode:
            # ── Local fast mode: direct Google Sheets via _load_cached_direct ─
            with st.spinner("Loading student data…"):
                try:
                    data = _load_cached_direct(student_id.strip())
                except LookupError as _le:
                    _sid_clean = student_id.strip()
                    _in_raw    = str(_le).endswith(":True")
                    if _in_raw:
                        st.markdown(f"""
                        <div style="background:rgba(255,171,64,.09);border:1px solid rgba(255,171,64,.28);
                                    border-radius:12px;padding:1.25rem 1.5rem;margin-bottom:1rem;">
                          <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.4rem;">
                            {icon("info","#ffab40",15,2)}
                            <span style="font-size:.85rem;font-weight:700;color:#ffab40;">Student Found in Raw Data</span>
                          </div>
                          <p style="font-size:.83rem;color:#aaa;margin:0 0 .9rem;line-height:1.6;">
                            <strong style="color:#e0e0e0">{_sid_clean}</strong> exists in the system
                            but hasn&rsquo;t been processed through the analytics pipeline yet.
                            Click below to run the pipeline for this student.
                          </p>
                        </div>
                        """, unsafe_allow_html=True)
                        if st.button(f"Process {_sid_clean} Now", key="process_now_btn"):
                            try:
                                _pr = requests.post(
                                    f"{API_BASE}/pipeline/run",
                                    json={"student_id": _sid_clean, "llm_provider": llm_provider},
                                    timeout=20,
                                )
                                if _pr.ok:
                                    st.session_state["_pipeline_job_id"] = _pr.json().get("job_id")
                                    st.session_state["_pipeline_target_sid"] = _sid_clean
                                    st.rerun()
                                else:
                                    st.error(f"Could not start pipeline (HTTP {_pr.status_code}).")
                            except Exception as _pe:
                                st.error(f"Could not reach pipeline server: {_pe}")
                    else:
                        st.markdown(
                            f'<div class="auth-error">{icon("alert","#ff3d57",14)}&nbsp;'
                            f'No report found for <strong>{_sid_clean}</strong>. '
                            f'Check the student ID or ask your admin to run the pipeline for this student.</div>',
                            unsafe_allow_html=True,
                        )
                    st.stop()
                except ValueError:
                    st.markdown(
                        f'<div class="auth-error">{icon("alert","#ff3d57",14)}&nbsp;'
                        f'No pipeline data found. Run the analytics pipeline first to generate reports.</div>',
                        unsafe_allow_html=True,
                    )
                    st.stop()
                except Exception as _e:
                    st.error(f"Could not load student data: {_e}")
                    st.stop()
        else:
            # ── Live mode via Render backend (local only, no fast_mode) ───
            payload = {"student_id": student_id.strip(), "llm_provider": llm_provider}
            with st.spinner("Generating live AI summary…"):
                try:
                    response = requests.post(LIVE_ENDPOINT, json=payload, timeout=180)
                except requests.exceptions.ConnectionError:
                    st.error("Cannot reach the backend. Is pipeline_server.py running?")
                    st.stop()

            if response.status_code == 404:
                _sid_clean = student_id.strip()
                _in_raw = False
                try:
                    _ex = requests.get(f"{API_BASE}/student/exists/{_sid_clean}", timeout=15)
                    if _ex.ok:
                        _in_raw = _ex.json().get("in_validated_results", False)
                except Exception:
                    pass
                if _in_raw:
                    st.markdown(f"""
                    <div style="background:rgba(255,171,64,.09);border:1px solid rgba(255,171,64,.28);
                                border-radius:12px;padding:1.25rem 1.5rem;margin-bottom:1rem;">
                      <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.4rem;">
                        {icon("info","#ffab40",15,2)}
                        <span style="font-size:.85rem;font-weight:700;color:#ffab40;">Student Found in Raw Data</span>
                      </div>
                      <p style="font-size:.83rem;color:#aaa;margin:0 0 .9rem;line-height:1.6;">
                        <strong style="color:#e0e0e0">{_sid_clean}</strong> exists in the system
                        but hasn&rsquo;t been processed through the analytics pipeline yet.
                        Click below to run the pipeline for this student.
                      </p>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button(f"Process {_sid_clean} Now", key="process_now_btn"):
                        try:
                            _pr = requests.post(
                                f"{API_BASE}/pipeline/run",
                                json={"student_id": _sid_clean, "llm_provider": llm_provider},
                                timeout=20,
                            )
                            if _pr.ok:
                                st.session_state["_pipeline_job_id"] = _pr.json().get("job_id")
                                st.session_state["_pipeline_target_sid"] = _sid_clean
                                st.rerun()
                            else:
                                st.error(f"Could not start pipeline (HTTP {_pr.status_code}). Check server logs.")
                        except Exception as _pe:
                            st.error(f"Could not reach pipeline server: {_pe}")
                else:
                    st.markdown(
                        f'<div class="auth-error">{icon("alert","#ff3d57",14)}&nbsp;'
                        f'No report found for <strong>{_sid_clean}</strong>. '
                        f'Check the student ID or ask your admin to run the pipeline for this student.</div>',
                        unsafe_allow_html=True,
                    )
                st.stop()
            if response.status_code != 200:
                st.error(f"Backend returned {response.status_code}. Check server logs.")
                st.stop()

            data = response.json()

        name          = data.get("student_name", "").upper() or student_id.upper()
        grade         = data.get("grade", "—")
        mode_label    = data.get("mode", "cached" if fast_mode else "live")
        provider_used = data.get("llm_provider_used", llm_provider)
        metrics       = data.get("numerical_performance", [])

        valid_scores = []
        for m in metrics:
            try: valid_scores.append(float(m.get("latest_score", 0)))
            except: pass
        overall_avg = round(sum(valid_scores) / len(valid_scores), 1) if valid_scores else 0
        avg_color   = score_color(overall_avg)

        risk_priority = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1, "—": 0}
        all_risks     = [m.get("risk_flag", "—") for m in metrics]
        overall_risk  = max(all_risks, key=lambda r: risk_priority.get(r, 0)) if all_risks else "—"
        risk_color    = "red" if overall_risk in ("High", "Critical") else "amber" if overall_risk == "Medium" else "green"

        t_list   = [trend_color(m.get("trend", "")) for m in metrics]
        t_counts = {"green": t_list.count("green"), "red": t_list.count("red"), "amber": t_list.count("amber")}
        dtc      = max(t_counts, key=t_counts.get) if t_list else "amber"
        ot_icon  = {"green": "↑", "amber": "→", "red": "↓"}.get(dtc, "→")
        ot_word  = {"green": "Improving", "amber": "Stable", "red": "Declining"}.get(dtc, "Stable")
        badge_cls = "green" if mode_label == "cached" else "amber"

        _kgrad = {
            "green": ("linear-gradient(135deg,#001a0e 0%,#002e18 100%)", "rgba(0,230,118,.18)",  "#00e676"),
            "amber": ("linear-gradient(135deg,#1a1000 0%,#2e1c00 100%)", "rgba(255,171,64,.18)", "#ffab40"),
            "red":   ("linear-gradient(135deg,#1a0005 0%,#2e000d 100%)", "rgba(255,61,87,.18)",  "#ff3d57"),
            "blue":  ("linear-gradient(135deg,#000d1a 0%,#001529 100%)", "rgba(41,121,255,.18)", "#2979ff"),
        }
        ag, ab, ac   = _kgrad[avg_color]
        rg, rb, rc   = _kgrad[risk_color]
        tg, tb, tc_k = _kgrad[dtc]
        bg, bb, bc   = _kgrad["blue"]

        subj_count = len(metrics)

        # KPI icons as inline SVG
        kpi_chart   = icon("bar-chart", ac,   28, 2.0)
        kpi_alert   = icon("alert",     rc,   26, 2.0)
        kpi_trend   = icon("trending",  tc_k, 26, 2.0)
        kpi_books   = icon("books",     bc,   26, 1.8)

        # ── 1. Student header ─────────────────────────────────────
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#050913 0%,#090f1d 60%,#050913 100%);
                    border:1px solid #131d33;border-radius:24px;padding:2rem 2.2rem 1.6rem;
                    margin-bottom:1.5rem;box-shadow:0 8px 40px rgba(0,0,0,.65);">
          <div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.4rem;flex-wrap:wrap;">
            <div style="font-size:2.3rem;font-weight:800;color:#f0f0f0;letter-spacing:-.03em;line-height:1;">{name}</div>
            <span style="display:inline-flex;align-items:center;background:rgba(41,121,255,.14);
                         border:1px solid rgba(41,121,255,.3);color:#2979ff;font-size:.76rem;
                         font-weight:700;letter-spacing:.07em;text-transform:uppercase;
                         padding:.28rem .8rem;border-radius:99px;">Grade {grade}</span>
            <span style="margin-left:auto;display:flex;gap:.5rem;align-items:center;flex-wrap:wrap;">
              <span class="sg-badge {badge_cls}">{mode_label.capitalize()} Mode</span>
              <span style="font-size:.73rem;color:#666;">Engine:&nbsp;<strong style="color:#2979ff">{provider_used}</strong></span>
            </span>
          </div>
          <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:.9rem;">
            <div style="background:{ag};border:1px solid {ab};border-radius:16px;padding:1.25rem 1rem;text-align:center;box-shadow:0 2px 12px rgba(0,0,0,.4);">
              <div style="margin-bottom:.35rem;">{kpi_chart}</div>
              <div style="font-size:2rem;font-weight:800;color:{ac};line-height:1;letter-spacing:-.02em;">{overall_avg}</div>
              <div style="font-size:.67rem;font-weight:700;color:#666;letter-spacing:.08em;text-transform:uppercase;margin-top:.4rem;">Overall Avg</div>
            </div>
            <div style="background:{rg};border:1px solid {rb};border-radius:16px;padding:1.25rem 1rem;text-align:center;box-shadow:0 2px 12px rgba(0,0,0,.4);">
              <div style="margin-bottom:.35rem;">{kpi_alert}</div>
              <div style="font-size:1.55rem;font-weight:800;color:{rc};line-height:1;letter-spacing:-.01em;">{overall_risk}</div>
              <div style="font-size:.67rem;font-weight:700;color:#666;letter-spacing:.08em;text-transform:uppercase;margin-top:.4rem;">Risk Level</div>
            </div>
            <div style="background:{tg};border:1px solid {tb};border-radius:16px;padding:1.25rem 1rem;text-align:center;box-shadow:0 2px 12px rgba(0,0,0,.4);">
              <div style="margin-bottom:.35rem;">{kpi_trend}</div>
              <div style="font-size:2rem;font-weight:800;color:{tc_k};line-height:1;">{ot_icon}</div>
              <div style="font-size:.67rem;font-weight:700;color:#666;letter-spacing:.08em;text-transform:uppercase;margin-top:.4rem;">Trend</div>
              <div style="font-size:.66rem;color:#555;margin-top:.15rem;">{ot_word}</div>
            </div>
            <div style="background:{bg};border:1px solid {bb};border-radius:16px;padding:1.25rem 1rem;text-align:center;box-shadow:0 2px 12px rgba(0,0,0,.4);">
              <div style="margin-bottom:.35rem;">{kpi_books}</div>
              <div style="font-size:2rem;font-weight:800;color:{bc};line-height:1;letter-spacing:-.02em;">{subj_count}</div>
              <div style="font-size:.67rem;font-weight:700;color:#666;letter-spacing:.08em;text-transform:uppercase;margin-top:.4rem;">Subjects</div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # ── 2. Academic overview ──────────────────────────────────
        overview = data.get("overall_summary", "")
        st.markdown(
            f'<div class="sg-card">'
            f'<div style="font-size:.67rem;font-weight:700;letter-spacing:.13em;text-transform:uppercase;'
            f'color:#2979ff;margin-bottom:.75rem;">Academic Overview</div>'
            + (
                f'<p style="font-size:.92rem;color:#c0c8d8;line-height:1.78;margin:0">{overview}</p>'
                if overview else
                f'<p style="font-size:.84rem;color:#555;margin:0;font-style:italic;">No data available.</p>'
            )
            + '</div>',
            unsafe_allow_html=True,
        )

        # ── 3. Radar chart ────────────────────────────────────────
        if metrics and len(metrics) >= 2:
            subj_r, scr_r, avg_r = [], [], []
            for m in metrics:
                subj_r.append(m.get("subject", ""))
                try: scr_r.append(float(m.get("latest_score", 0)))
                except: scr_r.append(0.0)
                try: avg_r.append(float(m.get("average_score", 0)))
                except: avg_r.append(0.0)

            fig_radar = go.Figure()
            fig_radar.add_trace(go.Scatterpolar(
                r=scr_r + [scr_r[0]], theta=subj_r + [subj_r[0]],
                fill='toself', fillcolor='rgba(41,121,255,0.14)',
                line=dict(color='#2979ff', width=2.5), name='Current Score',
                hovertemplate='%{theta}: <b>%{r:.0f}</b><extra></extra>',
            ))
            fig_radar.add_trace(go.Scatterpolar(
                r=avg_r + [avg_r[0]], theta=subj_r + [subj_r[0]],
                fill='toself', fillcolor='rgba(0,200,224,0.07)',
                line=dict(color='#00c8e0', width=1.5, dash='dot'), name='Average Score',
                hovertemplate='%{theta} avg: <b>%{r:.0f}</b><extra></extra>',
            ))
            fig_radar.update_layout(
                polar=dict(
                    bgcolor='#060606',
                    radialaxis=dict(
                        visible=True, range=[0, 100],
                        gridcolor='rgba(255,255,255,0.07)',
                        linecolor='rgba(255,255,255,0.05)',
                        tickfont=dict(size=10, color='#555', family='Inter'),
                        tickcolor='rgba(0,0,0,0)', dtick=25,
                    ),
                    angularaxis=dict(
                        gridcolor='rgba(255,255,255,0.07)',
                        linecolor='rgba(255,255,255,0.12)',
                        tickfont=dict(size=12, color='#9e9e9e', family='Inter'),
                    ),
                ),
                paper_bgcolor='#060606', plot_bgcolor='#060606',
                showlegend=True,
                legend=dict(font=dict(size=11, color='#9e9e9e', family='Inter'),
                            bgcolor='rgba(0,0,0,0)', orientation='h',
                            x=0.5, xanchor='center', y=-0.12),
                margin=dict(l=50, r=50, t=20, b=50), height=330,
            )
            st.markdown(
                f'{_section_label("Performance Radar")}',
                unsafe_allow_html=True,
            )
            st.plotly_chart(fig_radar, use_container_width=True, config={"displayModeBar": False})

        # ── 4. Subject performance cards ──────────────────────────
        if metrics:
            st.markdown(_section_label("Subject Performance"), unsafe_allow_html=True)
            cols = st.columns(len(metrics))
            for col, row in zip(cols, metrics):
                subj  = row.get("subject", "Subject")
                score = row.get("latest_score", 0)
                avg   = row.get("average_score", 0)
                risk  = row.get("risk_flag", "—")
                trend = row.get("trend", "")
                c     = score_color(score)
                tc    = trend_color(trend)
                tl    = trend_label(trend)
                subj_icon = SUBJ_ICONS.get(subj, _DEF_SUBJ_ICON)

                try: pct = min(float(score), 100)
                except: pct = 0.0

                pc  = {"green": "#00e676", "amber": "#ffab40", "red": "#ff3d57"}.get(c, "#ffab40")
                tch = {"green": "#00e676", "amber": "#ffab40", "red": "#ff3d57"}.get(tc, "#ffab40")
                gbg = {"green": "linear-gradient(160deg,#040f08 0%,#071308 100%)",
                       "amber": "linear-gradient(160deg,#0f0a04 0%,#130d04 100%)",
                       "red":   "linear-gradient(160deg,#0f0407 0%,#13040a 100%)"}.get(c, "#0d0d0d")
                bdr = {"green": "rgba(0,230,118,.2)", "amber": "rgba(255,171,64,.2)",
                       "red":   "rgba(255,61,87,.2)"}.get(c, "#1a1a1a")

                with col:
                    st.markdown(f"""
                    <div class="subj-card" style="background:{gbg};border:1px solid {bdr};
                                border-radius:18px;padding:1.5rem 1.3rem 1.2rem;
                                box-shadow:0 4px 20px rgba(0,0,0,.5);">
                      <div style="display:flex;align-items:center;gap:.55rem;margin-bottom:.9rem;">
                        {subj_icon}
                        <span style="font-size:.84rem;font-weight:700;color:#c8d0e0;">{subj}</span>
                      </div>
                      <div style="font-size:3rem;font-weight:800;color:{pc};line-height:1;letter-spacing:-.04em;margin-bottom:.1rem;">{score}</div>
                      <div style="font-size:.64rem;color:#555;letter-spacing:.07em;text-transform:uppercase;margin-bottom:.7rem;">out of 100</div>
                      <div style="background:rgba(255,255,255,.05);border-radius:99px;height:6px;overflow:hidden;margin-bottom:.85rem;">
                        <div style="height:6px;width:{pct}%;background:{pc};border-radius:99px;box-shadow:0 0 8px {pc}55;"></div>
                      </div>
                      <div style="display:flex;align-items:center;justify-content:space-between;gap:.3rem;flex-wrap:wrap;">
                        <span style="font-size:.73rem;color:#666;">Avg&nbsp;<strong style="color:#a0a8b0">{avg}</strong></span>
                        <span style="font-size:.73rem;font-weight:700;color:{tch};">{tl}</span>
                        <span class="sg-badge {c}" style="font-size:.61rem;">{risk}</span>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

        st.markdown("<div style='height:1.1rem'></div>", unsafe_allow_html=True)

        # ── 5. Subject insights + explainability ──────────────────
        subject_summaries = data.get("subject_summaries", [])
        if subject_summaries:
            st.markdown(_section_label("Subject Insights &amp; Evidence"), unsafe_allow_html=True)
            for subj in subject_summaries:
                subj_name = subj.get("subject", "Subject")
                subj_icon = SUBJ_ICONS.get(subj_name, _DEF_SUBJ_ICON)
                explain   = subj.get("explainability", {}) or {}

                evidence = explain.get("key_evidence_points", [])
                if isinstance(evidence, str):
                    evidence = [e.lstrip("- ").strip() for e in evidence.split("\n") if e.strip()]

                conf       = (explain.get("confidence_in_insight") or "unknown").capitalize()
                conf_color = {"High": "#00e676", "Medium": "#ffab40", "Low": "#ff3d57"}.get(conf, "#555")
                conf_pct   = {"High": 100, "Medium": 60, "Low": 30}.get(conf, 10)

                focus_raw   = explain.get("recommended_focus_area") or ""
                focus_areas = [f.strip() for f in focus_raw.split(",") if f.strip()] if focus_raw else []

                with st.expander(subj_name, expanded=False):

                    st.markdown(f"""
<div style="background:#06101a;border:1px solid #1a2540;border-left:3px solid #2979ff;
            border-radius:12px;padding:1.1rem 1.3rem;margin-bottom:1rem;">
  <div style="font-size:.62rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
              color:#2979ff;margin-bottom:.55rem;display:flex;align-items:center;gap:.4rem;">
    {icon("bar-chart","#2979ff",12,2)}&nbsp;Performance Summary
  </div>
  <p style="font-size:.89rem;color:#CBD5E1;line-height:1.74;margin:0">
    {subj.get("performance_summary", "—")}</p>
</div>""", unsafe_allow_html=True)

                    # Plotly bar chart — subject comparison
                    if metrics:
                        chart_subjs, chart_scores, chart_avgs = [], [], []
                        for m in metrics:
                            chart_subjs.append(m.get("subject", ""))
                            try:    chart_scores.append(float(m.get("latest_score", 0)))
                            except: chart_scores.append(0.0)
                            try:    chart_avgs.append(float(m.get("average_score", 0)))
                            except: chart_avgs.append(0.0)

                        _rgb = {
                            "#00e676": (0, 230, 118),
                            "#ffab40": (255, 171, 64),
                            "#ff3d57": (255, 61, 87),
                            "#2979ff": (41, 121, 255),
                        }
                        score_clrs, avg_clrs = [], []
                        for s_name in chart_subjs:
                            sm   = next((m for m in metrics if m.get("subject") == s_name), {})
                            c_s  = score_color(sm.get("latest_score", 0))
                            base = {"green": "#00e676", "amber": "#ffab40", "red": "#ff3d57"}.get(c_s, "#2979ff")
                            is_cur = s_name == subj_name
                            r, g, b = _rgb.get(base, (41, 121, 255))
                            score_clrs.append(f"rgba({r},{g},{b},{'0.8' if is_cur else '0.2'})")
                            avg_clrs.append("rgba(0,200,224,0.7)" if is_cur else "rgba(0,200,224,0.2)")

                        fig_bar = go.Figure()
                        fig_bar.add_trace(go.Bar(
                            x=chart_subjs, y=chart_scores, name="Latest Score",
                            marker=dict(color=score_clrs),
                            hovertemplate="%{x}: <b>%{y:.0f}</b><extra></extra>",
                        ))
                        fig_bar.add_trace(go.Bar(
                            x=chart_subjs, y=chart_avgs, name="Avg Score",
                            marker=dict(color=avg_clrs, line=dict(color="rgba(0,200,224,0.45)", width=1)),
                            hovertemplate="%{x} avg: <b>%{y:.0f}</b><extra></extra>",
                        ))
                        fig_bar.update_layout(
                            barmode="group",
                            paper_bgcolor="#060606", plot_bgcolor="#060606",
                            height=190, margin=dict(l=0, r=0, t=8, b=30),
                            showlegend=True,
                            legend=dict(
                                font=dict(size=10, color="#9e9e9e", family="Inter"),
                                bgcolor="rgba(0,0,0,0)", orientation="h",
                                x=0.5, xanchor="center", y=-0.45,
                            ),
                            xaxis=dict(
                                showgrid=False, zeroline=False,
                                tickfont=dict(size=11, color="#9e9e9e", family="Inter"),
                                linecolor="rgba(255,255,255,0.05)",
                            ),
                            yaxis=dict(
                                range=[0, 110], dtick=25,
                                gridcolor="rgba(255,255,255,0.04)",
                                linecolor="rgba(255,255,255,0.04)",
                                tickfont=dict(size=9, color="#555", family="Inter"),
                            ),
                        )
                        st.markdown(
                            f'<div style="font-size:.62rem;font-weight:700;letter-spacing:.12em;'
                            f'text-transform:uppercase;color:#00c8e0;margin-bottom:.25rem;'
                            f'display:flex;align-items:center;gap:.4rem;">'
                            f'{icon("bar-chart","#00c8e0",12,2)}&nbsp;Score Comparison</div>',
                            unsafe_allow_html=True,
                        )
                        st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})

                    st.markdown(f"""
<div style="background:#041414;border:1px solid #0d2a2a;border-left:3px solid #00c8e0;
            border-radius:12px;padding:1.1rem 1.3rem;margin-bottom:1rem;">
  <div style="font-size:.62rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
              color:#00c8e0;margin-bottom:.55rem;display:flex;align-items:center;gap:.4rem;">
    {icon("target","#00c8e0",12,2)}&nbsp;Improvement Plan
  </div>
  <p style="font-size:.89rem;color:#CBD5E1;line-height:1.74;margin:0">
    {subj.get("improvement_plan", "—")}</p>
</div>""", unsafe_allow_html=True)

                    st.markdown(f"""
<div style="background:#0d0900;border:1px solid rgba(255,171,64,.18);border-left:3px solid #ffab40;
            border-radius:12px;padding:1.1rem 1.3rem;margin-bottom:1rem;">
  <div style="font-size:.62rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
              color:#ffab40;margin-bottom:.55rem;display:flex;align-items:center;gap:.4rem;">
    {icon("sparkles","#ffab40",12,2)}&nbsp;Motivation Note
  </div>
  <p style="font-size:.89rem;color:#CBD5E1;line-height:1.74;margin:0;font-style:italic;">
    {subj.get("motivation_note", "—")}</p>
</div>""", unsafe_allow_html=True)

                    ev_bullets = "".join(f"""
<div style="display:flex;gap:.65rem;align-items:flex-start;margin-bottom:.52rem;">
  <span style="margin-top:.22rem;flex-shrink:0;">{icon("dot","#2979ff",10)}</span>
  <span style="font-size:.85rem;color:#CBD5E1;line-height:1.62;">{e}</span>
</div>""" for e in evidence)

                    if focus_areas:
                        pills = "".join(
                            f'<span style="display:inline-block;background:rgba(41,121,255,.1);'
                            f'border:1px solid rgba(41,121,255,.28);color:#2979ff;font-size:.72rem;'
                            f'font-weight:600;border-radius:99px;padding:.24rem .75rem;'
                            f'margin:.2rem .25rem .2rem 0;">{fa}</span>'
                            for fa in focus_areas
                        )
                        pills_html = (
                            '<div style="margin-top:.9rem;">'
                            '<div style="font-size:.6rem;font-weight:700;letter-spacing:.1em;'
                            'text-transform:uppercase;color:#555;margin-bottom:.45rem;">Focus Areas</div>'
                            f'{pills}</div>'
                        )
                    else:
                        pills_html = ""

                    st.markdown(f"""
<div style="background:#04080f;border:1px solid #192035;border-left:3px solid #2979ff;
            border-radius:12px;padding:1.15rem 1.3rem;margin-bottom:.3rem;">
  <div style="font-size:.62rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
              color:#2979ff;margin-bottom:.75rem;display:flex;align-items:center;gap:.4rem;">
    {icon("search","#2979ff",12,2)}&nbsp;Why This Conclusion Was Reached
  </div>
  <p style="font-size:.87rem;color:#CBD5E1;line-height:1.7;margin:0 0 .9rem;">
    {explain.get("explanation_summary", "—")}</p>
  {ev_bullets}
  <div style="margin-top:.85rem;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.4rem;">
      <span style="font-size:.65rem;font-weight:600;color:#555;letter-spacing:.07em;text-transform:uppercase;">Confidence Level</span>
      <span style="font-size:.78rem;font-weight:700;color:{conf_color};">{conf}</span>
    </div>
    <div style="background:rgba(255,255,255,.06);border-radius:99px;height:5px;overflow:hidden;">
      <div style="height:5px;width:{conf_pct}%;background:{conf_color};border-radius:99px;
                  box-shadow:0 0 8px {conf_color}66;"></div>
    </div>
  </div>
  {pills_html}
</div>""", unsafe_allow_html=True)

        # ── 6. Recommended next steps ─────────────────────────────
        steps = normalize_next_steps(data.get("recommended_next_steps"))
        if steps:
            steps_html = "".join(
                f'<div style="display:flex;gap:.7rem;align-items:flex-start;margin-bottom:.52rem;">'
                f'<span style="margin-top:2px;flex-shrink:0;">{icon("arrow-r","#2979ff",13,2.2)}</span>'
                f'<span style="color:#c0c8d8;font-size:.87rem;line-height:1.62">{s}</span>'
                f'</div>'
                for s in steps
            )
            st.markdown(
                f'<div class="sg-card">'
                f'<div style="font-size:.67rem;font-weight:700;letter-spacing:.13em;text-transform:uppercase;'
                f'color:#2979ff;margin-bottom:.75rem;">Recommended Next Steps</div>{steps_html}</div>',
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
        st.caption(
            f"Mode: **{mode_label}**  |  Engine: **{provider_used}** "
            f" |  STEM Globe Intelligence Platform"
        )

# ============================================================
# STUDENTS PAGE
# ============================================================

def show_students():
    st.markdown("""
    <div style="margin-bottom:1.6rem;padding-top:.3rem;">
        <div style="font-size:.63rem;font-weight:700;color:#666;letter-spacing:.14em;text-transform:uppercase;margin-bottom:.35rem;">
            Students
        </div>
        <div style="font-size:1.75rem;font-weight:800;color:#f0f0f0;letter-spacing:-.02em;line-height:1.15;">
            Student Directory
        </div>
        <div style="font-size:.84rem;color:#777;margin-top:.25rem;">
            Class roster with live analytics &mdash; click View to open any student&rsquo;s full report
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Data loading ──────────────────────────────────────────
    try:
        with st.spinner("Loading student roster…"):
            analytics_df    = pd.DataFrame(_cached_sheet("subject_analytics"))
            validated_df    = pd.DataFrame(_cached_sheet("validated_results"))
            consolidated_df = pd.DataFrame(_cached_sheet("student_consolidated_latest"))
    except Exception:
        _show_empty_state(
            icon("zap", "#2a2a2a", 48, 1.2),
            "Connection Unavailable",
            "Unable to connect to the database. Please try again in a few seconds.",
        )
        return

    if analytics_df.empty:
        _show_empty_state(
            icon("users", "#2a2a2a", 48, 1.2),
            "No Student Data Found",
            "Run the pipeline to process student records, then return here to view the roster.",
        )
        return

    # ── Build per-student roster ──────────────────────────────
    analytics_df["student_id"] = analytics_df["student_id"].astype(str).str.strip()

    name_map: dict = {}
    if not validated_df.empty and "student_id" in validated_df.columns:
        validated_df["student_id"] = validated_df["student_id"].astype(str).str.strip()
        if "Name" in validated_df.columns:
            name_map = (
                validated_df.dropna(subset=["Name"])
                .groupby("student_id")["Name"]
                .first()
                .to_dict()
            )

    consolidated_ids: set = set()
    if not consolidated_df.empty and "student_id" in consolidated_df.columns:
        consolidated_ids = set(consolidated_df["student_id"].astype(str).str.strip().unique())

    _RISK_PRI = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}

    roster = []
    for sid, grp in analytics_df.groupby("student_id"):
        grade_val = "—"
        if "grade" in grp.columns:
            g = grp["grade"].dropna()
            if not g.empty:
                try:
                    grade_val = str(int(float(g.iloc[0])))
                except Exception:
                    grade_val = str(g.iloc[0])

        avg_scores = pd.to_numeric(
            grp["average_score"] if "average_score" in grp.columns else pd.Series(),
            errors="coerce",
        ).dropna()
        overall_avg = round(float(avg_scores.mean()), 1) if not avg_scores.empty else 0.0

        risks = [str(r).strip() for r in grp.get("risk_flag", pd.Series()).values if str(r).strip()]
        overall_risk = max(risks, key=lambda r: _RISK_PRI.get(r, 0)) if risks else "—"

        raw_trends = [str(t).strip() for t in grp.get("trend", pd.Series()).values if str(t).strip()]
        if any("down" in t.lower() or "declin" in t.lower() for t in raw_trends):
            dominant_trend = "Declining"
        elif any("up" in t.lower() or "improv" in t.lower() for t in raw_trends):
            dominant_trend = "Improving"
        elif raw_trends:
            dominant_trend = raw_trends[0]
        else:
            dominant_trend = "Stable"

        subjects = sorted(grp["subject"].astype(str).str.strip().unique().tolist())

        roster.append({
            "student_id": str(sid),
            "name":        str(name_map.get(sid, "—")),
            "grade":       grade_val,
            "overall_avg": overall_avg,
            "risk_level":  overall_risk,
            "trend":       dominant_trend,
            "subjects":    subjects,
            "processed":   str(sid) in consolidated_ids,
        })

    roster.sort(key=lambda x: x["student_id"])

    # ── KPI cards ─────────────────────────────────────────────
    total           = len(roster)
    all_avgs        = [s["overall_avg"] for s in roster if s["overall_avg"] > 0]
    class_avg       = round(sum(all_avgs) / len(all_avgs), 1) if all_avgs else 0.0
    at_risk_n       = sum(1 for s in roster if s["risk_level"] in ("High", "Critical"))
    processed_n     = sum(1 for s in roster if s["processed"])
    all_subjects    = sorted({sub for s in roster for sub in s["subjects"]})
    avg_hex   = "#00e676" if class_avg >= 70 else "#ffab40" if class_avg >= 50 else "#ff3d57"
    avg_bg    = ("linear-gradient(160deg,#001a0e,#002e18)" if class_avg >= 70
                 else "linear-gradient(160deg,#1a1000,#2e1c00)" if class_avg >= 50
                 else "linear-gradient(160deg,#1a0005,#2e000d)")
    risk_hex  = "#ff3d57" if at_risk_n > 0 else "#00e676"
    risk_bg   = ("linear-gradient(160deg,#1a0005,#2e000d)" if at_risk_n > 0
                 else "linear-gradient(160deg,#001a0e,#002e18)")

    kc1, kc2, kc3, kc4 = st.columns(4)
    with kc1:
        st.markdown(f"""
        <div style="background:linear-gradient(160deg,#000d1a,#001529);
             border:1px solid rgba(41,121,255,.22);border-radius:14px;
             padding:1.2rem 1rem;text-align:center;position:relative;overflow:hidden;">
          <div style="position:absolute;top:0;left:0;right:0;height:3px;background:#2979ff;"></div>
          <div style="font-size:.67rem;font-weight:700;color:#555;letter-spacing:.09em;
               text-transform:uppercase;margin-bottom:.4rem;">Total Students</div>
          <div style="font-size:2.4rem;font-weight:800;color:#2979ff;line-height:1;">{total}</div>
          <div style="font-size:.74rem;color:#555;margin-top:.35rem;">{processed_n} fully processed</div>
        </div>""", unsafe_allow_html=True)
    with kc2:
        st.markdown(f"""
        <div style="background:{avg_bg};border:1px solid rgba(255,255,255,.07);
             border-radius:14px;padding:1.2rem 1rem;text-align:center;
             position:relative;overflow:hidden;">
          <div style="position:absolute;top:0;left:0;right:0;height:3px;background:{avg_hex};"></div>
          <div style="font-size:.67rem;font-weight:700;color:#555;letter-spacing:.09em;
               text-transform:uppercase;margin-bottom:.4rem;">Class Average</div>
          <div style="font-size:2.4rem;font-weight:800;color:{avg_hex};line-height:1;">{class_avg}</div>
          <div style="font-size:.74rem;color:#555;margin-top:.35rem;">out of 100</div>
        </div>""", unsafe_allow_html=True)
    with kc3:
        st.markdown(f"""
        <div style="background:{risk_bg};border:1px solid rgba(255,255,255,.07);
             border-radius:14px;padding:1.2rem 1rem;text-align:center;
             position:relative;overflow:hidden;">
          <div style="position:absolute;top:0;left:0;right:0;height:3px;background:{risk_hex};"></div>
          <div style="font-size:.67rem;font-weight:700;color:#555;letter-spacing:.09em;
               text-transform:uppercase;margin-bottom:.4rem;">At-Risk Students</div>
          <div style="font-size:2.4rem;font-weight:800;color:{risk_hex};line-height:1;">{at_risk_n}</div>
          <div style="font-size:.74rem;color:#555;margin-top:.35rem;">High or Critical risk</div>
        </div>""", unsafe_allow_html=True)
    with kc4:
        st.markdown(f"""
        <div style="background:linear-gradient(160deg,#04080f,#080f1e);
             border:1px solid #192035;border-radius:14px;padding:1.2rem 1rem;
             text-align:center;position:relative;overflow:hidden;">
          <div style="position:absolute;top:0;left:0;right:0;height:3px;background:#00c8e0;"></div>
          <div style="font-size:.67rem;font-weight:700;color:#555;letter-spacing:.09em;
               text-transform:uppercase;margin-bottom:.4rem;">Subjects Tracked</div>
          <div style="font-size:2.4rem;font-weight:800;color:#00c8e0;line-height:1;">{len(all_subjects)}</div>
          <div style="font-size:.74rem;color:#555;margin-top:.35rem;">{", ".join(all_subjects) or "—"}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:.85rem'></div>", unsafe_allow_html=True)

    # ── Roster table ──────────────────────────────────────────
    with st.container(border=True):
        st.markdown('<div class="sg-title">Student Roster</div>', unsafe_allow_html=True)

        search_q = st.text_input(
            "Search",
            placeholder="Filter by name or student ID…",
            key="students_search",
            label_visibility="collapsed",
        )

        q = search_q.strip().lower()
        visible = [
            s for s in roster
            if not q
            or q in s["student_id"].lower()
            or q in s["name"].lower()
        ]

        st.markdown(
            f'<div style="font-size:.72rem;color:#555;margin:.2rem 0 .85rem;">'
            f'Showing <strong style="color:#888">{len(visible)}</strong> of '
            f'<strong style="color:#888">{total}</strong> students</div>',
            unsafe_allow_html=True,
        )

        if not visible:
            _show_empty_state(
                icon("search", "#2a2a2a", 38, 1.2),
                "No matches",
                f'No students match "{search_q}".',
            )
        else:
            # Column proportions — shared between header and data rows
            _CR   = [0.75, 1.55, 0.44, 0.76, 1.0, 0.95, 2.1, 0.7]
            _HDRS = ["Student ID", "Name", "Grade", "Avg", "Risk Level", "Trend", "Subjects", ""]

            # Header
            h_cols = st.columns(_CR)
            for hc, ht in zip(h_cols, _HDRS):
                with hc:
                    st.markdown(
                        f'<div style="font-size:.6rem;font-weight:700;color:#444;'
                        f'letter-spacing:.11em;text-transform:uppercase;padding:.15rem 0 .5rem;">'
                        f'{ht}</div>',
                        unsafe_allow_html=True,
                    )
            st.markdown(
                '<div style="border-top:1px solid #1a1a1a;margin-bottom:.05rem;"></div>',
                unsafe_allow_html=True,
            )

            # Risk pill colours
            _RPILL = {
                "Critical": ("rgba(255,61,87,.13)", "#ff3d57",  "rgba(255,61,87,.3)"),
                "High":     ("rgba(255,61,87,.08)", "#ff3d57",  "rgba(255,61,87,.2)"),
                "Medium":   ("rgba(255,171,64,.10)", "#ffab40", "rgba(255,171,64,.28)"),
                "Low":      ("rgba(0,230,118,.08)", "#00e676",  "rgba(0,230,118,.22)"),
            }

            def _pill(risk: str) -> str:
                bg, fg, br = _RPILL.get(risk, ("rgba(255,255,255,.04)", "#444", "#1a1a1a"))
                return (
                    f'<span style="display:inline-block;font-size:.61rem;font-weight:700;'
                    f'letter-spacing:.09em;text-transform:uppercase;padding:2px 9px;'
                    f'border-radius:99px;background:{bg};color:{fg};border:1px solid {br};">'
                    f'{risk}</span>'
                )

            # Data rows
            for i, s in enumerate(visible[:100]):
                risk    = s["risk_level"]
                avg     = s["overall_avg"]
                avg_hex = "#00e676" if avg >= 70 else "#ffab40" if avg >= 50 else "#ff3d57"
                t       = s["trend"].lower()
                if "improv" in t or t == "improving":
                    t_label, t_hex = "↑ Improving", "#00e676"
                elif "declin" in t or t == "declining":
                    t_label, t_hex = "↓ Declining", "#ff3d57"
                else:
                    t_label, t_hex = "→ Stable", "#ffab40"

                status_badge = (
                    '<span style="font-size:.59rem;font-weight:700;background:rgba(0,230,118,.08);'
                    'color:#00e676;border:1px solid rgba(0,230,118,.2);border-radius:99px;'
                    'padding:1px 7px;letter-spacing:.06em;text-transform:uppercase;">Ready</span>'
                    if s["processed"] else
                    '<span style="font-size:.59rem;font-weight:700;background:rgba(255,171,64,.07);'
                    'color:#ffab40;border:1px solid rgba(255,171,64,.18);border-radius:99px;'
                    'padding:1px 7px;letter-spacing:.06em;text-transform:uppercase;">Pending</span>'
                )

                _cell = "padding:.52rem 0;line-height:1.3;"

                r_cols = st.columns(_CR)
                with r_cols[0]:
                    st.markdown(
                        f'<div style="{_cell}font-size:.82rem;font-family:monospace;color:#7ab4ff;">'
                        f'{s["student_id"]}</div>',
                        unsafe_allow_html=True,
                    )
                with r_cols[1]:
                    st.markdown(
                        f'<div style="{_cell}font-size:.84rem;color:#e0e0e0;font-weight:500;">'
                        f'{s["name"]}</div>',
                        unsafe_allow_html=True,
                    )
                with r_cols[2]:
                    st.markdown(
                        f'<div style="{_cell}font-size:.82rem;color:#666;text-align:center;">'
                        f'{s["grade"]}</div>',
                        unsafe_allow_html=True,
                    )
                with r_cols[3]:
                    st.markdown(
                        f'<div style="{_cell}font-size:.9rem;font-weight:700;color:{avg_hex};">'
                        f'{avg:.1f}</div>',
                        unsafe_allow_html=True,
                    )
                with r_cols[4]:
                    st.markdown(
                        f'<div style="padding:.42rem 0;">{_pill(risk)}</div>',
                        unsafe_allow_html=True,
                    )
                with r_cols[5]:
                    st.markdown(
                        f'<div style="{_cell}font-size:.8rem;font-weight:600;color:{t_hex};">'
                        f'{t_label}</div>',
                        unsafe_allow_html=True,
                    )
                with r_cols[6]:
                    st.markdown(
                        f'<div style="{_cell}font-size:.78rem;color:#666;">'
                        f'{", ".join(s["subjects"])}&nbsp;{status_badge}</div>',
                        unsafe_allow_html=True,
                    )
                with r_cols[7]:
                    st.markdown('<div class="ghost-btn-wrap">', unsafe_allow_html=True)
                    if st.button("View →", key=f"stu_view_{s['student_id']}", use_container_width=True):
                        st.session_state["_preload_sid"] = s["student_id"]
                        st.session_state.nav_page = "Dashboard"
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

                st.markdown(
                    '<div style="border-top:1px solid #0f0f0f;"></div>',
                    unsafe_allow_html=True,
                )

            if len(visible) > 100:
                st.markdown(
                    f'<div style="font-size:.75rem;color:#444;text-align:center;padding:.85rem 0;">'
                    f'Showing first 100 of {len(visible)} students — narrow your search to see more.</div>',
                    unsafe_allow_html=True,
                )

# ============================================================
# REPORTS PAGE
# ============================================================

def show_reports():
    st.markdown(f"""
    <div style="margin-bottom:1.6rem;padding-top:.3rem;">
        <div style="font-size:.63rem;font-weight:700;color:#666;letter-spacing:.14em;text-transform:uppercase;margin-bottom:.35rem;">
            Reports
        </div>
        <div style="font-size:1.75rem;font-weight:800;color:#f0f0f0;letter-spacing:-.02em;line-height:1.15;">
            Academic Reports
        </div>
        <div style="font-size:.84rem;color:#777;margin-top:.25rem;">
            View and export student performance reports
        </div>
    </div>
    """, unsafe_allow_html=True)

    try:
        reports_df = pd.DataFrame(_cached_sheet("student_consolidated_latest"))
    except Exception:
        _show_empty_state(
            icon("zap", "#2a2a2a", 48, 1.2),
            "Connection Unavailable",
            "Unable to connect to the database. Please try again in a few seconds.",
        )
        return

    if not reports_df.empty:
        st.markdown(_section_label("Recent Reports"), unsafe_allow_html=True)

        total = len(reports_df)
        _rc1, _rc2, _rc3 = st.columns(3)
        with _rc1:
            st.markdown(f"""
            <div class="sg-metric green">
                <div class="sg-metric-label">Total Reports</div>
                <div class="sg-metric-value green">{total}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

        # Show focused, human-readable columns only
        _col_map = {
            "student_id":    "Student ID",
            "student_name":  "Name",
            "grade":         "Grade",
            "overall_summary": "AI Summary (preview)",
            "llm_provider":  "Provider",
        }
        _show_cols = [c for c in _col_map if c in reports_df.columns]
        _disp_df = reports_df[_show_cols].head(50).rename(columns=_col_map).copy()
        if "AI Summary (preview)" in _disp_df.columns:
            _disp_df["AI Summary (preview)"] = (
                _disp_df["AI Summary (preview)"].astype(str).str[:120] + "…"
            )
        st.dataframe(_disp_df, use_container_width=True, hide_index=True)
    else:
        _show_empty_state(
            icon("file", "#2a2a2a", 48, 1.2),
            "No Reports Yet",
            "Generate a report from the Dashboard to see it here.",
        )

# ============================================================
# SETTINGS PAGE
# ============================================================

def show_settings():
    st.markdown(f"""
    <div style="margin-bottom:1.6rem;padding-top:.3rem;">
        <div style="font-size:.63rem;font-weight:700;color:#666;letter-spacing:.14em;text-transform:uppercase;margin-bottom:.35rem;">
            Settings
        </div>
        <div style="font-size:1.75rem;font-weight:800;color:#f0f0f0;letter-spacing:-.02em;line-height:1.15;">
            Account Settings
        </div>
        <div style="font-size:.84rem;color:#777;margin-top:.25rem;">
            Manage your profile and preferences
        </div>
    </div>
    """, unsafe_allow_html=True)

    u_name  = st.session_state.user_name  or "User"
    u_email = st.session_state.user_email or ""
    u_role  = st.session_state.user_role  or ""
    r_color = ROLE_COLORS.get(u_role, "#444")
    initials = _get_initials(u_name)

    with st.container(border=True):
        st.markdown('<div class="sg-title">Profile</div>', unsafe_allow_html=True)
        c1, c2 = st.columns([0.15, 0.85])
        with c1:
            st.markdown(f"""
            <div style="width:56px;height:56px;border-radius:50%;
                background:rgba(41,121,255,.16);border:2px solid rgba(41,121,255,.35);
                display:flex;align-items:center;justify-content:center;
                font-size:1.2rem;font-weight:800;color:#2979ff;">{initials}</div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div style="padding-top:.2rem;">
                <div style="font-size:1.1rem;font-weight:700;color:#f0f0f0;">{u_name}</div>
                <div style="font-size:.82rem;color:#777;margin-top:.15rem;">{u_email}</div>
                <span style="display:inline-block;margin-top:.45rem;font-size:.65rem;font-weight:700;
                    color:{r_color};background:rgba(255,255,255,.05);border:1px solid {r_color}33;
                    border-radius:99px;padding:.18rem .65rem;letter-spacing:.07em;text-transform:uppercase;">
                    {u_role}
                </span>
            </div>
            """, unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="sg-title">Platform Info</div>', unsafe_allow_html=True)
        rows = [
            ("Platform",  "STEM Globe Intelligence"),
            ("Version",   "2.5.1"),
            ("API",       API_BASE),
            ("Theme",     "OLED Dark"),
        ]
        for label, val in rows:
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;padding:.5rem 0;'
                f'border-bottom:1px solid #141414;">'
                f'<span style="font-size:.83rem;color:#666;">{label}</span>'
                f'<span style="font-size:.83rem;color:#c0c8d8;font-weight:500;">{val}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    if u_role == "Admin":
        with st.container(border=True):
            st.markdown('<div class="sg-title">Admin Controls</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="auth-success" style="justify-content:flex-start;">'
                f'{icon("check","#00e676",14)}&nbsp;'
                f'Full system access granted. Manage users and settings via Google Sheets.</div>',
                unsafe_allow_html=True,
            )

        with st.container(border=True):
            st.markdown('<div class="sg-title">Student ID Management</div>', unsafe_allow_html=True)
            st.markdown(
                '<p style="font-size:.84rem;color:#777;margin-bottom:1rem;">'
                'Assign or update Student IDs for registered student accounts. '
                'Edit the <strong style="color:#c0c8d8">Student ID</strong> column, then click Save.</p>',
                unsafe_allow_html=True,
            )
            try:
                _ac = get_gs_client()
                _as = get_spreadsheet(_ac)
                _udf = read_table(_as, "users")

                if not _udf.empty and "role" in _udf.columns:
                    _studs = _udf[_udf["role"].str.strip() == "Student"].copy()

                    if not _studs.empty:
                        if "student_id" not in _studs.columns:
                            _studs["student_id"] = ""
                        _disp = _studs[["full_name", "email", "student_id"]].reset_index(drop=True)
                        _disp.columns = ["Name", "Email", "Student ID"]

                        _edited = st.data_editor(
                            _disp,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "Name":       st.column_config.TextColumn("Name",       disabled=True),
                                "Email":      st.column_config.TextColumn("Email",      disabled=True),
                                "Student ID": st.column_config.TextColumn("Student ID",
                                              help="e.g. S001 — leave blank to unlink"),
                            },
                            key="admin_sid_editor",
                        )

                        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
                        if st.button("Save Student IDs", key="admin_save_sids"):
                            try:
                                _full = read_table(_as, "users")
                                if "student_id" not in _full.columns:
                                    _full["student_id"] = ""
                                for _, _er in _edited.iterrows():
                                    _em  = _er["Email"]
                                    _sid = str(_er.get("Student ID", "") or "").strip()
                                    _m   = _full["email"].str.lower().str.strip() == _em.strip().lower()
                                    _full.loc[_m, "student_id"] = _sid
                                write_table(_as, "users", _full)
                                st.markdown(
                                    f'<div class="auth-success">{icon("check","#00e676",14)}'
                                    '&nbsp;Student IDs saved successfully.</div>',
                                    unsafe_allow_html=True,
                                )
                            except Exception as _se:
                                st.markdown(
                                    f'<div class="auth-error">{icon("alert","#ff3d57",14)}'
                                    f'&nbsp;Save failed: {_se}</div>',
                                    unsafe_allow_html=True,
                                )
                    else:
                        st.markdown(
                            '<p style="font-size:.84rem;color:#555;">No registered student accounts found.</p>',
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown(
                        '<p style="font-size:.84rem;color:#555;">No user data available.</p>',
                        unsafe_allow_html=True,
                    )
            except Exception as _ae:
                st.markdown(
                    f'<div class="auth-error">{icon("alert","#ff3d57",14)}'
                    f'&nbsp;Could not load users: {_ae}</div>',
                    unsafe_allow_html=True,
                )

        # ── Add New Student ─────────────────────────────────────────────────
        with st.container(border=True):
            st.markdown('<div class="sg-title">Add New Student</div>', unsafe_allow_html=True)
            st.markdown(
                '<p style="font-size:.84rem;color:#777;margin-bottom:1rem;">'
                'Enter the student\'s details and exam scores. '
                '<strong style="color:#c0c8d8">Save Student</strong> writes the record '
                'to Google Sheets and triggers the AI pipeline for that student only.</p>',
                unsafe_allow_html=True,
            )

            # Basic info
            _ns_c1, _ns_c2, _ns_c3 = st.columns([1, 1.5, 1])
            with _ns_c1:
                _ns_sid = st.text_input(
                    "Student ID", placeholder="e.g. S051", key="ns_student_id"
                )
            with _ns_c2:
                _ns_name = st.text_input(
                    "Student Name", placeholder="e.g. Jane Smith", key="ns_student_name"
                )
            with _ns_c3:
                _ns_grade = st.text_input(
                    "Grade", placeholder="e.g. 11", key="ns_grade"
                )

            # Dynamic subject rows
            if "ns_subject_count" not in st.session_state:
                st.session_state.ns_subject_count = 1

            st.markdown(
                '<div style="font-size:.79rem;font-weight:600;color:#888;'
                'margin:.9rem 0 .4rem;text-transform:uppercase;letter-spacing:.06em;">'
                'Subjects &amp; Scores</div>',
                unsafe_allow_html=True,
            )

            _ns_subjects = []
            for _i in range(st.session_state.ns_subject_count):
                _sc1, _sc2, _sc3 = st.columns([1.5, 2.5, 0.8])
                with _sc1:
                    _sn = st.text_input(
                        f"Subject {_i + 1}",
                        placeholder="e.g. Math",
                        key=f"ns_subj_name_{_i}",
                    )
                with _sc2:
                    _ss = st.text_input(
                        "Scores (comma-separated)" if _i == 0 else " ",
                        placeholder="e.g. 85, 90, 78",
                        key=f"ns_subj_scores_{_i}",
                        label_visibility="visible" if _i == 0 else "hidden",
                    )
                with _sc3:
                    _sm = st.number_input(
                        "Max score" if _i == 0 else " ",
                        value=100,
                        min_value=1,
                        key=f"ns_subj_max_{_i}",
                        label_visibility="visible" if _i == 0 else "hidden",
                    )
                _ns_subjects.append({"name": _sn, "scores_str": _ss, "max_score": _sm})

            if st.button("+ Add Subject", key="ns_add_subject"):
                st.session_state.ns_subject_count += 1
                st.rerun()

            st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

            _ns_save = st.button(
                "Save Student", key="ns_save_student", use_container_width=True
            )

            if _ns_save:
                # ── Validation ──────────────────────────────────────────────
                _ns_errors = []
                _ns_sid_clean = _ns_sid.strip()
                _ns_name_clean = _ns_name.strip()
                _ns_grade_clean = _ns_grade.strip()

                if not _ns_sid_clean:
                    _ns_errors.append("Student ID is required.")
                if not _ns_name_clean:
                    _ns_errors.append("Student Name is required.")
                _ns_grade_int = None
                try:
                    _ns_grade_int = int(_ns_grade_clean)
                    if not (1 <= _ns_grade_int <= 12):
                        _ns_errors.append("Grade must be between 1 and 12.")
                except (ValueError, TypeError):
                    _ns_errors.append("Grade must be a number between 1 and 12.")

                _ns_parsed_subjects = []
                for _i, _s in enumerate(_ns_subjects):
                    if not _s["name"].strip():
                        _ns_errors.append(f"Subject {_i + 1} name is required.")
                        continue
                    try:
                        _scores = [
                            float(x.strip())
                            for x in _s["scores_str"].split(",")
                            if x.strip()
                        ]
                        if not _scores:
                            _ns_errors.append(
                                f"Subject {_i + 1} ({_s['name']}) has no scores."
                            )
                        else:
                            _ns_parsed_subjects.append({
                                "name":      _s["name"].strip(),
                                "scores":    _scores,
                                "max_score": float(_s["max_score"]),
                            })
                    except ValueError:
                        _ns_errors.append(
                            f"Subject {_i + 1} scores must be numbers "
                            f"(e.g. 85, 90, 78). Got: {_s['scores_str']!r}"
                        )

                if not _ns_parsed_subjects and not _ns_errors:
                    _ns_errors.append("At least one subject with scores is required.")

                if _ns_errors:
                    for _err in _ns_errors:
                        st.markdown(
                            f'<div class="auth-error">{icon("alert","#ff3d57",14)}'
                            f'&nbsp;{_err}</div>',
                            unsafe_allow_html=True,
                        )
                else:
                    _ns_student_data = {
                        "student_id": _ns_sid_clean,
                        "name":       _ns_name_clean,
                        "grade":      _ns_grade_int,
                        "subjects":   _ns_parsed_subjects,
                    }

                    # ── Step 1: write to Google Sheets ──────────────────────
                    try:
                        _gs_c = get_gs_client()
                        _gs_s = get_spreadsheet(_gs_c)
                        _nrows = write_student_raw_data(_gs_s, _ns_student_data)
                        st.markdown(
                            f'<div class="auth-success">{icon("check","#00e676",14)}'
                            f'&nbsp;Student {_ns_sid_clean} saved to database '
                            f'({_nrows} exam records).</div>',
                            unsafe_allow_html=True,
                        )
                    except Exception as _nse:
                        st.markdown(
                            f'<div class="auth-error">{icon("alert","#ff3d57",14)}'
                            f'&nbsp;Could not save student: {_nse}</div>',
                            unsafe_allow_html=True,
                        )
                        st.stop()

                    # ── Step 2: trigger pipeline ─────────────────────────────
                    _ns_llm = st.session_state.get("selected_provider", "ollama")

                    if IS_CLOUD:
                        try:
                            with st.spinner(
                                f"Processing {_ns_sid_clean} through the AI pipeline..."
                            ):
                                _npr = requests.post(
                                    "https://ai-student-intelligence.onrender.com/run-pipeline",
                                    json={"student_id": _ns_sid_clean, "llm_provider": _ns_llm},
                                    timeout=30,
                                )
                            if _npr.ok:
                                st.success(
                                    f"Report ready. Go to Dashboard and search "
                                    f"{_ns_sid_clean} to view."
                                )
                            else:
                                st.warning(
                                    f"Pipeline returned HTTP {_npr.status_code}. "
                                    "The report will appear in Google Sheets shortly."
                                )
                        except Exception as _npe:
                            st.warning(f"Could not reach pipeline server: {_npe}")
                    else:
                        try:
                            _npr = requests.post(
                                f"{API_BASE}/pipeline/run",
                                json={
                                    "student_id": _ns_sid_clean,
                                    "llm_provider": _ns_llm,
                                },
                                timeout=20,
                            )
                            if _npr.ok:
                                _job_id = _npr.json().get("job_id", "")
                                with st.spinner(
                                    f"Processing {_ns_sid_clean} through the AI pipeline..."
                                ):
                                    _done = False
                                    for _ in range(60):  # poll up to 5 minutes
                                        time.sleep(5)
                                        try:
                                            _sr = requests.get(
                                                f"{API_BASE}/pipeline/status/{_job_id}",
                                                timeout=10,
                                            )
                                            _st_val = _sr.json().get("status", "running")
                                            if _st_val == "done":
                                                _done = True
                                                break
                                            if _st_val == "failed":
                                                _err_msg = _sr.json().get("error", "")
                                                st.error(f"Pipeline failed: {_err_msg}")
                                                break
                                        except Exception:
                                            pass
                                if _done:
                                    st.success(
                                        f"Report ready. Go to Dashboard and search "
                                        f"{_ns_sid_clean} to view."
                                    )
                            else:
                                st.warning(
                                    f"Could not start pipeline "
                                    f"(HTTP {_npr.status_code})."
                                )
                        except requests.exceptions.ConnectionError:
                            st.warning(
                                "Cannot reach the local backend. "
                                "Is pipeline_server.py running?"
                            )
                        except Exception as _npe:
                            st.warning(f"Pipeline error: {_npe}")

# ============================================================
# HELPERS
# ============================================================

def _show_empty_state(icon_html: str, title: str, subtitle: str):
    st.markdown(f"""
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                min-height:42vh;text-align:center;padding:2rem;">
        <div style="margin-bottom:1.1rem;opacity:.25">{icon_html}</div>
        <div style="font-size:1.2rem;font-weight:700;color:#c0c8d8;margin-bottom:.5rem;">{title}</div>
        <div style="font-size:.86rem;color:#555;max-width:340px;line-height:1.6;">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# PAGE ROUTER
# ============================================================

page    = st.session_state.nav_page
u_role  = st.session_state.user_role or "Student"
allowed = ROLE_NAV_ACCESS.get(u_role, ["Dashboard"])

if page not in allowed:
    st.session_state.nav_page = "Dashboard"
    page = "Dashboard"

if   page == "Dashboard": show_dashboard()
elif page == "Students":  show_students()
elif page == "Reports":   show_reports()
elif page == "Settings":  show_settings()
