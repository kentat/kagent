"""
ツール実装モジュール
状態管理はすべて storage.py 経由（Redis移行対応済み）
"""

import os
import yfinance as yf
import requests
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import Optional

# ストレージ抽象レイヤー経由でアクセス
from storage import (
    save_note, get_notes,
    add_task, get_tasks, complete_task,
    get_channel_id, set_channel_id,
)


# ─────────────────────────────────────────
# 株価・市場データ
# ─────────────────────────────────────────

def get_stock_price(ticker: str) -> dict:
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
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "pe_ratio": info.get("trailingPE"),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M JST"),
        }
    except Exception as e:
        return {"error": str(e), "ticker": ticker}


def get_portfolio_prices(tickers: list) -> dict:
    return {t: get_stock_price(t) for t in tickers}


def get_exchange_rate(from_currency: str = "USD", to_currency: str = "JPY") -> dict:
    try:
        ticker = yf.Ticker(f"{from_currency}{to_currency}=X")
        hist = ticker.history(period="5d")
        if hist.empty:
            return {"error": "データなし"}
        rate = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else rate
        return {
            "pair": f"{from_currency}/{to_currency}",
            "rate": round(rate, 2),
            "change_pct": round((rate - prev) / prev * 100 if prev else 0, 2),
        }
    except Exception as e:
        return {"error": str(e)}


def get_market_indices() -> dict:
    indices = {"S&P500": "^GSPC", "NASDAQ": "^IXIC", "DOW": "^DJI", "日経225": "^N225"}
    results = {}
    for name, sym in indices.items():
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="5d")
            if not hist.empty:
                cur = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else cur
                results[name] = {
                    "value": round(cur, 2),
                    "change_pct": round((cur - prev) / prev * 100 if prev else 0, 2),
                }
        except Exception:
            pass
    return results


def get_portfolio_pnl() -> dict:
    from config import MY_PORTFOLIO
    positions = MY_PORTFOLIO.get("positions", {})
    if not positions:
        return {"error": "positions が config.py に設定されていません"}
    fx = get_exchange_rate("USD", "JPY")
    usdjpy = fx.get("rate", 150.0)
    results = []
    total_cost_usd = total_value_usd = 0
    for ticker, pos in positions.items():
        shares = pos["shares"]
        cost_usd = pos["cost_usd"]
        name = pos.get("name", ticker)
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
        results.append({
            "ticker": ticker,
            "name": name,
            "shares": shares,
            "cost_usd": round(cost_usd, 4),
            "current_price": current_price,
            "value_usd": round(value_total, 2),
            "pnl_usd": round(pnl_usd, 2),
            "pnl_pct": round(pnl_pct, 2),
            "pnl_jpy": round(pnl_usd * usdjpy, 0),
            "day_change_usd": round(price_data["change"] * shares, 2),
            "day_change_jpy": round(price_data["change"] * shares * usdjpy, 0),
            "day_change_pct": price_data["change_pct"],
        })
    total_pnl_usd = total_value_usd - total_cost_usd
    return {
        "usdjpy": usdjpy,
        "total_cost_usd": round(total_cost_usd, 2),
        "total_value_usd": round(total_value_usd, 2),
        "total_pnl_usd": round(total_pnl_usd, 2),
        "total_pnl_jpy": round(total_pnl_usd * usdjpy, 0),
        "total_pnl_pct": round((total_pnl_usd / total_cost_usd * 100) if total_cost_usd else 0, 2),
        "positions": sorted(results, key=lambda x: x["pnl_pct"], reverse=True),
    }


# ─────────────────────────────────────────
# Web検索・情報収集
# ─────────────────────────────────────────

def web_search(query: str) -> str:
    try:
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_redirect": 1, "no_html": 1},
            timeout=10,
        )
        data = resp.json()
        results = []
        if data.get("Abstract"):
            results.append(f"📌 {data['Abstract']}")
        if data.get("Answer"):
            results.append(f"✅ {data['Answer']}")
        for topic in data.get("RelatedTopics", [])[:5]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append(f"• {topic['Text'][:200]}")
        return f"🔍 {query}\n\n" + "\n".join(results) if results else f"「{query}」の結果なし"
    except Exception as e:
        return f"検索エラー: {str(e)}"


def fetch_url_content(url: str) -> str:
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


# ─────────────────────────────────────────
# 天気・交通
# ─────────────────────────────────────────

def get_weather(city: str = "Tokyo") -> dict:
    try:
        data = requests.get(f"https://wttr.in/{city}?format=j1", timeout=10).json()
        cur = data["current_condition"][0]
        today = data["weather"][0]
        return {
            "city": city,
            "temp_c": cur["temp_C"],
            "feels_like_c": cur["FeelsLikeC"],
            "description": cur["weatherDesc"][0]["value"],
            "humidity": cur["humidity"],
            "max_temp_c": today["maxtempC"],
            "min_temp_c": today["mintempC"],
        }
    except Exception as e:
        return {"error": str(e), "city": city}


def get_weather_kansai() -> dict:
    return get_weather("Osaka")


def get_keihan_status() -> dict:
    try:
        import re
        resp = requests.get(
            "https://www.keihan.co.jp/traffic/unkou/",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        resp.encoding = "utf-8"

        # 運行情報の主要部分だけ抽出（ページ全体だと誤検知が多い）
        html = resp.text
        # メインコンテンツ部分を絞り込む
        main_match = re.search(r'<main[^>]*>(.*?)</main>', html, re.DOTALL)
        target = main_match.group(1) if main_match else html[:5000]

        text = re.sub(r"<[^>]+>", " ", target)
        text = re.sub(r"\s+", " ", text).strip()

        # 「現在」「ただいま」「発生中」などの現在進行形の表現と組み合わせて判定
        is_normal = (
            "平常通り運転" in text
            or "平常運転" in text
            or "平常どおり" in text
            or "遅れはございません" in text
        )
        is_delayed = (
            ("遅延" in text and ("現在" in text or "発生" in text or "ただいま" in text))
            or "大幅な遅れ" in text
        )
        is_suspended = "運転見合わせ" in text or "運休" in text

        if is_suspended:
            return {"status": "🚫 運転見合わせ", "detail": "一部区間で運転を見合わせています"}
        elif is_delayed:
            return {"status": "⚠️ 遅延あり", "detail": "京阪電車で遅延が発生しています"}
        elif is_normal:
            return {"status": "✅ 平常通り運転", "detail": "遅延・運転見合わせなし"}
        else:
            # 判定できない場合は平常通りとみなす
            return {"status": "✅ 平常通り運転", "detail": "情報取得済み（異常なし）"}
    except Exception:
        return {"status": "📡 取得エラー", "detail": "京阪公式サイトをご確認ください"}


# ─────────────────────────────────────────
# 市場センチメント
# ─────────────────────────────────────────

def get_fear_greed_index() -> dict:
    """Fear & Greed Index を取得（CNNのAPIが変更された場合の代替エンドポイント付き）"""
    endpoints = [
        "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
        "https://fear-and-greed-index.p.rapidapi.com/v1/fgi",
    ]
    label_map = {
        "Extreme Fear": "極度の恐怖 😱",
        "Fear": "恐怖 😨",
        "Neutral": "中立 😐",
        "Greed": "強欲 😏",
        "Extreme Greed": "極度の強欲 🤑",
    }
    try:
        resp = requests.get(
            endpoints[0],
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        # レスポンス形式の違いに対応
        if "fear_and_greed" in data:
            fg = data["fear_and_greed"]
            score = round(float(fg["score"]))
            rating = fg.get("rating", "Neutral")
        elif "fgi" in data:
            fg = data["fgi"]
            score = round(float(fg.get("now", {}).get("value", 50)))
            rating = fg.get("now", {}).get("valueText", "Neutral")
        else:
            return {"score": 50, "rating": "Neutral", "label_jp": "データ取得不可 😐"}

        return {
            "score": score,
            "rating": rating,
            "label_jp": label_map.get(rating, rating),
        }
    except Exception as e:
        return {"score": 50, "rating": "Neutral", "label_jp": f"取得エラー（{str(e)[:30]}）😐"}


# ─────────────────────────────────────────
# Hacker News
# ─────────────────────────────────────────

def get_hacker_news(limit: int = 5) -> list:
    try:
        top_ids = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10
        ).json()[:limit]
        results = []
        for story_id in top_ids:
            item = requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json", timeout=5
            ).json()
            if item and item.get("type") == "story":
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                    "score": item.get("score", 0),
                    "comments": item.get("descendants", 0),
                })
        return results
    except Exception as e:
        return [{"error": str(e)}]


# ─────────────────────────────────────────
# YouTube新着動画
# ─────────────────────────────────────────

def _fetch_channel_id_from_api(handle: str) -> str:
    """YouTube Data API v3でチャンネルIDを取得"""
    from config import YOUTUBE_API_KEY
    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"forHandle": f"@{handle}", "part": "id", "key": YOUTUBE_API_KEY},
            timeout=10,
        )
        items = resp.json().get("items", [])
        return items[0]["id"] if items else ""
    except Exception:
        return ""


def get_youtube_new_videos(hours: int = 48) -> list:
    from config import YOUTUBE_CHANNELS
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    results = []
    for ch in YOUTUBE_CHANNELS:
        handle = ch["handle"]
        name = ch["name"]
        # キャッシュから取得、なければAPIで取得してキャッシュ
        cid = get_channel_id(handle)
        if not cid:
            cid = _fetch_channel_id_from_api(handle)
            if cid:
                set_channel_id(handle, cid)
        if not cid:
            continue
        try:
            resp = requests.get(
                f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}",
                timeout=10,
            )
            if resp.status_code != 200:
                continue
            ns = {
                "a": "http://www.w3.org/2005/Atom",
                "yt": "http://www.youtube.com/xml/schemas/2015",
            }
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
                except Exception:
                    continue
                if published < cutoff:
                    continue
                title = entry.findtext("a:title", namespaces=ns, default="不明")
                vid = entry.find("yt:videoId", ns)
                url = f"https://youtu.be/{vid.text}" if vid is not None else ""
                jst_str = published.astimezone(
                    timezone(timedelta(hours=9))
                ).strftime("%m/%d %H:%M")
                results.append({
                    "channel": name,
                    "title": title,
                    "url": url,
                    "published": jst_str,
                })
        except Exception:
            continue
    return sorted(results, key=lambda x: x["published"], reverse=True)


# ─────────────────────────────────────────
# Google カレンダー
# ─────────────────────────────────────────

def get_calendar_events(days: int = 3) -> list:
    """Googleカレンダーから予定を取得する"""
    try:
        from googleapiclient.discovery import build
        # _get_google_creds()でスコープを統一（calendar + tasks）
        service = build("calendar", "v3", credentials=_get_google_creds())
        jst = timezone(timedelta(hours=9))
        now = datetime.now(jst)
        time_min = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        time_max = (now + timedelta(days=days)).replace(
            hour=23, minute=59, second=59
        ).isoformat()
        events_result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
            maxResults=20,
        ).execute()
        events = events_result.get("items", [])
        results = []
        for e in events:
            start = e["start"].get("dateTime", e["start"].get("date", ""))
            end = e["end"].get("dateTime", e["end"].get("date", ""))
            if "T" not in start:
                start_str = start
                end_str = end
            else:
                dt = datetime.fromisoformat(start).astimezone(jst)
                dt_end = datetime.fromisoformat(end).astimezone(jst)
                start_str = dt.strftime("%m/%d(%a) %H:%M")
                end_str = dt_end.strftime("%H:%M")
            results.append({
                "title": e.get("summary", "（タイトルなし）"),
                "start": start_str,
                "end": end_str,
                "location": e.get("location", ""),
            })
        return results if results else [{"message": f"今後{days}日間の予定はありません"}]
    except Exception as ex:
        return [{"error": str(ex)}]


# ─────────────────────────────────────────
# ツールディスパッチャー
# ─────────────────────────────────────────

def execute_tool(tool_name: str, tool_input: dict) -> str:
    dispatch = {
        "get_stock_price": get_stock_price,
        "get_portfolio_prices": get_portfolio_prices,
        "get_portfolio_pnl": get_portfolio_pnl,
        "get_exchange_rate": get_exchange_rate,
        "get_market_indices": get_market_indices,
        "web_search": web_search,
        "fetch_url_content": fetch_url_content,
        "get_weather": get_weather,
        "get_weather_kansai": get_weather_kansai,
        "get_keihan_status": get_keihan_status,
        "get_fear_greed_index": get_fear_greed_index,
        "get_hacker_news": get_hacker_news,
        "save_note": save_note,
        "get_notes": get_notes,
        "add_task": add_task,
        "get_tasks": get_tasks,
        "complete_task": complete_task,
        "get_youtube_new_videos": get_youtube_new_videos,
        "get_calendar_events": get_calendar_events,
        "add_agent_issue": add_agent_issue,
        "add_agent_proposal": add_agent_proposal,
        "update_gtd_status": update_gtd_status,
        "get_all_issues": get_all_issues,
        "get_subscribed_channels": get_subscribed_channels,
        "get_youtube_summary_videos": get_youtube_summary_videos,
        "get_google_tasks_due_soon": get_google_tasks_due_soon,
        "get_upcoming_tasks": get_upcoming_tasks,
        "get_google_task_lists": get_google_task_lists,
        "get_google_tasks": get_google_tasks,
        "add_google_task": add_google_task,
        "complete_google_task": complete_google_task,
    }
    fn = dispatch.get(tool_name)
    if not fn:
        return f"不明なツール: {tool_name}"
    try:
        result = fn(**tool_input)
        return (
            json.dumps(result, ensure_ascii=False, indent=2)
            if not isinstance(result, str)
            else result
        )
    except Exception as e:
        return f"ツールエラー ({tool_name}): {str(e)}"


# ─────────────────────────────────────────
# 課題・機能提案管理（GTD方式）
# ─────────────────────────────────────────

from storage import add_issue, update_issue_status, get_issues, GTD_LABELS


def add_agent_issue(agent_name: str, title: str, detail: str = "") -> str:
    """課題を追加する（issue_type='issue'）"""
    issue_id = add_issue(agent_name, title, detail, issue_type="issue")
    return f"✅ 課題#{issue_id}を追加しました: {title}"


def add_agent_proposal(agent_name: str, title: str, detail: str = "") -> str:
    """機能提案を追加する（issue_type='proposal'）"""
    issue_id = add_issue(agent_name, title, detail, issue_type="proposal")
    return f"💡 提案#{issue_id}を追加しました: {title}"


def update_gtd_status(issue_id: int, gtd_status: str) -> str:
    """GTDステータスを更新する"""
    success = update_issue_status(issue_id, gtd_status)
    if success:
        label = GTD_LABELS.get(gtd_status, gtd_status)
        return f"✅ #{issue_id} のステータスを「{label}」に更新しました"
    return f"⚠️ ステータス更新に失敗しました（有効値: {', '.join(GTD_LABELS.keys())}）"


def get_all_issues(agent_name: str = None, issue_type: str = None) -> list:
    """課題・提案一覧を取得する"""
    return get_issues(agent_name=agent_name, issue_type=issue_type, include_done=False)


# ─────────────────────────────────────────
# Google Tasks
# ─────────────────────────────────────────

def _get_google_creds():
    """Google OAuth認証情報を取得する"""
    from google.oauth2.credentials import Credentials
    return Credentials(
        token=None,
        refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN", ""),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
        scopes=[
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/tasks",
            "https://www.googleapis.com/auth/youtube.readonly",
        ],
    )


def get_google_task_lists() -> list:
    """Googleタスクのリスト一覧を取得する"""
    try:
        from googleapiclient.discovery import build
        creds = _get_google_creds()
        service = build("tasks", "v1", credentials=creds)
        result = service.tasklists().list(maxResults=20).execute()
        lists = result.get("items", [])
        if not lists:
            return [{"message": "タスクリストが0件です（Google Tasksにリストがありません）"}]
        return [{"id": lst["id"], "title": lst["title"]} for lst in lists]
    except Exception as e:
        return [{"error": f"Google Tasks APIエラー: {str(e)}"}]


def get_google_tasks(tasklist_title: str = "バケツリスト", show_completed: bool = False,
                     due_within_days: int = None) -> list:
    """指定したリストのタスクを取得する。due_within_days指定で期限N日以内のみ返す"""
    try:
        from googleapiclient.discovery import build
        from datetime import timezone, timedelta
        service = build("tasks", "v1", credentials=_get_google_creds())

        lists_result = service.tasklists().list(maxResults=20).execute()
        all_lists = lists_result.get("items", [])

        if not all_lists:
            return [{"error": "Googleタスクにリストが1つもありません"}]

        tasklist_id = None
        for lst in all_lists:
            if tasklist_title.lower() in lst["title"].lower():
                tasklist_id = lst["id"]
                break

        if not tasklist_id:
            list_names = [lst["title"] for lst in all_lists]
            return [{"error": f"「{tasklist_title}」が見つかりません", "利用可能なリスト": list_names}]

        result = service.tasks().list(
            tasklist=tasklist_id,
            showCompleted=show_completed,
            showHidden=show_completed,
            maxResults=100,
        ).execute()

        tasks = result.get("items", [])
        if not tasks:
            return [{"message": f"「{tasklist_title}」にタスクが0件です"}]

        output = []
        now = datetime.now(timezone.utc)
        for t in tasks:
            due_str = t.get("due", "")
            task_data = {
                "id": t["id"],
                "title": t.get("title", ""),
                "status": t.get("status", ""),
                "due": due_str,
                "notes": t.get("notes", ""),
                "tasklist_id": tasklist_id,
            }
            if due_within_days is not None:
                if not due_str:
                    continue
                try:
                    due_dt = datetime.fromisoformat(due_str.replace("Z", "+00:00"))
                    if due_dt <= now + timedelta(days=due_within_days):
                        output.append(task_data)
                except Exception:
                    continue
            else:
                output.append(task_data)

        if not output:
            return [{"message": f"期限{due_within_days}日以内のタスクはありません"}]
        return output
    except Exception as e:
        return [{"error": f"Google Tasks APIエラー: {str(e)}"}]


def add_google_task(title: str, notes: str = "", due: str = "",
                    tasklist_title: str = "バケツリスト") -> str:
    """Googleタスクにタスクを追加する"""
    try:
        from googleapiclient.discovery import build
        service = build("tasks", "v1", credentials=_get_google_creds())

        lists_result = service.tasklists().list(maxResults=20).execute()
        tasklist_id = None
        for lst in lists_result.get("items", []):
            if tasklist_title.lower() in lst["title"].lower():
                tasklist_id = lst["id"]
                break
        if not tasklist_id:
            items = lists_result.get("items", [])
            tasklist_id = items[0]["id"] if items else "@default"

        task_body = {"title": title}
        if notes:
            task_body["notes"] = notes
        if due:
            task_body["due"] = due

        result = service.tasks().insert(
            tasklist=tasklist_id, body=task_body
        ).execute()
        return f"✅ タスク追加: {result.get('title', title)}"
    except Exception as e:
        return f"⚠️ タスク追加エラー: {str(e)}"


def complete_google_task(task_id: str, tasklist_title: str = "バケツリスト") -> str:
    """Googleタスクを完了にする"""
    try:
        from googleapiclient.discovery import build
        service = build("tasks", "v1", credentials=_get_google_creds())

        lists_result = service.tasklists().list(maxResults=20).execute()
        tasklist_id = None
        for lst in lists_result.get("items", []):
            if tasklist_title.lower() in lst["title"].lower():
                tasklist_id = lst["id"]
                break
        if not tasklist_id:
            items = lists_result.get("items", [])
            tasklist_id = items[0]["id"] if items else "@default"

        service.tasks().patch(
            tasklist=tasklist_id,
            task=task_id,
            body={"status": "completed"},
        ).execute()
        return f"✅ タスク完了: #{task_id}"
    except Exception as e:
        return f"⚠️ タスク完了エラー: {str(e)}"


# ─────────────────────────────────────────
# YouTube購読チャンネルの新着動画（要約付き）
# ─────────────────────────────────────────

def get_subscribed_channels() -> list:
    """Googleアカウントの購読チャンネル一覧を取得する"""
    try:
        from googleapiclient.discovery import build
        service = build("youtube", "v3", credentials=_get_google_creds())
        channels = []
        next_page = None
        while True:
            req = service.subscriptions().list(
                part="snippet",
                mine=True,
                maxResults=50,
                pageToken=next_page,
            )
            resp = req.execute()
            for item in resp.get("items", []):
                snippet = item["snippet"]
                channels.append({
                    "channel_id": snippet["resourceId"]["channelId"],
                    "title": snippet["title"],
                })
            next_page = resp.get("nextPageToken")
            if not next_page:
                break
        return channels
    except Exception as e:
        return [{"error": f"購読チャンネル取得エラー: {str(e)}"}]


def get_youtube_summary_videos(hours: int = 24) -> list:
    """
    購読チャンネルのN時間以内の新着動画を取得し、
    字幕があれば要約付きで返す（5:30バッチ処理用）
    """
    import feedparser
    from datetime import timezone, timedelta

    try:
        # 購読チャンネルを取得
        channels = get_subscribed_channels()
        if not channels or "error" in channels[0]:
            return [{"error": "購読チャンネルを取得できませんでした"}]

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        new_videos = []

        for ch in channels:
            channel_id = ch.get("channel_id", "")
            if not channel_id:
                continue
            try:
                feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:5]:
                    published = entry.get("published_parsed")
                    if not published:
                        continue
                    from time import mktime
                    pub_dt = datetime.fromtimestamp(mktime(published), tz=timezone.utc)
                    if pub_dt < cutoff:
                        continue

                    video_id = entry.get("yt_videoid", "")
                    new_videos.append({
                        "channel": ch["title"],
                        "title": entry.get("title", ""),
                        "url": f"https://youtu.be/{video_id}",
                        "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
                        "video_id": video_id,
                        "published": pub_dt.strftime("%m/%d %H:%M"),
                        "thumbnail": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                    })
            except Exception:
                continue

        if not new_videos:
            return [{"message": f"過去{hours}時間の新着動画はありませんでした"}]

        # 字幕取得して要約（最大5件）
        for video in new_videos[:5]:
            video["summary"] = _get_video_summary(video["video_id"])

        return new_videos

    except Exception as e:
        return [{"error": f"YouTube新着取得エラー: {str(e)}"}]


def _get_video_summary(video_id: str) -> str:
    """字幕を取得してAnthropicで要約する"""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        # 日本語優先、なければ英語
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["ja", "en"])
        except Exception:
            return "（字幕なし）"

        # 先頭3000文字に制限（コスト節約）
        text = " ".join([t["text"] for t in transcript])[:6000]
        if not text.strip():
            return "（字幕なし）"

        # Claudeで要約（詳しめ・5〜7行）
        import anthropic
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": f"""以下の動画字幕を要約してください。

ルール:
- 5〜7行程度でしっかり内容を伝える
- 投資・株・AIの動画なら重要な銘柄・数字・主張を必ず含める
- 箇条書きで読みやすく
- 最後に「💡 ポイント:」で1行の結論を書く

字幕:
{text}"""
            }]
        )
        return resp.content[0].text.strip()
    except Exception:
        return "（要約取得エラー）"


def get_google_tasks_due_soon(days: int = 3) -> list:
    """
    全タスクリストを横断して期限N日以内のタスクを返す
    リスト名に依存しない
    """
    try:
        from googleapiclient.discovery import build
        from datetime import timezone, timedelta
        service = build("tasks", "v1", credentials=_get_google_creds())

        # 全リストを取得
        lists_result = service.tasklists().list(maxResults=20).execute()
        all_lists = lists_result.get("items", [])
        if not all_lists:
            return [{"message": "タスクリストが見つかりません"}]

        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=days)
        due_soon = []

        for lst in all_lists:
            try:
                result = service.tasks().list(
                    tasklist=lst["id"],
                    showCompleted=False,
                    maxResults=50,
                ).execute()
                for t in result.get("items", []):
                    due_str = t.get("due", "")
                    if not due_str:
                        continue
                    try:
                        due_dt = datetime.fromisoformat(due_str.replace("Z", "+00:00"))
                        if due_dt <= cutoff:
                            due_soon.append({
                                "title": t.get("title", ""),
                                "due": due_dt.strftime("%-m/%-d"),
                                "list": lst["title"],
                                "notes": t.get("notes", ""),
                            })
                    except Exception:
                        continue
            except Exception:
                continue

        if not due_soon:
            return [{"message": f"期限{days}日以内のタスクはありません"}]

        # 期限順にソート
        due_soon.sort(key=lambda x: x["due"])
        return due_soon

    except Exception as e:
        return [{"error": f"タスク取得エラー: {str(e)}"}]


def get_upcoming_tasks(due_within_days: int = 3) -> list:
    """
    全Googleタスクリストを横断して期限N日以内のタスクを返す
    リスト名に関係なく期限が近いものを優先順で返す
    """
    try:
        from googleapiclient.discovery import build
        from datetime import timezone, timedelta
        service = build("tasks", "v1", credentials=_get_google_creds())

        # 全リスト取得
        lists_result = service.tasklists().list(maxResults=20).execute()
        all_lists = lists_result.get("items", [])
        if not all_lists:
            return [{"message": "タスクリストがありません"}]

        cutoff = datetime.now(timezone.utc) + timedelta(days=due_within_days)
        upcoming = []

        for lst in all_lists:
            try:
                result = service.tasks().list(
                    tasklist=lst["id"],
                    showCompleted=False,
                    maxResults=50,
                ).execute()
                for t in result.get("items", []):
                    due_str = t.get("due", "")
                    if not due_str:
                        continue
                    try:
                        due_dt = datetime.fromisoformat(due_str.replace("Z", "+00:00"))
                        if due_dt <= cutoff:
                            upcoming.append({
                                "title": t.get("title", ""),
                                "due": due_dt.strftime("%m/%d"),
                                "list": lst["title"],
                                "notes": t.get("notes", ""),
                            })
                    except Exception:
                        continue
            except Exception:
                continue

        if not upcoming:
            return [{"message": f"期限{due_within_days}日以内のタスクはありません"}]

        # 期限順にソート
        upcoming.sort(key=lambda x: x["due"])
        return upcoming[:10]  # 最大10件

    except Exception as e:
        return [{"error": f"タスク取得エラー: {str(e)}"}]
