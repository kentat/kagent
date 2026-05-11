"""
ストレージ抽象レイヤー
====================================================
現在の実装: SQLite + インメモリ辞書
将来の移行先: Redis

【Redis移行時の対応表】
┌─────────────────────┬──────────────────────────────────────┐
│ 現在（SQLite/Memory）│ Redis移行後                          │
├─────────────────────┼──────────────────────────────────────┤
│ _conversations dict │ Redis Hash: conversation:{user_id}   │
│ SQLite notes        │ Redis List: notes:{user_id}          │
│ SQLite tasks        │ Redis Hash: task:{task_id}           │
│ SQLite yt_channels  │ Redis String: yt:channel:{handle}    │
└─────────────────────┴──────────────────────────────────────┘

Redis移行時にやること:
1. pip install redis
2. REDIS_URL を Railway 環境変数に追加
3. このファイルの実装部分を redis.Redis() に置き換える
4. tools.py・main.py のコードは変更不要
====================================================
"""

import os
import sqlite3
import json
from datetime import datetime
from typing import Optional

# ─────────────────────────────────────────
# 設定
# ─────────────────────────────────────────

DB_PATH = os.getenv("DB_PATH", "./agent_memory.db")
REDIS_URL = os.getenv("REDIS_URL", "")  # 将来: redis://localhost:6379/0
MAX_CONVERSATION_LENGTH = 20  # 会話履歴の最大保持件数

# ─────────────────────────────────────────
# 会話履歴ストア
# 現在: インメモリ辞書
# 将来: Redis Hash（TTL付き）
# ─────────────────────────────────────────

_conversations: dict[int, list] = {}


def get_conversation(user_id: int) -> list:
    """
    会話履歴を取得する

    Redis移行時:
        data = redis_client.get(f"conversation:{user_id}")
        return json.loads(data) if data else []
    """
    return _conversations.get(user_id, [])


def set_conversation(user_id: int, history: list) -> None:
    """
    会話履歴を保存する（最大MAX_CONVERSATION_LENGTH件）

    Redis移行時:
        redis_client.setex(
            f"conversation:{user_id}",
            86400,  # 24時間TTL
            json.dumps(history[-MAX_CONVERSATION_LENGTH:])
        )
    """
    _conversations[user_id] = history[-MAX_CONVERSATION_LENGTH:]


def clear_conversation(user_id: int) -> None:
    """
    会話履歴をクリアする

    Redis移行時:
        redis_client.delete(f"conversation:{user_id}")
    """
    _conversations.pop(user_id, None)


# ─────────────────────────────────────────
# DB初期化（SQLite用）
# Redis移行時はこのブロックは不要になる
# ─────────────────────────────────────────

def init_db() -> None:
    """SQLiteのテーブルを初期化する"""
    if os.path.dirname(DB_PATH):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL,
        category TEXT DEFAULT 'general',
        created_at TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        due_date TEXT,
        created_at TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS yt_channels (
        handle TEXT PRIMARY KEY,
        channel_id TEXT,
        updated_at TEXT
    )""")
    conn.commit()
    conn.close()


# ─────────────────────────────────────────
# ノート（メモ）
# 現在: SQLite
# 将来: Redis List + Hash
# ─────────────────────────────────────────

def save_note(content: str, category: str = "general") -> str:
    """
    メモを保存する

    Redis移行時:
        note_id = redis_client.incr("note:seq")
        redis_client.hset(f"note:{note_id}", mapping={
            "content": content, "category": category,
            "created_at": datetime.now().isoformat()
        })
        redis_client.lpush(f"notes:{category}", note_id)
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO notes (content, category, created_at) VALUES (?, ?, ?)",
        (content, category, datetime.now().isoformat())
    )
    conn.commit()
    note_id = c.lastrowid
    conn.close()
    return f"✅ メモ#{note_id}保存（{category}）"


def get_notes(category: Optional[str] = None, limit: int = 10) -> list:
    """
    メモを取得する

    Redis移行時:
        ids = redis_client.lrange(f"notes:{category or 'all'}", 0, limit-1)
        return [redis_client.hgetall(f"note:{i}") for i in ids]
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if category:
        c.execute(
            "SELECT id,content,category,created_at FROM notes WHERE category=? ORDER BY created_at DESC LIMIT ?",
            (category, limit)
        )
    else:
        c.execute(
            "SELECT id,content,category,created_at FROM notes ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "content": r[1], "category": r[2], "created_at": r[3]} for r in rows]


# ─────────────────────────────────────────
# タスク
# 現在: SQLite
# 将来: Redis Hash + Sorted Set（期限でソート）
# ─────────────────────────────────────────

def add_task(title: str, due_date: Optional[str] = None) -> str:
    """
    タスクを追加する

    Redis移行時:
        task_id = redis_client.incr("task:seq")
        redis_client.hset(f"task:{task_id}", mapping={
            "title": title, "status": "pending",
            "due_date": due_date or "", "created_at": datetime.now().isoformat()
        })
        redis_client.sadd("tasks:pending", task_id)
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO tasks (title, status, due_date, created_at) VALUES (?, 'pending', ?, ?)",
        (title, due_date, datetime.now().isoformat())
    )
    conn.commit()
    task_id = c.lastrowid
    conn.close()
    return f"✅ タスク#{task_id}追加: {title}"


def get_tasks(status: str = "pending") -> list:
    """
    タスク一覧を取得する

    Redis移行時:
        ids = redis_client.smembers(f"tasks:{status}")
        return [redis_client.hgetall(f"task:{i}") for i in ids]
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id,title,status,due_date,created_at FROM tasks WHERE status=? ORDER BY created_at DESC",
        (status,)
    )
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "title": r[1], "status": r[2], "due_date": r[3], "created_at": r[4]} for r in rows]


def complete_task(task_id: int) -> str:
    """
    タスクを完了にする

    Redis移行時:
        redis_client.hset(f"task:{task_id}", "status", "done")
        redis_client.smove("tasks:pending", "tasks:done", task_id)
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE tasks SET status='done' WHERE id=?", (task_id,))
    conn.commit()
    conn.close()
    return f"✅ タスク#{task_id}完了"


# ─────────────────────────────────────────
# YouTubeチャンネルIDキャッシュ
# 現在: SQLite
# 将来: Redis String（長期TTL）
# ─────────────────────────────────────────

def get_channel_id(handle: str) -> str:
    """
    キャッシュからチャンネルIDを取得する

    Redis移行時:
        return redis_client.get(f"yt:channel:{handle}") or ""
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT channel_id FROM yt_channels WHERE handle=?", (handle,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else ""


def set_channel_id(handle: str, channel_id: str) -> None:
    """
    チャンネルIDをキャッシュに保存する

    Redis移行時:
        redis_client.setex(f"yt:channel:{handle}", 2592000, channel_id)  # 30日TTL
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO yt_channels VALUES (?,?,?)",
        (handle, channel_id, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


# ─────────────────────────────────────────
# エージェント作業ログ
# 現在: SQLite
# 将来: Redis Sorted Set（日付スコア付き）
#
# 目的:
#   ① 各エージェントが作業内容・思考プロセスを記録
#   ② 坂本が日報としてまとめてけんたに報告
#   ③ 次回起動時に読み返し、ナレッジを継承する
# ─────────────────────────────────────────

def _init_agent_logs():
    """エージェントログテーブルを初期化"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS agent_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_name TEXT NOT NULL,
        session_date TEXT NOT NULL,
        task TEXT NOT NULL,
        result_summary TEXT,
        issues TEXT,
        thinking_process TEXT,
        created_at TEXT NOT NULL
    )""")
    conn.commit()
    conn.close()


def write_agent_log(
    agent_name: str,
    task: str,
    result_summary: str = "",
    issues: str = "",
    thinking_process: str = "",
) -> None:
    """
    エージェントの作業ログを記録する

    Redis移行時:
        redis_client.zadd(f"logs:{agent_name}",
            {json.dumps(log): datetime.now().timestamp()})
    """
    _init_agent_logs()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now()
    c.execute(
        """INSERT INTO agent_logs
           (agent_name, session_date, task, result_summary, issues, thinking_process, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            agent_name,
            now.strftime("%Y-%m-%d"),
            task[:500],
            result_summary[:1000],
            issues[:500],
            thinking_process[:1000],
            now.isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def get_agent_logs(date: str = None, agent_name: str = None, limit: int = 20) -> list:
    """
    エージェントログを取得する

    Args:
        date: "YYYY-MM-DD" 形式。Noneなら今日
        agent_name: エージェント名でフィルタ。Noneなら全員
        limit: 取得件数

    Redis移行時:
        logs = redis_client.zrevrangebyscore(f"logs:{agent_name}",
            end_score, start_score, start=0, num=limit)
    """
    _init_agent_logs()
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if agent_name:
        c.execute(
            """SELECT agent_name, task, result_summary, issues, thinking_process, created_at
               FROM agent_logs WHERE session_date=? AND agent_name=?
               ORDER BY created_at DESC LIMIT ?""",
            (date, agent_name, limit),
        )
    else:
        c.execute(
            """SELECT agent_name, task, result_summary, issues, thinking_process, created_at
               FROM agent_logs WHERE session_date=?
               ORDER BY created_at DESC LIMIT ?""",
            (date, limit),
        )
    rows = c.fetchall()
    conn.close()

    return [
        {
            "agent": r[0],
            "task": r[1],
            "result": r[2],
            "issues": r[3],
            "thinking": r[4],
            "time": r[5],
        }
        for r in rows
    ]


def get_recent_knowledge(agent_name: str = None, days: int = 7) -> list:
    """
    直近N日分のログを取得してナレッジとして返す
    → エージェントが次回起動時に読み返すために使用

    Redis移行時:
        redis_client.zrevrangebyscore(f"logs:{agent_name}",
            now_score, week_ago_score, start=0, num=50)
    """
    _init_agent_logs()
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if agent_name:
        c.execute(
            """SELECT agent_name, task, result_summary, issues, thinking_process, session_date
               FROM agent_logs WHERE session_date >= ? AND agent_name=?
               ORDER BY created_at DESC LIMIT 30""",
            (cutoff, agent_name),
        )
    else:
        c.execute(
            """SELECT agent_name, task, result_summary, issues, thinking_process, session_date
               FROM agent_logs WHERE session_date >= ?
               ORDER BY created_at DESC LIMIT 50""",
            (cutoff,),
        )
    rows = c.fetchall()
    conn.close()

    return [
        {
            "agent": r[0],
            "task": r[1],
            "result": r[2],
            "issues": r[3],
            "thinking": r[4],
            "date": r[5],
        }
        for r in rows
    ]
