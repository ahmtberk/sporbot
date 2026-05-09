import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from runtime_config import ConfigStore
from telegram_service import TelegramControlledSlotService


def setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if os.getenv("LOG_TO_FILE", "false").lower() in {"1", "true", "yes"}:
        handlers.append(logging.FileHandler("bot.log", encoding="utf-8"))

    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


def main() -> None:
    setup_logging()
    service = TelegramControlledSlotService(ConfigStore())
    app = service.build_application()
    logging.getLogger("sporbot").info("Telegram controlled Spor Istanbul service started")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
