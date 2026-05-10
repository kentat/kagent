# デプロイ手順書

## 前提条件

- GitHubアカウント
- Railwayアカウント（railway.com）
- Telegram Bot Token（@BotFather で取得）
- Anthropic API Key（console.anthropic.com）
- 自分のTelegram User ID（@userinfobot で確認）

---

## Phase 1: GitHub リポジトリ作成

```bash
# WSL2 / Ubuntu で実行

# Gitの初期設定（初回のみ）
git config --global user.name "あなたの名前"
git config --global user.email "your@email.com"

# プロジェクトフォルダに移動
cd ~/kenta-agent

# Git初期化
git init

# 全ファイルをステージング（.envは.gitignoreで除外済み）
git add .

# 初回コミット
git commit -m "feat: initial commit - kenta-agent"
```

GitHubでリポジトリ作成:
1. https://github.com/new を開く
2. Repository name: `kenta-agent`
3. **Private** を選択
4. 「Create repository」をクリック

```bash
# GitHub と紐付け（URLは自分のものに変更）
git remote add origin https://github.com/YOUR_USERNAME/kenta-agent.git
git branch -M main
git push -u origin main
```

---

## Phase 2: Railway セットアップ

1. https://railway.com にアクセス
2. 「Login with GitHub」でログイン
3. 「New Project」→「Deploy from GitHub repo」
4. `kenta-agent` を選択

### Volume（永続ストレージ）の追加

1. プロジェクト画面で「+ New」→「Volume」
2. Mount Path: `/data`
3. 作成後、Serviceの設定から Volume をアタッチ

### 環境変数の設定

プロジェクト → Variables → 以下を追加:

| 変数名 | 値 |
|--------|-----|
| `TELEGRAM_TOKEN` | BotFatherから取得したToken |
| `ANTHROPIC_API_KEY` | Anthropicのコンソールから取得 |
| `ALLOWED_USER_ID` | 自分のTelegram User ID（数字） |
| `DB_PATH` | `/data/agent_memory.db` |

### コスト上限の設定

Settings → Usage Limits → 月額上限を $15 程度に設定（推奨）

---

## Phase 3: デプロイ確認

1. Railway ダッシュボードでビルドログを確認
2. `Successfully deployed` が出たら完了
3. Telegram で `/start` を送って動作確認
4. 「NVDAの株価を教えて」と送って返答を確認

---

## 日常的なコード更新フロー

```bash
# コードを修正したら
git add .
git commit -m "fix: 修正内容のメモ"
git push

# → Railway が自動でビルド・デプロイ（約2〜3分）
```

---

## トラブルシューティング

### ボットが応答しない
```bash
# Railwayのログを確認（ダッシュボード → Logs）
# または Railway CLI:
railway logs
```

### デプロイが失敗する
- `requirements.txt` の依存ライブラリ名を確認
- Railway ダッシュボードの Build Logs でエラー箇所を特定

### データが消えた
- Volume が正しくアタッチされているか確認
- `DB_PATH` 環境変数が `/data/agent_memory.db` になっているか確認
