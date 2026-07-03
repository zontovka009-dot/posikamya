# -*- coding: utf-8 -*-
"""
Мини-бот: две кнопки — "🔍 Поиск" и "⬅️ Назад".
Жмёшь "Поиск", пишешь описание картинки — бот ищет в интернете и присылает.

Установка перед запуском:
    pip install aiogram duckduckgo-search --break-system-packages
"""

import asyncio
import logging
import random

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from duckduckgo_search import DDGS

BOT_TOKEN = "ВСТАВЬ_СЮДА_ТОКЕН"

router = Router()


class SearchForm(StatesGroup):
    waiting_query = State()


def main_menu():
    kb = [[KeyboardButton(text="🔍 Поиск")], [KeyboardButton(text="⬅️ Назад")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Привет! Жми «Поиск» и опиши, что найти.", reply_markup=main_menu())


@router.message(F.text == "⬅️ Назад")
async def go_back(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Ок, жду команду.", reply_markup=main_menu())


@router.message(F.text == "🔍 Поиск")
async def search_start(message: Message, state: FSMContext):
    await state.set_state(SearchForm.waiting_query)
    await message.answer("Опиши картинку, которую нужно найти:", reply_markup=main_menu())


@router.message(SearchForm.waiting_query)
async def search_do(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.clear()
        await message.answer("Ок, жду команду.", reply_markup=main_menu())
        return

    query = message.text
    wait_msg = await message.answer("Ищу... 🔎")

    try:
        with DDGS() as ddgs:
            results = list(ddgs.images(query, max_results=10))
    except Exception as e:
        await wait_msg.edit_text(f"Не удалось выполнить поиск: {e}")
        return

    if not results:
        await wait_msg.edit_text("Ничего не нашлось, попробуй описать иначе.")
        return

    random.shuffle(results)
    sent = False
    for item in results:
        image_url = item.get("image")
        if not image_url:
            continue
        try:
            await message.answer_photo(image_url, caption=f"По запросу: {query}")
            sent = True
            break
        except Exception:
            continue  # если конкретная ссылка не грузится — пробуем следующую

    await wait_msg.delete()
    if not sent:
        await message.answer("Нашёл ссылки, но ни одна картинка не загрузилась. Попробуй другой запрос.")

    await state.clear()


async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
