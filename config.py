import os
import re

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
QWEN_PILOT_V2_ENABLED = os.getenv(
    "QWEN_PILOT_V2_ENABLED",
    "false",
).strip().lower() in {"1", "true", "yes", "on"}
SYNTHETIC_GEMINI_WORKER_ENABLED = os.getenv(
    "SYNTHETIC_GEMINI_WORKER_ENABLED",
    "false",
).strip().lower() in {"1", "true", "yes", "on"}
SYNTHETIC_WORKER_INTERVAL_SECONDS = max(
    5,
    int(os.getenv("SYNTHETIC_WORKER_INTERVAL_SECONDS", "15")),
)
SYNTHETIC_WORKER_MAX_ATTEMPTS = max(
    1,
    min(int(os.getenv("SYNTHETIC_WORKER_MAX_ATTEMPTS", "2")), 3),
)
BOT_MODE = os.getenv("BOT_MODE", "polling").strip().lower()
WEBHOOK_BASE_URL = (
    os.getenv("WEBHOOK_BASE_URL")
    or os.getenv("RENDER_EXTERNAL_URL")
    or ""
).rstrip("/")
WEBHOOK_PATH = os.getenv(
    "WEBHOOK_PATH",
    "/telegram/webhook",
)
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
PORT = int(os.getenv("PORT", "10000"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в .env")

if QWEN_PILOT_V2_ENABLED and not ADMIN_TELEGRAM_ID:
    raise ValueError(
        "Для QWEN_PILOT_V2_ENABLED нужен ADMIN_TELEGRAM_ID"
    )

if SYNTHETIC_GEMINI_WORKER_ENABLED and not ADMIN_TELEGRAM_ID:
    raise ValueError(
        "Для SYNTHETIC_GEMINI_WORKER_ENABLED нужен ADMIN_TELEGRAM_ID"
    )

if BOT_MODE not in {"polling", "webhook"}:
    raise ValueError("BOT_MODE должен быть polling или webhook")

if not WEBHOOK_PATH.startswith("/"):
    raise ValueError("WEBHOOK_PATH должен начинаться с /")

if BOT_MODE == "webhook":
    if not WEBHOOK_BASE_URL.startswith("https://"):
        raise ValueError(
            "Для webhook нужен HTTPS-адрес в WEBHOOK_BASE_URL "
            "или RENDER_EXTERNAL_URL"
        )

    if not WEBHOOK_SECRET:
        raise ValueError("WEBHOOK_SECRET не найден")

    if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", WEBHOOK_SECRET):
        raise ValueError(
            "WEBHOOK_SECRET может содержать только буквы, цифры, "
            "_ и -"
        )
