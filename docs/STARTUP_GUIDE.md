# 🚀 系统启动指南

## 📋 前置条件

### 1. 安装依赖

```bash
cd stock-analyzer
pip install -r requirements.txt
```

主要依赖：
- akshare >= 1.15.0 （A股数据）
- yfinance >= 0.2.0 （美股数据）
- pandas >= 2.0.0
- streamlit （Web界面）
- matplotlib, mplfinance （图表）

### 2. 验证安装

```bash
python3 -c "from main import StockAnalyzer; print('✅ 安装成功')"
```

---

## 🎯 启动方式

### 方式一：Web交互界面（推荐）

Web界面提供最友好的交互体验，支持实时分析、图表展示和策略配置。

#### 启动命令

```bash
cd stock-analyzer

# 方式A: 直接启动
python3 -m streamlit run web/app.py

# 方式B: 使用启动脚本
cd web && ./start.sh

# 方式C: 指定端口（如果8501被占用）
python3 -m streamlit run web/app.py --server.port 8502
```

#### 访问系统

启动后，在浏览器中打开：
```
http://localhost:8501
```

或终端中显示的Network URL。

#### Web界面功能

- 📊 **实时行情显示**：当前价格、涨跌幅、成交量
- 🎯 **交易信号分析**：综合信号、多策略对比、置信度评分
- 📈 **技术分析图表**：K线图、MACD、RSI、布林带
- 📉 **策略回测**：收益率、最大回撤、资金曲线
- ⚙️ **交互式配置**：选择策略、调整参数、更新数据

---

### 方式二：命令行模式

适合快速分析单个股票或自动化脚本。

#### 启动命令

```bash
cd stock-analyzer
python3 main.py
```

#### 示例输出

```
============================================================
股票分析系统
============================================================

正在分析股票: 000001

分析结果:
  当前价格: 10.91
  综合信号: HOLD
  置信度: 0.50

各策略详情:
  ma_cross: HOLD - MA5在MA20上方，偏离度0.21%
  macd: HOLD - DIF在DEA上方 (偏离:18.03%)
  rsi: HOLD - RSI在合理区间 (47.25)

正在回测 000001 的MACD策略...

回测结果:
  初始资金: 100000
  最终权益: 118571.35
  总收益率: 18.57%
  最大回撤: 41.09%
  交易次数: 53

正在生成图表...
图表已保存: output/charts/000001_candlestick.png
图表已保存: output/charts/000001_indicators.png

分析完成!
```

#### 代码中使用

```python
from main import StockAnalyzer

# 初始化
analyzer = StockAnalyzer()

# 分析股票
result = analyzer.analyze("000001", market="A")
print(f"信号: {result['final_signal']}")
print(f"置信度: {result['confidence']}")

# 回测
backtest = analyzer.backtest("000001", "macd", market="A")
print(f"收益率: {backtest['total_return_pct']}")

# 绘制图表
analyzer.plot_analysis("000001")
```

---

### 方式三：批量分析

同时分析多只股票，生成批量报告。

#### 启动命令

```bash
cd stock-analyzer
python3 examples/batch_analysis.py
```

#### 自定义股票列表

编辑 `examples/batch_analysis.py` 中的 `watchlist`:

```python
watchlist = [
    # A股
    ("000001", "A", "平安银行"),
    ("600519", "A", "贵州茅台"),
    ("300750", "A", "宁德时代"),
    # 美股
    ("AAPL", "US", "苹果"),
    ("TSLA", "US", "特斯拉"),
    # 添加更多...
]
```

#### 批量分析输出示例

```
================================================================================
股票批量分析报告
================================================================================
代码           名称           市场     价格         涨跌幅        信号       置信度     
--------------------------------------------------------------------------------
000001       平安银行         A      10.91      0.00      % ⚪ HOLD   0.50    
600519       贵州茅台         A      1485.30    -0.09     % ⚪ HOLD   0.50    
300750       宁德时代         A      365.34     -2.80     % 🔴 SELL   0.75    
AAPL         苹果           US     189.23     1.25      % 🟢 BUY    0.68    
TSLA         特斯拉          US     245.67     -1.50     % ⚪ HOLD   0.45    
================================================================================

📊 详细交易建议:
--------------------------------------------------------------------------------

🟢 买入建议:
  • AAPL (苹果): 置信度 0.68
    - macd: MACD金叉
    - ma_cross: 均线多头排列

🔴 卖出建议:
  • 300750 (宁德时代): 置信度 0.75
    - rsi: RSI从超买区回落

================================================================================
免责声明: 以上分析仅供参考，不构成投资建议。股市有风险，投资需谨慎。
================================================================================
```

---

## 🔧 高级用法

### 自定义策略组合

```python
from main import StockAnalyzer

analyzer = StockAnalyzer()

# 指定策略组合
strategies = ['ma_cross', 'macd', 'rsi', 'multi_factor']
result = analyzer.strategy_engine.analyze(df, strategies)

print(f"综合信号: {result['final_signal']}")
print(f"买入信号: {result['buy_signals']}")
print(f"卖出信号: {result['sell_signals']}")
```

### 定时更新数据

```bash
# 创建定时任务（Linux/Mac）
crontab -e

# 每天收盘后更新数据（15:30执行）
30 15 * * 1-5 cd /path/to/stock-analyzer && python3 -c "from main import StockAnalyzer; analyzer = StockAnalyzer(); analyzer.fetch_and_store('000001', 'A')"
```

### 后台运行Web服务

```bash
# Linux/Mac
nohup python3 -m streamlit run web/app.py > server.log 2>&1 &

# 查看日志
tail -f server.log

# 停止服务
pkill -f "streamlit run web/app.py"
```

---

## 🐛 常见问题

### 问题1: 端口被占用

**错误**: `Port 8501 is already in use`

**解决方案**:
```bash
# 使用其他端口
python3 -m streamlit run web/app.py --server.port 8502
```

### 问题2: 中文字体显示乱码

**现象**: 图表中中文显示为方框

**解决方案**:
- 系统已自动配置中文字体
- 如需手动配置，编辑 `utils/font_config.py`
- 确保系统已安装黑体（SimHei）或微软雅黑

### 问题3: 无法获取数据

**现象**: "未获取到股票数据" 或网络错误

**检查项**:
1. 网络连接是否正常
2. 股票代码是否正确（A股6位数字）
3. 防火墙是否阻止了请求

**测试数据获取**:
```bash
python3 -c "
from fetcher.akshare_fetcher import AKShareFetcher
fetcher = AKShareFetcher()
df = fetcher.fetch_daily_data('000001')
print(f'获取到 {len(df)} 条数据')
"
```

### 问题4: 策略报错 "未知策略"

**解决方案**:
```python
from strategy.engine import StrategyEngine

engine = StrategyEngine()
print(engine.get_strategy_list())
# 使用列表中的策略名称
```

### 问题5: 启动后页面空白

**可能原因**:
- 浏览器缓存问题：清除缓存或换浏览器
- 数据未加载：等待几秒钟或点击"更新数据"
- JavaScript被禁用：启用JavaScript

---

## 📊 系统架构

```
用户界面层
├── Web界面 (Streamlit) ← 推荐
├── 命令行模式
└── 批量分析脚本

业务逻辑层
├── 数据获取 (AKShare/yfinance)
├── 技术指标计算
├── 策略引擎 (11种策略)
├── 回测引擎
└── 可视化

数据存储层
└── SQLite数据库 (data/stock_analyzer.db)
```

---

## 🎯 快速开始检查清单

- [ ] 已安装 Python 3.9+
- [ ] 已安装依赖: `pip install -r requirements.txt`
- [ ] 已验证安装: `python3 -c "from main import StockAnalyzer"`
- [ ] 已启动系统: `python3 -m streamlit run web/app.py`
- [ ] 已打开浏览器: `http://localhost:8501`
- [ ] 已输入股票代码并点击"更新数据"
- [ ] 已查看分析结果和交易信号

---

## 📞 获取帮助

如果遇到问题：

1. 查看本文档的常见问题部分
2. 运行诊断工具：`python3 test_strategies.py`
3. 查看日志输出
4. 检查系统要求

---

## 🎉 开始使用

现在你已经了解了所有启动方式，选择最适合你的方式开始吧！

**推荐新手路径**:
1. 先使用 Web 界面进行交互式分析
2. 熟悉后尝试命令行模式
3. 最后使用批量分析进行多股票监控

祝你投资顺利！📈
