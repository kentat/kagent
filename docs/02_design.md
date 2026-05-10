# 設計判断ログ

このファイルはプロジェクトで下した設計判断とその理由を記録する。
「なぜこの選択をしたか」を後から振り返れるようにする。

---

## 通信レイヤー: Telegram Bot

**決定:** Telegram Bot API を使用

**理由:**
- すでにOpenClaw連携で慣れている環境
- APIキー不要でBotFatherからすぐ取得可能
- メッセージ・コマンド・ファイル送受信が標準対応
- 将来的にグループチャット・ボタンUIへの拡張が容易

**却下した選択肢:** LINE Bot（日本向けだが開発者向け機能がやや制限的）

---

## AIエンジン: Claude claude-sonnet-4-20250514

**決定:** Anthropic Claude API (claude-sonnet-4-20250514) + tool_use

**理由:**
- tool_useによる複数ツールの連鎖実行が得意
- 日本語の品質が高い
- コンテキスト管理（会話履歴）が扱いやすい

---

## クラウド実行環境: Railway

**決定:** Railway Hobby プラン

**理由:**
- GitHubと連携した自動デプロイ（push → 即反映）
- 長時間稼働プロセス（Telegramポーリング）に対応
- 上限額設定ができる（想定外課金の防止）
- Vercelは常駐プロセスに不向きなため却下

---

## データ永続化: SQLite + Railway Volume

**決定:** SQLite を Railway Volume にマウントして使用

**理由:**
- Railwayのデフォルトファイルシステムはデプロイごとにリセット
- Volumeを追加することで `/data` パスにSQLiteファイルを永続保存できる
- PostgreSQLへの移行はコードの書き換えコストが高いため現時点では見送り

**将来の移行先:** 利用規模が大きくなったらPostgreSQLに移行検討

**config.py での設定:**
```python
# Railway Volume マウントパス
DB_PATH = os.getenv("DB_PATH", "./agent_memory.db")
# Railway では /data/agent_memory.db を環境変数に設定
```

---

## デプロイ方式: GitHub連携

**決定:** GitHub Private リポジトリ → Railway 自動デプロイ

**フロー:**
```
ローカル編集 → git push → GitHub → Railway 自動ビルド → デプロイ完了
```

**理由:**
- コード変更が数分で本番反映
- ロールバックが容易（git revert）
- 設計ドキュメント・コード・履歴を一元管理

---

## セキュリティ設計

| 項目 | 対策 |
|------|------|
| APIキー | `.env` は `.gitignore` で除外、Railway環境変数で管理 |
| ボットアクセス | `ALLOWED_USER_ID` による個人限定制限 |
| リポジトリ | GitHub Private で非公開 |

---

## 未決定事項・将来検討

- [ ] Web検索の高精度化（Tavily API への切り替え）
- [ ] Gmail / Google Calendar 連携
- [ ] 株価アラート機能（閾値を下回ったら通知）
- [ ] データのバックアップ自動化
- [ ] Webhook方式への移行（現在はポーリング）
