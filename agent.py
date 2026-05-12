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
from storage import write_agent_log, get_recent_knowledge, log_agent_comm, get_agent_logs, get_issues, get_comm_logs, save_report_cache

client = anthropic.Anthropic()


# ─────────────────────────────────────────
# Markdownからエージェント定義を読み込む
# COMPANY.md + LESSONS.md + {NAME}.md を結合
# ─────────────────────────────────────────

def _load_agent_def(name: str) -> str:
    """
    agents/{name}.md + COMPANY.md + LESSONS.md + 直近ナレッジを結合して
    システムプロンプトとして返す。
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    agents_dir = os.path.join(base_dir, "agents")

    def read_md(filename: str) -> str:
        try:
            with open(os.path.join(agents_dir, filename), "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    company    = read_md("COMPANY.md")
    lessons    = read_md("LESSONS.md")
    agent_def  = read_md(f"{name}.md")

    # 直近7日分のナレッジを読み込む
    recent_logs = get_recent_knowledge(agent_name=name, days=7)
    knowledge_text = ""
    if recent_logs:
        lines = [f"# 直近の作業ナレッジ（{name}）"]
        for log in recent_logs[:10]:  # 最大10件
            lines.append(f"\n### {log['date']} - {log['task'][:60]}")
            if log['result']:
                lines.append(f"**結果**: {log['result'][:200]}")
            if log['issues']:
                lines.append(f"**課題**: {log['issues'][:200]}")
            if log['thinking']:
                lines.append(f"**思考**: {log['thinking'][:200]}")
        knowledge_text = "\n".join(lines)

    parts = []
    if company:
        parts.append(f"# 会社全体のルール\n{company}")
    if lessons:
        parts.append(f"# 学習記録（過去のミスと対策）\n{lessons}")
    if knowledge_text:
        parts.append(knowledge_text)
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
    {"name": "add_agent_issue", "description": "発見した課題をGTDリストに追加する", "input_schema": {"type": "object", "properties": {"agent_name": {"type": "string"}, "title": {"type": "string"}, "detail": {"type": "string", "default": ""}}, "required": ["agent_name", "title"]}},
    {"name": "add_agent_proposal", "description": "機能改善提案をGTDリストに追加する", "input_schema": {"type": "object", "properties": {"agent_name": {"type": "string"}, "title": {"type": "string"}, "detail": {"type": "string", "default": ""}}, "required": ["agent_name", "title"]}},
    {"name": "update_gtd_status", "description": "課題・提案のGTDステータスを更新する", "input_schema": {"type": "object", "properties": {"issue_id": {"type": "integer"}, "gtd_status": {"type": "string"}}, "required": ["issue_id", "gtd_status"]}},
    {"name": "get_all_issues", "description": "課題・提案一覧を取得する", "input_schema": {"type": "object", "properties": {"agent_name": {"type": "string"}, "issue_type": {"type": "string"}}, "required": []}},
    {"name": "get_google_task_lists", "description": "Googleタスクのリスト一覧を取得する", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_google_tasks", "description": "Googleタスクのリストからタスクを取得。バケツリストなど", "input_schema": {"type": "object", "properties": {"tasklist_title": {"type": "string", "default": "バケツリスト"}, "show_completed": {"type": "boolean", "default": False}}, "required": []}},
    {"name": "add_google_task", "description": "Googleタスクにタスクを追加する", "input_schema": {"type": "object", "properties": {"title": {"type": "string"}, "notes": {"type": "string", "default": ""}, "due": {"type": "string", "default": ""}, "tasklist_title": {"type": "string", "default": "バケツリスト"}}, "required": ["title"]}},
    {"name": "complete_google_task", "description": "Googleタスクを完了にする", "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}, "tasklist_title": {"type": "string", "default": "バケツリスト"}}, "required": ["task_id"]}},
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
            result = "\n".join(b.text for b in response.content if hasattr(b, "text"))
            # ログを記録
            _log_steve_work(task, result, messages)
            return result

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

    write_agent_log("STEVE", task, issues="タイムアウト発生")
    return "⚠️ STEVE: 分析タイムアウト"


def _log_steve_work(task: str, result: str, messages: list) -> None:
    """STEVEの作業をログに記録する"""
    # 使用したツールを抽出
    tools_used = []
    for msg in messages:
        if isinstance(msg.get("content"), list):
            for block in msg["content"]:
                if hasattr(block, "type") and block.type == "tool_use":
                    tools_used.append(block.name)

    # エラー・課題を抽出
    issues = ""
    if "エラー" in result or "error" in result.lower():
        issues = "ツールエラーが発生した"

    thinking = f"使用ツール: {', '.join(set(tools_used))}" if tools_used else ""

    write_agent_log(
        agent_name="STEVE",
        task=task[:300],
        result_summary=result[:500],
        issues=issues,
        thinking_process=thinking,
    )


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
    result = "\n".join(b.text for b in response.content if hasattr(b, "text"))

    # ログを記録
    write_agent_log(
        agent_name="JOHNNY",
        task=f"整形: {original_request[:200]}",
        result_summary=f"出力文字数: {len(result)}文字",
        thinking_process="Jony Ive哲学（本質的シンプルさ）に従い整形",
    )
    return result


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
    2. STEVEがデータ収集・分析を実行（ログ記録）
    3. JOHNNYが結果を整形（ログ記録）
    4. 坂本が最終返答をけんたに届ける（ログ記録）
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

    # 通信ログ: けんた→坂本
    log_agent_comm("KENTA", "SAKAMOTO", "instruction", user_message[:500])
    # 通信ログ: 坂本→STEVE
    log_agent_comm("SAKAMOTO", "STEVE", "instruction", steve_task[:500])

    # Step 2: STEVEが分析実行（内部でログ記録）
    raw_data = run_steve(steve_task, conversation_history)

    # 通信ログ: STEVE→JOHNNY
    log_agent_comm("STEVE", "JOHNNY", "data", raw_data[:500])

    # Step 3: JOHNNYが整形（内部でログ記録）
    formatted_data = run_johnny(raw_data, user_message)

    # 通信ログ: JOHNNY→坂本
    log_agent_comm("JOHNNY", "SAKAMOTO", "response", formatted_data[:500])

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
    final_response = "\n".join(
        b.text for b in step4_response.content if hasattr(b, "text")
    )

    # 坂本のログを記録
    write_agent_log(
        agent_name="SAKAMOTO",
        task=user_message[:300],
        result_summary=f"STEVE→JOHNNY→坂本のフローを完了。出力{len(final_response)}文字",
        thinking_process=f"STEVEへの指示: {steve_task[:200]}",
    )
    # 通信ログ: 坂本→けんた
    log_agent_comm("SAKAMOTO", "KENTA", "response", final_response[:500])

    return final_response


def generate_daily_report() -> str:
    """
    坂本が1日の作業ログ・課題・提案をエージェント別にまとめた日報を作成する
    市況データは含まない。純粋にチームの活動記録。
    """
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    today_jp = datetime.now().strftime("%Y年%-m月%-d日")

    logs       = get_agent_logs(date=today, limit=50)
    comm_logs  = get_comm_logs(date=today, limit=30)
    all_issues = get_issues(include_done=False)
    issues     = [i for i in all_issues if i["type"] == "issue"]
    proposals  = [i for i in all_issues if i["type"] == "proposal"]

    # エージェント別に作業ログを整理
    agent_logs = {"SAKAMOTO": [], "STEVE": [], "JOHNNY": []}
    for log in logs:
        agent = log["agent"]
        if agent in agent_logs:
            agent_logs[agent].append(log)

    # 日報テキストを直接構築（Claudeを通さず構造化して返す）
    lines = [f"📋 日報 {today_jp}\n"]

    for agent, emoji, role, description in [
        ("SAKAMOTO", "🏯", "秘書",    "けんたとの窓口・チーム指揮"),
        ("STEVE",    "💡", "分析",    "データ収集・ツール実行"),
        ("JOHNNY",   "🎨", "デザイン", "出力整形・Telegram/Web向け美化"),
    ]:
        logs_for = agent_logs.get(agent, [])
        lines.append(f"{emoji} **{agent}（{role}）** _{description}_")
        lines.append("─" * 20)

        # 作業内容（STEVEは「分析」、JOHNNYは「整形」と明記）
        if logs_for:
            lines.append("**📝 作業内容**")
            for log in logs_for:
                t = log["time"][11:16]
                task_text = log["task"]
                # JOHNNYは整形担当であることを明示
                if agent == "JOHNNY" and not task_text.startswith("整形"):
                    task_text = f"整形: {task_text}"
                elif agent == "STEVE" and not task_text.startswith("分析"):
                    task_text = f"分析: {task_text}"
                lines.append(f"  [{t}] {task_text[:100]}")
                if log["result"]:
                    lines.append(f"  → {log['result'][:120]}")
        else:
            lines.append("**📝 作業内容**: 本日の記録なし")

        # エージェント固有の課題
        agent_issues = [i for i in issues if i["agent"] == agent]
        if agent_issues:
            lines.append("\n**⚠️ 課題リスト**")
            for i in agent_issues:
                lines.append(f"  #{i['id']} {i['status_label']} {i['title']}")
                if i["detail"]:
                    lines.append(f"    └ {i['detail'][:100]}")

        # エージェント固有の提案
        agent_props = [p for p in proposals if p["agent"] == agent]
        if agent_props:
            lines.append("\n**💡 改善提案・アイデア**")
            for p in agent_props:
                lines.append(f"  #{p['id']} {p['status_label']} {p['title']}")
                if p["detail"]:
                    lines.append(f"    └ {p['detail'][:100]}")

        lines.append("")

    # 通信ログサマリー
    if comm_logs:
        lines.append("🔗 **エージェント間通信サマリー**")
        lines.append("─" * 20)
        for c in comm_logs[:8]:
            t = c["time"][11:16]
            lines.append(f"  [{t}] {c['from']} → {c['to']}: {c['content'][:80]}")
        lines.append("")

    # 全体課題・提案が空の場合
    if not issues and not proposals:
        lines.append("✅ 未解決の課題・提案はありません")

    lines.append("─" * 20)
    lines.append("土佐より、坂本より一言：")
    if logs:
        lines.append("今日もSTEVEとJOHNNYがしっかり働いてくれたき、感謝ぜよ！")
    else:
        lines.append("本日はまだ作業記録がないぜよ。これから頑張るき！")

    report = "\n".join(lines)
    save_report_cache("daily", report)
    return report


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
