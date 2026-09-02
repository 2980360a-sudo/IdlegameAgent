"""
API 依赖注入模块
提供全局 AgentRuntime 单例，供路由层调用。

默认运行在「模拟数据」模式（无需浏览器即可启动控制台）；
设置环境变量 USE_REAL_ADAPTER=true 后，start 会拉起真实 Melvor 浏览器
并运行诊断→规划→决策→执行 的自动循环，状态接口返回真实数据。
"""

import os
import time
import asyncio
from typing import Dict, Any, List, Optional

from core.storage import Storage

USE_REAL_ADAPTER = os.environ.get('USE_REAL_ADAPTER', 'false').lower() == 'true'


class AgentRuntime:
    """Agent 运行时上下文：状态、日志、运行标志、可选真实适配器。"""

    def __init__(self):
        self.is_running = False
        self._counter = 0
        self._mock_resources = {"gold": 1234.5, "wood": 567, "stone": 890}
        self._mock_combat = {"hp": 850, "max_hp": 1000, "in_combat": False}

        # SQLite 持久化（决策日志 + 状态快照）
        self.storage = Storage()

        # 真实适配器（按需初始化）
        self.adapter = None
        self.browser = None
        self._loop_task = None
        if USE_REAL_ADAPTER:
            self._init_real_adapter()

    # ============================================================
    # 真实适配器初始化
    # ============================================================
    def _init_real_adapter(self):
        try:
            from adapters.melvor_idle import MelvorIdleAdapter
            self.adapter = MelvorIdleAdapter()
            self.browser = self.adapter.browser
            self.add_log('info', 'system', '真实适配器已初始化（等待启动）')
        except Exception as e:
            self.add_log('error', 'system', f'真实适配器初始化失败: {e}')
            self.adapter = None
            self.browser = None

    async def _launch_real(self):
        """启动真实浏览器并完成登录/存档加载。"""
        if self.browser is None:
            self._init_real_adapter()
        if self.browser is None:
            raise RuntimeError('真实适配器不可用')
        if self.browser.page is None:
            await self.browser.launch()
            await self.browser.navigate()
            await self.browser.boot_sequence()
            self.add_log('info', 'system', '浏览器已启动并加载存档')

    async def _decision_loop(self):
        """真实模式下的自动决策循环。"""
        from core.engine import (
            DiagnosisEngine, PlanningEngine, DecisionEngine, ExecutionEngine,
        )
        from core.llm import LLMClient

        llm = LLMClient() if LLMClient().configured else None
        diag = DiagnosisEngine(self.adapter, storage=self.storage)
        planning = PlanningEngine(self.adapter, storage=self.storage)
        decision = DecisionEngine(self.adapter, llm_client=llm, storage=self.storage)
        execution = ExecutionEngine(self.adapter, storage=self.storage)

        while self.is_running:
            try:
                state = await self.adapter.read_state(self.browser.page)
                self.storage.save_state(state)
                d = await diag.diagnose(state)
                p = await planning.plan(d)
                dec = await decision.decide(p, state)
                res = await execution.execute(self.browser.page, dec)
                self.add_log(
                    'info', 'system',
                    f'决策循环完成：执行 {res.actions_executed} 个操作，成功={res.success}',
                    {'errors': res.errors},
                )
            except Exception as e:
                self.add_log('error', 'system', f'决策循环异常: {type(e).__name__}: {e}')
            await asyncio.sleep(60)

    # ============================================================
    # 状态获取
    # ============================================================
    async def get_status(self) -> Dict[str, Any]:
        """返回当前游戏状态（真实模式返回真实数据，否则返回模拟数据）。"""
        if self.adapter is not None and self.browser is not None and self.browser.page is not None:
            try:
                state = await self.adapter.read_state(self.browser.page)
                return {
                    'resources': {
                        k: v.quantity for k, v in state.resources.items()
                    },
                    'combat': {
                        'hp': state.hp or 0,
                        'max_hp': state.max_hp or 0,
                        'in_combat': state.combat_active,
                    },
                    'skills': {k: v.level for k, v in state.skills.items()},
                    'active_action': state.active_action,
                    'is_running': self.is_running,
                    'source': 'real',
                    'timestamp': time.time(),
                }
            except Exception as e:
                self.add_log('error', 'system', f'读取真实状态失败: {e}')

        # 模拟数据缓慢增长，让仪表盘有动态效果
        self._mock_resources['gold'] += 0.5
        self._mock_resources['wood'] += 0.3
        self._mock_resources['stone'] += 0.2
        return {
            'resources': dict(self._mock_resources),
            'combat': dict(self._mock_combat),
            'is_running': self.is_running,
            'source': 'mock',
            'timestamp': time.time(),
        }

    # ============================================================
    # 日志管理（内存 + SQLite）
    # ============================================================
    def get_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        logs = self.storage.get_logs(limit)
        if not logs:
            self._generate_sample_logs()
            logs = self.storage.get_logs(limit)
        # 倒序为时间正序返回（前端按时间显示）
        return list(reversed(logs))

    def add_log(self, level: str, module: str, message: str, data: Optional[Dict] = None):
        self.storage.add_log(level, module, message, data)

    def _generate_sample_logs(self):
        sample = [
            ('info', 'system', 'Agent 启动完成，等待指令'),
            ('info', 'diagnosis', '诊断完成：当前资源充足，建议升级伐木'),
            ('decision', 'decision', '决策：执行伐木操作'),
            ('action', 'execution', '执行动作：click #woodcutting'),
            ('info', 'system', '定时循环开始'),
            ('warning', 'monitor', '仓库木材接近上限，建议出售'),
            ('info', 'execution', '动作执行成功，木材 +10'),
        ]
        for level, module, msg in sample:
            self.add_log(level, module, msg)

    # ============================================================
    # 控制方法
    # ============================================================
    async def start(self) -> str:
        """启动 Agent。返回状态字符串: started | already。"""
        if self.is_running:
            return 'already'
        self.is_running = True

        if self.adapter is not None:
            try:
                await self._launch_real()
                self.add_log('info', 'system', 'Agent 已启动（真实模式）')
                self._loop_task = asyncio.create_task(self._decision_loop())
            except Exception as e:
                self.is_running = False
                self.add_log('error', 'system', f'真实模式启动失败: {e}')
                return 'failed'
        else:
            self.add_log('info', 'system', 'Agent 已启动（模拟模式）')
        return 'started'

    async def stop(self) -> str:
        """停止 Agent。"""
        if self._loop_task is not None:
            self._loop_task.cancel()
            self._loop_task = None
        was_running = self.is_running
        self.is_running = False
        if self.browser is not None and self.browser.page is not None:
            await self.browser.close()
        self.add_log('info', 'system', 'Agent 已停止')
        return 'stopped' if was_running else 'already'

    async def pause(self) -> str:
        """暂停 Agent（停止决策循环但保留浏览器）。"""
        if self._loop_task is not None:
            self._loop_task.cancel()
            self._loop_task = None
        self.is_running = False
        self.add_log('warning', 'system', 'Agent 已暂停')
        return 'paused'


# ============================================================
# 全局单例
# ============================================================
_runtime = AgentRuntime()


def get_runtime() -> AgentRuntime:
    return _runtime
