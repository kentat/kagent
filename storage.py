"""
ストレージ抽象レイヤー
========================================
REDIS_URL が設定されている場合: Redis使用
設定されていない場合: SQLite + メモリ（フォールバック）
========================================
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

REDIS_URL = os.getenv("REDIS_URL", "")
DB_PATH   = os.getenv("DB_PATH", "./agent_memory.db")

# ─────────────────────────────────────────
# Redis クライアント（REDIS_URL設定時のみ）
# ─────────────────────────────────────────

_redis_client = None

def _get_redis():
    global _redis_client
    if _redis_client is None and REDIS_URL:
        import redis
        import logging
        try:
            _redis_client = redis.from_url(
                REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            logging.getLogger(__name__).info(f"Redis接続成功: {REDIS_URL[:20]}...")
        except Exception as e:
            logging.getLogger(__name__).error(f"Redis接続エラー: {e}")
    return _redis_client


def _use_redis() -> bool:
    try:
        r = _get_redis()
        if r:
            r.ping()
            return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Redis ping失敗（SQLiteにフォールバック）: {e}")
    return False


# ─────────────────────────────────────────
# SQLite 初期化（フォールバック用）
# ─────────────────────────────────────────

def init_db():
    os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL, category TEXT DEFAULT 'general', created_at TEXT NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL, status TEXT DEFAULT 'pending', due_date TEXT, created_at TEXT NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS yt_channels (
        handle TEXT PRIMARY KEY, channel_id TEXT, updated_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS report_cache (
        report_type TEXT PRIMARY KEY, content TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS agent_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, agent_name TEXT NOT NULL,
        session_date TEXT NOT NULL, task TEXT NOT NULL, result_summary TEXT,
        issues TEXT, thinking_process TEXT, created_at TEXT NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS agent_issues (
        id INTEGER PRIMARY KEY AUTOINCREMENT, agent_name TEXT NOT NULL,
        issue_type TEXT NOT NULL, title TEXT NOT NULL, detail TEXT,
        gtd_status TEXT DEFAULT 'inbox', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS agent_comm_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, from_agent TEXT NOT NULL,
        to_agent TEXT NOT NULL, message_type TEXT NOT NULL, content TEXT NOT NULL,
        session_date TEXT NOT NULL, created_at TEXT NOT NULL)""")
    conn.commit()
    conn.close()


# ─────────────────────────────────────────
# 会話履歴
# ─────────────────────────────────────────

_conversations: dict = {}
MAX_CONV = 20

def get_conversation(user_id: int) -> list:
    if _use_redis():
        data = _get_redis().get(f"conversation:{user_id}")
        return json.loads(data) if data else []
    return _conversations.get(user_id, [])

def set_conversation(user_id: int, history: list) -> None:
    history = history[-MAX_CONV:]
    if _use_redis():
        _get_redis().setex(f"conversation:{user_id}", 86400, json.dumps(history))
    else:
        _conversations[user_id] = history

def clear_conversation(user_id: int) -> None:
    if _use_redis():
        _get_redis().delete(f"conversation:{user_id}")
    else:
        _conversations.pop(user_id, None)


# ─────────────────────────────────────────
# メモ
# ─────────────────────────────────────────

def save_note(content: str, category: str = "general") -> str:
    if _use_redis():
        r = _get_redis()
        note_id = r.incr("note:seq")
        now = datetime.now().isoformat()
        r.hset(f"note:{note_id}", mapping={
            "content": content, "category": category, "created_at": now})
        r.lpush(f"notes:{category}", note_id)
        r.lpush("notes:all", note_id)
        return f"✅ メモ#{note_id}保存（{category}）"
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO notes (content, category, created_at) VALUES (?, ?, ?)",
              (content, category, datetime.now().isoformat()))
    conn.commit(); note_id = c.lastrowid; conn.close()
    return f"✅ メモ#{note_id}保存（{category}）"

def get_notes(category: Optional[str] = None, limit: int = 10) -> list:
    if _use_redis():
        r = _get_redis()
        key = f"notes:{category}" if category else "notes:all"
        ids = r.lrange(key, 0, limit - 1)
        results = []
        for i in ids:
            data = r.hgetall(f"note:{i}")
            if data:
                results.append({"id": i, **data})
        return results
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if category:
        c.execute("SELECT id,content,category,created_at FROM notes WHERE category=? ORDER BY created_at DESC LIMIT ?", (category, limit))
    else:
        c.execute("SELECT id,content,category,created_at FROM notes ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = c.fetchall(); conn.close()
    return [{"id": r[0], "content": r[1], "category": r[2], "created_at": r[3]} for r in rows]


# ─────────────────────────────────────────
# タスク
# ─────────────────────────────────────────

def add_task(title: str, due_date: Optional[str] = None) -> str:
    if _use_redis():
        r = _get_redis()
        task_id = r.incr("task:seq")
        now = datetime.now().isoformat()
        r.hset(f"task:{task_id}", mapping={
            "title": title, "status": "pending",
            "due_date": due_date or "", "created_at": now})
        r.sadd("tasks:pending", task_id)
        return f"✅ タスク#{task_id}追加: {title}"
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO tasks (title, status, due_date, created_at) VALUES (?, 'pending', ?, ?)",
              (title, due_date, datetime.now().isoformat()))
    conn.commit(); task_id = c.lastrowid; conn.close()
    return f"✅ タスク#{task_id}追加: {title}"

def get_tasks(status: str = "pending") -> list:
    if _use_redis():
        r = _get_redis()
        ids = r.smembers(f"tasks:{status}")
        results = []
        for i in ids:
            data = r.hgetall(f"task:{i}")
            if data and data.get("status") == status:
                results.append({"id": i, **data})
        return sorted(results, key=lambda x: x.get("created_at", ""), reverse=True)
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id,title,status,due_date,created_at FROM tasks WHERE status=? ORDER BY created_at DESC", (status,))
    rows = c.fetchall(); conn.close()
    return [{"id": r[0], "title": r[1], "status": r[2], "due_date": r[3], "created_at": r[4]} for r in rows]

def complete_task(task_id: int) -> str:
    if _use_redis():
        r = _get_redis()
        r.hset(f"task:{task_id}", "status", "done")
        r.smove("tasks:pending", "tasks:done", task_id)
        return f"✅ タスク#{task_id}完了"
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE tasks SET status='done' WHERE id=?", (task_id,))
    conn.commit(); conn.close()
    return f"✅ タスク#{task_id}完了"


# ─────────────────────────────────────────
# YouTubeチャンネルIDキャッシュ
# ─────────────────────────────────────────

def get_channel_id(handle: str) -> str:
    if _use_redis():
        return _get_redis().get(f"yt:channel:{handle}") or ""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT channel_id FROM yt_channels WHERE handle=?", (handle,))
    row = c.fetchone(); conn.close()
    return row[0] if row else ""

def set_channel_id(handle: str, channel_id: str) -> None:
    if _use_redis():
        _get_redis().setex(f"yt:channel:{handle}", 2592000, channel_id)
        return
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO yt_channels VALUES (?,?,?)",
              (handle, channel_id, datetime.now().isoformat()))
    conn.commit(); conn.close()


# ─────────────────────────────────────────
# レポートキャッシュ（Web表示用）
# ─────────────────────────────────────────

def save_report_cache(report_type: str, content: str) -> None:
    if _use_redis():
        _get_redis().setex(f"report:{report_type}", 86400,
                           json.dumps({"content": content, "updated_at": datetime.now().isoformat()}))
        return
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO report_cache (report_type, content, updated_at) VALUES (?, ?, ?)",
              (report_type, content, datetime.now().isoformat()))
    conn.commit(); conn.close()

def get_report_cache(report_type: str) -> dict:
    if _use_redis():
        data = _get_redis().get(f"report:{report_type}")
        return json.loads(data) if data else {}
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT content, updated_at FROM report_cache WHERE report_type=?", (report_type,))
    row = c.fetchone(); conn.close()
    return {"content": row[0], "updated_at": row[1]} if row else {}


# ─────────────────────────────────────────
# エージェント作業ログ
# ─────────────────────────────────────────

def write_agent_log(agent_name: str, task: str, result_summary: str = "",
                    issues: str = "", thinking_process: str = "") -> None:
    now = datetime.now()
    if _use_redis():
        r = _get_redis()
        log_id = r.incr("log:seq")
        r.hset(f"log:{log_id}", mapping={
            "agent": agent_name, "date": now.strftime("%Y-%m-%d"),
            "task": task[:300], "result": result_summary[:500],
            "issues": issues[:300], "thinking": thinking_process[:500],
            "time": now.isoformat()})
        r.lpush(f"logs:{agent_name}:{now.strftime('%Y-%m-%d')}", log_id)
        r.lpush(f"logs:all:{now.strftime('%Y-%m-%d')}", log_id)
        r.expire(f"log:{log_id}", 604800)  # 7日TTL
        return
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""INSERT INTO agent_logs
               (agent_name, session_date, task, result_summary, issues, thinking_process, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
              (agent_name, now.strftime("%Y-%m-%d"), task[:300],
               result_summary[:500], issues[:300], thinking_process[:500], now.isoformat()))
    conn.commit(); conn.close()

def get_agent_logs(date: str = None, agent_name: str = None, limit: int = 20) -> list:
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    if _use_redis():
        r = _get_redis()
        key = f"logs:{agent_name}:{date}" if agent_name else f"logs:all:{date}"
        ids = r.lrange(key, 0, limit - 1)
        results = []
        for i in ids:
            data = r.hgetall(f"log:{i}")
            if data:
                results.append({"agent": data.get("agent"), "task": data.get("task"),
                                 "result": data.get("result"), "issues": data.get("issues"),
                                 "thinking": data.get("thinking"), "time": data.get("time")})
        return results
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if agent_name:
        c.execute("""SELECT agent_name, task, result_summary, issues, thinking_process, created_at
                     FROM agent_logs WHERE session_date=? AND agent_name=?
                     ORDER BY created_at DESC LIMIT ?""", (date, agent_name, limit))
    else:
        c.execute("""SELECT agent_name, task, result_summary, issues, thinking_process, created_at
                     FROM agent_logs WHERE session_date=?
                     ORDER BY created_at DESC LIMIT ?""", (date, limit))
    rows = c.fetchall(); conn.close()
    return [{"agent": r[0], "task": r[1], "result": r[2], "issues": r[3], "thinking": r[4], "time": r[5]} for r in rows]

def get_recent_knowledge(agent_name: str = None, days: int = 7) -> list:
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    if _use_redis():
        results = []
        r = _get_redis()
        for d in range(days):
            date = (datetime.now() - timedelta(days=d)).strftime("%Y-%m-%d")
            key = f"logs:{agent_name}:{date}" if agent_name else f"logs:all:{date}"
            ids = r.lrange(key, 0, 10)
            for i in ids:
                data = r.hgetall(f"log:{i}")
                if data:
                    results.append({"agent": data.get("agent"), "task": data.get("task"),
                                    "result": data.get("result"), "issues": data.get("issues"),
                                    "thinking": data.get("thinking"), "date": data.get("date")})
        return results[:30]
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if agent_name:
        c.execute("""SELECT agent_name, task, result_summary, issues, thinking_process, session_date
                     FROM agent_logs WHERE session_date >= ? AND agent_name=?
                     ORDER BY created_at DESC LIMIT 30""", (cutoff, agent_name))
    else:
        c.execute("""SELECT agent_name, task, result_summary, issues, thinking_process, session_date
                     FROM agent_logs WHERE session_date >= ?
                     ORDER BY created_at DESC LIMIT 50""", (cutoff,))
    rows = c.fetchall(); conn.close()
    return [{"agent": r[0], "task": r[1], "result": r[2], "issues": r[3], "thinking": r[4], "date": r[5]} for r in rows]


# ─────────────────────────────────────────
# GTD 課題・提案管理
# ─────────────────────────────────────────

GTD_STATUSES = ["inbox", "next_action", "in_progress", "waiting", "someday", "done"]
GTD_LABELS = {
    "inbox": "📥 受信", "next_action": "▶️ 次のアクション",
    "in_progress": "🔄 進行中", "waiting": "⏳ 待機中",
    "someday": "💭 いつかやる", "done": "✅ 完了",
}

def add_issue(agent_name: str, title: str, detail: str = "", issue_type: str = "issue") -> int:
    now = datetime.now().isoformat()
    if _use_redis():
        r = _get_redis()
        issue_id = r.incr("issue:seq")
        r.hset(f"issue:{issue_id}", mapping={
            "agent": agent_name, "type": issue_type, "title": title[:200],
            "detail": detail[:500], "status": "inbox",
            "created_at": now, "updated_at": now})
        r.sadd(f"issues:{agent_name}:inbox", issue_id)
        r.sadd("issues:all:inbox", issue_id)
        return issue_id
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""INSERT INTO agent_issues
               (agent_name, issue_type, title, detail, gtd_status, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'inbox', ?, ?)""",
              (agent_name, issue_type, title[:200], detail[:500], now, now))
    conn.commit(); issue_id = c.lastrowid; conn.close()
    return issue_id

def update_issue_status(issue_id: int, gtd_status: str) -> bool:
    if gtd_status not in GTD_STATUSES:
        return False
    if _use_redis():
        r = _get_redis()
        data = r.hgetall(f"issue:{issue_id}")
        if data:
            old_status = data.get("status", "inbox")
            agent = data.get("agent", "")
            r.hset(f"issue:{issue_id}", mapping={"status": gtd_status, "updated_at": datetime.now().isoformat()})
            r.smove(f"issues:{agent}:{old_status}", f"issues:{agent}:{gtd_status}", issue_id)
            r.smove(f"issues:all:{old_status}", f"issues:all:{gtd_status}", issue_id)
        return True
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE agent_issues SET gtd_status=?, updated_at=? WHERE id=?",
              (gtd_status, datetime.now().isoformat(), issue_id))
    conn.commit(); conn.close()
    return True

def get_issues(agent_name: str = None, issue_type: str = None,
               gtd_status: str = None, include_done: bool = False) -> list:
    if _use_redis():
        r = _get_redis()
        statuses = GTD_STATUSES if include_done else [s for s in GTD_STATUSES if s != "done"]
        results = []
        for st in statuses:
            key = f"issues:{agent_name}:{st}" if agent_name else f"issues:all:{st}"
            ids = r.smembers(key)
            for i in ids:
                data = r.hgetall(f"issue:{i}")
                if data:
                    if issue_type and data.get("type") != issue_type:
                        continue
                    results.append({
                        "id": i, "agent": data.get("agent"), "type": data.get("type"),
                        "title": data.get("title"), "detail": data.get("detail"),
                        "status": data.get("status"),
                        "status_label": GTD_LABELS.get(data.get("status", "inbox"), ""),
                        "created_at": data.get("created_at"), "updated_at": data.get("updated_at")})
        return sorted(results, key=lambda x: x.get("updated_at", ""), reverse=True)
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    where, params = [], []
    if agent_name: where.append("agent_name = ?"); params.append(agent_name)
    if issue_type: where.append("issue_type = ?"); params.append(issue_type)
    if gtd_status: where.append("gtd_status = ?"); params.append(gtd_status)
    if not include_done: where.append("gtd_status != 'done'")
    sql = "SELECT id, agent_name, issue_type, title, detail, gtd_status, created_at, updated_at FROM agent_issues"
    if where: sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY updated_at DESC"
    c.execute(sql, params)
    rows = c.fetchall(); conn.close()
    return [{"id": r[0], "agent": r[1], "type": r[2], "title": r[3], "detail": r[4],
             "status": r[5], "status_label": GTD_LABELS.get(r[5], r[5]),
             "created_at": r[6], "updated_at": r[7]} for r in rows]


# ─────────────────────────────────────────
# エージェント間通信ログ
# ─────────────────────────────────────────

def log_agent_comm(from_agent: str, to_agent: str, message_type: str, content: str) -> None:
    now = datetime.now()
    if _use_redis():
        r = _get_redis()
        log_id = r.incr("comm:seq")
        r.hset(f"comm:{log_id}", mapping={
            "from": from_agent, "to": to_agent, "type": message_type,
            "content": content[:500], "date": now.strftime("%Y-%m-%d"), "time": now.isoformat()})
        r.lpush(f"comms:{now.strftime('%Y-%m-%d')}", log_id)
        r.expire(f"comm:{log_id}", 604800)
        return
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""INSERT INTO agent_comm_logs
               (from_agent, to_agent, message_type, content, session_date, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
              (from_agent, to_agent, message_type, content[:500],
               now.strftime("%Y-%m-%d"), now.isoformat()))
    conn.commit(); conn.close()

def get_comm_logs(date: str = None, limit: int = 30) -> list:
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    if _use_redis():
        r = _get_redis()
        ids = r.lrange(f"comms:{date}", 0, limit - 1)
        results = []
        for i in ids:
            data = r.hgetall(f"comm:{i}")
            if data:
                results.append({"from": data.get("from"), "to": data.get("to"),
                                 "type": data.get("type"), "content": data.get("content"),
                                 "time": data.get("time")})
        return results
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""SELECT from_agent, to_agent, message_type, content, created_at
                 FROM agent_comm_logs WHERE session_date=?
                 ORDER BY created_at ASC LIMIT ?""", (date, limit))
    rows = c.fetchall(); conn.close()
    return [{"from": r[0], "to": r[1], "type": r[2], "content": r[3], "time": r[4]} for r in rows]
