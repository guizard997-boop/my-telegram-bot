import os
import time
import json
import re
import statistics
import requests
from datetime import datetime

# ================== НАСТРОЙКИ ==================
BOT_TOKEN = "8677610768:AAHDOe1Xzm-sS_3GnRZvEM38GlQmx7uLJ7c"
CHAT_ID = "630689571"

CHECK_INTERVAL = 30          # каждые 30 секунд
MIN_YEAR = 2015
MIN_DISCOUNT_TO_NOTIFY = 0.08  # уже 8% ниже рынка — кидает
MIN_SIMILAR_ADS = 3
CITY_ID = 103184
SEEN_FILE = "seen_ads.json"
USD_KGS_RATE = 87.5

# Только эти марки
ALLOWED_MAKES = {"byd", "kia"}

# Категории машин на Lalafo
CAR_CATEGORIES = [1576, 1543]  # обычные авто + электро/BYD

JUNK_KEYWORDS = [
    "ремонт", "запчаст", "запчасти", "диск", "диски", "ремень", "турбина",
    "двигатель", "мотор", "коробка", "акпп", "мкпп", "бампер", "крыло",
    "дверь", "капот", "стекло", "зеркало", "подшипник", "сайлент",
    "амортизатор", "стойка", "радиатор", "генератор", "стартер",
    "компрессор", "кондиционер", "шины", "резина", "колесо", "колпак",
    "ключ", "замок", "сигнализация", "магнитола", "камера", "парктроник",
    "услуг", "работа", "разбор", "контрактн", "б/у запчаст", "в разборе",
    "фара", "фары", "стоп", "стопы", "фонарь", "поворотник", "оптика",
    "лямбда", "гбц", "головка блока", "поршень", "клапан", "форсунка",
    "насос", "термостат", "обшивка", "сиденье", "кресло", "руль",
    "крышка багажника", "катализатор", "глушитель", "сцепление",
    "ступица", "рычаг", "шаровая", "наконечник", "тяга", "пружина",
    "трапеция", "решетка", "решётка", "дворник"
]

INSTALLMENT_KEYWORDS = [
    "рассрочк", "рассрочка", "первоначальн", "взнос", "в кредит", "кредит",
    "ежемесячн", "платеж", "платёж", "лизинг", "в месяц", "частями",
    "первый взнос", "пв ", "0-0-24", "0-0-12", "без первоначального"
]

ORDER_KEYWORDS = [
    "под заказ", "подзаказ", "на заказ", "заказ из", "заказать",
    "из китая", "из кореи", "из японии", "из оаэ", "из дубая",
    "из сша", "из америки", "из европы", "в пути", "едет",
    "ожидается", "прибудет", "доставка из", "пригон", "пригнать",
    "можно заказать", "с аукциона", "copart", "iaai", "manheim"
]

NOT_CLEARED_KEYWORDS = [
    "не растаможен", "не растаможена", "не растаможено",
    "без растаможки", "без растамож", "не на учете", "не стоит на учете",
    "временный учет", "временный учёт", "транзит", "не оформлен",
    "без птс", "на транзите", "транзитные номера"
]

URGENT_KEYWORDS = [
    "срочно", "срочная продажа", "срочно продаю", "срочн",
    "цена снижена", "снизил цену", "торг реальному", "ниже рынка",
    "отдам дешево", "отдам дёшево", "быстро продам", "нужны деньги"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "device": "pc",
    "language": "ru_RU",
    "country-id": "12",
}

# ================================================

def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data) if isinstance(data, list) else set()
        except Exception:
            return set()
    return set()


def save_seen(seen):
    recent = list(seen)[-4000:]
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(recent, f)


def send_telegram(text, photo_url=None):
    try:
        if photo_url:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
            data = {
                "chat_id": CHAT_ID,
                "photo": photo_url,
                "caption": text[:1024],
                "parse_mode": "HTML"
            }
        else:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            data = {
                "chat_id": CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False
            }
        r = requests.post(url, data=data, timeout=15)
        if r.status_code != 200:
            print("Telegram error:", r.text[:200])
    except Exception as e:
        print("Ошибка отправки в Telegram:", e)


def extract_year(title):
    if not title:
        return None
    match = re.search(r"(20\d{2}|19\d{2})\s*г", title, re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"\b(20\d{2}|19\d{2})\b", title)
    if match:
        return int(match.group(1))
    return None


def extract_make(title):
    if not title:
        return None
    clean = re.sub(r"[^\w\s\-]", " ", title.lower())
    clean = re.sub(r"\s+", " ", clean).strip()
    words = clean.split()
    for word in words:
        if word in ALLOWED_MAKES:
            return word
    return None


def is_junk_title(title):
    if not title:
        return True
    title_lower = title.lower()
    for word in JUNK_KEYWORDS:
        if word in title_lower:
            return True
    return False


def is_installment(title, description=""):
    text = (title + " " + (description or "")).lower()
    return any(w in text for w in INSTALLMENT_KEYWORDS)


def is_order_car(title, description=""):
    text = (title + " " + (description or "")).lower()
    return any(w in text for w in ORDER_KEYWORDS)


def is_not_cleared(title, description=""):
    text = (title + " " + (description or "")).lower()
    return any(w in text for w in NOT_CLEARED_KEYWORDS)


def is_urgent(title, description=""):
    text = (title + " " + (description or "")).lower()
    return any(w in text for w in URGENT_KEYWORDS)


def get_clean_price_usd(ad):
    price = ad.get("price")
    if price is None:
        return None
    try:
        price = float(price)
    except (ValueError, TypeError):
        return None

    currency = (ad.get("currency") or "").upper().strip()
    symbol = (ad.get("symbol") or "").upper().strip()

    is_usd = currency in ("USD",) or symbol in ("$", "USD")
    is_kgs = currency in ("KGS", "COM", "СОМ") or symbol in ("COM", "С", "СОМ")

    if is_usd:
        usd = price
    elif is_kgs:
        # иногда цену в сомах пишут как "15000" имея в виду доллары
        if 3000 <= price <= 80000:
            usd = price
        else:
            usd = price / USD_KGS_RATE
    else:
        usd = price if price < 100000 else price / USD_KGS_RATE

    if usd is None or usd < 2000 or usd > 120000:
        return None
    return round(usd)


def get_ads(page=1, q=None, category_id=None, per_page=40):
    params = {
        "per-page": per_page,
        "page": page,
        "expand": "url",
        "sort_by": "newest",
        "city_id": CITY_ID,
    }
    if category_id:
        params["category_id"] = category_id
    if q:
        params["q"] = q

    try:
        r = requests.get(
            "https://api.lalafo.com/v3/ads/search",
            params=params,
            headers=HEADERS,
            timeout=20
        )
        if r.status_code == 200:
            return r.json().get("items", [])
    except Exception as e:
        print("Ошибка запроса к Lalafo:", e)
    return []


def remove_outliers(prices):
    if len(prices) < 4:
        return prices
    med = statistics.median(prices)
    filtered = [p for p in prices if med * 0.5 <= p <= med * 1.4]
    return filtered if len(filtered) >= 3 else prices


def percentile(data, percent):
    if not data:
        return None
    size = len(data)
    sorted_data = sorted(data)
    index = (size - 1) * percent / 100
    floor = int(index)
    ceil = min(floor + 1, size - 1)
    if floor == ceil:
        return sorted_data[floor]
    return sorted_data[floor] * (ceil - index) + sorted_data[ceil] * (index - floor)


def get_market_price(make, year):
    if not make:
        return None, 0, None

    items = get_ads(q=make, per_page=50)
    prices = []

    for item in items:
        if is_junk_title(item.get("title", "")):
            continue
        item_make = extract_make(item.get("title", ""))
        if item_make != make:
            continue
        item_year = extract_year(item.get("title", ""))
        if year and item_year and abs(item_year - year) > 4:
            continue
        price = get_clean_price_usd(item)
        if price and 2000 < price < 120000:
            prices.append(price)

    prices = remove_outliers(prices)
    if len(prices) < MIN_SIMILAR_ADS:
        return None, len(prices), None

    market_hard = percentile(prices, 25)
    market_median = statistics.median(prices)
    return market_hard, len(prices), market_median


def analyze_and_notify(ad, seen):
    ad_id = ad.get("id")
    if ad_id in seen:
        return

    title = ad.get("title") or "Без названия"
    description = ad.get("description") or ""

    make = extract_make(title)
    if make not in ALLOWED_MAKES:
        seen.add(ad_id)
        return

    if is_junk_title(title):
        seen.add(ad_id)
        return
    if is_installment(title, description):
        seen.add(ad_id)
        return
    if is_order_car(title, description):
        seen.add(ad_id)
        return
    if is_not_cleared(title, description):
        seen.add(ad_id)
        return

    year = extract_year(title)
    if year is None or year < MIN_YEAR:
        seen.add(ad_id)
        return

    price_usd = get_clean_price_usd(ad)
    if not price_usd:
        seen.add(ad_id)
        return

    market_price, count, market_median = get_market_price(make, year)

    # Если рынок не посчитался — всё равно кидаем (чтобы хоть что-то шло)
    if market_price and count >= MIN_SIMILAR_ADS:
        discount = (market_price - price_usd) / market_price
        if discount < MIN_DISCOUNT_TO_NOTIFY and not is_urgent(title, description):
            seen.add(ad_id)
            return
        potential_profit = market_price - price_usd
    else:
        discount = 0
        potential_profit = 0
        market_price = None
        market_median = None

    url = "https://lalafo.kg" + (ad.get("url") or "")
    city = ad.get("city") or "Бишкек"
    photo = None
    if ad.get("images"):
        photo = ad["images"][0].get("original_url") or ad["images"][0].get("thumbnail_url")

    price_kgs = round(price_usd * USD_KGS_RATE)
    urgent = is_urgent(title, description)
    urgent_mark = "⚡ <b>СРОЧНО!</b>\n\n" if urgent else ""

    if market_price:
        market_kgs = round(market_price * USD_KGS_RATE)
        median_kgs = round(market_median * USD_KGS_RATE) if market_median else 0
        text = (
            f"{urgent_mark}"
            f"🔥 <b>{make.upper()}</b>\n\n"
            f"<b>{title}</b>\n"
            f"📍 {city}\n\n"
            f"💰 <b>Цена:</b> {price_kgs:,.0f} сом  (\~{price_usd}$)\n"
            f"📊 <b>Рынок (25%):</b> \~{market_kgs:,.0f} сом  (\~{market_price}$)\n"
            f"📈 Медиана: \~{median_kgs:,.0f} сом\n"
            f"📉 Ниже рынка: <b>{discount*100:.1f}%</b>\n"
            f"💵 Потенциал: <b>\~{potential_profit:.0f}$</b>\n"
            f"🔍 Похожих: {count}\n\n"
            f"<a href='{url}'>Открыть объявление</a>"
        )
    else:
        text = (
            f"{urgent_mark}"
            f"🔥 <b>{make.upper()}</b>\n\n"
            f"<b>{title}</b>\n"
            f"📍 {city}\n\n"
            f"💰 <b>Цена:</b> {price_kgs:,.0f} сом  (\~{price_usd}$)\n"
            f"📊 Рынок пока не посчитался\n\n"
            f"<a href='{url}'>Открыть объявление</a>"
        )

    send_telegram(text, photo)
    print(f"[{datetime.now()}] 🔥 {make.upper()} | {title[:50]} | {price_usd}$")
    seen.add(ad_id)


def main():
    print("Бот BYD + Kia запущен (каждые 30 сек)...")
    send_telegram(
        "✅ <b>Бот обновлён</b>\n\n"
        "• Только <b>BYD</b> и <b>Kia</b>\n"
        "• Проверка каждые 30 секунд\n"
        "• Категории машин исправлены\n"
        "• Запчасти / рассрочка / под заказ / нерастаможенные — отсекаются"
    )

    seen = load_seen()

    while True:
        try:
            print(f"[{datetime.now()}] Проверяю BYD + Kia...")
            all_ads = []

            # Ищем по брендам + по категориям
            for q in ["byd", "kia"]:
                ads = get_ads(q=q, per_page=30)
                all_ads.extend(ads)

            for cat in CAR_CATEGORIES:
                ads = get_ads(category_id=cat, per_page=25)
                all_ads.extend(ads)

            # Убираем дубли
            unique = {}
            for ad in all_ads:
                unique[ad.get("id")] = ad
            ads = list(unique.values())

            # Сначала срочные
            urgent_ads = []
            normal_ads = []
            for ad in ads:
                title = ad.get("title") or ""
                desc = ad.get("description") or ""
                if is_urgent(title, desc):
                    urgent_ads.append(ad)
                else:
                    normal_ads.append(ad)

            for ad in urgent_ads + normal_ads:
                analyze_and_notify(ad, seen)

            save_seen(seen)
            time.sleep(CHECK_INTERVAL)

        except Exception as e:
            print("Ошибка в основном цикле:", e)
            time.sleep(20)


if __name__ == "__main__":
    main()