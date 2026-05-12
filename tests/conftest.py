"""
テスト共通設定 - 外部パッケージをすべてモック
"""
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

# テスト用環境変数
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("DB_PATH", tempfile.mktemp(suffix="_test.db"))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("WEB_USERNAME", "testuser")
os.environ.setdefault("WEB_PASSWORD", "testpass")
os.environ.setdefault("ALLOWED_USER_ID", "12345")

# 外部パッケージを全てモック（インストール不要）
MOCK_MODULES = {
    "yfinance": MagicMock(),
    "anthropic": MagicMock(),
    "fastapi": MagicMock(),
    "fastapi.security": MagicMock(),
    "fastapi.responses": MagicMock(),
    "uvicorn": MagicMock(),
    "apscheduler": MagicMock(),
    "apscheduler.schedulers": MagicMock(),
    "apscheduler.schedulers.asyncio": MagicMock(),
    "apscheduler.triggers": MagicMock(),
    "apscheduler.triggers.cron": MagicMock(),
    "telegram": MagicMock(),
    "telegram.ext": MagicMock(),
    "google": MagicMock(),
    "google.oauth2": MagicMock(),
    "google.oauth2.credentials": MagicMock(),
    "googleapiclient": MagicMock(),
    "googleapiclient.discovery": MagicMock(),
    "feedparser": MagicMock(),
    "youtube_transcript_api": MagicMock(),
    "redis": MagicMock(),
    "requests": MagicMock(),
    "httpx": MagicMock(),
}

for mod, mock in MOCK_MODULES.items():
    if mod not in sys.modules:
        sys.modules[mod] = mock

# FastAPI特別設定
import fastapi as _fa
_fa.FastAPI = MagicMock(return_value=MagicMock())
_fa.Depends = lambda x: x
_fa.HTTPException = type("HTTPException", (Exception,), {"status_code": 401})
_fa.status = MagicMock()
_fa.status.HTTP_401_UNAUTHORIZED = 401

# requests特別設定
import requests as _req
_req.get = MagicMock()
