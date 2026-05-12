"""
Webサーバー - Kenta Agent Dashboard
JOHNNY（Jony Ive哲学）によるデザイン
"""

import os
import secrets
import sys
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from storage import get_report_cache

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
        p = re.sub(r'(https?://[^\s<>"]+)', r'<a href="\1" target="_blank">\1</a>', p)
        out.append(f'<p>{p}</p>')
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def _build_page(report_type: str, content: str, updated_at: str) -> str:
    titles = {"morning": "Morning Brief", "evening": "Evening News", "daily": "Daily Report"}
    icons  = {"morning": "🌅", "evening": "🌆", "daily": "📋"}
    title  = titles.get(report_type, "Report")
    icon   = icons.get(report_type, "📄")

    try:
        dt = datetime.fromisoformat(updated_at)
        updated_jp = dt.strftime("%-m月%-d日 %H:%M")
    except Exception:
        updated_jp = updated_at

    body_html = _md_to_html(content) if content else """
        <div class="empty">
            <div class="empty-icon">🏯</div>
            <p class="empty-title">まだレポートがありません</p>
            <p class="empty-sub">Telegramで <code>/morning</code> を実行すると<br>ここに表示されます</p>
        </div>"""

    nav_items = [
        ("/",        "🌅", "Morning",  "morning"),
        ("/evening", "🌆", "Evening",  "evening"),
        ("/report",  "📋", "Daily",    "daily"),
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


def _get_page(report_type: str) -> HTMLResponse:
    cache = get_report_cache(report_type)
    content    = cache.get("content", "")
    updated_at = cache.get("updated_at", datetime.now().isoformat())
    return HTMLResponse(_build_page(report_type, content, updated_at))


@app.get("/debug")
def debug(username: str = Depends(verify_credentials)):
    """デバッグ用：Redis接続とキャッシュの状態確認"""
    from storage import _use_redis, _get_redis, get_report_cache
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
    return _get_page("morning")

@app.get("/evening", response_class=HTMLResponse)
def evening(username: str = Depends(verify_credentials)):
    return _get_page("evening")

@app.get("/report", response_class=HTMLResponse)
def report(username: str = Depends(verify_credentials)):
    return _get_page("daily")
