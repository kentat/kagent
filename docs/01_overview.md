# ケンタエージェント - プロジェクト概要

## コンセプト

スマホ（Telegram）から自然言語で指示 → AIがバックグラウンドで調査・実行 → スマホで結果確認

個人秘書AIエージェント。情報収集・投資管理・タスク管理・定期レポートを一元化する。

---

## システム構成

```
[スマホ: Telegram]
       ↕
[Telegram Bot API]（無料）
       ↕
[Railway: Python プロセス]（$5〜/月・24時間稼働）
       ↕
[Claude API: claude-sonnet-4-20250514]（従量課金）
       +
[Tools: 株価 / 検索 / 天気 / SQLite]（ほぼ無料）
```

---

## 主な機能

| 機能 | 説明 | 使用ツール |
|------|------|-----------|
| 株価確認 | 保有・監視銘柄の現在値・騰落率 | yfinance |
| 為替レート | USD/JPY等 | yfinance |
| 主要指数 | S&P500, NASDAQ, 日経225 | yfinance |
| Web検索 | 企業ニュース・経済動向 | DuckDuckGo API |
| 天気 | 東京の天気・気温 | wttr.in |
| メモ保存 | 情報をローカルDBに永続保存 | SQLite |
| タスク管理 | タスクの追加・完了管理 | SQLite |
| 朝レポート | 平日7時に市況・天気・タスクを自動送信 | APScheduler |
| 夜間チェック | 平日23時にNY市場状況を自動送信 | APScheduler |

---

## ポートフォリオ設定（config.py）

```python
MY_PORTFOLIO = {
    "holdings": ["GEV", "NVDA", "MSFT", "CEG", "DELL", "CRDO", "ITA", "VYM", "JEPI"],
    "watchlist": ["MU", "AMD"],
}
```

---

## コスト試算（月額）

| 項目 | 費用 |
|------|------|
| Railway Hobby | $5.00 |
| Railway Volume | $0.25〜 |
| Claude API | $2〜5 |
| その他API | 無料 |
| **合計** | **$7〜10（約1,000〜1,500円）** |
