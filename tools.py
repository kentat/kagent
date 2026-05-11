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
        except:
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
        text = re.sub(r"<[^>]+>", " ", resp.text)
        text = re.sub(r"\s+", " ", text).strip()
        if "平常通り運転" in text or "平常運転" in text:
            return {"status": "✅ 平常通り運転", "detail": "遅延・運転見合わせなし"}
        elif "遅延" in text:
            return {"status": "⚠️ 遅延あり", "detail": "京阪電車で遅延が発生しています"}
        elif "運転見合わせ" in text or "運休" in text:
            return {"status": "🚫 運転見合わせ", "detail": "一部区間で運転を見合わせています"}
        else:
            return {"status": "📡 情報取得中", "detail": "京阪電車公式サイトをご確認ください"}
    except Exception as e:
        return {"status": "⚠️ 取得エラー", "detail": str(e)}


# ─────────────────────────────────────────
# 市場センチメント
# ─────────────────────────────────────────

def get_fear_greed_index() -> dict:
    try:
        resp = requests.get(
            "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        fg = resp.json()["fear_and_greed"]
        score = round(float(fg["score"]))
        rating = fg["rating"]
        label_map = {
            "Extreme Fear": "極度の恐怖 😱",
            "Fear": "恐怖 😨",
            "Neutral": "中立 😐",
            "Greed": "強欲 😏",
            "Extreme Greed": "極度の強欲 🤑",
        }
        return {
            "score": score,
            "rating": rating,
            "label_jp": label_map.get(rating, rating),
        }
    except Exception as e:
        return {"error": str(e)}


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
    except:
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
                except:
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
        except:
            continue
    return sorted(results, key=lambda x: x["published"], reverse=True)


# ─────────────────────────────────────────
# Google カレンダー
# ─────────────────────────────────────────

def get_calendar_events(days: int = 3) -> list:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN", "")

    if not all([client_id, client_secret, refresh_token]):
        return [{"error": "Google認証情報が設定されていません"}]
    try:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        )
        service = build("calendar", "v3", credentials=creds)
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
