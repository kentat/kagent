"""
スケジューラー - 定期実行タスク（JST）
朝6時：市況レポート / 朝7時：日報 / 夕18時：ニュースレポート（平日）
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from agent import run_agent, generate_daily_report
from output import deliver, OutputChannel
from storage import save_report_cache

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="Asia/Tokyo")


# ─────────────────────────────────────────
# レポートプロンプト
# ─────────────────────────────────────────

def _morning_report_prompt() -> str:
    return """【朝の市況レポート】以下のステップを順番にすべて実行してください。

=== STEP 1: 指数・為替 ===
get_market_indices で主要指数を取得
get_exchange_rate でUSD/JPYを取得

=== STEP 2: ポートフォリオ ===
get_portfolio_pnl で全銘柄の損益を取得

=== STEP 3: 天気・交通 ===
get_weather city=Osaka で大阪の天気を取得
get_weather city=Kyoto で京都の天気を取得
get_keihan_status で京阪電車の運行情報を取得

=== STEP 4: 市場心理 ===
get_fear_greed_index でFear & Greed Indexを取得

=== STEP 5: Google Tasks（優先TODO） ===
get_google_tasks tasklist_title=Inbox で受信箱タスクを取得
get_google_tasks tasklist_title=定期 で定期タスクを取得
→ 期限が近いもの・重要そうなものを最大5件ピックアップして表示

=== STEP 6: Google Calendar ===
get_calendar_events で今日〜3日分の予定を取得
日付は「5/14（水）13:30〜」のように具体的な日付と曜日で表示。「明日」などの相対表現禁止

=== STEP 7: YouTube新着 ===
get_youtube_new_videos hours=48 で新着動画を取得
動画がない場合は「📭 過去48時間の新着動画はありませんでした」と表示

=== 出力フォーマット ===
🌅 朝のレポート [日付]
---
📈 市況サマリー（指数・為替）
---
😱 市場心理: [スコア]/100（[状態]）
---
💰 ポートフォリオ（損益・上昇トップ3・下落ワースト3）
---
🌤 天気
大阪：（天気・最高/最低気温）
京都：（天気・最高/最低気温）
🚃 京阪電車：（運行状況）
---
✅ 今日のTODO（Googleタスクから期限・重要度でピックアップ最大5件）
---
📅 今日の予定（カレンダー3日分、なければ「なし」）
---
📺 YouTube新着（なければ「📭 過去48時間の新着動画はありませんでした」）"""


def _evening_report_prompt() -> str:
    return """【夕方ニュースレポート】以下を順番に実行してください。

=== STEP 1: 市場心理 ===
get_fear_greed_index で Fear & Greed Index を取得

=== STEP 2: 米国株ニュース ===
web_search「US stock market news today」で検索
web_search「S&P500 NASDAQ market today」で検索

=== STEP 3: AI・テクノロジーニュース ===
web_search「AI artificial intelligence news today 2026」で検索
web_search「AI business use case productivity 2026」で検索

=== STEP 4: Hacker News ===
get_hacker_news でトップ5記事を取得

=== 出力フォーマット ===
🌆 夕方ニュース [日付]
---
😱 市場心理: [スコア]/100（[状態]）
---
📈 米国株・市場（3〜5件・URL付き）
• タイトル
  要約（2〜3行）
  🔗 URL
---
🤖 AI・テクノロジー（3〜5件・URL付き）
• タイトル
  要約（2〜3行）
  🔗 URL
---
💻 Hacker News
• タイトル（スコア pt）
  🔗 URL

URLは必ず実際のリンクを記載すること。"""


# ─────────────────────────────────────────
# 実行関数
# ─────────────────────────────────────────

async def send_morning_report(bot, chat_id: int):
    """平日 朝6時 - 市況レポート"""
    try:
        logger.info("朝レポート生成開始")
        await bot.send_message(chat_id=chat_id, text="📊 朝の市況レポートを作成中...")
        report = run_agent(_morning_report_prompt())
        save_report_cache("morning", report)
        await deliver(bot, chat_id, report, OutputChannel.TELEGRAM)
        logger.info("朝レポート送信完了")
    except Exception as e:
        logger.error(f"朝レポートエラー: {e}")
        await bot.send_message(chat_id=chat_id, text=f"⚠️ レポート生成エラー: {str(e)}")


async def send_daily_report(bot, chat_id: int):
    """平日 朝7時 - 日報（課題・提案・進捗）"""
    try:
        logger.info("日報生成開始")
        report = generate_daily_report()
        save_report_cache("daily", report)
        await deliver(bot, chat_id, report, OutputChannel.TELEGRAM)
        logger.info("日報送信完了")
    except Exception as e:
        logger.error(f"日報エラー: {e}")


async def send_evening_report(bot, chat_id: int):
    """平日 夕18時 - ニュースレポート"""
    try:
        logger.info("夕方レポート生成開始")
        report = run_agent(_evening_report_prompt())
        save_report_cache("evening", report)
        await deliver(bot, chat_id, report, OutputChannel.TELEGRAM)
        logger.info("夕方レポート送信完了")
    except Exception as e:
        logger.error(f"夕方レポートエラー: {e}")


# ─────────────────────────────────────────
# セットアップ
# ─────────────────────────────────────────

def setup_scheduler(bot, chat_id: int):
    """定期タスクを登録して起動（すべてJST）"""
    # 平日 朝6時 - 市況レポート
    scheduler.add_job(
        send_morning_report,
        CronTrigger(hour=6, minute=0, day_of_week="mon-fri", timezone="Asia/Tokyo"),
        args=[bot, chat_id], id="morning_report", replace_existing=True,
    )
    # 平日 朝7時 - 日報
    scheduler.add_job(
        send_daily_report,
        CronTrigger(hour=7, minute=0, day_of_week="mon-fri", timezone="Asia/Tokyo"),
        args=[bot, chat_id], id="daily_report", replace_existing=True,
    )
    # 平日 夕18時 - ニュースレポート
    scheduler.add_job(
        send_evening_report,
        CronTrigger(hour=18, minute=0, day_of_week="mon-fri", timezone="Asia/Tokyo"),
        args=[bot, chat_id], id="evening_report", replace_existing=True,
    )
    scheduler.start()
    logger.info("スケジューラー起動: 朝6時（市況）・朝7時（日報）・夕18時（ニュース）（平日 JST）")
