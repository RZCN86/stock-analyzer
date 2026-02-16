#!/bin/bash
# GitHub 部署自动化脚本

set -e

echo "🚀 股票分析系统部署助手"
echo "=========================="
echo ""

# 检查 git
if ! command -v git &> /dev/null; then
    echo "❌ 请先安装 git"
    exit 1
fi

# 检查 GitHub CLI
if ! command -v gh &> /dev/null; then
    echo "⚠️  建议安装 GitHub CLI (gh) 以简化操作"
    echo "   Mac: brew install gh"
    echo "   其他: https://cli.github.com/"
    echo ""
fi

cd /Volumes/MacPlus/Dropbox/Code/ETF/stock-analyzer

# 获取 GitHub 用户名
read -p "请输入你的 GitHub 用户名: " USERNAME

if [ -z "$USERNAME" ]; then
    echo "❌ 用户名不能为空"
    exit 1
fi

REPO_NAME="stock-analyzer"
REPO_URL="https://github.com/$USERNAME/$REPO_NAME"

echo ""
echo "📋 步骤确认:"
echo "   GitHub 用户: $USERNAME"
echo "   仓库名称: $REPO_NAME"
echo "   仓库地址: $REPO_URL"
echo ""

read -p "确认以上信息正确? (y/n): " confirm
if [ "$confirm" != "y" ]; then
    echo "已取消"
    exit 1
fi

echo ""
echo "🔧 第1步: 配置 Git 远程仓库..."

# 移除已有的 remote（如果有）
git remote remove origin 2>/dev/null || true

# 添加新的 remote
git remote add origin "$REPO_URL"

echo "   ✅ Git 远程仓库已配置"

echo ""
echo "📤 第2步: 准备推送代码..."

# 确保所有更改都已提交
git add -A
git diff --cached --quiet || git commit -m "Update for deployment"

echo ""
echo "🚀 第3步: 推送到 GitHub..."
echo ""
echo "⚠️  如果这是第一次推送，会提示你登录 GitHub"
echo "   请按提示输入 GitHub 用户名和密码/Token"
echo ""

# 尝试推送
if git push -u origin main 2>&1; then
    echo ""
    echo "✅ 代码推送成功!"
    echo ""
    echo "🎉 部署准备完成!"
    echo ""
    echo "📎 仓库地址: $REPO_URL"
    echo ""
    echo "下一步: 部署到 Streamlit Cloud"
    echo "   1. 访问 https://streamlit.io/cloud"
    echo "   2. 用 GitHub 登录"
    echo "   3. 点击 'New app'"
    echo "   4. 选择仓库: $USERNAME/$REPO_NAME"
    echo "   5. 主文件路径: web/app.py"
    echo "   6. 点击 Deploy"
    echo ""
else
    echo ""
    echo "❌ 推送失败"
    echo ""
    echo "可能的原因:"
    echo "   1. GitHub 仓库尚未创建"
    echo "   2. 未登录 GitHub"
    echo "   3. 网络问题"
    echo ""
    echo "请手动完成以下步骤:"
    echo "   1. 访问 https://github.com/new"
    echo "   2. 创建名为 '$REPO_NAME' 的仓库"
    echo "   3. 重新运行此脚本"
    echo ""
fi
