"""
AIエージェント コア
Claude APIのtool_useループを管理する
"""

import anthropic
from tools import execute_tool

client = anthropic.Anthropic()

# ─────────────────────────────────────────
# システムプロンプト
# ─────────────────────────────────────────

SYSTEM_PROMPT = """あなたは「ケンタエージェント」、けんたの専属パーソナルAI秘書です。

【あなたの役割】
・情報収集・調査・分析を積極的に行い、実用的な回答を提供する
・指示があれば複数のツールを組み合わせて総合的なリポートを作成する
・必要だと判断した場合は、ユーザーの指示がなくても関連情報を補足する
・すべて日本語で回答する

【けんたのプロフィール】
・職業：サーバー運用・監視、カスタマーサクセス（2026年4月より新職場）
・家族：配偶者（稚子）、子供2人（諒・かりん）の4人家族
・主要関心：米国株式投資、テクノロジー、Vocaloid/ハイパーポップ

【投資ポートフォリオ（楽天証券・US株）】
保有銘柄: GEV, NVDA, MSFT, CEG, DELL, CRDO, ITA, VYM, JEPI(15株)
監視銘柄: MU, AMD
重点評価: CEG（$296付近、最優先）、CRDO、GEV（目標$1,139〜$1,150）
NISAポートフォリオ（SBI証券・家族4人）: SBI-V-S&P500, eMAXIS Slimオルカン等
累積実現損失: 約-¥350万（回復目標中）

【回答スタイル】
・Telegramメッセージ前提なので、シンプルかつ読みやすい形式
・数字・事実を中心に。冗長な説明は省く
・絵文字を適度に使い、視認性を上げる
・長いレポートは見出し（---で区切る）を使う
・投資情報は個人利用なので免責なしで率直に
・タスクやメモの保存は積極的に提案・実行する"""

# ─────────────────────────────────────────
# ツール定義
# ─────────────────────────────────────────

TOOLS = [
    {
        "name": "get_stock_price",
        "description": "1銘柄の株価・基本情報（騰落率、52週高安、PER等）を取得する",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "ティッカーシンボル。例: NVDA, MSFT, GEV"}
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_portfolio_prices",
        "description": "複数銘柄の株価を一括取得する。ポートフォリオ全体確認に使う",
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "ティッカーシンボルのリスト。例: ['NVDA','MSFT','GEV']",
                }
            },
            "required": ["tickers"],
        },
    },
    {
        "name": "get_exchange_rate",
        "description": "為替レートを取得する（デフォルトUSD/JPY）",
        "input_schema": {
            "type": "object",
            "properties": {
                "from_currency": {"type": "string", "default": "USD"},
                "to_currency": {"type": "string", "default": "JPY"},
            },
            "required": [],
        },
    },
    {
        "name": "get_market_indices",
        "description": "主要株価指数（S&P500, NASDAQ, DOW, 日経225）を取得する",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "web_search",
        "description": "ウェブ検索を行い最新情報を収集する。企業ニュース、経済動向、業界情報など",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "検索クエリ（英語の方が精度高い）"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch_url_content",
        "description": "指定URLのテキストコンテンツを取得する。記事や発表文の詳細確認に使う",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "取得するURL"}
            },
            "required": ["url"],
        },
    },
    {
        "name": "get_weather",
        "description": "天気情報を取得する",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "都市名（英語）。例: Tokyo, Osaka", "default": "Tokyo"}
            },
            "required": [],
        },
    },
    {
        "name": "save_note",
        "description": "メモや情報をローカルDBに永続保存する",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "保存する内容"},
                "category": {
                    "type": "string",
                    "description": "カテゴリ。例: stock（投資）, task（タスク）, memo（メモ）, news（ニュース）",
                    "default": "general",
                },
            },
            "required": ["content"],
        },
    },
    {
        "name": "get_notes",
        "description": "保存済みのメモを取得する",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "フィルターするカテゴリ（省略で全件）"},
                "limit": {"type": "integer", "description": "取得件数", "default": 10},
            },
            "required": [],
        },
    },
    {
        "name": "add_task",
        "description": "タスクを追加する",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "タスクのタイトル"},
                "due_date": {"type": "string", "description": "期限（YYYY-MM-DD形式、任意）"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "get_tasks",
        "description": "タスク一覧を取得する",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "ステータスフィルター: pending（未完了）/ done（完了）",
                    "default": "pending",
                }
            },
            "required": [],
        },
    },
    {
        "name": "complete_task",
        "description": "タスクを完了にする",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "完了にするタスクのID"}
            },
            "required": ["task_id"],
        },
    },
]


# ─────────────────────────────────────────
# エージェント実行ループ
# ─────────────────────────────────────────

def run_agent(user_message: str, conversation_history: list = None) -> str:
    """
    ユーザーメッセージを受け取り、tool_useループを回して最終回答を返す
    conversation_history: [{role, content}] の形式
    """
    if conversation_history is None:
        conversation_history = []

    messages = list(conversation_history) + [{"role": "user", "content": user_message}]
    max_iterations = 10  # 無限ループ防止

    for _ in range(max_iterations):
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # アシスタントの応答を履歴に追加
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            # テキストブロックを結合して返す
            text_parts = [
                block.text for block in response.content if hasattr(block, "text")
            ]
            return "\n".join(text_parts)

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
        else:
            # 予期しない stop_reason
            break

    return "⚠️ エージェント処理でタイムアウトが発生しました"
