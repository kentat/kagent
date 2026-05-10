"""
ツール実装モジュール
すべてのツールはClaudeのtool_useループから呼び出される
"""

import os
import yfinance as yf
import requests
import json
import sqlite3
from datetime import datetime
from typing import Optional

# Railway Volume 対応: 環境変数でDBパスを切り替え
# ローカル: ./agent_memory.db
# Railway: /data/agent_memory.db（環境変数 DB_PATH=/data/agent_memory.db を設定）
DB_PATH = os.getenv("DB_PATH", "./agent_memory.db")


# ─────────────────────────────────────────
# 株価・市場データ
# ─────────────────────────────────────────

def get_stock_price(ticker: str) -> dict:
    """1銘柄の株価・基本情報を取得"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        info = stock.info

        if hist.empty:
            return {"error": f"{ticker}: データなし", "ticker": ticker}

        current = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current
        change = current - prev
        change_pct = (change / prev * 100) if prev else 0

        return {
            "ticker": ticker.upper(),
            "company": info.get("longName", ticker),
            "price": round(current, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "currency": info.get("currency", "USD"),
            "volume": info.get("regularMarketVolume"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M JST"),
        }
    except Exception as e:
        return {"error": str(e), "ticker": ticker}


def get_portfolio_prices(tickers: list) -> dict:
    """複数銘柄を一括取得（ポートフォリオ一覧用）"""
    results = {}
    for ticker in tickers:
        results[ticker] = get_stock_price(ticker)
    return results


def get_exchange_rate(from_currency: str = "USD", to_currency: str = "JPY") -> dict:
    """為替レートを取得"""
    try:
        ticker = yf.Ticker(f"{from_currency}{to_currency}=X")
        hist = ticker.history(period="5d")
        if hist.empty:
            return {"error": "データなし"}
        rate = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else rate
        change_pct = (rate - prev) / prev * 100 if prev else 0
        return {
            "pair": f"{from_currency}/{to_currency}",
            "rate": round(rate, 2),
            "change_pct": round(change_pct, 2),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    except Exception as e:
        return {"error": str(e)}


def get_market_indices() -> dict:
    """主要指数（S&P500, NASDAQ, 日経）を取得"""
    indices = {
        "S&P500": "^GSPC",
        "NASDAQ": "^IXIC",
        "DOW": "^DJI",
        "日経225": "^N225",
    }
    results = {}
    for name, sym in indices.items():
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="5d")
            if not hist.empty:
                cur = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else cur
                pct = (cur - prev) / prev * 100 if prev else 0
                results[name] = {
                    "value": round(cur, 2),
                    "change_pct": round(pct, 2),
                }
        except:
            pass
    return results


# ─────────────────────────────────────────
# Web検索・情報収集
# ─────────────────────────────────────────

def web_search(query: str) -> str:
    """DuckDuckGo Instant Answer APIで検索（APIキー不要）"""
    try:
        url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "no_redirect": 1, "no_html": 1}
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()

        results = []
        if data.get("Abstract"):
            results.append(f"📌 {data['Abstract']}")
        if data.get("Answer"):
            results.append(f"✅ {data['Answer']}")
        for topic in data.get("RelatedTopics", [])[:5]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append(f"• {topic['Text'][:200]}")

        if not results:
            return f"「{query}」の検索結果が見つかりませんでした。より具体的なキーワードをお試しください。"
        return f"🔍 検索: {query}\n\n" + "\n".join(results)
    except Exception as e:
        return f"検索エラー: {str(e)}"


def fetch_url_content(url: str) -> str:
    """URLのテキストコンテンツを取得"""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; KentaAgent/1.0)"}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        # HTMLの場合は簡易テキスト抽出
        content = resp.text
        if "html" in resp.headers.get("content-type", "").lower():
            import re
            # タグを除去
            content = re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL)
            content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL)
            content = re.sub(r"<[^>]+>", " ", content)
            content = re.sub(r"\s+", " ", content).strip()

        return content[:3000] + ("..." if len(content) > 3000 else "")
    except Exception as e:
        return f"URL取得エラー: {str(e)}"


# ─────────────────────────────────────────
# 生活情報
# ─────────────────────────────────────────

def get_weather(city: str = "Tokyo") -> dict:
    """天気情報を取得（wttr.in - APIキー不要）"""
    try:
        url = f"https://wttr.in/{city}?format=j1"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        cur = data["current_condition"][0]
        today = data["weather"][0]

        return {
            "city": city,
            "temp_c": cur["temp_C"],
            "feels_like_c": cur["FeelsLikeC"],
            "description": cur["weatherDesc"][0]["value"],
            "humidity": cur["humidity"],
            "wind_kmph": cur["windspeedKmph"],
            "max_temp_c": today["maxtempC"],
            "min_temp_c": today["mintempC"],
            "sunrise": today.get("astronomy", [{}])[0].get("sunrise", "N/A"),
            "sunset": today.get("astronomy", [{}])[0].get("sunset", "N/A"),
        }
    except Exception as e:
        return {"error": str(e), "city": city}


# ─────────────────────────────────────────
# メモリ・ノート（SQLite永続化）
# ─────────────────────────────────────────

def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            created_at TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            due_date TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_note(content: str, category: str = "general") -> str:
    """メモを保存する"""
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO notes (content, category, created_at) VALUES (?, ?, ?)",
        (content, category, datetime.now().isoformat()),
    )
    conn.commit()
    note_id = c.lastrowid
    conn.close()
    return f"✅ メモ#{note_id}を保存しました（カテゴリ: {category}）"


def get_notes(category: Optional[str] = None, limit: int = 10) -> list:
    """保存済みメモを取得する"""
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if category:
        c.execute(
            "SELECT id, content, category, created_at FROM notes WHERE category=? ORDER BY created_at DESC LIMIT ?",
            (category, limit),
        )
    else:
        c.execute(
            "SELECT id, content, category, created_at FROM notes ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "content": r[1], "category": r[2], "created_at": r[3]} for r in rows]


def add_task(title: str, due_date: Optional[str] = None) -> str:
    """タスクを追加する"""
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO tasks (title, status, due_date, created_at) VALUES (?, 'pending', ?, ?)",
        (title, due_date, datetime.now().isoformat()),
    )
    conn.commit()
    task_id = c.lastrowid
    conn.close()
    return f"✅ タスク#{task_id}を追加しました: {title}"


def get_tasks(status: str = "pending") -> list:
    """タスク一覧を取得する"""
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, title, status, due_date, created_at FROM tasks WHERE status=? ORDER BY created_at DESC",
        (status,),
    )
    rows = c.fetchall()
    conn.close()
    return [
        {"id": r[0], "title": r[1], "status": r[2], "due_date": r[3], "created_at": r[4]}
        for r in rows
    ]


def complete_task(task_id: int) -> str:
    """タスクを完了にする"""
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE tasks SET status='done' WHERE id=?", (task_id,))
    conn.commit()
    conn.close()
    return f"✅ タスク#{task_id}を完了にしました"


# ─────────────────────────────────────────
# ツールディスパッチャー
# ─────────────────────────────────────────

def execute_tool(tool_name: str, tool_input: dict) -> str:
    """ツール名と引数を受け取り実行、結果をstr返却"""
    dispatch = {
        "get_stock_price": get_stock_price,
        "get_portfolio_prices": get_portfolio_prices,
        "get_exchange_rate": get_exchange_rate,
        "get_market_indices": get_market_indices,
        "web_search": web_search,
        "fetch_url_content": fetch_url_content,
        "get_weather": get_weather,
        "save_note": save_note,
        "get_notes": get_notes,
        "add_task": add_task,
        "get_tasks": get_tasks,
        "complete_task": complete_task,
    }

    fn = dispatch.get(tool_name)
    if not fn:
        return f"不明なツール: {tool_name}"
    try:
        result = fn(**tool_input)
        return json.dumps(result, ensure_ascii=False, indent=2) if not isinstance(result, str) else result
    except Exception as e:
        return f"ツールエラー ({tool_name}): {str(e)}"
