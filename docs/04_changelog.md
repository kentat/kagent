# 変更履歴・開発ログ

プロジェクトの進捗・変更内容をここに記録する。

---

## [Unreleased] - 開発中

### 追加予定
- [ ] Railway Volume によるSQLite永続化対応
- [ ] Tavily API による高精度Web検索
- [ ] 株価アラート機能
- [ ] Gmail 連携
- [ ] Google Calendar 連携

---

## [0.1.0] - 2026-05-10

### 追加
- Telegram Bot 基本機能（自然言語メッセージ対応）
- Claude claude-sonnet-4-20250514 + tool_use によるエージェントループ
- 12種のツール実装（株価・指数・為替・検索・天気・メモ・タスク）
- 平日7時 朝レポート自動送信
- 平日23時 NY市場チェック自動送信
- SQLite によるメモ・タスク管理
- Telegramコマンド: /start /help /clear /morning /portfolio /tasks /notes /status
- Railway デプロイ用設定（Procfile, runtime.txt）
- GitHub Private リポジトリ管理体制

### 設計判断
- デプロイ先: Railway（GitHub連携・自動デプロイ）
- DB: SQLite + Railway Volume（将来PostgreSQLへ移行検討）
- 検索: DuckDuckGo API（無料・APIキー不要）
