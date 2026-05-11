"""
Kenta Agent Company - 3エージェント構成
==========================================
坂本（秘書・窓口） / STEVE（分析） / JOHNNY（デザイン）
各エージェントの定義は agents/ のMarkdownファイルを参照
==========================================
"""

import os
import anthropic
from tools import execute_tool

client = anthropic.Anthropic()


# ─────────────────────────────────────────
# Markdownからエージェント定義を読み込む
# COMPANY.md + LESSONS.md + {NAME}.md を結合
# ─────────────────────────────────────────

def _load_agent_def(name: str) -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    agents_dir = os.path.join(base_dir, "agents")

    def read_md(filename: str) -> str:
        try:
            with open(os.path.join(agents_dir, filename), "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    company = read_md("COMPANY.md")
    lessons = read_md("LESSONS.md")
    agent_def = read_md(f"{name}.md")

    parts = []
    if company:
        parts.append(f"# 会社全体のルール\n{company}")
    if lessons:
        parts.append(f"# 学習記録（過去のミスと対策）\n{lessons}")
    if agent_def:
        parts.append(f"# あなたの職務定義\n{agent_def}")

    return "\n\n---\n\n".join(parts) if parts else f"あなたは{name}エージェントです。"


# ─────────────────────────────────────────
# ツール定義（STEVEが使用）
# ─────────────────────────────────────────

TOOLS = [
    {"name": "get_stock_price", "description": "1銘柄の株価・基本情報を取得", "input_schema": {"type": "object", "properties": {"ticker": {"type": "string"}}, "required": ["ticker"]}},
    {"name": "get_portfolio_prices", "description": "複数銘柄の株価を一括取得", "input_schema": {"type": "object", "properties": {"tickers": {"type": "array", "items": {"type": "string"}}}, "required": ["tickers"]}},
    {"name": "get_portfolio_pnl", "description": "ポートフォリオ全銘柄の損益計算（含み損益・前日比・円換算）", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_exchange_rate", "description": "為替レート取得", "input_schema": {"type": "object", "properties": {"from_currency": {"type": "string"}, "to_currency": {"type": "string"}}, "required": []}},
    {"name": "get_market_indices", "description": "主要指数（S&P500,NASDAQ,DOW,日経225）取得", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "web_search", "description": "ウェブ検索で最新情報収集", "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "fetch_url_content", "description": "指定URLのテキスト取得", "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
    {"name": "get_weather", "description": "指定都市の天気（city=Osaka, city=Kyoto など）", "input_schema": {"type": "object", "properties": {"city": {"type": "string", "default": "Osaka"}}, "required": []}},
    {"name": "get_weather_kansai", "description": "大阪（関西）の天気情報を取得", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_keihan_status", "description": "京阪電車の運行情報を取得", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_fear_greed_index", "description": "CNNのFear & Greed Index（市場心理指数）を取得", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_hacker_news", "description": "Hacker Newsのトップ記事を取得", "input_schema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 5}}, "required": []}},
    {"name": "save_note", "description": "メモをDBに保存", "input_schema": {"type": "object", "properties": {"content": {"type": "string"}, "category": {"type": "string", "default": "general"}}, "required": ["content"]}},
    {"name": "get_notes", "description": "保存済みメモを取得", "input_schema": {"type": "object", "properties": {"category": {"type": "string"}, "limit": {"type": "integer", "default": 10}}, "required": []}},
    {"name": "add_task", "description": "タスクを追加", "input_schema": {"type": "object", "properties": {"title": {"type": "string"}, "due_date": {"type": "string"}}, "required": ["title"]}},
    {"name": "get_tasks", "description": "タスク一覧取得", "input_schema": {"type": "object", "properties": {"status": {"type": "string", "default": "pending"}}, "required": []}},
    {"name": "complete_task", "description": "タスクを完了にする", "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}}, "required": ["task_id"]}},
    {"name": "get_youtube_new_videos", "description": "登録YouTubeチャンネルの新着動画を取得", "input_schema": {"type": "object", "properties": {"hours": {"type": "integer", "default": 48}}, "required": []}},
    {"name": "get_calendar_events", "description": "Googleカレンダーから予定を取得", "input_schema": {"type": "object", "properties": {"days": {"type": "integer", "default": 3}}, "required": []}},
]


# ═══════════════════════════════════════════
# STEVE - 分析エージェント
# Steve Jobs哲学でデータ収集・分析を行う
# ═══════════════════════════════════════════

def run_steve(task: str, conversation_history: list = None) -> str:
    """STEVE: ツールを使ってデータ収集・分析を実行する"""
    if conversation_history is None:
        conversation_history = []

    steve_system = _load_agent_def("STEVE")
    messages = list(conversation_history) + [{"role": "user", "content": task}]

    for _ in range(15):
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=steve_system,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            return "\n".join(b.text for b in response.content if hasattr(b, "text"))

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "user", "content": tool_results})

    return "⚠️ STEVE: 分析タイムアウト"


# ═══════════════════════════════════════════
# JOHNNY - デザインエージェント
# Jony Ive哲学で出力を整形する
# ═══════════════════════════════════════════

def run_johnny(raw_data: str, original_request: str) -> str:
    """JOHNNY: STEVEの生データをJony Ive哲学でTelegram向けに整形する"""
    johnny_system = _load_agent_def("JOHNNY")
    prompt = f"""以下のデータを、Telegram向けに整形してください。
Jony Iveの設計哲学に従い、本質的にシンプルで、
読み手への深い共感を持った出力にしてください。

【けんたの元のリクエスト】
{original_request}

【STEVEが収集した生データ】
{raw_data}
"""
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=johnny_system,
        messages=[{"role": "user", "content": prompt}],
    )
    return "\n".join(b.text for b in response.content if hasattr(b, "text"))


# ═══════════════════════════════════════════
# 坂本 - 秘書エージェント（唯一の窓口）
# 坂本龍馬哲学・高知弁でけんたと話す
# すべての返答は坂本を通す
# ═══════════════════════════════════════════

def run_agent(user_message: str, conversation_history: list = None) -> str:
    """
    坂本（秘書エージェント）- メインエントリーポイント

    フロー:
    1. 坂本がけんたのリクエストを受け取り、STEVEへのタスクを定義
    2. STEVEがデータ収集・分析を実行
    3. JOHNNYが結果を整形
    4. 坂本が最終返答をけんたに届ける
    """
    if conversation_history is None:
        conversation_history = []

    sakamoto_system = _load_agent_def("SAKAMOTO")

    # Step 1: 坂本がSTEVEへの指示を定義
    step1_prompt = f"""けんたから以下のリクエストが届きました。

【けんたのリクエスト】
{user_message}

【会話の文脈】
{_format_history(conversation_history)}

STEVEに渡す分析タスクを明確に定義してください。
何を・どこまで調べるべきか、具体的に指示してください。
（この指示はSTEVEへの内部指示です。けんたへの返答はまだしません）"""

    step1_response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=sakamoto_system,
        messages=[{"role": "user", "content": step1_prompt}],
    )
    steve_task = "\n".join(
        b.text for b in step1_response.content if hasattr(b, "text")
    )

    # Step 2: STEVEが分析実行
    raw_data = run_steve(steve_task, conversation_history)

    # Step 3: JOHNNYが整形
    formatted_data = run_johnny(raw_data, user_message)

    # Step 4: 坂本がけんたへの最終返答を生成（高知弁で）
    step4_prompt = f"""けんたへの返答を作成してください。

【けんたのリクエスト】
{user_message}

【STEVEとJOHNNYが作成したレポート】
{formatted_data}

このレポートをそのままけんたに渡してください。
冒頭に坂本らしい一言（高知弁で、短く、前向きに）を添えてください。
例：「ほんまに、ええ動きしちゅうぜよ！」「任せちょきや、調べてきたき！」
レポートは改変せず、そのまま出力してください。"""

    step4_response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=sakamoto_system,
        messages=[{"role": "user", "content": step4_prompt}],
    )
    return "\n".join(
        b.text for b in step4_response.content if hasattr(b, "text")
    )


def _format_history(history: list) -> str:
    if not history:
        return "（なし）"
    recent = history[-4:]
    lines = []
    for msg in recent:
        role = "けんた" if msg["role"] == "user" else "坂本"
        content = msg["content"] if isinstance(msg["content"], str) else "[データ]"
        lines.append(f"{role}: {content[:100]}")
    return "\n".join(lines)
