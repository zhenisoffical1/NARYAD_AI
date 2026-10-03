"""Telegram-бот. Запуск: python -m app.bot

Без TELEGRAM_BOT_TOKEN процесс остаётся запущенным и ничего не делает — так
docker compose не перезапускает контейнер по кругу, а уведомления идут только в PWA.
"""

import asyncio
import logging

from app.config import settings

log = logging.getLogger("naryadai.bot")


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    if not settings.telegram_bot_token:
        log.info("TELEGRAM_BOT_TOKEN не задан — бот выключен, уведомления идут только в PWA")
        await asyncio.Event().wait()
    log.info("Бот будет подключён на этапе уведомлений")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
