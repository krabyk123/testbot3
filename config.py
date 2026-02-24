# ================================================================
# config.py — ВСЕ настройки бота
# ================================================================
#
#  ОБЯЗАТЕЛЬНО ЗАПОЛНИТЬ:
#    1. VK_TOKEN         — токен вашей группы-бота
#    2. VK_GROUP_ID      — ID вашей группы-бота
#    3. VK_SERVICE_TOKEN — сервисный ключ (чтение групп стримеров)
#    4. ADMIN_IDS        — ваш VK user ID (для админ-команд)
#    5. STREAMERS        — ссылки на стримеров
#
#  ОПЦИОНАЛЬНО (рекомендуется):
#    6. TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET
#    7. YOUTUBE_API_KEY
# ================================================================


# ── 1. Токен группы-бота ───────────────────────────────────────
# vk.com → Ваша группа → Управление → Работа с API → Ключи доступа
# Права: ✅ Сообщения, ✅ Управление
VK_TOKEN = "vk1.a.M2NzVybh-yEfXDAM5cS0Yv5TawW50Vf40_7JWXuu2kI7ekAQZ27gAM4drtLQPAhmP1jerRevby_XsaWec7X0efEZkgBv_B-XaGGeJBN-_A4_jKMcsUDrjSkHfar7HTLXOdSR7fEVa8Y8DBbeIN6vAeeqBwx8avNUD8VGutkvCP9T90C5NRj5pEVk_ZJYXB6xJpbfdz4NLKVQyFFDg40W1Q"

# ── 2. ID группы-бота ──────────────────────────────────────────
# URL группы: vk.com/clubЧИСЛО — это и есть ID
VK_GROUP_ID = 236231799

# ── 3. Сервисный ключ VK ───────────────────────────────────────
# vk.com/dev → Мои приложения → Создать → Мини-приложение
# → Настройки → Сервисный ключ доступа
VK_SERVICE_TOKEN = "989ef03d989ef03d989ef03d1e9ba1f8389989e989ef03df10343c3f897ec2e36948d3d"

# ── 4. Список администраторов ──────────────────────────────────
# Ваш VK user ID (число из vk.com/id ЧИСЛО)
# Администраторы могут использовать служебные команды бота
ADMIN_IDS = [0]  # ← замени на свой VK user ID  # например: [12345678]

# ── 5. Список стримеров ────────────────────────────────────────
STREAMERS = [
    {
        "id":       "hardplay",
        "name":     "HARD PLAY",
        "twitch":   "https://twitch.tv/hardgamechannel",
        "youtube":  "https://www.youtube.com/@hardplayyt/live",
        "kick":     "https://kick.com/hardplayofficial",
        "vkplay":   "https://live.vkvideo.ru/hardplay",
        "telegram": "https://t.me/hplegion",
        "vk_group": "https://vk.com/hp_legion",
    },

    # Шаблон — раскомментируй и заполни:
    # {
    #     "id":       "streamer2",
    #     "name":     "Имя Стримера",
    #     "twitch":   "https://twitch.tv/LOGIN",
    #     "youtube":  "https://www.youtube.com/@HANDLE/live",
    #     "kick":     "https://kick.com/LOGIN",
    #     "vkplay":   "https://live.vkvideo.ru/LOGIN",
    #     "telegram": "https://t.me/CHANNEL",
    #     "vk_group": "https://vk.com/GROUP",
    # },
]

# ── 6. Twitch API ──────────────────────────────────────────────
# Без ключей Cloudflare блокирует HTML-парсинг!
# Бесплатно: https://dev.twitch.tv/console/apps
TWITCH_CLIENT_ID     = ""
TWITCH_CLIENT_SECRET = ""

# ── 7. YouTube API ─────────────────────────────────────────────
# Бесплатно: console.cloud.google.com → YouTube Data API v3
YOUTUBE_API_KEY = ""


# ── Настройки проверки ─────────────────────────────────────────
CHECK_INTERVAL_SECONDS = 60    # интервал проверки платформ

# Если бот перезапустился и нашёл уже идущий стрим —
# уведомить только если стрим идёт НЕ ДОЛЬШЕ этого числа минут
MAX_LATE_NOTIFY_MIN = 30

# Ключевые слова для постов в TG и ВК группе
KEYWORD_MIN_MATCHES = 1
STREAM_KEYWORDS = {
    "стрим", "stream", "live", "лайв", "эфир", "трансляция",
    "начал", "стримим", "в эфире", "онлайн стрим", "смотрите",
}
STREAM_LINK_DOMAINS = [
    "twitch.tv", "youtube.com/watch", "youtube.com/live",
    "youtu.be", "kick.com", "vkplay.live", "live.vkvideo.ru",
]


# ── Тексты сообщений ───────────────────────────────────────────
MSG_WELCOME = (
    "👋 Привет! Я бот уведомлений о стримах.\n\n"
    "Выбери стримеров — нажми на имя чтобы подписаться.\n"
    "✅ — подписан  |  ➕ — не подписан\n\n"
    "Как только стример выйдет в эфир — ты получишь уведомление!"
)
MSG_SUBSCRIBED   = "✅ Подписка на {name} включена!"
MSG_UNSUBSCRIBED = "❌ Подписка на {name} отключена."
MSG_NO_SUBS      = "У тебя пока нет подписок. Нажми /start чтобы выбрать стримеров."
MSG_LIVE         = "🔴 {name} в эфире!\n{platform_icon} {platform_name}: {url}"
MSG_LIVE_LATE    = "🔴 {name} в эфире!\n{platform_icon} {platform_name}: {url}\n⏱ Стрим идёт уже {minutes} мин."
