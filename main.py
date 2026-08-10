import json
import os
import re
import statistics
import time
from datetime import datetime
import requests

# ================== НАСТРОЙКИ ==================
BOT_TOKEN = "8677610768:AAHDOe1Xzm-sS_3GnRZvEM38GlQmx7uLJ7c"
CHAT_ID = "8569472160"

# ИИ (опционально)
AI_API_KEY = "ВСТАВЬ_СВОЙ_КЛЮЧ_СЮДА"
AI_BASE_URL = "https://api.openai.com/v1"
AI_MODEL = "gpt-4o-mini"

CHECK_INTERVAL = 45
MIN_YEAR = 2005
CITY_ID = 103184
SEEN_FILE = "seen_ads.json"
USD_KGS_RATE = 87.5

# ---- ЭКОНОМИКА СКУПКИ (главное) ----
EXPENSES_USD = 250  # оформление, мелкий ремонт, объявления, бензин
NEGOTIATION_RESERVE = 0.04  # 4% — запас на торг при перепродаже
REQUIRED_PROFIT_USD = 600  # стандартная желаемая чистая прибыль

# Настройки для СВЕРХЛИКВИДА (Camry 70 Hybrid)
CAMRY_REQUIRED_PROFIT_USD = 400  # сниженный порог прибыли, так как уходит за пару часов

MIN_PROFIT_RATIO = 0.06  # хотя бы ~6% от цены быстрой продажи

# Рыночная «быстрая продажа» = консервативный низ нормального рынка
QUICK_SELL_PERCENTILE = 22  # 22-й перцентиль очищенных аналогов
MIN_COMPARABLES = 5  # меньше — не считаем MAX_BUY уверенно
YEAR_TOLERANCE = 1
MILEAGE_TOLERANCE = 0.30  # ±30%

KNOWN_MAKES = {
    "toyota",
    "lexus",
    "honda",
    "nissan",
    "hyundai",
    "kia",
    "bmw",
    "mercedes",
    "mercedes-benz",
    "audi",
    "volkswagen",
    "vw",
    "ford",
    "chevrolet",
    "mazda",
    "subaru",
    "mitsubishi",
    "suzuki",
    "opel",
    "skoda",
    "renault",
    "peugeot",
    "citroen",
    "volvo",
    "land rover",
    "range rover",
    "jeep",
    "dodge",
    "chrysler",
    "infiniti",
    "acura",
    "genesis",
    "ssangyong",
    "daewoo",
    "ravon",
    "geely",
    "chery",
    "haval",
    "great wall",
    "byd",
    "tesla",
    "porsche",
    "mini",
    "daihatsu",
    "lifan",
    "faw",
    "uaz",
    "lada",
    "ваз",
}

JUNK_KEYWORDS = [
    "ремонт",
    "запчаст",
    "диск",
    "диски",
    "ремень",
    "турбина",
    "двигатель",
    "коробка",
    "акпп",
    "мкпп",
    "бампер",
    "крыло",
    "дверь",
    "капот",
    "стекло",
    "зеркало",
    "подшипник",
    "сайлент",
    "амортизатор",
    "стойка",
    "радиатор",
    "генератор",
    "стартер",
    "компрессор",
    "кондиционер",
    "шины",
    "резина",
    "колесо",
    "колпак",
    "ключ",
    "замок",
    "сигнализация",
    "магнитола",
    "камера",
    "парктроник",
    "услуг",
    "работа",
    "разбор",
    "контрактн",
    "б/у запчаст",
    "продаю запчаст",
    "в разборе",
    "фара",
    "фары",
    "стоп",
    "стопы",
    "фонарь",
    "поворотник",
]

DAMAGE_KEYWORDS = [
    "битый",
    "битая",
    "битое",
    "бит",
    "после дтп",
    "после аварии",
    "аварийный",
    "аварийная",
    "дтп",
    "не на ходу",
    "не находу",
    "под восстановление",
    "на запчасти",
    "на запчасть",
    "требует ремонта",
    "нужен ремонт",
    "кузовной",
    "после удара",
    "вмятин",
    "скручен",
    "скрутка",
    "некондиция",
    "на разбор",
    "распил",
    "каркас",
    "только на запчасти",
    "конструктор",
    "распилен",
]

INSTALLMENT_KEYWORDS = [
    "рассрочк",
    "рассрочка",
    "первоначальн",
    "первоначальный взнос",
    "взнос",
    "в кредит",
    "кредит",
    "ежемесячн",
    "платеж",
    "платёж",
    "лизинг",
    "в месяц",
    "по месяц",
    "оплата частями",
    "частями",
    "первый взнос",
    "перв. взнос",
    "пв ",
    " пв",
    "0-0-24",
    "0-0-12",
    "без первоначального",
    "без взноса",
]

ORDER_KEYWORDS = [
    "под заказ",
    "подзаказ",
    "на заказ",
    "заказ из",
    "заказать",
    "из китая",
    "из кореи",
    "из японии",
    "из оаэ",
    "из дубая",
    "из сша",
    "из америки",
    "из европы",
    "в пути",
    "едет",
    "ожидается",
    "ожидание",
    "прибудет",
    "приход",
    "доставка из",
    "пригон",
    "пригнать",
    "привезу",
    "привезем",
    "можно заказать",
    "заказной",
    "с аукциона",
    "copart",
    "iaai",
    "manheim",
]

NOT_CLEARED_KEYWORDS = [
    "не растаможен",
    "не растаможена",
    "не растаможено",
    "без растаможки",
    "без растамож",
    "не растаможенная",
    "не на учете",
    "не стоит на учете",
    "на учете не стоит",
    "временный учет",
    "временный учёт",
    "транзит",
    "не оформлен",
    "не оформлена",
    "без птс",
    "без учёта",
    "на транзите",
    "транзитные номера",
    "временные номера",
]

URGENT_KEYWORDS = [
    "срочно",
    "срочная продажа",
    "срочно продаю",
    "срочн",
    "цена снижена",
    "снизил цену",
    "торг реальному",
    "торг уместен",
    "ниже рынка",
    "отдам дешево",
    "отдам дёшево",
    "быстро продам",
    "нужны деньги",
    "срочный выкуп",
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
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen)[-3000:], f)


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
        else:
            print("Telegram OK")
    except Exception as e:
        print("Telegram:", e)


def text_has(text, words):
    t = (text or "").lower()
    return any(w in t for w in words)


def extract_year(title):
    if not title:
        return None
    m = re.search(r"(20\d{2}|19\d{2})\s*г", title, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(20\d{2}|19\d{2})\b", title)
    return int(m.group(1)) if m else None


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
    if not make and words:
        make = words[0]
        model_parts = words[1:3]
    model = " ".join(model_parts).strip() if model_parts else None
    return make, model


def extract_mileage(text):
    if not text:
        return None
    patterns = [
        r"пробег[:\s]*(\d{1,3}[\s]?000|\d{4,7})\s*(км|km)?",
        r"(\d{1,3}[\s]?\d{3})\s*(км|km)",
        r"(\d+)\s*тыс\.?\s*(км|km)?",
    ]
    for p in patterns:
        m = re.search(p, text.lower())
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
    if not text:
        return None
    m = re.search(r"\b([1-6][.,]\d)\s*(л|l|cci|куб)?\b", text.lower())
    if m:
        return m.group(1).replace(",", ".")
    m = re.search(r"\b([1-6]\.\d)\b", text.lower())
    return m.group(1) if m else None


def extract_fuel(text):
    t = (text or "").lower()
    if any(x in t for x in ["дизел", "diesel", "дизель"]):
        return "diesel"
    if any(x in t for x in ["гибрид", "hybrid"]):
        return "hybrid"
    if any(x in t for x in ["электро", "electric", "ev "]):
        return "electric"
    if any(x in t for x in ["бензин", "petrol", "gas"]):
        return "petrol"
    return None


def extract_transmission(text):
    t = (text or "").lower()
    if any(
        x in t
        for x in ["акпп", "автомат", "automatic", "cvt", "вариатор", "робот"]
    ):
        return "auto"
    if any(x in t for x in ["мкпп", "механика", "механич", "manual"]):
        return "manual"
    return None


def extract_drive(text):
    t = (text or "").lower()
    if any(x in t for x in ["полный", "4wd", "awd", "4x4", "полный привод"]):
        return "awd"
    if any(x in t for x in ["передний", "fwd"]):
        return "fwd"
    if any(x in t for x in ["задний", "rwd"]):
        return "rwd"
    return None


def extract_body(text):
    t = (text or "").lower()
    mapping = [
        ("седан", "sedan"),
        ("хетч", "hatch"),
        ("хэтч", "hatch"),
        ("универсал", "wagon"),
        ("внедорожник", "suv"),
        ("кроссовер", "suv"),
        ("suv", "suv"),
        ("минивэн", "mpv"),
        ("минивен", "mpv"),
        ("пикап", "pickup"),
        ("купе", "coupe"),
        ("кабрио", "cabrio"),
    ]
    for k, v in mapping:
        if k in t:
            return v
    return None


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
    if currency in ("USD", "$") or symbol in ("$", "USD"):
        usd = price
    elif currency in ("KGS", "COM", "СОМ", "SOM") or symbol in (
        "COM",
        "С",
        "СОМ",
        "SOM",
    ):
        usd = price / USD_KGS_RATE
    else:
        usd = price / USD_KGS_RATE if price >= 80000 else price
    if usd is None or usd < 1500 or usd > 100000:
        return None
    return round(usd)


def parse_ad_specs(ad):
    title = ad.get("title") or ""
    desc = ad.get("description") or ""
    blob = f"{title} {desc}"
    make, model = extract_make_model(title)
    return {
        "make": make,
        "model": model,
        "year": extract_year(title),
        "mileage": extract_mileage(blob),
        "engine": extract_engine(blob),
        "fuel": extract_fuel(blob),
        "transmission": extract_transmission(blob),
        "drive": extract_drive(blob),
        "body": extract_body(blob),
        "price": get_clean_price_usd(ad),
        "title": title,
        "description": desc,
        "ad": ad,
    }


def is_camry_70_hybrid(specs):
    """Проверка, является ли машина Toyota Camry 70 Hybrid."""
    blob = f"{specs.get('title', '')} {specs.get('description', '')}".lower()

    is_camry = "camry" in blob or "камри" in blob
    if not is_camry:
        return False

    is_hybrid = (
        specs.get("fuel") == "hybrid" or "гибрид" in blob or "hybrid" in blob
    )
    if not is_hybrid:
        return False

    year = specs.get("year")
    # 70 кузов выпускается с late 2017 по 2024
    is_70_year = year and year >= 2017
    is_70_keyword = any(
        k in blob for k in ["70", "v70", "xv70", "75", "v75", "семьдесят"]
    )

    return is_70_year or is_70_keyword


def is_bad_listing(title, description=""):
    blob = f"{title} {description}"
    if text_has(title, JUNK_KEYWORDS):
        return True
    if text_has(blob, DAMAGE_KEYWORDS):
        return True
    if text_has(blob, INSTALLMENT_KEYWORDS):
        return True
    if text_has(blob, ORDER_KEYWORDS):
        return True
    if text_has(blob, NOT_CLEARED_KEYWORDS):
        return True
    return False


def get_ads(page=1, q=None, per_page=50, year_from=None, year_to=None):
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
            headers=HEADERS,
            timeout=15,
        )
        if r.status_code == 200:
            return r.json().get("items", [])
    except Exception as e:
        print("Lalafo error:", e)
    return []


def specs_match(target, cand):
    if not target.get("make") or not cand.get("make"):
        return False
    if (
        target["make"] != cand["make"]
        and target["make"] not in (cand["make"] or "")
        and (cand["make"] or "") not in target["make"]
    ):
        return False

    t_model = (target.get("model") or "").split()
    c_model = (cand.get("model") or "").split()
    if t_model and c_model:
        if t_model[0] != c_model[0]:
            return False
    elif t_model and not c_model:
        return False

    ty, cy = target.get("year"), cand.get("year")
    if ty and cy and abs(ty - cy) > YEAR_TOLERANCE:
        return False
    if ty and not cy:
        return False

    for key in ("engine", "fuel", "transmission", "body", "drive"):
        tv, cv = target.get(key), cand.get(key)
        if tv and cv and tv != cv:
            return False

    tm, cm = target.get("mileage"), cand.get("mileage")
    if tm and cm and tm > 0:
        if abs(cm - tm) / tm > MILEAGE_TOLERANCE:
            return False

    return True


def remove_price_outliers(prices):
    if len(prices) < 4:
        return prices
    med = statistics.median(prices)
    low, high = med * 0.55, med * 1.28
    cleaned = [p for p in prices if low <= p <= high]
    return cleaned if len(cleaned) >= 3 else prices


def percentile(data, percent):
    if not data:
        return None
    s = sorted(data)
    n = len(s)
    idx = (n - 1) * percent / 100
    f, c = int(idx), min(int(idx) + 1, n - 1)
    if f == c:
        return s[f]
    return s[f] * (c - idx) + s[c] * (idx - f)


def calc_real_quick_sell_price(comparable_prices):
    cleaned = remove_price_outliers(comparable_prices)
    if len(cleaned) < MIN_COMPARABLES:
        return None, cleaned
    return percentile(cleaned, QUICK_SELL_PERCENTILE), cleaned


def calc_max_buy_price(quick_sell, required_profit=REQUIRED_PROFIT_USD):
    if not quick_sell or quick_sell <= 0:
        return None
    after_reserve = quick_sell * (1 - NEGOTIATION_RESERVE)
    max_buy = after_reserve - EXPENSES_USD - required_profit
    if (
        quick_sell > 0
        and (quick_sell - max_buy) / quick_sell < MIN_PROFIT_RATIO
    ):
        max_buy = quick_sell * (1 - MIN_PROFIT_RATIO) - EXPENSES_USD
    return max(0, round(max_buy))


def find_comparables(target_specs):
    make = target_specs.get("make")
    model = target_specs.get("model")
    year = target_specs.get("year")
    if not make or not year:
        return []

    query = make
    if model:
        query += " " + model.split()[0]

    year_from = max(year - YEAR_TOLERANCE, 1985)
    year_to = year + YEAR_TOLERANCE

    items = get_ads(q=query, per_page=60, year_from=year_from, year_to=year_to)
    items += get_ads(
        page=2, q=query, per_page=40, year_from=year_from, year_to=year_to
    )

    comps = []
    for item in items:
        if is_bad_listing(
            item.get("title") or "", item.get("description") or ""
        ):
            continue
        sp = parse_ad_specs(item)
        if not sp["price"]:
            continue
        if not specs_match(target_specs, sp):
            continue
        comps.append(sp)
    return comps


def analyze_and_notify(ad, seen):
    ad_id = ad.get("id")
    if ad_id in seen:
        return

    title = ad.get("title") or ""
    description = ad.get("description") or ""

    if is_bad_listing(title, description):
        seen.add(ad_id)
        return

    target = parse_ad_specs(ad)
    if not target["price"] or not target["make"] or not target["year"]:
        seen.add(ad_id)
        return
    if target["year"] < MIN_YEAR:
        seen.add(ad_id)
        return

    # Проверка на приоритет (Camry 70 Hybrid)
    is_camry_70_h = is_camry_70_hybrid(target)
    req_profit = (
        CAMRY_REQUIRED_PROFIT_USD if is_camry_70_h else REQUIRED_PROFIT_USD
    )

    comps = find_comparables(target)
    prices = [c["price"] for c in comps if c.get("price")]

    quick_sell, cleaned = calc_real_quick_sell_price(prices)
    if quick_sell is None:
        print(f"  skip (мало данных): {title[:40]} | comps={len(prices)}")
        seen.add(ad_id)
        return

    max_buy = calc_max_buy_price(quick_sell, required_profit=req_profit)
    if max_buy is None or max_buy <= 0:
        seen.add(ad_id)
        return

    seller = target["price"]

    # ГЛАВНОЕ ПРАВИЛО
    if seller > max_buy:
        print(
            f"  skip (дорого): {title[:35]} | ask={seller}$ max_buy={max_buy}$"
            f" qs={quick_sell:.0f}$"
        )
        seen.add(ad_id)
        return

    # REAL_BUY
    expected_profit = quick_sell - seller - EXPENSES_USD
    margin_pct = (expected_profit / quick_sell * 100) if quick_sell else 0
    urgent = text_has(f"{title} {description}", URGENT_KEYWORDS)

    url = "https://lalafo.kg" + (ad.get("url") or "")
    city = ad.get("city") or "Бишкек"
    photo = None
    if ad.get("images"):
        photo = ad["images"][0].get("original_url") or ad["images"][0].get(
            "thumbnail_url"
        )

    seller_kgs = round(seller * USD_KGS_RATE)
    max_buy_kgs = round(max_buy * USD_KGS_RATE)
    qs_kgs = round(quick_sell * USD_KGS_RATE)

    header = "🎯 <b>СВЕРХЛИКВИД: CAMRY 70 HYBRID</b>\n" if is_camry_70_h else ""
    urgent_mark = "⚡ <b>СРОЧНО</b>\n" if urgent else ""

    text = (
        f"{header}"
        f"{urgent_mark}"
        f"✅ <b>REAL BUY — МОЖНО ЗАБИРАТЬ</b>\n\n"
        f"<b>{title}</b>\n"
        f"📍 {city}\n\n"
        f"💰 <b>Цена продавца:</b> {seller_kgs:,.0f} сом (~{seller}$)\n"
        f"🛒 <b>MAX BUY (твой потолок):</b> {max_buy_kgs:,.0f} сом (~{max_buy}$)\n"
        f"🏷 <b>Быстрая продажа (ориентир):</b> ~{qs_kgs:,.0f} сом (~{quick_sell:.0f}$)\n\n"
        f"📉 Запас до потолка: <b>{max_buy - seller}$</b>\n"
        f"💵 Ожид. прибыль после расходов: <b>~{expected_profit:.0f}$</b> ({margin_pct:.0f}%)\n"
        f"🔧 Расходы заложены: {EXPENSES_USD}$ | резерв торга {int(NEGOTIATION_RESERVE*100)}% | цель прибыли {req_profit}$\n"
        f"🔍 Чистых аналогов: {len(cleaned)} (из {len(prices)})\n\n"
        f"<a href='{url}'>Открыть объявление</a>"
    )

    send_telegram(text, photo)
    print(
        f"[{datetime.now()}] REAL_BUY | {title[:40]} | ask={seller}$"
        f" max={max_buy}$ profit~{expected_profit:.0f}$"
    )
    seen.add(ad_id)


def main():
    print("Бот REAL_BUY / MAX_BUY запущен...")
    send_telegram(
        "🎩 <b>Господин Дияр, ваш бот обновлен и готов к работе.</b>\n\n"
        f"🔥 <b>ВКЛЮЧЕН ПРИОРИТЕТ: Toyota Camry 70 Hybrid</b>\n"
        f"• Алгоритм проводит приоритетный поиск по Камри Гибрид 70\n"
        f"• Порог прибыли для них снижен до ${CAMRY_REQUIRED_PROFIT_USD} (уходят мгновенно)\n"
        f"• Аналоги: марка+модель+год±{YEAR_TOLERANCE}, пробег±{int(MILEAGE_TOLER