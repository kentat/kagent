"""
スケジューラー - 定期実行タスク
朝7時：市況レポート / 夜23時：ニュースレポート（平日）
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from agent import run_agent, generate_daily_report
from config import MORNING_REPORT_HOUR, MORNING_REPORT_MINUTE, MARKET_CHECK_HOUR, MARKET_CHECK_MINUTE

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

=== STEP 5: タスク ===
get_tasks で未完了タスク一覧を取得

=== STEP 6: YouTube新着 ===
get_youtube_new_videos hours=48 で新着動画を取得
動画がない場合は「📭 過去48時間の新着動画はありませんでした」と表示

=== STEP 7: カレンダー ===
get_calendar_events で今日〜3日分の予定を取得
日付は「5/14（水）13:30〜」のように具体的な日付と曜日で表示。「明日」などの相対表現禁止

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
📋 タスク（なければ「なし」）
---
📺 YouTube新着（なければ「📭 過去48時間の新着動画はありませんでした」）
---
📅 今日の予定（なければ「なし」）"""


def _evening_report_prompt() -> str:
    return """【夜間ニュースレポート】以下を順番に実行してください。

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
🌙 夜間ニュース [日付]
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
    try:
        logger.info("朝レポート生成開始")
        await bot.send_message(chat_id=chat_id, text="📊 朝の市況レポートを作成中...")
        report = run_agent(_morning_report_prompt())
        await bot.send_message(chat_id=chat_id, text=report)
        logger.info("朝レポート送信完了")
    except Exception as e:
        logger.error(f"朝レポートエラー: {e}")
        await bot.send_message(chat_id=chat_id, text=f"⚠️ レポート生成エラー: {str(e)}")


async def send_evening_report(bot, chat_id: int):
    try:
        logger.info("夜間レポート生成開始")
        report = run_agent(_evening_report_prompt())
        await bot.send_message(chat_id=chat_id, text=report)
        logger.info("夜間レポート送信完了")
    except Exception as e:
        logger.error(f"夜間レポートエラー: {e}")


# ─────────────────────────────────────────
# セットアップ
# ─────────────────────────────────────────

async def send_daily_report(bot, chat_id: int):
    """坂本による日報を送信（平日22時）"""
    try:
        logger.info("日報生成開始")
        report = generate_daily_report()
        await bot.send_message(chat_id=chat_id, text=report)
        logger.info("日報送信完了")
    except Exception as e:
        logger.error(f"日報エラー: {e}")


def setup_scheduler(bot, chat_id: int):
    """定期タスクを登録して起動"""
    scheduler.add_job(
        send_morning_report,
        CronTrigger(hour=MORNING_REPORT_HOUR, minute=MORNING_REPORT_MINUTE,
                    day_of_week="mon-fri", timezone="Asia/Tokyo"),
        args=[bot, chat_id], id="morning_report", replace_existing=True,
    )
    # 平日22:00 - 日報（作業ログまとめ）
    scheduler.add_job(
        send_daily_report,
        CronTrigger(hour=22, minute=0,
                    day_of_week="mon-fri", timezone="Asia/Tokyo"),
        args=[bot, chat_id], id="daily_report", replace_existing=True,
    )
    scheduler.add_job(
        send_evening_report,
        CronTrigger(hour=MARKET_CHECK_HOUR, minute=MARKET_CHECK_MINUTE,
                    day_of_week="mon-fri", timezone="Asia/Tokyo"),
        args=[bot, chat_id], id="evening_report", replace_existing=True,
    )
    scheduler.start()
    logger.info(f"スケジューラー起動: 朝{MORNING_REPORT_HOUR}時・夜22時（日報）・夜{MARKET_CHECK_HOUR}時（平日）")
