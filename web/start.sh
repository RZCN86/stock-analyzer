#!/bin/bash

cd "$(dirname "$0")/.."

echo "🚀 启动股票分析系统 Web界面..."
echo ""
echo "📱 应用将在浏览器中打开"
echo "📝 如果浏览器没有自动打开，请手动访问: http://localhost:8501"
echo ""

python3 -m streamlit run web/app.py --server.port 8501 --server.address localhost
