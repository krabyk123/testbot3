"""
bot.py — главный файл. Запускать: python bot.py

Что умеет:
  • Подписка/отписка на стримеров через VK-кнопки
  • Уведомления только при начале стрима на реальных площадках
  • При перезапуске — уведомляет если стрим идёт < 30 мин
  • Не падает при разрыве VK LongPoll — переподключается сам
  • Не падает если пользователь заблокировал бота
  • Админ-команды для мониторинга
"""
import logging, threading, time, json, signal, sys
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.exceptions import ApiError

import config, database as db, checker as chk

# ─── Логирование ──────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger("bot")

# ─── VK сессия ────────────────────────────────────────────────

vk_session = vk_api.VkApi(token=config.VK_TOKEN)
vk = vk_session.get_api()

# Платформы, которые шлют уведомления (TG и ВК — только вспомогательные)
NOTIFY_PLATFORMS = {"twitch", "youtube", "kick", "vkplay"}


# ─── Отправка сообщений ───────────────────────────────────────

def send(user_id: int, text: str, keyboard: str | None = None) -> bool:
    """
    Отправить сообщение пользователю.
    Если пользователь заблокировал бота — помечаем и пропускаем.
    Возвращает True при успехе.
    """
    try:
        params = dict(
            user_id=user_id,
            message=text,
            random_id=int(time.time() * 1000) % 2**31,
        )
        if keyboard:
            params["keyboard"] = keyboard
        vk.messages.send(**params)
        return True
    except ApiError as e:
        code = e.code if hasattr(e, "code") else 0
        if code in (901, 902):
            # Пользователь заблокировал бота или запретил сообщения
            log.warning("User %s blocked bot, marking", user_id)
            db.mark_blocked(user_id)
        else:
            log.error("send %s (ApiError %s): %s", user_id, code, e)
    except Exception as e:
        log.error("send %s: %s", user_id, e)
    return False

def send_many(user_ids: list[int], text: str):
    """Разослать сообщение списку пользователей с паузой (анти-флуд VK)."""
    for i, uid in enumerate(user_ids):
        send(uid, text)
        if i > 0 and i % 20 == 0:
            time.sleep(1)  # VK: не более 20 сообщений/сек


# ─── Клавиатура ───────────────────────────────────────────────

def build_keyboard(user_id: int) -> str:
    kb = VkKeyboard(one_time=False, inline=False)
    for streamer in config.STREAMERS:
        subscribed = db.is_subscribed(user_id, streamer["id"])
        label = f"{'✅' if subscribed else '➕'} {streamer['name']}"
        kb.add_button(
            label,
            color=VkKeyboardColor.POSITIVE if subscribed else VkKeyboardColor.SECONDARY,
            payload=json.dumps({"cmd": "toggle", "sid": streamer["id"]})
        )
        kb.add_line()
    kb.add_button("📋 Мои подписки", color=VkKeyboardColor.PRIMARY,
                  payload=json.dumps({"cmd": "mysubs"}))
    kb.add_button("❌ Отписаться от всех", color=VkKeyboardColor.NEGATIVE,
                  payload=json.dumps({"cmd": "unsub_all"}))
    return kb.get_keyboard()


# ─── Обработка сообщений ──────────────────────────────────────

def handle(user_id: int, text: str, payload: dict | None):
    db.touch_user(user_id)
    text_lower = text.strip().lower()
    is_admin = user_id in config.ADMIN_IDS

    # ── Кнопка: переключить подписку ──
    if payload and payload.get("cmd") == "toggle":
        sid = payload["sid"]
        streamer = next((s for s in config.STREAMERS if s["id"] == sid), None)
        if not streamer:
            return
        if db.is_subscribed(user_id, sid):
            db.unsubscribe(user_id, sid)
            msg = config.MSG_UNSUBSCRIBED.format(name=streamer["name"])
        else:
            db.subscribe(user_id, sid)
            msg = config.MSG_SUBSCRIBED.format(name=streamer["name"])
        send(user_id, msg, keyboard=build_keyboard(user_id))
        return

    # ── Кнопка: мои подписки ──
    if (payload and payload.get("cmd") == "mysubs") or text_lower in ("/list", "мои подписки"):
        subs = db.get_user_subscriptions(user_id)
        if not subs:
            send(user_id, config.MSG_NO_SUBS, keyboard=build_keyboard(user_id))
        else:
            names = [s["name"] for s in config.STREAMERS if s["id"] in subs]
            send(user_id,
                 "📋 Твои подписки:\n" + "\n".join(f"• {n}" for n in names),
                 keyboard=build_keyboard(user_id))
        return

    # ── Кнопка: отписаться от всех ──
    if (payload and payload.get("cmd") == "unsub_all") or text_lower in ("/stop", "stop", "отписаться"):
        db.unsubscribe_all(user_id)
        send(user_id, "❌ Ты отписан от всех стримеров.", keyboard=build_keyboard(user_id))
        return

    # ── /start ──
    if text_lower in ("/start", "start", "начать", "привет"):
        send(user_id, config.MSG_WELCOME, keyboard=build_keyboard(user_id))
        return

    # ── Админ-команды ──
    if is_admin:
        if text_lower == "/stats":
            _cmd_stats(user_id)
            return
        if text_lower == "/streamers":
            _cmd_streamers(user_id)
            return
        if text_lower.startswith("/broadcast "):
            msg = text.strip()[len("/broadcast "):]
            _cmd_broadcast(user_id, msg)
            return

    # ── Всё остальное ──
    send(user_id,
         "Используй кнопки ниже для управления подписками.\n"
         "Напиши /start чтобы увидеть меню.",
         keyboard=build_keyboard(user_id))


# ─── Админ-команды ────────────────────────────────────────────

def _cmd_stats(admin_id: int):
    total = db.get_all_subscribers_count()
    by_streamer = db.get_subscribers_count_by_streamer()
    lines = [f"📊 Статистика бота\n",
             f"Всего уникальных подписчиков: {total}\n"]
    for row in by_streamer:
        name = next((s["name"] for s in config.STREAMERS
                     if s["id"] == row["streamer_id"]), row["streamer_id"])
        lines.append(f"• {name}: {row['count']} чел.")
    send(admin_id, "\n".join(lines))

def _cmd_streamers(admin_id: int):
    lines = ["📡 Текущее состояние стримеров:\n"]
    for s in config.STREAMERS:
        live_platforms = [
            pid for pid in NOTIFY_PLATFORMS
            if db.get_live(s["id"], pid)
        ]
        status = "🔴 LIVE: " + ", ".join(live_platforms) if live_platforms else "⚫ офлайн"
        lines.append(f"• {s['name']} — {status}")
    send(admin_id, "\n".join(lines))

def _cmd_broadcast(admin_id: int, message: str):
    if not message:
        send(admin_id, "Использование: /broadcast текст сообщения")
        return
    # Собрать всех уникальных подписчиков
    all_users: set[int] = set()
    for s in config.STREAMERS:
        all_users.update(db.get_subscribers_of(s["id"]))
    send(admin_id, f"📤 Рассылка {len(all_users)} пользователям...")
    send_many(list(all_users), message)
    send(admin_id, f"✅ Рассылка завершена.")
    log.info("Broadcast by admin %s: %d users", admin_id, len(all_users))


# ─── Цикл проверки стримов ────────────────────────────────────

def check_loop():
    log.info("Checker started (interval=%ds)", config.CHECK_INTERVAL_SECONDS)
    while True:
        try:
            _do_checks()
        except Exception as e:
            log.error("check_loop unhandled: %s", e)
        time.sleep(config.CHECK_INTERVAL_SECONDS)


def _do_checks():
    for streamer in config.STREAMERS:
        results = chk.check_streamer(streamer)

        for res in results:
            pid  = res["platform"]
            live = res["is_live"]
            was  = db.get_live(streamer["id"], pid)

            # Уведомляем только реальные стрим-площадки
            if pid in NOTIFY_PLATFORMS and live and not was:
                _notify_live(streamer, res)

            db.set_live(streamer["id"], pid, live)


def _notify_live(streamer: dict, res: dict):
    pid = res["platform"]
    url = res["url"]

    # Проверяем длительность стрима
    duration = chk.get_stream_duration(pid, url)

    if duration > config.MAX_LATE_NOTIFY_MIN:
        log.info("SKIP %s/%s — стрим идёт %d мин (> %d)",
                 streamer["id"], pid, duration, config.MAX_LATE_NOTIFY_MIN)
        return

    parts = res["icon"].split(" ", 1)
    icon  = parts[0]
    pname = parts[1] if len(parts) > 1 else ""

    if duration > 0:
        text = config.MSG_LIVE_LATE.format(
            name=streamer["name"],
            platform_icon=icon,
            platform_name=pname,
            url=url,
            minutes=duration,
        )
    else:
        text = config.MSG_LIVE.format(
            name=streamer["name"],
            platform_icon=icon,
            platform_name=pname,
            url=url,
        )

    users = db.get_subscribers_of(streamer["id"])
    log.info("LIVE %s/%s ~%dмин → %d users", streamer["id"], pid, duration, len(users))
    send_many(users, text)


# ─── VK LongPoll — с автоперезапуском ────────────────────────

def poll_loop():
    log.info("LongPoll started")
    while True:
        try:
            lp = VkLongPoll(vk_session)
            for event in lp.listen():
                if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                    payload = None
                    try:
                        raw = event.extra_values.get("payload")
                        if raw:
                            payload = json.loads(raw)
                    except Exception:
                        pass
                    try:
                        handle(event.user_id, event.text or "", payload)
                    except Exception as e:
                        log.error("handle %s: %s", event.user_id, e)
        except KeyboardInterrupt:
            log.info("Остановка по Ctrl+C")
            sys.exit(0)
        except Exception as e:
            log.warning("LongPoll упал, переподключение через 5 сек: %s", e)
            time.sleep(5)


# ─── Точка входа ──────────────────────────────────────────────

if __name__ == "__main__":
    log.info("=== Бот запускается ===")
    db.init()

    # Поток проверки стримов
    t = threading.Thread(target=check_loop, daemon=True, name="checker")
    t.start()

    # Основной поток — VK LongPoll
    poll_loop()
