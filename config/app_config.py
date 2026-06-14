import os

# Path to the Google Service Account JSON file (local fallback)
GOOGLE_SHEETS_CREDENTIALS = "config/google_service_account.json"

# Spreadsheet name — overridable via env var or st.secrets
GOOGLE_SHEETS_DB_NAME = os.getenv("GOOGLE_SHEETS_DB_NAME", "AI_Student_Intelligence_DB")
