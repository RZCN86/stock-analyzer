import os
import logging
from datetime import datetime
from typing import Optional


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    format_str: Optional[str] = None,
) -> logging.Logger:
    """设置日志"""
    if format_str is None:
        format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # 创建logger
    logger = logging.getLogger("stock_analyzer")
    logger.setLevel(level)

    # 清除已有处理器前先显式关闭，避免文件句柄泄漏
    for handler in logger.handlers:
        try:
            handler.close()
        except Exception:
            pass
    logger.handlers.clear()

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(format_str))
    logger.addHandler(console_handler)

    # 文件处理器
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(format_str))
        logger.addHandler(file_handler)

    return logger


# 全局logger实例
logger = setup_logging()


def format_date(date_str: str) -> str:
    """格式化日期字符串"""
    # 支持多种日期格式
    formats = ["%Y-%m-%d", "%Y%m%d", "%Y/%m/%d", "%d-%m-%Y"]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"无法解析日期格式: {date_str}")


def ensure_dir(path: str):
    """确保目录存在"""
    os.makedirs(path, exist_ok=True)


def validate_symbol(symbol: str, market: str = "A") -> bool:
    """验证股票代码格式"""
    if market == "A":
        # A股代码格式: 6位数字
        return len(symbol) == 6 and symbol.isdigit()
    elif market == "US":
        # 美股代码格式: 1-5位字母
        return 1 <= len(symbol) <= 5 and symbol.isalpha()
    return False
