import anthropic
from tools import execute_tool

client = anthropic.Anthropic()

# ─────────────────────────────────────────
# 共通設定
# ─────────────────────────────────────────

KENTA_PROFILE = """
【けんたのプロフィール】
・職業：サーバー運用・監視、カスタマーサクセス（2026年4月より新職場）
・家族：配偶者（稚子）、子供2人（諒・かりん）の4人家族
・主要関心：米国株式投資、テクノロジー、Vocaloid/ハイパーポップ

【投資ポートフォリオ（楽天証券・US株）】
保有：B,GM,UNFI,EAT,VYM,LITE,SYF,TWLO,EZPW,DY,PARR,NEM,BLBD,INCY,APP,CLS,NEXA,MU,CRDO,TIGO,KGC,GEV,CDE
監視：NVDA,MSFT,CEG,AMD
"""

TOOLS = [
    {
        "name": "get_stock_price",
        "description": "1銘柄の株価・基本情報を取得",
        "input_schema": {"type": "object", "properties": {"ticker": {"type": "string"}}, "required": ["ticker"]},
    },
    {
        "name": "get_portfolio_prices",
        "description": "複数銘柄の株価を一括取得",
        "input_schema": {"type": "object", "properties": {"tickers": {"type": "array", "items": {"type": "string"}}}, "required": ["tickers"]},
    },
    {
        "name": "get_portfolio_pnl",
        "description": "ポートフォリオ全銘柄の損益計算。含み損益・前日比・円換算を一括計算",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_exchange_rate",
        "description": "為替レート取得（デフォルトUSD/JPY）",
        "input_schema": {"type": "object", "properties": {"from_currency": {"type": "string"}, "to_currency": {"type": "string"}}, "required": []},
    },
    {
        "name": "get_market_indices",
        "description": "主要指数（S&P500,NASDAQ,DOW,日経225）取得",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "web_search",
        "description": "ウェブ検索で最新情報収集",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "fetch_url_content",
        "description": "指定URLのテキスト取得",
        "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
    },
    {
        "name": "get_weather",
        "description": "指定都市の天気情報取得。city=Osaka で大阪、city=Kyoto で京都など",
        "input_schema": {"type": "object", "properties": {"city": {"type": "string", "default": "Tokyo"}}, "required": []},
    },
    {
        "name": "get_weather_kansai",
        "description": "大阪（関西）の天気情報を取得する",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_keihan_status",
        "description": "京阪電車の運行情報を取得する",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_fear_greed_index",
        "description": "CNNのFear & Greed Index（市場心理指数）を取得",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_hacker_news",
        "description": "Hacker Newsのトップ記事を取得",
        "input_schema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 5}}, "required": []},
    },
    {
        "name": "save_note",
        "description": "メモをDBに保存",
        "input_schema": {"type": "object", "properties": {"content": {"type": "string"}, "category": {"type": "string", "default": "general"}}, "required": ["content"]},
    },
    {
        "name": "get_notes",
        "description": "保存済みメモを取得",
        "input_schema": {"type": "object", "properties": {"category": {"type": "string"}, "limit": {"type": "integer", "default": 10}}, "required": []},
    },
    {
        "name": "add_task",
        "description": "タスクを追加",
        "input_schema": {"type": "object", "properties": {"title": {"type": "string"}, "due_date": {"type": "string"}}, "required": ["title"]},
    },
    {
        "name": "get_tasks",
        "description": "タスク一覧取得",
        "input_schema": {"type": "object", "properties": {"status": {"type": "string", "default": "pending"}}, "required": []},
    },
    {
        "name": "complete_task",
        "description": "タスクを完了にする",
        "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}}, "required": ["task_id"]},
    },
    {
        "name": "get_youtube_new_videos",
        "description": "登録YouTubeチャンネルの新着動画を取得",
        "input_schema": {"type": "object", "properties": {"hours": {"type": "integer", "default": 48}}, "required": []},
    },
    {
        "name": "get_calendar_events",
        "description": "Googleカレンダーから予定を取得",
        "input_schema": {"type": "object", "properties": {"days": {"type": "integer", "default": 3}}, "required": []},
    },
]


# ─────────────────────────────────────────
# 分析エージェント
# ツールを使ってデータ収集・分析を行い生データを返す
# ─────────────────────────────────────────

ANALYSIS_SYSTEM = f"""あなたは「分析エージェント」です。
けんたのパーソナルAIの分析部門として、ツールを使って情報収集・データ取得・分析を行います。

役割：
・ツールを積極的に使って必要な情報をすべて収集する
・収集した生データ・分析結果をそのまま出力する
・整形・装飾は行わない（次のデザインエージェントが担当）
・データは正確に、数字は省略せずに出力する

{KENTA_PROFILE}"""


def run_analysis_agent(user_message: str, conversation_history: list = None) -> str:
    """分析エージェント: ツールを使ってデータ収集・分析を実行"""
    if conversation_history is None:
        conversation_history = []

    messages = list(conversation_history) + [{"role": "user", "content": user_message}]

    for _ in range(15):  # ツールを多用するため多めに
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=ANALYSIS_SYSTEM,
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

    return "⚠️ 分析タイムアウト"


# ─────────────────────────────────────────
# デザインエージェント
# 分析結果を受け取りTelegram向けに美しく整形する
# ─────────────────────────────────────────

DESIGN_SYSTEM = f"""あなたは「デザインエージェント」です。
けんたのパーソナルAIのデザイン・編集部門として、分析エージェントが収集した生データを
Telegramで読みやすい形に整形・美化します。

役割：
・受け取った生データを読みやすく整理する
・適切な絵文字・見出し・区切り線を使う
・数字は必ず円（JPY）優先で表示（USDは補足）
・スマホ画面（幅が狭い）を意識したレイアウト
・長すぎず短すぎず、要点を絞る
・投資情報はポジティブ/ネガティブを明確に

ツールは使わない。整形・編集に専念する。

{KENTA_PROFILE}"""


def run_design_agent(analysis_result: str, original_request: str) -> str:
    """デザインエージェント: 分析結果をTelegram向けに整形"""
    prompt = f"""以下の分析結果を、Telegram向けに読みやすく整形してください。

【元のリクエスト】
{original_request}

【分析結果（生データ）】
{analysis_result}
"""
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=DESIGN_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return "\n".join(b.text for b in response.content if hasattr(b, "text"))


# ─────────────────────────────────────────
# 秘書エージェント（統括・外部インターフェース）
# ユーザーからの指示を受け取り分析→デザインを統括する
# ─────────────────────────────────────────

def run_agent(user_message: str, conversation_history: list = None) -> str:
    """
    秘書エージェント（メインエントリーポイント）
    1. 分析エージェントでデータ収集
    2. デザインエージェントで整形
    3. 最終結果を返す
    """
    if conversation_history is None:
        conversation_history = []

    # Step 1: 分析
    analysis_result = run_analysis_agent(user_message, conversation_history)

    # Step 2: デザイン整形
    formatted_result = run_design_agent(analysis_result, user_message)

    return formatted_result
