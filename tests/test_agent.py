"""
agent.py リグレッションテスト
================================
Claude APIはモック
エージェントのフロー・ログ・通信を検証
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["REDIS_URL"] = ""
import tempfile
os.environ["DB_PATH"] = tempfile.mktemp(suffix=".db")


def make_mock_response(text: str):
    """Anthropic APIのレスポンスモックを生成"""
    mock_block = MagicMock()
    mock_block.text = text
    mock_block.type = "text"
    mock_resp = MagicMock()
    mock_resp.content = [mock_block]
    mock_resp.stop_reason = "end_turn"
    return mock_resp


class TestLoadAgentDef:
    """エージェント定義の読み込みリグレッション"""

    def test_load_sakamoto(self):
        from agent import _load_agent_def
        result = _load_agent_def("SAKAMOTO")
        assert len(result) > 100
        assert "坂本" in result or "SAKAMOTO" in result or "秘書" in result

    def test_load_steve(self):
        from agent import _load_agent_def
        result = _load_agent_def("STEVE")
        assert len(result) > 100
        assert "STEVE" in result or "分析" in result

    def test_load_johnny(self):
        from agent import _load_agent_def
        result = _load_agent_def("JOHNNY")
        assert len(result) > 100
        # JOHNNYはナレッジを含まない（出力混入防止）
        assert "直近の作業ナレッジ" not in result

    def test_johnny_no_knowledge_leakage(self):
        """JOHNNYのシステムプロンプトに過去ログが含まれないことを確認"""
        # ログを先に書いておく
        import storage
        storage.write_agent_log("JOHNNY", "テストタスク", "テスト結果")
        from agent import _load_agent_def
        result = _load_agent_def("JOHNNY")
        assert "直近の作業ナレッジ" not in result


class TestRunJohnny:
    """JOHNNYのフォーマット処理リグレッション"""

    @patch("agent.client")
    def test_run_johnny_basic(self, mock_client):
        mock_client.messages.create.return_value = make_mock_response(
            "🌅 テストレポート\n---\n• 項目1\n• 項目2"
        )
        from agent import run_johnny
        result = run_johnny("生データ", "モーニングブリーフ")
        assert isinstance(result, str)
        assert len(result) > 0

    @patch("agent.client")
    def test_run_johnny_logs_work(self, mock_client):
        """JOHNNYが作業ログを記録するか"""
        mock_client.messages.create.return_value = make_mock_response("テスト出力")
        import storage
        storage.init_db()
        from agent import run_johnny
        run_johnny("生データ", "テストリクエスト")
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        logs = storage.get_agent_logs(date=today, agent_name="JOHNNY")
        assert len(logs) >= 1
        assert any("整形" in log["task"] for log in logs)


class TestRunSteve:
    """STEVEのデータ収集リグレッション"""

    @patch("agent.client")
    def test_run_steve_end_turn(self, mock_client):
        """ツールなしで即終了するケース"""
        mock_client.messages.create.return_value = make_mock_response(
            "データ収集完了: S&P500 7412.84"
        )
        from agent import run_steve
        result = run_steve("株価を取得してください")
        assert isinstance(result, str)
        assert len(result) > 0

    @patch("agent.execute_tool")
    @patch("agent.client")
    def test_run_steve_with_tool_use(self, mock_client, mock_tool):
        """ツールを使うケース"""
        # 1回目: tool_use
        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.id = "tool_001"
        mock_tool_block.name = "get_stock_price"
        mock_tool_block.input = {"ticker": "NVDA"}

        mock_tool_resp = MagicMock()
        mock_tool_resp.content = [mock_tool_block]
        mock_tool_resp.stop_reason = "tool_use"

        # 2回目: end_turn
        mock_end_resp = make_mock_response("NVDA: $215.20")

        mock_client.messages.create.side_effect = [mock_tool_resp, mock_end_resp]
        mock_tool.return_value = '{"price": 215.20}'

        from agent import run_steve
        result = run_steve("NVDAの株価を教えて")
        assert isinstance(result, str)
        mock_tool.assert_called_once()


class TestRunAgent:
    """坂本（メインエージェント）フローのリグレッション"""

    @patch("agent.client")
    def test_run_agent_flow(self, mock_client):
        """坂本→STEVE→JOHNNY→坂本のフローが完走するか"""
        mock_client.messages.create.return_value = make_mock_response(
            "STEVEへの指示: 株価を取得してください"
        )
        from agent import run_agent
        result = run_agent("NVDAの株価は？")
        assert isinstance(result, str)
        assert len(result) > 0

    @patch("agent.client")
    def test_run_agent_logs_comm(self, mock_client):
        """エージェント間通信がログに記録されるか"""
        mock_client.messages.create.return_value = make_mock_response("テスト返答")
        import storage
        storage.init_db()
        from agent import run_agent
        run_agent("テストメッセージ")
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        logs = storage.get_comm_logs(date=today)
        assert len(logs) >= 1
        # けんた→坂本の通信が記録されているか
        assert any(log["from"] == "KENTA" for log in logs)
