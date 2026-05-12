"""
batch.py - 5:30バッチ処理
========================================
AIを使わず、ツールを直接呼び出して生データを収集し
Redisに保存する。APIコスト0。

6:00にscheduler.pyがこのデータをRedisから読み込み、
JOHNNYが1回だけAIを使って整形・送信する。
========================================
"""

import json
import logging
from datetime import datetime
from tools import execute_tool
from storage import _use_redis, _get_redis

logger = logging.getLogger(__name__)
BATCH_KEY = "morning:batch_data"
BATCH_TTL = 3600  # 1時間


def collect_all_data() -> dict:
    """
    全ツールを直接呼び出してデータを収集する（AI不使用）
    戻り値: 生データのdict
    """
    logger.info("バッチデータ収集開始（AI不使用）")
    data = {}

    tools = [
        ("market_indices",   "get_market_indices",    {}),
        ("exchange_rate",    "get_exchange_rate",      {}),
        ("portfolio_pnl",    "get_portfolio_pnl",      {}),
        ("weather_osaka",    "get_weather",            {"city": "Osaka"}),
        ("weather_kyoto",    "get_weather",            {"city": "Kyoto"}),
        ("keihan",           "get_keihan_status",      {}),
        ("fear_greed",       "get_fear_greed_index",   {}),
        ("tasks_bucket",     "get_google_tasks",       {"tasklist_title": "バケツリスト", "due_within_days": 3}),
        ("tasks_teiki",      "get_google_tasks",       {"tasklist_title": "定期", "due_within_days": 3}),
        ("calendar",         "get_calendar_events",    {"days": 3}),
        ("youtube",          "get_youtube_summary_videos", {"hours": 24}),
    ]

    for key, tool_name, args in tools:
        try:
            result = execute_tool(tool_name, args)
            data[key] = result
            logger.info(f"  ✅ {tool_name}")
        except Exception as e:
            data[key] = {"error": str(e)}
            logger.warning(f"  ⚠️ {tool_name}: {e}")

    data["collected_at"] = datetime.now().isoformat()
    logger.info(f"バッチ収集完了（{len(tools)}ツール）")
    return data


def save_batch_data(data: dict) -> bool:
    """生データをRedisに保存する"""
    if _use_redis():
        _get_redis().setex(BATCH_KEY, BATCH_TTL, json.dumps(data, ensure_ascii=False))
        logger.info(f"✅ Redisに保存完了（TTL={BATCH_TTL}秒）")
        return True
    logger.warning("Redis未接続 → メモリ保存")
    return False


def load_batch_data() -> dict:
    """Redisから生データを取得する"""
    if _use_redis():
        raw = _get_redis().get(BATCH_KEY)
        if raw:
            return json.loads(raw)
    return {}


def format_batch_for_johnny(data: dict) -> str:
    """
    Redisの生データをJOHNNYが読める形式のテキストに変換する（AI不使用）
    """
    if not data:
        return "データなし"

    lines = ["【モーニングブリーフ用生データ】"]
    lines.append(f"収集時刻: {data.get('collected_at', '不明')}")
    lines.append("")

    for key, value in data.items():
        if key == "collected_at":
            continue
        lines.append(f"[{key}]")
        lines.append(json.dumps(value, ensure_ascii=False, indent=2)[:500])
        lines.append("")

    return "\n".join(lines)
