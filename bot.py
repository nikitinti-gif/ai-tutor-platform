import asyncio
import json
import logging
import os
import sys

import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramAPIError
from aiogram.webhook.aiohttp_server import (
    SimpleRequestHandler,
    setup_application,
)

from config import (
    BOT_MODE,
    BOT_TOKEN,
    PORT,
    WEBHOOK_BASE_URL,
    WEBHOOK_PATH,
    WEBHOOK_SECRET,
    SYNTHETIC_GEMINI_WORKER_ENABLED,
    LIVE_DIAGNOSTIC_SELF_CHECK_ENABLED,
)
from src.services.submission_worker import run_synthetic_submission_worker
from src.telegram_bot.handlers.registration import register_registration_handlers
from src.telegram_bot.handlers.student import register_student_handlers
from src.telegram_bot.handlers.ege_hint import register_ege_hint_handlers
from src.telegram_bot.handlers.parent import register_parent_handlers
from src.telegram_bot.handlers.teacher import register_teacher_handlers
from src.telegram_bot.handlers.demo import register_demo_handlers


logger = logging.getLogger(__name__)
background_tasks: set[asyncio.Task] = set()


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher()

    register_registration_handlers(dp)
    register_demo_handlers(dp)
    register_ege_hint_handlers(dp)
    register_student_handlers(dp)
    register_parent_handlers(dp)
    register_teacher_handlers(dp)
    dp.startup.register(log_ege_persistence_backend)
    dp.startup.register(log_outbound_location)
    dp.startup.register(schedule_submission_worker)
    dp.startup.register(schedule_live_diagnostic_self_check)

    return dp


async def run_polling() -> None:
    bot = Bot(token=BOT_TOKEN)
    dp = create_dispatcher()
    await dp.start_polling(bot)


def ege_persistence_report() -> dict:
    """Describe whether EGE state can survive replacement of a Render instance."""
    if os.getenv("DATABASE_URL", "").strip():
        return {"backend": "postgres", "durable": True}
    return {
        "backend": "json",
        "durable": False,
        "warning": "Render restart/deploy may lose student exam state",
    }


async def log_ege_persistence_backend() -> None:
    report = ege_persistence_report()
    message = "EGE_PERSISTENCE backend=%s durable=%s"
    args = [report["backend"], str(report["durable"]).lower()]
    if report.get("warning"):
        message += ' warning="%s"'
        args.append(report["warning"])
    logger.warning(message, *args) if not report["durable"] else logger.info(message, *args)


async def health_check(_: web.Request) -> web.Response:
    payload = {
        "status": "ok",
        "mode": BOT_MODE,
        "ege_persistence": ege_persistence_report(),
    }
    if LIVE_DIAGNOSTIC_SELF_CHECK_ENABLED:
        from src.services.ege_exam_service import SELF_CHECK_RESULT_PATH

        if SELF_CHECK_RESULT_PATH.exists():
            try:
                payload["live_diagnostic_self_check"] = json.loads(
                    SELF_CHECK_RESULT_PATH.read_text(encoding="utf-8")
                )
            except (OSError, ValueError):
                payload["live_diagnostic_self_check"] = {"status": "unreadable"}
        else:
            payload["live_diagnostic_self_check"] = {"status": "running"}
    return web.json_response(payload)


async def log_outbound_location() -> None:
    """Log the public egress location without exposing the service IP."""
    timeout = aiohttp.ClientTimeout(total=10)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get("https://ipinfo.io/json") as response:
                response.raise_for_status()
                payload = await response.json()
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as error:
        logger.warning("Outbound location check failed: %s", error)
        return

    logger.info(
        "Outbound location: country=%s, region=%s, city=%s, timezone=%s",
        payload.get("country", "unknown"),
        payload.get("region", "unknown"),
        payload.get("city", "unknown"),
        payload.get("timezone", "unknown"),
    )


async def set_telegram_webhook_with_retry(bot: Bot) -> None:
    attempt = 0

    while True:
        attempt += 1

        try:
            await bot.set_webhook(
                f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}",
                secret_token=WEBHOOK_SECRET,
                allowed_updates=["message", "callback_query"],
            )
            logger.info("Telegram webhook зарегистрирован.")
            return
        except TelegramAPIError as error:
            retry_delay = min(5 * attempt, 60)
            logger.warning(
                "Webhook пока не зарегистрирован (попытка %s): %s. "
                "Повтор через %s сек.",
                attempt,
                error,
                retry_delay,
            )
            await asyncio.sleep(retry_delay)


async def schedule_telegram_webhook(bot: Bot) -> None:
    task = asyncio.create_task(set_telegram_webhook_with_retry(bot))
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)


async def schedule_submission_worker(bot: Bot) -> None:
    if not SYNTHETIC_GEMINI_WORKER_ENABLED:
        logger.info("Synthetic Gemini worker is disabled.")
        return

    if not os.getenv("DATABASE_URL", "").strip():
        logger.info(
            "Synthetic Gemini worker skipped: DATABASE_URL is not configured."
        )
        return

    task = asyncio.create_task(run_synthetic_submission_worker(bot))
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)


async def schedule_live_diagnostic_self_check(bot: Bot) -> None:
    """Run the temporary real-Gemini probe check without blocking startup."""
    if not LIVE_DIAGNOSTIC_SELF_CHECK_ENABLED:
        return

    from src.services.ege_exam_service import run_live_diagnostic_self_check

    task = asyncio.create_task(run_live_diagnostic_self_check(bot))
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)


def run_webhook() -> None:
    bot = Bot(token=BOT_TOKEN)
    dp = create_dispatcher()
    dp.startup.register(schedule_telegram_webhook)

    app = web.Application()
    app.router.add_get("/", health_check)
    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET,
    ).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    web.run_app(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    if BOT_MODE == "webhook":
        run_webhook()
    else:
        asyncio.run(run_polling())
