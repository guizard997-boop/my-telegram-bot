import os
import time
import json
import re
import statistics
import requests
from datetime import datetime

# ================== CONFIG ==================
BOT_TOKEN = "8677610768:AAHDOe1Xzm-sS_3GnRZvEM38GlQmx7uLJ7c"
CHAT_ID = "8569472160"

CHECK_INTERVAL = 45
CITY_ID = 103184
# Реальные категории легковых на Lalafo.kg (1501 больше не отдаёт авто)
CAR_CATEGORY_IDS = [1608, 1557, 1570, 1581, 1572, 1559, 1576]
FEED_QUERIES = [
    "toyota", "toyota camry", "lexus", "honda", "hyundai", "kia",
    "bmw", "mercedes", "nissan", "mazda", "subaru", "volkswagen",
]
SEEN_FILE = "seen_ads_lalafo.json"
USD_KGS_RATE = 87.5

# REAL_SELL → BUY (скупка ниже реальной продажи, не ниже «хотелок»)
REAL_SELL_PERCENTILE = 30
WHOLESALE_MARGIN_PCT = 0.30
WHOLESALE_MARGIN_HIGH_LIQ = 0.27
WHOLESALE_MARGIN_LOW_LIQ = 0.35

MIN_PROFIT = 1000
MIN_DISCOUNT_VS_REAL_SELL = 0.22
MIN_SIMILAR_LISTINGS = 4
MIN_YEAR = 2008
STAGE1_MIN_DISCOUNT = 0.12
MIN_SCORE = 60

MIN_PRICE_USD = 3500
MAX_PRICE_USD = 80000
HEARTBEAT_EVERY = 40  # циклов (~30 мин) — чтобы было видно, что бот жив

URGENT_BOOST_KEYWORDS = [
    "срочно", "торг", "уступлю", "сегодня", "торг реальному",
    "нужны деньги", "быстро продам", "цена снижена",
]

KNOWN_MAKES = {
    "toyota", "lexus", "honda", "nissan", "hyundai", "kia", "bmw", "mercedes",
    "mercedes-benz", "audi", "volkswagen", "vw", "ford", "chevrolet", "mazda",
    "subaru", "mitsubishi", "suzuki", "opel", "skoda", "renault", "peugeot",
    "citroen", "volvo", "land rover", "range rover", "jeep", "infiniti",
    "acura", "genesis", "ssangyong", "daewoo", "geely", "chery", "haval",
    "byd", "porsche", "mini", "lada", "ваз",
}

HIGH_LIQUIDITY = {
    ("toyota", "camry"), ("toyota", "corolla"), ("toyota", "rav4"),
    ("toyota", "prado"), ("toyota", "highlander"), ("toyota", "land"),
    ("lexus", "rx"), ("lexus", "gx"), ("lexus", "es"), ("lexus", "lx"),
    ("honda", "cr"), ("honda", "accord"), ("honda", "fit"),
    ("hyundai", "tucson"), ("hyundai", "sonata"), ("hyundai", "elantra"),
    ("kia", "sportage"), ("kia", "k5"), ("kia", "sorento"),
    ("bmw", "x5"), ("bmw", "x3"), ("mercedes", "e"), ("mercedes-benz", "e"),
}

MEDIUM_LIQUIDITY_MAKES = {
    "toyota", "lexus", "honda", "nissan", "hyundai", "kia", "bmw",
    "mercedes", "mercedes-benz", "audi", "subaru", "mazda", "volkswagen", "vw",
}

STOP_WORDS = [
    "чехол", "стекло на", "стекло для", "запчаст", "аксессуар",
    "коробка от", "документы на", "ремонт", "услуг", "работаю",
    "разбор", "в разборе", "контрактн", "б/у запчаст",
    "диск", "диски", "бампер", "крыло", "капот", "зеркало",
    "радиатор", "генератор", "стартер", "шины", "резина",
    "магнитола", "фара", "фары", "коврик", "оплетка", "фильтр",
    "аккумулятор", "масло мотор", "аренда", "портер такси",
    "вывоз мусор", "грузчик", "погрузчик",
]

CRITICAL_DAMAGE = [
    "битый", "битая", "битое", "после дтп", "после аварии",
    "аварийный", "не на ходу", "не находу", "на запчасти",
    "распил", "каркас", "конструктор",
]

INSTALLMENT_KEYWORDS = [
    "рассрочк", "первоначальн", "в кредит", "кредит",
    "ежемесячн", "лизинг", "оплата частями", "первый взнос",
]

ORDER_KEYWORDS = [
    "под заказ", "подзаказ", "на заказ", "заказ из", "из китая",
    "из кореи", "из японии", "из оаэ", "из дубая", "из сша",
    "в пути", "едет", "ожидается", "пригон", "с аукциона",
]

NOT_CLEARED = [
    "не растаможен", "не растаможена", "без растаможки",
    "без растамож", "не на учете", "временный учет", "транзит", "без птс",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "device": "pc",
    "language": "ru_RU",
    "country-id": "12",
}

CYRILLIC_MAKE_MAP = {
    "тойота": "toyota", "лексус": "lexus", "хонда": "honda", "ниссан": "nissan",
    "хундай": "hyundai", "хендай": "hyundai", "киа": "kia", "бмв": "bmw",
    "мерседес": "mercedes", "ауди": "audi", "фольксваген": "volkswagen",
    "мазда": "mazda", "субару": "subaru", "мицубиси": "mitsubishi", "камри": "camry",
}

PRICE_FLOORS = {
    ("lexus", "gx"): 40000, ("lexus", "lx"): 45000, ("lexus", "rx"): 18000,
    ("lexus", "es"): 12000, ("toyota", "prado"): 18000, ("toyota", "land"): 22000,
    ("toyota", "camry"): 7000, ("toyota", "highlander"): 15000,
    ("bmw", "x5"): 15000, ("bmw", "x7"): 35000,
    ("mercedes", "g"): 40000, ("mercedes-benz", "g"): 40000,
}


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return {}
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return {str(x): None for x in data}
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def save_seen(seen):
    items = list(seen.items())[-5000:]
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(dict(items), f)


def send_telegram(text, photo_url=None):
    try:
        if photo_url and len(text) <= 1000:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
            data = {
                "chat_id": CHAT_ID,
                "photo": photo_url,
                "caption": text[:1024],
                "parse_mode": "HTML",
            }
        else:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            data = {
                "chat_id": CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            }
        r = requests.post(url, data=data, timeout=15)
        if r.status_code != 200:
            print("Telegram error:", r.text[:250])
            return False
        print("Telegram OK")
        return True
    except Exception as e:
        print("Telegram:", e)
        return False


def text_has(text, words):
    t = (text or "").lower()
    return any(w in t for w in words)


def is_blocked(title, description=""):
    blob = f"{title} {description}"
    return (
        text_has(blob, STOP_WORDS)
        or text_has(blob, CRITICAL_DAMAGE)
        or text_has(blob, INSTALLMENT_KEYWORDS)
        or text_has(blob, ORDER_KEYWORDS)
        or text_has(blob, NOT_CLEARED)
    )


def extract_year(title):
    if not title:
        return None
    m = re.search(r"(20\d{2}|19\d{2})\s*г", title, re.I)
    if m:
        y = int(m.group(1))
        if 1990 <= y <= 2027:
            return y
    m = re.search(r"\b(20\d{2}|19\d{2})\b", title)
    if m:
        y = int(m.group(1))
        if 1990 <= y <= 2027:
            return y
    return None


def extract_make_model(title):
    if not title:
        return None, None
    clean = re.sub(r"[^\w\s\-]", " ", title.lower())
    clean = re.sub(r"\s+", " ", clean).strip()
    clean = re.sub(r"\b(19|20)\d{2}\b", "", clean)
    clean = re.sub(r"\s*г\.?\s*", " ", clean).strip()
    for cyr, lat in CYRILLIC_MAKE_MAP.items():
        clean = re.sub(rf"\b{cyr}\b", lat, clean)
    clean = clean.replace("камри", "camry").replace("гибрид", "hybrid")
    words = clean.split()
    if not words:
        return None, None
    make, model_parts = None, []
    for i, word in enumerate(words):
        if word in KNOWN_MAKES:
            make = word
            model_parts = words[i + 1 : i + 3]
            break
        if i + 1 < len(words):
            two = f"{word} {words[i + 1]}"
            if two in KNOWN_MAKES:
                make = two
                model_parts = words[i + 2 : i + 4]
                break
    if not make and "camry" in clean:
        make = "toyota"
        model_parts = ["camry"] + (["hybrid"] if "hybrid" in clean else [])
    if not make and words:
        make = words[0]
        model_parts = words[1:3]
    model = " ".join(model_parts).strip() if model_parts else None
    return make, model


def extract_mileage(text):
    if not text:
        return None
    for p in [
        r"пробег[:\s]*(\d{1,3}[\s]?000|\d{4,7})\s*(км|km)?",
        r"(\d{1,3}[\s]?\d{3})\s*(км|km)",
        r"(\d+)\s*тыс\.?\s*(км|km)?",
    ]:
        m = re.search(p, (text or "").lower())
        if m:
            raw = re.sub(r"\s+", "", m.group(1))
            try:
                val = int(raw)
                if "тыс" in (m.group(0) or ""):
                    val *= 1000
                if 1000 <= val <= 900000:
                    return val
            except ValueError:
                pass
    return None


def extract_engine(text):
    m = re.search(r"\b([1-6][.,]\d)\s*(л|l)?\b", (text or "").lower())
    return m.group(1).replace(",", ".") if m else None


def extract_fuel(text):
    t = (text or "").lower()
    if any(x in t for x in ["дизел", "diesel", "дизель"]):
        return "diesel"
    if any(x in t for x in ["гибрид", "hybrid"]):
        return "hybrid"
    if any(x in t for x in ["электро", "electric"]):
        return "electric"
    if any(x in t for x in ["бензин", "petrol"]):
        return "petrol"
    return None


def extract_transmission(text):
    t = (text or "").lower()
    if any(x in t for x in ["акпп", "автомат", "automatic", "cvt", "вариатор", "типтроник"]):
        return "auto"
    if any(x in t for x in ["мкпп", "механика", "manual"]):
        return "manual"
    return None


def extract_drive(text):
    t = (text or "").lower()
    if any(x in t for x in ["полный", "4wd", "awd", "4x4"]):
        return "awd"
    if any(x in t for x in ["передний", "fwd"]):
        return "fwd"
    if any(x in t for x in ["задний", "rwd"]):
        return "rwd"
    return None


def extract_body(text):
    t = (text or "").lower()
    for k, v in [
        ("седан", "sedan"), ("хетч", "hatch"), ("хэтч", "hatch"),
        ("универсал", "wagon"), ("внедорожник", "suv"), ("кроссовер", "suv"),
        ("минивэн", "mpv"), ("пикап", "pickup"), ("купе", "coupe"),
    ]:
        if k in t:
            return v
    return None


def price_to_usd(ad):
    price = ad.get("price")
    if price is None:
        return None
    try:
        price = float(price)
    except (ValueError, TypeError):
        return None
    currency = (ad.get("currency") or "").upper().strip()
    symbol = (ad.get("symbol") or "").upper().strip()
    if currency in ("USD", "$") or symbol in ("$", "USD"):
        usd = price
    elif currency in ("KGS", "COM", "СОМ", "SOM") or symbol in ("COM", "С", "СОМ", "SOM"):
        usd = price / USD_KGS_RATE
    else:
        usd = price / USD_KGS_RATE if price >= 80000 else price
    if usd < 1500 or usd > 120000:
        return None
    return round(usd)


def normalize(ad):
    title = ad.get("title") or ""
    desc = ad.get("description") or ""
    blob = f"{title} {desc}"
    make, model = extract_make_model(title)
    return {
        "id": ad.get("id"),
        "title": title,
        "description": desc,
        "make": make,
        "model": model,
        "year": extract_year(title),
        "engine": extract_engine(blob),
        "fuel": extract_fuel(blob),
        "transmission": extract_transmission(blob),
        "drive": extract_drive(blob),
        "body": extract_body(blob),
        "mileage": extract_mileage(blob),
        "price_usd": price_to_usd(ad),
        "url": ad.get("url") or "",
        "city": (ad.get("city") or {}).get("name") if isinstance(ad.get("city"), dict) else (ad.get("city") or "Бишкек"),
        "images": ad.get("images"),
        "category_id": ad.get("category_id"),
        "raw": ad,
    }


def looks_like_car(title):
    t = title or ""
    if not extract_year(t):
        return False
    make, _ = extract_make_model(t)
    if not make:
        return False
    # типичный формат Lalafo: "Toyota Camry: 2019 г., 2.5 л,..."
    if ":" in t and re.search(r"20\d{2}|19\d{2}", t):
        return True
    if make in KNOWN_MAKES:
        return True
    return False


def has_urgent_marker(title, description=""):
    return text_has(f"{title} {description}", URGENT_BOOST_KEYWORDS)


def sane_min_price(make, model, year=None):
    make = (make or "").lower()
    model = (model or "").lower()
    first = model.split()[0] if model else ""
    floor = MIN_PRICE_USD
    for (m, tok), f in PRICE_FLOORS.items():
        if make == m and (tok in model or first == tok or tok in first):
            floor = max(floor, f)
            break
    if year and year >= 2022 and floor >= 15000:
        floor = int(floor * 1.35)
    elif year and year >= 2018 and floor >= 15000:
        floor = int(floor * 1.15)
    return floor


def get_liquidity_margin_pct(make, model):
    make = (make or "").lower()
    model = (model or "").lower()
    first = model.split()[0] if model else ""
    for hm, hmod in HIGH_LIQUIDITY:
        if make == hm and (hmod in model or first.startswith(hmod) or hmod in first):
            return WHOLESALE_MARGIN_HIGH_LIQ, "высокая"
    if make in MEDIUM_LIQUIDITY_MAKES:
        return WHOLESALE_MARGIN_PCT, "средняя"
    return WHOLESALE_MARGIN_LOW_LIQ, "низкая"


def get_ads(page=1, q=None, per_page=40, category_id=None):
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
            timeout=20,
        )
        if r.status_code == 200:
            return r.json().get("items") or []
        print(f"Lalafo HTTP {r.status_code}: {r.text[:120]}")
    except Exception as e:
        print("Lalafo error:", e)
    return []


def fetch_feed():
    """Лента только реальных авто: категории + запросы по маркам."""
    raw = []
    for cid in CAR_CATEGORY_IDS:
        raw += get_ads(page=1, per_page=30, category_id=cid)
    for q in FEED_QUERIES:
        raw += get_ads(page=1, per_page=20, q=q)

    seen_ids = set()
    cars = []
    for ad in raw:
        aid = ad.get("id")
        if not aid or aid in seen_ids:
            continue
        seen_ids.add(aid)
        title = ad.get("title") or ""
        desc = ad.get("description") or ""
        if is_blocked(title, desc):
            continue
        if not looks_like_car(title):
            continue
        if not price_to_usd(ad):
            continue
        cars.append(ad)
    print(f"Лента авто: {len(cars)} из {len(raw)} сырых")
    return cars


def similar_match(target, cand):
    if not target.get("make") or not cand.get("make"):
        return False
    if target["make"] != cand["make"]:
        return False
    t_m = (target.get("model") or "").split()
    c_m = (cand.get("model") or "").split()
    if t_m and c_m and t_m[0] != c_m[0]:
        return False
    ty, cy = target.get("year"), cand.get("year")
    if ty and cy and abs(ty - cy) > 1:
        return False
    for key in ("fuel", "body"):
        tv, cv = target.get(key), cand.get(key)
        if tv and cv and tv != cv:
            return False
    return True


def remove_outliers(prices):
    if len(prices) < 4:
        return prices
    med = statistics.median(prices)
    cleaned = [p for p in prices if med * 0.50 <= p <= med * 1.25]
    return cleaned if len(cleaned) >= min(3, MIN_SIMILAR_LISTINGS) else prices


def percentile(data, percent):
    if not data:
        return None
    s = sorted(data)
    n = len(s)
    idx = (n - 1) * percent / 100.0
    f = int(idx)
    c = min(f + 1, n - 1)
    if f == c:
        return s[f]
    return s[f] * (c - idx) + s[c] * (idx - f)


def calc_price_levels(prices):
    cleaned = remove_outliers(prices)
    if len(cleaned) < MIN_SIMILAR_LISTINGS:
        return None, None, cleaned
    ask_median = statistics.median(cleaned)
    real_sell = percentile(cleaned, REAL_SELL_PERCENTILE)
    if real_sell is None:
        return None, None, cleaned
    if real_sell > ask_median:
        real_sell = ask_median * 0.92
    half = sorted(cleaned)[: max(3, len(cleaned) // 2)]
    if half:
        real_sell = min(real_sell, statistics.median(half))
    return ask_median, round(real_sell), cleaned


def find_similar_prices(car):
    make, model, year = car.get("make"), car.get("model"), car.get("year")
    if not make:
        return []
    query = make
    if model:
        query += " " + model.split()[0]
    if make == "toyota" and model and "camry" in model:
        query = "toyota camry"
        if car.get("fuel") == "hybrid":
            query += " hybrid"

    items = get_ads(q=query, per_page=50)
    items += get_ads(page=2, q=query, per_page=40)
    prices = []
    for item in items:
        if is_blocked(item.get("title") or "", item.get("description") or ""):
            continue
        c = normalize(item)
        if not c["price_usd"] or not c["year"]:
            continue
        if str(c["id"]) == str(car.get("id")):
            continue
        if c["price_usd"] < MIN_PRICE_USD or c["price_usd"] > MAX_PRICE_USD:
            continue
        if year and abs(c["year"] - year) > 1:
            continue
        if not similar_match(car, c):
            continue
        prices.append(c["price_usd"])
    return remove_outliers(prices)


def stage1_rough_reject(car):
    """Быстрый отсев явно рыночных цен."""
    make, model = car.get("make"), car.get("model")
    listing = car.get("price_usd")
    if not make or not listing:
        return True
    query = make + ((" " + model.split()[0]) if model else "")
    items = get_ads(q=query, per_page=25)
    prices = []
    for item in items:
        if is_blocked(item.get("title") or "", item.get("description") or ""):
            continue
        p = price_to_usd(item)
        if p and MIN_PRICE_USD <= p <= MAX_PRICE_USD:
            prices.append(p)
    if len(prices) < 3:
        return False  # мало данных — не отсекаем на stage1
    prices = sorted(prices)
    low = statistics.median(prices[: max(2, len(prices) // 2)])
    if low <= 0:
        return True
    disc = (low - listing) / low
    return disc < STAGE1_MIN_DISCOUNT


def deal_score(discount, potential_profit, n_similar, liq_label, urgent=False):
    score = 0.0
    score += min(50, max(0, discount * 100 * 1.5))
    if potential_profit >= 2500:
        score += 25
    elif potential_profit >= 1500:
        score += 18
    elif potential_profit >= 1000:
        score += 12
    elif potential_profit >= MIN_PROFIT:
        score += 6
    else:
        score -= 8
    if n_similar >= 8:
        score += 8
    elif n_similar >= MIN_SIMILAR_LISTINGS:
        score += 4
    if liq_label == "высокая":
        score += 8
    elif liq_label == "низкая":
        score -= 8
    if urgent:
        score += 4
    return int(max(0, min(100, round(score))))


def score_fires(discount, potential_profit):
    if discount >= 0.30 and potential_profit >= 1500:
        return "🔥🔥🔥"
    if discount >= 0.24 and potential_profit >= 1000:
        return "🔥🔥"
    return "🔥"


def analyze(ad, seen):
    ad_id = str(ad.get("id") or "")
    if not ad_id:
        return False

    title = ad.get("title") or ""
    description = ad.get("description") or ""

    if is_blocked(title, description):
        seen[ad_id] = price_to_usd(ad)
        return False

    car = normalize(ad)
    listing = car["price_usd"]

    if not listing or not car["make"] or not car["year"]:
        seen[ad_id] = listing
        return False
    if car["year"] < MIN_YEAR:
        seen[ad_id] = listing
        return False
    if listing < MIN_PRICE_USD or listing > MAX_PRICE_USD:
        seen[ad_id] = listing
        return False

    floor = sane_min_price(car["make"], car["model"], car["year"])
    if listing < floor:
        print(f"  skip floor ${listing}<${floor}: {title[:40]}")
        seen[ad_id] = listing
        return False

    if ad_id in seen and seen[ad_id] is not None and seen[ad_id] == listing:
        return False

    if stage1_rough_reject(car):
        print(f"  stage1 market-price: {title[:40]} | ${listing}")
        seen[ad_id] = listing
        return False

    similar = find_similar_prices(car)
    if len(similar) < MIN_SIMILAR_LISTINGS:
        print(f"  skip analogs={len(similar)}: {title[:40]}")
        seen[ad_id] = listing
        return False

    ask_median, real_sell, cleaned = calc_price_levels(similar)
    if not real_sell or not ask_median:
        print(f"  skip no real_sell: {title[:40]}")
        seen[ad_id] = listing
        return False

    # близко к хотелкам = обычная продажа
    if listing >= ask_median * 0.95:
        print(f"  skip near-ask ${listing}~${ask_median}: {title[:40]}")
        seen[ad_id] = listing
        return False

    if listing < real_sell * 0.45:
        print(f"  skip suspicious ${listing} vs real ${real_sell}: {title[:40]}")
        seen[ad_id] = listing
        return False

    margin_pct, liq_label = get_liquidity_margin_pct(car["make"], car["model"])
    buy_price = round(real_sell * (1 - margin_pct))
    discount = (real_sell - listing) / real_sell if real_sell else 0
    potential_profit = real_sell - listing

    if listing >= buy_price:
        print(f"  skip >=BUY ${listing}>=${buy_price} (real ${real_sell}): {title[:35]}")
        seen[ad_id] = listing
        return False
    if discount < MIN_DISCOUNT_VS_REAL_SELL:
        print(f"  skip disc {discount*100:.0f}%: {title[:40]}")
        seen[ad_id] = listing
        return False
    if potential_profit < MIN_PROFIT:
        print(f"  skip profit ${potential_profit:.0f}: {title[:40]}")
        seen[ad_id] = listing
        return False

    urgent = has_urgent_marker(title, description)
    score = deal_score(discount, potential_profit, len(cleaned), liq_label, urgent)
    if score < MIN_SCORE:
        print(f"  skip score {score}: {title[:40]}")
        seen[ad_id] = listing
        return False

    fires = score_fires(discount, potential_profit)
    url = "https://lalafo.kg" + (car["url"] or "")
    photo = None
    if car.get("images"):
        img0 = car["images"][0]
        photo = img0.get("original_url") or img0.get("thumbnail_url")

    urgent_mark = "⚡ " if urgent else ""
    text = (
        f"🚨 <b>СКУПКА</b> {fires}\n\n"
        f"{urgent_mark}<b>{title}</b>\n"
        f"Источник: Lalafo\n"
        f"Цена: <b>${listing:,.0f}</b>\n"
        f"Хотелки (медиана): ~${ask_median:,.0f}\n"
        f"Реал. продажа: ~${real_sell:,.0f}\n"
        f"Цена скупки: ≤${buy_price:,.0f}\n"
        f"Запас: ~${potential_profit:,.0f}\n"
        f"Оценка: {fires} ({score}/100)\n"
        f"<a href='{url}'>Ссылка</a>"
    )
    send_telegram(text, photo)
    print(f"[{datetime.now()}] SEND {fires} {score} | {title[:45]} | ${listing}")
    seen[ad_id] = listing
    return True


def main():
    print("Бот СКУПКА Lalafo запущен...")
    ok = send_telegram(
        "🎩 <b>Господин Дияр, бот Lalafo перезапущен и работает.</b>\n"
        "Ищет реальную скупку (ниже реальной продажи, не «хотелок»)."
    )
    if not ok:
        print("ВНИМАНИЕ: Telegram не отправил стартовое сообщение — проверь токен/chat_id")

    seen = load_seen()
    print(f"seen={len(seen)} | wholesale={WHOLESALE_MARGIN_PCT*100:.0f}% of REAL_SELL")
    cycles = 0
    sent_total = 0

    while True:
        try:
            cycles += 1
            print(f"\n[{datetime.now()}] цикл {cycles} | Lalafo...")
            ads = fetch_feed()
            sent_now = 0
            for ad in ads:
                try:
                    if analyze(ad, seen):
                        sent_now += 1
                        sent_total += 1
                except Exception as e:
                    print("analyze err:", e)
            save_seen(seen)
            print(f"Цикл OK: проверено {len(ads)}, отправлено {sent_now}, всего {sent_total}")

            if cycles % HEARTBEAT_EVERY == 0:
                send_telegram(
                    f"💓 Бот жив. Циклов: {cycles}, отправлено скупки: {sent_total}, "
                    f"в памяти: {len(seen)}"
                )

            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print("Ошибка цикла:", e)
            time.sleep(25)


if __name__ == "__main__":
    main()
