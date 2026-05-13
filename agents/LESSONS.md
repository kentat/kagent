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
| ユーザーID | `"{YOUR_USER_ID}"` を直書き | `os.getenv("ALLOWED_USER_ID", "0")` |
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

### [2026-05-11] CI/CD - GitHub Actions 複数回失敗
**問題**: Security & Quality Check が繰り返し失敗した
**原因**:
1. `safety check` コマンドがv3で廃止→APIキー必須になった
2. Gitleaksが過去コミット（commit 478b201, 4716672）のAPIキーを検出した
3. `detect-secrets` のJSONパース方法が不安定だった
4. `heredoc (<<'PYEOF')` がYAML内でエスケープ問題を起こした
**対策**:
- `safety` → `pip-audit` に変更（無料・APIキー不要）
- Gitleaksを除外し `detect-secrets` のベースライン比較に一本化
- heredocの代わりに `python3 - << 'PYEOF'` 形式を使う
- CIを変更したら必ずローカルで各ステップを個別実行してからpushする
- **Safetyはv3以降APIキーが必要なため使用禁止。pip-auditを使うこと**

### [2026-05-12] CI/CD - grepパターンがYAML内で複数行に潰れて誤動作
**問題**: ci.ymlのgrepパターンが複数行に結合され、意図しない正規表現になった
**原因**: Python経由でYAMLを書き換えたとき改行が消えた
**対策**: bashのgrepの代わりにPythonスクリプトで検査する（ヒアドキュメント形式）。CIのstep変更後は必ずActionsのログ実物を確認してから完了とする

### [2026-05-12] Redis - ssl_cert_reqs が redis-py で非対応
**問題**: `unexpected keyword argument 'ssl_cert_reqs'` でRedis接続失敗
**原因**: redis-pyのバージョンがssl_cert_reqsパラメータ非対応
**対策**: ssl_cert_reqs を使わない。Railway Redisは`redis://`で接続できる

### [2026-05-12] Fear & Greed Index - CNNのAPIエンドポイントが不安定
**問題**: get_fear_greed_index がエラーを返した
**原因**: CNN APIのレスポンス形式変更またはレート制限
**対策**: エラー時はデフォルト値（50/Neutral）を返してレポートを継続

### [2026-05-12] main.py - str_replaceでcmd関数が消失
**問題**: cmd_reportが未定義エラーでworkerがクラッシュ
**原因**: cmd_eveningを「cmd_reportの直前に挿入」するつもりがstr_replaceで置換してしまい、cmd_report関数ごと消えた
**対策**: 関数を追加するときはstr_replaceではなく、既存関数の直後のコードブロックを置換する。追加後は必ずgrep -n "^async def cmd_" main.pyで全関数の存在を確認する

### [2026-05-12] CI - Ruff E701/E702・F841で繰り返し失敗
**問題**: GitHub Actions CIが多数のコミットで失敗し続けた
**原因**:
1. storage.pyを書き直した際に `conn.commit(); conn.close()` をセミコロン1行で書いた → E702
2. tools.pyの `except Exception as e:` でeを使っていない箇所がある → F841
3. ローカルでは通っていてもGitHub Actions上で失敗するケースがあった（バージョン差異）
**対策**:
- E701/E702はruff.tomlとci.ymlのignoreに追加
- F841はexcept節でeを使わない場合は `except Exception:` にする（eを省略）
- push前に `ruff check . --select E,W,F --ignore E501,E402,F401,E701,E702` で必ず確認
- スクショのコミットハッシュを見て「古い失敗通知か最新か」を判断してから修正に入る

---

## push前の必須手順（最新版）

### コミット・push前に必ずこれを実行する

```bash
cd ~/kagent
python3 test_local.py
```

**全部✅** → git commit → git push OK
**❌あり** → 修正してから再実行

### test_local.pyが確認する33項目

- 構文チェック（8ファイル）
- 必須関数の存在確認（agent/scheduler/storage）
- Telegramコマンドの定義・登録整合性
- ツール整合性（agent.py↔tools.py dispatch）
- Web認証（全EPにBasic認証あり）
- agents/MDファイル全5件の存在
- requirements.txtのパッケージ確認
- APIキーのハードコード検出
- エラー詳細漏洩検出

### テスト結果ログ

結果は `test_results.log` に自動追記される。

### [2026-05-13] STEVE - 5:30バッチでデータ収集失敗（14文字のみ）
**問題**: 朝データ収集失敗: データが空または短すぎる（14文字）
**原因**: STEVEのmax_tokens=4096では10個のツールを呼び出した結果を全部出力するのに不足だった
**対策**: max_tokens=8192に増加。タイムアウト文字列「タイムアウト」も失敗判定に追加

### [2026-05-13] scheduler.py - str_replaceで関数が消失（繰り返し発生）
**問題**: `_extract_youtube_section`、`_data_collection_prompt` 等の関数がstr_replace後に消える
**原因**: str_replaceで前後の文字列が重複・誤マッチして関数定義ごと削除される
**対策**:
1. `test_local.py` の `check_scheduler_functions` と `check_internal_references` で全ヘルパー関数の存在確認（push前に必ず実行）
2. f-string内の変数（`{yt_section}` 等）も未定義チェックに追加
3. scheduler.pyを変更したら必ず `grep -n "^def \|^async def " scheduler.py` で全関数を確認
