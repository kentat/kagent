import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))  # 自分のTelegram User ID

# ポートフォリオ設定（けんたのポートフォリオ）
MY_PORTFOLIO = {
    "holdings": ["GEV", "NVDA", "MSFT", "CEG", "DELL", "CRDO", "ITA", "VYM", "JEPI"],
    "watchlist": ["MU", "AAPL", "AMD"],
    "base_currency": "JPY",
}

# スケジュール設定
MORNING_REPORT_HOUR = 7    # 朝レポート送信時刻（JST）
MORNING_REPORT_MINUTE = 0
MARKET_CHECK_HOUR = 23     # 夜間（NY市場中）チェック時刻
MARKET_CHECK_MINUTE = 0
