import os, yfinance as yf, requests, json, sqlite3
from datetime import datetime
from typing import Optional

DB_PATH = os.getenv("DB_PATH", "./agent_memory.db")

def get_stock_price(ticker):
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
        return {"ticker": ticker.upper(), "company": info.get("longName", ticker), "price": round(current, 2), "change": round(change, 2), "change_pct": round(change_pct, 2), "currency": info.get("currency", "USD"), "52w_high": info.get("fiftyTwoWeekHigh"), "52w_low": info.get("fiftyTwoWeekLow"), "pe_ratio": info.get("trailingPE"), "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M JST")}
    except Exception as e:
        return {"error": str(e), "ticker": ticker}

def get_portfolio_prices(tickers):
    return {t: get_stock_price(t) for t in tickers}

def get_exchange_rate(from_currency="USD", to_currency="JPY"):
    try:
        ticker = yf.Ticker(f"{from_currency}{to_currency}=X")
        hist = ticker.history(period="5d")
        if hist.empty:
            return {"error": "データなし"}
        rate = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else rate
        return {"pair": f"{from_currency}/{to_currency}", "rate": round(rate, 2), "change_pct": round((rate-prev)/prev*100 if prev else 0, 2)}
    except Exception as e:
        return {"error": str(e)}

def get_market_indices():
    indices = {"S&P500": "^GSPC", "NASDAQ": "^IXIC", "DOW": "^DJI", "日経225": "^N225"}
    results = {}
    for name, sym in indices.items():
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="5d")
            if not hist.empty:
                cur = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else cur
                results[name] = {"value": round(cur, 2), "change_pct": round((cur-prev)/prev*100 if prev else 0, 2)}
        except:
            pass
    return results

def get_portfolio_pnl():
    from config import MY_PORTFOLIO
    positions = MY_PORTFOLIO.get("positions", {})
    if not positions:
        return {"error": "positions が config.py に設定されていません"}
    fx = get_exchange_rate("USD", "JPY")
    usdjpy = fx.get("rate", 150.0)
    results = []
    total_cost_usd = total_value_usd = 0
    for ticker, pos in positions.items():
        shares, cost_usd, name = pos["shares"], pos["cost_usd"], pos.get("name", ticker)
        price_data = get_stock_price(ticker)
        if "error" in price_data:
            continue
        current_price = price_data["price"]
        cost_total = cost_usd * shares
        value_total = current_price * shares
        pnl_usd = value_total - cost_total
        pnl_pct = (pnl_usd / cost_total * 100) if cost_total else 0
        total_cost_usd += cost_total
        total_value_usd += value_total
        results.append({"ticker": ticker, "name": name, "shares": shares, "cost_usd": round(cost_usd, 4), "current_price": current_price, "value_usd": round(value_total, 2), "pnl_usd": round(pnl_usd, 2), "pnl_pct": round(pnl_pct, 2), "pnl_jpy": round(pnl_usd * usdjpy, 0), "day_change_usd": round(price_data["change"] * shares, 2), "day_change_jpy": round(price_data["change"] * shares * usdjpy, 0), "day_change_pct": price_data["change_pct"]})
    total_pnl_usd = total_value_usd - total_cost_usd
    return {"usdjpy": usdjpy, "total_cost_usd": round(total_cost_usd, 2), "total_value_usd": round(total_value_usd, 2), "total_pnl_usd": round(total_pnl_usd, 2), "total_pnl_jpy": round(total_pnl_usd * usdjpy, 0), "total_pnl_pct": round((total_pnl_usd/total_cost_usd*100) if total_cost_usd else 0, 2), "positions": sorted(results, key=lambda x: x["pnl_pct"], reverse=True)}

def web_search(query):
    try:
        resp = requests.get("https://api.duckduckgo.com/", params={"q": query, "format": "json", "no_redirect": 1, "no_html": 1}, timeout=10)
        data = resp.json()
        results = []
        if data.get("Abstract"): results.append(f"📌 {data['Abstract']}")
        if data.get("Answer"): results.append(f"✅ {data['Answer']}")
        for topic in data.get("RelatedTopics", [])[:5]:
            if isinstance(topic, dict) and topic.get("Text"): results.append(f"• {topic['Text'][:200]}")
        return f"🔍 {query}\n\n" + "\n".join(results) if results else f"「{query}」の結果なし"
    except Exception as e:
        return f"検索エラー: {str(e)}"

def fetch_url_content(url):
    try:
        import re
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        content = resp.text
        if "html" in resp.headers.get("content-type", "").lower():
            content = re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL)
            content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL)
            content = re.sub(r"<[^>]+>", " ", content)
            content = re.sub(r"\s+", " ", content).strip()
        return content[:3000]
    except Exception as e:
        return f"URL取得エラー: {str(e)}"

def get_weather(city="Tokyo"):
    try:
        data = requests.get(f"https://wttr.in/{city}?format=j1", timeout=10).json()
        cur = data["current_condition"][0]
        today = data["weather"][0]
        return {"city": city, "temp_c": cur["temp_C"], "feels_like_c": cur["FeelsLikeC"], "description": cur["weatherDesc"][0]["value"], "humidity": cur["humidity"], "max_temp_c": today["maxtempC"], "min_temp_c": today["mintempC"]}
    except Exception as e:
        return {"error": str(e)}

def _init_db():
    if os.path.dirname(DB_PATH): os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT NOT NULL, category TEXT DEFAULT 'general', created_at TEXT NOT NULL)")
    c.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, status TEXT DEFAULT 'pending', due_date TEXT, created_at TEXT NOT NULL)")
    conn.commit(); conn.close()

def save_note(content, category="general"):
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO notes (content, category, created_at) VALUES (?, ?, ?)", (content, category, datetime.now().isoformat()))
    conn.commit(); note_id = c.lastrowid; conn.close()
    return f"✅ メモ#{note_id}保存（{category}）"

def get_notes(category=None, limit=10):
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if category:
        c.execute("SELECT id,content,category,created_at FROM notes WHERE category=? ORDER BY created_at DESC LIMIT ?", (category, limit))
    else:
        c.execute("SELECT id,content,category,created_at FROM notes ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = c.fetchall(); conn.close()
    return [{"id": r[0], "content": r[1], "category": r[2], "created_at": r[3]} for r in rows]

def add_task(title, due_date=None):
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO tasks (title, status, due_date, created_at) VALUES (?, 'pending', ?, ?)", (title, due_date, datetime.now().isoformat()))
    conn.commit(); task_id = c.lastrowid; conn.close()
    return f"✅ タスク#{task_id}追加: {title}"

def get_tasks(status="pending"):
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id,title,status,due_date,created_at FROM tasks WHERE status=? ORDER BY created_at DESC", (status,))
    rows = c.fetchall(); conn.close()
    return [{"id": r[0], "title": r[1], "status": r[2], "due_date": r[3], "created_at": r[4]} for r in rows]

def complete_task(task_id):
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE tasks SET status='done' WHERE id=?", (task_id,))
    conn.commit(); conn.close()
    return f"✅ タスク#{task_id}完了"

def execute_tool(tool_name, tool_input):
    dispatch = {"get_stock_price": get_stock_price, "get_portfolio_prices": get_portfolio_prices, "get_portfolio_pnl": get_portfolio_pnl, "get_exchange_rate": get_exchange_rate, "get_market_indices": get_market_indices, "web_search": web_search, "fetch_url_content": fetch_url_content, "get_weather": get_weather, "save_note": save_note, "get_notes": get_notes, "add_task": add_task, "get_tasks": get_tasks, "complete_task": complete_task}
    fn = dispatch.get(tool_name)
    if not fn: return f"不明なツール: {tool_name}"
    try:
        result = fn(**tool_input)
        return json.dumps(result, ensure_ascii=False, indent=2) if not isinstance(result, str) else result
    except Exception as e:
        return f"ツールエラー ({tool_name}): {str(e)}"


# ─────────────────────────────────────────
# YouTube新着動画チェック
# ─────────────────────────────────────────

import xml.etree.ElementTree as ET
from datetime import timezone, timedelta

def _get_channel_id(handle: str) -> str:
    """ハンドルからチャンネルIDを取得（SQLiteキャッシュ付き）"""
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS yt_channels (handle TEXT PRIMARY KEY, channel_id TEXT, updated_at TEXT)")
    conn.commit()
    c.execute("SELECT channel_id FROM yt_channels WHERE handle=?", (handle,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0]
    try:
        import re
        resp = requests.get(f"https://www.youtube.com/@{handle}",
                            headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        match = re.search(r'"channelId":"(UC[a-zA-Z0-9_-]{22})"', resp.text)
        if not match:
            match = re.search(r'channel/(UC[a-zA-Z0-9_-]{22})', resp.text)
        if match:
            cid = match.group(1)
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO yt_channels VALUES (?,?,?)",
                      (handle, cid, datetime.now().isoformat()))
            conn.commit(); conn.close()
            return cid
    except:
        pass
    return ""


def get_youtube_new_videos(hours: int = 24) -> list:
    """登録チャンネルの新着動画を取得する"""
    from config import YOUTUBE_CHANNELS
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    results = []
    for ch in YOUTUBE_CHANNELS:
        cid = _get_channel_id(ch["handle"])
        if not cid:
            continue
        try:
            resp = requests.get(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}", timeout=10)
            if resp.status_code != 200:
                continue
            ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
            root = ET.fromstring(resp.content)
            for entry in root.findall("a:entry", ns)[:5]:
                pub = entry.findtext("a:published", namespaces=ns, default="")
                if not pub:
                    continue
                pub = pub.replace("Z", "+00:00")
                try:
                    published = datetime.fromisoformat(pub)
                    if published.tzinfo is None:
                        published = published.replace(tzinfo=timezone.utc)
                except:
                    continue
                if published < cutoff:
                    continue
                title = entry.findtext("a:title", namespaces=ns, default="不明")
                vid = entry.find("yt:videoId", ns)
                url = f"https://youtu.be/{vid.text}" if vid is not None else ""
                jst_str = published.astimezone(timezone(timedelta(hours=9))).strftime("%m/%d %H:%M")
                results.append({"channel": ch["name"], "title": title, "url": url, "published": jst_str})
        except:
            continue
    return sorted(results, key=lambda x: x["published"], reverse=True)
