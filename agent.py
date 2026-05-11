"""
ケンタエージェント - 3エージェント構成
========================================
AOI（秘書）/ SORA（分析）/ RIO（デザイン）
各エージェントの定義は agents/ ディレクトリのMarkdownファイルを参照
========================================
"""

import os
import anthropic
from tools import execute_tool

client = anthropic.Anthropic()

# ─────────────────────────────────────────
# エージェント定義をMarkdownから読み込む
# ─────────────────────────────────────────

def _load_agent_def(name: str) -> str:
    """
    agents/{name}.md を読み込み、COMPANY.md と LESSONS.md と結合して
    システムプロンプトとして返す。
    
    全エージェントが会社全体のルールと学習記録を共有する。
    """
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
# 共通プロフィール（全エージェントが共有）
# ─────────────────────────────────────────

KENTA_PROFILE = """
【けんたのプロフィール】
名前: けんたろう（健太郎）
職業: サーバー運用・監視、カスタマーサクセス（2026年4月より新職場）
家族: 配偶者（稚子）、子供2人（諒・かりん）の4人家族
居住: 関西（京阪電車沿線）
関心: 米国株式投資、テクノロジー、Vocaloid/ハイパーポップ、音楽

【投資ポートフォリオ】
保有: B,GM,UNFI,EAT,VYM,LITE,SYF,TWLO,EZPW,DY,PARR,NEM,BLBD,INCY,APP,CLS,NEXA,MU,CRDO,TIGO,KGC,GEV,CDE
監視: NVDA,MSFT,CEG,AMD
方針: 中期・中リスク。累積実現損失 約-¥350万からの回復を目指す
"""

# ─────────────────────────────────────────
# ツール定義（SORAが使用）
# ─────────────────────────────────────────

TOOLS = [
    {"name": "get_stock_price", "description": "1銘柄の株価・基本情報を取得", "input_schema": {"type": "object", "properties": {"ticker": {"type": "string"}}, "required": ["ticker"]}},
    {"name": "get_portfolio_prices", "description": "複数銘柄の株価を一括取得", "input_schema": {"type": "object", "properties": {"tickers": {"type": "array", "items": {"type": "string"}}}, "required": ["tickers"]}},
    {"name": "get_portfolio_pnl", "description": "ポートフォリオ全銘柄の損益計算（含み損益・前日比・円換算）", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_exchange_rate", "description": "為替レート取得", "input_schema": {"type": "object", "properties": {"from_currency": {"type": "string"}, "to_currency": {"type": "string"}}, "required": []}},
    {"name": "get_market_indices", "description": "主要指数（S&P500,NASDAQ,DOW,日経225）取得", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "web_search", "description": "ウェブ検索で最新情報収集", "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "fetch_url_content", "description": "指定URLのテキスト取得", "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
    {"name": "get_weather", "description": "指定都市の天気情報取得（city=Osaka, city=Kyoto など）", "input_schema": {"type": "object", "properties": {"city": {"type": "string", "default": "Osaka"}}, "required": []}},
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
# SORA（ソラ）- 分析エージェント
# 役割: データ収集・調査・分析の専門家
# ═══════════════════════════════════════════

def run_sora(task: str, conversation_history: list = None) -> str:
    """SORA: ツールを使ってデータ収集・分析を実行する"""
    if conversation_history is None:
        conversation_history = []

    sora_system = _load_agent_def("SORA")
    messages = list(conversation_history) + [{"role": "user", "content": task}]

    for _ in range(15):
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=sora_system,
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

    return "⚠️ SORA: 分析タイムアウト"


# ═══════════════════════════════════════════
# RIO（リオ）- デザインエージェント
# 役割: 出力整形・読みやすさの専門家
# ═══════════════════════════════════════════

def run_johnny(raw_data: str, original_request: str) -> str:
    """JOHNNY: SORAの生データをJony Ive哲学でTelegram向けに整形する"""
    johnny_system = _load_agent_def("JOHNNY")
    prompt = f"""以下のデータを、Telegram向けに整形してください。
Jony Iveの設計哲学に従い、本質的にシンプルで、
読み手への深い共感を持った出力にしてください。

【けんたの元のリクエスト】
{original_request}

【SORAが収集した生データ】
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
# AOI（アオイ）- 秘書エージェント（窓口）
# 役割: けんたとの窓口。SORA・RIOを統括する
# ═══════════════════════════════════════════

def run_agent(user_message: str, conversation_history: list = None) -> str:
    """
    AOI（秘書エージェント）- メインエントリーポイント
    agents/AOI.md の定義に従って動作する
    """
    if conversation_history is None:
        conversation_history = []

    aoi_system = _load_agent_def("AOI")

    aoi_prompt = f"""けんたから以下のリクエストが届きました。
SORAに渡す分析タスクを明確に定義してください。

【けんたのリクエスト】
{user_message}

【会話の文脈】
{_format_history(conversation_history)}

SORAへの指示:"""

    aoi_response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=aoi_system,
        messages=[{"role": "user", "content": aoi_prompt}],
    )
    sora_task = "\n".join(
        b.text for b in aoi_response.content if hasattr(b, "text")
    )

    raw_data = run_sora(sora_task, conversation_history)
    formatted = run_johnny(raw_data, user_message)
    return formatted


def _format_history(history: list) -> str:
    """会話履歴を文字列に変換"""
    if not history:
        return "（なし）"
    recent = history[-4:]  # 直近2往復
    lines = []
    for msg in recent:
        role = "けんた" if msg["role"] == "user" else "AOI"
        content = msg["content"] if isinstance(msg["content"], str) else "[データ]"
        lines.append(f"{role}: {content[:100]}")
    return "\n".join(lines)
