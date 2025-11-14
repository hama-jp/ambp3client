#!/bin/bash
#
# AMB P3 Real-time Dashboard Startup Script
# ラップタイマーダッシュボード起動スクリプト
#

echo "🏁 AMB P3 ラップタイマーダッシュボードを起動します..."
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "仮想環境が見つかりません。作成しています..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "依存関係をインストールしています..."
pip install -r requirements.txt
pip install -r requirements-webapp.txt

echo ""
echo "✅ セットアップ完了"
echo ""
echo "ダッシュボードを起動しています..."
echo "ブラウザで http://localhost:8000 にアクセスしてください"
echo ""
echo "停止するには Ctrl+C を押してください"
echo ""

# Start the web application
python -m uvicorn webapp.app:app --host 0.0.0.0 --port 8000 --reload
