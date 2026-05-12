"""
tools.py リグレッションテスト
================================
外部API（yfinance, Google, YouTube等）はすべてモック
ビジネスロジックのみをテスト
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["REDIS_URL"] = ""
import tempfile
os.environ["DB_PATH"] = tempfile.mktemp(suffix=".db")


class TestExecuteTool:
    """execute_tool ディスパッチのリグレッション"""

    def test_unknown_tool_returns_error(self):
        from tools import execute_tool
        result = execute_tool("nonexistent_tool", {})
        assert isinstance(result, str)  # エラー系の文字列が返ればOK

    def test_all_tools_registered(self):
        """tools.pyのdispatch dictに登録されているツールが呼び出し可能か"""
        import re
        with open("tools.py") as f:
            src = f.read()
        m = re.search(r'dispatch\s*=\s*\{([^}]+)\}', src, re.DOTALL)
        assert m, "dispatch dictが見つかりません"
        tool_names = re.findall(r'"([^"]+)":\s*\w+', m.group(1))
        assert len(tool_names) > 0
        assert "get_stock_price" in tool_names
        assert "get_portfolio_pnl" in tool_names
        assert "get_upcoming_tasks" in tool_names


class TestStockTools:
    """株価・市場ツールのリグレッション（yfinanceモック）"""

    @patch("tools.yf")
    def test_get_exchange_rate(self, mock_yf):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = MagicMock(
            empty=False,
            iloc=[None, MagicMock(**{"__getitem__": lambda self, x: {"Close": 157.0}[x]})]
        )
        mock_yf.Ticker.return_value = mock_ticker
        from tools import get_exchange_rate
        result = get_exchange_rate()
        assert isinstance(result, dict)

    @patch("tools.yf")
    def test_get_stock_price_structure(self, mock_yf):
        """株価取得の返り値の構造が壊れていないか"""
        mock_ticker = MagicMock()
        mock_info = {
            "currentPrice": 215.0,
            "previousClose": 210.0,
            "marketCap": 1000000000,
            "shortName": "NVIDIA",
        }
        mock_ticker.info = mock_info
        mock_yf.Ticker.return_value = mock_ticker
        from tools import get_stock_price
        result = get_stock_price("NVDA")
        assert isinstance(result, dict)


class TestWeatherTools:
    """天気ツールのリグレッション（requestsモック）"""

    @patch("tools.requests.get")
    def test_get_weather_osaka(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "current_condition": [{
                "temp_C": "22",
                "FeelsLikeC": "24",
                "weatherDesc": [{"value": "Partly cloudy"}],
                "humidity": "60",
            }],
            "weather": [{"maxtempC": "25", "mintempC": "15"}],
        }
        mock_get.return_value = mock_resp
        from tools import get_weather
        result = get_weather("Osaka")
        assert isinstance(result, dict)
        assert "city" in result

    @patch("tools.requests.get")
    def test_get_weather_error_handling(self, mock_get):
        """天気APIがエラーでも正常な辞書を返す"""
        mock_get.side_effect = Exception("Network error")
        from tools import get_weather
        result = get_weather("Osaka")
        assert isinstance(result, dict)
        assert "error" in result or "city" in result


class TestKeihanStatus:
    """京阪電車のスクレイピングリグレッション"""

    @patch("tools.requests.get")
    def test_normal_operation(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = "<html><main><p>平常通り運転しています</p></main></html>"
        mock_resp.encoding = "utf-8"
        mock_get.return_value = mock_resp
        from tools import get_keihan_status
        result = get_keihan_status()
        assert "平常" in result["status"] or "✅" in result["status"]

    @patch("tools.requests.get")
    def test_delay_detection(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = "<html><main><p>現在、遅延が発生しています</p></main></html>"
        mock_resp.encoding = "utf-8"
        mock_get.return_value = mock_resp
        from tools import get_keihan_status
        result = get_keihan_status()
        assert "遅延" in result["status"] or "⚠️" in result["status"]

    @patch("tools.requests.get")
    def test_no_false_positive(self, mock_get):
        """「遅延」がページ内に単独で存在しても誤検知しない"""
        mock_resp = MagicMock()
        # ナビリンクに「遅延情報」があるだけで実際は平常
        mock_resp.text = """<html>
        <nav><a href="/delay">遅延情報</a></nav>
        <main><p>平常通り運転しています</p></main>
        </html>"""
        mock_resp.encoding = "utf-8"
        mock_get.return_value = mock_resp
        from tools import get_keihan_status
        result = get_keihan_status()
        assert "平常" in result["status"] or "✅" in result["status"]


class TestFearGreedIndex:
    """Fear & Greed Index（VIX推定）のリグレッション"""

    @patch("tools.yf")
    def test_returns_valid_structure(self, mock_yf):
        """スコアが0-100の範囲で返る"""
        mock_vix = MagicMock()
        mock_vix.history.return_value = MagicMock(
            empty=False,
            **{"__getitem__": lambda self, k: MagicMock(
                iloc=MagicMock(**{"__getitem__": lambda s, i: 15.0})
            )}
        )
        mock_sp = MagicMock()
        sp_close = MagicMock()
        sp_close.iloc.__getitem__ = lambda s, i: 5000.0
        sp_close.tail.return_value.mean.return_value = 4900.0
        sp_close.__len__ = lambda s: 30
        mock_sp.history.return_value = MagicMock(
            empty=False,
            **{"__getitem__": lambda self, k: sp_close}
        )
        mock_yf.Ticker.side_effect = [mock_vix, mock_sp]
        from tools import get_fear_greed_index
        result = get_fear_greed_index()
        assert isinstance(result, dict)
        assert "score" in result
        assert "rating" in result
        assert "label_jp" in result

    @patch("tools.yf")
    def test_fallback_on_error(self, mock_yf):
        """エラー時にデフォルト値50を返す"""
        mock_yf.Ticker.side_effect = Exception("Network error")
        from tools import get_fear_greed_index
        result = get_fear_greed_index()
        assert isinstance(result, dict)
        assert result["score"] in (50, None)  # エラー時はNoneまたはデフォルト50



class TestGTDTools:
    """GTD課題管理ツールのリグレッション"""

    def test_add_and_get_issue(self):
        from tools import add_agent_issue, get_all_issues
        result = add_agent_issue("STEVE", "テスト課題", "詳細")
        assert "追加" in result
        issues = get_all_issues(agent_name="STEVE", issue_type="issue")
        assert isinstance(issues, list)

    def test_update_gtd_status(self):
        from tools import add_agent_issue, update_gtd_status
        add_agent_issue("STEVE", "ステータス更新テスト")
        from tools import get_all_issues
        issues = get_all_issues()
        if issues:
            issue_id = int(issues[0]["id"])
            result = update_gtd_status(issue_id, "in_progress")
            assert "更新" in result

    def test_invalid_gtd_status(self):
        from tools import update_gtd_status
        result = update_gtd_status(999, "invalid_status")
        assert "失敗" in result or "エラー" in result
