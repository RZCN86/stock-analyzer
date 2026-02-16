import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class HistoryItem:
    """历史记录项"""

    symbol: str
    name: str
    market: str
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HistoryItem":
        return cls(**data)


class HistoryManager:
    """历史记录管理器 - 管理最近查询的标的"""

    def __init__(self, max_history: int = 10, cache_dir: str = "data/cache"):
        self.max_history = max_history
        self.cache_dir = cache_dir
        self.history_file = os.path.join(cache_dir, "query_history.json")
        self._history: List[HistoryItem] = []
        self._load_history()

    def _load_history(self):
        """加载历史记录"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._history = [HistoryItem.from_dict(item) for item in data]
            except Exception:
                self._history = []

    def _save_history(self):
        """保存历史记录"""
        os.makedirs(self.cache_dir, exist_ok=True)
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(
                    [item.to_dict() for item in self._history],
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception as e:
            print(f"保存历史记录失败: {e}")

    def add(self, symbol: str, name: str, market: str = "A"):
        """
        添加历史记录

        Args:
            symbol: 股票代码
            name: 股票名称
            market: 市场类型
        """
        # 如果已存在，先移除旧的
        self._history = [
            h for h in self._history if not (h.symbol == symbol and h.market == market)
        ]

        # 添加到开头（最新的）
        new_item = HistoryItem(
            symbol=symbol,
            name=name,
            market=market,
            timestamp=datetime.now().isoformat(),
        )
        self._history.insert(0, new_item)

        # 限制数量
        if len(self._history) > self.max_history:
            self._history = self._history[: self.max_history]

        self._save_history()

    def get_history(self, limit: int = None) -> List[HistoryItem]:
        """
        获取历史记录

        Args:
            limit: 限制返回数量，默认返回全部

        Returns:
            历史记录列表
        """
        if limit:
            return self._history[:limit]
        return self._history.copy()

    def get_recent(self, n: int = 10) -> List[HistoryItem]:
        """获取最近n条记录"""
        return self._history[:n]

    def clear(self):
        """清空历史记录"""
        self._history = []
        self._save_history()

    def remove(self, symbol: str, market: str = "A"):
        """删除特定记录"""
        self._history = [
            h for h in self._history if not (h.symbol == symbol and h.market == market)
        ]
        self._save_history()

    def is_empty(self) -> bool:
        """是否为空"""
        return len(self._history) == 0

    def __len__(self) -> int:
        return len(self._history)


# 全局历史记录实例
_history_manager = HistoryManager(max_history=10)


def add_to_history(symbol: str, name: str, market: str = "A"):
    """添加到历史记录"""
    _history_manager.add(symbol, name, market)


def get_history(limit: int = 10) -> List[Dict[str, Any]]:
    """获取历史记录"""
    items = _history_manager.get_recent(n=limit)
    return [item.to_dict() for item in items]


def get_recent_symbols(n: int = 10) -> List[str]:
    """获取最近查询的代码列表"""
    items = _history_manager.get_recent(n=n)
    return [item.symbol for item in items]


def clear_history():
    """清空历史记录"""
    _history_manager.clear()
