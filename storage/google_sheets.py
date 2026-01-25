# -*- coding: utf-8 -*-

import os
import json
import base64
from typing import List

import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials

from config.app_config import GOOGLE_SHEETS_DB_NAME

# =====================================================
# AUTH — RENDER SAFE (BASE64, NO FILES)
# =====================================================

def get_gs_client() -> gspread.Client:
    """
    Authenticate using GOOGLE_CREDENTIALS_BASE64
    (Required for Render / cloud deployments)
    """

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    creds_b64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")
    if not creds_b64:
        raise RuntimeError("GOOGLE_CREDENTIALS_BASE64 environment variable not set")

    try:
        creds_json = json.loads(
            base64.b64decode(creds_b64).decode("utf-8")
        )
    except Exception as e:
        raise RuntimeError("Invalid GOOGLE_CREDENTIALS_BASE64 value") from e

    credentials = Credentials.from_service_account_info(
        creds_json,
        scopes=scopes,
    )

    return gspread.authorize(credentials)


def get_spreadsheet(client: gspread.Client) -> gspread.Spreadsheet:
    if not GOOGLE_SHEETS_DB_NAME:
        raise RuntimeError("GOOGLE_SHEETS_DB_NAME not set")
    return client.open(GOOGLE_SHEETS_DB_NAME)

# =====================================================
# SANITIZER (ABSOLUTE)
# =====================================================

def _sanitize_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    df = df.copy()
    df.replace([np.nan, np.inf, -np.inf], "", inplace=True)
    return df

# =====================================================
# READ (HEADER SAFE)
# =====================================================

def read_table(
    spreadsheet: gspread.Spreadsheet,
    table_name: str,
) -> pd.DataFrame:
    worksheet = spreadsheet.worksheet(table_name)
    values = worksheet.get_all_values()

    if not values or len(values) < 2:
        return pd.DataFrame()

    headers = values[0]
    rows = values[1:]

    return pd.DataFrame(rows, columns=headers)

# =====================================================
# WRITE (HEADER FIRST)
# =====================================================

def write_table(
    spreadsheet: gspread.Spreadsheet,
    table_name: str,
    df: pd.DataFrame,
):
    df = _sanitize_df(df)

    try:
        worksheet = spreadsheet.worksheet(table_name)
        worksheet.clear()
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=table_name,
            rows=str(max(len(df) + 10, 100)),
            cols=str(len(df.columns) + 5),
        )

    worksheet.update(
        [df.columns.tolist()] + df.values.tolist()
    )

# =====================================================
# APPEND
# =====================================================

def append_table(
    spreadsheet: gspread.Spreadsheet,
    table_name: str,
    df: pd.DataFrame,
):
    if df is None or df.empty:
        return

    df = _sanitize_df(df)

    try:
        worksheet = spreadsheet.worksheet(table_name)
        values = worksheet.get_all_values()
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=table_name,
            rows=str(max(len(df) + 10, 100)),
            cols=str(len(df.columns) + 5),
        )
        values = []

    # If headers mismatch → rewrite
    if not values or values[0] != df.columns.tolist():
        worksheet.clear()
        worksheet.update(
            [df.columns.tolist()] + df.values.tolist()
        )
    else:
        worksheet.append_rows(
            df.values.tolist(),
            value_input_option="USER_ENTERED",
        )

# =====================================================
# UPSERT (IDEMPOTENT)
# =====================================================

def upsert_table(
    spreadsheet: gspread.Spreadsheet,
    table_name: str,
    df: pd.DataFrame,
    key_columns: List[str],
):
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

    cleaned = existing[mask]
    final_df = pd.concat([cleaned, df], ignore_index=True)
    final_df = _sanitize_df(final_df)

    write_table(spreadsheet, table_name, final_df)
