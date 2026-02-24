"""
test_checker.py — ручная проверка всех источников.
Запуск: python test_checker.py
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(__file__))

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import config

G = "\033[92m"   # зелёный
R = "\033[91m"   # красный
Y = "\033[93m"   # жёлтый
C = "\033[96m"   # голубой
B = "\033[1m"    # жирный
X = "\033[0m"    # сброс

SEP = "─" * 55

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9",
}
S = requests.Session()
S.headers.update(HEADERS)


def slug(url):
    if not url:
        return ""
    path = urlparse(url).path.strip("/").split("/")
    parts = [p for p in path if p and p not in ("live", "stream", "streams", "c", "user")]
    return parts[-1].lstrip("@") if parts else ""

def mark(cond):
    return f"{G}✅ ДА{X}" if cond else f"{R}❌ НЕТ{X}"

def check_keywords(text):
    tl = text.lower()
    kw    = [k for k in config.STREAM_KEYWORDS if k in tl]
    links = [d for d in config.STREAM_LINK_DOMAINS if d in tl]
    live  = bool(links) or len(kw) >= config.KEYWORD_MIN_MATCHES
    return kw, links, live

def p(line=""):
    print(line)

def pi(line="", indent=2):
    print(" " * indent + line)


# ══ Telegram ══════════════════════════════════════════════════

def test_telegram(url):
    channel = slug(url)
    if not channel:
        pi(f"{R}URL пустой{X}"); return
    pi(f"Канал: @{channel}")
    try:
        r = S.get(f"https://t.me/s/{channel}", timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        posts = soup.find_all(class_="tgme_widget_message_wrap")[-5:]
        if not posts:
            pi(f"{Y}⚠ Постов не найдено (закрытый канал?){X}"); return
        pi(f"Найдено постов: {len(posts)}")
        p()
        any_live = False
        for i, post in enumerate(posts, 1):
            text = post.get_text(separator=" ").strip()
            links = [a.get("href", "") for a in post.find_all("a") if a.get("href")]
            stream_links = [l for l in links if any(d in l for d in config.STREAM_LINK_DOMAINS)]
            full = text + " " + " ".join(links)
            kw, fl, is_live = check_keywords(full)
            any_live = any_live or is_live
            tag = f" {G}[→ СТРИМ]{X}" if is_live else ""
            pi(f"{C}── Пост #{i}{tag}{X}")
            short = text[:220] + ("..." if len(text) > 220 else "")
            pi(f"   Текст: {short}")
            if stream_links:
                pi(f"   {G}Ссылки: {stream_links}{X}")
            if kw:
                pi(f"   {G}Ключевые слова: {kw}{X}")
            if not kw and not stream_links:
                pi(f"   {Y}(ничего не найдено){X}")
            p()
        pi(f"Итог: {mark(any_live)}")
    except Exception as e:
        pi(f"{R}Ошибка: {e}{X}")


# ══ VK группа ═════════════════════════════════════════════════

def test_vk_group(url):
    domain = slug(url)
    if not domain:
        pi(f"{R}URL пустой{X}"); return
    pi(f"Группа: vk.com/{domain}")
    token = config.VK_SERVICE_TOKEN
    if not token or "СЮДА" in token:
        pi(f"{Y}⚠ VK_SERVICE_TOKEN не заполнен — пропускаю{X}"); return
    try:
        r = requests.get("https://api.vk.com/method/wall.get", params={
            "domain": domain, "count": 5,
            "access_token": token, "v": "5.199",
        }, timeout=10)
        data = r.json()
        if "error" in data:
            pi(f"{R}VK API: {data['error']['error_msg']}{X}"); return
        items = data.get("response", {}).get("items", [])
        if not items:
            pi(f"{Y}⚠ Постов не найдено{X}"); return
        pi(f"Найдено постов: {len(items)}")
        p()
        any_live = False
        for i, post in enumerate(items, 1):
            text = post.get("text", "")
            attachments = post.get("attachments", [])
            al = [a.get("link", {}).get("url", "") for a in attachments if a.get("type") == "link"]
            il = re.findall(r'https?://\S+', text)
            all_links = al + il
            sl = [l for l in all_links if any(d in l for d in config.STREAM_LINK_DOMAINS)]
            full = text + " " + " ".join(all_links)
            kw, fl, is_live = check_keywords(full)
            any_live = any_live or is_live
            tag = f" {G}[→ СТРИМ]{X}" if is_live else ""
            pi(f"{C}── Пост #{i}{tag}{X}")
            short = text[:220].strip() or "(без текста)"
            pi(f"   Текст: {short}{'...' if len(text) > 220 else ''}")
            if sl:
                pi(f"   {G}Ссылки: {sl}{X}")
            if kw:
                pi(f"   {G}Ключевые слова: {kw}{X}")
            if not kw and not sl:
                pi(f"   {Y}(ничего не найдено){X}")
            p()
        pi(f"Итог: {mark(any_live)}")
    except Exception as e:
        pi(f"{R}Ошибка: {e}{X}")


# ══ Twitch ════════════════════════════════════════════════════

def test_twitch(url):
    login = slug(url)
    if not login:
        pi(f"{R}URL пустой{X}"); return
    pi(f"Логин: {login}")
    if config.TWITCH_CLIENT_ID and config.TWITCH_CLIENT_SECRET:
        try:
            tok = S.post("https://id.twitch.tv/oauth2/token", params={
                "client_id": config.TWITCH_CLIENT_ID,
                "client_secret": config.TWITCH_CLIENT_SECRET,
                "grant_type": "client_credentials",
            }, timeout=10).json().get("access_token")
            r = S.get("https://api.twitch.tv/helix/streams",
                      params={"user_login": login},
                      headers={"Client-ID": config.TWITCH_CLIENT_ID,
                               "Authorization": f"Bearer {tok}"},
                      timeout=10)
            data = r.json().get("data", [])
            pi("Метод: Twitch API")
            if data:
                from datetime import datetime, timezone
                started = data[0].get("started_at", "")
                mins = 0
                if started:
                    start = datetime.fromisoformat(started.replace("Z", "+00:00"))
                    mins = int((datetime.now(timezone.utc) - start).total_seconds() / 60)
                pi(f"{G}Стрим: {data[0].get('title','')} / {data[0].get('game_name','')}{X}")
                pi(f"{G}Идёт: {mins} мин{X}")
            pi(f"Итог: {mark(bool(data))}")
            return
        except Exception as e:
            pi(f"{Y}Twitch API недоступен: {e}{X}")
    try:
        r = S.get(url, timeout=15)
        live = "isLiveBroadcast" in r.text or "В ЭФИРЕ" in r.text
        pi("Метод: HTML парсинг")
        pi(f"{Y}⚠ Без API ключей Cloudflare может блокировать{X}")
        pi(f"Итог: {mark(live)}")
    except Exception as e:
        pi(f"{R}Ошибка: {e}{X}")


# ══ YouTube ═══════════════════════════════════════════════════

def test_youtube(url):
    if not url:
        pi(f"{R}URL пустой{X}"); return
    live_url = url if url.endswith("/live") else url.rstrip("/") + "/live"
    pi(f"URL: {live_url}")
    if config.YOUTUBE_API_KEY:
        path = urlparse(url).path.strip("/").split("/")
        ch_id = next((p for p in path if p.startswith("@") or p.startswith("UC")), path[-1])
        try:
            r = S.get("https://www.googleapis.com/youtube/v3/search", params={
                "part": "snippet", "channelId": ch_id,
                "eventType": "live", "type": "video",
                "key": config.YOUTUBE_API_KEY,
            }, timeout=10)
            items = r.json().get("items", [])
            pi("Метод: YouTube API")
            if items:
                vid = items[0]["id"]["videoId"]
                pi(f"{G}Стрим: {items[0]['snippet'].get('title','')}{X}")
                r2 = S.get("https://www.googleapis.com/youtube/v3/videos", params={
                    "part": "liveStreamingDetails", "id": vid,
                    "key": config.YOUTUBE_API_KEY,
                }, timeout=10)
                start_str = r2.json().get("items",[{}])[0].get("liveStreamingDetails",{}).get("actualStartTime","")
                if start_str:
                    from datetime import datetime, timezone
                    start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    mins = int((datetime.now(timezone.utc) - start).total_seconds() / 60)
                    pi(f"{G}Идёт: {mins} мин{X}")
            pi(f"Итог: {mark(bool(items))}")
            return
        except Exception as e:
            pi(f"{Y}YouTube API недоступен: {e}{X}")
    try:
        r = S.get(live_url, timeout=15)
        live = ('"liveBroadcastContent":"live"' in r.text or
                "isLiveBroadcast" in r.text or "ЭФИР" in r.text)
        pi("Метод: HTML парсинг")
        pi(f"Итог: {mark(live)}")
    except Exception as e:
        pi(f"{R}Ошибка: {e}{X}")


# ══ Kick ══════════════════════════════════════════════════════

def test_kick(url):
    login = slug(url)
    if not login:
        pi(f"{R}URL пустой{X}"); return
    pi(f"Логин: {login}")
    try:
        r = S.get(f"https://kick.com/api/v1/channels/{login}", timeout=15)
        ls = r.json().get("livestream")
        pi("Метод: Kick API")
        if ls:
            pi(f"{G}Стрим: {ls.get('session_title','')}{X}")
            r2 = S.get(url, timeout=15)
            soup = BeautifulSoup(r2.text, "html.parser")
            timer = soup.find("span", class_=lambda c: c and "tabular-nums" in c)
            if timer and ":" in timer.get_text():
                pi(f"{G}Таймер: {timer.get_text(strip=True)}{X}")
        pi(f"Итог: {mark(bool(ls))}")
    except Exception as e:
        pi(f"{R}Ошибка: {e}{X}")


# ══ VK Play Live ══════════════════════════════════════════════

def test_vkplay(url):
    login = slug(url)
    if not login:
        pi(f"{R}URL пустой{X}"); return
    pi(f"Логин: {login}")
    try:
        r = S.get(f"https://api.vkplay.live/v1/blog/{login}/public_video_stream", timeout=15)
        data = r.json()
        pi(f"Тип ответа API: {type(data).__name__}")
        if isinstance(data, list):
            online = any(item.get("isOnline") or item.get("data", {}).get("isOnline")
                         for item in data if isinstance(item, dict))
            title  = next((item.get("title","") or item.get("data",{}).get("title","")
                           for item in data if isinstance(item, dict)
                           if item.get("isOnline") or item.get("data",{}).get("isOnline")), "")
        else:
            inner = data.get("data", {})
            if isinstance(inner, list):
                online = any(item.get("isOnline") for item in inner if isinstance(item, dict))
                title  = next((item.get("title","") for item in inner
                               if isinstance(item, dict) and item.get("isOnline")), "")
            else:
                online = bool(inner.get("isOnline"))
                title  = inner.get("title", "")
        if online:
            pi(f"{G}Стрим: {title}{X}")
            r2 = S.get(url, timeout=15)
            soup = BeautifulSoup(r2.text, "html.parser")
            timer = soup.find(class_=lambda c: c and "ChannelStreamPanel_timer" in c)
            if timer:
                pi(f"{G}Таймер: {timer.get_text(strip=True)}{X}")
        pi(f"Итог: {mark(online)}")
    except Exception as e:
        pi(f"{R}Ошибка: {e}{X}")


# ══ Запуск ════════════════════════════════════════════════════

TESTS = [
    ("twitch",   "🟣 Twitch",        test_twitch),
    ("youtube",  "🔴 YouTube",       test_youtube),
    ("kick",     "🟢 Kick",          test_kick),
    ("vkplay",   "🔵 VK Play Live",  test_vkplay),
    ("telegram", "✈️  Telegram",     test_telegram),
    ("vk_group", "💙 Группа ВК",    test_vk_group),
]

def run():
    p()
    p(f"{B}{'═'*55}{X}")
    p(f"{B}  РУЧНАЯ ПРОВЕРКА ВСЕХ ИСТОЧНИКОВ{X}")
    p(f"{B}{'═'*55}{X}")
    p(f"  Ключевых слов: {len(config.STREAM_KEYWORDS)}  |  "
      f"Мин. совпадений: {config.KEYWORD_MIN_MATCHES}  |  "
      f"Доменов: {len(config.STREAM_LINK_DOMAINS)}")
    p()

    for streamer in config.STREAMERS:
        p(f"{B}┌{'─'*53}┐{X}")
        p(f"{B}│  🎮 {streamer['name']}  (id: {streamer['id']}){X}")
        p(f"{B}└{'─'*53}┘{X}")

        for key, label, fn in TESTS:
            url = streamer.get(key, "")
            if not url:
                continue
            p()
            p(f"{B}  {label}{X}")
            p(f"  URL: {url}")
            p(f"  {SEP}")
            fn(url)

        p()

    p(f"{B}{'═'*55}{X}")
    p(f"{B}  ПРОВЕРКА ЗАВЕРШЕНА{X}")
    p(f"{B}{'═'*55}{X}")
    p()

if __name__ == "__main__":
    run()
