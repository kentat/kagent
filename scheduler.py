"""
スケジューラー
定期実行タスク（朝レポート、夜間市況チェック等）
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from agent import run_agent
from config import (
    MORNING_REPORT_HOUR,
    MORNING_REPORT_MINUTE,
    MARKET_CHECK_HOUR,
    MARKET_CHECK_MINUTE,
    MY_PORTFOLIO,
)

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="Asia/Tokyo")


# ─────────────────────────────────────────
# レポートプロンプト定義
# ─────────────────────────────────────────

def _morning_report_prompt() -> str:
    tickers = ", ".join(MY_PORTFOLIO["holdings"])
    return f"""【朝の市況レポート】を作成してください。

以下を順番に調査してまとめてください：
1. 主要指数（S&P500, NASDAQ, 日経225）の昨日の終値・騰落率
2. USD/JPY為替レート
3. 保有銘柄の株価: {tickers}
   → 各銘柄: 現値・前日比・特筆事項
4. 東京の今日の天気（最高/最低気温、天気）
5. 今日のタスク（DBから取得）
6. 登録YouTubeチャンネルの昨日からの新着動画（タイトルとリンク）
7. Googleカレンダーから今日〜3日分の予定

フォーマット：
📊 朝の市況 [日付]
---
🌍 主要指数
（内容）
---
💴 為替
（内容）
---
📈 ポートフォリオ
（内容）
---
🌤 天気
（内容）
---
📋 今日のタスク
（内容）"""


def _evening_report_prompt() -> str:
    return """【夜間ニュースレポート】NYマーケット時間帯の注目ニュースをまとめてください。

以下を順番にweb_searchで調査してまとめてください：

【米国株・市場ニュース】
1. 「US stock market news today」で検索
2. 「S&P500 NASDAQ market today」で検索
   → 今日の相場全体の動き・注目セクター・話題の銘柄ニュース

【AI・テクノロジーニュース】
3. 「AI artificial intelligence news today 2026」で検索
4. 「AI business use case productivity 2026」で検索
   → 新しいAI技術・ツール・活用事例・ビジネス利用法

各ニュースは：
- 内容を簡潔に日本語で要約（2〜3行）
- 元記事のURLも必ず含める

フォーマット：
🌙 夜間ニュース [日付]
---
📈 米国株・市場
• ニュースタイトル
  要約（2〜3行）
  🔗 URL

---
🤖 AI・テクノロジー
• ニュースタイトル
  要約（2〜3行）
  🔗 URL

重要：URLは必ず実際のリンクを記載すること。ニュースは各セクション3〜5件。"""


# ─────────────────────────────────────────
# スケジュール実行関数
# ─────────────────────────────────────────

async def send_morning_report(bot, chat_id: int):
    """朝レポートを送信"""
    try:
        logger.info("朝レポート生成開始")
        await bot.send_message(chat_id=chat_id, text="📊 おはようございます。朝の市況レポートを作成中...")
        report = run_agent(_morning_report_prompt())
        await bot.send_message(chat_id=chat_id, text=report)
        logger.info("朝レポート送信完了")
    except Exception as e:
        logger.error(f"朝レポートエラー: {e}")
        await bot.send_message(chat_id=chat_id, text=f"⚠️ レポート生成エラー: {str(e)}")


async def send_evening_report(bot, chat_id: int):
    """夜間市況チェックを送信"""
    try:
        logger.info("夜間チェック開始")
        report = run_agent(_evening_report_prompt())
        await bot.send_message(chat_id=chat_id, text=report)
        logger.info("夜間チェック送信完了")
    except Exception as e:
        logger.error(f"夜間チェックエラー: {e}")


# ─────────────────────────────────────────
# スケジューラーセットアップ
# ─────────────────────────────────────────

def setup_scheduler(bot, chat_id: int):
    """定期タスクを登録して起動"""

    # 平日朝7:00 - 朝の市況レポート
    scheduler.add_job(
        send_morning_report,
        CronTrigger(
            hour=MORNING_REPORT_HOUR,
            minute=MORNING_REPORT_MINUTE,
            day_of_week="mon-fri",
            timezone="Asia/Tokyo",
        ),
        args=[bot, chat_id],
        id="morning_report",
        replace_existing=True,
    )

    # 平日夜23:00 - NY市場チェック
    scheduler.add_job(
        send_evening_report,
        CronTrigger(
            hour=MARKET_CHECK_HOUR,
            minute=MARKET_CHECK_MINUTE,
            day_of_week="mon-fri",
            timezone="Asia/Tokyo",
        ),
        args=[bot, chat_id],
        id="evening_report",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(f"スケジューラー起動: 朝{MORNING_REPORT_HOUR}時・夜{MARKET_CHECK_HOUR}時（平日）")
