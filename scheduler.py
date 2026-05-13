"""
スケジューラー - 定期実行タスク（JST）

【モーニングブリーフの2段階処理】
5:30 → STEVEがデータ収集バッチ（ツール呼び出し・生データをRedisに保存）
6:00 → JOHNNYが保存済みデータを整形して送信（APIコスト最小・高速）

【その他】
7:00 → 日報
18:00 → 夕方ニュース
"""

import json
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from agent import run_agent, generate_daily_report, run_steve, run_johnny
from output import deliver, OutputChannel
from storage import save_report_cache, _get_redis, _use_redis

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="Asia/Tokyo")

# ─────────────────────────────────────────
# モーニングブリーフ Step1: データ収集バッチ（5:30）
# STEVEがツールを呼び出して生データをRedisに保存
# AIによる整形はしない → APIコスト最小
# ─────────────────────────────────────────




def _extract_youtube_section(raw_data: str) -> str:
    """生データからYouTubeセクションをコードで直接フォーマット"""
    import re
    lines = raw_data.split("\n")
    videos = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("【") and "】" in line:
            channel_title = line
            url = ""
            published = ""
            j = i + 1
            while j < len(lines) and not (lines[j].strip().startswith("【") and "】" in lines[j]):
                ln = lines[j].strip()
                if ln.startswith("URL: "):
                    url = ln[5:]
                elif ln.startswith("公開: "):
                    published = ln[4:]
                j += 1
            if url:
                entry = f"📺 {channel_title}"
                if published:
                    entry += f"\n🕐 {published}"
                entry += f"\n🔗 {url}"
                videos.append(entry)
            i = j
        else:
            i += 1

    if not videos:
        # フォールバック: URLを直接検索
        urls = re.findall(r"https://youtu\.be/[A-Za-z0-9_-]+", raw_data)
        titles = re.findall(r"タイトル: (.+)", raw_data)
        channels = re.findall(r"チャンネル: (.+)", raw_data)
        for idx in range(len(urls)):
            entry = "📺 "
            if idx < len(channels):
                entry += f"【{channels[idx]}】"
            if idx < len(titles):
                entry += titles[idx]
            entry += f"\n🔗 {urls[idx]}"
            videos.append(entry)

    return "\n\n".join(videos) if videos else "📭 過去24時間の新着動画はありませんでした"


def _design_prompt(raw_data: str) -> str:
    today = datetime.now().strftime("%-m/%-d")
    yt_section = _extract_youtube_section(raw_data)
    return f"""以下の生データをモーニングブリーフとして整形してください。

【生データ】
{raw_data}

【出力フォーマット】
🌅 朝のレポート {today}
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
✅ 今日のTODO（期限・重要度でピックアップ最大5件）
---
📅 今日の予定（日付は「5/14（水）13:30〜」形式。「明日」禁止）
---
📺 YouTube新着
{yt_section}"""


_RAW_DATA_KEY = "morning:raw_data"
_RAW_DATA_TTL = 3600  # 1時間TTL


def _data_collection_prompt() -> str:
    """STEVEへのデータ収集指示（ツール呼び出しのみ・整形不要）"""
    return """【朝のデータ収集バッチ】
以下のツールをすべて呼び出してデータを収集し、
収集したデータをそのまま出力してください（整形・要約は不要）。

1. get_market_indices（主要指数）
2. get_exchange_rate（USD/JPY）
3. get_portfolio_pnl（ポートフォリオ損益）
4. get_weather city=Osaka（大阪天気）
5. get_weather city=Kyoto（京都天気）
6. get_keihan_status（京阪電車）
7. get_fear_greed_index（市場心理）
8. get_upcoming_tasks due_within_days=3（全リスト横断・期限3日以内）
9. get_calendar_events（カレンダー3日分）
10. get_youtube_summary_videos hours=24（購読チャンネル24時間以内新着・字幕要約付き）

YouTube動画の出力は必ず以下の形式で全件出力すること：
【チャンネル名】タイトル
URL: https://youtu.be/VIDEO_ID
公開: MM/DD HH:MM
要約: （字幕ありの場合のみ）

すべての生データをそのまま出力してください。"""


async def collect_morning_data(bot, chat_id: int) -> bool:
    """5:30 - STEVEがデータ収集してRedisに保存（AIコスト最小）"""
    import asyncio
    try:
        logger.info("朝データ収集開始（5:30バッチ）")
        loop = asyncio.get_running_loop()
        raw_data = await loop.run_in_executor(
            None, lambda: run_steve(_data_collection_prompt())
        )

        if not raw_data or len(raw_data) < 50 or "タイムアウト" in raw_data:
            logger.error(f"朝データ収集失敗: データが空または短すぎる（{len(raw_data) if raw_data else 0}文字）")
            return False

        if _use_redis():
            _get_redis().setex(_RAW_DATA_KEY, _RAW_DATA_TTL, raw_data)
            logger.info(f"✅ 生データをRedisに保存（{len(raw_data)}文字）")
        else:
            scheduler._morning_raw_data = raw_data
            logger.info(f"✅ 生データをメモリに保存（{len(raw_data)}文字）")
        return True

    except Exception as e:
        logger.error(f"朝データ収集エラー: {e}", exc_info=True)
        return False


async def send_morning_report(bot, chat_id: int):
    """6:00 - 保存済み生データをJOHNNYが整形して送信（高速・低コスト）"""
    import asyncio
    try:
        logger.info("モーニングブリーフ送信開始（6:00）")
        loop = asyncio.get_running_loop()

        # Redisから生データを取得
        raw_data = None
        if _use_redis():
            raw_data = _get_redis().get(_RAW_DATA_KEY)
        if not raw_data:
            raw_data = getattr(scheduler, '_morning_raw_data', None)

        if not raw_data:
            # データなし → その場でSTEVEが収集（フォールバック）
            logger.warning("生データなし → その場でデータ収集")
            await bot.send_message(chat_id=chat_id, text="📊 データ収集中...")
            raw_data = await loop.run_in_executor(
                None, lambda: run_steve(_data_collection_prompt())
            )

        # JOHNNYが整形（ここだけAI使用）
        report = await loop.run_in_executor(
            None, lambda: run_johnny(raw_data, _design_prompt(raw_data))
        )
        save_report_cache("morning", report)
        await deliver(bot, chat_id, report, OutputChannel.TELEGRAM)
        logger.info("モーニングブリーフ送信完了")

    except Exception as e:
        logger.error(f"モーニングブリーフエラー: {e}", exc_info=True)
        await bot.send_message(chat_id=chat_id, text="⚠️ レポートの生成中にエラーが発生しました")


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
        logger.info("イブニングニュース生成開始")
        report = run_agent(_evening_report_prompt())
        save_report_cache("evening", report)
        await deliver(bot, chat_id, report, OutputChannel.TELEGRAM)
        logger.info("イブニングニュース送信完了")
    except Exception as e:
        logger.error(f"イブニングニュースエラー: {e}")


# ─────────────────────────────────────────
# セットアップ
# ─────────────────────────────────────────

def setup_scheduler(bot, chat_id: int):
    """定期タスクを登録して起動（すべてJST）"""

    # 平日 5:30 - データ収集バッチ（STEVE・ツールのみ・AIコスト最小）
    scheduler.add_job(
        collect_morning_data,
        CronTrigger(hour=5, minute=30, day_of_week="mon-fri", timezone="Asia/Tokyo"),
        args=[bot, chat_id], id="collect_morning_data", replace_existing=True,
    )
    # 平日 6:00 - モーニングブリーフ送信（JOHNNYが整形・高速）
    scheduler.add_job(
        send_morning_report,
        CronTrigger(hour=6, minute=0, day_of_week="mon-fri", timezone="Asia/Tokyo"),
        args=[bot, chat_id], id="morning_report", replace_existing=True,
    )
    # 平日 7:00 - 日報
    scheduler.add_job(
        send_daily_report,
        CronTrigger(hour=7, minute=0, day_of_week="mon-fri", timezone="Asia/Tokyo"),
        args=[bot, chat_id], id="daily_report", replace_existing=True,
    )
    # 平日 18:00 - 夕方ニュース
    scheduler.add_job(
        send_evening_report,
        CronTrigger(hour=18, minute=0, day_of_week="mon-fri", timezone="Asia/Tokyo"),
        args=[bot, chat_id], id="evening_report", replace_existing=True,
    )
    scheduler.start()
    logger.info("スケジューラー起動: 5:30データ収集→6:00モーニングブリーフ→7:00日報→18:00ニュース（平日 JST）")
