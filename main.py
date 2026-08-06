import asyncio
import logging
import re
from typing import Set
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
CHECK_INTERVAL = 60

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

seen_ids: Set[int] = set()
first_run = True

# ====================== ФИЛЬТР ======================

def is_allowed_car(title: str, description: str = "") -> bool:
    text = f"{title} {description}".lower()

    keywords = [
        "song plus", "сонг плюс", "songplus", "сонгплюс",
        "sportage", "спортейдж", "спортедж"
    ]
    for kw in keywords:
        if kw in text:
            return True

    # fuzzy на всякий случай
    for model in ["byd song plus", "киа спортейдж", "kia sportage"]:
        if fuzz.partial_ratio(model, text) >= 78:
            return True
    return False

# ====================== ПАРСИНГ ======================

def fetch_lalafo(query: str) -> list:
    url = "https://lalafo.kg/api/search/v3/feed/search"
    params = {
        "expand": "url",
        "per-page": 50,
        "q": query,
        "sort_by": "newest",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        "Origin": "https://lalafo.kg",
        "Referer": "https://lalafo.kg/",
    }
    try:
        r = requests.get(url, params=params, headers=headers, timeout=20)
        logger.info(f"Lalafo [{query}] → status {r.status_code}")
        if r.status_code != 200:
            logger.error(f"Ответ: {r.text[:300]}")
            return []
        data = r.json()
        items = data.get("items") or data.get("data", {}).get("items") or []
        logger.info(f"Lalafo [{query}] → найдено {len(items)} объявлений")
        return items
    except Exception as e:
        logger.error(f"Ошибка Lalafo ({query}): {e}")
        return []

async def check_new_ads(force_send: bool = False):
    global first_run
    queries = ["BYD Song Plus", "Kia Sportage", "БИД Сонг Плюс", "Киа Спортейдж", "Song Plus", "Спортейдж"]

    total_found = 0
    total_new = 0

    for query in queries:
        items = fetch_lalafo(query)
        for item in items:
            ad_id = item.get("id")
            if not ad_id:
                continue

            title = item.get("title") or ""
            description = item.get("description") or ""
            price = item.get("price")
            city = item.get("city") or item.get("city_name") or "Бишкек"
            url_path = item.get("url") or ""
            url = f"https://lalafo.kg{url_path}" if url_path.startswith("/") else url_path

            if not is_allowed_car(title, description):
                continue

            total_found += 1

            if ad_id in seen_ids and not force_send:
                continue

            # Первый запуск — только запоминаем
            if first_run and not force_send:
                seen_ids.add(ad_id)
                continue

            # Отправляем
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
                total_new += 1
                logger.info(f"[SENT] {title[:70]}")
            except Exception as e:
                logger.error(f"Ошибка отправки: {e}")

        await asyncio.sleep(1.5)

    if first_run and not force_send:
        first_run = False
        logger.info(f"Первый запуск завершён. Запомнено: {len(seen_ids)}")

    return total_found, total_new

# ====================== ФОНОВАЯ ЗАДАЧА ======================

async def monitoring_loop():
    logger.info("Мониторинг запущен")
    while True:
        try:
            found, new = await check_new_ads()
            logger.info(f"Проверка: найдено подходящих {found}, новых отправлено {new}")
        except Exception as e:
            logger.error(f"Ошибка цикла: {e}")
        await asyncio.sleep(CHECK_INTERVAL)

# ====================== КОМАНДЫ ======================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Бот работает.\nИщет BYD Song Plus и Kia Sportage")

@dp.message(Command("check"))
async def cmd_check(message: types.Message):
    """Принудительная проверка + отправка"""
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Проверяю Lalafo...")
    found, new = await check_new_ads(force_send=True)
    await message.answer(f"Найдено подходящих: <b>{found}</b>\nОтправлено новых: <b>{new}</b>")

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(f"В памяти объявлений: <b>{len(seen_ids)}</b>\nПервый запуск: <b>{first_run}</b>")

# ====================== ЗАПУСК ======================

async def main():
    try:
        await bot.send_message(TARGET_CHAT_ID, "Здравствуйте сер рад служить")
    except Exception as e:
        logger.error(f"Приветствие не отправилось: {e}")

    asyncio.create_task(monitoring_loop())
    logger.info("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())