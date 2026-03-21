"""
富途牛牛 OpenD 配置加载器
支持模拟账户和真实账户的自动切换
需要本地运行 OpenD 网关（富途官方客户端）
"""
import os
from typing import Optional
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()


class FutuConfigLoader:
    """富途配置加载器"""

    PAPER_MODE = "paper"  # 模拟账户
    REAL_MODE = "real"    # 真实账户

    def __init__(self, mode: Optional[str] = None):
        """
        初始化配置加载器

        Args:
            mode: 账户模式 'paper' 或 'real'，如果不指定则从环境变量读取
        """
        self.mode = mode or os.getenv("FUTU_MODE", self.PAPER_MODE)
        self._validate_mode()

    def _validate_mode(self):
        """验证账户模式"""
        if self.mode not in [self.PAPER_MODE, self.REAL_MODE]:
            raise ValueError(
                f"Invalid FUTU_MODE: {self.mode}. "
                f"Must be '{self.PAPER_MODE}' or '{self.REAL_MODE}'"
            )

    def get_host(self) -> str:
        """获取 OpenD 网关主机地址"""
        return os.getenv("FUTU_HOST", "127.0.0.1")

    def get_port(self) -> int:
        """获取 OpenD 网关端口"""
        return int(os.getenv("FUTU_PORT", "11111"))

    def get_trd_env(self):
        """获取富途 TrdEnv 枚举值"""
        from futu import TrdEnv
        return TrdEnv.SIMULATE if self.is_paper_mode() else TrdEnv.REAL

    def is_paper_mode(self) -> bool:
        """是否为模拟账户模式"""
        return self.mode == self.PAPER_MODE

    def is_real_mode(self) -> bool:
        """是否为真实账户模式"""
        return self.mode == self.REAL_MODE

    def is_auto_trade_enabled(self) -> bool:
        """是否启用自动交易"""
        return os.getenv("FUTU_AUTO_TRADE", "false").lower() == "true"

    def is_dry_run(self) -> bool:
        """是否为模拟运行模式（不实际下单）"""
        return os.getenv("FUTU_DRY_RUN", "true").lower() == "true"


def load_futu_config(mode: Optional[str] = None) -> FutuConfigLoader:
    """
    快捷函数：创建富途配置加载器

    Args:
        mode: 账户模式 'paper' 或 'real'

    Returns:
        FutuConfigLoader 实例

    Example:
        >>> loader = load_futu_config()
        >>> loader = load_futu_config("paper")
    """
    return FutuConfigLoader(mode)
