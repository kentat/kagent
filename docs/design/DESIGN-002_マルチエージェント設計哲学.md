# マルチエージェント設計哲学

**文書番号**: DESIGN-002  
**バージョン**: 1.0  
**作成日**: 2026-05-11  
**参考**: 動画「AI社員に仕事を任せる方法」/ Anthropic公式 / 2026年業界標準

---

## 1. 設計哲学の根幹

### フォルダ＝会社、Markdownファイル＝就業規則

```
kagent/
└── agents/
    ├── COMPANY.md   ← 会社の憲法（全員が守るルール）
    ├── AOI.md       ← 秘書の職務定義書
    ├── SORA.md      ← 分析員の職務定義書
    └── RIO.md       ← デザイナーの職務定義書
```

AIエージェントを「AIツール」ではなく「AI社員」として扱う。
採用・教育・役割分担のすべてをMarkdownで管理する。

---

## 2. 核心原則

### 原則1：1エージェント＝1タスク

```
❌ 悪い例（万能エージェント）
  一人のAIが「データ収集して、分析して、整形して、返答して」

✅ 良い例（専門分業）
  AOI → 意図理解・タスク定義
  SORA → データ収集・分析のみ
  RIO → 整形・美化のみ
```

**理由**: 複数の役割を持たせると、どちらも中途半端になる。
専門特化させることで、各エージェントが自分の仕事に集中できる。

### 原則2：役割の境界線を明確に定義する

各エージェントの定義書には必ず：
- ✅ やること（具体的に）
- ❌ やらないこと（これが最重要）

「やらないこと」を書かないと、エージェントが越権行為をする。

### 原則3：使うほど賢くなる設計

```
LESSONS.md（学習記録）
  ← けんたから修正を受けるたびに追記
  ← 全エージェントが毎セッション参照
  ← 同じミスを繰り返さない
```

### 原則4：コードではなくMarkdownで行動を定義する

```
変更したいとき：
  Before: agent.pyのコードを直接編集 → デプロイ必要
  After:  agents/RIO.mdを編集するだけ → 即反映
```

エージェントの「人格」はコードではなくMarkdownで管理する。

---

## 3. エージェント間の通信設計

### 現在の方式（In-Process）

```python
# AOI → SORA への指示
sora_task = run_aoi(user_message)  # 文字列

# SORA → RIO へのデータ渡し
raw_data = run_sora(sora_task)      # 文字列

# RIO → ユーザーへの出力
formatted = run_rio(raw_data)       # 文字列
```

**特徴**:
- シンプル・デバッグしやすい
- 同一プロセス内なので低レイテンシ
- ただしスケールしにくい

### 将来の方式（別プロセス）

```
AOI Service (port 8001)
  POST /task → SORA Service (port 8002)
  
SORA Service (port 8002)
  POST /design → RIO Service (port 8003)
  
エージェント間通信: HTTP REST または Redis Queue
共有状態: Redis
```

---

## 4. オーケストレーションパターン

### Pattern A: 逐次処理（現在の実装）

```
AOI → SORA → RIO
所要時間: ~120秒（23銘柄の株価取得が直列）
```

### Pattern B: 並列処理（将来の改善）

```
       ┌→ SORA-株価（非同期）  ─┐
AOI →→ ├→ SORA-天気（非同期）  ─┼→ RIO → 出力
       └→ SORA-カレンダー（非同期）─┘
所要時間: ~30秒（並列実行）
```

### Pattern C: 階層型（最終形）

```
AOI（マネージャー）
  ├→ 分析チーム（SORA系、複数エージェント）
  └→ 出力チーム（RIO系、フォーマット別）
```

---

## 5. Anthropicの推奨設計パターンとの対応

| Anthropic推奨 | ケンタエージェントでの実装 |
|--------------|--------------------------|
| Orchestrator-Worker | AOI（Orchestrator）→ SORA/RIO（Workers） |
| Clear role separation | agents/*.md で役割を明確に定義 |
| Shared memory | storage.py 抽象レイヤー |
| Tool specialization | SORA のみツール使用、RIOはツールなし |
| Feedback loops | LESSONS.md で継続改善 |

---

## 6. 2026年業界標準との対応

### MCP（Model Context Protocol）対応可能性

現在の `tools.py` は将来MCPサーバーとして公開できる。

```python
# 現在
execute_tool("get_stock_price", {"ticker": "NVDA"})

# MCP対応後（将来）
@mcp.tool()
def get_stock_price(ticker: str) -> dict:
    ...
# → 外部エージェントからも呼び出し可能
```

### A2A（Agent-to-Agent Protocol）対応可能性

現在の `agents/*.md` は A2A の「Agent Card」概念に相当する。
プロセス分離時にそのまま A2A Agent Card として利用できる。

---

## 更新履歴

| 日付 | バージョン | 変更内容 |
|------|-----------|---------|
| 2026-05-11 | 1.0 | 初版作成 |
