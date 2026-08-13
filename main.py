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

CHECK_INTERVAL = 60
SEEN_FILE = "seen_ads.json"
USD_KGS_RATE = 87.5

# --- Скупка (как на Lalafo-версии) ---
REQUIRED_MARGIN_PCT = 0.23
REQUIRED_MARGIN_PCT_HIGH_LIQ = 0.20
REQUIRED_MARGIN_PCT_LOW_LIQ = 0.28
MIN_PROFIT = 800
MIN_DISCOUNT = 0.18
MIN_SIMILAR_LISTINGS = 5
MIN_YEAR = 2008
STAGE1_MIN_DISCOUNT = 0.12

MIN_PRICE_USD = 3500
MAX_PRICE_USD = 80000

MASHINA_FEED_PAGES = 2
MASHINA_FEED_LIMIT = 12          # деталок за страницу ленты
MASHINA_MARKET_LIMIT = 8         # деталок для рынка по модели

URGENT_BOOST_KEYWORDS = [
    "срочно", "торг", "уступлю", "сегодня", "торг реальному",
    "нужны деньги", "быстро продам", "цена снижена",
]

# ===========================================================

KNOWN_MAKES = {
    "toyota", "lexus", "honda", "nissan", "hyundai", "kia", "bmw", "mercedes",
    "mercedes-benz", "audi", "volkswagen", "vw", "ford", "chevrolet", "mazda",
    "subaru", "mitsubishi", "suzuki", "opel", "skoda", "renault", "peugeot",
    "citroen", "volvo", "land rover", "range rover", "jeep", "dodge", "chrysler",
    "infiniti", "acura", "genesis", "ssangyong", "daewoo", "ravon", "geely",
    "chery", "haval", "great wall", "byd", "tesla", "porsche", "mini", "daihatsu",
    "lifan", "faw", "uaz", "lada", "ваз",
}

HIGH_LIQUIDITY = {
    ("toyota", "camry"), ("toyota", "corolla"), ("toyota", "rav4"),
    ("toyota", "prado"), ("toyota", "highlander"), ("toyota", "land"),
    ("lexus", "rx"), ("lexus", "gx"), ("lexus", "es"), ("lexus", "lx"),
    ("honda", "cr"), ("honda", "accord"), ("honda", "fit"),
    ("hyundai", "tucson"), ("hyundai", "sonata"), ("hyundai", "elantra"),
    ("kia", "sportage"), ("kia", "k5"), ("kia", "sorento"),
    ("nissan", "x"), ("nissan", "patrol"),
    ("bmw", "x5"), ("bmw", "x3"), ("mercedes", "e"), ("mercedes-benz", "e"),
}

MEDIUM_LIQUIDITY_MAKES = {
    "toyota", "lexus", "honda", "nissan", "hyundai", "kia", "bmw",
    "mercedes", "mercedes-benz", "audi", "subaru", "mazda", "volkswagen", "vw",
}

STOP_WORDS = [
    "чехол", "стекло на", "стекло для", "запчаст", "запчасти", "аксессуар",
    "коробка от", "документы на", "ремонт", "услуг", "работаю", "работы",
    "разбор", "в разборе", "контрактн", "б/у запчаст", "продаю запчаст",
    "диск", "диски", "ремень", "турбина", "бампер", "крыло", "дверь",
    "капот", "зеркало", "подшипник", "сайлент", "амортизатор", "стойка",
    "радиатор", "генератор", "стартер", "компрессор", "шины", "резина",
    "колесо", "колпак", "магнитола", "парктроник",
    "фара", "фары", "стоп", "стопы", "фонарь", "поворотник", "коврик",
    "накидк", "оплетка", "оплётка", "щетк", "дворник", "фильтр",
    "колодк", "свеч", "аккумулятор", "масло мотор",
]

CRITICAL_DAMAGE = [
    "битый", "битая", "битое", "после дтп", "после аварии",
    "аварийный", "аварийная", "не на ходу", "не находу",
    "на запчасти", "на запчасть", "распил", "каркас", "конструктор",
    "распилен", "только на запчасти",
]

INSTALLMENT_KEYWORDS = [
    "рассрочк", "рассрочка", "первоначальн", "в кредит", "кредит",
    "ежемесячн", "платеж", "платёж", "лизинг", "оплата частями",
    "первый взнос", "0-0-24", "0-0-12", "без первоначального",
]

ORDER_KEYWORDS = [
    "под заказ", "подзаказ", "на заказ", "заказ из", "из китая", "из кореи",
    "из японии", "из оаэ", "из дубая", "из сша", "из америки", "из европы",
    "в пути", "едет", "ожидается", "пригон", "с аукциона", "copart", "iaai",
]

NOT_CLEARED = [
    "не растаможен", "не растаможена", "не растаможено", "без растаможки",
    "без растамож", "не на учете", "временный учет", "временный учёт",
    "транзит", "без птс", "транзитные номера",
]

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

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
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
    items = list(seen.items())[-4000:]
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
            print("Telegram error:", r.text[:200])
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
    m = re.search(r"\b([1-6][.,]\d)\s*(л|l)?\b", text.lower())
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
    if any(x in t for x in ["акпп", "автомат", "automatic", "cvt", "вариатор"]):
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


def text_has_blocked(title, description=""):
    blob = f"{title} {description}"
    if text_has(blob, STOP_WORDS):
        return True
    if text_has(blob, CRITICAL_DAMAGE):
        return True
    if text_has(blob, INSTALLMENT_KEYWORDS):
        return True
    if text_has(blob, ORDER_KEYWORDS):
        return True
    if text_has(blob, NOT_CLEARED):
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
            return REQUIRED_MARGIN_PCT_HIGH_LIQ, "высокая"
    if make in MEDIUM_LIQUIDITY_MAKES:
        return REQUIRED_MARGIN_PCT, "средняя"
    return REQUIRED_MARGIN_PCT_LOW_LIQ, "низкая"


def _slug_title(slug):
    if not slug:
        return "Авто Mashina"
    parts = slug.split("-")
    while parts and (len(parts[-1]) >= 10 or re.fullmatch(r"[0-9a-f]{8,}", parts[-1] or "")):
        parts.pop()
    return " ".join(p.capitalize() for p in parts) if parts else slug


def fetch_mashina_detail(slug):
    """Цена/год/текст только со страницы объявления — без чужих цен из списка."""
    url = f"https://www.mashina.kg/details/{slug}"
    try:
        r = requests.get(url, headers=HTTP_HEADERS, timeout=20)
        if r.status_code != 200:
            return None
        t = r.text
        price_usd = None
        for m in re.finditer(
            r'"price"\s*:\s*(\d+)\s*,\s*"priceCurrency"\s*:\s*"(USD|KGS|SOM|COM)"',
            t, re.I,
        ):
            val = int(m.group(1))
            cur = m.group(2).upper()
            if cur == "USD" and 2000 <= val <= 250000:
                price_usd = val
                break
            if cur in ("KGS", "SOM", "COM") and val >= 100000:
                cand = round(val / USD_KGS_RATE)
                if 2000 <= cand <= 250000:
                    price_usd = cand
                    break
        if price_usd is None:
            m = re.search(r'"priceCurrency"\s*:\s*"USD"\s*,\s*"price"\s*:\s*(\d+)', t, re.I)
            if m:
                val = int(m.group(1))
                if 2000 <= val <= 250000:
                    price_usd = val
        if price_usd is None:
            for m in re.finditer(r'"price"\s*:\s*(\d{6,8})', t):
                val = int(m.group(1))
                if val >= 500000:
                    cand = round(val / USD_KGS_RATE)
                    if 2000 <= cand <= 250000:
                        price_usd = cand
                        break

        year = None
        for pat in [r'(20\d{2})\s*г', r'"year"\s*:\s*(20\d{2})', r'\b(20[0-2]\d)\.']:
            mm = re.search(pat, t)
            if mm:
                y = int(mm.group(1))
                if 1990 <= y <= 2027:
                    year = y
                    break

        # кусок текста для стоп-слов (без огромного HTML)
        plain = re.sub(r"<script[^>]*>.*?</script>", " ", t, flags=re.I | re.S)
        plain = re.sub(r"<[^>]+>", " ", plain)
        plain = re.sub(r"\s+", " ", plain)[:3000]

        return {
            "price_usd": price_usd,
            "year": year,
            "url": url,
            "text": plain,
            "slug": slug,
        }
    except Exception as e:
        print("detail err:", e)
        return None


def normalize_mashina(slug, meta):
    title = _slug_title(slug)
    year = meta.get("year")
    if year:
        title = f"{title} {year}"
    desc = meta.get("text") or ""
    make, model = extract_make_model(title)
    # fuel/engine from page text
    blob = f"{title} {desc}"
    return {
        "id": f"mashina_{slug}",
        "title": title,
        "description": desc[:1500],
        "make": make,
        "model": model,
        "year": year or extract_year(title),
        "engine": extract_engine(blob),
        "fuel": extract_fuel(blob),
        "transmission": extract_transmission(blob),
        "drive": extract_drive(blob),
        "body": extract_body(blob),
        "mileage": extract_mileage(blob),
        "price_usd": meta.get("price_usd"),
        "url": meta.get("url") or f"https://www.mashina.kg/details/{slug}",
        "city": "Бишкек",
        "images": None,
        "source": "mashina",
    }


def list_mashina_slugs(q=None, pages=1, limit=12):
    slugs = []
    seen = set()
    for page in range(1, pages + 1):
        if q:
            url = f"https://www.mashina.kg/search/all/?q={requests.utils.quote(q)}&currency=2&page={page}"
        else:
            url = f"https://www.mashina.kg/search/all/?currency=2&sort_by=upped_at+desc&page={page}"
        try:
            r = requests.get(url, headers=HTTP_HEADERS, timeout=25)
            if r.status_code != 200:
                continue
            for slug in re.findall(r"/details/([a-z0-9\-]+)", r.text):
                if slug not in seen:
                    seen.add(slug)
                    slugs.append(slug)
                if len(slugs) >= limit * pages:
                    return slugs
        except Exception as e:
            print("list err:", e)
    return slugs[: limit * pages]


def fetch_mashina_feed():
    """Лента: slug с поиска → цена только с detail."""
    results = []
    for slug in list_mashina_slugs(pages=MASHINA_FEED_PAGES, limit=MASHINA_FEED_LIMIT):
        meta = fetch_mashina_detail(slug)
        if not meta or not meta.get("price_usd"):
            continue
        car = normalize_mashina(slug, meta)
        if text_has_blocked(car["title"], car["description"]):
            continue
        results.append(car)
    print(f"Mashina feed ok: {len(results)}")
    return results


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
    for key in ("engine", "fuel", "body", "transmission", "drive"):
        tv, cv = target.get(key), cand.get(key)
        if tv and cv and tv != cv:
            return False
    return True


def remove_outliers(prices):
    if len(prices) < 4:
        return prices
    med = statistics.median(prices)
    cleaned = [p for p in prices if med * 0.55 <= p <= med * 1.35]
    return cleaned if len(cleaned) >= min(3, MIN_SIMILAR_LISTINGS) else prices


def find_similar_prices(car):
    """Рынок только с Mashina.kg (detail-цены)."""
    make, model, year = car.get("make"), car.get("model"), car.get("year")
    if not make:
        return []
    q = make
    if model:
        q += " " + model.split()[0]
    if make == "toyota" and model and "camry" in model and car.get("fuel") == "hybrid":
        q = "toyota camry hybrid"

    prices = []
    for slug in list_mashina_slugs(q=q, pages=2, limit=MASHINA_MARKET_LIMIT):
        if f"mashina_{slug}" == str(car.get("id")):
            continue
        meta = fetch_mashina_detail(slug)
        if not meta or not meta.get("price_usd"):
            continue
        c = normalize_mashina(slug, meta)
        if text_has_blocked(c["title"], c["description"]):
            continue
        p = c["price_usd"]
        if p < MIN_PRICE_USD or p > MAX_PRICE_USD:
            continue
        floor = sane_min_price(c.get("make"), c.get("model"), c.get("year"))
        if p < floor:
            continue
        if car.get("year") and c.get("year") and abs(car["year"] - c["year"]) > 1:
            continue
        if not similar_match(car, c):
            # если у целевого нет года — уже мягче в similar_match
            if car.get("year"):
                continue
            # без года: хотя бы make+model
            if c.get("make") != car.get("make"):
                continue
        prices.append(p)
    return remove_outliers(prices)


def stage1_rough_reject(car):
    make, model = car.get("make"), car.get("model")
    listing = car.get("price_usd")
    if not make or not listing:
        return True
    q = make + ((" " + model.split()[0]) if model else "")
    prices = []
    for slug in list_mashina_slugs(q=q, pages=1, limit=6):
        meta = fetch_mashina_detail(slug)
        if meta and meta.get("price_usd"):
            p = meta["price_usd"]
            if MIN_PRICE_USD <= p <= MAX_PRICE_USD:
                prices.append(p)
    if len(prices) < 3:
        return False
    med = statistics.median(prices)
    if med <= 0:
        return True
    return (med - listing) / med < STAGE1_MIN_DISCOUNT


def deal_score(discount, potential_profit, n_similar, liq_label, urgent=False):
    score = 0.0
    score += min(55, max(0, discount * 100 * 1.6))
    if potential_profit >= 2500:
        score += 25
    elif potential_profit >= 1500:
        score += 18
    elif potential_profit >= 1000:
        score += 12
    elif potential_profit >= MIN_PROFIT:
        score += 6
    else:
        score -= 10
    if n_similar >= 10:
        score += 8
    elif n_similar >= MIN_SIMILAR_LISTINGS:
        score += 4
    if liq_label == "высокая":
        score += 8
    elif liq_label == "низкая":
        score -= 10
    if urgent:
        score += 3
    return int(max(0, min(100, round(score))))


def score_fires(discount, potential_profit):
    if discount >= 0.28 and potential_profit >= 1500:
        return "🔥🔥🔥"
    if discount >= 0.22 and potential_profit >= 1000:
        return "🔥🔥"
    return "🔥"


def analyze(car, seen):
    """car — уже normalize_mashina dict."""
    ad_id = str(car.get("id") or "")
    if not ad_id:
        return

    title = car.get("title") or ""
    description = car.get("description") or ""
    listing = car.get("price_usd")

    if text_has_blocked(title, description):
        seen[ad_id] = listing
        return
    if not listing or not car.get("make"):
        seen[ad_id] = listing
        return

    year = car.get("year")
    if year and year < MIN_YEAR:
        seen[ad_id] = listing
        return

    if listing < MIN_PRICE_USD or listing > MAX_PRICE_USD:
        print(f"  skip range ${listing}: {title[:40]}")
        seen[ad_id] = listing
        return

    floor = sane_min_price(car.get("make"), car.get("model"), year)
    if listing < floor:
        print(f"  skip floor ${listing}<${floor}: {title[:40]}")
        seen[ad_id] = listing
        return

    if ad_id in seen and seen[ad_id] is not None and seen[ad_id] == listing:
        return

    if stage1_rough_reject(car):
        print(f"  stage1 drop: {title[:40]} | ${listing}")
        seen[ad_id] = listing
        return

    similar = find_similar_prices(car)
    if len(similar) < MIN_SIMILAR_LISTINGS:
        print(f"  skip analogs {len(similar)}: {title[:40]}")
        seen[ad_id] = listing
        return

    market_price = statistics.median(similar)
    if not market_price:
        seen[ad_id] = listing
        return

    if listing < market_price * 0.55:
        print(f"  skip suspicious ${listing} vs ${market_price:.0f}: {title[:40]}")
        seen[ad_id] = listing
        return

    margin_pct, liq_label = get_liquidity_margin_pct(car.get("make"), car.get("model"))
    buy_price = round(market_price * (1 - margin_pct))
    discount = (market_price - listing) / market_price
    potential_profit = market_price - listing

    if listing >= buy_price:
        print(f"  skip >=BUY ${listing}>${buy_price}: {title[:35]}")
        seen[ad_id] = listing
        return
    if discount < MIN_DISCOUNT:
        print(f"  skip disc {discount*100:.1f}%: {title[:40]}")
        seen[ad_id] = listing
        return
    if potential_profit < MIN_PROFIT:
        print(f"  skip profit ${potential_profit:.0f}: {title[:40]}")
        seen[ad_id] = listing
        return

    urgent = has_urgent_marker(title, description)
    score = deal_score(discount, potential_profit, len(similar), liq_label, urgent)
    if score < 70:
        print(f"  skip score {score}: {title[:40]}")
        seen[ad_id] = listing
        return

    fires = score_fires(discount, potential_profit)
    url = car.get("url") or ""
    urgent_mark = "⚡ " if urgent else ""
    text = (
        f"🚨 <b>СКУПКА</b> {fires}\n\n"
        f"{urgent_mark}<b>{title}</b>\n"
        f"Источник: Mashina.kg\n"
        f"Цена: <b>${listing:,.0f}</b>\n"
        f"Рынок: ~${market_price:,.0f}\n"
        f"Цена скупки: ≤${buy_price:,.0f}\n"
        f"Запас: ~${potential_profit:,.0f}\n"
        f"Оценка: {fires} ({score}/100)\n"
        f"<a href='{url}'>Ссылка</a>"
    )
    send_telegram(text)
    print(f"[{datetime.now()}] SEND {fires} {score} | {title[:40]} | ${listing}")
    seen[ad_id] = listing


def main():
    print("Бот СКУПКА Mashina-only запущен...")
    send_telegram("🎩 <b>Господин Дияр, ваш бот полностью готов служить вам.</b>")
    seen = load_seen()
    print(f"seen={len(seen)} | only Mashina.kg | margin={REQUIRED_MARGIN_PCT*100:.0f}%")

    while True:
        try:
            print(f"\n[{datetime.now()}] Mashina.kg...")
            cars = fetch_mashina_feed()
            for car in cars:
                try:
                    analyze(car, seen)
                except Exception as e:
                    print("analyze err:", e)
            save_seen(seen)
            print(f"Цикл OK, сон {CHECK_INTERVAL}с")
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print("Ошибка:", e)
            time.sleep(25)


if __name__ == "__main__":
    main()
