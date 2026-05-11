"""
Webサーバー - モーニングブリーフのHTML表示
============================================
エンドポイント:
  GET /          → 最新モーニングブリーフ
  GET /evening   → 最新夕方ニュース
  GET /report    → 最新日報
  GET /health    → ヘルスチェック（認証不要）

Basic認証:
  環境変数 WEB_USERNAME / WEB_PASSWORD で設定
  デフォルト: kenta / kenta2026
============================================
"""

import os
import secrets
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from storage import get_report_cache

app = FastAPI(title="Kenta Agent Dashboard", docs_url=None, redoc_url=None)
security = HTTPBasic()

WEB_USERNAME = os.getenv("WEB_USERNAME", "kenta")
WEB_PASSWORD = os.getenv("WEB_PASSWORD", "kenta2026")


def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Basic認証チェック"""
    correct_user = secrets.compare_digest(credentials.username, WEB_USERNAME)
    correct_pass = secrets.compare_digest(credentials.password, WEB_PASSWORD)
    if not (correct_user and correct_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証に失敗しました",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def _markdown_to_html(text: str) -> str:
    """MarkdownをシンプルなHTMLに変換する"""
    import re
    lines = text.split("\n")
    html_lines = []

    for line in lines:
        # 見出し
        if line.startswith("## "):
            line = f"<h2>{line[3:]}</h2>"
        elif line.startswith("# "):
            line = f"<h1>{line[2:]}</h1>"
        # 区切り線
        elif line.strip() == "---":
            line = "<hr>"
        # 箇条書き
        elif line.startswith("• ") or line.startswith("- "):
            content = line[2:]
            # **太字** 処理
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
            line = f"<li>{content}</li>"
        # 太字
        else:
            line = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
            if line.strip():
                line = f"<p>{line}</p>"

    return "\n".join(html_lines) if html_lines else "\n".join(
        f"<p>{l}</p>" if l.strip() and not l.startswith("<") else l
        for l in lines
    )


def _build_html(title: str, content: str, updated_at: str, report_type: str) -> str:
    """レポートをHTMLページに変換する"""
    import re

    # Markdownの太字・リストを処理
    content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
    content = re.sub(r'^## (.+)$', r'<h2>\1</h2>', content, flags=re.MULTILINE)
    content = re.sub(r'^# (.+)$', r'<h1>\1</h1>', content, flags=re.MULTILINE)
    content = re.sub(r'^---+$', r'<hr>', content, flags=re.MULTILINE)
    content = re.sub(r'^[•\-] (.+)$', r'<li>\1</li>', content, flags=re.MULTILINE)
    # li タグを ul で囲む
    content = re.sub(r'(<li>.*?</li>\n?)+', lambda m: f'<ul>{m.group()}</ul>', content, flags=re.DOTALL)
    # 残りのテキスト行をpに
    lines = []
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("<"):
            lines.append(line)
        else:
            lines.append(f"<p>{line}</p>")
    content_html = "\n".join(lines)

    # 更新時刻を日本語に
    try:
        dt = datetime.fromisoformat(updated_at)
        updated_jp = dt.strftime("%Y年%m月%d日 %H:%M")
    except:
        updated_jp = updated_at

    nav_items = [
        ("/", "🌅 モーニング"),
        ("/evening", "🌆 夕方ニュース"),
        ("/report", "📋 日報"),
    ]
    nav_html = " ".join(
        f'<a href="{href}" class="{"active" if href == ("/" if report_type == "morning" else f"/{report_type}") else ""}">{label}</a>'
        for href, label in nav_items
    )

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | Kenta Agent</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Noto Sans JP", sans-serif;
      background: #0d1117;
      color: #e6edf3;
      min-height: 100vh;
    }}
    header {{
      background: #161b22;
      border-bottom: 1px solid #30363d;
      padding: 16px 24px;
      position: sticky;
      top: 0;
      z-index: 100;
    }}
    .header-inner {{
      max-width: 800px;
      margin: 0 auto;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
    }}
    .logo {{ font-size: 18px; font-weight: 700; color: #58a6ff; }}
    nav a {{
      display: inline-block;
      padding: 6px 14px;
      border-radius: 20px;
      text-decoration: none;
      color: #8b949e;
      font-size: 13px;
      transition: all 0.2s;
      margin-left: 4px;
    }}
    nav a:hover {{ background: #21262d; color: #e6edf3; }}
    nav a.active {{ background: #1f6feb; color: #fff; }}
    main {{
      max-width: 800px;
      margin: 0 auto;
      padding: 24px 16px;
    }}
    .meta {{
      font-size: 12px;
      color: #8b949e;
      margin-bottom: 20px;
    }}
    .content {{
      background: #161b22;
      border: 1px solid #30363d;
      border-radius: 12px;
      padding: 24px;
      line-height: 1.8;
    }}
    h1 {{ font-size: 20px; color: #58a6ff; margin: 16px 0 8px; }}
    h2 {{ font-size: 16px; color: #79c0ff; margin: 16px 0 8px; border-left: 3px solid #1f6feb; padding-left: 10px; }}
    p {{ margin: 6px 0; font-size: 14px; color: #c9d1d9; }}
    hr {{ border: none; border-top: 1px solid #30363d; margin: 16px 0; }}
    ul {{ list-style: none; padding: 0; margin: 8px 0; }}
    li {{ padding: 4px 0 4px 16px; font-size: 14px; color: #c9d1d9; position: relative; }}
    li::before {{ content: "•"; position: absolute; left: 4px; color: #58a6ff; }}
    strong {{ color: #e6edf3; }}
    .empty {{
      text-align: center;
      padding: 60px 20px;
      color: #8b949e;
    }}
    .empty .icon {{ font-size: 48px; margin-bottom: 12px; }}
    @media (max-width: 600px) {{
      .header-inner {{ flex-direction: column; align-items: flex-start; }}
      nav {{ width: 100%; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="header-inner">
      <div class="logo">🏯 Kenta Agent</div>
      <nav>{nav_html}</nav>
    </div>
  </header>
  <main>
    <div class="meta">最終更新: {updated_jp}</div>
    <div class="content">
      {content_html}
    </div>
  </main>
</body>
</html>"""


def _get_page(report_type: str) -> HTMLResponse:
    titles = {
        "morning": "🌅 モーニングブリーフ",
        "evening": "🌆 夕方ニュース",
        "daily":   "📋 日報",
    }
    cache = get_report_cache(report_type)
    if not cache:
        html = _build_html(
            titles.get(report_type, "レポート"),
            "まだレポートがありません。\n\nTelegramで /morning を実行するとここに表示されます。",
            datetime.now().isoformat(),
            report_type,
        )
    else:
        html = _build_html(
            titles.get(report_type, "レポート"),
            cache["content"],
            cache["updated_at"],
            report_type,
        )
    return HTMLResponse(content=html)


@app.get("/health")
def health():
    return {"status": "ok", "service": "kenta-agent"}


@app.get("/", response_class=HTMLResponse)
def morning_report(username: str = Depends(verify_credentials)):
    return _get_page("morning")


@app.get("/evening", response_class=HTMLResponse)
def evening_report(username: str = Depends(verify_credentials)):
    return _get_page("evening")


@app.get("/report", response_class=HTMLResponse)
def daily_report(username: str = Depends(verify_credentials)):
    return _get_page("daily")
