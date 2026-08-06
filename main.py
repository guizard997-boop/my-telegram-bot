import asyncio
import logging
import os
import re
from typing import Dict, Any, Set
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from fuzzywuzzy import fuzz

# ====================== НАСТРОЙКИ ======================
BOT_TOKEN = "8677610768:AAHDOe1Xzm-sS_3GnRZvEM38GlQmx7uLJ7c"
ADMIN_ID = 630689571
TARGET_CHAT_ID = 630689571
EXCHANGE_RATE = 87.5
CHECK_INTERVAL = 70  # секунд между проверками

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Уже отправленные объявления (чтобы не дублировать)
seen_ids: Set[int] = set()

# ====================== ФИЛЬТР ======================

ALLOWED_MODELS = [
    "byd song plus", "byd song+", "бид сонг плюс", "бид сонг+",
    "бйд сонг плюс", "song plus", "сонг плюс", "songplus", "сонгплюс",
    "kia sportage", "киа спортейдж", "киа спортедж", "киа sportage",
    "sportage", "спортейдж", "спортедж",
]

def is_allowed_car(title: str, description: str = "") -> bool:
    text = f"{title} {description}".lower()

    exact_patterns = [
        r"byd\s*song\s*plus", r"byd\s*song\s*\+", r"бид\s*сонг\s*плюс",
        r"бид\s*сонг\s*\+", r"бйд\s*сонг\s*плюс", r"song\s*plus",
        r"сонг\s*плюс", r"songplus", r"сонгплюс",
        r"kia\s*sportage", r"киа\s*спортейдж", r"киа\s*спортедж",
        r"киа\s*sportage", r"sportage", r"спортейдж", r"спортедж",
    ]
    for pattern in exact_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True

    for model in ALLOWED_MODELS:
        if fuzz.partial_ratio(model, text) >= 82:
            return True
    return False

# ====================== ПАРСИНГ LALAFO ======================

def fetch_lalafo(query: str) -> list:
    """Получаем объявления с Lalafo по запросу"""
    url = "https://lalafo.kg/api/search/v3/feed/search"
    params = {
        "expand": "url",
        "per-page": 40,
        "q": query,
        "city_id": 103184,  # Бишкек
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }

    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data.get("items", [])
    except Exception as e:
        logger.error(f"Ошибка парсинга Lalafo ({query}): {e}")
        return []

async def check_new_ads():
    """Проверяем новые объявления"""
    queries = ["BYD Song Plus", "Kia Sportage", "БИД Сонг Плюс", "Киа Спортейдж"]

    for query in queries:
        items = fetch_lalafo(query)
        for item in items:
            ad_id = item.get("id")
            if not ad_id or ad_id in seen_ids:
                continue

            title = item.get("title", "")
            description = item.get("description", "") or ""
            price = item.get("price")
            city = item.get("city", "Бишкек")
            url = "https://lalafo.kg" + item.get("url", "") if item.get("url") else ""

            if not is_allowed_car(title, description):
                continue

            # Формируем цену
            try:
                price_num = float(price) if price else 0
                price_text = f"{price_num:,.0f} сом (\~{price_num / EXCHANGE_RATE:.0f}$)"
            except:
                price_text = str(price) if price else "не указана"

            text = (
                f"<b>{title}</b>\n"
                f"💰 Цена: {price_text}\n"
                f"📍 {city}"
            )
            if url:
                text += f"\n\n<a href='{url}'>Открыть объявление</a>"

            try:
                await bot.send_message(TARGET_CHAT_ID, text)
                seen_ids.add(ad_id)
                logger.info(f"[SENT] {title[:60]}")
            except Exception as e:
                logger.error(f"Ошибка отправки: {e}")

        await asyncio.sleep(1)  # небольшая пауза между запросами

# ====================== ФОНОВАЯ ЗАДАЧА ======================

async def monitoring_loop():
    logger.info("Мониторинг Lalafo запущен")
    while True:
        try:
            await check_new_ads()
        except Exception as e:
            logger.error(f"Ошибка в цикле мониторинга: {e}")
        await asyncio.sleep(CHECK_INTERVAL)

# ====================== КОМАНДЫ ======================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(
        "Бот работает.\n"
        "Ищет: <b>BYD Song Plus</b> и <b>Kia Sportage</b>\n"
        f"Проверка каждые {CHECK_INTERVAL} сек."
    )

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(f"Отправлено уникальных объявлений: <b>{len(seen_ids)}</b>")

# ====================== ЗАПУСК ======================

async def main():
    # Запускаем мониторинг в фоне
    asyncio.create_task(monitoring_loop())
    logger.info("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())