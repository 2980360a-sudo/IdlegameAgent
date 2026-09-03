# IdleAgent — 开源 LLM Agent 决策系统

> 一个从产品定义到工程落地的全栈 LLM Agent 项目：以高复杂度放置游戏为验证场景，构建「攻略知识库 → 检索决策 → 自动化执行 → 审计」的完整闭环。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/Version-0.9.0-green.svg)]()

---

## 这是什么

IdleAgent **不是「游戏脚本」**，而是一个 **LLM Agent 决策系统**。游戏（Melvor Idle）只是验证场景——就像 OpenAI 用 Dota、星际来验证强化学习 Agent 一样，我们用一款高复杂度、规则开放的游戏来验证 **RAG + Agent** 在开放任务中的决策能力。

**一句话**：让 LLM 阅读攻略、判断现状、自主决策并执行操作，全程可审计、成本可控。

## 核心架构

```
┌─────────────── 决策闭环 ───────────────┐
│  攻略知识库(RAG) → 动态动作目录          │
│        ↓                               │
│   LLM 决策（判断当前阶段该做什么）        │
│        ↓                               │
│   执行器（技能训练 / 战斗 / 维护）        │
│        ↓                               │
│   审计日志 + 账号检查文档                │
└─────────────── 用户建议注入 ↑ ──────────┘
```

## 核心亮点（产品视角）

| 能力 | 说明 | 体现的产品思维 |
|------|------|---------------|
| **攻略方针驱动的决策** | LLM 依据官方 Wiki + 社区攻略判断「当前该做什么」，而非硬编码规则 | 技术选型判断力 |
| **三种运行模式** | 效率优先 / 极限不死亡 / 用户脚本 | 需求分层 |
| **用户建议对话框** | 用户反馈注入后续决策 | 人机协同 / 反馈闭环 |
| **账号检查文档** | 首次生成 + 增量修改 + 持久化 | 可审计性 |
| **Token 监控 + 成本上限** | 实时统计消耗，巡检间隔封顶 24 小时 | 成本意识 |
| **定时巡检 + LLM 自主排程** | 让 LLM 决定下次检查时机 | 智能调度 |

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python · FastAPI · Playwright（浏览器自动化） |
| 存储 | SQLite（日志 / 状态快照 / 决策审计 / 设置） |
| 模型 | DeepSeek（OpenAI 兼容接口，可热切换） |
| 决策 | RAG（攻略知识库）+ 动态动作目录 + LLM |
| 前端 | 原生 HTML/CSS/JS 仪表盘 |

## 快速开始

```bash
git clone https://github.com/2980360a-sudo/IdlegameAgent.git
cd IdlegameAgent
pip install -r requirements.txt
playwright install chromium
# 配置 .env：填入游戏账号 + LLM_API_KEY
python -m uvicorn api.app:app --host 0.0.0.0 --port 8000
```

打开 http://localhost:8000 ，在「系统设置」页配置模型 API，在「梅尔沃放置」页登录游戏账号并启动挂机。

## 版本

**v0.9.0**（首个发布版），自 v0.1.0 起迭代 12+ 个版本。

## 许可证

本项目基于 [MIT License](LICENSE) 开源。
