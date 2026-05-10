# 🤖 ケンタエージェント セットアップガイド

Telegramから指示 → AIがバックグラウンドで調査・実行 → Telegramに結果返信

---

## アーキテクチャ

```
[スマホ Telegram]
       ↓↑
[Telegram Bot API]
       ↓↑
[main.py - ボットハンドラ]
       ↓
[agent.py - Claude claude-sonnet-4-20250514 + tool_use]
       ↓
[tools.py - 株価/検索/天気/メモ/タスク]
       ↓↑
[scheduler.py - 朝7時・夜23時 自動レポート]
```

---

## セットアップ手順

### Step 1: Telegram Bot作成（5分）

1. Telegramで `@BotFather` を開く
2. `/newbot` を送信
3. Bot名とユーザー名を設定
4. **Token** をコピー（`123456:ABC-DEF...` 形式）

### Step 2: 自分のUser ID確認

1. Telegramで `@userinfobot` を開く
2. `/start` を送信
3. **User ID** をコピー（数字のみ）

### Step 3: APIキー取得

- Anthropic: https://console.anthropic.com → API Keys

### Step 4: インストール（WSL2 / Ubuntu）

```bash
# プロジェクトフォルダに移動
cd ~/kenta-agent

# 仮想環境作成（推奨）
python3 -m venv venv
source venv/bin/activate

# 依存ライブラリインストール
pip install -r requirements.txt

# 設定ファイル作成
cp .env.example .env
nano .env   # 各値を入力・保存
```

### Step 5: 起動

```bash
# 通常起動
python main.py

# バックグラウンド起動（ターミナル閉じても動く）
nohup python main.py > agent.log 2>&1 &

# ログ確認
tail -f agent.log

# プロセス確認・停止
ps aux | grep main.py
kill <PID>
```

---

## 使い方（Telegramから）

### 自然言語で何でも聞ける

```
「NVDAとMSFTとCEGの株価を教えて」
「GEVについて最新ニュースを調べて」
「ポートフォリオ全体の状況をまとめて」
「USD/JPY為替と主要指数を確認して」
「明日までにやること: 〇〇をタスク追加して」
「今週のメモを見せて」
「今日の東京の天気は？」
```

### コマンド

| コマンド | 説明 |
|---------|------|
| /morning | 朝レポートを今すぐ実行 |
| /portfolio | 全保有銘柄の株価一括確認 |
| /tasks | 未完了タスク一覧 |
| /notes | 最近のメモ一覧 |
| /clear | 会話履歴リセット |
| /status | 定期タスクのスケジュール確認 |

### 自動レポート（毎日自動送信）

- **平日朝7:00** — 朝の市況レポート（指数・為替・ポートフォリオ・天気）
- **平日夜23:00** — NY市場チェック（主要指数・重点銘柄）

---

## ファイル構成

```
kenta-agent/
├── main.py          # Telegramボット本体
├── agent.py         # Claudeエージェント + ツール定義
├── tools.py         # ツール実装（株価/検索/天気/DB）
├── scheduler.py     # 定期実行タスク
├── config.py        # 設定（ポートフォリオ銘柄等）
├── requirements.txt
├── .env             # APIキー（要作成）
├── .env.example     # テンプレート
└── agent_memory.db  # メモ・タスクDB（自動生成）
```

---

## カスタマイズ

### ポートフォリオ銘柄変更
`config.py` の `MY_PORTFOLIO` を編集

### レポート時刻変更
`config.py` の `MORNING_REPORT_HOUR` 等を変更

### レポート内容変更
`scheduler.py` の `_morning_report_prompt()` を編集

---

## トラブルシューティング

**ボットが応答しない**
```bash
# ログを確認
tail -f agent.log

# プロセスが動いているか確認
ps aux | grep main.py
```

**株価が取得できない**
- `yfinance` の制限（短時間に大量リクエスト）の可能性
- 少し待ってから再試行

**Anthropic APIエラー**
- `.env` の `ANTHROPIC_API_KEY` を確認
- https://console.anthropic.com でクレジット残高確認
