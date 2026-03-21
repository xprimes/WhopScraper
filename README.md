# 期权信号抓取器 + 自动交易系统 v2.6.15

使用 Playwright 实时监控 Whop 页面，解析期权交易信号，并通过 **富途牛牛（Futu）** 或长桥证券 API 自动执行交易，含完整持仓管理、风险控制和 Web 可视化看板。

## ⚠️ 注意
本项目对于指令的解析完全基于文本正则匹配和历史消息关联，没有使用任何大模型，因此对于新的自然语言描述格式，可能会存在不识别的情况；

## 效果展示
### 1. 程序启动
![](./images/terminal_1.png)

### 2. 更新配置和账户信息
![](./images/terminal_2.png)

### 3. 监听消息
![](./images/terminal_3.png)

### 4. 分析股票做T情况
![](./images/terminal_4.png)

## 安装依赖

```bash
# 安装 Python 依赖（需 Python 3.8+）
pip install -r requirements.txt

# 安装 Playwright 浏览器
python -m playwright install chromium
```

## 配置

> 💡 **统一配置管理**：所有配置项都在 `.env` 文件中设置，无需修改代码。

### 配置步骤

1. 复制配置模板：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，填入对应凭据（默认使用富途，详见下方）。

---

## 富途牛牛配置（默认）

富途不需要 App Key / Secret，通过本地 **OpenD 网关**进行通信，**无需任何密钥**。

### 1. 启动 OpenD
- 打开富途牛牛桌面客户端，登录账号（客户端内置 OpenD，登录即启动）
- 或从 [富途开发者中心](https://openapi.futunn.com/) 单独下载命令行版 OpenD

### 2. 验证连接（可选）
```bash
python -c "
from futu import OpenQuoteContext
ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
print(ctx.get_global_state())
ctx.close()
"
```

### 3. `.env` 富途配置
```bash
# 经纪商选择（默认富途）
BROKER_TYPE=futu

# OpenD 网关地址（默认本机）
FUTU_HOST=127.0.0.1
FUTU_PORT=11111

# 账户模式
FUTU_MODE=paper              # paper=模拟账户, real=真实账户

# 交易模式
FUTU_AUTO_TRADE=false        # 是否启用自动交易
FUTU_DRY_RUN=true            # true=仅打印不下单（建议先开启测试）
```

---

## 长桥 OpenAPI 配置（可选）

如需切换到长桥，设置 `BROKER_TYPE=longport`，并填入 API 凭据。

获取 AppKey / AppSecret / AccessToken：[https://open.longbridge.com/zh-CN/](https://open.longbridge.com/zh-CN/)

> 注意：通过 API 下单需购买对应的 OpenAPI 行情权限。

```bash
# 切换到长桥
BROKER_TYPE=longport

# 账户模式
LONGPORT_MODE=paper            # paper=模拟账户, real=真实账户

# API 凭据（模拟账户）
LONGPORT_PAPER_APP_KEY=xxxx
LONGPORT_PAPER_APP_SECRET=xxxx
LONGPORT_PAPER_ACCESS_TOKEN=xxxx

# API 凭据（真实账户）
LONGPORT_REAL_APP_KEY=xxxx
LONGPORT_REAL_APP_SECRET=xxxx
LONGPORT_REAL_ACCESS_TOKEN=xxxx

# 交易模式
LONGPORT_AUTO_TRADE=true
LONGPORT_DRY_RUN=false
```

---

## Telegram 通知（可选）

```bash
# 开启后，解析到交易指令会发到 Telegram Bot，带「确认/取消」按钮，点确认才实际下单
TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN=xxxx:xxxx
TELEGRAM_CHAT_ID=xxxx
```

## 抓取 Cookie

```bash
# 需要抓取网页的 Cookie，获取登录态，后续可直接监听无需重复登录
# 执行后会自动打开浏览器，登录完毕后在命令行按回车即可
# Cookie 默认保存在 .auth/whop_cookie.json
python whop/whop_login.py
```

---

## 启动

### 一键启动（推荐）

同时启动 Web 看板和信号抓取，Ctrl+C 一次停止全部：

```bash
python run.py
```

访问看板：**http://localhost:5000**

### 单独启动

```bash
python run.py --web     # 仅启动 Web 看板（演示 / 查看数据）
python run.py --main    # 仅启动信号抓取主程序
```

---

## Web 看板说明

| 路由 | 说明 |
|------|------|
| `/` 或 `/dashboard` | 持仓概览 + 最近信号 |
| `/positions` | 完整持仓列表 |
| `/trades` | 交易记录 |
| `/signals` | 全量信号列表 |

### 演示数据 / 真实数据切换

页面右上角有切换开关：

- **演示数据**（默认）：内置示例数据，无需运行主程序即可预览
- **真实数据**：读取 `output/signals.json` 和 `data/positions.json`，需先运行主程序产生数据

也可在 `.env` 中设置默认模式：
```bash
DEMO_MODE=true   # true=演示数据（默认）, false=真实数据
```

## 开发者指南

### 导出页面消息（自动滚动抓取）

全屏打开浏览器，自动滚动消息区以加载历史，抓取后按 domID 去重导出为 JSON。

```bash
python3 scripts/scraper/export_page_message.py [--type stock|option] [--output PATH] [--url URL]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--type` | 页面类型：`stock` 正股、`option` 期权 | `stock` |
| `--output` | 消息导出路径 | `tmp/<type>/origin_message.json` |
| `--url` | 目标页面 URL；不传则从 `.env` 的 `PAGES` 中按 `--type` 取首个 | - |

示例：
```bash
# 正股页消息导出到默认路径 tmp/stock/origin_message.json
python3 scripts/scraper/export_page_message.py

# 期权页消息导出到指定路径
python3 scripts/scraper/export_page_message.py --type option --output tmp/option/origin_message.json

# 指定 URL（可直接复制 .env 中 PAGES 的 url）
python3 scripts/scraper/export_page_message.py --type stock --url "https://whop.com/joined/stock-and-option/-GiWyN1ZTuUjwlG/app/"
python3 scripts/scraper/export_page_message.py --type option --url "https://whop.com/joined/stock-and-option/-gZyq1MzOZAWO98/app/"
```

### 导出页面 HTML

打开目标页面，将当前 DOM 的 HTML 导出到本地文件（用于分析页面结构或调试滚动逻辑）。

```bash
python3 scripts/scraper/export_page_html.py [--type stock|option] [--output PATH] [--url URL]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--type` | 页面类型：`stock` 正股、`option` 期权 | `stock` |
| `--output` | HTML 导出路径 | `tmp/<type>/page_html.html` |
| `--url` | 目标页面 URL；不传则从 `.env` 的 `PAGES` 中按 `--type` 取首个 | - |

示例：
```bash
# 正股页 HTML 导出到默认路径 tmp/stock/page_html.html
python3 scripts/scraper/export_page_html.py

# 期权页 HTML 导出到指定路径
python3 scripts/scraper/export_page_html.py --type option --output tmp/option/page_html.html

# 指定 URL（可直接复制 .env 中 PAGES 的 url）
python3 scripts/scraper/export_page_html.py --type stock --url "https://whop.com/joined/stock-and-option/-GiWyN1ZTuUjwlG/app/"
python3 scripts/scraper/export_page_html.py --type option --url "https://whop.com/joined/stock-and-option/-gZyq1MzOZAWO98/app/"
```

### 按股票过滤消息

从原始消息 JSON 中筛出**仅在本条 content 中提及指定股票**的消息，导出到 `tmp/stock/origin_<TICKER>_message.json`（不按 history 匹配）。

```bash
python3 scripts/parser/filter_target_stock.py TICKER [--input PATH] [--output PATH]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `TICKER` | 股票代码（必填） | - |
| `--input` | 原始消息 JSON 路径 | `tmp/stock/origin_message.json` |
| `--output` | 导出路径 | `tmp/stock/origin_<TICKER>_message.json` |

示例：
```bash
# 过滤出 content 中提到 TSLL 的消息，导出到 tmp/stock/origin_TSLL_message.json
python3 scripts/parser/filter_target_stock.py tsll

# 指定输入与输出路径
python3 scripts/parser/filter_target_stock.py HIMS --input data/stock_origin_message.json --output tmp/stock/origin_HIMS_message.json
```

### 股票做T情况分析

分析单只股票的买卖记录，识别哪些买入成本尚未通过当日 T 交易消除；结果以表格形式输出到终端（未 T 出的买入仓位、已完成 T 交易、超额卖出、汇总）。

**数据来源**：不指定 `--file` 时从长桥 API 拉取该股票最近 N 天已成交订单（含当日已成交）；指定 `--file` 时从本地 JSON 读取。

**匹配策略**：卖单在「买入价 < 卖价」的批次中按**买入价从高到低**匹配，优先消掉高成本仓位。

```bash
python3 scripts/analysis/t_trade_analysis.py [TICKER] [--file PATH] [--days N]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `TICKER` | 股票代码（如 TSLL，不含 .US） | `TSLL` |
| `--file` | 交易记录 JSON 路径 | 不指定则走长桥 API |
| `--days` | API 拉取最近天数（仅在不使用 `--file` 时生效） | `90` |

示例：
```bash
# 从长桥 API 拉取 TSLL 最近 90 天（含当日）并分析
python3 scripts/analysis/t_trade_analysis.py TSLL

# 拉取最近 60 天
python3 scripts/analysis/t_trade_analysis.py TSLL --days 60

# 从本地文件分析
python3 scripts/analysis/t_trade_analysis.py TSLL --file data/stock_trade_records.json
```

## 文档索引

- [股票页监控与关注列表](docs/stock_monitoring.md) — 正股页面监控、关注股票列表、消息抓取脚本

### 配置分类

#### Whop 平台配置
```env
# 可选：页面 URL
# TARGET_URL=https://whop.com/joined/stock-and-option/-9vfxZgBNgXykNt/app/
# LOGIN_URL=https://whop.com/login/

# 可选：浏览器设置
HEADLESS=false          # 是否无头模式运行
SLOW_MO=0               # 浏览器操作延迟（毫秒）

# 可选：监控设置
POLL_INTERVAL=2.0       # 轮询间隔（秒）
```

#### 长桥证券配置
```env
# 必填：账户模式
LONGPORT_MODE=paper     # paper=模拟账户, real=真实账户

# 必填：API 凭据（根据账户模式填写对应的配置）
LONGPORT_PAPER_APP_KEY=your_paper_app_key
LONGPORT_PAPER_APP_SECRET=your_paper_app_secret
LONGPORT_PAPER_ACCESS_TOKEN=your_paper_access_token

# 可选：交易模式
LONGPORT_AUTO_TRADE=false   # 是否启用自动交易
LONGPORT_DRY_RUN=true       # 是否启用模拟模式（不实际下单）
```

## 使用方法

### 仅监控模式

如果只想监控信号而不交易，关闭自动交易：

```bash
# 富途（默认）
FUTU_AUTO_TRADE=false

# 长桥
LONGPORT_AUTO_TRADE=false
```

然后运行：

```bash
python main.py
```

## 支持的指令格式

### 1. 开仓指令

| 示例 | 解析结果 |
|------|---------|
| `INTC - $48 CALLS 本周 $1.2` | 股票: INTC, 行权价: 48, 类型: CALL, 价格: 1.2 |
| `AAPL $150 PUTS 1/31 $2.5` | 股票: AAPL, 行权价: 150, 类型: PUT, 到期: 1/31, 价格: 2.5 |
| `TSLA - 250 CALL $3.0 小仓位` | 股票: TSLA, 行权价: 250, 类型: CALL, 价格: 3.0, 仓位: 小仓位 |

**⚠️ 期权过期校验**：系统会自动检查期权到期日，如果期权已过期（到期日早于当前日期），将自动拦截并跳过该指令，不会执行下单操作。

### 2. 止损指令

| 示例 | 解析结果 |
|------|---------|
| `止损 0.95` | 止损价: 0.95 |
| `止损提高到1.5` | 调整止损至: 1.5 |

### 3. 止盈/出货指令

| 示例 | 解析结果 |
|------|---------|
| `1.75出三分之一` | 价格: 1.75, 比例: 1/3 |
| `1.65附近出剩下三分之二` | 价格: 1.65, 比例: 2/3 |
| `2.0 出一半` | 价格: 2.0, 比例: 1/2 |

## 输出格式

解析后的指令保存在 `output/signals.json`，格式如下：

```json
[
  {
    "timestamp": "2026-01-28T10:00:00",
    "raw_message": "INTC - $48 CALLS 本周 $1.2",
    "instruction_type": "OPEN",
    "ticker": "INTC",
    "option_type": "CALL",
    "strike": 48.0,
    "expiry": "本周",
    "price": 1.2,
    "position_size": "小仓位",
    "message_id": "abc123"
  }
]
```

## 对接券商 API

### 富途牛牛集成（默认）

本项目已集成富途 OpenD API，支持：
- ✅ 模拟账户和真实账户自动切换
- ✅ 期权自动下单（美股期权）
- ✅ 风险控制和 Dry Run 模式
- ✅ 无需 API Key，本地 OpenD 直连

快速开始：

```bash
# 1. 启动富途牛牛桌面客户端（自动启动 OpenD）

# 2. 配置 .env
BROKER_TYPE=futu
FUTU_MODE=paper        # 先用模拟账户
FUTU_DRY_RUN=true      # 先开 Dry Run 观察日志

# 3. 启动系统
python main.py
```

### 长桥证券集成

切换到长桥：

```bash
# 1. 配置 .env
BROKER_TYPE=longport
LONGPORT_MODE=paper
LONGPORT_PAPER_APP_KEY=your_key
LONGPORT_PAPER_APP_SECRET=your_secret
LONGPORT_PAPER_ACCESS_TOKEN=your_token

# 2. 运行集成测试
PYTHONPATH=. python test/test_longport_integration.py

# 3. 启动
python main.py
```

**完整接入指南**：[LONGPORT_INTEGRATION_GUIDE.md](./doc/LONGPORT_INTEGRATION_GUIDE.md)

### 扩展其他券商

在 `broker/` 目录下新增 `xxx_broker.py` 并实现 `BrokerBase` 接口，然后在 `.env` 中设置 `BROKER_TYPE=xxx` 即可。
