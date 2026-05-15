"""
Webサーバー - Kenta Agent Dashboard
JOHNNY（Jony Ive哲学）によるデザイン
"""

import os
import re
import secrets
import sys
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from storage import get_report_cache, _use_redis, _get_redis
import json

app = FastAPI(title="Kenta Agent", docs_url=None, redoc_url=None)
security = HTTPBasic()

WEB_USERNAME = os.getenv("WEB_USERNAME", "")
WEB_PASSWORD = os.getenv("WEB_PASSWORD", "")

if not WEB_USERNAME or not WEB_PASSWORD:
    print("ERROR: WEB_USERNAME / WEB_PASSWORD が設定されていません", file=sys.stderr)
    sys.exit(1)


def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    ok_u = secrets.compare_digest(credentials.username, WEB_USERNAME)
    ok_p = secrets.compare_digest(credentials.password, WEB_PASSWORD)
    if not (ok_u and ok_p):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def _md_to_html(text: str) -> str:
    """MarkdownをHTMLに変換"""
    import re
    lines = text.split("\n")
    out = []
    in_list = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append('<div class="spacer"></div>')
            continue
        if stripped == "---":
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append('<hr class="divider">')
            continue
        if stripped.startswith("## "):
            if in_list:
                out.append("</ul>")
                in_list = False
            h = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', stripped[3:])
            out.append(f'<h2>{h}</h2>')
            continue
        if stripped.startswith("# "):
            if in_list:
                out.append("</ul>")
                in_list = False
            h = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', stripped[2:])
            out.append(f'<h1>{h}</h1>')
            continue
        if stripped.startswith(("• ", "- ", "· ")):
            if not in_list:
                out.append('<ul>')
                in_list = True
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', stripped[2:])
            # URLをリンクに変換
            content = re.sub(r'(https?://[^\s<>"]+)', r'<a href="\1" target="_blank">\1</a>', content)
            out.append(f'<li>{content}</li>')
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        p = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', stripped)
        # YouTubeリンクはサムネイル付きカードに変換
        def make_yt_card(m):
            url = m.group(1)
            if "youtu.be/" in url or "youtube.com/watch" in url:
                vid = re.search(r'(?:youtu\.be/|v=)([A-Za-z0-9_-]{11})', url)
                if vid:
                    v = vid.group(1)
                    return f'''<a href="{url}" target="_blank" class="yt-card">
                        <img src="https://img.youtube.com/vi/{v}/mqdefault.jpg" class="yt-thumb" loading="lazy">
                        <span class="yt-label">▶ YouTubeで見る</span>
                    </a>'''
            return f'<a href="{url}" target="_blank">{url}</a>'
        p = re.sub(r'(https?://[^\s<>"]+)', make_yt_card, p)
        out.append(f'<p>{p}</p>')
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def _parse_morning_data(content: str) -> dict:
    """テキストのモーニングブリーフからデータを抽出してdictに変換"""
    import re
    data = {
        "indices": [], "fx": "—", "fx_change": "",
        "fear_score": None, "fear_label": "",
        "pnl_jpy": "", "pnl_pct": "",
        "gainers": [], "losers": [],
        "weather_osaka": "", "weather_kyoto": "",
        "transit": "", "transit_ok": True,
        "tasks": [], "calendar": [],
        "youtube": [], "updated": "",
    }
    if not content:
        return data

    lines = content.split("\n")

    for line in lines:
        # 指数
        for name in ["S&P500", "NASDAQ", "DOW", "日経225"]:
            if name in line:
                m = re.search(r"([\d,]+\.?\d*)\s*[\(\+]?([-+]?\d+\.?\d*)%", line)
                if m:
                    data["indices"].append({"name": name, "value": m.group(1), "change": float(m.group(2))})
        # 為替
        if "USD/JPY" in line or "ドル円" in line:
            m = re.search(r"([\d,]+\.?\d+)", line)
            mc = re.search(r"([-+]?\d+\.?\d*)%", line)
            if m:
                data["fx"] = m.group(1)
                data["fx_change"] = mc.group(1) if mc else ""
        # Fear & Greed
        if "市場心理" in line or "Fear" in line:
            m = re.search(r"(\d+)/100", line)
            if m:
                data["fear_score"] = int(m.group(1))
                if "恐怖" in line:
                    data["fear_label"] = "恐怖"
                elif "強欲" in line:
                    data["fear_label"] = "強欲"
                else:
                    data["fear_label"] = "中立"
        # 損益
        if "損益" in line or "¥" in line:
            m = re.search(r"\+?¥([\d,]+)", line)
            mp = re.search(r"([-+]?\d+\.?\d*)%", line)
            if m and "損益" in line:
                data["pnl_jpy"] = "¥" + m.group(1)
            if mp and "損益" in line:
                data["pnl_pct"] = mp.group(1) + "%"
        # 天気
        if "大阪" in line:
            data["weather_osaka"] = line.strip().lstrip("•- ")
        if "京都" in line:
            data["weather_kyoto"] = line.strip().lstrip("•- ")
        # 京阪
        if "京阪" in line:
            data["transit"] = line.strip()
            data["transit_ok"] = "平常" in line or "✅" in line
        # タスク
        if any(k in line for k in ["TODO", "期限", "5/1", "5/2"]) and "•" in line:
            data["tasks"].append(line.strip().lstrip("•- "))
        # カレンダー
        if "誕生日" in line or ("5/" in line and "予定" not in line and "今日" not in line):
            data["calendar"].append(line.strip().lstrip("•- "))
        # YouTube
        if "📺" in line and "youtu" not in line.lower():
            yt_title = re.sub(r"📺\s*【.*?】", "", line).strip()
            if yt_title:
                ch_m = re.search(r"【(.+?)】", line)
                data["youtube"].append({
                    "channel": ch_m.group(1) if ch_m else "",
                    "title": yt_title,
                    "url": "",
                    "views": ""
                })
        if "youtu.be" in line:
            if data["youtube"]:
                data["youtube"][-1]["url"] = line.strip()
        if "👁" in line and data["youtube"]:
            vm = re.search(r"👁\s*(\S+)", line)
            if vm:
                data["youtube"][-1]["views"] = vm.group(1)

    return data


def _build_morning_dashboard(content: str, updated_at: str) -> str:
    """モーニングブリーフをダッシュボードUIで表示"""
    import json as _json

    try:
        if not updated_at:
            updated_jp = "未取得"
        else:
            from zoneinfo import ZoneInfo
            dt = datetime.fromisoformat(updated_at)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ZoneInfo("UTC"))
            dt_jst = dt.astimezone(ZoneInfo("Asia/Tokyo"))
            updated_jp = dt_jst.strftime("%-m/%-d %H:%M 更新")
            DOW = ["月", "火", "水", "木", "金", "土", "日"]
            date_label = f"{dt_jst.month}/{dt_jst.day}（{DOW[dt_jst.weekday()]}）"
    except Exception:
        updated_jp = "不明"
        date_label = ""

    d = _parse_morning_data(content)

    nav_html = ""
    for href, ico, label, key in [("/", "🌅", "Morning", "morning"), ("/evening", "🌆", "Evening", "evening"), ("/report", "📋", "日報", "daily"), ("/settings", "⚙️", "設定", "settings")]:
        active = "active" if key == "morning" else ""
        nav_html += f'<a href="{href}" class="nav-item {active}"><span class="nav-icon">{ico}</span><span class="nav-label">{label}</span></a>'

    # 指数HTML
    indices_html = ""
    for idx in d["indices"]:
        color = "#10b981" if idx["change"] >= 0 else "#ef4444"
        arrow = "▲" if idx["change"] >= 0 else "▼"
        indices_html += f'''
        <div class="idx-row">
          <div><div class="idx-name">{idx["name"]}</div><div class="idx-val">{idx["value"]}</div></div>
          <span class="idx-chg" style="color:{color}">{arrow}{abs(idx["change"])}%</span>
        </div>'''

    # Fear&Greedゲージ
    score = d["fear_score"] or 50
    fg_color = "#ef4444" if score < 30 else "#f97316" if score < 45 else "#eab308" if score < 55 else "#22c55e" if score < 75 else "#10b981"
    angle = (score / 100) * 180 - 90
    dashoffset = 157 - (score / 100) * 157

    # タスクHTML
    tasks_html = ""
    for t in (d["tasks"] or ["タスクなし"]):
        urgent = "5/1" in t and any(x in t for x in ["期限", "遅れ", "締切"])
        bg = "rgba(239,68,68,0.08)" if urgent else "rgba(255,255,255,0.03)"
        border = "rgba(239,68,68,0.3)" if urgent else "rgba(255,255,255,0.05)"
        badge = "🔴 " if urgent else ""
        tasks_html += f'<div class="task-item" style="background:{bg};border-color:{border}">{badge}{t}</div>'

    # カレンダーHTML
    cal_html = ""
    for ev in (d["calendar"] or ["予定なし"]):
        cal_html += f'<div class="cal-item">{ev}</div>'

    # YouTubeHTML
    yt_html = ""
    for v in (d["youtube"] or []):
        vid_m = __import__("re").search(r"youtu\.be/([A-Za-z0-9_-]+)", v.get("url", ""))
        thumb = f'https://img.youtube.com/vi/{vid_m.group(1)}/mqdefault.jpg' if vid_m else ""
        img_tag = f'<img src="{thumb}" class="yt-thumb" loading="lazy">' if thumb else '<div class="yt-thumb-placeholder">▶</div>'
        link_start = f'<a href="{v["url"]}" target="_blank" class="yt-card">' if v.get("url") else '<div class="yt-card">'
        link_end = "</a>" if v.get("url") else "</div>"
        yt_html += f'''{link_start}{img_tag}
          <div class="yt-info">
            <div class="yt-ch">{v["channel"]}</div>
            <div class="yt-title">{v["title"]}</div>
            {"<div class='yt-views'>👁 " + v["views"] + "</div>" if v.get("views") else ""}
          </div>{link_end}'''

    if not yt_html:
        yt_html = '<div style="color:#475569;font-size:13px;padding:16px">📭 過去24時間の新着動画はありませんでした</div>'

    # transit_color: used inline
    transit_dot = "#10b981" if d["transit_ok"] else "#ef4444"

    pnl_jpy = d.get("pnl_jpy") or "—"
    pnl_pct = d.get("pnl_pct") or ""
    pnl_color = "#10b981" if "+" in pnl_pct else "#ef4444" if "-" in pnl_pct else "#e2e8f0"

    empty_notice = "" if content else '<div style="text-align:center;padding:40px;color:#475569">まだデータがありません。<code>/collect</code> → <code>/morning</code> を実行してください。</div>'

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  <title>Morning Brief | Kenta Agent</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #020817; --surface: rgba(15,23,42,0.7); --surface2: rgba(30,41,59,0.5);
      --border: rgba(255,255,255,0.06); --text: #e2e8f0; --text2: #94a3b8; --text3: #475569;
      --green: #10b981; --red: #ef4444; --blue: #3b82f6;
      --nav-h: 64px; --radius: 14px;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }}
    body {{
      background: radial-gradient(ellipse at 20% 10%, rgba(16,185,129,0.05) 0%, transparent 50%),
                  radial-gradient(ellipse at 80% 90%, rgba(59,130,246,0.05) 0%, transparent 50%),
                  var(--bg);
      color: var(--text); font-family: 'JetBrains Mono', monospace; min-height: 100vh;
    }}
    header {{
      position: fixed; top: 0; left: 0; right: 0; height: 52px;
      background: rgba(2,8,23,0.85); backdrop-filter: blur(20px);
      border-bottom: 1px solid var(--border); display: flex; align-items: center;
      padding: 0 20px; z-index: 100;
    }}
    .logo {{ font-size: 15px; font-weight: 700; letter-spacing: 0.05em; }}
    .logo span {{ color: var(--green); }}
    .header-right {{ margin-left: auto; display: flex; align-items: center; gap: 8px; }}
    .live-dot {{ width: 6px; height: 6px; border-radius: 50%; background: var(--green); box-shadow: 0 0 8px var(--green); animation: pulse 2s infinite; }}
    .updated {{ font-size: 11px; color: var(--text3); }}

    main {{ max-width: 1100px; margin: 0 auto; padding: 68px 16px calc(var(--nav-h) + 24px); }}
    .date-heading {{ font-size: 20px; font-weight: 700; padding: 16px 0 20px; color: var(--text); }}

    .grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; margin-bottom: 14px; }}
    @media(max-width: 768px) {{ .grid {{ grid-template-columns: 1fr; }} }}

    .card {{
      background: var(--surface); backdrop-filter: blur(20px);
      border: 1px solid var(--border); border-radius: var(--radius);
      padding: 18px; box-shadow: 0 4px 24px rgba(0,0,0,0.4);
    }}
    .card.glow {{ border-color: rgba(16,185,129,0.25); box-shadow: 0 0 24px rgba(16,185,129,0.08), 0 4px 24px rgba(0,0,0,0.4); }}
    .sec-label {{ font-size: 10px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--text3); font-weight: 700; margin-bottom: 14px; }}

    .idx-row {{ display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--border); }}
    .idx-row:last-child {{ border-bottom: none; }}
    .idx-name {{ font-size: 11px; color: var(--text2); }}
    .idx-val {{ font-size: 16px; font-weight: 700; }}
    .idx-chg {{ font-size: 13px; font-weight: 600; }}

    .fx-rate {{ font-size: 28px; font-weight: 700; }}
    .gauge-wrap {{ display: flex; justify-content: center; margin-top: 4px; }}

    .pnl-main {{ text-align: center; padding: 8px 0 16px; }}
    .pnl-val {{ font-size: 30px; font-weight: 700; }}
    .pnl-sub {{ font-size: 13px; color: var(--text2); margin-top: 4px; }}

    .task-item {{
      border: 1px solid; border-radius: 8px; padding: 9px 12px;
      font-size: 13px; margin-bottom: 6px; line-height: 1.4;
    }}
    .cal-item {{ padding: 8px 0; border-bottom: 1px solid var(--border); font-size: 13px; }}
    .cal-item:last-child {{ border-bottom: none; }}

    .transit-row {{ display: flex; align-items: center; gap: 10px; }}
    .transit-dot {{ width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }}

    .yt-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }}
    .yt-card {{
      display: block; text-decoration: none; color: var(--text);
      background: var(--surface2); border: 1px solid var(--border);
      border-radius: 10px; overflow: hidden;
      transition: transform 0.2s, border-color 0.2s;
    }}
    .yt-card:hover {{ transform: translateY(-2px); border-color: rgba(16,185,129,0.3); }}
    .yt-thumb {{ width: 100%; aspect-ratio: 16/9; object-fit: cover; display: block; }}
    .yt-thumb-placeholder {{ width: 100%; aspect-ratio: 16/9; background: rgba(15,23,42,0.8); display: flex; align-items: center; justify-content: center; font-size: 28px; color: var(--text3); }}
    .yt-info {{ padding: 10px 12px; }}
    .yt-ch {{ font-size: 10px; color: var(--green); margin-bottom: 4px; letter-spacing: 0.06em; }}
    .yt-title {{ font-size: 12px; font-weight: 600; line-height: 1.4; margin-bottom: 6px; }}
    .yt-views {{ font-size: 10px; color: var(--text3); }}

    nav {{
      position: fixed; bottom: 0; left: 0; right: 0; height: var(--nav-h);
      background: rgba(2,8,23,0.9); backdrop-filter: blur(20px);
      border-top: 1px solid var(--border); display: flex;
      align-items: flex-start; padding-top: 8px; z-index: 100;
    }}
    .nav-item {{ flex: 1; display: flex; flex-direction: column; align-items: center; gap: 3px; text-decoration: none; color: var(--text3); padding: 4px 0; }}
    .nav-item.active {{ color: var(--green); }}
    .nav-icon {{ font-size: 20px; }}
    .nav-label {{ font-size: 10px; font-weight: 600; }}

    @keyframes pulse {{ 0%,100% {{ opacity:1 }} 50% {{ opacity:0.4 }} }}
    @keyframes urgentPulse {{ 0%,100% {{ box-shadow: 0 0 0 0 rgba(239,68,68,0) }} 50% {{ box-shadow: 0 0 0 4px rgba(239,68,68,0.15) }} }}
  </style>
</head>
<body>
<header>
  <div class="logo">🏯 <span>KENTA</span> AGENT</div>
  <div class="header-right">
    <div class="live-dot"></div>
    <div class="updated">{updated_jp}</div>
  </div>
</header>

<main>
  {empty_notice}
  <div class="date-heading">🌅 {date_label} Morning Brief</div>

  <div class="grid">
    <!-- 左：市況 -->
    <div style="display:flex;flex-direction:column;gap:12px">
      <div class="card">
        <div class="sec-label">📈 Market Indices</div>
        {indices_html or '<div style="color:var(--text3);font-size:13px">データなし</div>'}
      </div>
      <div class="card">
        <div class="sec-label">💱 USD / JPY</div>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span class="fx-rate">¥{d["fx"]}</span>
          <span style="color:var(--text2);font-size:13px">{d["fx_change"]}%</span>
        </div>
      </div>
      <div class="card">
        <div class="sec-label">😱 Fear &amp; Greed</div>
        <div class="gauge-wrap">
          <svg width="130" height="75" viewBox="0 0 130 75">
            <defs>
              <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stop-color="#ef4444"/>
                <stop offset="25%" stop-color="#f97316"/>
                <stop offset="50%" stop-color="#eab308"/>
                <stop offset="75%" stop-color="#22c55e"/>
                <stop offset="100%" stop-color="#10b981"/>
              </linearGradient>
            </defs>
            <path d="M 15 65 A 50 50 0 0 1 115 65" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="8" stroke-linecap="round"/>
            <path d="M 15 65 A 50 50 0 0 1 115 65" fill="none" stroke="url(#g)" stroke-width="8" stroke-linecap="round" stroke-dasharray="157" stroke-dashoffset="{dashoffset:.0f}"/>
            <g transform="rotate({angle:.0f}, 65, 65)">
              <line x1="65" y1="65" x2="65" y2="23" stroke="white" stroke-width="2" stroke-linecap="round"/>
              <circle cx="65" cy="65" r="4" fill="white"/>
            </g>
            <text x="65" y="74" text-anchor="middle" fill="white" font-size="13" font-weight="700" font-family="JetBrains Mono">{score}</text>
          </svg>
        </div>
        <div style="text-align:center;font-size:12px;font-weight:600;color:{fg_color};margin-top:4px">{d["fear_label"]}</div>
      </div>
    </div>

    <!-- 中：ポートフォリオ -->
    <div style="display:flex;flex-direction:column;gap:12px">
      <div class="card glow">
        <div class="sec-label">💰 Portfolio</div>
        <div class="pnl-main">
          <div class="pnl-val" style="color:{pnl_color}">{pnl_jpy}</div>
          <div style="font-size:18px;font-weight:700;color:{pnl_color};opacity:0.85">{pnl_pct}</div>
        </div>
      </div>
      <div class="card">
        <div class="sec-label">🚃 Transit</div>
        <div class="transit-row">
          <div class="transit-dot" style="background:{transit_dot};box-shadow:0 0 8px {transit_dot}"></div>
          <span style="font-size:13px">{d["transit"] or "京阪電車"}</span>
        </div>
      </div>
      <div class="card">
        <div class="sec-label">🌤 Weather</div>
        <div style="font-size:13px;color:var(--text2);line-height:2">{d["weather_osaka"] or "大阪: —"}<br>{d["weather_kyoto"] or "京都: —"}</div>
      </div>
    </div>

    <!-- 右：タスク・カレンダー -->
    <div style="display:flex;flex-direction:column;gap:12px">
      <div class="card">
        <div class="sec-label">✅ Tasks</div>
        {tasks_html or '<div style="color:var(--text3);font-size:13px">期限近いタスクなし</div>'}
      </div>
      <div class="card">
        <div class="sec-label">📅 Calendar</div>
        {cal_html or '<div style="color:var(--text3);font-size:13px">予定なし</div>'}
      </div>
    </div>
  </div>

  <!-- YouTube -->
  <div class="card">
    <div class="sec-label">📺 YouTube — 注目動画</div>
    <div class="yt-grid">{yt_html}</div>
  </div>
</main>

<nav>{nav_html}</nav>
</body>
</html>"""


def _build_page(report_type: str, content: str, updated_at: str) -> str:
    # モーニングはダッシュボードUIで表示
    if report_type == "morning":
        return _build_morning_dashboard(content, updated_at)


    try:
        if not updated_at:
            updated_jp = "未取得"
        else:
            from zoneinfo import ZoneInfo
            dt = datetime.fromisoformat(updated_at)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ZoneInfo("UTC"))
            dt_jst = dt.astimezone(ZoneInfo("Asia/Tokyo"))
            updated_jp = dt_jst.strftime("%-m/%-d %H:%M 更新")
    except Exception:
        updated_jp = "不明"

    body_html = _md_to_html(content) if content else """
        <div class="empty">
            <div class="empty-icon">🏯</div>
            <p class="empty-title">まだレポートがありません</p>
            <p class="empty-sub">Telegramで <code>/morning</code> を実行すると<br>ここに表示されます</p>
        </div>"""

    nav_items = [
        ("/",        "🌅", "Morning", "morning"),
        ("/evening", "🌆", "Evening", "evening"),
        ("/report",  "📋", "日報",    "daily"),
    ]
    nav_html = ""
    for href, ico, label, key in nav_items:
        active = "active" if key == report_type else ""
        nav_html += f'<a href="{href}" class="nav-item {active}"><span class="nav-icon">{ico}</span><span class="nav-label">{label}</span></a>'

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <title>Kenta Agent</title>
  <style>
    :root {{
      --bg:       #000000;
      --surface:  #111111;
      --surface2: #1a1a1a;
      --border:   rgba(255,255,255,0.08);
      --text:     #f5f5f7;
      --text2:    #86868b;
      --text3:    #515154;
      --accent:   #2997ff;
      --accent2:  #30d158;
      --warn:     #ff9f0a;
      --danger:   #ff453a;
      --radius:   16px;
      --nav-h:    64px;
      --safe-bot: env(safe-area-inset-bottom, 0px);
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }}

    html, body {{
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Hiragino Sans",
                   "Noto Sans JP", sans-serif;
      font-size: 15px;
      line-height: 1.7;
      min-height: 100vh;
      -webkit-font-smoothing: antialiased;
    }}

    /* ── Header ── */
    header {{
      position: fixed;
      top: 0; left: 0; right: 0;
      height: 52px;
      background: rgba(0,0,0,0.85);
      backdrop-filter: saturate(180%) blur(20px);
      -webkit-backdrop-filter: saturate(180%) blur(20px);
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      padding: 0 20px;
      z-index: 100;
      padding-top: env(safe-area-inset-top, 0px);
    }}
    .logo {{
      font-size: 17px;
      font-weight: 600;
      color: var(--text);
      letter-spacing: -0.3px;
    }}
    .logo span {{ color: var(--accent); }}
    .updated {{
      margin-left: auto;
      font-size: 12px;
      color: var(--text3);
    }}

    /* ── Main ── */
    main {{
      max-width: 680px;
      margin: 0 auto;
      padding: 72px 16px calc(var(--nav-h) + var(--safe-bot) + 24px);
    }}

    /* ── Page title ── */
    .page-header {{
      padding: 24px 0 16px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 20px;
    }}
    .page-title {{
      font-size: 28px;
      font-weight: 700;
      letter-spacing: -0.5px;
      color: var(--text);
    }}

    /* ── Content ── */
    .content {{ }}

    h1 {{
      font-size: 20px;
      font-weight: 600;
      color: var(--accent);
      margin: 20px 0 8px;
      letter-spacing: -0.3px;
    }}
    h2 {{
      font-size: 13px;
      font-weight: 600;
      color: var(--text2);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin: 20px 0 8px;
    }}
    p {{
      font-size: 15px;
      color: var(--text);
      margin: 4px 0;
    }}
    .divider {{
      border: none;
      border-top: 1px solid var(--border);
      margin: 16px 0;
    }}
    .spacer {{ height: 4px; }}
    ul {{
      list-style: none;
      background: var(--surface);
      border-radius: var(--radius);
      border: 1px solid var(--border);
      overflow: hidden;
      margin: 8px 0;
    }}
    li {{
      font-size: 14px;
      color: var(--text);
      padding: 12px 16px;
      border-bottom: 1px solid var(--border);
      line-height: 1.6;
    }}
    li:last-child {{ border-bottom: none; }}
    li::before {{ display: none; }}
    strong {{ color: var(--text); font-weight: 600; }}
    a {{
      color: var(--accent);
      text-decoration: none;
      word-break: break-all;
    }}
    a:hover {{ text-decoration: underline; }}
    code {{
      font-family: "SF Mono", "Fira Code", monospace;
      font-size: 13px;
      background: var(--surface2);
      color: var(--accent2);
      padding: 2px 6px;
      border-radius: 6px;
    }}

    /* ── Empty state ── */
    .empty {{
      text-align: center;
      padding: 80px 20px;
    }}
    .empty-icon {{ font-size: 52px; margin-bottom: 16px; }}
    .empty-title {{
      font-size: 20px;
      font-weight: 600;
      color: var(--text);
      margin-bottom: 8px;
    }}
    .empty-sub {{
      font-size: 14px;
      color: var(--text2);
      line-height: 1.8;
    }}

    /* ── Bottom Nav ── */
    nav {{
      position: fixed;
      bottom: 0; left: 0; right: 0;
      height: calc(var(--nav-h) + var(--safe-bot));
      background: rgba(0,0,0,0.85);
      backdrop-filter: saturate(180%) blur(20px);
      -webkit-backdrop-filter: saturate(180%) blur(20px);
      border-top: 1px solid var(--border);
      display: flex;
      align-items: flex-start;
      padding-top: 8px;
      padding-bottom: var(--safe-bot);
      z-index: 100;
    }}
    .nav-item {{
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 3px;
      text-decoration: none;
      color: var(--text3);
      transition: color 0.15s;
      padding: 4px 0;
    }}
    .nav-item.active {{ color: var(--accent); }}
    .nav-icon {{ font-size: 22px; line-height: 1; }}
    .nav-label {{ font-size: 10px; font-weight: 500; letter-spacing: 0.02em; }}

    /* ── Animations ── */
    .content {{ animation: fadeIn 0.3s ease; }}
    @keyframes fadeIn {{
      from {{ opacity: 0; transform: translateY(6px); }}
      to   {{ opacity: 1; transform: translateY(0); }}
    }}

    /* ── YouTube Card ── */
    .yt-card {{
      display: block;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      overflow: hidden;
      margin: 8px 0;
      text-decoration: none;
    }}
    .yt-thumb {{
      width: 100%;
      height: 180px;
      object-fit: cover;
      display: block;
    }}
    .yt-label {{
      display: block;
      padding: 8px 12px;
      font-size: 13px;
      color: var(--accent);
      font-weight: 500;
    }}

    @media (prefers-color-scheme: light) {{
      :root {{
        --bg: #f2f2f7;
        --surface: #ffffff;
        --surface2: #f2f2f7;
        --border: rgba(0,0,0,0.1);
        --text: #1d1d1f;
        --text2: #6e6e73;
        --text3: #aeaeb2;
      }}
      header, nav {{
        background: rgba(242,242,247,0.85);
      }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="logo">🏯 <span>Kenta</span> Agent</div>
    <div class="updated">{updated_jp}</div>
  </header>

  <main>
    <div class="page-header">
      <div class="page-title">{icon} {title}</div>
    </div>
    <div class="content">
      {body_html}
    </div>
  </main>

  <nav>{nav_html}</nav>
</body>
</html>"""


def _get_morning_dashboard() -> HTMLResponse:
    """モーニングブリーフをダッシュボードUIで返す"""
    import re as _re
    from zoneinfo import ZoneInfo
    from datetime import datetime as _dt

    cache = get_report_cache("morning")
    raw   = cache.get("content", "")
    updated_at = cache.get("updated_at", "")

    # 更新日時
    try:
        dt = datetime.fromisoformat(updated_at)
        if dt.tzinfo is None:
            from zoneinfo import ZoneInfo as _ZI
            dt = dt.replace(tzinfo=_ZI("UTC"))
        dt_jst = dt.astimezone(ZoneInfo("Asia/Tokyo"))
        updated_jp = dt_jst.strftime("%-m/%-d %H:%M 更新")
    except Exception:
        updated_jp = "未取得"

    # キャッシュなし
    if not raw:
        return HTMLResponse(_dashboard_empty(updated_jp))

    # テキストから各セクションをパース
    def extract(label):
        pat = rf"{re.escape(label)}.*?\n(.*?)(?=\n---|\Z)"
        m = _re.search(pat, raw, _re.DOTALL)
        return m.group(1).strip() if m else ""

    market_raw   = extract("📈")
    psycho_raw   = extract("😱") or extract("😐")
    portfolio_raw= extract("💰")
    weather_raw  = extract("🌤")
    todo_raw     = extract("✅")
    cal_raw      = extract("📅")
    yt_raw       = extract("📺")

    def to_items(text):
        items = []
        for line in text.split("\n"):
            line = line.strip().lstrip("•·-").strip()
            if line:
                items.append(line)
        return items

    market_items   = to_items(market_raw)
    psycho_items   = to_items(psycho_raw)
    portfolio_items= to_items(portfolio_raw)
    weather_items  = to_items(weather_raw)
    todo_items     = to_items(todo_raw)
    cal_items      = to_items(cal_raw)
    yt_items       = to_items(yt_raw)

    def items_html(items, urgent_kw=None):
        rows = ""
        for item in items:
            is_urgent = urgent_kw and any(k in item for k in urgent_kw)
            color = "#fca5a5" if is_urgent else "#cbd5e1"
            bg    = "rgba(239,68,68,0.08)" if is_urgent else "rgba(255,255,255,0.02)"
            bdr   = "rgba(239,68,68,0.25)" if is_urgent else "rgba(255,255,255,0.05)"
            rows += f'<div style="padding:8px 10px;border-radius:8px;background:{bg};border:1px solid {bdr};margin-bottom:6px;font-size:13px;color:{color};line-height:1.5">{item}</div>'
        return rows or '<div style="color:#475569;font-size:13px">なし</div>'

    # YouTube行をリンク付きカードに
    yt_cards = ""
    for item in yt_items[:8]:
        url_m = _re.search(r"(https://youtu\.be/\S+)", item)
        url   = url_m.group(1) if url_m else "#"
        title = _re.sub(r"https://\S+", "", item).strip().lstrip("🔗📺").strip()
        yt_cards += f'''<a href="{url}" target="_blank" style="display:block;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:12px;text-decoration:none;transition:border-color 0.2s"
            onmouseover="this.style.borderColor='rgba(16,185,129,0.3)'" onmouseout="this.style.borderColor='rgba(255,255,255,0.06)'">
            <div style="font-size:12px;color:#94a3b8;line-height:1.5">{title[:80]}</div>
            <div style="font-size:10px;color:#10b981;margin-top:4px">▶ 視聴する</div>
        </a>'''

    nav = '''<nav style="position:fixed;bottom:0;left:0;right:0;height:60px;background:rgba(2,8,23,0.9);backdrop-filter:blur(20px);border-top:1px solid rgba(255,255,255,0.06);display:flex;align-items:flex-start;padding-top:8px;z-index:100">
        <a href="/" style="flex:1;display:flex;flex-direction:column;align-items:center;gap:2px;text-decoration:none;color:#2997ff"><span style="font-size:20px">🌅</span><span style="font-size:9px;font-weight:600">Morning</span></a>
        <a href="/evening" style="flex:1;display:flex;flex-direction:column;align-items:center;gap:2px;text-decoration:none;color:#475569"><span style="font-size:20px">🌆</span><span style="font-size:9px">Evening</span></a>
        <a href="/report" style="flex:1;display:flex;flex-direction:column;align-items:center;gap:2px;text-decoration:none;color:#475569"><span style="font-size:20px">📋</span><span style="font-size:9px">日報</span></a>
        <a href="/settings" style="flex:1;display:flex;flex-direction:column;align-items:center;gap:2px;text-decoration:none;color:#475569"><span style="font-size:20px">⚙️</span><span style="font-size:9px">設定</span></a>
    </nav>'''

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
  <title>Morning Brief | Kenta Agent</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:radial-gradient(ellipse at 20% 10%,rgba(16,185,129,.05) 0%,transparent 50%),radial-gradient(ellipse at 80% 90%,rgba(59,130,246,.05) 0%,transparent 50%),#020817;color:#e2e8f0;font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Noto Sans JP",sans-serif;min-height:100vh;padding-bottom:80px}}
    .header{{position:sticky;top:0;background:rgba(2,8,23,.85);backdrop-filter:blur(20px);border-bottom:1px solid rgba(255,255,255,.06);padding:12px 16px;display:flex;align-items:center;gap:12px;z-index:50}}
    .card{{background:rgba(15,23,42,.7);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,.06);border-radius:14px;padding:16px}}
    .card-glow{{border-color:rgba(16,185,129,.25);box-shadow:0 0 20px rgba(16,185,129,.08)}}
    .label{{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:#475569;font-weight:700;margin-bottom:10px}}
    .grid3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}}
    .grid2{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}
    @media(max-width:700px){{.grid3{{grid-template-columns:1fr}}.grid2{{grid-template-columns:1fr}}}}
  </style>
</head>
<body>
<div class="header">
  <span style="font-size:15px;font-weight:700">🏯 <span style="color:#2997ff">Kenta</span> Agent</span>
  <span style="font-size:20px;font-weight:700">🌅 モーニングブリーフ</span>
  <span style="margin-left:auto;font-size:11px;color:#475569">{updated_jp}</span>
</div>

<div style="padding:16px;display:flex;flex-direction:column;gap:12px;max-width:900px;margin:0 auto">

  <div class="grid3">
    <!-- 市況 -->
    <div class="card">
      <div class="label">📈 市況</div>
      {items_html(market_items)}
    </div>
    <!-- ポートフォリオ -->
    <div class="card card-glow">
      <div class="label">💰 ポートフォリオ</div>
      {items_html(portfolio_items)}
    </div>
    <!-- 市場心理 -->
    <div class="card">
      <div class="label">😱 市場心理</div>
      {items_html(psycho_items)}
    </div>
  </div>

  <div class="grid3">
    <!-- 天気 -->
    <div class="card">
      <div class="label">🌤 天気・交通</div>
      {items_html(weather_items)}
    </div>
    <!-- TODO -->
    <div class="card">
      <div class="label">✅ 今日のTODO</div>
      {items_html(todo_items, urgent_kw=["期限", "遅れ", "⚠"])}
    </div>
    <!-- 予定 -->
    <div class="card">
      <div class="label">📅 予定</div>
      {items_html(cal_items)}
    </div>
  </div>

  <!-- YouTube -->
  <div class="card">
    <div class="label">📺 YouTube 新着</div>
    <div class="grid2" style="grid-template-columns:repeat(auto-fill,minmax(200px,1fr))">
      {yt_cards if yt_cards else '<div style="color:#475569;font-size:13px">新着なし</div>'}
    </div>
  </div>

</div>
{nav}
</body>
</html>"""
    return HTMLResponse(html)


def _dashboard_empty(updated_jp: str) -> str:
    return f"""<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Morning Brief</title><style>body{{background:#020817;color:#e2e8f0;font-family:-apple-system,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;flex-direction:column;gap:16px}}</style></head>
    <body><div style="font-size:48px">🌅</div><div style="font-size:18px;font-weight:700">まだレポートがありません</div>
    <div style="color:#475569;font-size:14px">Telegramで /collect → /morning を実行してください</div>
    <div style="color:#334155;font-size:12px">{updated_jp}</div></body></html>"""


def _get_page(report_type: str) -> HTMLResponse:
    cache = get_report_cache(report_type)
    content    = cache.get("content", "")
    updated_at = cache.get("updated_at", "")  # 空なら「未取得」として表示
    return HTMLResponse(_build_page(report_type, content, updated_at))


@app.get("/api/portfolio")
def api_portfolio_get(username: str = Depends(verify_credentials)):
    """ポートフォリオ取得（Redisの user_portfolio キー）"""
    if _use_redis():
        data = _get_redis().get("user_portfolio")
        if data:
            return json.loads(data)
    return []


@app.post("/api/portfolio")
async def api_portfolio_post(request: Request, username: str = Depends(verify_credentials)):
    """ポートフォリオ保存（Redisの user_portfolio キーに保存）"""
    body = await request.json()
    # フロントは { positions: [...] } または { portfolio: [...] } で送る
    portfolio = body.get("positions") or body.get("portfolio", [])
    # tickerを大文字に統一
    for item in portfolio:
        if "ticker" in item:
            item["ticker"] = item["ticker"].upper()
    if _use_redis():
        _get_redis().set("user_portfolio", json.dumps(portfolio))
    return {"ok": True, "count": len(portfolio)}


@app.get("/settings", response_class=HTMLResponse)
def settings_page(username: str = Depends(verify_credentials)):
    from web_settings import settings_html
    return HTMLResponse(settings_html())


@app.get("/api/portfolio/csv")
def api_portfolio_csv_export(username: str = Depends(verify_credentials)):
    """ポートフォリオCSVエクスポート"""
    from web_settings import export_csv_response
    return export_csv_response()


@app.post("/api/portfolio/csv")
async def api_portfolio_csv_import(request: Request, username: str = Depends(verify_credentials)):
    """ポートフォリオCSVインポート"""
    from fastapi import UploadFile
    from web_settings import import_csv_data
    form = await request.form()
    file = form.get("file")
    if not file:
        return {"ok": False, "error": "ファイルがありません"}
    content = await file.read()
    count = import_csv_data(content)
    return {"ok": True, "count": count}


@app.get("/api/rate")
def api_rate(username: str = Depends(verify_credentials)):
    try:
        import yfinance as yf
        t = yf.Ticker("USDJPY=X")
        h = t.history(period="1d")
        rate = float(h["Close"].iloc[-1]) if not h.empty else 155.0
    except Exception:
        rate = 155.0
    return {"rate": rate}


@app.get("/api/prices")
def api_prices(tickers: str, username: str = Depends(verify_credentials)):
    try:
        import yfinance as yf
        prices = {}
        for ticker in [t.strip() for t in tickers.split(",") if t.strip()]:
            try:
                info = yf.Ticker(ticker).info
                prices[ticker] = info.get("currentPrice") or info.get("regularMarketPrice", 0)
            except Exception:
                prices[ticker] = 0
        return prices
    except Exception:
        return {}


@app.get("/debug")
def debug(username: str = Depends(verify_credentials)):
    """デバッグ用：Redis接続とキャッシュの状態確認"""
    redis_ok = _use_redis()
    result = {"redis_connected": redis_ok}
    if redis_ok:
        r = _get_redis()
        result["redis_keys"] = r.keys("report:*")
    result["morning_cache"] = bool(get_report_cache("morning"))
    result["evening_cache"] = bool(get_report_cache("evening"))
    return result


    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
def morning(username: str = Depends(verify_credentials)):
    return _get_morning_dashboard()

@app.get("/evening", response_class=HTMLResponse)
def evening(username: str = Depends(verify_credentials)):
    return _get_page("evening")

@app.get("/report", response_class=HTMLResponse)
def report(username: str = Depends(verify_credentials)):
    return _get_page("daily")
