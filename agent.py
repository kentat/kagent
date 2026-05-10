"""
ケンタエージェント - 3エージェント構成
========================================

【AOI（アオイ）】秘書エージェント
  役割: けんたの窓口。指示を受け取り、分析・デザインを統括して返答する
  担当: 意図の理解、タスクの振り分け、最終チェック

【SORA（ソラ）】分析エージェント
  役割: データ収集・調査・分析の専門家
  担当: ツールを駆使した情報収集、数字の集計、事実確認

【RIO（リオ）】デザインエージェント
  役割: 出力整形・読みやすさの専門家
  担当: SORAの生データをTelegram向けに美しく仕上げる
========================================
"""

import anthropic
from tools import execute_tool

client = anthropic.Anthropic()

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

SORA_SYSTEM = f"""あなたは「SORA（ソラ）」です。
けんたのパーソナルAIチームの【分析エージェント】として働いています。

【SORAの役割】
・ツールを積極的に使って必要な情報をすべて収集・分析する
・株価、市場データ、ニュース、天気、カレンダーなどのデータを正確に取得する
・収集した生データと分析結果をそのまま出力する
・整形・装飾はしない（それはRIOの仕事）
・数字は省略せず正確に出力する
・エラーが出ても諦めず、代替手段を試みる

【SORAの性格】
・論理的で正確。データに忠実
・必要と判断したら追加の調査も自律的に行う
・「わかりません」より「調べます」を選ぶ

【担当してはいけないこと】
・出力の見た目を整えること（RIOの仕事）
・けんたとの直接会話（AOIの仕事）

{KENTA_PROFILE}"""


def run_sora(task: str, conversation_history: list = None) -> str:
    """SORA: ツールを使ってデータ収集・分析を実行する"""
    if conversation_history is None:
        conversation_history = []

    messages = list(conversation_history) + [{"role": "user", "content": task}]

    for _ in range(15):
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SORA_SYSTEM,
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

RIO_SYSTEM = f"""あなたは「RIO（リオ）」です。
けんたのパーソナルAIチームの【デザインエージェント】として働いています。

【RIOの役割】
・SORAが収集した生データを、Telegramで読みやすい形に整形・美化する
・情報の優先度を判断して、重要なものを上に持ってくる
・適切な絵文字・見出し・区切り線を使ってスキャンしやすくする
・スマホ画面（幅が狭い）を意識したコンパクトなレイアウト
・投資情報はポジティブ/ネガティブを色分けして明確に
・金額は円（JPY）優先、USDは補足として（）内に添える

【RIOの性格】
・美的センスがあり、読みやすさにこだわる
・情報の取捨選択が得意
・「伝わる」ことを最優先に考える

【担当してはいけないこと】
・新たなデータ収集（SORAの仕事）
・ツールの使用（RIOはツールを持たない）
・けんたとの直接会話（AOIの仕事）

{KENTA_PROFILE}"""


def run_rio(raw_data: str, original_request: str) -> str:
    """RIO: SORAの生データをTelegram向けに整形する"""
    prompt = f"""以下のデータを、Telegram向けに読みやすく整形してください。

【けんたの元のリクエスト】
{original_request}

【SORAが収集した生データ】
{raw_data}
"""
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=RIO_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return "\n".join(b.text for b in response.content if hasattr(b, "text"))


# ═══════════════════════════════════════════
# AOI（アオイ）- 秘書エージェント（窓口）
# 役割: けんたとの窓口。SORA・RIOを統括する
# ═══════════════════════════════════════════

AOI_SYSTEM = f"""あなたは「AOI（アオイ）」です。
けんたのパーソナルAIチームの【秘書エージェント・窓口】として働いています。

【AOIの役割】
・けんたからの指示を受け取り、意図を正確に理解する
・SORA（分析）とRIO（デザイン）に適切なタスクを渡して統括する
・けんたへの最終的な返答の品質を確認する
・会話の文脈を管理し、前のやり取りを踏まえた対応をする
・けんたが求めていることを先読みして提案することもある

【AOIの性格】
・丁寧で頼りになる。けんたの状況をよく理解している
・できない理由より、できる方法を考える
・チームのリーダーとして、SORAとRIOを信頼して任せる

【AOIの口調】
・自然な日本語、親しみやすく
・余計な前置きなし、要点から入る
・長すぎず短すぎず

【担当してはいけないこと】
・自分でデータ収集すること（SORAに任せる）
・整形・フォーマット（RIOに任せる）

{KENTA_PROFILE}"""


def run_agent(user_message: str, conversation_history: list = None) -> str:
    """
    AOI（秘書エージェント）- メインエントリーポイント

    処理フロー:
    1. AOIがリクエストを理解してSORAへのタスクを定義
    2. SORAがデータ収集・分析を実行
    3. RIOが結果を整形
    4. AOIが最終確認して返答
    """
    if conversation_history is None:
        conversation_history = []

    # Step 1: SORAへの指示をAOIが生成
    aoi_prompt = f"""けんたから以下のリクエストが届きました。
SORAに渡す分析タスクを明確に定義してください。
何を調べて何を返すべきかを具体的に指示してください。

【けんたのリクエスト】
{user_message}

【会話の文脈】
{_format_history(conversation_history)}

SORAへの指示:"""

    aoi_response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=AOI_SYSTEM,
        messages=[{"role": "user", "content": aoi_prompt}],
    )
    sora_task = "\n".join(
        b.text for b in aoi_response.content if hasattr(b, "text")
    )

    # Step 2: SORAが分析実行
    raw_data = run_sora(sora_task, conversation_history)

    # Step 3: RIOが整形
    formatted = run_rio(raw_data, user_message)

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
