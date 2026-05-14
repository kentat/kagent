"""
設定画面 API & HTML
==================
GET  /settings          → 設定画面HTML
GET  /api/portfolio     → ポートフォリオ一覧JSON
POST /api/portfolio     → ポートフォリオ全体保存
GET  /api/portfolio/csv → CSVエクスポート
POST /api/portfolio/csv → CSVインポート
"""

import csv
import io
import json
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

from storage import _use_redis, _get_redis, save_report_cache, get_report_cache

router = APIRouter()

PORTFOLIO_KEY = "settings:portfolio"


# ─── データモデル ───

class Position(BaseModel):
    ticker: str
    name: str
    shares: float
    cost_jpy: float  # 平均取得価額（円）


class PortfolioData(BaseModel):
    positions: List[Position]


# ─── ストレージ ───

def load_portfolio() -> List[dict]:
    """ポートフォリオをRedis or config.pyから読み込む"""
    if _use_redis():
        data = _get_redis().get(PORTFOLIO_KEY)
        if data:
            return json.loads(data)

    # config.pyからデフォルト読み込み
    try:
        from config import MY_PORTFOLIO
        import yfinance as yf
        rate = 155.0
        try:
            t = yf.Ticker("USDJPY=X")
            h = t.history(period="1d")
            if not h.empty:
                rate = float(h["Close"].iloc[-1])
        except Exception:
            pass

        positions = []
        for ticker, pos in MY_PORTFOLIO.get("positions", {}).items():
            positions.append({
                "ticker": ticker,
                "name": pos.get("name", ticker),
                "shares": pos.get("shares", 0),
                "cost_jpy": round(pos.get("cost_usd", 0) * rate),
            })
        return positions
    except Exception:
        return []


def save_portfolio(positions: List[dict]) -> None:
    """ポートフォリオをRedisに保存"""
    if _use_redis():
        _get_redis().set(PORTFOLIO_KEY, json.dumps(positions))


# ─── ヘルパー関数（web_server.pyから呼び出す）───

def export_csv_response():
    from fastapi.responses import StreamingResponse
    positions = load_portfolio()
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["ticker", "name", "shares", "cost_jpy"])
    writer.writeheader()
    writer.writerows(positions)
    output.seek(0)
    now = datetime.now().strftime("%Y%m%d")
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=portfolio_{now}.csv"}
    )


def import_csv_data(content: bytes) -> int:
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    positions = []
    for row in reader:
        positions.append({
            "ticker": row.get("ticker", "").strip().upper(),
            "name": row.get("name", "").strip(),
            "shares": float(row.get("shares", 0)),
            "cost_jpy": float(row.get("cost_jpy", 0)),
        })
    save_portfolio(positions)
    return len(positions)


# ─── 設定画面HTML ───

def settings_html() -> str:
    return """<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  <title>設定 | Kenta Agent</title>
  <style>
    :root {
      --bg: #000; --surface: #111; --surface2: #1a1a1a;
      --border: rgba(255,255,255,0.08); --text: #f5f5f7;
      --text2: #86868b; --text3: #515154; --accent: #2997ff;
      --accent2: #30d158; --danger: #ff453a; --warn: #ff9f0a;
      --radius: 12px; --nav-h: 64px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
    body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", sans-serif; font-size: 15px; min-height: 100vh; }

    header {
      position: fixed; top: 0; left: 0; right: 0; height: 52px;
      background: rgba(0,0,0,0.85); backdrop-filter: blur(20px);
      border-bottom: 1px solid var(--border); display: flex;
      align-items: center; padding: 0 20px; z-index: 100;
    }
    .logo { font-size: 17px; font-weight: 600; }
    .logo span { color: var(--accent); }
    .updated { margin-left: auto; font-size: 12px; color: var(--text3); }

    main { max-width: 720px; margin: 0 auto; padding: 72px 16px calc(var(--nav-h) + 24px); }

    .page-title { font-size: 28px; font-weight: 700; padding: 24px 0 16px; border-bottom: 1px solid var(--border); margin-bottom: 20px; }

    .section-title {
      font-size: 13px; font-weight: 600; color: var(--text2);
      text-transform: uppercase; letter-spacing: 0.06em;
      margin: 24px 0 10px;
    }

    /* ツールバー */
    .toolbar { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
    .btn {
      padding: 8px 16px; border-radius: 20px; border: none;
      font-size: 14px; font-weight: 500; cursor: pointer; transition: opacity 0.15s;
    }
    .btn:active { opacity: 0.7; }
    .btn-primary { background: var(--accent); color: #fff; }
    .btn-success { background: var(--accent2); color: #fff; }
    .btn-danger  { background: var(--danger); color: #fff; }
    .btn-outline { background: transparent; color: var(--accent); border: 1px solid var(--accent); }

    /* テーブル */
    .table-wrap { overflow-x: auto; border-radius: var(--radius); border: 1px solid var(--border); }
    table { width: 100%; border-collapse: collapse; min-width: 560px; }
    th {
      background: var(--surface2); color: var(--text2);
      font-size: 12px; font-weight: 600; text-align: left;
      padding: 10px 12px; border-bottom: 1px solid var(--border);
    }
    td { padding: 10px 12px; border-bottom: 1px solid var(--border); font-size: 14px; }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: rgba(255,255,255,0.03); }

    input[type=text], input[type=number] {
      background: var(--surface2); color: var(--text);
      border: 1px solid var(--border); border-radius: 6px;
      padding: 5px 8px; font-size: 14px; width: 100%;
    }
    input:focus { outline: none; border-color: var(--accent); }

    .del-btn {
      background: none; border: none; color: var(--danger);
      font-size: 18px; cursor: pointer; padding: 0 4px;
    }

    /* トースト */
    #toast {
      position: fixed; bottom: calc(var(--nav-h) + 16px); left: 50%;
      transform: translateX(-50%); background: var(--accent2);
      color: #fff; padding: 10px 20px; border-radius: 20px;
      font-size: 14px; font-weight: 500; opacity: 0;
      transition: opacity 0.3s; pointer-events: none; z-index: 200;
    }
    #toast.show { opacity: 1; }
    #toast.error { background: var(--danger); }

    /* summary */
    .summary {
      background: var(--surface); border: 1px solid var(--border);
      border-radius: var(--radius); padding: 16px 20px;
      margin-bottom: 16px; display: flex; gap: 24px; flex-wrap: wrap;
    }
    .summary-item { }
    .summary-label { font-size: 12px; color: var(--text2); }
    .summary-value { font-size: 20px; font-weight: 700; color: var(--text); }
    .summary-value.pos { color: var(--accent2); }
    .summary-value.neg { color: var(--danger); }

    /* bottom nav */
    nav {
      position: fixed; bottom: 0; left: 0; right: 0;
      height: var(--nav-h); background: rgba(0,0,0,0.85);
      backdrop-filter: blur(20px); border-top: 1px solid var(--border);
      display: flex; align-items: flex-start; padding-top: 8px; z-index: 100;
    }
    .nav-item { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 3px; text-decoration: none; color: var(--text3); padding: 4px 0; }
    .nav-item.active { color: var(--accent); }
    .nav-icon { font-size: 22px; }
    .nav-label { font-size: 10px; font-weight: 500; }
  </style>
</head>
<body>
<header>
  <div class="logo">🏯 <span>Kenta</span> Agent</div>
  <div class="updated" id="rate-label">為替取得中...</div>
</header>

<main>
  <div class="page-title">⚙️ 設定</div>

  <div class="section-title">📈 ポートフォリオ</div>

  <div class="summary" id="summary" style="display:none">
    <div class="summary-item">
      <div class="summary-label">保有銘柄数</div>
      <div class="summary-value" id="s-count">-</div>
    </div>
    <div class="summary-item">
      <div class="summary-label">投資元本（円）</div>
      <div class="summary-value" id="s-cost">-</div>
    </div>
    <div class="summary-item">
      <div class="summary-label">評価額（円）</div>
      <div class="summary-value" id="s-value">-</div>
    </div>
    <div class="summary-item">
      <div class="summary-label">損益（円）</div>
      <div class="summary-value" id="s-pnl">-</div>
    </div>
    <div class="summary-item">
      <div class="summary-label">損益（%）</div>
      <div class="summary-value" id="s-pct">-</div>
    </div>
  </div>

  <div class="toolbar">
    <button class="btn btn-success" onclick="addRow()">＋ 追加</button>
    <button class="btn btn-primary" onclick="saveAll()">💾 保存</button>
    <button class="btn btn-outline" onclick="exportCSV()">📤 CSV出力</button>
    <label class="btn btn-outline" style="cursor:pointer">
      📥 CSV読込
      <input type="file" accept=".csv" style="display:none" onchange="importCSV(this)">
    </label>
    <button class="btn btn-outline" onclick="calcPnl()">💹 損益計算</button>
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>ティッカー</th>
          <th>銘柄名</th>
          <th>保有数</th>
          <th>平均取得価額（円）</th>
          <th>現在値（円）</th>
          <th>損益（円）</th>
          <th>損益（%）</th>
          <th></th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>
</main>

<nav>
  <a href="/" class="nav-item"><span class="nav-icon">🌅</span><span class="nav-label">Morning</span></a>
  <a href="/evening" class="nav-item"><span class="nav-icon">🌆</span><span class="nav-label">Evening</span></a>
  <a href="/report" class="nav-item"><span class="nav-icon">📋</span><span class="nav-label">日報</span></a>
  <a href="/settings" class="nav-item active"><span class="nav-icon">⚙️</span><span class="nav-label">設定</span></a>
</nav>

<div id="toast"></div>

<script>
let rows = [];
let usdJpy = 155.0;

async function init() {
  // 為替取得
  try {
    const r = await fetch('/api/rate');
    if (r.ok) { const d = await r.json(); usdJpy = d.rate; document.getElementById('rate-label').textContent = `1USD = ¥${usdJpy.toFixed(2)}`; }
  } catch(e) { document.getElementById('rate-label').textContent = '1USD ≈ ¥155'; }

  // ポートフォリオ取得
  const res = await fetch('/api/portfolio');
  const data = await res.json();
  rows = data.positions || [];
  renderTable();
}

function renderTable() {
  const tbody = document.getElementById('tbody');
  tbody.innerHTML = '';
  rows.forEach((row, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><input type="text" value="${row.ticker||''}" onchange="rows[${i}].ticker=this.value.toUpperCase()" style="width:80px"></td>
      <td><input type="text" value="${row.name||''}" onchange="rows[${i}].name=this.value"></td>
      <td><input type="number" value="${row.shares||0}" step="0.01" onchange="rows[${i}].shares=parseFloat(this.value)||0" style="width:80px"></td>
      <td><input type="number" value="${row.cost_jpy||0}" step="1" onchange="rows[${i}].cost_jpy=parseFloat(this.value)||0" style="width:110px"></td>
      <td id="price-${i}" style="color:var(--text2)">-</td>
      <td id="pnl-${i}" style="color:var(--text2)">-</td>
      <td id="pct-${i}" style="color:var(--text2)">-</td>
      <td><button class="del-btn" onclick="deleteRow(${i})">×</button></td>
    `;
    tbody.appendChild(tr);
  });
}

function addRow() {
  rows.push({ ticker: '', name: '', shares: 0, cost_jpy: 0 });
  renderTable();
  const inputs = document.querySelectorAll('#tbody tr:last-child input');
  if (inputs[0]) inputs[0].focus();
}

function deleteRow(i) {
  if (!confirm(`「${rows[i].ticker}」を削除しますか？`)) return;
  rows.splice(i, 1);
  renderTable();
}

async function saveAll() {
  const valid = rows.filter(r => r.ticker);
  const res = await fetch('/api/portfolio', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ positions: valid })
  });
  if (res.ok) showToast('✅ 保存しました');
  else showToast('❌ 保存失敗', true);
}

function exportCSV() { window.location.href = '/api/portfolio/csv'; }

async function importCSV(input) {
  const file = input.files[0];
  if (!file) return;
  const form = new FormData();
  form.append('file', file);
  const res = await fetch('/api/portfolio/csv', { method: 'POST', body: form });
  if (res.ok) {
    const d = await res.json();
    showToast(`✅ ${d.count}件読み込みました`);
    await init();
  } else showToast('❌ CSV読込失敗', true);
  input.value = '';
}

async function calcPnl() {
  const tickers = rows.filter(r => r.ticker).map(r => r.ticker);
  if (!tickers.length) return;
  showToast('📡 株価取得中...');
  try {
    const res = await fetch('/api/prices?tickers=' + tickers.join(','));
    const prices = await res.json();

    let totalCost = 0, totalValue = 0;
    rows.forEach((row, i) => {
      const price = prices[row.ticker];
      if (!price) return;
      const cost = row.shares * row.cost_jpy;
      const value = row.shares * price * usdJpy;
      const pnl = value - cost;
      const pct = cost > 0 ? (pnl / cost * 100) : 0;
      totalCost += cost;
      totalValue += value;
      const priceEl = document.getElementById(`price-${i}`);
      const pnlEl   = document.getElementById(`pnl-${i}`);
      const pctEl   = document.getElementById(`pct-${i}`);
      if (priceEl) priceEl.textContent = `¥${Math.round(price * usdJpy).toLocaleString()}`;
      if (pnlEl) { pnlEl.textContent = `¥${Math.round(pnl).toLocaleString()}`; pnlEl.style.color = pnl >= 0 ? 'var(--accent2)' : 'var(--danger)'; }
      if (pctEl) { pctEl.textContent = `${pct.toFixed(2)}%`; pctEl.style.color = pct >= 0 ? 'var(--accent2)' : 'var(--danger)'; }
    });

    const totalPnl = totalValue - totalCost;
    const totalPct = totalCost > 0 ? (totalPnl / totalCost * 100) : 0;
    document.getElementById('summary').style.display = 'flex';
    document.getElementById('s-count').textContent = rows.filter(r=>r.ticker).length + '銘柄';
    document.getElementById('s-cost').textContent = '¥' + Math.round(totalCost).toLocaleString();
    document.getElementById('s-value').textContent = '¥' + Math.round(totalValue).toLocaleString();
    const pnlEl = document.getElementById('s-pnl');
    const pctEl = document.getElementById('s-pct');
    pnlEl.textContent = (totalPnl >= 0 ? '+' : '') + '¥' + Math.round(totalPnl).toLocaleString();
    pnlEl.className = 'summary-value ' + (totalPnl >= 0 ? 'pos' : 'neg');
    pctEl.textContent = (totalPct >= 0 ? '+' : '') + totalPct.toFixed(2) + '%';
    pctEl.className = 'summary-value ' + (totalPct >= 0 ? 'pos' : 'neg');
    showToast('✅ 損益計算完了');
  } catch(e) { showToast('❌ 株価取得失敗', true); }
}

function showToast(msg, isError=false) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = isError ? 'show error' : 'show';
  setTimeout(() => t.className = '', 3000);
}

init();
</script>
</body>
</html>"""
