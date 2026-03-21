"""
证券交易模块
支持长桥（LongPort）和富途牛牛（Futu）双券商，可通过 BROKER_TYPE 环境变量切换
"""

from .config_loader import LongPortConfigLoader, load_longport_config
from .longport_broker import (
    LongPortBroker,
    convert_to_longport_symbol,
    validate_option_expiry,
    calculate_quantity
)
from .futu_config_loader import FutuConfigLoader, load_futu_config
from .futu_broker import FutuBroker, convert_to_futu_symbol, convert_from_futu_symbol
from .position_manager import (
    PositionManager,
    Position,
    create_position_from_order
)
from .auto_trader import AutoTrader

__all__ = [
    'LongPortConfigLoader',
    'load_longport_config',
    'LongPortBroker',
    'convert_to_longport_symbol',
    'validate_option_expiry',
    'calculate_quantity',
    'FutuConfigLoader',
    'load_futu_config',
    'FutuBroker',
    'convert_to_futu_symbol',
    'convert_from_futu_symbol',
    'PositionManager',
    'Position',
    'create_position_from_order',
    'AutoTrader',
]
