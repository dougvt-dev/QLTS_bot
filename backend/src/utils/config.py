import os
import urllib.parse
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Thiếu biến môi trường bắt buộc: {name}")
    return value


DB_SERVER = _require("DB_SERVER")
DB_NAME = _require("DB_NAME")
DB_USER = _require("DB_USER")
DB_PASS = _require("DB_PASS")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash-lite")

# URL encode the password to handle special characters like '@'
password_encoded = urllib.parse.quote_plus(DB_PASS)

# Construct connection URL for SQLAlchemy
CONNECTION_URL = (
    f"mssql+pyodbc://{DB_USER}:{password_encoded}@{DB_SERVER}:1433/{DB_NAME}"
    f"?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
)
