import os
import time
import json
import re
import statistics
import requests
from datetime import datetime

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
# MAX_BUY = REAL_QUICK_SELL - EXPENSES - NEGOTIATION_RESERVE - REQUIRED_PROFIT
EXPENSES_USD = 250              # оформление, мелкий ремонт, объявления, бензин
NEGOTIATION_RESERVE = 0.04      # 4% — запас на торг при перепродаже
REQUIRED_PROFIT_USD = 600       # минимальная чистая прибыль, которую хочешь
# Дополнительно: не брать, если запас прибыли < этого %
MIN_PROFIT_RATIO = 0.06         # хотя бы ~6% от цены быстрой продажи

# Рыночная «быстрая продажа» = консервативный низ нормального рынка
QUICK_SELL_PERCENTILE = 22      # 22-й перцентиль очищенных аналогов
MIN_COMPARABLES = 5             # меньше — не считаем MAX_BUY уверенно
YEAR_TOLERANCE = 1
MILEAGE_TOLERANCE = 0.30        # ±30%

# ---- ПРИОРИТЕТНЫЕ МОДЕЛИ ----
# Camry Hybrid 70 (XV70): примерно 2017–2024, ликвид в Бишкеке
# Для них: мягче порог данных и чуть ниже требуемая прибыль
PRIORITY_REQUIRED_PROFIT_USD = 450
PRIORITY_MIN_COMPARABLES = 4
PRIORITY_EXPENSES_USD = 200

KNOWN_MAKES = {
    "toyota", "lexus", "honda", "nissan", "hyundai", "kia", "bmw", "mercedes",
    "mercedes-benz", "audi", "volkswagen", "vw", "ford", "chevrolet", "mazda",
    "subaru", "mitsubishi", "suzuki", "opel", "skoda", "renault", "peugeot",
    "citroen", "volvo", "land rover", "range rover", "jeep", "dodge", "chrysler",
    "infiniti", "acura", "genesis", "ssangyong", "daewoo", "ravon", "geely",
    "chery", "haval", "great wall", "byd", "tesla", "porsche", "mini", "daihatsu",
    "lifan", "faw", "uaz", "lada", "ваз"
}

JUNK_KEYWORDS = [
    "ремонт", "запчаст", "диск", "диски", "ремень", "турбина", "двигатель",
    "коробка", "акпп", "мкпп", "бампер", "крыло", "дверь", "капот",
    "стекло", "зеркало", "подшипник", "сайлент", "амортизатор", "стойка",
    "радиатор", "генератор", "стартер", "компрессор", "кондиционер",
    "шины", "резина", "колесо", "колпак", "ключ", "замок",
    "сигнализация", "магнитола", "камера", "парктроник", "услуг", "работа",
    "разбор", "контрактн", "б/у запчаст", "продаю запчаст", "в разборе",
    "фара", "фары", "стоп", "стопы", "фонарь", "поворотник"
]

DAMAGE_KEYWORDS = [
    "битый", "битая", "битое", "бит", "после дтп", "после аварии",
    "аварийный", "аварийная", "дтп", "не на ходу", "не находу",
    "под восстановление", "на запчасти", "на запчасть", "требует ремонта",
    "нужен ремонт", "кузовной", "после удара", "вмятин",
    "скручен", "скрутка", "некондиция", "на разбор",
    "распил", "каркас", "только на запчасти", "конструктор", "распилен"
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
    "заказной", "с аукциона", "copart", "iaai", "manheim"
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
    "нужны деньги", "срочный выкуп"
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


CYRILLIC_MAKE_MAP = {
    "тойота": "toyota",
    "лексус": "lexus",
    "хонда": "honda",
    "ниссан": "nissan",
    "хундай": "hyundai",
    "хендай": "hyundai",
    "киа": "kia",
    "бмв": "bmw",
    "мерседес": "mercedes",
    "ауди": "audi",
    "фольксваген": "volkswagen",
    "мазда": "mazda",
    "субару": "subaru",
    "мицубиси": "mitsubishi",
    "камри": "camry",  # иногда пишут без марки
}


def extract_make_model(title):
    if not title:
        return None, None
    clean = re.sub(r"[^\w\s\-]", " ", title.lower())
    clean = re.sub(r"\s+", " ", clean).strip()
    clean = re.sub(r"\b(19|20)\d{2}\b", "", clean)
    clean = re.sub(r"\s*г\.?\s*", " ", clean).strip()
    # нормализация кириллицы марок
    for cyr, lat in CYRILLIC_MAKE_MAP.items():
        clean = re.sub(rf"\b{cyr}\b", lat, clean)
    # частые модели
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
    # если в тексте camry, а make не найден — toyota
    if not make and "camry" in clean:
        make = "toyota"
        model_parts = ["camry"]
        if "hybrid" in clean:
            model_parts.append("hybrid")
    if not make and words:
        make = words[0]
        model_parts = words[1:3]
    model = " ".join(model_parts).strip() if model_parts else None
    return make, model


def extract_mileage(text):
    """Пробег в км из текста. None если нет."""
    if not text:
        return None
    t = text.lower().replace(" ", "")
    # 120000км, 120 тыс, 120000 km, пробег: 85 000
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
    """Объём двигателя примерно: 1.6, 2.0, 3.5 и т.д."""
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
    if any(x in t for x in ["гибрид", "hybrid", "hv", "hybrid"] ):
        return "hybrid"
    if any(x in t for x in ["электро", "electric", "ev "]):
        return "electric"
    if any(x in t for x in ["бензин", "petrol", "gas"]):
        return "petrol"
    return None


def is_priority_model(specs, title="", description=""):
    """
    Приоритет: Toyota Camry Hybrid 70 (XV70).
    Годы ~2017–2024, в названии camry/камри + hybrid/гибрид или просто camry 70.
    """
    make = (specs.get("make") or "").lower()
    model = (specs.get("model") or "").lower()
    year = specs.get("year")
    blob = f"{title} {description} {model}".lower()

    if make not in ("toyota",):
        return False
    if year and not (2017 <= year <= 2024):
        return False

    is_camry = ("camry" in blob) or ("камри" in blob) or ("camry" in model) or ("камри" in model)
    is_hybrid = (
        specs.get("fuel") == "hybrid"
        or "hybrid" in blob
        or "гибрид" in blob
        or "гибрид" in model
    )
    is_70 = (
        re.search(r"\b70\b", blob) is not None
        or "xv70" in blob
        or "xv-70" in blob
        or (year is not None and 2017 <= year <= 2024)
    )

    # Camry Hybrid в годах 70-ки — приоритет даже без явной цифры 70
    if is_camry and is_hybrid and year and 2017 <= year <= 2024:
        return True
    if is_camry and is_hybrid and is_70:
        return True
    return False


def extract_transmission(text):
    t = (text or "").lower()
    if any(x in t for x in ["акпп", "автомат", "automatic", "cvt", "вариатор", "робот"]):
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
    elif currency in ("KGS", "COM", "СОМ", "SOM") or symbol in ("COM", "С", "СОМ", "SOM"):
        usd = price / USD_KGS_RATE
    else:
        usd = price / USD_KGS_RATE if price >= 80000 else price
    if usd is None or usd < 1500 or usd > 100000:
        return None
    return round(usd)


def parse_ad_specs(ad):
    """Собрать характеристики объявления для сопоставления."""
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
    """
    Максимально похожие аналоги:
    brand + model + year±1 + (engine/fuel/trans/body/drive если есть) + mileage±30%.
    Обязательны: make, model (базово), year±1.
    Остальное — если указано у обоих, должно совпадать.
    """
    if not target.get("make") or not cand.get("make"):
        return False
    if target["make"] != cand["make"] and target["make"] not in (cand["make"] or "") and (cand["make"] or "") not in target["make"]:
        return False

    # model: хотя бы первое слово модели
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

    # Опциональные поля — только если есть у обоих
    for key in ("engine", "fuel", "transmission", "body", "drive"):
        tv, cv = target.get(key), cand.get(key)
        if tv and cv and tv != cv:
            return False

    tm, cm = target.get("mileage"), cand.get("mileage")
    if tm and cm and tm > 0:
        if abs(cm - tm) / tm > MILEAGE_TOLERANCE:
            return False

    return True



def fetch_mashina_market_prices(make, model, year=None, pages=2):
    """Цены похожих авто с Mashina.kg для общего рынка (вариант B)."""
    if not make:
        return []
    q = make
    if model:
        q += " " + model.split()[0]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }
    prices = []
    for page in range(1, pages + 1):
        url = f"https://www.mashina.kg/search/all/?q={requests.utils.quote(q)}&currency=2&page={page}"
        try:
            r = requests.get(url, headers=headers, timeout=20)
            if r.status_code != 200:
                continue
            html = r.text
            links = list(dict.fromkeys(re.findall(r"/details/([a-z0-9\-]+)", html)))
            raw_prices = re.findall(r"\$[\s\xa0\u00a0]?([\d\s\xa0\u00a0]+)", html)
            parsed = []
            for p in raw_prices:
                digits = re.sub(r"\D", "", p)
                if digits.isdigit():
                    val = int(digits)
                    if 1500 <= val <= 100000:
                        parsed.append(val)
            # парим по порядку: ссылка ~ цена
            make_l = make.lower().replace(" ", "-")
            model_token = (model or "").split()[0].lower() if model else ""
            for i, slug in enumerate(links):
                slug_l = slug.lower()
                if make_l not in slug_l and make.lower() not in slug_l:
                    # slug вида toyota-camry-...
                    if make.lower() not in slug_l:
                        continue
                if model_token and model_token not in slug_l and model_token not in ("hybrid", "гибрид"):
                    # для hybrid camry slug может быть toyota-camry-...
                    if model_token == "camry" and "camry" not in slug_l:
                        continue
                    if model_token not in ("camry",) and model_token not in slug_l:
                        continue
                if year:
                    # год в тексте рядом редко; не режем жёстко
                    pass
                if i < len(parsed):
                    prices.append(parsed[i])
        except Exception as e:
            print("Mashina error:", e)
    return prices


def fetch_bazar_market_prices(make, model, year=None):
    """Заготовка под Bazar.kg — сайт нестабилен для авто, возвращаем []."""
    # Bazar.kg сейчас без удобной категории авто/API.
    # Оставляем хук, чтобы не ломать архитектуру варианта B.
    return []


def remove_price_outliers(prices):
    """Убрать слишком дорогие и подозрительно дешёвые."""
    if len(prices) < 4:
        return prices
    med = statistics.median(prices)
    # жёстче сверху (дорогие «хотелки»), мягче снизу но режем явный мусор
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


def calc_real_quick_sell_price(comparable_prices, min_comps=None):
    """
    REAL_QUICK_SELL_PRICE — цена, по которой реально быстро уйдёт.
    Не среднее. Консервативный низ нормального очищенного рынка.
    """
    need = MIN_COMPARABLES if min_comps is None else min_comps
    cleaned = remove_price_outliers(comparable_prices)
    if len(cleaned) < need:
        return None, cleaned
    return percentile(cleaned, QUICK_SELL_PERCENTILE), cleaned


def calc_max_buy_price(quick_sell, expenses=None, required_profit=None):
    """
    MAX_BUY_PRICE =
      REAL_QUICK_SELL
      - EXPENSES
      - NEGOTIATION_RESERVE
      - REQUIRED_PROFIT
    """
    if not quick_sell or quick_sell <= 0:
        return None
    exp = EXPENSES_USD if expenses is None else expenses
    profit = REQUIRED_PROFIT_USD if required_profit is None else required_profit
    after_reserve = quick_sell * (1 - NEGOTIATION_RESERVE)
    max_buy = after_reserve - exp - profit
    if quick_sell > 0 and (quick_sell - max_buy) / quick_sell < MIN_PROFIT_RATIO:
    max_buy = quick_sell * (1 - MIN_PROFIT_RATIO) - exp
return max(0, round(max_buy))


def find_comparables(target_specs):
    """Собрать похожие объявления: Lalafo + Mashina (+ Bazar hook) — вариант B."""
    make = target_specs.get("make")
    model = target_specs.get("model")
    year = target_specs.get("year")
    if not make or not year:
        return []

    query = make
    if model:
        query += " " + model.split()[0]

    blob_model = f"{model or ''} {target_specs.get('fuel') or ''}".lower()
    if make == "toyota" and ("camry" in (model or "") or "камри" in (model or "")):
        if target_specs.get("fuel") == "hybrid" or "hybrid" in blob_model or "гибрид" in blob_model:
            query = "toyota camry hybrid"

    year_from = max(year - YEAR_TOLERANCE, 1985)
    year_to = year + YEAR_TOLERANCE

    items = get_ads(q=query, per_page=60, year_from=year_from, year_to=year_to)
    items += get_ads(page=2, q=query, per_page=40, year_from=year_from, year_to=year_to)

    comps = []
    for item in items:
        if is_bad_listing(item.get("title") or "", item.get("description") or ""):
            continue
        sp = parse_ad_specs(item)
        if not sp["price"]:
            continue
        if not specs_match(target_specs, sp):
            continue
        sp["source"] = "lalafo"
        comps.append(sp)

    # --- Mashina.kg prices into market pool ---
    mashina_prices = fetch_mashina_market_prices(make, model, year)
    for p in mashina_prices:
        comps.append({
            "make": make,
            "model": model,
            "year": year,
            "price": p,
            "source": "mashina",
            "title": f"{make} {model or ''} mashina",
            "description": "",
            "mileage": None,
            "engine": None,
            "fuel": target_specs.get("fuel"),
            "transmission": None,
            "drive": None,
            "body": None,
            "ad": None,
        })

    # --- Bazar.kg hook (пока пусто) ---
    for p in fetch_bazar_market_prices(make, model, year):
        comps.append({
            "make": make,
            "model": model,
            "year": year,
            "price": p,
            "source": "bazar",
            "title": f"{make} {model or ''} bazar",
            "description": "",
            "mileage": None,
            "engine": None,
            "fuel": None,
            "transmission": None,
            "drive": None,
            "body": None,
            "ad": None,
        })

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

    priority = is_priority_model(target, title, description)
    min_comps = PRIORITY_MIN_COMPARABLES if priority else MIN_COMPARABLES
    exp = PRIORITY_EXPENSES_USD if priority else EXPENSES_USD
    req_profit = PRIORITY_REQUIRED_PROFIT_USD if priority else REQUIRED_PROFIT_USD

    comps = find_comparables(target)
    prices = [c["price"] for c in comps if c.get("price")]
    src_lalafo = sum(1 for c in comps if c.get("source") == "lalafo")
    src_mashina = sum(1 for c in comps if c.get("source") == "mashina")

    quick_sell, cleaned = calc_real_quick_sell_price(prices, min_comps=min_comps)
    if quick_sell is None:
        print(f"  skip (мало данных): {title[:40]} | comps={len(prices)} | priority={priority}")
        seen.add(ad_id); return

    max_buy = calc_max_buy_price(quick_sell, expenses=exp, required_profit=req_profit)
    if not max_buy:
        seen.add(ad_id); return

    seller = target["price"]

    # ГЛАВНОЕ ПРАВИЛО
    if seller > max_buy:
        print(f"  skip (дорого): {title[:35]} | ask={seller}$ max_buy={max_buy}$ qs={quick_sell:.0f}$ | prio={priority}")
        seen.add(ad_id); return

    # REAL_BUY
    expected_profit = quick_sell - seller - exp
    margin_pct = (expected_profit / quick_sell * 100) if quick_sell else 0
    urgent = text_has(f"{title} {description}", URGENT_KEYWORDS)

    url = "https://lalafo.kg" + (ad.get("url") or "")
    city = ad.get("city") or "Бишкек"
    photo = None
    if ad.get("images"):
        photo = ad["images"][0].get("original_url") or ad["images"][0].get("thumbnail_url")

    seller_kgs = round(seller * USD_KGS_RATE)
    max_buy_kgs = round(max_buy * USD_KGS_RATE)
    qs_kgs = round(quick_sell * USD_KGS_RATE)

    urgent_mark = "⚡ <b>СРОЧНО</b>\n" if urgent else ""
    prio_mark = "⭐ <b>ПРИОРИТЕТ: Camry Hybrid 70</b>\n" if priority else ""
    text = (
        f"{urgent_mark}{prio_mark}"
        f"✅ <b>REAL BUY — МОЖНО ЗАБИРАТЬ</b>\n\n"
        f"<b>{title}</b>\n"
        f"📍 {city}\n\n"
        f"💰 <b>Цена продавца:</b> {seller_kgs:,.0f} сом (~{seller}$)\n"
        f"🛒 <b>MAX BUY (твой потолок):</b> {max_buy_kgs:,.0f} сом (~{max_buy}$)\n"
        f"🏷 <b>Быстрая продажа (ориентир):</b> ~{qs_kgs:,.0f} сом (~{quick_sell:.0f}$)\n\n"
        f"📉 Запас до потолка: <b>{max_buy - seller}$</b>\n"
        f"💵 Ожид. прибыль после расходов: <b>~{expected_profit:.0f}$</b> ({margin_pct:.0f}%)\n"
        f"🔧 Расходы: {exp}$ | торг {int(NEGOTIATION_RESERVE*100)}% | цель прибыли {req_profit}$\n"
        f"🔍 Чистых аналогов: {len(cleaned)} (из {len(prices)}) | Lalafo:{src_lalafo} Mashina:{src_mashina}\n\n"
        f"<a href='{url}'>Открыть объявление</a>"
    )

    send_telegram(text, photo)
    tag = "PRIORITY_CAMRY70" if priority else "REAL_BUY"
    print(f"[{datetime.now()}] {tag} | {title[:40]} | ask={seller}$ max={max_buy}$ profit~{expected_profit:.0f}$")
    seen.add(ad_id)


def main():
    print("Бот REAL_BUY / MAX_BUY запущен...")
    send_telegram(
        "🎩 <b>Господин Дияр, ваш бот полностью готов служить вам.</b>\n\n"
        f"✅ Алгоритм скупки активен\n"
        f"⭐ Приоритет: <b>Camry Hybrid 70</b> (2017–2024)\n"
        f"🌐 Рынок: Lalafo + Mashina.kg (вариант B)\n"
        f"• Аналоги: марка+модель+год±{YEAR_TOLERANCE}, пробег±{int(MILEAGE_TOLERANCE*100)}%\n"
        f"• Быстрая продажа = {QUICK_SELL_PERCENTILE}-й перцентиль\n"
        f"• MAX_BUY = продажа − расходы − торг − прибыль\n"
        f"• Кидаю только если цена ≤ MAX_BUY"
    )
    seen = load_seen()
    print(f"seen={len(seen)}")

    while True:
        try:
            print(f"\n[{datetime.now()}] Проверка...")
            ads = get_ads(page=1, per_page=40)
            print(f"Новых с ленты: {len(ads)}")
            if not ads:
                time.sleep(CHECK_INTERVAL)
                continue

            for ad in ads:
                analyze_and_notify(ad, seen)

            save_seen(seen)
            print(f"Цикл OK, сон {CHECK_INTERVAL}с")
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print("Ошибка:", e)
            time.sleep(20)


if __name__ == "__main__":
    main()
 