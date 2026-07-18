import asyncio
import logging
import sys

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
)
from src.services.submission_worker import run_synthetic_submission_worker
from src.telegram_bot.handlers.registration import register_registration_handlers
from src.telegram_bot.handlers.student import register_student_handlers
from src.telegram_bot.handlers.parent import register_parent_handlers
from src.telegram_bot.handlers.teacher import register_teacher_handlers
from src.telegram_bot.handlers.demo import register_demo_handlers


logger = logging.getLogger(__name__)
background_tasks: set[asyncio.Task] = set()


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher()

    register_registration_handlers(dp)
    register_demo_handlers(dp)
    register_student_handlers(dp)
    register_parent_handlers(dp)
    register_teacher_handlers(dp)
    dp.startup.register(schedule_submission_worker)

    return dp


async def run_polling() -> None:
    bot = Bot(token=BOT_TOKEN)
    dp = create_dispatcher()
    await dp.start_polling(bot)


async def health_check(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "mode": BOT_MODE})


async def set_telegram_webhook_with_retry(bot: Bot) -> None:
    attempt = 0

    while True:
        attempt += 1

        try:
            await bot.set_webhook(
                f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}",
                secret_token=WEBHOOK_SECRET,
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

    task = asyncio.create_task(run_synthetic_submission_worker(bot))
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
