import os
import re
import logging
from dotenv import load_dotenv

load_dotenv()

# ─── Bot ──────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change_this_secret_2024")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
API_PORT = int(os.getenv("API_PORT", "5000"))
# DB config:
# 1) If DATABASE_URL is provided, use it directly.
# 2) Otherwise build URL from POSTGRES_* variables.
_db_url = os.getenv("DATABASE_URL", "").strip()
if _db_url:
    DATABASE_URL = _db_url
else:
    _pg_user = os.getenv("POSTGRES_USER", "bot")
    _pg_pass = os.getenv("POSTGRES_PASSWORD", "botpass")
    _pg_host = os.getenv("POSTGRES_HOST", "localhost")
    _pg_port = os.getenv("POSTGRES_PORT", "5432")
    _pg_db = os.getenv("POSTGRES_DB", "fastbot")
    DATABASE_URL = f"postgresql://{_pg_user}:{_pg_pass}@{_pg_host}:{_pg_port}/{_pg_db}"
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# ─── Rate limiting ────────────────────────────────────────
TG_RATE_LIMIT = 25
TG_RETRY_ATTEMPTS = 3

# ─── Logging ──────────────────────────────────────────────
logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
log = logging.getLogger("fast_edu")


# ─── Utils ────────────────────────────────────────────────
def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) == 9:
        digits = "998" + digits
    elif len(digits) == 10 and digits.startswith("8"):
        digits = "998" + digits[1:]
    return digits
