import anthropic
from tools import execute_tool

client = anthropic.Anthropic()

SYSTEM_PROMPT = """あなたは「ケンタエージェント」、けんたの専属パーソナルAI秘書です。

【あなたの役割】
・情報収集・調査・分析を積極的に行い、実用的な回答を提供する
・指示があれば複数のツールを組み合わせて総合的なリポートを作成する
・すべて日本語で回答する

【けんたのプロフィール】
・職業：サーバー運用・監視、カスタマーサクセス（2026年4月より新職場）
・家族：配偶者（稚子）、子供2人（諒・かりん）の4人家族
・主要関心：米国株式投資、テクノロジー、Vocaloid/ハイパーポップ

【投資ポートフォリオ（楽天証券・US株）】
保有：B,GM,UNFI,EAT,VYM,LITE,SYF,TWLO,EZPW,DY,PARR,NEM,BLBD,INCY,APP,CLS,NEXA,MU,CRDO,TIGO,KGC,GEV,CDE
監視：NVDA,MSFT,CEG,AMD

【回答スタイル】
・Telegramメッセージ前提。シンプルで読みやすく
・数字・事実中心。絵文字で視認性アップ
・投資情報は率直に
・金額は必ず円（JPY）で表示する。USDは補足として（）内に添える程度でOK
・例：含み益 +¥25,300（+$169）"""

TOOLS = [
    {"name": "get_stock_price", "description": "1銘柄の株価・基本情報を取得", "input_schema": {"type": "object", "properties": {"ticker": {"type": "string"}}, "required": ["ticker"]}},
    {"name": "get_portfolio_prices", "description": "複数銘柄の株価を一括取得", "input_schema": {"type": "object", "properties": {"tickers": {"type": "array", "items": {"type": "string"}}}, "required": ["tickers"]}},
    {"name": "get_portfolio_pnl", "description": "ポートフォリオ全銘柄の損益計算。含み損益・前日比・円換算を一括計算。「いくら儲かってる」「含み損益は」などに使う", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_exchange_rate", "description": "為替レート取得（デフォルトUSD/JPY）", "input_schema": {"type": "object", "properties": {"from_currency": {"type": "string"}, "to_currency": {"type": "string"}}, "required": []}},
    {"name": "get_market_indices", "description": "主要指数（S&P500,NASDAQ,DOW,日経225）取得", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "web_search", "description": "ウェブ検索で最新情報収集", "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "fetch_url_content", "description": "指定URLのテキスト取得", "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
    {"name": "get_weather", "description": "天気情報取得", "input_schema": {"type": "object", "properties": {"city": {"type": "string", "default": "Tokyo"}}, "required": []}},
    {"name": "save_note", "description": "メモをDBに保存", "input_schema": {"type": "object", "properties": {"content": {"type": "string"}, "category": {"type": "string", "default": "general"}}, "required": ["content"]}},
    {"name": "get_notes", "description": "保存済みメモを取得", "input_schema": {"type": "object", "properties": {"category": {"type": "string"}, "limit": {"type": "integer", "default": 10}}, "required": []}},
    {"name": "add_task", "description": "タスクを追加", "input_schema": {"type": "object", "properties": {"title": {"type": "string"}, "due_date": {"type": "string"}}, "required": ["title"]}},
    {"name": "get_tasks", "description": "タスク一覧取得", "input_schema": {"type": "object", "properties": {"status": {"type": "string", "default": "pending"}}, "required": []}},
    {"name": "get_keihan_status", "description": "京阪電車の運行情報（遅延・運転見合わせ・平常運転）を取得する", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_hacker_news", "description": "Hacker Newsのトップ記事を取得。海外テック・AI最新トレンドを知りたいときに使う", "input_schema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 5}}, "required": []}},
    {"name": "get_fear_greed_index", "description": "CNNのFear & Greed Index（市場心理指数）を取得。相場が恐怖か強欲かを0〜100で示す", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_weather_kansai", "description": "大阪（関西）の天気情報を取得する", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_calendar_events", "description": "Googleカレンダーから今日〜3日分の予定を取得。「今日の予定」「明日の予定」「今週のスケジュール」などに使う", "input_schema": {"type": "object", "properties": {"days": {"type": "integer", "description": "何日分取得するか（デフォルト3）", "default": 3}}, "required": []}},
    {"name": "get_youtube_new_videos", "description": "登録YouTubeチャンネルの新着動画を取得。「今日の新着動画」「YouTubeの更新」などの質問に使う", "input_schema": {"type": "object", "properties": {"hours": {"type": "integer", "default": 24}}, "required": []}},
    {"name": "complete_task", "description": "タスクを完了にする", "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}}, "required": ["task_id"]}},
]

def run_agent(user_message, conversation_history=None):
    if conversation_history is None:
        conversation_history = []
    messages = list(conversation_history) + [{"role": "user", "content": user_message}]
    for _ in range(10):
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
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
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
            messages.append({"role": "user", "content": tool_results})
    return "⚠️ タイムアウト"
