# -*- coding: utf-8 -*-

import os
import json
import base64
import time
import pandas as pd
import numpy as np
import gspread
import streamlit as st
from google.oauth2.service_account import Credentials
from typing import List


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _with_backoff(fn, *args, max_retries=5, **kwargs):
    """Retry fn(*args, **kwargs) with exponential backoff on Google 429 errors and transient network resets."""
    import requests as _requests
    delay = 10
    for attempt in range(max_retries):
        try:
            return fn(*args, **kwargs)
        except gspread.exceptions.APIError as e:
            if attempt == max_retries - 1:
                raise
            status = getattr(e.response, "status_code", None)
            if status != 429:
                raise
            print(f"[google_sheets] 429 rate-limit hit, retrying in {delay}s...")
            time.sleep(delay)
            delay = min(delay * 2, 120)
        except (_requests.exceptions.ConnectionError, ConnectionResetError, OSError) as e:
            if attempt == max_retries - 1:
                raise
            print(f"[google_sheets] Network error ({type(e).__name__}), retrying in {delay}s...")
            time.sleep(delay)
            delay = min(delay * 2, 120)


# =====================================================
# CREDENTIAL LOADER (STREAMLIT CLOUD + RENDER + LOCAL)
# =====================================================

def get_credentials() -> Credentials:
    # Method 1: Streamlit Cloud secrets (gcp_service_account section)
    try:
        if hasattr(st, 'secrets') and 'gcp_service_account' in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            return Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    except Exception:
        pass

    # Method 2: base64-encoded JSON — env var (Render) or Streamlit secret string (old format)
    try:
        b64 = os.environ.get("GOOGLE_CREDENTIALS_BASE64")
        if not b64:
            b64 = st.secrets.get("GOOGLE_CREDENTIALS_BASE64")
        if b64:
            creds_json = json.loads(base64.b64decode(b64))
            return Credentials.from_service_account_info(creds_json, scopes=SCOPES)
    except Exception:
        pass

    # Method 3: Local development — JSON file on disk
    local_paths = [
        "config/google_service_account.json",
        "google_service_account.json",
        "service_account.json",
    ]
    for path in local_paths:
        if os.path.exists(path):
            return Credentials.from_service_account_file(path, scopes=SCOPES)

    raise ValueError(
        "Google Sheets credentials not found. "
        "Set gcp_service_account in Streamlit secrets, "
        "GOOGLE_CREDENTIALS_BASE64 env var on Render, "
        "or place JSON at config/google_service_account.json locally."
    )


def get_sheet_id() -> str:
    # Streamlit Cloud
    try:
        if hasattr(st, 'secrets') and 'GOOGLE_SHEETS_ID' in st.secrets:
            return st.secrets["GOOGLE_SHEETS_ID"]
    except Exception:
        pass
    # Environment variable or .env
    sheet_id = os.environ.get("GOOGLE_SHEETS_ID")
    if sheet_id:
        return sheet_id
    raise ValueError("GOOGLE_SHEETS_ID not found in secrets or environment.")


# =====================================================
# AUTH
# =====================================================

def get_gs_client() -> gspread.Client:
    return gspread.authorize(get_credentials())


def get_spreadsheet(client: gspread.Client) -> gspread.Spreadsheet:
    try:
        sheet_id = get_sheet_id()
        return _with_backoff(client.open_by_key, sheet_id)
    except ValueError:
        # Fall back to opening by name (backward compat for GOOGLE_SHEETS_DB_NAME)
        from config.app_config import GOOGLE_SHEETS_DB_NAME
        return _with_backoff(client.open, GOOGLE_SHEETS_DB_NAME)


# =====================================================
# SANITIZER
# =====================================================

def _sanitize_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    df = df.copy()
    df.replace([np.nan, np.inf, -np.inf], "", inplace=True)
    return df


# =====================================================
# READ
# =====================================================

def read_table(spreadsheet: gspread.Spreadsheet, table_name: str) -> pd.DataFrame:
    worksheet = _with_backoff(spreadsheet.worksheet, table_name)
    values = _with_backoff(worksheet.get_all_values)

    if not values or len(values) < 2:
        return pd.DataFrame()

    headers = values[0]
    rows = values[1:]
    return pd.DataFrame(rows, columns=headers)


# =====================================================
# WRITE
# =====================================================

def write_table(spreadsheet, table_name: str, df: pd.DataFrame):
    df = _sanitize_df(df)

    try:
        ws = _with_backoff(spreadsheet.worksheet, table_name)
        _with_backoff(ws.clear)
    except gspread.WorksheetNotFound:
        ws = _with_backoff(
            spreadsheet.add_worksheet,
            title=table_name,
            rows=str(max(len(df) + 10, 100)),
            cols=str(len(df.columns) + 5),
        )

    _with_backoff(ws.update, [df.columns.tolist()] + df.values.tolist())


def append_table(spreadsheet, table_name: str, df: pd.DataFrame):
    if df is None or df.empty:
        return

    df = _sanitize_df(df)

    try:
        ws = _with_backoff(spreadsheet.worksheet, table_name)
        values = _with_backoff(ws.get_all_values)
    except gspread.WorksheetNotFound:
        ws = _with_backoff(
            spreadsheet.add_worksheet,
            title=table_name,
            rows=str(max(len(df) + 10, 100)),
            cols=str(len(df.columns) + 5),
        )
        values = []

    if not values or values[0] != df.columns.tolist():
        _with_backoff(ws.clear)
        _with_backoff(ws.update, [df.columns.tolist()] + df.values.tolist())
    else:
        _with_backoff(ws.append_rows, df.values.tolist(), value_input_option="USER_ENTERED")


def update_user_student_id(spreadsheet, email: str, student_id: str):
    """Set student_id for a user row identified by email, adding the column if missing."""
    df = read_table(spreadsheet, "users")
    if df.empty or "email" not in df.columns:
        return
    if "student_id" not in df.columns:
        cols = list(df.columns)
        insert_at = cols.index("role") + 1 if "role" in cols else len(cols)
        cols.insert(insert_at, "student_id")
        df = df.reindex(columns=cols, fill_value="")
    mask = df["email"].str.lower().str.strip() == email.strip().lower()
    if not mask.any():
        return
    df.loc[mask, "student_id"] = student_id
    write_table(spreadsheet, "users", df)


# =====================================================
# PER-STUDENT QUERY HELPERS
# Each opens its own GS client so callers don't need
# to manage the spreadsheet handle.
# =====================================================

def _filter_by_student(table_name: str, student_id: str) -> pd.DataFrame:
    client = get_gs_client()
    sp = get_spreadsheet(client)
    df = read_table(sp, table_name)
    if df.empty or "student_id" not in df.columns:
        return pd.DataFrame()
    df["student_id"] = df["student_id"].astype(str).str.strip()
    return df[df["student_id"] == student_id.strip()]


def get_student_consolidated(student_id: str) -> dict:
    rows = _filter_by_student("student_consolidated_latest", student_id)
    return rows.iloc[0].to_dict() if not rows.empty else {}


def get_subject_summaries(student_id: str) -> list:
    return _filter_by_student("subject_summaries", student_id).to_dict("records")


def get_subject_insights(student_id: str) -> list:
    return _filter_by_student("subject_insights", student_id).to_dict("records")


def get_subject_analytics(student_id: str) -> list:
    return _filter_by_student("subject_analytics", student_id).to_dict("records")


def get_student_report_direct(student_id: str) -> dict:
    """Read pre-computed student data directly from Google Sheets, bypassing any API server.

    Returns a dict with keys: consolidated, summaries, insights, analytics.
    Each value is a list of row dicts filtered to the given student_id.
    Empty list means that tab had no rows for this student (or the tab doesn't exist).
    """
    creds = get_credentials()
    client = gspread.authorize(creds)
    sheet = client.open_by_key(get_sheet_id())

    tabs = {
        "consolidated": "student_consolidated_latest",
        "summaries":    "subject_summaries",
        "insights":     "subject_insights",
        "analytics":    "subject_analytics",
    }

    result: dict = {}
    for key, tab_name in tabs.items():
        try:
            worksheet = _with_backoff(sheet.worksheet, tab_name)
            records = _with_backoff(worksheet.get_all_records)
            filtered = [
                r for r in records
                if str(r.get("student_id", "")).strip().upper() ==
                   str(student_id).strip().upper()
            ]
            result[key] = filtered
        except Exception:
            result[key] = []

    return result


def upsert_table(spreadsheet, table_name: str, df: pd.DataFrame, key_columns: List[str]):
    df = _sanitize_df(df)

    try:
        existing = read_table(spreadsheet, table_name)
    except Exception:
        existing = pd.DataFrame()

    if existing.empty:
        write_table(spreadsheet, table_name, df)
        return

    mask = ~existing[key_columns].apply(tuple, axis=1).isin(
        df[key_columns].apply(tuple, axis=1)
    )
    final_df = pd.concat([existing[mask], df], ignore_index=True)
    write_table(spreadsheet, table_name, final_df)
