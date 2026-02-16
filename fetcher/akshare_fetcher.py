import akshare as ak
import pandas as pd
from typing import Optional, Dict, Any
from datetime import datetime

from fetcher.base_fetcher import BaseFetcher
from utils.helpers import logger


class AKShareFetcher(BaseFetcher):
    """AKShare数据获取器 - 用于A股、港股、ETF数据"""

    def __init__(self):
        super().__init__("A")
        logger.info("AKShare获取器初始化完成")

    def fetch_daily_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """
        获取A股日线数据

        Args:
            symbol: 股票代码，如 "000001"
            start_date: 开始日期，格式 "YYYYMMDD"
            end_date: 结束日期，格式 "YYYYMMDD"
            adjust: 复权方式，qfq=前复权, hfq=后复权, 空=不复权
        """
        self._respect_rate_limit()

        try:
            # 格式化日期
            if start_date:
                start_date = start_date.replace("-", "")
            if end_date:
                end_date = end_date.replace("-", "")

            # 获取历史数据
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date or "19700101",
                end_date=end_date or datetime.now().strftime("%Y%m%d"),
                adjust=adjust,
            )

            if df.empty:
                logger.warning(f"未获取到股票 {symbol} 的数据")
                return pd.DataFrame()

            # 重命名列以便统一处理
            # AKShare返回: 日期, 股票代码, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 振幅, 涨跌幅, 涨跌额, 换手率
            column_mapping = {
                "日期": "date",
                "股票代码": "symbol",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
                "成交额": "amount",
                "振幅": "amplitude",
                "涨跌幅": "pct_change",
                "涨跌额": "change_amount",
                "换手率": "turnover",
            }
            df = df.rename(columns=column_mapping)
            df["date"] = pd.to_datetime(df["date"])
            # 移除symbol列（已在参数中指定）
            df = df.drop(columns=["symbol"], errors="ignore")

            logger.info(f"成功获取 {symbol} 的 {len(df)} 条数据")
            return df

        except Exception as e:
            logger.error(f"获取股票 {symbol} 数据失败: {e}")
            return pd.DataFrame()

    def fetch_etf_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        获取ETF历史数据

        Args:
            symbol: ETF代码，如 "510300"
            start_date: 开始日期，格式 "YYYYMMDD"
            end_date: 结束日期，格式 "YYYYMMDD"
        """
        self._respect_rate_limit()

        try:
            symbol = symbol.strip()
            if start_date:
                start_date = start_date.replace("-", "")
            if end_date:
                end_date = end_date.replace("-", "")

            df = ak.fund_etf_hist_em(
                symbol=symbol,
                period="daily",
                start_date=start_date or "19700101",
                end_date=end_date or datetime.now().strftime("%Y%m%d"),
                adjust="",
            )

            if df.empty:
                logger.warning(f"ETF主接口无数据，尝试备用源: {symbol}")
                sina_symbol = symbol.lower()
                if not sina_symbol.startswith(("sh", "sz")):
                    sina_symbol = (
                        f"sh{symbol}" if symbol.startswith(("5", "6", "9")) else f"sz{symbol}"
                    )
                df = ak.fund_etf_hist_sina(symbol=sina_symbol)
                if df.empty:
                    logger.warning(f"未获取到ETF {symbol} 的数据")
                    return pd.DataFrame()

                df = df.rename(
                    columns={
                        "日期": "date",
                        "开盘": "open",
                        "收盘": "close",
                        "最高": "high",
                        "最低": "low",
                        "成交量": "volume",
                        "成交额": "amount",
                    }
                )
                df["date"] = pd.to_datetime(df["date"])
                if start_date:
                    df = df[df["date"] >= pd.to_datetime(start_date)]
                if end_date:
                    df = df[df["date"] <= pd.to_datetime(end_date)]

                if "change_amount" not in df.columns:
                    if "prevclose" in df.columns:
                        df["change_amount"] = df["close"] - df["prevclose"]
                    else:
                        df["change_amount"] = df["close"].diff()
                if "pct_change" not in df.columns:
                    df["pct_change"] = df["close"].pct_change() * 100
                if "amplitude" not in df.columns:
                    df["amplitude"] = None
                if "turnover" not in df.columns:
                    df["turnover"] = None
            else:
                # 统一列名
                df.columns = [
                    "date",
                    "open",
                    "close",
                    "high",
                    "low",
                    "volume",
                    "amount",
                    "amplitude",
                    "pct_change",
                    "change_amount",
                    "turnover",
                ]
                df["date"] = pd.to_datetime(df["date"])

            logger.info(f"成功获取ETF {symbol} 的 {len(df)} 条数据")
            return df

        except Exception as e:
            logger.error(f"获取ETF {symbol} 数据失败: {e}")
            return pd.DataFrame()

    def fetch_stock_list(self) -> pd.DataFrame:
        """获取A股股票列表"""
        self._respect_rate_limit()

        try:
            # 获取上海A股
            sh_df = ak.stock_sh_a_spot_em()
            sh_df["exchange"] = "SH"

            self._respect_rate_limit()

            # 获取深圳A股
            sz_df = ak.stock_sz_a_spot_em()
            sz_df["exchange"] = "SZ"

            # 合并数据
            df = pd.concat([sh_df, sz_df], ignore_index=True)

            # 兼容AKShare字段变更
            columns_map = {"代码": "symbol", "名称": "name", "交易所": "exchange"}
            df = df.rename(columns=columns_map)

            industry_column = next(
                (col for col in ["所属行业", "行业", "行业板块"] if col in df.columns),
                None,
            )
            if industry_column:
                df = df.rename(columns={industry_column: "industry"})
            if "industry" not in df.columns:
                df["industry"] = "未知"
            if "exchange" not in df.columns:
                df["exchange"] = "UNKNOWN"

            df["market"] = "A"

            # 只保留需要的列
            result = df[["symbol", "name", "market", "industry", "exchange"]].copy()

            logger.info(f"成功获取 {len(result)} 只A股股票列表")
            return result

        except Exception as e:
            logger.error(f"获取A股列表失败: {e}")
            return pd.DataFrame()

    def fetch_etf_list(self) -> pd.DataFrame:
        """获取ETF列表"""
        self._respect_rate_limit()

        try:
            df = ak.fund_etf_spot_em()

            columns_map = {"代码": "symbol", "名称": "name"}

            df = df.rename(columns=columns_map)
            df["market"] = "A"
            df["exchange"] = df["symbol"].apply(
                lambda x: "SH" if x.startswith("51") else "SZ"
            )
            df["industry"] = "ETF"

            result = df[["symbol", "name", "market", "industry", "exchange"]].copy()

            logger.info(f"成功获取 {len(result)} 只ETF列表")
            return result

        except Exception as e:
            logger.error(f"获取ETF列表失败: {e}")
            return pd.DataFrame()

    def fetch_realtime_quote(self, symbol: str) -> Dict[str, Any]:
        """获取A股实时行情"""
        self._respect_rate_limit()

        try:
            df = ak.stock_zh_a_spot_em()
            stock_data = df[df["代码"] == symbol]

            if stock_data.empty:
                return {}

            row = stock_data.iloc[0]
            return {
                "symbol": symbol,
                "name": row["名称"],
                "price": row["最新价"],
                "change": row["涨跌幅"],
                "volume": row["成交量"],
                "turnover": row["成交额"],
                "high": row["最高"],
                "low": row["最低"],
                "open": row["今开"],
                "pre_close": row["昨收"],
            }

        except Exception as e:
            logger.error(f"获取 {symbol} 实时行情失败: {e}")
            return {}

    def fetch_index_data(
        self,
        index_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        获取指数数据

        Args:
            index_code: 指数代码，如 "000001"(上证指数), "399001"(深证成指)
        """
        self._respect_rate_limit()

        try:
            if start_date:
                start_date = start_date.replace("-", "")
            if end_date:
                end_date = end_date.replace("-", "")

            # 判断是上海还是深圳指数
            if index_code.startswith("000") or index_code.startswith("880"):
                df = ak.index_zh_a_hist(
                    symbol=index_code,
                    period="daily",
                    start_date=start_date or "19700101",
                    end_date=end_date or datetime.now().strftime("%Y%m%d"),
                )
            else:
                df = ak.index_zh_a_hist(
                    symbol=index_code,
                    period="daily",
                    start_date=start_date or "19700101",
                    end_date=end_date or datetime.now().strftime("%Y%m%d"),
                )

            if df.empty:
                return pd.DataFrame()

            df.columns = [
                "date",
                "open",
                "close",
                "high",
                "low",
                "volume",
                "amount",
                "amplitude",
                "pct_change",
                "change_amount",
                "turnover",
            ]
            df["date"] = pd.to_datetime(df["date"])

            return df

        except Exception as e:
            logger.error(f"获取指数 {index_code} 数据失败: {e}")
            return pd.DataFrame()
