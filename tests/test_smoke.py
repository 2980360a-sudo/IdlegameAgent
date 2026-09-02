#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""冒烟测试：在不启动浏览器的情况下验证核心引擎、规则加载与 SQLite 持久化。

运行: python tests/test_smoke.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 测试数据库放在项目内（沙箱工作区），避免写系统临时目录
_TMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'state')
os.makedirs(os.path.abspath(_TMP), exist_ok=True)

from core.state import GameState, Action, ActionType, EventType, SkillInfo, ResourceInfo
from core.adapter import GameAdapter
from core.engine import DiagnosisEngine, PlanningEngine, DecisionEngine, ExecutionEngine
from core.storage import Storage


class FakeAdapter(GameAdapter):
    """最小化适配器，用于引擎测试。"""

    async def read_state(self, page):
        return GameState(game_name='Fake Game')

    async def execute_action(self, page, action: Action) -> bool:
        return action.action_type in ActionType.__members__.values()

    def map_dom(self, raw_html):
        from core.state import DOMMap
        return DOMMap(game_name='Fake Game')

    async def watch_events(self, page):
        return []

    async def diagnose_custom(self, state):
        return {'warnings': [], 'recommendations': []}


def make_low_hp_state():
    return GameState(
        game_name='Melvor Idle',
        hp=10, max_hp=100, combat_active=True,
        bank_used=50, bank_max=100,
        skills={'woodcutting': SkillInfo(name='woodcutting', level=99, xp=1000)},
        resources={'gold': ResourceInfo(name='gold', quantity=1234)},
    )


async def main():
    passed = 0
    failed = 0

    def check(name, cond):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f'  [PASS] {name}')
        else:
            failed += 1
            print(f'  [FAIL] {name}')

    print('\n== 1. 规则加载 ==')
    adapter = FakeAdapter({'name': 'Melvor Idle', 'url': 'https://melvoridle.com'})
    rules = GameAdapter.load_rules('melvor_idle')
    check('加载 melvor_idle.yaml', rules.get('game') == 'Melvor Idle')
    check('包含 safety 硬约束', 'hard_constraints' in rules.get('safety', {}))
    check('包含 priorities', 'short_term' in rules.get('priorities', {}))

    print('\n== 2. 诊断引擎（低血量触发硬约束）==')
    storage = Storage(db_path=os.path.join(os.path.abspath(_TMP), 'test.db'))
    diag = DiagnosisEngine(adapter, storage=storage)
    state = make_low_hp_state()
    result = await diag.diagnose(state)
    check('检测到 HP 过低', any('HP' in w or '生命' in w for w in result.warnings))
    check('推荐 stop_combat', 'stop_combat' in result.recommendations)

    print('\n== 3. 条件求值 ==')
    check('hp/max_hp < 0.2 为真', diag._check_condition(state, 'hp / max_hp < 0.2'))
    check('bank_used/bank_max > 0.9 为假', not diag._check_condition(state, 'bank_used / bank_max > 0.9'))
    check('空条件为假', not diag._check_condition(state, ''))

    print('\n== 4. 规划 -> 决策 -> 执行 ==')
    planning = PlanningEngine(adapter, storage=storage)
    decision = DecisionEngine(adapter, storage=storage)
    execution = ExecutionEngine(adapter, storage=storage)

    plan = await planning.plan(result)
    check('规划含推荐目标', 'stop_combat' in plan.short_term_goals)

    dec = await decision.decide(plan, state)
    check('生成了操作', len(dec.actions) > 0)

    class Page:
        pass
    exec_result = await execution.execute(Page(), dec)
    check('执行成功', exec_result.success)
    check('执行了至少 1 个操作', exec_result.actions_executed >= 1)

    print('\n== 5. SQLite 持久化 ==')
    logs = storage.get_logs(limit=100)
    check('有诊断日志', any(l['module'] == 'diagnosis' for l in logs))
    check('有决策记录', len(storage.get_snapshots(0)) >= 0)
    storage.add_log('info', 'system', '冒烟测试日志')
    check('日志可写入', any(l['message'] == '冒烟测试日志' for l in storage.get_logs(10)))
    storage.close()

    print('\n== 6. 状态模型（枚举） ==')
    check('ActionType.CLICK 值为 click', ActionType.CLICK.value == 'click')
    check('EventType.DEATH 值为 death', EventType.DEATH.value == 'death')
    a = Action(action_type=ActionType.WAIT.value, target='body', params={'duration': 5})
    check('Action 构造与序列化', a.model_dump()['action_type'] == 'wait')

    print(f'\n===== 结果: {passed} 通过, {failed} 失败 =====')
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
