# システムアーキテクチャ概要

**文書番号**: DESIGN-001  
**バージョン**: 1.0  
**作成日**: 2026-05-11  
**対象システム**: Kenta Agent（パーソナルAI秘書）

---

## 1. システム概要

### 目的
けんたの生活・投資・仕事をAIの力で最大限サポートする
パーソナルAI秘書システム。

### コアコンセプト
> 「1人に1人の秘書がいるだけで人生が変わる」をAIで実現する

### 主要機能
| 機能 | 説明 |
|------|------|
| 自然言語対話 | Telegramから日本語で指示・質問 |
| 投資管理 | 23銘柄のポートフォリオ損益リアルタイム管理 |
| 情報収集 | 株価・市況・ニュース・AI動向の自動収集 |
| 生活支援 | 天気・交通・カレンダー・タスク管理 |
| 自動レポート | 平日朝7時・夜23時の定期レポート配信 |

---

## 2. 全体構成図

```
【外部インターフェース】
スマートフォン（Telegram）
        ↕ Telegram Bot API
        
【クラウド実行環境】Railway（24時間稼働・US West）
┌─────────────────────────────────────┐
│  main.py（Telegramボットハンドラ）  │
│  scheduler.py（定期タスク管理）     │
│         ↓                           │
│  ┌─────────────────────────────┐   │
│  │     agent.py                │   │
│  │  ┌──────────────────────┐  │   │
│  │  │ AOI（秘書エージェント）│  │   │
│  │  └──────────┬───────────┘  │   │
│  │             ↓               │   │
│  │  ┌──────────────────────┐  │   │
│  │  │SORA（分析エージェント）│  │   │
│  │  │  tools.py経由でAPI    │  │   │
│  │  └──────────┬───────────┘  │   │
│  │             ↓               │   │
│  │  ┌──────────────────────┐  │   │
│  │  │ RIO（デザインエージェント）│ │   │
│  │  └──────────────────────┘  │   │
│  └─────────────────────────────┘   │
│                                     │
│  storage.py（状態管理抽象レイヤー） │
│  SQLite DB（→Redis移行予定）       │
└─────────────────────────────────────┘

【外部APIサービス】
├── Anthropic API（Claude claude-sonnet-4-20250514）
├── Yahoo Finance（yfinance）株価・為替
├── wttr.in 天気情報
├── YouTube Data API v3 チャンネルID取得
├── YouTube RSS フィード 新着動画
├── Google Calendar API 予定取得
├── CNN Fear & Greed API 市場心理
├── Hacker News API テックニュース
└── DuckDuckGo API Web検索

【コード管理】GitHub（kentat/kagent, Private）
```

---

## 3. 技術スタック

| レイヤー | 技術 | バージョン | 用途 |
|---------|------|-----------|------|
| 実行環境 | Python | 3.11 | メイン言語 |
| クラウド | Railway | Hobby | 24時間稼働 |
| ボット | python-telegram-bot | 21.6 | Telegram連携 |
| AI | Anthropic Claude | claude-sonnet-4-20250514 | エージェントエンジン |
| スケジューラ | APScheduler | 3.x | 定期実行 |
| 株価データ | yfinance | 0.2.x | 市場データ |
| 状態管理（現在） | SQLite | - | データ永続化 |
| 状態管理（将来） | Redis | - | 移行予定 |
| バージョン管理 | GitHub | - | コード・設計書管理 |

---

## 4. ファイル構成

```
kagent/
├── main.py              # Telegramボット・コマンドハンドラ
├── agent.py             # 3エージェント実装（AOI/SORA/RIO）
├── tools.py             # ツール実装（19種類）
├── storage.py           # 状態管理抽象レイヤー（Redis移行対応）
├── scheduler.py         # 定期タスク（朝7時・夜23時）
├── config.py            # 設定（ポートフォリオ・APIキー参照）
├── requirements.txt     # 依存ライブラリ
├── Procfile             # Railway起動コマンド
├── runtime.txt          # Pythonバージョン指定
│
├── agents/              # エージェント定義（会社のルール）
│   ├── COMPANY.md       # 就業規則（全員共通）
│   ├── AOI.md           # 秘書エージェント職務定義書
│   ├── SORA.md          # 分析エージェント職務定義書
│   ├── RIO.md           # デザインエージェント職務定義書
│   └── LESSONS.md       # 学習記録（ミスと改善）
│
└── docs/                # ドキュメント
    ├── design/          # 設計書・仕様書（本フォルダ）
    │   ├── DESIGN-001_アーキテクチャ概要.md（本文書）
    │   ├── DESIGN-002_マルチエージェント設計哲学.md
    │   ├── DESIGN-003_エージェント定義仕様.md
    │   ├── DESIGN-004_ストレージ設計とRedis移行計画.md
    │   └── DESIGN-005_ロードマップ.md
    └── 01_overview.md   # プロジェクト概要（既存）
```

---

## 5. 環境変数一覧

| 変数名 | 用途 | 設定場所 |
|--------|------|---------|
| `TELEGRAM_TOKEN` | Telegram Bot認証 | Railway Variables |
| `ANTHROPIC_API_KEY` | Claude API認証 | Railway Variables |
| `ALLOWED_USER_ID` | アクセス制限（ユーザーID） | Railway Variables |
| `DB_PATH` | SQLiteファイルパス | Railway Variables |
| `YOUTUBE_API_KEY` | YouTube Data API v3 | Railway Variables |
| `GOOGLE_CLIENT_ID` | Google OAuth認証 | Railway Variables |
| `GOOGLE_CLIENT_SECRET` | Google OAuth認証 | Railway Variables |
| `GOOGLE_REFRESH_TOKEN` | Google APIアクセス | Railway Variables |
| `REDIS_URL` | Redis接続URL（将来） | Railway Variables（未設定） |

---

## 更新履歴

| 日付 | バージョン | 変更内容 |
|------|-----------|---------|
| 2026-05-11 | 1.0 | 初版作成 |
