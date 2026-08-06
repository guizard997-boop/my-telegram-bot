import asyncio
import re
import logging
from typing import Dict, Any
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ====================== ФИЛЬТР ======================

ALLOWED_MODELS = [
    "byd song plus",
    "byd song+",
    "бид сонг плюс",
    "бид сонг+",
    "бйд сонг плюс",
    "song plus",
    "сонг плюс",
    "songplus",
    "сонгплюс",
    "kia sportage",
    "киа спортейдж",
    "киа спортедж",
    "киа sportage",
    "sportage",
    "спортейдж",
    "спортедж",
]

def is_allowed_car(ad: Dict[str, Any]) -> bool:
    title = (ad.get("title") or ad.get("name") or "").lower()
    description = (ad.get("description") or ad.get("text") or "").lower()
    text = f"{title} {description}"

    # Точное совпадение
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

    # Нечёткий поиск
    for model in ALLOWED_MODELS:
        if fuzz.partial_ratio(model, text) >= 80:
            return True

    return False

# ====================== ОТПРАВКА ======================

async def process_and_send(ad: Dict[str, Any]):
    if not is_allowed_car(ad):
        return

    title = ad.get("title") or ad.get("name") or "Без названия"
    city = ad.get("city") or "Бишкек"
    link = ad.get("url") or ad.get("link") or ""

    # Цена
    raw_price = ad.get("price") or ad.get("seller_price") or 0
    try:
        price = float(str(raw_price).replace(" ", "").replace(",", "."))
        price_text = f"{price:,.0f} сом (\~{price / EXCHANGE_RATE:.0f}$)"
    except:
        price_text = str(raw_price)

    text = (
        f"<b>{title}</b>\n"
        f"💰 Цена: {price_text}\n"
        f"📍 {city}"
    )

    if link:
        text += f"\n\n<a href='{link}'>Открыть объявление</a>"

    try:
        await bot.send_message(TARGET_CHAT_ID, text)
        logger.info(f"[SENT] {title[:60]}")
    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")

# ====================== КОМАНДЫ ======================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Бот запущен.\nИщет только: <b>BYD Song Plus</b> и <b>Kia Sportage</b>")

@dp.message(Command("test"))
async def cmd_test(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    test_ads = [
        {"title": "BYD Song Plus 2023", "price": 2500000},
        {"title": "Киа Спортейдж 2021", "price": 1800000},
        {"title": "Лямбда зонд Toyota", "price": 3500},
        {"title": "Kia Sportage полный", "price": 2100000},
        {"title": "Бид Сонг Плюс гибрид", "price": 2700000},
        {"title": "Обшивка багажника Lexus", "price": 15000},
    ]

    results = []
    for ad in test_ads:
        ok = is_allowed_car(ad)
        results.append(f"{'✅' if ok else '❌'} {ad['title']}")

    await message.answer("<b>Тест фильтра:</b>\n\n" + "\n".join(results))

# ====================== ЗАПУСК ======================

async def main():
    logger.info("Бот запущен. Ищет только BYD Song Plus и Kia Sportage")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())