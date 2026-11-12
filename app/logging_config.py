"""Console logs: never log Telegram updates or third-party exception messages."""

import copy
import logging
import re
from collections.abc import Iterable


class SafeFormatter(logging.Formatter):
    def __init__(self, secrets: Iterable[str] = ()) -> None:
        super().__init__("%(asctime)s %(levelname)s %(name)s: %(message)s")
        self.secrets = tuple(value for value in secrets if value)

    def format(self, record: logging.LogRecord) -> str:
        safe = copy.copy(record)
        if not record.name.startswith("app."):
            # Library diagnostics may contain request URLs, tokens or user text.
            safe.msg = "Kutubxona hodisasi (xabar mazmuni yashirildi)."
            safe.args = ()
        if safe.exc_info:
            safe.msg = f"{safe.getMessage()} error_type={safe.exc_info[0].__name__}"
            safe.args = ()
        safe.exc_info = None
        safe.exc_text = None
        safe.stack_info = None
        text = super().format(safe)
        for value in self.secrets:
            text = text.replace(value, "[SECRET]")
        text = re.sub(r"\b[0-9]{5,}:[A-Za-z0-9_-]{20,}\b", "[BOT_TOKEN]", text)
        return re.sub(r"\bgsk_[A-Za-z0-9_-]+\b", "[API_KEY]", text)


def configure_logging(level: str = "INFO", secrets: Iterable[str] = ()) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(SafeFormatter(secrets))
    logging.basicConfig(level=level, handlers=[handler], force=True)
    # Keep noisy request/update logs out of the console, even in DEBUG mode.
    for name in ("aiogram", "aiohttp", "asyncio"):
        logging.getLogger(name).setLevel(logging.WARNING)
