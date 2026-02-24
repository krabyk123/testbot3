"""
database.py — SQLite: подписки, состояние стримов, статистика
"""
import sqlite3, os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "bot.db")


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _conn() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id     INTEGER NOT NULL,
                streamer_id TEXT    NOT NULL,
                created_at  TEXT    DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, streamer_id)
            );
            CREATE TABLE IF NOT EXISTS stream_state (
                streamer_id TEXT    NOT NULL,
                platform    TEXT    NOT NULL,
                is_live     INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (streamer_id, platform)
            );
            CREATE TABLE IF NOT EXISTS users (
                user_id    INTEGER PRIMARY KEY,
                first_seen TEXT DEFAULT (datetime('now')),
                last_seen  TEXT DEFAULT (datetime('now')),
                blocked    INTEGER DEFAULT 0
            );
        """)


# ── Подписки ──────────────────────────────────────────────────

def subscribe(user_id: int, streamer_id: str):
    with _conn() as db:
        db.execute("INSERT OR IGNORE INTO subscriptions VALUES (?,?,datetime('now'))",
                   (user_id, streamer_id))

def unsubscribe(user_id: int, streamer_id: str):
    with _conn() as db:
        db.execute("DELETE FROM subscriptions WHERE user_id=? AND streamer_id=?",
                   (user_id, streamer_id))

def is_subscribed(user_id: int, streamer_id: str) -> bool:
    with _conn() as db:
        return bool(db.execute(
            "SELECT 1 FROM subscriptions WHERE user_id=? AND streamer_id=?",
            (user_id, streamer_id)
        ).fetchone())

def get_user_subscriptions(user_id: int) -> list[str]:
    with _conn() as db:
        rows = db.execute(
            "SELECT streamer_id FROM subscriptions WHERE user_id=?", (user_id,)
        ).fetchall()
    return [r["streamer_id"] for r in rows]

def get_subscribers_of(streamer_id: str) -> list[int]:
    """Подписчики стримера (не заблокированные)."""
    with _conn() as db:
        rows = db.execute("""
            SELECT s.user_id FROM subscriptions s
            LEFT JOIN users u ON s.user_id = u.user_id
            WHERE s.streamer_id=? AND (u.blocked IS NULL OR u.blocked=0)
        """, (streamer_id,)).fetchall()
    return [r["user_id"] for r in rows]

def unsubscribe_all(user_id: int):
    with _conn() as db:
        db.execute("DELETE FROM subscriptions WHERE user_id=?", (user_id,))

def get_all_subscribers_count() -> int:
    with _conn() as db:
        row = db.execute("SELECT COUNT(DISTINCT user_id) as c FROM subscriptions").fetchone()
    return row["c"] if row else 0

def get_subscribers_count_by_streamer() -> list[dict]:
    with _conn() as db:
        rows = db.execute("""
            SELECT streamer_id, COUNT(*) as cnt
            FROM subscriptions GROUP BY streamer_id
        """).fetchall()
    return [{"streamer_id": r["streamer_id"], "count": r["cnt"]} for r in rows]


# ── Пользователи ──────────────────────────────────────────────

def touch_user(user_id: int):
    """Зафиксировать активность пользователя."""
    with _conn() as db:
        db.execute("""
            INSERT INTO users (user_id) VALUES (?)
            ON CONFLICT(user_id) DO UPDATE SET
                last_seen = datetime('now'),
                blocked   = 0
        """, (user_id,))

def mark_blocked(user_id: int):
    """Пользователь заблокировал бота — не слать ему сообщения."""
    with _conn() as db:
        db.execute("""
            INSERT INTO users (user_id, blocked) VALUES (?, 1)
            ON CONFLICT(user_id) DO UPDATE SET blocked=1
        """, (user_id,))


# ── Состояние стримов ─────────────────────────────────────────

def get_live(streamer_id: str, platform: str) -> bool:
    with _conn() as db:
        row = db.execute(
            "SELECT is_live FROM stream_state WHERE streamer_id=? AND platform=?",
            (streamer_id, platform)
        ).fetchone()
    return bool(row["is_live"]) if row else False

def set_live(streamer_id: str, platform: str, is_live: bool):
    with _conn() as db:
        db.execute("""
            INSERT INTO stream_state (streamer_id, platform, is_live) VALUES (?,?,?)
            ON CONFLICT(streamer_id, platform) DO UPDATE SET is_live=excluded.is_live
        """, (streamer_id, platform, int(is_live)))
