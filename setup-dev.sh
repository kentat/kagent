#!/bin/bash
# ============================================================
# 開発環境セットアップスクリプト
# Ubuntu（WSL2）で1回だけ実行する
# 使い方: bash setup-dev.sh
# ============================================================

set -e
echo "🚀 Kenta Agent 開発環境をセットアップ中..."

cd ~/kagent

# 1. pre-commit インストール
echo "📦 pre-commit をインストール中..."
pip install pre-commit detect-secrets bandit ruff --break-system-packages

# 2. pre-commit フックを Git に登録
echo "🔗 Git フックを登録中..."
pre-commit install

# 3. detect-secrets のベースライン作成
echo "🔐 シークレットベースライン作成中..."
detect-secrets scan \
  --exclude-files '*.lock' \
  --exclude-files '.env.example' \
  --exclude-files '*.md' \
  > .secrets.baseline

echo ""
echo "✅ セットアップ完了！"
echo ""
echo "これからは git commit のたびに自動で以下がチェックされます："
echo "  ① 構文チェック（check-ast）"
echo "  ② シークレット検出（detect-secrets）"
echo "  ③ セキュリティスキャン（bandit）"
echo "  ④ コード品質（ruff）"
echo ""
echo "また GitHub に push するたびに GitHub Actions でも同じチェックが走ります。"
