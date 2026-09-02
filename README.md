# IdleAgent v0.5.0 🎮🤖

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/Version-0.5.0-green.svg)]()
[![Status](https://img.shields.io/badge/Status-Beta-orange.svg)]()

一个基于 LLM 的通用挂机游戏（Idle/Incremental Games）自动化决策 Agent 框架。支持多游戏接入、可配置决策规则、可审计决策日志与持续策略学习。

> 本项目源于对 [Melvor Idle](https://melvoridle.com) 的实战 Agent 开发，目标是抽象出一套可复用于任意挂机游戏的通用决策引擎。

---

## 版本信息

- **当前版本**: v0.5.0
- **发布日期**: 2026-09-03
- **更新内容**: 新增用户注册/登录与用户信息存储（`core/auth.py` 密码哈希 + 签名 token + SQLite 用户库，`/api/auth/*` 路由）；前端重构为登录/注册 + 仪表盘 + 个人资料三大页面

### 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|---------|
| v0.5.0 | 2026-09-03 | 新增用户认证（注册/登录/资料，`core/auth.py` + `/api/auth/*`）；前端重构为登录/注册 + 仪表盘 + 个人资料 |
| v0.4.0 | 2026-09-03 | 完成「真实适配器接入引擎」「LLM 决策（DeepSeek）」「SQLite 持久化」；修复适配器/数据模型不一致、`/health` 被静态挂载遮蔽、损坏的 `__init__.py` 与 `melvor.py`；新增 `core/llm.py`、`core/storage.py`、`tests/test_smoke.py` |
| v0.3.0 | 2026-09-02 | 修复 `browser.py`/`main.py` 换行问题；API 服务可用；WebSocket 心跳正常；前端联调通过 |
| v0.2.0 | 2026-09-01 | 通用框架重构、MelvorIdleAdapter、脱敏、Web 控制台、YAML 规则配置、FastAPI 后端骨架 |
| v0.1.0 | 2026-08 | Melvor Idle 单游戏脚本原型（72h 零人工干预验证） |

---

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│  LLM 决策辅助层          │  审计与学习层                     │
│  DeepSeek / GPT-4 / ...  │  决策日志 · 社区学习 · 策略迭代   │
├─────────────────────────────────────────────────────────────┤
│                    ⚙️ 核心决策引擎                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ 诊断引擎  │  │ 规划引擎  │  │ 决策引擎  │  │ 执行引擎  │  │
│  │Diagnosis │  │ Planning │  │ Decision │  │Execution │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         📐 通用规则系统（YAML 配置）                  │  │
│  │  资源卖留规则 · 优先级规则 · 合成路径 · 安全约束      │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         💾 SQLite 持久化（日志 + 状态快照 + 审计）     │  │
│  └──────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│              🔌 游戏适配层（Game Adapter）                  │
│  状态抓取器  │  操作执行器  │  DOM映射  │  事件监听        │
├─────────────────────────────────────────────────────────────┤
│              🎮 游戏层（浏览器实例）                        │
│  Melvor Idle │ Clicker Heroes │ NGU Idle │ 其他挂机游戏    │
└─────────────────────────────────────────────────────────────┘
```

**核心设计**：每个新游戏只需实现「游戏适配层」的 4 个接口，核心引擎完全复用。

---

## 功能特性

- ✅ **通用化架构** — 诊断/规划/决策/审计四层引擎，与具体游戏解耦
- ✅ **YAML 规则配置** — 无需改代码，通过配置文件调整决策策略（含安全约束条件求值）
- ✅ **LLM 辅助决策** — 已接入 DeepSeek（OpenAI 兼容接口），规则无法覆盖时由 LLM 生成操作序列
- ✅ **可审计决策日志** — 每次操作均可回溯其依据与上下文
- ✅ **Web 管理控制台** — 实时监控、规则编辑、日志查看、数据分析
- ✅ **FastAPI 后端服务** — REST API + WebSocket 实时推送
- ✅ **用户账号系统** — 注册/登录/个人资料，PBKDF2 密码哈希 + 签名 token + SQLite 用户存储
- ✅ **安全约束系统** — 硬约束（如角色死亡即暂停）与软约束分级管理
- ✅ **弹窗安全协议** — 危险词/交易词/损失警告黑名单，绝不误操作
- ✅ **SQLite 持久化** — 决策日志、状态快照、决策审计入库，支持历史回溯
- ✅ **真实适配器接入** — `MelvorIdleAdapter.read_state()` 驱动引擎，Web 控制台可切换真实/模拟数据
- 🔄 **社区学习机制** — Agent 主动学习攻略并迭代自身策略（规划中）

---

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/2980360a-sudo/IdlegameAgent.git
cd IdlegameAgent
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的游戏账号和 LLM API Key
```

关键变量：`MELVOR_ACCOUNT` / `MELVOR_PASSWORD`（游戏账号）、`LLM_API_KEY`（DeepSeek）、
`USE_REAL_ADAPTER`（API 是否接入真实浏览器，默认 `false` 走模拟数据）。

### 4. 启动后端 API 服务

```bash
python -m uvicorn api.app:app --reload --host 0.0.0.0 --port 8000
# 访问 http://localhost:8000 即可看到控制台界面
```

### 5. 运行 Agent（命令行模式）

```bash
# 自动模式（定时诊断+决策+执行，需真实账号）
python main.py --game melvor_idle --mode auto

# 单次状态检查
python main.py --game melvor_idle --mode inspect

# 守卫模式（药剂修正+动作恢复）
python main.py --game melvor_idle --mode guards
```

### 6. 运行冒烟测试（无需浏览器）

```bash
python tests/test_smoke.py
```

---

## 目录结构

```
IdleAgent/ v0.5.0
├── .env.example              # 环境变量模板（脱敏）
├── requirements.txt          # Python 依赖
├── .gitignore                # Git 忽略规则
├── LICENSE                   # MIT 许可证
├── README.md                 # 本文件
├── main.py                   # 统一入口（支持 auto/inspect/guards/manual）
├── api/                      # FastAPI 后端服务
│   ├── app.py                # FastAPI 应用入口（REST + WebSocket）
│   ├── dependencies.py       # AgentRuntime 依赖注入（模拟/真实数据切换 + SQLite）
│   ├── managers.py           # WebSocket 连接管理器
│   └── routes/               # API 路由
│       ├── auth.py           # 用户认证：注册/登录/登出/我的信息/更新
│       ├── status.py         # GET /api/status — 游戏状态
│       ├── control.py        # POST /api/control/{start|stop|pause} — 启停控制
│       ├── logs.py           # GET /api/logs — 决策日志查询
│       └── rules.py          # GET /api/rules — 规则配置读取
├── core/                     # 通用引擎（与游戏解耦）
│   ├── __init__.py
│   ├── adapter.py            # GameAdapter 抽象基类（4个接口契约 + YAML 规则加载）
│   ├── state.py              # Pydantic 数据模型（GameState/Action/GameEvent/枚举...）
│   ├── auth.py               # 用户认证（密码哈希 + 签名 token + SQLite 用户存储）
│   ├── browser.py            # Playwright 浏览器管理（启动/登录/存档/导航）
│   ├── safety.py             # 弹窗安全系统（危险词/交易词/损失警告黑名单）
│   ├── engine.py             # 四层引擎：诊断/规划/决策/执行（含条件求值 + LLM 决策）
│   ├── llm.py                # LLM 客户端（DeepSeek/OpenAI 兼容，httpx 实现）
│   ├── storage.py            # SQLite 持久化（日志/状态快照/决策审计）
│   └── scheduler.py          # APScheduler 定时任务调度
├── adapters/                 # 游戏适配器
│   ├── __init__.py
│   └── melvor_idle.py        # Melvor Idle 专用适配器（JS注入+DOM解析双策略 + 守卫）
├── scripts/                  # 可执行脚本
│   ├── melvor.py             # 完整巡检脚本（脱敏）
│   └── patrol.py             # 精简守卫脚本（脱敏）
├── config/rules/             # 规则配置文件（YAML 热更新）
│   ├── _base.yaml            # 通用基础规则（所有游戏共享）
│   └── melvor_idle.yaml      # Melvor 专用规则（覆盖基础规则）
├── tests/                    # 测试
│   └── test_smoke.py         # 冒烟测试（引擎/规则/持久化，无需浏览器）
└── dashboard/                # Web 管理控制台（前端）
    ├── index.html            # 单页应用入口
    ├── css/style.css         # 样式表
    └── js/app.js             # 前端逻辑（API调用 + WebSocket + 页面渲染）
```

---

## 技术栈

| 层级 | 技术 | 状态 |
|------|------|------|
| 前端控制台 | Vanilla HTML/CSS/JS | ✅ 可用 |
| 后端 API | FastAPI + Uvicorn | ✅ 可用 |
| 实时通信 | WebSocket | ✅ 心跳正常 |
| 浏览器自动化 | Playwright | ✅ 可用 |
| 数据模型 | Pydantic v2 | ✅ 可用 |
| 规则引擎 | PyYAML | ✅ 可用（含条件求值） |
| 调度系统 | APScheduler | ✅ 可用 |
| 数据存储 | SQLite | ✅ 已实现（日志 + 快照 + 审计 + 用户） |
| LLM 调用 | DeepSeek API（OpenAI 兼容） | ✅ 已实现（httpx） |
| 用户认证 | PBKDF2 + HMAC 签名 token | ✅ 已实现（无第三方依赖） |

---

## 已适配游戏

| 游戏 | 状态 | 完成度 |
|------|------|--------|
| [Melvor Idle](https://melvoridle.com) | v0.5.0 可用 | 适配器完整，JS 注入 + DOM 解析双策略，守卫操作、状态读取、动作执行已接入引擎 |
| Clicker Heroes | 计划中 | 适配器模板待开发 |
| NGU Idle | 计划中 | — |

---

## API 接口文档

启动后端后访问 `http://localhost:8000/docs` 查看自动生成的 Swagger UI。

### 核心接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/api/auth/register` | 注册用户（返回 token + 用户信息） |
| POST | `/api/auth/login` | 登录（用户名或邮箱 + 密码） |
| POST | `/api/auth/logout` | 登出 |
| GET | `/api/auth/me` | 获取当前登录用户（需 Bearer token） |
| PATCH | `/api/auth/me` | 更新资料（昵称/邮箱/备注/密码） |
| GET | `/api/status` | 获取当前游戏状态（模拟或真实数据，取决于 `USE_REAL_ADAPTER`） |
| POST | `/api/control/start` | 启动 Agent |
| POST | `/api/control/stop` | 停止 Agent |
| POST | `/api/control/pause` | 暂停 Agent |
| GET | `/api/logs?limit=50` | 获取决策日志（SQLite） |
| GET | `/api/rules` | 获取规则配置 |
| WS | `/ws` | WebSocket 实时推送（ping/pong 心跳） |

---

## 开发指南

### 添加新游戏适配器

参考 `adapters/melvor_idle.py`，实现 `GameAdapter` 的四个抽象方法：

```python
class MyGameAdapter(GameAdapter):
    async def read_state(self, page) -> GameState:
        """从游戏页面提取统一状态"""
        pass

    async def execute_action(self, page, action: Action) -> bool:
        """执行原子操作：点击、选择、输入、等待、导航等"""
        pass

    def map_dom(self, raw_html: str) -> DOMMap:
        """将游戏原始 DOM 映射为统一结构"""
        pass

    async def watch_events(self, page) -> List[GameEvent]:
        """监听游戏事件：升级、死亡、弹窗、完成度变化等"""
        pass
```

可选钩子：`diagnose_custom(state)`（游戏专用诊断）、`guards(page)`（守卫）、`pre_boot` / `post_shutdown`。

### 修改决策逻辑

优先编辑 `config/rules/melvor_idle.yaml` 中的规则（`safety.hard_constraints[].condition`
支持形如 `hp / max_hp < 0.2` 的表达式），避免改动核心代码。

### 接入 LLM

在 `.env` 中配置 `LLM_API_KEY` 即可启用 LLM 决策（`core/engine.py` 的 `DecisionEngine._llm_decide()`）：
1. 构建 Prompt（包含状态、目标、历史）
2. 调用 DeepSeek/OpenAI 兼容接口（`core/llm.py`）
3. 解析 JSON 返回，生成 Action 列表
4. 记录审计日志（`core/storage.py`）

### 数据持久化

`core/storage.py` 提供 SQLite 三层存储：`logs`（日志）、`state_snapshots`（状态快照）、
`decisions`（决策审计）。默认库文件为 `state/idleagent.db`。

### 扩展 Web 控制台

- 后端新增 API：在 `api/routes/` 下新建文件，添加路由
- 前端调用：在 `dashboard/js/app.js` 的 API 对象中增加方法，并更新渲染函数

---

## 已知问题

- Melvor Idle 的 DOM 结构可能随版本变化，需定期更新适配器中的选择器
- WebSocket 收到的 "pong" 纯文本不会影响功能（已在前端做了兼容处理）
- Windows 下 Git 换行符问题：建议 `git config --global core.autocrlf false`，或添加 `.gitattributes` 统一换行符
- 真实模式（`USE_REAL_ADAPTER=true` / `main.py --mode auto`）依赖已安装的 Chromium 与有效账号，未在 CI 中自动化联调

---

## 未来计划（优先级排序）

1. ✅ **集成真实适配器到引擎** — `MelvorIdleAdapter.read_state()` 驱动决策（已实现）
2. ✅ **实现 LLM 决策** — 完成 `_llm_decide()`，接入 DeepSeek API（已实现）
3. ✅ **SQLite 存储** — 持久化日志和状态快照，支持历史回溯（已实现）
4. 🔄 **完善 Web 控制台** — 游戏管理、规则编辑、数据分析图表
5. 🔄 **多游戏适配器** — 添加 Clicker Heroes、NGU Idle 等，验证通用性
6. 🔄 **Docker 化部署** — 支持远程访问

---

## 贡献指南

欢迎提交 Issue 和 PR！

1. Fork 本仓库
2. 创建你的功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

### 特别欢迎的贡献方向

- 新的游戏适配器（Clicker Heroes、NGU Idle 等）
- 规则配置模板
- 前端控制台功能增强（Chart.js 图表、实时数据连接）
- LLM 决策 Prompt 优化
- 单元测试与集成测试
- 文档和教程
- Bug 修复和性能优化

---

## 作者

**孙屿航 (Eric Sun)**

- 从传统制造业 PM 转型 AI 产品经理
- 独立主导 AI 知识库（RAGFlow + DeepSeek）从 0 到 1 落地
- 独立设计并运行 Melvor Idle 全自动决策 Agent（72h 零干预验证）
- 求职意向：AI 产品经理 / AI 项目经理

## 许可证

本项目基于 [MIT License](LICENSE) 开源。

---

> **声明**：本工具仅供学习和研究使用。使用自动化工具操作在线游戏可能违反游戏服务条款，请自行评估风险。作者不对因使用本工具导致的任何账号封禁或其他后果负责。
