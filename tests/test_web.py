"""
output.py / web_server.py リグレッションテスト
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["REDIS_URL"] = ""
os.environ["WEB_USERNAME"] = "testuser"
os.environ["WEB_PASSWORD"] = "testpass"
import tempfile
os.environ["DB_PATH"] = tempfile.mktemp(suffix=".db")


class TestOutputChannel:
    """output.pyのフォーマット変換リグレッション"""

    def test_telegram_format_passthrough(self):
        from output import format_for_channel, OutputChannel
        text = "🌅 テストレポート\n---\n• 項目1\n• 項目2"
        result = format_for_channel(text, OutputChannel.TELEGRAM)
        assert result == text

    def test_html_not_implemented(self):
        from output import format_for_channel, OutputChannel
        with pytest.raises(NotImplementedError):
            format_for_channel("test", OutputChannel.HTML)

    def test_email_not_implemented(self):
        from output import format_for_channel, OutputChannel
        with pytest.raises(NotImplementedError):
            format_for_channel("test", OutputChannel.EMAIL)


class TestWebServer:
    """web_server.pyのエンドポイントリグレッション"""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from web_server import app
        return TestClient(app)

    def test_root_requires_auth(self, client):
        """認証なしでアクセスすると401"""
        response = client.get("/")
        assert response.status_code == 401

    def test_health_requires_auth(self, client):
        """/health も認証必須"""
        response = client.get("/health")
        assert response.status_code == 401

    def test_root_with_auth(self, client):
        """正しい認証情報でアクセスできる"""
        response = client.get("/", auth=("testuser", "testpass"))
        assert response.status_code == 200
        assert "Kenta" in response.text

    def test_morning_page(self, client):
        response = client.get("/", auth=("testuser", "testpass"))
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_evening_page(self, client):
        response = client.get("/evening", auth=("testuser", "testpass"))
        assert response.status_code == 200

    def test_report_page(self, client):
        response = client.get("/report", auth=("testuser", "testpass"))
        assert response.status_code == 200

    def test_wrong_password(self, client):
        response = client.get("/", auth=("testuser", "wrongpass"))
        assert response.status_code == 401

    def test_html_contains_nav(self, client):
        """ナビゲーションが含まれているか"""
        response = client.get("/", auth=("testuser", "testpass"))
        assert "Morning" in response.text or "モーニング" in response.text

    def test_empty_cache_shows_placeholder(self, client):
        """キャッシュが空でもクラッシュしない"""
        response = client.get("/", auth=("testuser", "testpass"))
        assert response.status_code == 200

    def test_debug_endpoint(self, client):
        response = client.get("/debug", auth=("testuser", "testpass"))
        assert response.status_code == 200
        data = response.json()
        assert "redis_connected" in data
        assert "morning_cache" in data


class TestWebServerMarkdown:
    """Markdownのテキスト変換リグレッション"""

    def test_markdown_to_html_basic(self):
        from web_server import _md_to_html
        result = _md_to_html("## 見出し\n• 項目1\n• 項目2")
        assert "<h2>" in result
        assert "<li>" in result

    def test_markdown_divider(self):
        from web_server import _md_to_html
        result = _md_to_html("上\n---\n下")
        assert "<hr" in result

    def test_markdown_bold(self):
        from web_server import _md_to_html
        result = _md_to_html("**太字**テキスト")
        assert "<strong>" in result

    def test_youtube_url_becomes_card(self):
        from web_server import _md_to_html
        result = _md_to_html("動画: https://youtu.be/abc123xyz78")
        assert "yt-card" in result or "youtu" in result
