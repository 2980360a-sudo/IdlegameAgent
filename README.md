# IdleAgent v0.2.0 🎮🤖

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/Version-0.2.0-green.svg)]()
[![Status](https://img.shields.io/badge/Status-Alpha-orange.svg)]()

一个基于 LLM 的通用挂机游戏（Idle/Incremental Games）自动化决策 Agent 框架。支持多游戏接入、可配置决策规则、可审计决策日志与持续策略学习。

> 本项目源于对 [Melvor Idle](https://melvoridle.com) 的实战 Agent 开发，目标是抽象出一套可复用于任意挂机游戏的通用决策引擎。

## 版本信息

- **当前版本**: v0.2.0
- **发布日期**: 2026-09-01
- **更新内容**: 通用框架重构 + MelvorIdleAdapter + 脱敏 + Web 控制台

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
├─────────────────────────────────────────────────────────────┤
│              🔌 游戏适配层（Game Adapter）                  │
│  状态抓取器  │  操作执行器  │  DOM映射  │  事件监听        │
├─────────────────────────────────────────────────────────────┤
│              🎮 游戏层（浏览器实例）                        │
│  Melvor Idle │ Clicker Heroes │ NGU Idle │ 其他挂机游戏    │
└─────────────────────────────────────────────────────────────┘
```

**核心设计**：每个新游戏只需实现「游戏适配层」的 4 个接口，核心引擎完全复用。

## 功能特性

- **通用化架构** — 诊断/规划/决策/审计四层引擎，与具体游戏解耦
- **YAML 规则配置** — 无需改代码，通过配置文件调整决策策略
- **LLM 辅助决策** — 支持 DeepSeek、GPT-4 等模型进行复杂判断
- **可审计决策日志** — 每次操作均可回溯其依据与上下文
- **社区学习机制** — Agent 主动学习攻略并迭代自身策略
- **Web 管理控制台** — 实时监控、规则编辑、日志查看、数据分析
- **安全约束系统** — 硬约束（如角色死亡即暂停）与软约束分级管理
- **弹窗安全协议** — 危险词/交易词/损失警告黑名单，绝不误操作

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

### 4. 运行 Agent

```bash
# 自动模式（定时诊断+决策+执行）
python main.py --game melvor_idle --mode auto

# 单次巡检
python scripts/patrol.py inspect

# 守卫模式（药剂修正+动作恢复）
python scripts/patrol.py guards
```

### 5. 启动 Web 控制台

```bash
cd dashboard
python -m http.server 8080
# 打开 http://localhost:8080
```

## 目录结构

```
IdleAgent/ v0.2.0
├── .env.example              # 环境变量模板（脱敏）
├── requirements.txt          # Python 依赖
├── .gitignore               # Git 忽略规则
├── LICENSE                  # MIT 许可证
├── README.md                # 本文件
├── main.py                  # 统一入口（支持 auto/inspect/guards/manual）
├── core/                    # 通用引擎
│   ├── __init__.py
│   ├── adapter.py           # GameAdapter 抽象基类（4个接口）
│   ├── state.py             # Pydantic 数据模型
│   ├── browser.py           # 浏览器管理（启动/登录/存档/导航）
│   ├── safety.py            # 弹窗安全系统（危险词黑名单）
│   ├── engine.py            # 诊断/规划/决策/执行引擎
│   └── scheduler.py         # APScheduler 定时调度
├── adapters/                # 游戏适配器
│   ├── __init__.py
│   └── melvor_idle.py       # Melvor Idle 专用适配器
├── scripts/                 # 可执行脚本
│   ├── melvor.py            # 完整巡检脚本（脱敏）
│   └── patrol.py            # 精简守卫脚本（脱敏）
├── config/rules/            # 规则配置文件
│   ├── _base.yaml           # 通用基础规则
│   └── melvor_idle.yaml     # Melvor 专用规则
└── dashboard/               # Web 管理控制台
    ├── index.html
    ├── css/style.css
    └── js/app.js
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端控制台 | Vanilla HTML/CSS/JS |
| 浏览器自动化 | Playwright |
| 视觉识别 | LLM Vision (GPT-4o / Claude 3.5) |
| 后端框架 | Python + FastAPI (预留) |
| 规则引擎 | PyYAML + Pydantic |
| 调度系统 | APScheduler |
| 数据存储 | SQLite (预留) |
| LLM 调用 | DeepSeek API / OpenAI API |

## 已适配游戏

| 游戏 | 状态 | 完成度 |
|------|------|--------|
| [Melvor Idle](https://melvoridle.com) | v0.2.0 可用 | 诊断/规划/决策/执行全链路验证 |
| Clicker Heroes | 计划中 | 适配器模板待开发 |
| NGU Idle | 计划中 | — |

## 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|---------|
| v0.2.0 | 2026-09-01 | 通用框架重构、MelvorIdleAdapter、脱敏、Web控制台、YAML规则配置 |
| v0.1.0 | 2026-08 | Melvor Idle 单游戏脚本原型 |

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
- 前端控制台功能增强
- 文档和教程
- Bug 修复和性能优化

## 作者

**孙屿航 (Eric Sun)**

- 从传统制造业 PM 转型 AI 产品经理
- 独立主导 AI 知识库（RAGFlow + DeepSeek）从 0 到 1 落地
- 独立设计并运行 Melvor Idle 全自动决策 Agent（72h 零干预）
- 求职意向：AI 产品经理 / AI 项目经理

## 许可证

本项目基于 [MIT License](LICENSE) 开源。

---

> **声明**：本工具仅供学习和研究使用。使用自动化工具操作在线游戏可能违反游戏服务条款，请自行评估风险。作者不对因使用本工具导致的任何账号封禁或其他后果负责。
