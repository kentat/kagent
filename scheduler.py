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
    return f"""【朝の市況レポート】を作成してください。以下の全セクションを必ず順番に実行してください。

=== STEP 1: 指数・為替 ===
get_market_indices で主要指数を取得
get_exchange_rate でUSD/JPYを取得

=== STEP 2: ポートフォリオ ===
get_portfolio_pnl でポートフォリオ全銘柄の損益を取得
→ 上昇トップ3・下落ワースト3・監視銘柄も表示

=== STEP 3: 天気 ===
必ず以下2つのツールを両方呼び出すこと：
- get_weather city=Osaka → 大阪の天気
- get_weather city=Kyoto → 京都の天気
両方の結果を必ずレポートに含めること

=== STEP 3.2: 京阪電車 ===
get_keihan_status で京阪電車の運行情報を取得

=== STEP 3.5: 市場心理 ===
get_fear_greed_index でFear & Greed Indexを取得

=== STEP 4: タスク ===
get_tasks で未完了タスク一覧を取得

=== STEP 5: YouTube新着動画 ===
必ず get_youtube_new_videos hours=48 を呼び出すこと
- 動画がある場合：タイトルとURLをリスト表示
- 動画がない場合：「📭 過去48時間の新着動画はありませんでした」と必ず明記すること

=== STEP 6: カレンダー ===
get_calendar_events で今日〜3日分の予定を取得

=== STEP 4: タスク ===
get_tasks で未完了タスク一覧を取得

=== STEP 5: YouTube新着動画 ===
get_youtube_new_videos hours=48 で過去48時間の新着動画を取得
→ タイトルとURLをリスト表示。1件もなければ「過去48時間の新着なし」と表示

=== STEP 6: カレンダー ===
get_calendar_events で今日〜3日分の予定を取得

=== 出力フォーマット ===
🌅 朝のレポート [日付]
---
📈 市況サマリー
（指数・為替）
---
😱 市場心理: [スコア]/100（[状態]）
---
💰 ポートフォリオ
（損益・ヒーロー銘柄・注意銘柄）
---
🌤 天気
大阪：（天気・最高/最低気温）
京都：（天気・最高/最低気温）
🚃 京阪電車：（運行状況）
---
📋 タスク
（未完了タスク一覧、なければ「予定なし」）
---
📺 YouTube新着
（新着動画があればタイトルとURL一覧。1件もなければ「📭 過去48時間の新着動画はありませんでした」と表示）
---
📅 今日の予定
（カレンダー3日分。日付は「明日」「今日」などの相対表現を使わず「5/14（水）」のように具体的な日付と曜日で表示すること。なければ「予定なし」）"""


def _evening_report_prompt() -> str:
    return """【夜間ニュースレポート】NYマーケット時間帯の注目ニュースをまとめてください。

以下を順番にweb_searchで調査してまとめてください：

【米国株・市場ニュース】
1. 「US stock market news today」で検索
2. 「S&P500 NASDAQ market today」で検索
   → 今日の相場全体の動き・注目セクター・話題の銘柄ニュース
3. get_fear_greed_index で市場心理指数を取得

【AI・テクノロジーニュース】
4. 「AI artificial intelligence news today 2026」で検索
5. 「AI business use case productivity 2026」で検索
   → 新しいAI技術・ツール・活用事例・ビジネス利用法

【Hacker Newsトップ】
6. get_hacker_news でトップ5記事を取得
   → タイトルとURL・スコアを表示

各ニュースは：
- 内容を簡潔に日本語で要約（2〜3行）
- 元記事のURLも必ず含める

フォーマット：
🌙 夜間ニュース [日付]
---
😱 市場心理（Fear & Greed）
（スコアと状態）
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
---
💻 Hacker News
• タイトル（スコア pt）
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
