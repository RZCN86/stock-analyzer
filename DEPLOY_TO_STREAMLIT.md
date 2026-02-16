# 🚀 Streamlit Cloud 部署步骤

## 第一步：创建 GitHub 仓库

1. 访问 https://github.com/new
2. 仓库名称：`stock-analyzer`
3. 选择 **Public**（免费）
4. 点击 **Create repository**

## 第二步：推送代码到 GitHub

在终端执行以下命令：

```bash
cd /Volumes/MacPlus/Dropbox/Code/ETF/stock-analyzer

# 添加远程仓库（用你的用户名替换 YOUR_USERNAME）
git remote add origin https://github.com/YOUR_USERNAME/stock-analyzer.git

# 推送代码
git push -u origin main
```

## 第三步：部署到 Streamlit Cloud

1. 访问 https://streamlit.io/cloud
2. 点击 **Sign in with GitHub**
3. 授权访问你的仓库
4. 点击 **New app**
5. 选择：
   - **Repository**: your-username/stock-analyzer
   - **Branch**: main
   - **Main file path**: web/app.py
6. 点击 **Deploy**

## 第四步：等待部署完成

- 部署大约需要 2-5 分钟
- 成功后会显示一个类似 `https://stock-analyzer-xxx.streamlit.app` 的链接
- 点击链接即可访问！

---

## ⚠️ 重要提示

### 免费版的限制
- **休眠机制**：15分钟无人访问后会休眠，下次访问需要10-30秒启动
- **资源限制**：1 GB RAM，适合个人使用

### 数据库说明
- 数据存储在临时目录，应用重启后会重置
- 如果需要持久化存储，需要：
  1. 使用外部数据库（如 PostgreSQL）
  2. 或使用 Streamlit Cloud 的持久化存储（付费功能）

### 快速链接

- Streamlit Cloud: https://streamlit.io/cloud
- 部署文档: https://docs.streamlit.io/streamlit-community-cloud

---

🎉 部署完成后，你就可以通过链接随时随地访问股票分析系统了！
