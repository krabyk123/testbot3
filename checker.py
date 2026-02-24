"""
checker.py — проверка стримов по публичным URL + определение длительности.
Стримеру не нужно давать никаких прав и доступов.
"""
import logging, re
from datetime import datetime, timezone
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import config

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
S = requests.Session()
S.headers.update(HEADERS)


# ─── Вспомогательные функции ───────────────────────────────────

def _slug(url: str) -> str:
    if not url:
        return ""
    path = urlparse(url).path.strip("/").split("/")
    parts = [p for p in path if p and p not in ("live", "stream", "streams", "c", "user")]
    return parts[-1].lstrip("@") if parts else ""

def _yt_channel_id(url: str) -> str:
    path = urlparse(url).path.strip("/").split("/")
    for i, p in enumerate(path):
        if p == "channel" and i + 1 < len(path):
            return path[i + 1]
        if p.startswith("@"):
            return p
        if p in ("c", "user") and i + 1 < len(path):
            return path[i + 1]
    return path[-1] if path else ""

def _is_stream_post(text: str) -> bool:
    text_lower = text.lower()
    for domain in config.STREAM_LINK_DOMAINS:
        if domain in text_lower:
            return True
    hits = sum(1 for kw in config.STREAM_KEYWORDS if kw in text_lower)
    return hits >= config.KEYWORD_MIN_MATCHES

def _parse_timer(time_str: str) -> int:
    """'HH:MM:SS' или 'MM:SS' → минуты."""
    try:
        parts = time_str.strip().split(":")
        if len(parts) == 3:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 2:
            return int(parts[0])
    except Exception:
        pass
    return 0


# ─── Twitch ────────────────────────────────────────────────────

_tw_token: str | None = None

def _tw_oauth() -> str | None:
    global _tw_token
    if _tw_token:
        return _tw_token
    if not (config.TWITCH_CLIENT_ID and config.TWITCH_CLIENT_SECRET):
        return None
    try:
        r = S.post("https://id.twitch.tv/oauth2/token", params={
            "client_id": config.TWITCH_CLIENT_ID,
            "client_secret": config.TWITCH_CLIENT_SECRET,
            "grant_type": "client_credentials",
        }, timeout=10)
        _tw_token = r.json().get("access_token")
        return _tw_token
    except Exception as e:
        log.error("Twitch OAuth: %s", e)
        return None

def _tw_stream_data(login: str) -> dict | None:
    """Возвращает данные стрима из Twitch API или None."""
    token = _tw_oauth()
    if not token:
        return None
    try:
        r = S.get("https://api.twitch.tv/helix/streams",
                  params={"user_login": login},
                  headers={"Client-ID": config.TWITCH_CLIENT_ID,
                           "Authorization": f"Bearer {token}"},
                  timeout=10)
        data = r.json().get("data", [])
        return data[0] if data else None
    except Exception as e:
        log.warning("Twitch API: %s", e)
        return None

def check_twitch(url: str) -> bool:
    login = _slug(url)
    if not login:
        return False
    stream = _tw_stream_data(login)
    if stream is not None:
        return True
    # Fallback HTML
    try:
        r = S.get(url, timeout=15)
        return "isLiveBroadcast" in r.text or "В ЭФИРЕ" in r.text
    except Exception as e:
        log.error("Twitch HTML: %s", e)
    return False

def get_duration_twitch(url: str) -> int:
    """Минуты с начала стрима на Twitch (через API)."""
    login = _slug(url)
    if not login:
        return 0
    stream = _tw_stream_data(login)
    if stream:
        started_at = stream.get("started_at", "")
        if started_at:
            try:
                start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                return int((datetime.now(timezone.utc) - start).total_seconds() / 60)
            except Exception:
                pass
    return 0


# ─── YouTube ───────────────────────────────────────────────────

def _yt_live_video_id(ch_id: str) -> str | None:
    if not config.YOUTUBE_API_KEY:
        return None
    try:
        r = S.get("https://www.googleapis.com/youtube/v3/search", params={
            "part": "snippet", "channelId": ch_id,
            "eventType": "live", "type": "video",
            "key": config.YOUTUBE_API_KEY,
        }, timeout=10)
        items = r.json().get("items", [])
        return items[0]["id"]["videoId"] if items else None
    except Exception as e:
        log.warning("YT search API: %s", e)
        return None

def check_youtube(url: str) -> bool:
    if not url:
        return False
    if config.YOUTUBE_API_KEY:
        ch_id = _yt_channel_id(url)
        vid = _yt_live_video_id(ch_id)
        if vid is not None:
            return bool(vid)
    live_url = url if url.endswith("/live") else url.rstrip("/") + "/live"
    try:
        r = S.get(live_url, timeout=15)
        return ('"liveBroadcastContent":"live"' in r.text or
                "isLiveBroadcast" in r.text or "ЭФИР" in r.text)
    except Exception as e:
        log.error("YT HTML: %s", e)
    return False

def get_duration_youtube(url: str) -> int:
    """Минуты с начала стрима на YouTube (через API)."""
    if not config.YOUTUBE_API_KEY:
        return 0
    ch_id = _yt_channel_id(url)
    vid = _yt_live_video_id(ch_id)
    if not vid:
        return 0
    try:
        r = S.get("https://www.googleapis.com/youtube/v3/videos", params={
            "part": "liveStreamingDetails", "id": vid,
            "key": config.YOUTUBE_API_KEY,
        }, timeout=10)
        start_str = (r.json().get("items", [{}])[0]
                     .get("liveStreamingDetails", {})
                     .get("actualStartTime", ""))
        if start_str:
            start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            return int((datetime.now(timezone.utc) - start).total_seconds() / 60)
    except Exception as e:
        log.error("YT duration: %s", e)
    return 0


# ─── Kick ──────────────────────────────────────────────────────

def _kick_data(login: str) -> dict | None:
    try:
        r = S.get(f"https://kick.com/api/v1/channels/{login}", timeout=15)
        return r.json()
    except Exception:
        return None

def check_kick(url: str) -> bool:
    login = _slug(url)
    if not login:
        return False
    data = _kick_data(login)
    if data is not None:
        return bool(data.get("livestream"))
    try:
        r = S.get(url, timeout=15)
        return "bg-green-500" in r.text and "LIVE" in r.text
    except Exception as e:
        log.error("Kick: %s", e)
    return False

def get_duration_kick(url: str) -> int:
    """Минуты с начала стрима на Kick (через HTML таймер)."""
    try:
        r = S.get(url, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        timer = soup.find("span", class_=lambda c: c and "tabular-nums" in c)
        if timer:
            text = timer.get_text(strip=True)
            if ":" in text:
                return _parse_timer(text)
    except Exception as e:
        log.error("Kick duration: %s", e)
    return 0


# ─── VK Play Live ─────────────────────────────────────────────

def _vkplay_inner(data) -> dict | list | None:
    """Извлечь внутренние данные из ответа VK Play API."""
    if isinstance(data, dict):
        return data.get("data")
    return data

def check_vkplay(url: str) -> bool:
    login = _slug(url)
    if not login:
        return False
    try:
        r = S.get(f"https://api.vkplay.live/v1/blog/{login}/public_video_stream", timeout=15)
        inner = _vkplay_inner(r.json())
        if isinstance(inner, list):
            return any(item.get("isOnline") for item in inner if isinstance(item, dict))
        elif isinstance(inner, dict):
            return bool(inner.get("isOnline"))
    except Exception:
        pass
    try:
        r = S.get(url, timeout=15)
        return "StreamStatus_isOnline" in r.text or '"isOnline":true' in r.text
    except Exception as e:
        log.error("VKPlay: %s", e)
    return False

def get_duration_vkplay(url: str) -> int:
    """Минуты с начала стрима на VK Play Live (через HTML таймер)."""
    try:
        r = S.get(url, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        timer = soup.find(class_=lambda c: c and "ChannelStreamPanel_timer" in c)
        if timer:
            return _parse_timer(timer.get_text(strip=True))
    except Exception as e:
        log.error("VKPlay duration: %s", e)
    return 0


# ─── Telegram ─────────────────────────────────────────────────

def check_telegram(url: str) -> bool:
    channel = _slug(url)
    if not channel:
        return False
    try:
        r = S.get(f"https://t.me/s/{channel}", timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        posts = soup.find_all(class_="tgme_widget_message_wrap")[-5:]
        for post in posts:
            text = post.get_text(separator=" ")
            links = [a.get("href", "") for a in post.find_all("a")]
            if _is_stream_post(text + " " + " ".join(links)):
                return True
    except Exception as e:
        log.error("Telegram: %s", e)
    return False


# ─── VK группа ────────────────────────────────────────────────

def check_vk_group(url: str) -> bool:
    domain = _slug(url)
    if not domain:
        return False
    try:
        r = requests.get("https://api.vk.com/method/wall.get", params={
            "domain": domain, "count": 5,
            "access_token": config.VK_SERVICE_TOKEN, "v": "5.199",
        }, timeout=10)
        items = r.json().get("response", {}).get("items", [])
        for post in items:
            text = post.get("text", "")
            attachments = post.get("attachments", [])
            extra = " ".join(a.get("link", {}).get("url", "")
                             for a in attachments if a.get("type") == "link")
            inline = " ".join(re.findall(r'https?://\S+', text))
            if _is_stream_post(text + " " + extra + " " + inline):
                return True
    except Exception as e:
        log.error("VK group: %s", e)
    return False


# ─── Длительность (универсальная) ─────────────────────────────

def get_stream_duration(platform: str, url: str) -> int:
    """Возвращает минуты текущего стрима. 0 если неизвестно."""
    funcs = {
        "twitch":  get_duration_twitch,
        "youtube": get_duration_youtube,
        "kick":    get_duration_kick,
        "vkplay":  get_duration_vkplay,
    }
    fn = funcs.get(platform)
    if fn:
        try:
            return fn(url)
        except Exception as e:
            log.error("duration %s: %s", platform, e)
    return 0


# ─── Общая проверка стримера ──────────────────────────────────

PLATFORMS = [
    ("twitch",   "🟣 Twitch",       check_twitch,    lambda s: s.get("twitch", "")),
    ("youtube",  "🔴 YouTube",      check_youtube,   lambda s: s.get("youtube", "")),
    ("kick",     "🟢 Kick",         check_kick,      lambda s: s.get("kick", "")),
    ("vkplay",   "🔵 VK Play Live", check_vkplay,    lambda s: s.get("vkplay", "")),
    ("telegram", "✈️ Telegram",     check_telegram,  lambda s: s.get("telegram", "")),
    ("vk_group", "💙 ВКонтакте",    check_vk_group,  lambda s: s.get("vk_group", "")),
]

def check_streamer(streamer: dict) -> list[dict]:
    results = []
    for pid, icon, fn, get_url in PLATFORMS:
        url = get_url(streamer)
        if not url:
            continue
        try:
            live = fn(url)
        except Exception as e:
            log.error("check %s/%s: %s", streamer["id"], pid, e)
            live = False
        results.append({"platform": pid, "icon": icon, "is_live": live, "url": url})
    return results
