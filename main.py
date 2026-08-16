# -*- coding: utf-8 -*-
"""
Бот Lalafo — кидает ниже рынка и скупку + рамки цен
"""

import os
import time
import json
import re
import statistics
import requests
from datetime import datetime

BOT_TOKEN = "8677610768:AAHDOe1Xzm-sS_3GnRZvEM38GlQmx7uLJ7c"
CHAT_ID = "8569472160"

CHECK_INTERVAL = 35
CITY_ID = 103184
CAR_CATEGORY_IDS = [1608, 1557, 1570, 1581, 1572, 1559, 1576]
FEED_QUERIES = [
    "toyota", "camry", "lexus", "honda", "hyundai", "kia",
    "bmw", "mercedes", "nissan", "mazda", "subaru", "rav4", "prado",
]
SEEN_FILE = "seen_ads_lalafo.json"
USD_KGS_RATE = 87.5

REAL_SELL_PERCENTILE = 35
WHOLESALE_MARGIN_PCT = 0.15
WHOLESALE_MARGIN_HIGH_LIQ = 0.12
WHOLESALE_MARGIN_LOW_LIQ = 0.18

# Ниже медианы рынка на 8%+ и запас от $400 → кидать
MIN_VS_MEDIAN = 0.08
MIN_GAP_MEDIAN = 400
# Ниже реал.продажи на 8%+ → скупка
MIN_VS_REAL = 0.08
MIN_GAP_REAL = 500
MIN_SIMILAR = 3
MIN_YEAR = 2005
MIN_SCORE = 35
MIN_PRICE_USD = 3000
MAX_PRICE_USD = 90000
HEARTBEAT_EVERY = 25

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "device": "pc",
    "language": "ru_RU",
    "country-id": "12",
}

KNOWN_MAKES = {
    "toyota", "lexus", "honda", "nissan", "hyundai", "kia", "bmw", "mercedes",
    "mercedes-benz", "audi", "volkswagen", "vw", "ford", "chevrolet", "mazda",
    "subaru", "mitsubishi", "suzuki", "skoda", "renault", "volvo", "infiniti",
    "acura", "genesis", "geely", "chery", "haval", "lada", "ваз",
}
HIGH_LIQUIDITY = {
    ("toyota", "camry"), ("toyota", "corolla"), ("toyota", "rav4"),
    ("toyota", "prado"), ("toyota", "highlander"), ("toyota", "land"),
    ("lexus", "rx"), ("lexus", "gx"), ("lexus", "es"),
    ("honda", "cr"), ("honda", "accord"), ("hyundai", "tucson"), ("hyundai", "sonata"),
    ("kia", "sportage"), ("kia", "k5"), ("bmw", "x5"), ("bmw", "x3"), ("mercedes", "e"),
}
MEDIUM_LIQ = {
    "toyota", "lexus", "honda", "nissan", "hyundai", "kia", "bmw",
    "mercedes", "mercedes-benz", "audi", "subaru", "mazda", "volkswagen", "vw",
}
STOP = [
    "чехол", "стекло на", "запчаст", "аксессуар", "ремонт", "услуг", "разбор",
    "бампер", "крыло", "капот", "шины", "резина", "фара", "аренда", "портер",
    "вывоз мусор", "погрузчик",
]
BAD = ["битый", "битая", "после дтп", "не на ходу", "на запчасти", "распил", "каркас"]
CREDIT = ["рассрочк", "в кредит", "лизинг", "первый взнос"]
ORDER = ["под заказ", "из китая", "из кореи", "в пути", "пригон", "аукцион"]
NOT_CLEAR = ["не растаможен", "без растамож", "временный учет", "транзит", "без птс"]
CYR = {
    "тойота": "toyota", "лексус": "lexus", "хонда": "honda", "ниссан": "nissan",
    "хундай": "hyundai", "хендай": "hyundai", "киа": "kia", "бмв": "bmw",
    "мерседес": "mercedes", "камри": "camry",
}
FLOORS = {
    ("lexus", "gx"): 35000, ("lexus", "lx"): 40000, ("lexus", "rx"): 15000,
    ("toyota", "prado"): 14000, ("toyota", "land"): 18000, ("toyota", "camry"): 5000,
    ("toyota", "highlander"): 12000, ("bmw", "x5"): 12000,
}


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return {}
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        return {str(x): None for x in d} if isinstance(d, list) else (d if isinstance(d, dict) else {})
    except Exception:
        return {}


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(dict(list(seen.items())[-5000:]), f)


def send_telegram(text, photo_url=None):
    try:
        if photo_url and len(text) <= 1000:
            r = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                data={"chat_id": CHAT_ID, "photo": photo_url, "caption": text[:1024], "parse_mode": "HTML"},
                timeout=15,
            )
        else:
            r = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": False},
                timeout=15,
            )
        ok = r.status_code == 200 and (r.json() or {}).get("ok")
        print("TG", "OK" if ok else r.text[:150])
        return ok
    except Exception as e:
        print("TG", e)
        return False


def has(text, words):
    t = (text or "").lower()
    return any(w in t for w in words)


def blocked(title, desc=""):
    b = f"{title} {desc}"
    return has(b, STOP) or has(b, BAD) or has(b, CREDIT) or has(b, ORDER) or has(b, NOT_CLEAR)


def year_of(title):
    if not title:
        return None
    m = re.search(r"(20\d{2}|19\d{2})\s*г", title, re.I) or re.search(r"\b(20\d{2}|19\d{2})\b", title)
    if m:
        y = int(m.group(1))
        if 1990 <= y <= 2027:
            return y
    return None


def make_model(title):
    if not title:
        return None, None
    clean = re.sub(r"[^\w\s\-]", " ", title.lower())
    clean = re.sub(r"\s+", " ", clean)
    clean = re.sub(r"\b(19|20)\d{2}\b", "", clean)
    clean = re.sub(r"\s*г\.?\s*", " ", clean).strip()
    for a, b in CYR.items():
        clean = re.sub(rf"\b{a}\b", b, clean)
    clean = clean.replace("камри", "camry")
    words = clean.split()
    if not words:
        return None, None
    make, parts = None, []
    for i, w in enumerate(words):
        if w in KNOWN_MAKES:
            make, parts = w, words[i + 1 : i + 3]
            break
    if not make and "camry" in clean:
        make, parts = "toyota", ["camry"]
    if not make:
        make, parts = words[0], words[1:3]
    return make, (" ".join(parts).strip() or None)


def fuel_of(t):
    t = (t or "").lower()
    if any(x in t for x in ["дизел", "diesel"]):
        return "diesel"
    if any(x in t for x in ["гибрид", "hybrid"]):
        return "hybrid"
    if "бензин" in t:
        return "petrol"
    return None


def price_usd(ad):
    p = ad.get("price")
    if p is None:
        return None
    try:
        p = float(p)
    except Exception:
        return None
    cur = (ad.get("currency") or "").upper()
    sym = (ad.get("symbol") or "").upper()
    if cur in ("USD", "$") or sym in ("$", "USD"):
        u = p
    elif cur in ("KGS", "COM", "СОМ", "SOM") or sym in ("COM", "С"):
        u = p / USD_KGS_RATE
    else:
        u = p / USD_KGS_RATE if p >= 80000 else p
    if u < 1500 or u > 120000:
        return None
    return round(u)


def norm(ad):
    title = ad.get("title") or ""
    desc = ad.get("description") or ""
    make, model = make_model(title)
    city = ad.get("city")
    if isinstance(city, dict):
        city = city.get("name")
    return {
        "id": ad.get("id"),
        "title": title,
        "description": desc,
        "make": make,
        "model": model,
        "year": year_of(title),
        "fuel": fuel_of(f"{title} {desc}"),
        "price_usd": price_usd(ad),
        "url": ad.get("url") or "",
        "city": city or "Бишкек",
        "images": ad.get("images"),
    }


def floor_price(make, model, year=None):
    make = (make or "").lower()
    model = (model or "").lower()
    first = model.split()[0] if model else ""
    fl = MIN_PRICE_USD
    for (m, tok), f in FLOORS.items():
        if make == m and (tok in model or first == tok):
            fl = max(fl, f)
    return fl


def margin_of(make, model):
    make = (make or "").lower()
    model = (model or "").lower()
    first = model.split()[0] if model else ""
    for hm, hmod in HIGH_LIQUIDITY:
        if make == hm and (hmod in model or first.startswith(hmod)):
            return WHOLESALE_MARGIN_HIGH_LIQ, "высокая"
    if make in MEDIUM_LIQ:
        return WHOLESALE_MARGIN_PCT, "средняя"
    return WHOLESALE_MARGIN_LOW_LIQ, "низкая"


def get_ads(page=1, q=None, per_page=40, category_id=None):
    params = {"per-page": per_page, "page": page, "expand": "url", "sort_by": "newest", "city_id": CITY_ID}
    if category_id:
        params["category_id"] = category_id
    if q:
        params["q"] = q
    try:
        r = requests.get("https://api.lalafo.com/v3/ads/search", params=params, headers=HEADERS, timeout=20)
        if r.status_code == 200:
            return r.json().get("items") or []
    except Exception as e:
        print("Lalafo", e)
    return []


def fetch_feed():
    raw = []
    for cid in CAR_CATEGORY_IDS:
        raw += get_ads(1, per_page=40, category_id=cid)
    for q in FEED_QUERIES:
        raw += get_ads(1, q=q, per_page=30)
    seen, cars = set(), []
    for ad in raw:
        i = ad.get("id")
        if not i or i in seen:
            continue
        seen.add(i)
        t, d = ad.get("title") or "", ad.get("description") or ""
        if blocked(t, d):
            continue
        if not year_of(t) or not make_model(t)[0] or not price_usd(ad):
            continue
        cars.append(ad)
    print(f"Лента {len(cars)} / {len(raw)}")
    return cars


def similar_ok(a, b):
    if not a.get("make") or a["make"] != b.get("make"):
        return False
    am = (a.get("model") or "").split()
    bm = (b.get("model") or "").split()
    if am and bm and am[0] != bm[0]:
        return False
    ay, by = a.get("year"), b.get("year")
    if ay and by and abs(ay - by) > 2:
        return False
    return True


def outliers(prices):
    if len(prices) < 4:
        return prices
    med = statistics.median(prices)
    c = [p for p in prices if med * 0.45 <= p <= med * 1.40]
    return c if len(c) >= 2 else prices


def percentile(data, p):
    s = sorted(data)
    n = len(s)
    if not n:
        return None
    idx = (n - 1) * p / 100.0
    f = int(idx)
    c = min(f + 1, n - 1)
    return s[f] if f == c else s[f] * (c - idx) + s[c] * (idx - f)


def levels(prices):
    c = outliers(prices)
    if len(c) < MIN_SIMILAR:
        return None, None, None, c
    med = statistics.median(c)
    avg = statistics.mean(c)
    real = percentile(c, REAL_SELL_PERCENTILE)
    if real is None:
        return None, None, None, c
    if real > med:
        real = med * 0.94
    half = sorted(c)[: max(2, len(c) // 2)]
    if half:
        real = min(real, statistics.median(half))
    return round(med), round(avg), round(real), c


def find_similar(car):
    make, model, year = car.get("make"), car.get("model"), car.get("year")
    if not make:
        return []
    q = make + ((" " + model.split()[0]) if model else "")
    if make == "toyota" and model and "camry" in model:
        q = "toyota camry"
    items = get_ads(q=q, per_page=55) + get_ads(page=2, q=q, per_page=40)
    prices = []
    for it in items:
        if blocked(it.get("title") or "", it.get("description") or ""):
            continue
        c = norm(it)
        if not c["price_usd"] or not c["year"]:
            continue
        if str(c["id"]) == str(car.get("id")):
            continue
        if not (MIN_PRICE_USD <= c["price_usd"] <= MAX_PRICE_USD):
            continue
        if year and abs(c["year"] - year) > 2:
            continue
        if not similar_ok(car, c):
            continue
        prices.append(c["price_usd"])
    return outliers(prices)


def money(n):
    return f"${n:,.0f}".replace(",", " ")


def frame(listing, med, avg, real, buy):
    def pct(a, b):
        return f"{int(round(a / b * 100))}%" if b else "—"

    return (
        "<pre>"
        "┌──────────────────────────────┐\n"
        "│  РАМКИ ЦЕН (USD)             │\n"
        "├──────────────────────────────┤\n"
        f"│ Среднее (было)        {money(avg):>8} │\n"
        f"│ Медиана (было)        {money(med):>8} │\n"
        f"│ Реал. продажа         {money(real):>8} │\n"
        f"│ СЕЙЧАС                {money(listing):>8} │\n"
        f"│ Скупка (вход)         {money(buy):>8} │\n"
        "└──────────────────────────────┘\n"
        "</pre>\n"
        f"От медианы: <b>{pct(listing, med)}</b> · от реала: <b>{pct(listing, real)}</b>\n"
        f"Выгода к медиане: <b>{money(max(0, med - listing))}</b> · к реалу: <b>{money(max(0, real - listing))}</b>"
    )


def score_of(vs_med, vs_real, gap_med, gap_real, n, liq):
    s = min(35, max(0, vs_med * 100 * 1.2))
    s += min(25, max(0, vs_real * 100 * 1.3))
    if gap_med >= 1500 or gap_real >= 1200:
        s += 20
    elif gap_med >= 800 or gap_real >= 600:
        s += 12
    elif gap_med >= 400:
        s += 6
    if n >= 6:
        s += 8
    elif n >= 3:
        s += 4
    if liq == "высокая":
        s += 8
    elif liq == "низкая":
        s -= 4
    return int(max(0, min(100, round(s))))


def fires(vs, gap):
    if vs >= 0.18 and gap >= 1000:
        return "🔥🔥🔥"
    if vs >= 0.12 and gap >= 600:
        return "🔥🔥"
    return "🔥"


def analyze(ad, seen):
    ad_id = str(ad.get("id") or "")
    if not ad_id:
        return False
    title, desc = ad.get("title") or "", ad.get("description") or ""
    if blocked(title, desc):
        seen[ad_id] = price_usd(ad)
        return False
    car = norm(ad)
    listing = car["price_usd"]
    if not listing or not car["make"] or not car["year"]:
        seen[ad_id] = listing
        return False
    if car["year"] < MIN_YEAR or not (MIN_PRICE_USD <= listing <= MAX_PRICE_USD):
        seen[ad_id] = listing
        return False
    fl = floor_price(car["make"], car["model"], car["year"])
    if listing < fl * 0.85:  # только явный мусор по полу
        print(f"  floor {listing}<{fl}: {title[:36]}")
        seen[ad_id] = listing
        return False
    if ad_id in seen and seen[ad_id] == listing:
        return False

    similar = find_similar(car)
    if len(similar) < MIN_SIMILAR:
        print(f"  analogs {len(similar)}: {title[:36]}")
        seen[ad_id] = listing
        return False

    med, avg, real, cleaned = levels(similar)
    if not med or not real:
        seen[ad_id] = listing
        return False

    # выше медианы — обычный рынок, не кидаем
    if listing >= med * 0.98:
        print(f"  >=median {listing}>={med}: {title[:32]}")
        seen[ad_id] = listing
        return False

    # слишком дёшево = риск
    if listing < real * 0.42:
        print(f"  sus {listing} vs {real}")
        seen[ad_id] = listing
        return False

    m_pct, liq = margin_of(car["make"], car["model"])
    buy = round(real * (1 - m_pct))
    vs_med = (med - listing) / med
    vs_real = (real - listing) / real if real else 0
    gap_med = med - listing
    gap_real = real - listing

    is_buy = listing <= buy and gap_real >= MIN_GAP_REAL
    is_real = vs_real >= MIN_VS_REAL and gap_real >= MIN_GAP_REAL
    is_med = vs_med >= MIN_VS_MEDIAN and gap_med >= MIN_GAP_MEDIAN

    if not (is_buy or is_real or is_med):
        print(f"  weak med={med} real={real} now={listing}: {title[:28]}")
        seen[ad_id] = listing
        return False

    sc = score_of(vs_med, max(0, vs_real), gap_med, max(0, gap_real), len(cleaned), liq)
    if sc < MIN_SCORE:
        print(f"  score {sc}: {title[:36]}")
        seen[ad_id] = listing
        return False

    tag = "СКУПКА" if (is_buy or vs_real >= 0.12) else "НИЖЕ РЫНКА"
    fr = fires(max(vs_med, max(0, vs_real)), max(gap_med, max(0, gap_real)))
    url = "https://lalafo.kg" + (car["url"] or "")
    photo = None
    if car.get("images"):
        photo = car["images"][0].get("original_url") or car["images"][0].get("thumbnail_url")
    text = (
        f"🚨 <b>{tag}</b> {fr}\n\n"
        f"<b>{title}</b>\n"
        f"Lalafo · {car.get('city')} · аналогов: {len(cleaned)} · {liq}\n\n"
        f"{frame(listing, med, avg, real, buy)}\n\n"
        f"Оценка: {fr} ({sc}/100)\n"
        f"<a href='{url}'>Открыть</a>"
    )
    if photo and len(text) > 1000:
        photo = None
    send_telegram(text, photo)
    print(f"SEND {tag} {sc} | {title[:40]} | ${listing}")
    seen[ad_id] = listing
    return True


def main():
    print("Car bot SOFT start...")
    # Новый seen-файл опционально — если старый забит, раскомментируй:
    # if os.path.exists(SEEN_FILE): os.remove(SEEN_FILE)
    send_telegram(
        "🎩 <b>Бот машин перезапущен</b>\n"
        "Фильтры мягкие — кидает ниже рынка и скупку.\n"
        "В сообщениях рамки цен."
    )
    seen = load_seen()
    # если seen огромный — подчистим старое (оставим 500)
    if len(seen) > 2000:
        seen = dict(list(seen.items())[-500:])
        save_seen(seen)
        print("seen trimmed to", len(seen))

    cycles = total = 0
    while True:
        try:
            cycles += 1
            print(f"\n[{datetime.now()}] #{cycles}")
            ads = fetch_feed()
            now = 0
            for ad in ads[:100]:
                try:
                    if analyze(ad, seen):
                        now += 1
                        total += 1
                        time.sleep(0.8)
                except Exception as e:
                    print("err", e)
            save_seen(seen)
            print(f"OK лента={len(ads)} кинул={now} всего={total}")
            if cycles % HEARTBEAT_EVERY == 0:
                send_telegram(f"💓 Жив. циклов {cycles}, кинул {total}, seen {len(seen)}")
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print("cycle", e)
            time.sleep(20)


if __name__ == "__main__":
    main()
