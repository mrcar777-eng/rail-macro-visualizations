import os
from dotenv import load_dotenv

load_dotenv()

FRED_SERIES_IDS = {
    "RAILFRTCARLOADSD11":   "Rail Freight Carloads (SA)",
    "RAILFRTINTERMODALD11": "Intermodal Traffic (SA)",
    "PCU4821114821114":     "Line-Haul Railroads PPI",
    "WPU30110101":          "Railroad Equipment PPI",
    "CES4348200001":        "Rail Transportation Employment",
}

# Ticker -> 10-digit zero-padded CIK from SEC Edgar
TARGET_RAIL_COMPANIES = {
    "UNP": "0000100885",  # Union Pacific Corporation
    "CSX": "0000277948",  # CSX Corporation
    "NSC": "0000702165",  # Norfolk Southern Corporation
}

FRED_API_KEY    = os.getenv("FRED_API_KEY")
SEC_USER_AGENT  = os.getenv("SEC_USER_AGENT")
STB_APP_TOKEN   = os.getenv("STB_APP_TOKEN")
FRA_USERNAME    = os.getenv("FRA_USERNAME")   # FRA SecureApi account username
FRA_PASSWORD    = os.getenv("FRA_PASSWORD")   # FRA SecureApi account password
FAF5_CSV_URL    = os.getenv("FAF5_CSV_URL", "https://faf.ornl.gov/faf5/data/download_files/FAF5.7.1_2017-2024.zip")

DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_USER     = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME     = os.getenv("DB_NAME", "rail_macro_db")
