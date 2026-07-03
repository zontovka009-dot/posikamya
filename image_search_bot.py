# -*- coding: utf-8 -*-
"""
Мини-бот: две кнопки — "🔍 Поиск" и "⬅️ Назад".
Жмёшь "Поиск", пишешь описание картинки — бот ищет в интернете и присылает 3 штуки.

Зависимости: только aiogram и aiohttp (aiohttp обычно и так ставится вместе
с aiogram, отдельного пакета для поиска картинок больше не нужно).

Установка перед запуском:
    pip install aiogram aiohttp --break-system-packages
"""

import asyncio
import json
import logging
import random

import aiohttp
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

BOT_TOKEN = "8367142448:AAGvcZ24lUbFOy0ZOTLdLg2aHqJMA-lOmpY"
RESULTS_TO_SEND = 3

router = Router()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}


class SearchForm(StatesGroup):
    waiting_query = State()


def main_menu():
    kb = [[KeyboardButton(text="🔍 Поиск")], [KeyboardButton(text="⬅️ Назад")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


# ==================== ИСТОЧНИК 1: Openverse (CC-лицензированные картинки) ====================

async def fetch_openverse(session: aiohttp.ClientSession, query: str, limit: int = 20):
    try:
        async with session.get(
            "https://api.openverse.engineering/v1/images/",
            params={"q": query, "page_size": limit},
        ) as resp:
            if resp.status != 200:
                return []
            data = await resp.json(content_type=None)
            return [item.get("url") for item in data.get("results", []) if item.get("url")]
    except Exception:
        return []


# ==================== ИСТОЧНИК 2: Wikimedia Commons (гораздо шире база) ====================

async def fetch_wikimedia(session: aiohttp.ClientSession, query: str, limit: int = 20):
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrnamespace": "6",
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url",
    }
    try:
        async with session.get(
            "https://commons.wikimedia.org/w/api.php", params=params
        ) as resp:
            if resp.status != 200:
                return []
            data = await resp.json(content_type=None)
            pages = data.get("query", {}).get("pages", {})
            urls = []
            for page in pages.values():
                info = page.get("imageinfo")
                if info:
                    url = info[0].get("url")
                    if url:
                        urls.append(url)
            return urls
    except Exception:
        return []


async def search_images(query: str):
    """
    Ищет одновременно по двум источникам и объединяет результаты,
    чтобы почти на любой запрос что-то находилось.
    """
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        openverse_urls, wikimedia_urls = await asyncio.gather(
            fetch_openverse(session, query),
            fetch_wikimedia(session, query),
        )

    all_urls = openverse_urls + wikimedia_urls
    seen = set()
    unique_urls = []
    for url in all_urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)

    random.shuffle(unique_urls)
    return unique_urls


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
        candidates = await search_images(query)
    except Exception as e:
        await wait_msg.edit_text(f"Не удалось выполнить поиск: {e}")
        return

    if not candidates:
        await wait_msg.edit_text("Ничего не нашлось, попробуй описать иначе.")
        return

    sent_count = 0
    for image_url in candidates:
        if sent_count >= RESULTS_TO_SEND:
            break
        try:
            await message.answer_photo(image_url, caption=f"По запросу: {query}")
            sent_count += 1
        except Exception:
            continue  # если конкретная ссылка не грузится — пробуем следующую

    await wait_msg.delete()
    if sent_count == 0:
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
