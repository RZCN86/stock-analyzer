import yfinance as yf
import pandas as pd
from typing import Optional, Dict, Any
from datetime import datetime

from fetcher.base_fetcher import BaseFetcher
from utils.helpers import logger


class YFinanceFetcher(BaseFetcher):
    """YFinance数据获取器 - 用于美股数据"""

    def __init__(self):
        super().__init__("US")
        logger.info("YFinance获取器初始化完成")

    def fetch_daily_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """获取美股日线数据"""
        self._respect_rate_limit()

        try:
            # yfinance使用标准股票代码格式
            ticker = yf.Ticker(symbol)

            # 转换日期格式
            start = start_date if start_date else "2020-01-01"
            end = end_date if end_date else datetime.now().strftime("%Y-%m-%d")

            # 获取历史数据
            df = ticker.history(start=start, end=end, auto_adjust=(adjust == "qfq"))

            if df.empty:
                logger.warning(f"未获取到美股 {symbol} 的数据")
                return pd.DataFrame()

            # 重置索引并格式化
            df.reset_index(inplace=True)
            df.columns = [col.lower().replace(" ", "_") for col in df.columns]

            # 标准化列名
            column_mapping = {
                "date": "date",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "volume",
                "dividends": "dividends",
                "stock_splits": "splits",
            }

            df = df.rename(columns=column_mapping)
            df["date"] = pd.to_datetime(df["date"])

            # 计算涨跌幅
            df["pct_change"] = df["close"].pct_change() * 100
            df["change_amount"] = df["close"].diff()

            # 保留需要的列
            result_columns = [
                "date",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "pct_change",
                "change_amount",
            ]
            df = df[[col for col in result_columns if col in df.columns]].copy()

            logger.info(f"成功获取美股 {symbol} 的 {len(df)} 条数据")
            return df

        except Exception as e:
            logger.error(f"获取美股 {symbol} 数据失败: {e}")
            return pd.DataFrame()

    def fetch_stock_list(self) -> pd.DataFrame:
        """获取美股股票列表（使用预设的热门股票）"""
        # yfinance不提供完整股票列表，返回一些热门股票作为示例
        popular_stocks = [
            {"symbol": "AAPL", "name": "Apple Inc.", "industry": "Technology"},
            {
                "symbol": "MSFT",
                "name": "Microsoft Corporation",
                "industry": "Technology",
            },
            {"symbol": "GOOGL", "name": "Alphabet Inc.", "industry": "Technology"},
            {
                "symbol": "AMZN",
                "name": "Amazon.com Inc.",
                "industry": "Consumer Cyclical",
            },
            {"symbol": "TSLA", "name": "Tesla Inc.", "industry": "Consumer Cyclical"},
            {"symbol": "META", "name": "Meta Platforms Inc.", "industry": "Technology"},
            {"symbol": "NVDA", "name": "NVIDIA Corporation", "industry": "Technology"},
            {
                "symbol": "JPM",
                "name": "JPMorgan Chase & Co.",
                "industry": "Financial Services",
            },
            {"symbol": "JNJ", "name": "Johnson & Johnson", "industry": "Healthcare"},
            {"symbol": "V", "name": "Visa Inc.", "industry": "Financial Services"},
            {"symbol": "WMT", "name": "Walmart Inc.", "industry": "Consumer Defensive"},
            {
                "symbol": "PG",
                "name": "Procter & Gamble Co.",
                "industry": "Consumer Defensive",
            },
            {
                "symbol": "UNH",
                "name": "UnitedHealth Group Inc.",
                "industry": "Healthcare",
            },
            {
                "symbol": "HD",
                "name": "Home Depot Inc.",
                "industry": "Consumer Cyclical",
            },
            {
                "symbol": "MA",
                "name": "Mastercard Inc.",
                "industry": "Financial Services",
            },
            {
                "symbol": "BAC",
                "name": "Bank of America Corporation",
                "industry": "Financial Services",
            },
            {"symbol": "ABBV", "name": "AbbVie Inc.", "industry": "Healthcare"},
            {"symbol": "PFE", "name": "Pfizer Inc.", "industry": "Healthcare"},
            {
                "symbol": "KO",
                "name": "Coca-Cola Company",
                "industry": "Consumer Defensive",
            },
            {
                "symbol": "DIS",
                "name": "Walt Disney Company",
                "industry": "Communication Services",
            },
        ]

        df = pd.DataFrame(popular_stocks)
        df["market"] = "US"
        df["exchange"] = "NYSE/NASDAQ"

        logger.info(f"返回 {len(df)} 只热门美股")
        return df

    def fetch_realtime_quote(self, symbol: str) -> Dict[str, Any]:
        """获取美股实时行情"""
        self._respect_rate_limit()

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            return {
                "symbol": symbol,
                "name": info.get("longName", ""),
                "price": info.get("currentPrice", info.get("regularMarketPrice")),
                "change": info.get("regularMarketChangePercent"),
                "volume": info.get("volume"),
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
            }

        except Exception as e:
            logger.error(f"获取美股 {symbol} 实时行情失败: {e}")
            return {}

    def fetch_etf_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """获取美股ETF数据"""
        return self.fetch_daily_data(symbol, start_date, end_date)

    def fetch_company_info(self, symbol: str) -> Dict[str, Any]:
        """获取公司详细信息"""
        self._respect_rate_limit()

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            return {
                "symbol": symbol,
                "name": info.get("longName"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "employees": info.get("fullTimeEmployees"),
                "country": info.get("country"),
                "website": info.get("website"),
                "business_summary": info.get("longBusinessSummary"),
            }

        except Exception as e:
            logger.error(f"获取 {symbol} 公司信息失败: {e}")
            return {}
