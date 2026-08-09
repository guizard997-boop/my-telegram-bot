import os
import time
import json
import re
import statistics
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# ================== НАСТРОЙКИ ==================
BOT_TOKEN = "8677610768:AAHDOe1Xzm-sS_3GnRZvEM38GlQmx7uLJ7c"
CHAT_ID = "8569472160"

CHECK_INTERVAL = 90                  # секунд между проверками
MIN_YEAR = 1990
WHOLESALE_MARGIN = 0.20              # 20% скидка для скупки
MIN_DISCOUNT_TO_NOTIFY = 0.15        # минимальная скидка для уведомления
MIN_SIMILAR_ADS = 5
CITY_ID = 103184                     # Бишкек
SEEN_FILE = "seen_ads.json"
USD_KGS_RATE = 87.5

# Источники (можно убрать ненужные)
ENABLED_SOURCES = ["lalafo", "mashina", "bazar"]

KNOWN_MAKES = {
    "toyota", "lexus", "honda", "nissan", "hyundai", "kia", "bmw", "mercedes",
    "mercedes-benz", "audi", "volkswagen", "vw", "ford", "chevrolet", "mazda",
    "subaru", "mitsubishi", "suzuki", "opel", "skoda", "renault", "peugeot",
    "citroen", "volvo", "land rover", "range rover", "jeep", "dodge", "chrysler",
    "infiniti", "acura", "genesis", "ssangyong", "daewoo", "ravon", "geely",
    "chery", "haval", "great wall", "byd", "tesla", "porsche", "mini", "daihatsu",
    "ваз", "lada", "уаз", "газ"
}

JUNK_KEYWORDS = [
    "ремонт", "запчаст", "диск", "диски", "ремень", "турбина", "двигатель",
    "коробка", "акпп", "мкпп", "бампер", "крыло", "дверь", "капот",
    "стекло", "зеркало", "подшипник", "сайлент", "амортизатор", "стойка",
    "радиатор", "генератор", "стартер", "компрессор", "кондиционер",
    "шины", "резина", "колесо", "колпак", "ключ", "замок",
    "сигнализация", "магнитола", "камера", "парктроник", "услуг", "работа",
    "разбор", "контрактн", "б/у запчаст", "продаю запчаст", "в разборе",
    "фара", "фары", "передняя фара", "задняя фара", "стоп", "стопы",
    "стоп-сигнал", "стоп сигнал", "задний стоп", "передний стоп",
    "фонарь", "фонари", "поворотник", "поворотники"
]

INSTALLMENT_KEYWORDS = [
    "рассрочк", "рассрочка", "первоначальн", "первоначальный взнос",
    "взнос", "в кредит", "кредит", "ежемесячн", "платеж", "платёж",
    "лизинг", "в месяц", "по месяц", "оплата частями", "частями",
    "первый взнос", "перв. взнос", "пв ", " пв", "0-0-24", "0-0-12",
    "без первоначального", "без взноса"
]

ORDER_KEYWORDS = [
    "под заказ", "подзаказ", "на заказ", "заказ из", "заказать",
    "из китая", "из кореи", "из японии", "из оаэ", "из дубая",
    "из сша", "из америки", "из европы", "в пути", "едет",
    "ожидается", "ожидание", "прибудет", "приход", "доставка из",
    "пригон", "пригнать", "привезу", "привезем", "можно заказать",
    "заказной", "на заказ из", "авто из китая", "авто из кореи",
    "авто из японии", "авто из сша", "с аукциона", "copart", "iaai", "manheim"
]

NOT_CLEARED_KEYWORDS = [
    "не растаможен", "не растаможена", "не растаможено",
    "без растаможки", "без растамож", "не растаможенная",
    "не на учете", "не стоит на учете", "на учете не стоит",
    "временный учет", "временный учёт", "транзит",
    "не оформлен", "не оформлена", "без птс", "без учёта",
    "на транзите", "транзитные номера", "временные номера"
]

URGENT_KEYWORDS = [
    "срочно", "срочная продажа", "срочно продаю", "срочн",
    "цена снижена", "снизил цену", "торг реальному", "торг уместен",
    "ниже рынка", "отдам дешево", "отдам дёшево", "быстро продам",
    "нужны деньги", "срочный выкуп", "сегодня", "только сегодня"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

LALAFO_HEADERS = {
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
    try:
        recent = list(seen)[-4000:]
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(recent, f)
    except Exception as e:
        print("Не удалось сохранить seen:", e)


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
            print("Telegram error:", r.text[:300])
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


def extract_make_model(title):
    if not title:
        return None, None

    clean = re.sub(r"[^\w\s\-]", " ", title.lower())
    clean = re.sub(r"\s+", " ", clean).strip()
    clean = re.sub(r"\b(19|20)\d{2}\b", "", clean)
    clean = re.sub(r"\s*г\.?\s*", " ", clean).strip()

    words = clean.split()
    if not words:
        return None, None

    make = None
    model_parts = []

    for i, word in enumerate(words):
        if word in KNOWN_MAKES:
            make = word
            model_parts = words[i+1:i+3]
            break
        if i + 1 < len(words):
            two = f"{word} {words[i+1]}"
            if two in KNOWN_MAKES:
                make = two
                model_parts = words[i+2:i+4]
                break

    if not make and words:
        make = words[0]
        model_parts = words[1:3]

    model = " ".join(model_parts).strip() if model_parts else None
    return make, model


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
    return any(word in text for word in INSTALLMENT_KEYWORDS)


def is_order_car(title, description=""):
    text = (title + " " + (description or "")).lower()
    return any(word in text for word in ORDER_KEYWORDS)


def is_not_cleared(title, description=""):
    text = (title + " " + (description or "")).lower()
    return any(word in text for word in NOT_CLEARED_KEYWORDS)


def is_urgent(title, description=""):
    text = (title + " " + (description or "")).lower()
    return any(word in text for word in URGENT_KEYWORDS)


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

    is_usd = currency in ("USD", "\( ") or symbol in (" \)", "USD")
    is_kgs = currency in ("KGS", "COM", "СОМ", "SOM") or symbol in ("COM", "С", "СОМ", "SOM")

    if is_usd:
        usd = price
    elif is_kgs:
        usd = price / USD_KGS_RATE
    else:
        usd = price / USD_KGS_RATE if price > 5000 else price

    if is_kgs and 3500 <= price <= 65000:
        usd = price

    if usd is None or usd < 1500 or usd > 90000:
        return None

    if is_kgs and price < 80000 and not (3500 <= price <= 65000):
        return None

    return round(usd)


def get_lalafo_ads(page=1, q=None, per_page=40, year_from=None, year_to=None):
    params = {
        "per-page": per_page,
        "page": page,
        "expand": "url",
        "sort_by": "newest",
        "city_id": CITY_ID,
        "category_id": 1501,
    }
    if q:
        params["q"] = q
    if year_from:
        params["parameters[62][from]"] = year_from
    if year_to:
        params["parameters[62][to]"] = year_to

    try:
        r = requests.get(
            "https://api.lalafo.com/v3/ads/search",
            params=params,
            headers=LALAFO_HEADERS,
            timeout=20
        )
        if r.status_code == 200:
            items = r.json().get("items", [])
            result = []
            for item in items:
                result.append({
                    "id": f"lalafo_{item.get('id')}",
                    "source": "Lalafo.kg",
                    "title": item.get("title") or "",
                    "description": item.get("description") or "",
                    "price": item.get("price"),
                    "currency": item.get("currency"),
                    "symbol": item.get("symbol"),
                    "url": "https://lalafo.kg" + (item.get("url") or ""),
                    "city": item.get("city") or "Бишкек",
                    "images": item.get("images") or [],
                })
            return result
    except Exception as e:
        print("Ошибка Lalafo:", e)
    return []


def get_mashina_ads(limit=25):
    ads = []
    try:
        urls = [
            "https://m.mashina.kg/search/all?sort=new",
            "https://www.mashina.kg/search/all/?sort=new",
        ]
        for url in urls:
            try:
                r = requests.get(url, headers=HEADERS, timeout=15)
                if r.status_code != 200:
                    continue
                soup = BeautifulSoup(r.text, "html.parser")
                cards = soup.select("a[href*='/details/']")
                seen_ids = set()
                for card in cards:
                    try:
                        href = card.get("href") or ""
                        if "/details/" not in href:
                            continue
                        full_url = urljoin("https://www.mashina.kg", href)
                        ad_id = href.strip("/").split("/")[-1]
                        if ad_id in seen_ids:
                            continue
                        seen_ids.add(ad_id)

                        title = card.get_text(strip=True)
                        if not title or len(title) < 8:
                            continue

                        ads.append({
                            "id": f"mashina_{ad_id}",
                            "source": "Mashina.kg",
                            "title": title[:200],
                            "description": "",
                            "price": None,
                            "currency": "USD",
                            "symbol": "$",
                            "url": full_url,
                            "city": "Бишкек",
                            "images": [],
                        })
                        if len(ads) >= limit:
                            break
                    except Exception:
                        continue
                if ads:
                    break
            except Exception as e:
                print(f"Mashina error: {e}")
    except Exception as e:
        print("Ошибка Mashina.kg:", e)
    print(f"[Mashina] найдено: {len(ads)}")
    return ads


def get_bazar_ads(limit=25):
    ads = []
    try:
        url = "https://www.bazar.kg/index.php/kyrgyzstan/transport/legkovye-avtomobili"
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.find_all("a", href=re.compile(r"/details/"))
        seen = set()
        for card in cards:
            try:
                href = card.get("href", "")
                if "/details/" not in href:
                    continue
                full_url = urljoin("https://www.bazar.kg", href)
                ad_id = href.strip("/").split("/")[-1].split("?")[0]
                if ad_id in seen:
                    continue
                seen.add(ad_id)

                title = card.get_text(strip=True)
                if not title or len(title) < 10:
                    continue

                ads.append({
                    "id": f"bazar_{ad_id}",
                    "source": "Bazar.kg",
                    "title": title[:200],
                    "description": "",
                    "price": None,
                    "currency": "KGS",
                    "symbol": "сом",
                    "url": full_url,
                    "city": "Бишкек",
                    "images": [],
                })
                if len(ads) >= limit:
                    break
            except Exception:
                continue
    except Exception as e:
        print("Ошибка Bazar.kg:", e)
    print(f"[Bazar] найдено: {len(ads)}")
    return ads


def remove_outliers(prices):
    if len(prices) < 5:
        return prices
    med = statistics.median(prices)
    filtered = [p for p in prices if med * 0.45 <= p <= med * 1.35]
    return filtered if len(filtered) >= 4 else prices


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


def get_market_price(make, model, year):
    if not make:
        return None, 0, None

    query = make
    if model:
        first_model = model.split()[0]
        if len(first_model) > 1:
            query += " " + first_model

    year_from = max(year - 3, 1985) if year else None
    year_to = year + 3 if year else None

    items = get_lalafo_ads(q=query, per_page=60, year_from=year_from, year_to=year_to)
    prices = []

    for item in items:
        if is_junk_title(item.get("title", "")):
            continue
        item_year = extract_year(item.get("title", ""))
        if year and item_year and abs(item_year - year) > 3:
            continue
        item_make, _ = extract_make_model(item.get("title", ""))
        if item_make and make and item_make != make and make not in item_make and item_make not in make:
            continue
        price = get_clean_price_usd(item)
        if price and 1500 < price < 90000:
            prices.append(price)

    prices = remove_outliers(prices)
    if len(prices) < MIN_SIMILAR_ADS:
        return None, len(prices), None

    return percentile(prices, 20), len(prices), statistics.median(prices)


def analyze_and_notify(ad, seen):
    ad_id = ad.get("id")
    if ad_id in seen:
        return

    title = ad.get("title") or "Без названия"
    description = ad.get("description") or ""
    source = ad.get("source") or "Неизвестно"

    if is_junk_title(title) or is_installment(title, description) or \
       is_order_car(title, description) or is_not_cleared(title, description):
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

    make, model = extract_make_model(title)
    market_price, count, market_median = get_market_price(make, model, year)

    if not market_price or count < MIN_SIMILAR_ADS:
        seen.add(ad_id)
        return

    asking = price_usd
    wholesale_target = market_price * (1 - WHOLESALE_MARGIN)
    discount = (market_price - asking) / market_price
    potential_profit = market_price - asking

    urgent = is_urgent(title, description)

    is_excellent_deal = (
        discount >= MIN_DISCOUNT_TO_NOTIFY and
        asking <= wholesale_target * 1.08
    )
    if urgent and discount >= 0.12:
        is_excellent_deal = True

    if not is_excellent_deal:
        seen.add(ad_id)
        return

    url = ad.get("url") or ""
    city = ad.get("city") or "Бишкек"
    photo = None
    images = ad.get("images") or []
    if images and isinstance(images[0], dict):
        photo = images[0].get("original_url") or images[0].get("thumbnail_url")

    price_kgs = round(asking * USD_KGS_RATE)
    market_kgs = round(market_price * USD_KGS_RATE)
    wholesale_kgs = round(wholesale_target * USD_KGS_RATE)
    median_kgs = round(market_median * USD_KGS_RATE) if market_median else 0

    urgent_mark = "⚡ <b>СРОЧНО!</b>\n\n" if urgent else ""
    source_icon = {"Lalafo.kg": "🟡", "Mashina.kg": "🔵", "Bazar.kg": "🟢"}.get(source, "⚪")

    text = (
        f"{urgent_mark}"
        f"🔥 <b>ВЫГОДНО ДЛЯ ПЕРЕКУПА</b>\n\n"
        f"<b>{title}</b>\n"
        f"📍 {city}\n"
        f"{source_icon} <b>Источник: {source}</b>\n\n"
        f"💰 <b>Цена продавца:</b> {price_kgs:,.0f} сом  (\~{asking:.0f}$)\n"
        f"📊 <b>Рыночная (20%):</b> \~{market_kgs:,.0f} сом  (\~{market_price:.0f}$)\n"
        f"📈 Медиана: \~{median_kgs:,.0f} сом\n"
        f"🛒 <b>Скупочная цель (−{int(WHOLESALE_MARGIN*100)}%):</b> \~{wholesale_kgs:,.0f} сом  (\~{wholesale_target:.0f}$)\n\n"
        f"📉 Ниже рынка на: <b>{discount*100:.1f}%</b>\n"
        f"💵 Потенциал: <b>\~{potential_profit:.0f}$</b>\n"
        f"🔍 Похожих: {count}\n\n"
        f"<a href='{url}'>Открыть объявление</a>"
    )

    send_telegram(text, photo)
    status = "СРОЧНО" if urgent else "ВЫГОДНО"
    print(f"[{datetime.now()}] 🔥 {status} | {source} | {title[:45]} | −{discount*100:.1f}%")

    seen.add(ad_id)


def main():
    print("=" * 50)
    print("Бот перекупа запущен")
    print(f"Источники: {ENABLED_SOURCES}")
    print("=" * 50)

    send_telegram(
        f"✅ <b>Бот запущен</b>\n\n"
        f"• Источники: {', '.join(ENABLED_SOURCES)}\n"
        f"• В сообщениях видно источник\n"
        f"• Интервал: {CHECK_INTERVAL} сек"
    )

    seen = load_seen()

    while True:
        try:
            print(f"\n[{datetime.now()}] Проверяю объявления...")

            all_ads = []

            if "lalafo" in ENABLED_SOURCES:
                print("→ Lalafo.kg")
                all_ads.extend(get_lalafo_ads(page=1, per_page=50))

            if "mashina" in ENABLED_SOURCES:
                print("→ Mashina.kg")
                all_ads.extend(get_mashina_ads(limit=25))

            if "bazar" in ENABLED_SOURCES:
                print("→ Bazar.kg")
                all_ads.extend(get_bazar_ads(limit=25))

            urgent_ads = [ad for ad in all_ads if is_urgent(ad.get("title", ""), ad.get("description", ""))]
            normal_ads = [ad for ad in all_ads if ad not in urgent_ads]

            print(f"Всего: {len(all_ads)} | Срочных: {len(urgent_ads)}")

            for ad in urgent_ads + normal_ads:
                analyze_and_notify(ad, seen)

            save_seen(seen)
            time.sleep(CHECK_INTERVAL)

        except Exception as e:
            print("Ошибка в цикле:", e)
            time.sleep(30)


if __name__ == "__main__":
    main()