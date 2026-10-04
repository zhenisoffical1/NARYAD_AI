"""Telegram-бот. Запуск: python -m app.bot

Два цикла в одном процессе: приём команд и кнопок (long polling) и отправка уведомлений —
бот раз в пару секунд забирает из ленты то, что ещё не ушло в Telegram.

Без TELEGRAM_BOT_TOKEN процесс остаётся запущенным и ничего не делает — так
docker compose не перезапускает контейнер по кругу, а уведомления идут только в PWA.
"""

import asyncio
import logging
from datetime import timedelta

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import select

from app.bot.handlers import handle_callback, link_chat, unlink_chat
from app.bot.messages import OutMessage, render
from app.config import settings
from app.db import SessionLocal
from app.errors import DomainError
from app.models import Employee, Notification
from app.models.base import utcnow

log = logging.getLogger("naryadai.bot")
router = Router()

# Старое не досылаем: после простоя бота важны только свежие уведомления
SEND_WINDOW = timedelta(minutes=15)

HELLO = (
    "Это бот НарядAI. Чтобы получать наряды сюда, откройте приложение → «Профиль» → "
    "«Подключить Telegram»."
)


def keyboard(message: OutMessage) -> InlineKeyboardMarkup | None:
    if not message.rows:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=b.text, callback_data=b.callback, url=b.url) for b in row]
            for row in message.rows
        ]
    )


@router.message(CommandStart())
async def on_start(message: Message, command: CommandObject) -> None:
    if not command.args:
        await message.answer(HELLO)
        return
    async with SessionLocal() as session:
        await message.answer(await link_chat(session, command.args.strip(), message.chat.id))


@router.message(Command("stop"))
async def on_stop(message: Message) -> None:
    async with SessionLocal() as session:
        await message.answer(await unlink_chat(session, message.chat.id))


@router.callback_query(F.data)
async def on_button(query: CallbackQuery) -> None:
    if query.message is None or query.data is None:
        await query.answer()
        return
    async with SessionLocal() as session:
        try:
            result = await handle_callback(session, query.message.chat.id, query.data)
        except DomainError as exc:
            await query.answer(exc.message, show_alert=True)
            return
    await query.answer(result)
    if isinstance(query.message, Message) and query.message.html_text:
        await query.message.edit_text(
            f"{query.message.html_text}\n\n<b>{result}</b>", reply_markup=None
        )


async def send_pending(bot: Bot) -> int:
    """Отправить неотправленные уведомления тем, у кого привязан Telegram."""
    sent = 0
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(Notification, Employee)
                .join(Employee, Employee.id == Notification.employee_id)
                .where(
                    Notification.telegram_sent_at.is_(None),
                    Notification.created_at >= utcnow() - SEND_WINDOW,
                    Employee.telegram_chat_id.is_not(None),
                )
                .order_by(Notification.id)
                .limit(50)
            )
        ).all()
        for note, employee in rows:
            assert employee.telegram_chat_id is not None
            out = render(note, employee)
            try:
                await bot.send_message(
                    employee.telegram_chat_id,
                    out.text,
                    reply_markup=keyboard(out),
                    disable_notification=False,
                )
                sent += 1
            except TelegramAPIError:
                # Пользователь заблокировал бота и т. п. — не повторяем, лента PWA всё равно есть
                log.exception("Не удалось отправить уведомление %d", note.id)
            note.telegram_sent_at = utcnow()
            await session.commit()
    return sent


async def sender_loop(bot: Bot) -> None:
    while True:
        try:
            await send_pending(bot)
        except Exception:
            log.exception("Ошибка отправки уведомлений")
        await asyncio.sleep(settings.telegram_poll_seconds)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    if not settings.telegram_bot_token:
        log.info("TELEGRAM_BOT_TOKEN не задан — бот выключен, уведомления идут только в PWA")
        await asyncio.Event().wait()
        return

    bot = Bot(settings.telegram_bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    me = await bot.get_me()
    if settings.telegram_bot_username and me.username != settings.telegram_bot_username.lstrip("@"):
        log.warning(
            "TELEGRAM_BOT_USERNAME=%s, а токен от @%s — ссылки привязки будут вести не туда",
            settings.telegram_bot_username,
            me.username,
        )
    dp = Dispatcher()
    dp.include_router(router)
    log.info("Бот @%s запущен", me.username)
    sender = asyncio.create_task(sender_loop(bot))
    try:
        await dp.start_polling(bot, handle_signals=False)
    finally:
        sender.cancel()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
