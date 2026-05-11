# LESSONS.md - エージェント学習記録・開発ルール

全エージェントはセッション開始時に必ずこのファイルを読み込む。
同じミスを繰り返さない。ルールを守る。

---

## ═══ 開発ルール（push前に毎回実行） ═══

### 自動チェック体制（設定済み）

```
git commit → pre-commit が自動実行（ローカル）
    ├─ ① 構文チェック（check-ast）
    ├─ ② シークレット検出（detect-secrets）
    ├─ ③ セキュリティスキャン（bandit）
    └─ ④ コード品質（ruff）

git push → GitHub Actions が自動実行（クラウド）
    ├─ Job1: Gitleaks（Git履歴全体のシークレットスキャン）
    ├─ Job2: bandit + Safety（依存ライブラリの脆弱性）
    ├─ Job3: 構文・整合性・認証チェック
    └─ Job4: ハードコーディング・エラー漏洩チェック
```

**初回セットアップ（Ubuntu/WSL2で1回だけ）:**
```bash
cd ~/kagent && bash setup-dev.sh
```

### 手動チェック（必要な場合）

### ① セキュリティスキャン（ハードコード禁止）

```bash
cd ~/kagent

# APIキー・トークンのハードコードチェック
grep -rn "AIzaSy\|sk-ant\|github_pat\|GOCSPX\|1//0e\|:AAH" --include="*.py" --include="*.md" .

# デフォルト値に長い文字列（機密情報）がないかチェック
grep -rn 'getenv.*"[A-Za-z0-9+/]\{20,\}"' --include="*.py" .

# パスワードのハードコードチェック
grep -rn "password\s*=\s*['\"][^'\"]\{4,\}['\"]" --include="*.py" . | grep -iv "os.getenv\|#"

# エラー詳細がユーザーに送信されていないかチェック
grep -rn 'send_message.*str(e)\|reply_text.*str(e)' --include="*.py" .

# 認証なしWebエンドポイントがないかチェック
grep -n "@app.get\|@app.post" web_server.py
```
→ **何も出なければOK。1行でも出たらpush禁止・即修正**

### ② 構文チェック

```bash
cd ~/kagent
for f in main.py agent.py tools.py storage.py scheduler.py output.py config.py web_server.py; do
  [ -f "$f" ] && python3 -c "import ast; ast.parse(open('$f').read()); print('✅ $f')"
done
```
→ **全ファイル✅になるまでpush禁止**

### ③ 整合性チェック（ツール追加・変更時）

```bash
cd ~/kagent
python3 << 'PYEOF'
import re
with open("agent.py") as f: agent_tools = set(re.findall(r'"name":\s*"([^"]+)"', f.read()))
with open("tools.py") as f:
    src = f.read()
    m = re.search(r'dispatch\s*=\s*\{([^}]+)\}', src, re.DOTALL)
    dispatched = set(re.findall(r'"([^"]+)":\s*\w+', m.group(1))) if m else set()
missing = agent_tools - dispatched
print(f"❌ dispatch未登録: {missing}" if missing else "✅ 整合性OK")
PYEOF
```
→ **❌が出たらdispatchに追加してからpush**

### ④ Telegram動作確認

- 追加・変更した機能を実際にTelegramから呼び出す
- エラーが出たら⑤に記録してから修正・再push

### ⑤ バグ修正時はこのファイルに記録

問題・原因・対策を「バグ記録」セクションに追記する

---

## ═══ ハードコーディング禁止ルール ═══

| 種類 | 禁止 | 正しい書き方 |
|------|------|------------|
| APIキー | `"AIzaSy..."` を直書き | `os.getenv("YOUTUBE_API_KEY", "")` |
| パスワード | `getenv("PW", "kenta2026")` | `getenv("PW", "")` + 未設定時はsys.exit() |
| ユーザーID | `"8609780798"` を直書き | `os.getenv("ALLOWED_USER_ID", "0")` |
| .mdファイル | 実際のキー・IDを記載 | `{user_id}` などプレースホルダーを使う |

**インシデント発生時:**
1. GitHub検出 → **即座にキーを無効化**（各サービスのコンソールで）
2. 新しいキーを発行 → Railway Variablesを更新
3. このファイルに記録

---

## ═══ 継続的注意事項 ═══

- 新ツール追加 → dispatch dictへの登録を必ず確認（チェック③）
- カレンダー日付 → `5/14（水）13:30〜` の形式。「明日」「来週」等の相対表現禁止
- 複数都市の天気 → 全都市分のツールを個別に呼び出す
- コマンド追加 → プレースホルダー（pass）のまま終わらない・動作確認まで行う
- Google系ツール → すべて `_get_google_creds()` を使いスコープを統一する
- エラーメッセージ → `str(e)` をユーザーに送信しない。ログのみ詳細を残す
- Webエンドポイント → /healthを含む全エンドポイントにBasic認証をかける

---

## ═══ バグ記録 ═══

### [2026-05-11] STEVE/JOHNNY - YouTubeツールがdispatch未登録
**問題**: `get_youtube_new_videos` を呼び出してもエラーになった
**原因**: tools.pyのdispatch dictにツールを追加し忘れた
**対策**: 新しいツールを追加するときは必ずdispatch dictへの登録を確認する（チェック③）

### [2026-05-11] 坂本 - /morningコマンドが何も返さなかった
**問題**: `/morning`を送っても返答がなかった
**原因**: cmd_morning関数が`pass`のプレースホルダーのままだった
**対策**: コマンドを追加するときは実装まで確認し、Telegramで動作確認する（チェック④）

### [2026-05-11] JOHNNY - カレンダー日付を「明日」と誤表示
**問題**: 5/14の予定を「明日」と表示したが実際は3日後だった
**原因**: 相対的な日付表現を使ってしまった
**対策**: カレンダー日付は「5/14（水）」のように具体的な日付と曜日で表示する

### [2026-05-11] STEVE - 京都の天気が出力されなかった
**問題**: 大阪の天気のみで京都が含まれなかった
**原因**: プロンプトで1つのツールしか呼ばなかった
**対策**: 複数都市の天気は必ず全都市分のツールを個別に呼び出す

### [2026-05-11] web_server.py - セキュリティ問題
**問題**: デフォルトパスワード・認証なしエンドポイント・エラー詳細漏洩
**原因**: セキュリティレビューなしでコーディングした
**対策**: push前に必ずチェック①を実行する

### [2026-05-11] STEVE - Google Calendar invalid_scope エラー
**問題**: カレンダー取得で `invalid_scope` エラーが発生した
**原因**: `get_calendar_events` が `calendar.readonly` スコープで認証していたが、新しいトークンは `calendar`（フル）スコープで発行されていた
**対策**: Google系ツールはすべて `_get_google_creds()` を使いスコープを統一する。新しいOAuthトークン取得後は全Googleツールの動作確認を行う（チェック④）
