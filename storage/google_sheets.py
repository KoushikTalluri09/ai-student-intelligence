# -*- coding: utf-8 -*-

import os
import json
import base64
import tempfile
import time
import functools
import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials
from typing import List


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

from config.app_config import GOOGLE_SHEETS_DB_NAME, GOOGLE_SHEETS_CREDENTIALS as _DEFAULT_CRED_PATH

# =====================================================
# CREDENTIAL LOADER (RENDER + LOCAL SAFE)
# =====================================================

def _load_credentials_file() -> str:
    """
    Loads Google credentials from:
    1) GOOGLE_CREDENTIALS_BASE64 (Render / prod)
    2) GOOGLE_SHEETS_CREDENTIALS (local file path)
    """
    b64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")
    path = os.getenv("GOOGLE_SHEETS_CREDENTIALS")

    if b64:
        decoded = base64.b64decode(b64).decode("utf-8")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        tmp.write(decoded.encode("utf-8"))
        tmp.close()
        return tmp.name

    if path and os.path.exists(path):
        return path

    if os.path.exists(_DEFAULT_CRED_PATH):
        return _DEFAULT_CRED_PATH

    raise RuntimeError(
        "Google Sheets credentials not found. "
        "Set GOOGLE_CREDENTIALS_BASE64 (Render) or GOOGLE_SHEETS_CREDENTIALS (local path), "
        f"or place the service account JSON at '{_DEFAULT_CRED_PATH}'."
    )

# =====================================================
# AUTH
# =====================================================

def get_gs_client() -> gspread.Client:
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    cred_file = _load_credentials_file()
    credentials = Credentials.from_service_account_file(
        cred_file,
        scopes=scopes,
    )
    return gspread.authorize(credentials)

def get_spreadsheet(client: gspread.Client) -> gspread.Spreadsheet:
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
