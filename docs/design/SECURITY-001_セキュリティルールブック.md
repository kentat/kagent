# セキュリティルールブック

**文書番号**: SECURITY-001  
**バージョン**: 1.0  
**作成日**: 2026-05-11  
**適用範囲**: Kenta Agent Companyの全コード・ドキュメント

---

## 第1条：絶対禁止事項（コードレビュー必須）

### 1-1. シークレット情報のハードコード禁止

以下は**コードに直接書いてはいけない**：

| 種類 | 例 |
|------|-----|
| APIキー | `sk-ant-...`, `AIzaSy...` |
| OAuthトークン | `1//0e...`, `GOCSPX-...` |
| パスワード | `kenta2026`, `admin123` |
| BOTトークン | `{BOT_TOKEN}...` |
| GitHubトークン | `github_pat_...` |
| ユーザーID | `{YOUR_USER_ID}` |

**✅ 正しい書き方:**
```python
# 環境変数から取得。デフォルト値は空文字（機密情報はデフォルト禁止）
API_KEY = os.getenv("API_KEY", "")

# 未設定の場合は起動エラー（デフォルト動作させない）
if not API_KEY:
    sys.exit("ERROR: API_KEY が設定されていません")
```

**❌ 禁止:**
```python
# デフォルト値に実際の値を書く
PASSWORD = os.getenv("PASSWORD", "kenta2026")  # ❌ 禁止

# 直接書く
API_KEY = "AIzaSyAc7C1UQ..."  # ❌ 禁止
```

---

### 1-2. ドキュメントへの機密情報記載禁止

Markdownファイル（`.md`）にも以下は記載しない：
- 実際のAPIキー・トークン
- 実際のユーザーID・メールアドレス
- 実際のパスワード

**✅ 代わりに:**
```
# 良い例
KEY: conversation:{user_id}     ← プレースホルダー
GOOGLE_REFRESH_TOKEN=1//...     ← 例示は最初の数文字のみ
```

---

### 1-3. エラー詳細のユーザー公開禁止

エラーの詳細（`str(e)`）をユーザー向けメッセージに含めない。

**✅ 正しい書き方:**
```python
try:
    result = do_something()
except Exception as e:
    logger.error(f"詳細エラー: {e}", exc_info=True)  # ログには詳細を記録
    await bot.send_message(chat_id, "⚠️ エラーが発生しました")  # ユーザーには汎用メッセージ
```

**❌ 禁止:**
```python
await bot.send_message(chat_id, f"⚠️ エラー: {str(e)}")  # 内部情報が漏れる
```

---

### 1-4. 認証なしエンドポイントの禁止

Webサーバーのすべてのエンドポイントに認証をかける。

**✅ 正しい:**
```python
@app.get("/health")
def health(username: str = Depends(verify_credentials)):  # 認証必須
    return {"status": "ok"}
```

**❌ 禁止:**
```python
@app.get("/health")
def health():  # 認証なし → サーバー情報が漏れる
    return {"status": "ok", "service": "kenta-agent", "version": "1.0"}
```

---

## 第2条：環境変数の管理ルール

### 2-1. 設定場所

| 環境 | 設定場所 |
|------|---------|
| 本番（Railway）| Railway Variables |
| ローカル開発 | `.env`ファイル（`.gitignore`に追加済み）|
| テスト | 環境変数のみ（コードに書かない）|

### 2-2. `.env.example` の管理

`.env.example` には**キー名のみ**記載し、値は空にする：

```bash
# .env.example（値は書かない）
TELEGRAM_TOKEN=
ANTHROPIC_API_KEY=
WEB_USERNAME=
WEB_PASSWORD=
```

### 2-3. デフォルト値のルール

```python
# ✅ 機密情報のデフォルトは空文字
SECRET = os.getenv("SECRET", "")

# ✅ 未設定時は起動エラー
if not SECRET:
    sys.exit("ERROR: SECRET が未設定")

# ✅ 非機密情報（ポート番号など）はデフォルトOK
PORT = int(os.getenv("PORT", "8000"))
```

---

## 第3条：GitHubへのpush前チェックリスト

コードをpushする前に必ず確認：

```
□ APIキー・トークンが含まれていないか
□ パスワードのデフォルト値が設定されていないか
□ ユーザーID・メールアドレスがハードコードされていないか
□ エラーメッセージにstr(e)が含まれていないか
□ 認証なしのエンドポイントがないか
□ .envファイルがgit addされていないか
```

**自動チェックコマンド:**
```bash
# push前に実行
cd ~/kagent
grep -rn "GOCSPX\|sk-ant\|AIzaSy\|github_pat\|8609780\|8517618" --include="*.py" --include="*.md" .
```

---

## 第4条：セキュリティインシデント対応

APIキーやトークンがGitHubにpushされた場合：

1. **即座に**該当のAPIキーを無効化（各サービスのコンソールで）
2. 新しいAPIキーを発行
3. Railway Variablesを更新
4. Gitの履歴から削除（`git filter-branch` または `BFG Repo Cleaner`）

---

## 発見済みの問題と対応履歴

| 日付 | 問題 | 対応 |
|------|------|------|
| 2026-05-11 | `web_server.py` にデフォルトパスワード `kenta2026` がハードコード | 削除・起動時チェックに変更 |
| 2026-05-11 | `/health` エンドポイントが認証なし | 認証を追加 |
| 2026-05-11 | `str(e)` がTelegramに送信されていた | 汎用メッセージに変更 |
| 2026-05-11 | `DESIGN-004.md` にユーザーIDが記載 | プレースホルダーに変更 |
| 以前 | YouTube APIキーが `config.py` にハードコード | Railway Variables に移動済み |

---

## 改訂履歴

| 日付 | バージョン | 変更内容 |
|------|-----------|---------|
| 2026-05-11 | 1.0 | 初版作成（セキュリティ監査結果に基づく）|
