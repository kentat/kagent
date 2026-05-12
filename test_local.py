"""
pre-push テストスクリプト
======================
pushの前に必ずこれを実行する。
結果はtest_results.log に追記される。

使い方:
    python3 test_local.py
    # 全部✅ならgit push OK
    # ❌があればpush禁止・修正してから再実行
"""

import ast
import re
import sys
import os
import importlib.util
import json
from datetime import datetime

LOG_FILE = "test_results.log"
PASS = []
FAIL = []


def log(status: str, name: str, detail: str = ""):
    icon = "✅" if status == "OK" else "❌"
    msg = f"{icon} {name}"
    if detail:
        msg += f": {detail}"
    print(msg)
    if status == "OK":
        PASS.append(name)
    else:
        FAIL.append(f"{name}: {detail}")


def check_syntax():
    """全Pythonファイルの構文チェック"""
    files = [
        "main.py", "agent.py", "tools.py", "storage.py",
        "scheduler.py", "output.py", "config.py", "web_server.py"
    ]
    for f in files:
        if not os.path.exists(f):
            log("FAIL", f"構文:{f}", "ファイルが存在しない")
            continue
        try:
            with open(f) as fp:
                ast.parse(fp.read())
            log("OK", f"構文:{f}")
        except SyntaxError as e:
            log("FAIL", f"構文:{f}", str(e))


def check_tool_integrity():
    """agent.pyのTOOLSリストとtools.pyのdispatch tableの整合性"""
    try:
        with open("agent.py") as f:
            agent_tools = set(re.findall(r'"name":\s*"([^"]+)"', f.read()))
        with open("tools.py") as f:
            src = f.read()
            m = re.search(r'dispatch\s*=\s*\{([^}]+)\}', src, re.DOTALL)
            dispatched = set(re.findall(r'"([^"]+)":\s*\w+', m.group(1))) if m else set()

        missing = agent_tools - dispatched
        if missing:
            log("FAIL", "ツール整合性", f"dispatch未登録: {missing}")
        else:
            log("OK", "ツール整合性", f"{len(agent_tools)}ツール一致")
    except Exception as e:
        log("FAIL", "ツール整合性", str(e))


def check_scheduler_functions():
    """scheduler.pyの必須関数が存在するか"""
    required = [
        "_data_collection_prompt",
        "_design_prompt",
        "_RAW_DATA_KEY",
        "_RAW_DATA_TTL",
        "collect_morning_data",
        "send_morning_report",
        "send_daily_report",
        "send_evening_report",
        "setup_scheduler",
    ]
    try:
        with open("scheduler.py") as f:
            content = f.read()
        for name in required:
            if name in content:
                log("OK", f"scheduler:{name}")
            else:
                log("FAIL", f"scheduler:{name}", "定義が見つかりません")
    except Exception as e:
        log("FAIL", "scheduler関数チェック", str(e))


def check_agent_functions():
    """agent.pyの必須関数が存在するか"""
    required = ["run_steve", "run_johnny", "run_agent", "generate_daily_report"]
    try:
        with open("agent.py") as f:
            content = f.read()
        for name in required:
            if f"def {name}" in content:
                log("OK", f"agent:{name}")
            else:
                log("FAIL", f"agent:{name}", "定義が見つかりません")
    except Exception as e:
        log("FAIL", "agent関数チェック", str(e))


def check_cmd_handlers():
    """main.pyのコマンドハンドラーが全部定義・登録されているか"""
    try:
        with open("main.py") as f:
            content = f.read()

        # 定義されているcmd_*関数
        defined = set(re.findall(r"^async def (cmd_\w+)", content, re.MULTILINE))
        # CommandHandlerに登録されているもの
        registered = set(re.findall(r'CommandHandler\("[^"]+",\s*(cmd_\w+)\)', content))

        missing_reg = defined - registered
        if missing_reg:
            log("FAIL", "コマンド登録", f"定義済みだが未登録: {missing_reg}")
        else:
            log("OK", "コマンド登録", f"{len(defined)}コマンド全登録済み")
    except Exception as e:
        log("FAIL", "コマンド登録チェック", str(e))


def check_web_auth():
    """web_server.pyの全エンドポイントに認証があるか"""
    try:
        with open("web_server.py") as f:
            src = f.read()
        pat = re.compile(
            r'@app\.(?:get|post|put|delete)\(["\']([^"\']+)["\']\)\n(?:async )?def \w+\(([^)]*\))',
            re.MULTILINE
        )
        bad = [p for p, a in pat.findall(src) if 'Depends(verify_credentials)' not in a]
        if bad:
            log("FAIL", "Web認証", f"認証なしEP: {bad}")
        else:
            log("OK", "Web認証", "全エンドポイント認証あり")
    except Exception as e:
        log("FAIL", "Web認証チェック", str(e))


def check_no_hardcoded_secrets():
    """APIキー・パスワードのハードコードがないか"""
    patterns = [
        (r"AIzaSy[A-Za-z0-9_-]{10,}", "YouTube/Google APIキー"),
        (r"sk-ant-api[A-Za-z0-9_-]+", "Anthropic APIキー"),
        (r"ghp_[A-Za-z0-9]{36,}", "GitHub PAT"),
        (r"GOCSPX-[A-Za-z0-9_-]+", "Google OAuthシークレット"),
    ]
    py_files = [
        "main.py", "agent.py", "tools.py", "storage.py",
        "scheduler.py", "output.py", "config.py", "web_server.py"
    ]
    found = []
    for f in py_files:
        try:
            with open(f) as fp:
                content = fp.read()
            for pattern, name in patterns:
                if re.search(pattern, content):
                    found.append(f"{f}: {name}")
        except Exception:
            pass

    if found:
        log("FAIL", "シークレット直書き", str(found))
    else:
        log("OK", "シークレット直書き", "なし")


def check_no_error_leakage():
    """エラー詳細がユーザーに送信されていないか"""
    try:
        found = []
        for f in ["main.py", "scheduler.py", "agent.py"]:
            with open(f) as fp:
                for i, line in enumerate(fp, 1):
                    if re.search(r'send_message.*str\(e\)|reply_text.*str\(e\)', line):
                        found.append(f"{f}:{i}")
        if found:
            log("FAIL", "エラー漏洩", str(found))
        else:
            log("OK", "エラー漏洩", "なし")
    except Exception as e:
        log("FAIL", "エラー漏洩チェック", str(e))


def check_storage_functions():
    """storage.pyの必須関数が存在するか"""
    required = [
        "get_conversation", "set_conversation", "clear_conversation",
        "save_note", "get_notes", "add_task", "get_tasks", "complete_task",
        "save_report_cache", "get_report_cache",
        "write_agent_log", "get_agent_logs",
        "log_agent_comm", "get_comm_logs",
        "add_issue", "get_issues",
    ]
    try:
        with open("storage.py") as f:
            content = f.read()
        missing = [fn for fn in required if f"def {fn}" not in content]
        if missing:
            log("FAIL", "storage関数", f"未定義: {missing}")
        else:
            log("OK", "storage関数", f"{len(required)}関数全定義済み")
    except Exception as e:
        log("FAIL", "storage関数チェック", str(e))


def check_requirements():
    """requirements.txtに必要なパッケージがあるか"""
    required = [
        "anthropic", "python-telegram-bot", "fastapi", "uvicorn",
        "redis", "apscheduler", "yfinance", "feedparser",
        "google-auth", "google-api-python-client", "youtube-transcript-api",
    ]
    try:
        with open("requirements.txt") as f:
            content = f.read().lower()
        missing = [pkg for pkg in required if pkg.lower() not in content]
        if missing:
            log("FAIL", "requirements.txt", f"不足: {missing}")
        else:
            log("OK", "requirements.txt", f"{len(required)}パッケージ確認済み")
    except Exception as e:
        log("FAIL", "requirements.txt確認", str(e))


def check_agents_md():
    """agents/ディレクトリの必須MDファイルが存在するか"""
    required = ["COMPANY.md", "SAKAMOTO.md", "STEVE.md", "JOHNNY.md", "LESSONS.md"]
    for f in required:
        path = f"agents/{f}"
        if os.path.exists(path):
            log("OK", f"agents/{f}")
        else:
            log("FAIL", f"agents/{f}", "ファイルが存在しない")


def save_log():
    """テスト結果をファイルに追記"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = len(PASS) + len(FAIL)
    with open(LOG_FILE, "a") as f:
        f.write(f"\n{'='*50}\n")
        f.write(f"テスト実行: {now}\n")
        f.write(f"結果: {len(PASS)}/{total} OK\n")
        if FAIL:
            f.write("失敗:\n")
            for item in FAIL:
                f.write(f"  ❌ {item}\n")
        else:
            f.write("全チェック通過\n")
        f.write(f"{'='*50}\n")
    print(f"\n📄 ログ保存: {LOG_FILE}")


def main():
    print(f"\n{'='*50}")
    print(f"Kenta Agent pre-push テスト")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")

    print("--- 構文チェック ---")
    check_syntax()

    print("\n--- 関数存在チェック ---")
    check_agent_functions()
    check_scheduler_functions()
    check_storage_functions()
    check_cmd_handlers()

    print("\n--- 整合性チェック ---")
    check_tool_integrity()
    check_web_auth()
    check_agents_md()
    check_requirements()

    print("\n--- セキュリティチェック ---")
    check_no_hardcoded_secrets()
    check_no_error_leakage()

    print(f"\n{'='*50}")
    print(f"結果: ✅ {len(PASS)}件OK  ❌ {len(FAIL)}件NG")
    print(f"{'='*50}")

    save_log()

    if FAIL:
        print("\n❌ 失敗があります。修正してから再実行してください。")
        sys.exit(1)
    else:
        print("\n✅ 全チェック通過。git push OK！")
        sys.exit(0)


if __name__ == "__main__":
    main()
