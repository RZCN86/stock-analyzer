import os
import yaml
from typing import Dict, Any


class Config:
    """配置管理类"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.settings = self._load_yaml("config/settings.yaml")
        self.strategies = self._load_yaml("config/strategies.yaml")
        self._initialized = True

    def _load_yaml(self, path: str) -> Dict[str, Any]:
        """加载YAML配置文件"""
        full_path = os.path.join(self.base_dir, path)
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            print(f"警告: 配置文件不存在 {full_path}")
            return {}
        except yaml.YAMLError as e:
            print(f"错误: 配置文件解析失败 {full_path}: {e}")
            return {}

    def get(self, key: str, default=None, section: str = "settings"):
        """获取配置项"""
        config = self.settings if section == "settings" else self.strategies
        keys = key.split(".")
        value = config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def get_database_path(self) -> str:
        """获取数据库路径"""
        db_path = self.get("database.path")
        if not os.path.isabs(db_path):
            db_path = os.path.join(self.base_dir, db_path)
        # 确保目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        return db_path

    def get_strategy_config(self, strategy_name: str) -> Dict[str, Any]:
        """获取策略配置"""
        strategies = self.strategies.get("strategies", {})
        return strategies.get(strategy_name, {})

    def get_enabled_strategies(self) -> Dict[str, Dict[str, Any]]:
        """获取所有启用的策略"""
        strategies = self.strategies.get("strategies", {})
        return {
            name: config
            for name, config in strategies.items()
            if config.get("enabled", False)
        }


# 全局配置实例
config = Config()
