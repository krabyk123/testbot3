"""
test_notify.py — ручная проверка отправки уведомлений.
Запуск: python test_notify.py
"""
import time
import vk_api
import config

vk_session = vk_api.VkApi(token=config.VK_TOKEN)
vk = vk_session.get_api()

# ← Вставь свой VK user ID (число из vk.com/idЧИСЛО)
MY_USER_ID = 427099655

if MY_USER_ID == 0:
    print("❌ Заполни MY_USER_ID в файле test_notify.py")
    exit(1)

msg = (
    "🔴 ТЕСТ — HARD PLAY в эфире!\n"
    "🟣 Twitch: https://twitch.tv/hardgamechannel\n\n"
    "Если видишь это — уведомления работают ✅"
)

try:
    vk.messages.send(
        user_id=MY_USER_ID,
        message=msg,
        random_id=int(time.time()),
    )
    print("✅ Сообщение отправлено! Проверь ВК.")
except Exception as e:
    print(f"❌ Ошибка: {e}")
