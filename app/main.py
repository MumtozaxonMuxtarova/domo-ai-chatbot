"""Run with `python -m app.main`; --check-config performs no network requests."""

import argparse
import asyncio
import logging
import sys

from aiogram.exceptions import TelegramConflictError, TelegramNetworkError, TelegramUnauthorizedError
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats

from app.bot.factory import create_bot, create_dispatcher
from app.bot.ai import create_ai_runtime
from app.config import ConfigurationError, Settings, load_settings
from app.logging_config import configure_logging
from app.faq import KnowledgeBaseError

logger = logging.getLogger("app.main")


async def run_bot(settings: Settings) -> None:
    dispatcher = create_dispatcher()
    bot = create_bot(settings)
    runtime = None
    try:
        runtime = await create_ai_runtime(dispatcher["faq_catalog"])
        dispatcher["rag_service"] = runtime
        scope = BotCommandScopeAllPrivateChats()
        await bot.set_my_commands([
            BotCommand(command="start", description="Boshlash / Начать"),
            BotCommand(command="help", description="Yordam / Помощь"),
            BotCommand(command="language", description="Til / Язык"),
        ], scope=scope)
        logger.info("DOMO AI ishga tushmoqda. Rejim: DEMO, FAQ + RAG. AI_ready=%s", runtime is not None)
        # Do not delete webhooks or discard pending updates automatically.
        await dispatcher.start_polling(
            bot, allowed_updates=dispatcher.resolve_used_update_types(), close_bot_session=False
        )
    finally:
        try:
            if runtime is not None:
                await runtime.aclose()
        finally:
            await dispatcher.storage.close()
            await dispatcher.fsm.events_isolation.close()
            await bot.session.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DOMO AI — FAQ + RAG Telegram demo")
    parser.add_argument("--check-config", action="store_true", help="Sozlamalarni tarmoqsiz tekshirish")
    args = parser.parse_args(argv)
    try:
        settings = load_settings()
    except ConfigurationError as error:
        print(f"Sozlama xatosi: {error}", file=sys.stderr)
        return 2
    configure_logging(settings.log_level, [settings.bot_token.get_secret_value()])
    if args.check_config:
        print("Sozlamalar formati to'g'ri. Token Telegram orqali tekshirilmagan.")
        return 0
    try:
        asyncio.run(run_bot(settings))
    except (KeyboardInterrupt, SystemExit):
        logger.info("DOMO AI to'xtatildi.")
    except TelegramUnauthorizedError:
        logger.error("Telegram tokenni qabul qilmadi. BotFather tokenini tekshiring.")
        return 1
    except TelegramConflictError:
        logger.error("Bot boshqa joyda ishlayapti yoki webhook faol. Bitta ishga tushirish usulidan foydalaning.")
        return 1
    except TelegramNetworkError:
        logger.error("Telegram bilan aloqa yo'q. Internet ulanishini tekshiring.")
        return 1
    except KnowledgeBaseError as error:
        logger.error("Bilim bazasi xatosi: %s", error)
        return 1
    except Exception as error:
        logger.error("Botni ishga tushirishda xatolik. error_type=%s", type(error).__name__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
