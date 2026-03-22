"""
WhopScraper Web Dashboard
只读界面：从 data/ 目录读取 JSON 数据文件并展示，无需连接任何券商 API。

启动方式:
    python web/app.py
    FLASK_PORT=5000 python web/app.py

数据模式:
    DEMO_MODE=true   使用内置假数据（默认）
    DEMO_MODE=false  使用真实 data/ 目录文件
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, render_template, jsonify, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "whopscraper-dashboard-secret")

# 项目根目录（web/ 的上级目录）
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Demo 数据（内置假数据）
# ---------------------------------------------------------------------------

DEMO_POSITIONS = {
    "NVDA260320C150000.US": {
        "symbol": "NVDA260320C150000.US", "ticker": "NVDA", "option_type": "CALL",
        "strike": 150.0, "expiry": "260320", "quantity": 15, "available_quantity": 15,
        "avg_cost": 5.20, "current_price": 7.85, "market_value": 11775.0,
        "unrealized_pnl": 3975.0, "unrealized_pnl_pct": 50.96,
        "stop_loss_price": 3.20, "take_profit_price": 10.0,
        "open_time": "2026-03-10T09:30:00", "updated_at": "2026-03-21T16:00:00",
    },
    "TSLA260418P250000.US": {
        "symbol": "TSLA260418P250000.US", "ticker": "TSLA", "option_type": "PUT",
        "strike": 250.0, "expiry": "260418", "quantity": 10, "available_quantity": 10,
        "avg_cost": 8.50, "current_price": 6.20, "market_value": 6200.0,
        "unrealized_pnl": -2300.0, "unrealized_pnl_pct": -27.06,
        "stop_loss_price": 5.00, "take_profit_price": None,
        "open_time": "2026-03-15T10:15:00", "updated_at": "2026-03-21T16:00:00",
    },
    "AAPL260320C220000.US": {
        "symbol": "AAPL260320C220000.US", "ticker": "AAPL", "option_type": "CALL",
        "strike": 220.0, "expiry": "260320", "quantity": 20, "available_quantity": 20,
        "avg_cost": 3.10, "current_price": 3.45, "market_value": 6900.0,
        "unrealized_pnl": 700.0, "unrealized_pnl_pct": 11.29,
        "stop_loss_price": 1.90, "take_profit_price": 5.0,
        "open_time": "2026-03-18T14:00:00", "updated_at": "2026-03-21T16:00:00",
    },
}

DEMO_SIGNALS = [
    {
        "origin": {"domID": "demo_001", "content": "NVDA 150c 3/20 入场价 5.2 小仓位", "timestamp": "2026-03-10 09:28:00.000"},
        "parsed": {"instruction_type": "BUY", "ticker": "NVDA", "option_type": "CALL", "strike": 150.0, "expiry": "260320", "price": 5.2},
        "status": "✅",
    },
    {
        "origin": {"domID": "demo_002", "content": "止损设3.2", "timestamp": "2026-03-10 09:30:00.000"},
        "parsed": {"instruction_type": "MODIFY", "ticker": "NVDA", "option_type": "CALL", "strike": 150.0, "expiry": "260320", "price": None},
        "status": "✅",
    },
    {
        "origin": {"domID": "demo_003", "content": "TSLA 250p 4/18 入场价 8.5", "timestamp": "2026-03-15 10:14:00.000"},
        "parsed": {"instruction_type": "BUY", "ticker": "TSLA", "option_type": "PUT", "strike": 250.0, "expiry": "260418", "price": 8.5},
        "status": "✅",
    },
    {
        "origin": {"domID": "demo_004", "content": "TSLA 减三分之一", "timestamp": "2026-03-16 11:00:00.000"},
        "parsed": {"instruction_type": "SELL", "ticker": "TSLA", "option_type": "PUT", "strike": 250.0, "expiry": "260418", "price": None},
        "status": "✅",
    },
    {
        "origin": {"domID": "demo_005", "content": "今天市场波动较大，注意风控", "timestamp": "2026-03-17 09:15:00.000"},
        "parsed": None,
        "reason": "无关信息",
        "status": "❌",
    },
    {
        "origin": {"domID": "demo_006", "content": "AAPL 220c 3/20 入场价 3.1", "timestamp": "2026-03-18 13:58:00.000"},
        "parsed": {"instruction_type": "BUY", "ticker": "AAPL", "option_type": "CALL", "strike": 220.0, "expiry": "260320", "price": 3.1},
        "status": "✅",
    },
]

DEMO_TRADE_RECORDS = [
    {"symbol": "NVDA260320C150000.US", "side": "BUY", "quantity": 15, "price": 5.20, "time": "2026-03-10 09:30:15", "remark": "Auto trade via Futu"},
    {"symbol": "TSLA260418P250000.US", "side": "BUY", "quantity": 10, "price": 8.50, "time": "2026-03-15 10:15:30", "remark": "Auto trade via Futu"},
    {"symbol": "TSLA260418P250000.US", "side": "SELL", "quantity": 3, "price": 9.10, "time": "2026-03-16 11:05:00", "remark": "减三分之一"},
    {"symbol": "AAPL260320C220000.US", "side": "BUY", "quantity": 20, "price": 3.10, "time": "2026-03-18 14:00:45", "remark": "Auto trade via Futu"},
]

# ---------------------------------------------------------------------------
# 数据加载
# ---------------------------------------------------------------------------

def _is_demo_mode() -> bool:
    """判断当前是否为 Demo 模式（session 优先，其次环境变量，默认 true）"""
    if "demo_mode" in session:
        return session["demo_mode"]
    return os.getenv("DEMO_MODE", "false").lower() != "false"


def _load_json(relative_path: str, default):
    full_path = PROJECT_ROOT / relative_path
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _get_positions():
    if _is_demo_mode():
        data = DEMO_POSITIONS
    else:
        data = _load_json("data/positions.json", {})
    positions = list(data.values()) if isinstance(data, dict) else data
    positions.sort(key=lambda p: p.get("market_value", 0), reverse=True)
    return positions


def _get_stock_positions():
    if _is_demo_mode():
        return []
    data = _load_json("data/stock_positions.json", {})
    positions = list(data.values()) if isinstance(data, dict) else data
    positions.sort(key=lambda p: p.get("market_value", 0), reverse=True)
    return positions


def _get_signals():
    if _is_demo_mode():
        return list(reversed(DEMO_SIGNALS))
    data = _load_json("data/parsed_message.json", [])
    return list(reversed(data)) if isinstance(data, list) else []


def _get_trade_records():
    if _is_demo_mode():
        return list(reversed(DEMO_TRADE_RECORDS))
    data = _load_json("data/trade_records.json", {})
    flat = []
    if isinstance(data, dict):
        for symbol, records in data.items():
            if isinstance(records, list):
                for r in records:
                    flat.append({**r, "symbol": r.get("symbol", symbol)})
    elif isinstance(data, list):
        flat = data
    flat.sort(key=lambda x: x.get("time", x.get("submitted_at", "")), reverse=True)
    return flat

# ---------------------------------------------------------------------------
# 切换数据模式
# ---------------------------------------------------------------------------

@app.route("/toggle-mode", methods=["POST"])
def toggle_mode():
    session["demo_mode"] = not _is_demo_mode()
    return redirect(request.referrer or url_for("index"))

# ---------------------------------------------------------------------------
# 页面路由
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    positions = _get_positions()
    total_market_value = sum(p.get("market_value", 0) for p in positions)
    total_unrealized_pnl = sum(p.get("unrealized_pnl", 0) for p in positions)
    cost_basis = total_market_value - total_unrealized_pnl
    total_unrealized_pnl_pct = (total_unrealized_pnl / cost_basis * 100) if cost_basis else 0.0
    recent_signals = _get_signals()[:10]
    return render_template(
        "index.html",
        positions=positions[:5],
        total_positions=len(positions),
        total_market_value=total_market_value,
        total_unrealized_pnl=total_unrealized_pnl,
        total_unrealized_pnl_pct=total_unrealized_pnl_pct,
        recent_signals=recent_signals,
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        demo_mode=_is_demo_mode(),
    )


@app.route("/positions")
def positions():
    return render_template(
        "positions.html",
        positions=_get_positions(),
        stock_positions=_get_stock_positions(),
        demo_mode=_is_demo_mode(),
    )


@app.route("/orders")
def orders():
    return render_template("orders.html", orders=_get_trade_records(), demo_mode=_is_demo_mode())


@app.route("/signals")
def signals():
    return render_template("signals.html", signals=_get_signals(), demo_mode=_is_demo_mode())


# ---------------------------------------------------------------------------
# JSON API
# ---------------------------------------------------------------------------

@app.route("/api/positions")
def api_positions():
    return jsonify(_get_positions())


@app.route("/api/signals")
def api_signals():
    return jsonify(_get_signals()[:50])


@app.route("/api/orders")
def api_orders():
    return jsonify(_get_trade_records()[:50])


@app.route("/api/summary")
def api_summary():
    positions = _get_positions()
    total_market_value = sum(p.get("market_value", 0) for p in positions)
    total_unrealized_pnl = sum(p.get("unrealized_pnl", 0) for p in positions)
    return jsonify({
        "total_positions": len(positions),
        "total_market_value": round(total_market_value, 2),
        "total_unrealized_pnl": round(total_unrealized_pnl, 2),
        "total_signals": len(_get_signals()),
        "demo_mode": _is_demo_mode(),
        "updated_at": datetime.now().isoformat(),
    })


if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    mode = "演示数据" if os.getenv("DEMO_MODE", "false").lower() not in ("false", "0", "no") else "真实数据"
    print(f"\n  WhopScraper Dashboard  [{mode}]")
    print(f"  访问地址: http://localhost:{port}")
    print(f"  数据目录: {PROJECT_ROOT / 'data'}")
    print(f"  切换数据: 点击界面右上角 Demo/Real 开关\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
