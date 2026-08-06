import asyncio
import logging
import re
from typing import Set
import requests
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# ====================== НАСТРОЙКИ ======================
BOT_TOKEN = "8677610768:AAHDOe1Xzm-sS_3GnRZvEM38GlQmx7uLJ7c"
ADMIN_ID = 630689571
TARGET_CHAT_ID = 630689571
CHECK_INTERVAL = 30

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ====================== ПАРСИНГ MASHINA.KG ======================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

SEARCH_URLS = [
    "https://www.mashina.kg/search/byd/song-plus/",
    "https://www.mashina.kg/search/kia/sportage/",
    "https://m.mashina.kg/search/byd/song-plus/",
    "https://m.mashina.kg/search/kia/sportage/",
]

def parse_mashina(url: str) -> list:
    """Парсит страницу поиска mashina.kg"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        logger.info(f"Mashina [{url}] → {r.status_code}")
        if r.status_code != 200:
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        ads = []

        # Ищем карточки объявлений (несколько возможных селекторов)
        cards = soup.select("div[class*='listing'], div[class*='car'], a[href*='/details/']")
        
        seen_links = set()
        for card in cards:
            # Ссылка
            link_tag = card if card.name == "a" else card.find("a", href=re.compile(r"/details/"))
            if not link_tag:
                continue
            href = link_tag.get("href", "")
            if "/details/" not in href:
                continue
            if not href.startswith("http"):
                href = "https://www.mashina.kg" + href
            if href in seen_links:
                continue
            seen_links.add(href)

            # Название
            title = link_tag.get_text(strip=True) or card.get_text(strip=True)[:80]
            if not title or len(title) < 5:
                continue

            # Цена
            price_text = ""
            price_tag = card.find(string=re.compile(r"\$|сом|USD", re.I))
            if price_tag:
                price_text = price_tag.strip()
            else:
                # Ищем рядом
                parent = card.parent if card.parent else card
                price_match = re.search(r"(\$?\s*[\d\s]+(?:сом|USD)?)", parent.get_text())
                if price_match:
                    price_text = price_match.group(1).strip()

            # Фильтр по моделям
            text_lower = (title + " " + price_text).lower()
            if not any(x in text_lower for x in ["song plus", "сонг плюс", "sportage", "спортейдж", "спортедж"]):
                # Если ссылка уже с song-plus / sportage — пропускаем фильтр
                if "song-plus" not in href and "sportage" not in href:
                    continue

            ads.append({
                "title": title[:100],
                "price": price_text or "цена не указана",
                "url": href,
                "city": "Бишкек / Кыргызстан"
            })

        logger.info(f"Найдено объявлений на {url}: {len(ads)}")
        return ads

    except Exception as e:
        logger.error(f"Ошибка парсинга {url}: {e}")
        return []

async def send_all_ads():
    all_ads = []
    seen_urls = set()

    for url in SEARCH_URLS:
        ads = parse_mashina(url)
        for ad in ads:
            if ad["url"] not in seen_urls:
                seen_urls.add(ad["url"])
                all_ads.append(ad)
        await asyncio.sleep(1)

    total = 0
    for ad in all_ads:
        text = (
            f"<b>{ad['title']}</b>\n"
            f"💰 Цена: {ad['price']}\n"
            f"📍 {ad['city']}\n\n"
            f"<a href='{ad['url']}'>Открыть объявление</a>"
        )
        try:
            await bot.send_message(TARGET_CHAT_ID, text)
            total += 1
            logger.info(f"[SENT] {ad['title'][:60]}")
            await asyncio.sleep(0.8)
        except Exception as e:
            logger.error(f"Ошибка отправки: {e}")

    logger.info(f"Всего отправлено: {total}")
    return total

# ====================== ФОНОВАЯ ЗАДАЧА ======================

async def monitoring_loop():
    logger.info("Мониторинг mashina.kg запущен (каждые 30 сек)")
    while True:
        try:
            await send_all_ads()
        except Exception as e:
            logger.error(f"Ошибка цикла: {e}")
        await asyncio.sleep(CHECK_INTERVAL)

# ====================== КОМАНДЫ ======================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Бот работает на mashina.kg\nКаждые 30 сек кидает все объявления.")

@dp.message(Command("check"))
async def cmd_check(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Собираю объявления с mashina.kg...")
    sent = await send_all_ads()
    await message.answer(f"Отправлено: <b>{sent}</b>")

# ====================== ЗАПУСК ======================

async def main():
    try:
        await bot.send_message(TARGET_CHAT_ID, "Здравствуйте сер рад служить")
    except Exception as e:
        logger.error(f"Приветствие: {e}")

    asyncio.create_task(monitoring_loop())
    logger.info("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())