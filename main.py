import json
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = FastAPI(title="Google Sheets Analytics API")

# Enable CORS for our frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
# Render pe hum secret file upload karenge 'hide.json' naam se
SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "hide.json")

# The Google Sheet ID from your URL
SPREADSHEET_ID = "1Wrli-3CPxnnQCRpPXMLoraReJGLroXS8gHVnUJmnk3Y"

# Scope for gspread
SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

@app.get("/")
def root():
    return {"status": "ok", "message": "DelhiLivery API is running"}

@app.get("/api/orders")
def get_orders():
    """
    Connects to Google Sheets via gspread using the service account,
    fetches all records from 'Sheet1', and returns them as a JSON array.
    """
    try:
        # 1. Authenticate with Service Account
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            SERVICE_ACCOUNT_FILE, SCOPES
        )
        client = gspread.authorize(creds)

        # 2. Open the Spreadsheet and specific sheet
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet("Sheet1")

        # 3. Get all records as dictionary (auto-maps headers to dict keys)
        records = sheet.get_all_records()

        return {"success": True, "data": records}

    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    # Make sure to run on 0.0.0.0 and dynamically get the PORT from Render
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
