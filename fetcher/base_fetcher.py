from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
import pandas as pd
from datetime import datetime, timedelta
import time

from utils.config import config
from utils.helpers import logger, format_date


class BaseFetcher(ABC):
    """数据获取基类"""

    def __init__(self, market: str):
        self.market = market  # A, US, HK
        self.rate_limit = self._get_rate_limit()
        self.last_request_time = 0

    def _get_rate_limit(self) -> float:
        """获取请求频率限制"""
        if self.market == "A":
            return config.get("fetcher.akshare.rate_limit", 1.0)
        return config.get("fetcher.yfinance.rate_limit", 0.5)

    def _respect_rate_limit(self):
        """遵守请求频率限制"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self.last_request_time = time.time()

    @abstractmethod
    def fetch_daily_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """获取日线数据"""
        pass

    @abstractmethod
    def fetch_stock_list(self) -> pd.DataFrame:
        """获取股票列表"""
        pass

    @abstractmethod
    def fetch_realtime_quote(self, symbol: str) -> Dict[str, Any]:
        """获取实时行情"""
        pass
