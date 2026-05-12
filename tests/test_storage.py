"""
storage.py リグレッションテスト
================================
実際のSQLiteを使用（テスト用DB）
Redisはモック
"""

import os
import sys
import pytest
import tempfile
from unittest.mock import MagicMock, patch

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# テスト用の環境変数を設定（本番DBを汚染しない）
os.environ["REDIS_URL"] = ""  # Redisなし→SQLiteで動作
TEST_DB = tempfile.mktemp(suffix=".db")
os.environ["DB_PATH"] = TEST_DB

import storage


@pytest.fixture(autouse=True)
def clean_db():
    """各テスト前後にテスト用DBを初期化"""
    storage.init_db()
    yield
    # テスト後にグローバル状態をリセット
    storage._conversations.clear()


class TestConversationHistory:
    """会話履歴のCRUD"""

    def test_get_empty_conversation(self):
        result = storage.get_conversation(12345)
        assert result == []

    def test_set_and_get_conversation(self):
        history = [{"role": "user", "content": "こんにちは"}]
        storage.set_conversation(12345, history)
        result = storage.get_conversation(12345)
        assert result == history

    def test_conversation_max_length(self):
        """20件を超えたら古いものが削除される"""
        history = [{"role": "user", "content": f"msg{i}"} for i in range(25)]
        storage.set_conversation(12345, history)
        result = storage.get_conversation(12345)
        assert len(result) <= storage.MAX_CONV

    def test_clear_conversation(self):
        storage.set_conversation(12345, [{"role": "user", "content": "test"}])
        storage.clear_conversation(12345)
        assert storage.get_conversation(12345) == []


class TestNotes:
    """メモのCRUD"""

    def test_save_and_get_note(self):
        result = storage.save_note("テストメモ", "general")
        assert "保存" in result

        notes = storage.get_notes()
        assert len(notes) >= 1
        assert any("テストメモ" in n["content"] for n in notes)

    def test_get_notes_by_category(self):
        storage.save_note("投資メモ", "investment")
        storage.save_note("一般メモ", "general")

        investment_notes = storage.get_notes(category="investment")
        assert all(n.get("category") == "investment" for n in investment_notes)

    def test_note_limit(self):
        for i in range(15):
            storage.save_note(f"メモ{i}")
        notes = storage.get_notes(limit=5)
        assert len(notes) <= 5


class TestTasks:
    """タスクのCRUD"""

    def test_add_task(self):
        result = storage.add_task("テストタスク")
        assert "追加" in result

    def test_get_pending_tasks(self):
        storage.add_task("未完了タスク")
        tasks = storage.get_tasks(status="pending")
        assert any("未完了タスク" in t["title"] for t in tasks)

    def test_complete_task(self):
        storage.add_task("完了するタスク")
        tasks = storage.get_tasks(status="pending")
        task_id = int(tasks[0]["id"])
        result = storage.complete_task(task_id)
        assert "完了" in result

        # 完了後はpendingに出ない
        pending = storage.get_tasks(status="pending")
        assert not any(int(t["id"]) == task_id for t in pending)


class TestReportCache:
    """レポートキャッシュ"""

    def test_save_and_get_morning_report(self):
        content = "🌅 テストモーニングブリーフ"
        storage.save_report_cache("morning", content)
        result = storage.get_report_cache("morning")
        assert result["content"] == content
        assert "updated_at" in result

    def test_get_nonexistent_report(self):
        result = storage.get_report_cache("nonexistent")
        assert result == {}

    def test_overwrite_report(self):
        storage.save_report_cache("evening", "旧レポート")
        storage.save_report_cache("evening", "新レポート")
        result = storage.get_report_cache("evening")
        assert result["content"] == "新レポート"


class TestAgentLogs:
    """エージェント作業ログ"""

    def test_write_and_get_log(self):
        storage.write_agent_log(
            agent_name="STEVE",
            task="テストタスク",
            result_summary="テスト完了",
            issues="",
            thinking_process="テスト思考"
        )
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        logs = storage.get_agent_logs(date=today, agent_name="STEVE")
        assert len(logs) >= 1
        assert any("テストタスク" in log["task"] for log in logs)

    def test_get_recent_knowledge(self):
        storage.write_agent_log("STEVE", "ナレッジテスト")
        knowledge = storage.get_recent_knowledge(agent_name="STEVE", days=1)
        assert isinstance(knowledge, list)


class TestGTDIssues:
    """GTD課題・提案管理"""

    def test_add_issue(self):
        issue_id = storage.add_issue("STEVE", "テスト課題", "詳細", "issue")
        assert isinstance(issue_id, int)

    def test_add_proposal(self):
        issue_id = storage.add_issue("JOHNNY", "テスト提案", "詳細", "proposal")
        assert isinstance(issue_id, int)

    def test_get_issues(self):
        storage.add_issue("STEVE", "課題A")
        issues = storage.get_issues()
        assert len(issues) >= 1

    def test_update_issue_status(self):
        issue_id = storage.add_issue("STEVE", "ステータステスト")
        result = storage.update_issue_status(issue_id, "in_progress")
        assert result is True

    def test_invalid_status(self):
        issue_id = storage.add_issue("STEVE", "無効ステータステスト")
        result = storage.update_issue_status(issue_id, "invalid_status")
        assert result is False


class TestCommLogs:
    """エージェント間通信ログ"""

    def test_log_and_get_comm(self):
        storage.log_agent_comm("SAKAMOTO", "STEVE", "instruction", "テスト指示")
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        logs = storage.get_comm_logs(date=today)
        assert any(
            log["from"] == "SAKAMOTO" and "テスト指示" in log["content"]
            for log in logs
        )
