# LESSONS.md - エージェント学習記録

けんたから修正・指摘を受けた際に記録する。
セッション開始時に参照し、同じミスを繰り返さない。

---

## 記録フォーマット

```
### [日付] [エージェント名] - [ミスの概要]
**問題**: 何が起きたか
**原因**: なぜ起きたか
**対策**: 今後どうするか
```

---

## 記録

### [2026-05-11] SORA/RIO - YouTubeツールがディスパッチテーブル未登録
**問題**: `get_youtube_new_videos` を呼び出してもエラーになった
**原因**: tools.pyのdispatch dictにツールを追加し忘れた
**対策**: 新しいツールを追加するときは必ずdispatch dictへの登録を確認する

### [2026-05-11] AOI - /morningコマンドが何も返さなかった
**問題**: `/morning`を送っても返答がなかった
**原因**: main.pyのcmd_morning関数が`pass`のプレースホルダーのままだった
**対策**: コマンドを追加するときは実装まで確認する

### [2026-05-11] RIO - カレンダー日付を「明日」と誤表示
**問題**: 5/14の予定を「明日」と言ったが実際は3日後だった
**原因**: 相対的な日付表現を使ってしまった
**対策**: カレンダー日付は「5/14（水）」のように具体的な日付と曜日で表示する

### [2026-05-11] SORA - 京都の天気が出力されなかった
**問題**: 大阪の天気のみで京都が含まれなかった
**原因**: プロンプトで1つのツールしか呼ばなかった
**対策**: 複数都市の天気は必ず全都市分のツールを個別に呼び出す

---

## 継続的に注意すること

- ✅ 新ツール追加 → dispatch dict確認
- ✅ カレンダー日付 → 絶対表現（相対表現禁止）
- ✅ 複数都市天気 → 全都市分ツールを呼ぶ
- ✅ コマンド実装 → プレースホルダーのまま終わらない

### [2026-05-11] STEVE - Google Calendar invalid_scope エラー
**問題**: カレンダー取得で `invalid_scope` エラーが発生した
**原因**: `get_calendar_events` が `calendar.readonly` スコープで認証していたが、新しいトークンは `calendar`（フル）スコープで発行されていた
**対策**: Google系ツールはすべて `_get_google_creds()` を使いスコープを統一する。新しいOAuthトークン取得後は全Googleツールの動作確認を行う

### [2026-05-11] STEVE - Google Calendar invalid_scope エラー
**問題**: カレンダー取得で `invalid_scope` エラーが発生した
**原因**: `get_calendar_events` が `calendar.readonly` スコープで認証していたが、新しいトークンは `calendar`（フル）スコープで発行されていた
**対策**: Google系ツールはすべて `_get_google_creds()` を使いスコープを統一する。新しいOAuthトークン取得後は全Googleツールの動作確認を行う

---

## 開発ルール（全エージェント必読）

### コーディング後の必須チェックリスト

**① セキュリティレビュー（push前に必ず実行）**
```bash
# APIキー・トークンのハードコードチェック
grep -rn "AIzaSy\|sk-ant\|github_pat\|GOCSPX\|1//0e" --include="*.py" --include="*.md" .

# デフォルト値に機密情報がないかチェック
grep -rn 'getenv.*"[A-Za-z0-9+/]\{20,\}"' --include="*.py" .

# パスワードのハードコードチェック
grep -rn "password.*=.*\"[^\"]\+\"\|PASSWORD.*=.*\"[^\"]\+\"" --include="*.py" .
```

**② 構文チェック（push前に必ず実行）**
```bash
for f in main.py agent.py tools.py storage.py scheduler.py output.py config.py web_server.py; do
  python3 -c "import ast; ast.parse(open('$f').read()); print('✅ $f')" 2>&1
done
```

**③ 整合性チェック（新ツール追加時）**
```bash
# agent.py TOOLSリスト ↔ tools.py dispatch の整合性
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

### ハードコーディング絶対禁止ルール

- APIキー・OAuthトークン・パスワードは**コードに書かない**
- `os.getenv("KEY", "")` が正しい形。デフォルト値に実値を入れない
- 機密情報が未設定なら `sys.exit()` でエラーにする
- ドキュメント（.md）にも実際のキー・ID・パスワードを書かない
- push後にGitHubから検出されたら**即座にキーを無効化**して再発行

### 新機能追加後の動作テスト手順

1. **構文チェック** → `python3 -c "import ast; ast.parse(open('file.py').read())"`
2. **セキュリティスキャン** → 上記①のgrepコマンド実行
3. **整合性チェック** → 上記③のスクリプト実行
4. **Telegramで動作確認** → 該当機能を実際に呼び出してエラーがないか確認
5. **エラー時はLESSONS.mdに記録** → 原因・対策を残す

---

## 開発ルール（全エージェント必読）

### ハードコーディング絶対禁止ルール

- APIキー・OAuthトークン・パスワードは**コードに絶対に書かない**
- `os.getenv("KEY", "")` が正しい形。デフォルト値に実値を入れない
- 機密情報が未設定なら `sys.exit()` でエラーにする
- ドキュメント（.md）にも実際のキー・ID・パスワードを書かない
- push後にGitHubから検出されたら**即座にキーを無効化**して再発行

### コーディング後の必須チェックリスト（push前に毎回実行）

**① セキュリティスキャン**
```bash
cd ~/kagent

# APIキー・トークンのハードコードチェック
grep -rn "AIzaSy\|sk-ant\|github_pat\|GOCSPX\|1//0e" --include="*.py" --include="*.md" .

# デフォルト値に機密情報がないかチェック
grep -rn 'getenv.*"[A-Za-z0-9+/]\{20,\}"' --include="*.py" .
```
→ **何も出なければOK。1行でも出たらpush禁止**

**② 構文チェック**
```bash
for f in main.py agent.py tools.py storage.py scheduler.py output.py config.py web_server.py; do
  python3 -c "import ast; ast.parse(open('$f').read()); print('OK: $f')"
done
```
→ **全ファイルOKになるまでpush禁止**

**③ 整合性チェック（ツール追加・変更時）**
```bash
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

**④ Telegramで動作確認**
- 追加・変更した機能を実際にTelegramから呼び出す
- エラーが出たらLESSONS.mdに記録してから修正

**⑤ エラー時の記録**
- バグを修正したら必ず `agents/LESSONS.md` に「問題・原因・対策」を追記する
