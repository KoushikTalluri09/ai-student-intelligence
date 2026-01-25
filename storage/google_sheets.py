# -*- coding: utf-8 -*-

import os
import json
import base64
import tempfile
import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials
from typing import List

from config.app_config import GOOGLE_SHEETS_DB_NAME

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

    raise RuntimeError(
        "Google Sheets credentials not found. "
        "Set GOOGLE_CREDENTIALS_BASE64 (Render) or GOOGLE_SHEETS_CREDENTIALS (local)."
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
    return client.open(GOOGLE_SHEETS_DB_NAME)

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
    worksheet = spreadsheet.worksheet(table_name)
    values = worksheet.get_all_values()

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
        ws = spreadsheet.worksheet(table_name)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(
            title=table_name,
            rows=str(max(len(df) + 10, 100)),
            cols=str(len(df.columns) + 5),
        )

    ws.update([df.columns.tolist()] + df.values.tolist())

def append_table(spreadsheet, table_name: str, df: pd.DataFrame):
    if df is None or df.empty:
        return

    df = _sanitize_df(df)

    try:
        ws = spreadsheet.worksheet(table_name)
        values = ws.get_all_values()
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(
            title=table_name,
            rows=str(max(len(df) + 10, 100)),
            cols=str(len(df.columns) + 5),
        )
        values = []

    if not values or values[0] != df.columns.tolist():
        ws.clear()
        ws.update([df.columns.tolist()] + df.values.tolist())
    else:
        ws.append_rows(df.values.tolist(), value_input_option="USER_ENTERED")

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
