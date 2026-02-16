# 🚀 快速启动指南

## 1️⃣ 安装依赖

```bash
cd stock-analyzer
pip install -r requirements.txt
```

## 2️⃣ 启动系统（三种方式）

### 🌐 方式一：Web界面（推荐）

```bash
python3 -m streamlit run web/app.py
```

然后打开浏览器访问：**http://localhost:8501**

### 💻 方式二：命令行

```bash
python3 main.py
```

### 📊 方式三：批量分析

```bash
python3 examples/batch_analysis.py
```

---

## 📖 详细文档

- 完整启动指南：`docs/STARTUP_GUIDE.md`
- 策略说明：`docs/STRATEGIES.md`
- 策略清单：`docs/STRATEGY_LIST.md`

---

## 🎯 使用示例

```python
from main import StockAnalyzer

analyzer = StockAnalyzer()

# 分析股票
result = analyzer.analyze("000001", market="A")
print(f"信号: {result['final_signal']}, 置信度: {result['confidence']}")

# 回测
backtest = analyzer.backtest("000001", "macd", market="A")
print(f"收益率: {backtest['total_return_pct']}")

# 绘制图表
analyzer.plot_analysis("000001")
```

祝你使用愉快！📈
