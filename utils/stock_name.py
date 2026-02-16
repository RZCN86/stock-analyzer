import akshare as ak
import pandas as pd
from typing import Optional, Dict, Any
from datetime import datetime
import os
import json

from fetcher.base_fetcher import BaseFetcher
from utils.helpers import logger


class StockNameCache:
    """股票名称缓存"""

    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = cache_dir
        self.cache_file = os.path.join(cache_dir, "stock_names.json")
        self._cache = {}
        self._load_cache()

    def _load_cache(self):
        """加载缓存"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except:
                self._cache = {}

    def _save_cache(self):
        """保存缓存"""
        os.makedirs(self.cache_dir, exist_ok=True)
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, ensure_ascii=False, indent=2)

    def get(self, symbol: str, market: str = "A") -> Optional[str]:
        """获取股票名称"""
        key = f"{market}:{symbol}"
        return self._cache.get(key)

    def set(self, symbol: str, name: str, market: str = "A"):
        """设置股票名称"""
        key = f"{market}:{symbol}"
        self._cache[key] = name
        self._save_cache()


# 全局缓存实例
_name_cache = StockNameCache()


def is_etf(symbol: str) -> bool:
    """判断是否为ETF代码"""
    # ETF代码特征：
    # 上海ETF：51xxxx, 56xxxx, 58xxxx, 52xxxx
    # 深圳ETF：15xxxx, 16xxxx
    # 科创板ETF：588xxx
    if len(symbol) == 6:
        if symbol.startswith(("51", "56", "58", "52")):
            return True
        if symbol.startswith(("15", "16")):
            return True
        if symbol.startswith("588"):
            return True
    return False


def get_stock_name(symbol: str, market: str = "A") -> str:
    """
    获取股票名称

    Args:
        symbol: 股票代码
        market: 市场类型 (A/US)

    Returns:
        股票名称，如果未找到则返回代码
    """
    # 先查缓存
    cached_name = _name_cache.get(symbol, market)
    if cached_name:
        return cached_name

    try:
        if market == "A":
            # 判断是否为ETF
            if is_etf(symbol):
                name = get_etf_name(symbol)
                if name != symbol:
                    _name_cache.set(symbol, name, market)
                    return name

            # 获取A股名称
            df = ak.stock_zh_a_spot_em()
            stock_data = df[df["代码"] == symbol]
            if not stock_data.empty:
                name = stock_data.iloc[0]["名称"]
                _name_cache.set(symbol, name, market)
                return name
        elif market == "US":
            # 对于美股，返回代码作为名称（或使用映射表）
            name = get_us_stock_name(symbol)
            if name:
                _name_cache.set(symbol, name, market)
                return name
    except Exception as e:
        logger.warning(f"获取股票 {symbol} 名称失败: {e}")

    return symbol  # 如果找不到，返回代码


def get_us_stock_name(symbol: str) -> str:
    """获取美股名称（使用常见美股映射）"""
    us_stock_names = {
        "AAPL": "苹果公司",
        "MSFT": "微软",
        "GOOGL": "谷歌A",
        "GOOG": "谷歌C",
        "AMZN": "亚马逊",
        "TSLA": "特斯拉",
        "META": "Meta",
        "NVDA": "英伟达",
        "JPM": "摩根大通",
        "JNJ": "强生",
        "V": "Visa",
        "WMT": "沃尔玛",
        "PG": "宝洁",
        "UNH": "联合健康",
        "HD": "家得宝",
        "MA": "万事达",
        "BAC": "美国银行",
        "ABBV": "艾伯维",
        "PFE": "辉瑞",
        "KO": "可口可乐",
        "DIS": "迪士尼",
        "NFLX": "奈飞",
        "AMD": "AMD",
        "INTC": "英特尔",
        "CSCO": "思科",
        "ADBE": "Adobe",
        "CRM": "Salesforce",
        "PYPL": "PayPal",
        "UBER": "优步",
        "LYFT": "Lyft",
        "BABA": "阿里巴巴",
        "JD": "京东",
        "NIO": "蔚来",
        "XPEV": "小鹏汽车",
        "LI": "理想汽车",
        "PDD": "拼多多",
    }
    return us_stock_names.get(symbol, symbol)


def get_etf_name(symbol: str) -> str:
    """获取ETF名称"""
    etf_names = {
        "510300": "沪深300ETF",
        "510500": "中证500ETF",
        "512000": "券商ETF",
        "512880": "证券ETF",
        "510050": "上证50ETF",
        "159915": "创业板ETF",
        "159949": "创业板50ETF",
        "512800": "银行ETF",
        "512200": "地产ETF",
        "515700": "新能源ETF",
        "512480": "半导体ETF",
        "512760": "芯片ETF",
        "512690": "酒ETF",
        "512170": "医疗ETF",
        "512010": "医药ETF",
        "515030": "新能源车ETF",
        "159995": "芯片ETF",
        "159928": "消费ETF",
        "159938": "医药ETF",
    }

    # 先查映射表
    if symbol in etf_names:
        return etf_names[symbol]

    # 尝试从AKShare获取
    try:
        df = ak.fund_etf_spot_em()
        etf_data = df[df["代码"] == symbol]
        if not etf_data.empty:
            return etf_data.iloc[0]["名称"]
    except:
        pass

    return f"{symbol}ETF"


def get_stock_info(symbol: str, market: str = "A") -> Dict[str, Any]:
    """
    获取股票完整信息

    Returns:
        {
            'symbol': 代码,
            'name': 名称,
            'market': 市场,
            'industry': 行业,
            # ... 其他字段
        }
    """
    info = {
        "symbol": symbol,
        "name": get_stock_name(symbol, market),
        "market": market,
        "industry": "",
    }

    try:
        if market == "A":
            df = ak.stock_zh_a_spot_em()
            stock_data = df[df["代码"] == symbol]
            if not stock_data.empty:
                row = stock_data.iloc[0]
                info.update(
                    {
                        "name": row["名称"],
                        "industry": row.get("所属行业", ""),
                        "price": row.get("最新价", 0),
                        "change_pct": row.get("涨跌幅", 0),
                    }
                )
        elif market == "US":
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            stock_info = ticker.info
            info.update(
                {
                    "name": stock_info.get("longName", get_us_stock_name(symbol)),
                    "industry": stock_info.get("industry", ""),
                    "sector": stock_info.get("sector", ""),
                    "market_cap": stock_info.get("marketCap", 0),
                }
            )
    except Exception as e:
        logger.warning(f"获取股票 {symbol} 完整信息失败: {e}")

    return info
