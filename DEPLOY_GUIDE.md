# Streamlit Cloud 部署指南

## 1. 准备 GitHub 仓库

```bash
cd /Volumes/MacPlus/Dropbox/Code/ETF/stock-analyzer

# 初始化 git 仓库
git init

# 添加所有文件
git add .

# 提交
git commit -m "Initial commit for Streamlit Cloud deployment"

# 推送到 GitHub（你需要先创建 GitHub 仓库）
git remote add origin https://github.com/YOUR_USERNAME/stock-analyzer.git
git push -u origin main
```

## 2. 部署步骤

1. 访问 https://streamlit.io/cloud
2. 用 GitHub 账号登录
3. 点击 "New app"
4. 选择你的仓库
5. 主文件路径填：`web/app.py`
6. 点击 "Deploy"

## 3. 配置 requirements.txt

确保 requirements.txt 已包含所有依赖：

```
streamlit>=1.30.0
pandas>=2.0.0
numpy>=1.24.0
akshare>=1.15.0
yfinance>=0.2.0
matplotlib>=3.7.0
mplfinance>=0.12.0
plotly>=5.0.0
pyyaml>=6.0
tqdm>=4.65.0
```

## 4. 配置 secrets（可选）

如果需要数据库等敏感配置，在 Streamlit Cloud 的 Advanced settings 中设置。

---

部署完成后会获得一个类似 `https://stock-analyzer-xxx.streamlit.app` 的链接。
