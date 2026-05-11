# ストレージ設計とRedis移行計画

**文書番号**: DESIGN-004  
**バージョン**: 1.0  
**作成日**: 2026-05-11

---

## 1. 設計方針

### 抽象レイヤーパターン

```
tools.py / main.py（利用側）
        ↓ 関数呼び出し
storage.py（抽象レイヤー）← ここだけ変える
        ↓ 実装
SQLite（現在）→ Redis（将来）
```

**目的**: `tools.py` や `main.py` を変更せずに、
`storage.py` の実装だけ変えることでRedisに移行できる。

---

## 2. 現在の実装（SQLite + メモリ）

### データの種類と保存場所

| データ種別 | 現在の保存場所 | 特徴 |
|-----------|--------------|------|
| 会話履歴 | Pythonメモリ（dict）| 再起動で消える |
| メモ（notes） | SQLite | 永続 |
| タスク（tasks） | SQLite | 永続 |
| YouTubeチャンネルID | SQLite | 永続・キャッシュ |

### storage.pyのインターフェース

```python
# 会話履歴
get_conversation(user_id: int) -> list
set_conversation(user_id: int, history: list) -> None
clear_conversation(user_id: int) -> None

# メモ
save_note(content: str, category: str) -> str
get_notes(category: str, limit: int) -> list

# タスク
add_task(title: str, due_date: str) -> str
get_tasks(status: str) -> list
complete_task(task_id: int) -> str

# YouTubeキャッシュ
get_channel_id(handle: str) -> str
set_channel_id(handle: str, channel_id: str) -> None
```

---

## 3. Redis移行計画

### 対応表

| データ | 現在（SQLite/Memory） | Redis移行後 |
|--------|---------------------|------------|
| 会話履歴 | `dict[user_id, list]` | `Hash: conversation:{user_id}` + TTL 24h |
| メモ | `SQLite: notes table` | `List: notes:{category}` + `Hash: note:{id}` |
| タスク | `SQLite: tasks table` | `Hash: task:{id}` + `Set: tasks:{status}` |
| チャンネルID | `SQLite: yt_channels` | `String: yt:channel:{handle}` + TTL 30日 |

### Redisデータ構造の詳細

```
# 会話履歴
KEY: conversation:{user_id}
TYPE: String (JSON)
TTL: 86400秒（24時間）
VALUE: [{"role":"user","content":"..."}, ...]

# メモ
KEY: note:seq → incrementするカウンター
KEY: note:{id} → Hash（content, category, created_at）
KEY: notes:{category} → List（note IDのリスト）

# タスク
KEY: task:seq → インクリメントカウンター
KEY: task:{id} → Hash（title, status, due_date, created_at）
KEY: tasks:pending → Set（task IDのセット）
KEY: tasks:done → Set（完了task IDのセット）

# YouTubeチャンネルID
KEY: yt:channel:{handle}
TYPE: String
TTL: 2592000秒（30日）
VALUE: "UCxxxxxxxxxxxxxxxx"
```

### 移行手順

```bash
# Step 1: Railway に Redis を追加
# Railway Dashboard → New → Database → Redis → Add

# Step 2: 環境変数を追加
# REDIS_URL=redis://default:password@host:port/0

# Step 3: storage.py のインポートを変更
# pip install redis

# Step 4: storage.py の実装を Redis に切り替え
# ← 関数シグネチャは変えない（互換性維持）
```

### Redisへの移行後のstorage.py（参考実装）

```python
import redis
import json
import os

_redis = None

def _get_redis():
    global _redis
    if _redis is None:
        _redis = redis.from_url(os.getenv("REDIS_URL"))
    return _redis

def get_conversation(user_id: int) -> list:
    """Redis移行後の実装"""
    r = _get_redis()
    data = r.get(f"conversation:{user_id}")
    return json.loads(data) if data else []

def set_conversation(user_id: int, history: list) -> None:
    """Redis移行後の実装"""
    r = _get_redis()
    r.setex(
        f"conversation:{user_id}",
        86400,  # 24時間TTL
        json.dumps(history[-20:])
    )
```

---

## 4. コスト試算

### 現在（SQLite）
- 追加コスト: $0

### Redis移行後
- Railway Redis: $0（Hobby プランで無料枠あり）
- または Railway Redis Pro: ~$5/月
- データ量が少ないため無料枠で十分

---

## 5. 移行タイミングの判断基準

以下のどちらかに該当したら移行を検討する：

1. **会話が途切れる** → Railwayが再デプロイするたびに会話履歴が消える問題が顕在化
2. **並列処理の実装時** → 複数プロセスで状態を共有する必要が生じたとき

---

## 更新履歴

| 日付 | バージョン | 変更内容 |
|------|-----------|---------|
| 2026-05-11 | 1.0 | 初版作成 |
