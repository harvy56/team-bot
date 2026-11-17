
import os
import asyncio
import html
import sqlite3

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 7914331846

SUPPORT = "hatk1d"
DISCORD = "https://discord.gg/Wqyuhk4Jn"

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not configured")

bot = Bot(TOKEN)
dp = Dispatcher(storage=MemoryStorage())


class Form(StatesGroup):
    cheat = State()
    nickname = State()
    age = State()
    timezone = State()


def menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Подать заявку в Тиму")],
            [KeyboardButton(text="Связаться с поддержкой")]
        ],
        resize_keyboard=True
    )


def decisions():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Принять",
            callback_data="accept"
        )],
        [InlineKeyboardButton(
            text="❌ Отклонить",
            callback_data="reject"
        )]
    ])


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет! Добро пожаловать в нашу Тиму!",
        reply_markup=menu()
    )


@dp.message(F.text == "Связаться с поддержкой")
async def support(message: Message):
    await message.answer(f"Поддержка: https://t.me/{SUPPORT}")


@dp.message(F.text == "Подать заявку в Тиму")
async def apply(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Form.cheat)
    await message.answer("1/4. С каким читом ты играешь?")


@dp.message(Form.cheat)
async def cheat(message: Message, state: FSMContext):
    await state.update_data(cheat=message.text or "")
    await state.set_state(Form.nickname)
    await message.answer("2/4. Напиши свой игровой ник:")


@dp.message(Form.nickname)
async def nickname(message: Message, state: FSMContext):
    await state.update_data(nickname=message.text or "")
    await state.set_state(Form.age)
    await message.answer("3/4. Сколько тебе лет?")


@dp.message(Form.age)
async def age(message: Message, state: FSMContext):
    value = (message.text or "").strip()
    if not value.isdigit() or not 1 <= int(value) <= 99:
        await message.answer("Напиши возраст числом.")
        return
    await state.update_data(age=value)
    await state.set_state(Form.timezone)
    await message.answer("4/4. Напиши часовой пояс (например UTC+3):")


@dp.message(Form.timezone)
async def timezone(message: Message, state: FSMContext):
    await state.update_data(timezone=message.text or "")
    data = await state.get_data()
    user = message.from_user

    text = (
        "📝 <b>Новая заявка в Тиму</b>\n\n"
        f"Telegram: @{html.escape(user.username or 'нет')}\n"
        f"ID: <code>{user.id}</code>\n"
        f"Чит: {html.escape(data['cheat'])}\n"
        f"Ник: {html.escape(data['nickname'])}\n"
        f"Возраст: {html.escape(data['age'])}\n"
        f"Часовой пояс: {html.escape(data['timezone'])}"
    )

    sent = await bot.send_message(
        ADMIN_ID, text,
        parse_mode="HTML",
        reply_markup=decisions()
    )

    with sqlite3.connect("applications.db") as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                message_id INTEGER PRIMARY KEY,
                user_id INTEGER,
                status TEXT DEFAULT 'pending'
            )
        """)
        db.execute(
            "INSERT INTO applications (message_id, user_id) VALUES (?, ?)",
            (sent.message_id, user.id)
        )

    await state.clear()
    await message.answer(
        "✅ Заявка отправлена! Ожидай решения.",
        reply_markup=menu()
    )


async def decision(callback: CallbackQuery, accepted: bool):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Это действие только для администратора.", show_alert=True)
        return

    if not callback.message:
        return

    with sqlite3.connect("applications.db") as db:
        row = db.execute(
            "SELECT user_id, status FROM applications WHERE message_id=?",
            (callback.message.message_id,)
        ).fetchone()

        if not row or row[1] != "pending":
            await callback.answer("Заявка уже обработана.")
            return

        db.execute(
            "UPDATE applications SET status=? WHERE message_id=?",
            ("accepted" if accepted else "rejected",
             callback.message.message_id)
        )

    user_id = row[0]

    if accepted:
        await bot.send_message(
            user_id,
            "🎉 Твоя заявка принята!\nDiscord: " + DISCORD
        )
    else:
        await bot.send_message(
            user_id,
            "К сожалению, твоя заявка отклонена."
        )

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Готово!")


@dp.callback_query(F.data == "accept")
async def accept(callback: CallbackQuery):
    await decision(callback, True)


@dp.callback_query(F.data == "reject")
async def reject(callback: CallbackQuery):
    await decision(callback, False)


async def main():
    async with bot:
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
  
