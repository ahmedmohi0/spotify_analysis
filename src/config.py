from pathlib import Path
from dotenv import load_dotenv
import os
BASE_DIR = Path(__file__).resolve().parent.parent

RAW_DATA_DIR = BASE_DIR / "data" / "output"

load_dotenv()
DB_username = os.getenv("DB_USERNAME")
DB_password = os.getenv("DB_PASSWORD")
DB_host = os.getenv("DB_HOST")
DB_port = os.getenv("DB_PORT")
DB_name = os.getenv("DB_NAME")