"""
富途牛牛证券交易接口
通过本地 OpenD 网关连接富途服务器，支持模拟和真实账户
需提前启动富途 OpenD 网关（富途官方桌面客户端内置）
"""
from typing import Dict, Optional, List
import logging
import os
from datetime import datetime

from .futu_config_loader import FutuConfigLoader
from .order_formatter import (
    print_order_submitting_display,
    print_order_submitted_display,
    print_order_modify_table,
    print_order_cancel_table,
    print_orders_summary_table,
    print_account_info_table,
    print_positions_table,
    print_success_message,
    print_error_message,
    print_warning_message,
    print_order_failed_table,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Symbol 转换工具函数
# ---------------------------------------------------------------------------

def convert_to_futu_symbol(internal_symbol: str) -> str:
    """
    将内部格式 symbol 转换为富途格式

    内部格式: AAPL260207C250000.US  （ticker + YYMMDD + C/P + strike*1000 + .US）
    富途格式:  US.AAPL260207C250000

    同样适用于正股: AAPL.US -> US.AAPL
    """
    base = internal_symbol.removesuffix(".US")
    return f"US.{base}"


def convert_from_futu_symbol(futu_symbol: str) -> str:
    """
    将富途格式 symbol 转换回内部格式

    富途格式:  US.AAPL260207C250000
    内部格式:  AAPL260207C250000.US
    """
    base = futu_symbol.removeprefix("US.")
    return f"{base}.US"


# ---------------------------------------------------------------------------
# FutuBroker 主类
# ---------------------------------------------------------------------------

class FutuBroker:
    """富途牛牛证券交易接口（与 LongPortBroker 接口完全兼容）"""

    def __init__(self, config_loader: Optional[FutuConfigLoader] = None):
        """
        初始化富途交易接口

        Args:
            config_loader: 配置加载器，不传则从环境变量自动加载
        """
        if config_loader is None:
            config_loader = FutuConfigLoader()

        self.config_loader = config_loader
        self.dry_run = config_loader.is_dry_run()
        self.auto_trade = config_loader.is_auto_trade_enabled()
        self.is_paper = config_loader.is_paper_mode()
        self._trd_env = config_loader.get_trd_env()
        self._host = config_loader.get_host()
        self._port = config_loader.get_port()

        self._quote_ctx = None
        self._trade_ctx = None
        self._connect()

    def _connect(self):
        """建立到 OpenD 网关的连接"""
        try:
            from futu import OpenQuoteContext, OpenUSTradeContext
            self._quote_ctx = OpenQuoteContext(host=self._host, port=self._port)
            self._trade_ctx = OpenUSTradeContext(host=self._host, port=self._port)
            logger.info(f"富途 OpenD 连接成功: {self._host}:{self._port}")
        except Exception as e:
            logger.error(f"富途 OpenD 连接失败: {e}")
            raise

    def _check_ret(self, ret_code, data, operation: str):
        """统一检查富途 API 返回码，失败时抛出异常"""
        from futu import RET_OK
        if ret_code != RET_OK:
            raise RuntimeError(f"富途 API 调用失败 [{operation}]: {data}")

    def _mock_order_response(
        self, symbol: str, side: str, quantity: int, price: Optional[float]
    ) -> Dict:
        """生成模拟订单响应（dry_run 或 auto_trade=false 时使用）"""
        return {
            "order_id": f"MOCK_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "status": "mock",
            "submitted_at": datetime.now().isoformat(),
            "mode": "dry_run",
        }

    def close(self) -> None:
        """释放 OpenD 连接"""
        for ctx in (self._quote_ctx, self._trade_ctx):
            if ctx is not None:
                try:
                    ctx.close()
                except Exception as e:
                    logger.debug("关闭富途连接时忽略: %s", e)
        self._quote_ctx = None
        self._trade_ctx = None
        logger.debug("富途连接已释放")

    # ------------------------------------------------------------------
    # 下单相关
    # ------------------------------------------------------------------

    def submit_option_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: Optional[float] = None,
        order_type: str = "LIMIT",
        remark: str = "",
        trigger_price: Optional[float] = None,
        trailing_percent: Optional[float] = None,
        trailing_amount: Optional[float] = None,
        instruction_timestamp: Optional[str] = None,
    ) -> Dict:
        """
        提交期权订单

        Args:
            symbol: 内部期权代码，如 "AAPL260207C250000.US"
            side: 买卖方向 "BUY" / "SELL"
            quantity: 合约数量
            price: 限价单价格
            order_type: "LIMIT" / "MARKET" / "LIT"
            remark: 备注
            trigger_price: 触发价格（LIT 条件单）
            trailing_percent: 跟踪止损百分比
            trailing_amount: 跟踪止损金额
            instruction_timestamp: 指令时间戳（用于展示）

        Returns:
            订单信息字典
        """
        if not self.auto_trade:
            logger.warning("⚠️  自动交易未启用，跳过订单提交")
            return self._mock_order_response(symbol, side, quantity, price)

        if self.dry_run:
            logger.info(f"🧪 [DRY RUN] 模拟下单: {symbol} {side} {quantity} @ {price}")
            return self._mock_order_response(symbol, side, quantity, price)

        try:
            from futu import TrdSide, OrderType as FutuOrderType, TrdEnv

            futu_symbol = convert_to_futu_symbol(symbol)
            trd_side = TrdSide.BUY if side.upper() == "BUY" else TrdSide.SELL

            if order_type.upper() == "MARKET":
                futu_order_type = FutuOrderType.MARKET
                submit_price = 0.0
            else:
                futu_order_type = FutuOrderType.NORMAL
                if price is None:
                    raise ValueError("限价单必须提供价格")
                submit_price = float(price)

            order_info = {
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": float(price) if price else None,
                "status": "submitted",
                "submitted_at": datetime.now().isoformat(),
                "mode": "paper" if self.is_paper else "real",
                "trigger_price": trigger_price,
                "trailing_percent": trailing_percent,
                "trailing_amount": trailing_amount,
                "remark": remark or f"Auto trade via Futu - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "instruction_timestamp": instruction_timestamp,
            }

            print_order_submitting_display(order_info)

            ret_code, data = self._trade_ctx.place_order(
                code=futu_symbol,
                price=submit_price,
                qty=quantity,
                trd_side=trd_side,
                order_type=futu_order_type,
                trd_env=self._trd_env,
                remark=order_info["remark"],
            )
            self._check_ret(ret_code, data, "place_order")

            order_id = str(data["orderid"].iloc[0]) if hasattr(data, "iloc") else str(data)
            order_info["order_id"] = order_id
            return order_info

        except ValueError as e:
            failed_order = {
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": float(price) if price else None,
                "mode": "paper" if self.is_paper else "real",
                "remark": remark,
            }
            print_order_failed_table(failed_order, str(e))
            logger.error(f"❌ 订单提交失败: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ 订单提交失败: {e}")
            raise

    def submit_stock_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: Optional[float] = None,
        order_type: str = "LIMIT",
        remark: str = "",
        trigger_price: Optional[float] = None,
        trailing_percent: Optional[float] = None,
        trailing_amount: Optional[float] = None,
    ) -> Dict:
        """
        提交正股订单

        Args:
            symbol: 内部股票代码，如 "AAPL.US"
            side: 买卖方向 "BUY" / "SELL"
            quantity: 股数
            price: 限价单价格
            order_type: "LIMIT" / "MARKET"
            remark: 备注

        Returns:
            订单信息字典
        """
        if not self.auto_trade:
            logger.warning("⚠️  自动交易未启用，跳过订单提交")
            mock = self._mock_order_response(symbol, side, quantity, price)
            print_order_submitted_display(mock, multiplier=1)
            return mock

        if self.dry_run:
            logger.info(f"🧪 [DRY RUN] 模拟下单: {symbol} {side} {quantity} @ {price}")
            mock = self._mock_order_response(symbol, side, quantity, price)
            print_order_submitted_display(mock, multiplier=1)
            return mock

        try:
            from futu import TrdSide, OrderType as FutuOrderType

            futu_symbol = convert_to_futu_symbol(symbol)
            trd_side = TrdSide.BUY if side.upper() == "BUY" else TrdSide.SELL

            if order_type.upper() == "MARKET":
                futu_order_type = FutuOrderType.MARKET
                submit_price = 0.0
            else:
                futu_order_type = FutuOrderType.NORMAL
                if price is None:
                    raise ValueError("限价单必须提供价格")
                submit_price = float(price)

            order_info = {
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": float(price) if price else None,
                "status": "submitted",
                "submitted_at": datetime.now().isoformat(),
                "mode": "paper" if self.is_paper else "real",
                "remark": remark or f"Auto trade via Futu - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            }

            ret_code, data = self._trade_ctx.place_order(
                code=futu_symbol,
                price=submit_price,
                qty=quantity,
                trd_side=trd_side,
                order_type=futu_order_type,
                trd_env=self._trd_env,
                remark=order_info["remark"],
            )
            self._check_ret(ret_code, data, "place_order")

            order_id = str(data["orderid"].iloc[0]) if hasattr(data, "iloc") else str(data)
            order_info["order_id"] = order_id
            print_order_submitted_display(order_info, multiplier=1)
            return order_info

        except Exception as e:
            logger.error(f"❌ 正股订单提交失败: {e}")
            raise

    def cancel_order(self, order_id: str) -> Dict:
        """撤销订单"""
        if not self.auto_trade:
            logger.warning("⚠️  自动交易未启用，跳过订单撤销")
            return {"order_id": order_id, "status": "skipped", "reason": "auto_trade_disabled"}

        if self.dry_run:
            logger.info(f"🧪 [DRY RUN] 模拟撤销订单: {order_id}")
            return {"order_id": order_id, "status": "mock_cancelled", "mode": "dry_run"}

        try:
            from futu import ModifyOrderOp

            orders = self.get_today_orders()
            target_order = next((o for o in orders if o.get("order_id") == order_id), None)

            ret_code, data = self._trade_ctx.modify_order(
                modify_order_op=ModifyOrderOp.CANCEL,
                order_id=order_id,
                qty=0,
                price=0,
                trd_env=self._trd_env,
            )
            self._check_ret(ret_code, data, "cancel_order")

            result = {
                "order_id": order_id,
                "status": "cancelled",
                "cancelled_at": datetime.now().isoformat(),
                "mode": "paper" if self.is_paper else "real",
            }
            if target_order:
                result.update({
                    "symbol": target_order.get("symbol"),
                    "side": target_order.get("side"),
                    "quantity": target_order.get("quantity"),
                    "price": target_order.get("price"),
                })

            print_success_message("订单撤销成功")
            print_order_cancel_table(result, "撤销订单详情")
            return result

        except Exception as e:
            print_error_message(f"订单撤销失败: {e}")
            raise

    def replace_order(
        self,
        order_id: str,
        quantity: int,
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        trailing_percent: Optional[float] = None,
        trailing_amount: Optional[float] = None,
        remark: str = "",
    ) -> Dict:
        """修改订单"""
        if not self.auto_trade:
            logger.warning("⚠️  自动交易未启用，跳过订单修改")
            return {"order_id": order_id, "status": "skipped", "reason": "auto_trade_disabled"}

        if self.dry_run:
            logger.info(f"🧪 [DRY RUN] 模拟修改订单: {order_id}")
            return {
                "order_id": order_id,
                "quantity": quantity,
                "price": price,
                "status": "mock_replaced",
                "mode": "dry_run",
            }

        try:
            from futu import ModifyOrderOp

            orders = self.get_today_orders()
            old_order = next((o for o in orders if o.get("order_id") == order_id), None)
            if not old_order:
                raise ValueError(f"未找到订单: {order_id}")

            submit_price = price if price is not None else old_order.get("price", 0)

            ret_code, data = self._trade_ctx.modify_order(
                modify_order_op=ModifyOrderOp.NORMAL,
                order_id=order_id,
                qty=quantity,
                price=float(submit_price) if submit_price else 0,
                trd_env=self._trd_env,
            )
            self._check_ret(ret_code, data, "replace_order")

            new_values = {
                "quantity": quantity,
                "price": float(price) if price is not None else old_order.get("price"),
                "trigger_price": trigger_price,
                "trailing_percent": trailing_percent,
                "trailing_amount": trailing_amount,
            }
            result = {
                "order_id": order_id,
                "quantity": quantity,
                "price": float(price) if price else None,
                "status": "replaced",
                "replaced_at": datetime.now().isoformat(),
                "mode": "paper" if self.is_paper else "real",
            }

            print_success_message("订单修改成功")
            print_order_modify_table(order_id, old_order, new_values, "订单修改详情")
            return result

        except Exception as e:
            logger.error("订单修改失败: %s", e)
            raise

    # ------------------------------------------------------------------
    # 查询相关
    # ------------------------------------------------------------------

    def get_today_orders(self) -> list:
        """获取当日订单"""
        try:
            ret_code, data = self._trade_ctx.order_list_query(trd_env=self._trd_env)
            self._check_ret(ret_code, data, "order_list_query")

            orders = []
            for _, row in data.iterrows():
                orders.append({
                    "order_id": str(row.get("order_id", "")),
                    "symbol": convert_from_futu_symbol(str(row.get("code", ""))),
                    "side": "BUY" if str(row.get("trd_side", "")).upper() in ("BUY", "TRDSIDE.BUY") else "SELL",
                    "quantity": int(row.get("qty", 0)),
                    "executed_quantity": int(row.get("dealt_qty", 0)),
                    "price": float(row.get("price", 0)) or None,
                    "status": str(row.get("order_status", "")),
                    "submitted_at": str(row.get("create_time", "")),
                })
            return orders
        except Exception as e:
            logger.error(f"获取当日订单失败: {e}")
            return []

    def get_history_orders(self, start_at: datetime, end_at: datetime) -> list:
        """获取历史成交订单"""
        try:
            from futu import OrderStatus as FutuOrderStatus
            ret_code, data = self._trade_ctx.history_order_list_query(
                status_filter_list=[FutuOrderStatus.FILLED_ALL],
                start=start_at.strftime("%Y-%m-%d %H:%M:%S"),
                end=end_at.strftime("%Y-%m-%d %H:%M:%S"),
                trd_env=self._trd_env,
            )
            self._check_ret(ret_code, data, "history_order_list_query")

            orders = []
            for _, row in data.iterrows():
                orders.append({
                    "order_id": str(row.get("order_id", "")),
                    "symbol": convert_from_futu_symbol(str(row.get("code", ""))),
                    "side": "BUY" if str(row.get("trd_side", "")).upper() in ("BUY", "TRDSIDE.BUY") else "SELL",
                    "quantity": int(row.get("qty", 0)),
                    "executed_quantity": int(row.get("dealt_qty", 0)),
                    "price": float(row.get("price", 0)) or None,
                    "status": str(row.get("order_status", "")),
                    "submitted_at": str(row.get("create_time", "")),
                })
            return orders
        except Exception as e:
            logger.debug(f"获取历史订单失败: {e}")
            return []

    def get_positions(self) -> list:
        """获取持仓信息"""
        try:
            ret_code, data = self._trade_ctx.position_list_query(trd_env=self._trd_env)
            self._check_ret(ret_code, data, "position_list_query")

            positions = []
            for _, row in data.iterrows():
                positions.append({
                    "symbol": convert_from_futu_symbol(str(row.get("code", ""))),
                    "symbol_name": str(row.get("stock_name", "")),
                    "quantity": float(row.get("qty", 0)),
                    "available_quantity": float(row.get("can_sell_qty", 0)),
                    "cost_price": float(row.get("cost_price", 0)),
                    "currency": str(row.get("currency", "USD")),
                    "market": "US",
                })
            return positions
        except Exception as e:
            logger.error(f"获取持仓失败: {e}")
            return []

    def get_account_balance(self) -> dict:
        """获取账户余额"""
        try:
            ret_code, data = self._trade_ctx.accinfo_query(trd_env=self._trd_env)
            self._check_ret(ret_code, data, "accinfo_query")

            row = data.iloc[0]
            available_cash = float(row.get("cash", 0))
            net_assets = float(row.get("total_assets", 0))
            market_val = float(row.get("market_val", 0))
            return {
                "available_cash": available_cash,
                "cash": available_cash,
                "net_assets": net_assets,
                "total_cash": net_assets,
                "currency": "USD",
                "mode": "paper" if self.is_paper else "real",
            }
        except Exception as e:
            logger.error(f"获取账户余额失败: {e}")
            return {}

    def get_option_quote(self, symbols: List[str]) -> List[Dict]:
        """获取期权实时报价"""
        try:
            futu_symbols = [convert_to_futu_symbol(s) for s in symbols]
            ret_code, data = self._quote_ctx.get_market_snapshot(futu_symbols)
            self._check_ret(ret_code, data, "get_market_snapshot")

            quotes = []
            for _, row in data.iterrows():
                quotes.append({
                    "symbol": convert_from_futu_symbol(str(row.get("code", ""))),
                    "last_done": float(row.get("last_price", 0)),
                    "open": float(row.get("open_price", 0)),
                    "high": float(row.get("high_price", 0)),
                    "low": float(row.get("low_price", 0)),
                    "volume": int(row.get("volume", 0)),
                    "bid_price": float(row.get("bid_price", 0)),
                    "ask_price": float(row.get("ask_price", 0)),
                })
            return quotes
        except Exception as e:
            logger.error(f"获取期权报价失败: {e}")
            return []

    def get_stock_quote(self, symbols: List[str]) -> List[Dict]:
        """获取正股实时报价"""
        try:
            futu_symbols = [convert_to_futu_symbol(s) for s in symbols]
            ret_code, data = self._quote_ctx.get_market_snapshot(futu_symbols)
            self._check_ret(ret_code, data, "get_market_snapshot")

            quotes = []
            for _, row in data.iterrows():
                quotes.append({
                    "symbol": convert_from_futu_symbol(str(row.get("code", ""))),
                    "last_done": float(row.get("last_price", 0)),
                    "prev_close": float(row.get("prev_close_price", 0)),
                    "open": float(row.get("open_price", 0)),
                    "high": float(row.get("high_price", 0)),
                    "low": float(row.get("low_price", 0)),
                    "volume": int(row.get("volume", 0)),
                    "turnover": float(row.get("turnover", 0)),
                    "timestamp": str(row.get("update_time", "")),
                })
            return quotes
        except Exception as e:
            logger.error(f"获取正股报价失败: {e}")
            return []

    def get_option_expiry_dates(self, symbol: str) -> List[str]:
        """
        获取期权到期日列表

        Returns:
            到期日列表，格式为 YYMMDD 字符串，如 ["260207", "260214"]
        """
        try:
            futu_symbol = convert_to_futu_symbol(symbol)
            ret_code, data = self._quote_ctx.get_option_expiration_date(futu_symbol)
            self._check_ret(ret_code, data, "get_option_expiration_date")

            expiry_dates = []
            for _, row in data.iterrows():
                # Futu 返回 YYYY-MM-DD 格式，转换为 YYMMDD
                date_str = str(row.get("strikeTime", ""))
                if date_str and len(date_str) >= 10:
                    try:
                        d = datetime.strptime(date_str[:10], "%Y-%m-%d")
                        expiry_dates.append(d.strftime("%y%m%d"))
                    except ValueError:
                        pass

            logger.info(f"获取 {symbol} 期权到期日: {len(expiry_dates)} 个")
            return expiry_dates
        except Exception as e:
            logger.error(f"获取期权到期日失败: {e}")
            return []

    def get_option_chain_info(self, symbol: str, expiry_date: str) -> Dict:
        """
        获取指定到期日的期权链信息

        Args:
            symbol: 内部标的代码，如 "AAPL.US"
            expiry_date: 到期日，格式 YYMMDD，如 "260207"

        Returns:
            期权链信息字典，含 strike_prices / call_symbols / put_symbols
        """
        try:
            futu_symbol = convert_to_futu_symbol(symbol)
            # 转换 YYMMDD -> YYYY-MM-DD
            date_obj = datetime.strptime(expiry_date, "%y%m%d")
            date_str = date_obj.strftime("%Y-%m-%d")

            ret_code, data = self._quote_ctx.get_option_chain(
                code=futu_symbol,
                start=date_str,
                end=date_str,
            )
            self._check_ret(ret_code, data, "get_option_chain")

            option_chain = {
                "symbol": symbol,
                "expiry_date": expiry_date,
                "strike_prices": [],
                "call_symbols": [],
                "put_symbols": [],
            }

            for _, row in data.iterrows():
                strike = float(row.get("strike_price", 0))
                call_code = str(row.get("call_code", ""))
                put_code = str(row.get("put_code", ""))
                if strike:
                    option_chain["strike_prices"].append(strike)
                    option_chain["call_symbols"].append(
                        convert_from_futu_symbol(call_code) if call_code else ""
                    )
                    option_chain["put_symbols"].append(
                        convert_from_futu_symbol(put_code) if put_code else ""
                    )

            logger.info(
                f"获取 {symbol} {expiry_date} 期权链: "
                f"{len(option_chain['strike_prices'])} 个行权价"
            )
            return option_chain
        except Exception as e:
            logger.error(f"获取期权链信息失败: {e}")
            return {}

    # ------------------------------------------------------------------
    # 展示相关（复用 order_formatter）
    # ------------------------------------------------------------------

    def show_account_info(self):
        """以表格形式展示账户信息"""
        try:
            balance_info = self.get_account_balance()
            positions = self.get_positions()
            position_value = sum(
                pos.get("quantity", 0) * pos.get("cost_price", 0)
                for pos in positions
            )
            account_info = {**balance_info, "position_value": position_value}
            mode_display = "🧪 模拟账户" if self.is_paper else "💰 真实账户"
            print_account_info_table(account_info, title=f"账户信息 ({mode_display}) [富途]")
        except Exception as e:
            logger.error(f"展示账户信息失败: {e}")
            print_error_message(f"展示账户信息失败: {e}")

    def show_positions(self):
        """以表格形式展示持仓信息"""
        try:
            positions = self.get_positions()
            if not positions:
                print_warning_message("无持仓")
                return
            mode_display = "🧪 模拟账户" if self.is_paper else "💰 真实账户"
            print_positions_table(positions, title=f"持仓信息 ({mode_display}) [富途]")
        except Exception as e:
            logger.error(f"展示持仓信息失败: {e}")
            print_error_message(f"展示持仓信息失败: {e}")

    def show_today_orders(self):
        """以表格形式展示当日订单"""
        try:
            orders = self.get_today_orders()
            if not orders:
                print_warning_message("无当日订单")
                return
            mode_display = "🧪 模拟账户" if self.is_paper else "💰 真实账户"
            print_orders_summary_table(orders, title=f"当日订单 ({mode_display}) [富途]")
        except Exception as e:
            logger.error(f"展示当日订单失败: {e}")
            print_error_message(f"展示当日订单失败: {e}")
