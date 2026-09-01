# IdleAgent v0.2.0 - core/engine.py
# Generated: 2026-09-01

from typing import List, Dict, Any, Optional
from datetime import datetime
from .state import GameState, DiagnosisResult, Plan, Decision, ExecutionResult, Action
from .adapter import GameAdapter


class DiagnosisEngine:
    """诊断引擎：定期全面盘点游戏状态，识别瓶颈和风险。"""

    def __init__(self, adapter: GameAdapter):
        self.adapter = adapter

    async def diagnose(self, state: GameState) -> DiagnosisResult:
        result = DiagnosisResult(
            game_name=state.game_name,
            current_state=state
        )
        # 安全约束检查
        safety_rules = self.adapter.get_safety_rules()
        hard = safety_rules.get('hard_constraints', [])
        for rule in hard:
            if self._check_condition(state, rule.get('condition', '')):
                result.warnings.append(f'[硬约束] {rule.get("description", "")}')
                result.recommendations.append(rule.get('action', 'pause_all'))
        # 资源上限检查
        bank_used = state.bank_used or 0
        bank_max = state.bank_max or 1
        if bank_used / bank_max > 0.9:
            result.warnings.append('仓库空间紧张')
            result.recommendations.append('sell_excess')
        # 战斗安全检查
        if state.combat_active:
            if state.hp and state.max_hp and state.hp / state.max_hp < 0.2:
                result.warnings.append('角色HP过低，建议立即停止战斗')
                result.recommendations.append('stop_combat')
        # 游戏专用诊断
        custom = await self.adapter.diagnose_custom(state)
        result.warnings.extend(custom.get('warnings', []))
        result.recommendations.extend(custom.get('recommendations', []))
        return result

    def _check_condition(self, state: GameState, condition: str) -> bool:
        return False


class PlanningEngine:
    """规划引擎：根据诊断结果生成目标队列。"""

    def __init__(self, adapter: GameAdapter):
        self.adapter = adapter

    async def plan(self, diagnosis: DiagnosisResult) -> Plan:
        plan = Plan(game_name=diagnosis.game_name)
        priorities = self.adapter.get_priority_rules()
        plan.short_term_goals = priorities.get('short_term', [])
        plan.mid_term_goals = priorities.get('mid_term', [])
        plan.long_term_goals = priorities.get('long_term', [])
        for rec in diagnosis.recommendations:
            plan.short_term_goals.insert(0, rec)
        plan.priority_queue = [{'action': rec, 'priority': 'critical', 'reason': '诊断推荐'}
                               for rec in diagnosis.recommendations]
        return plan


class DecisionEngine:
    """决策引擎：根据规划生成具体操作序列。"""

    def __init__(self, adapter: GameAdapter, llm_client=None):
        self.adapter = adapter
        self.llm_client = llm_client

    async def decide(self, plan: Plan, state: GameState) -> Decision:
        decision = Decision(
            game_name=plan.game_name,
            plan_id=str(id(plan))
        )
        for item in plan.priority_queue:
            if item['priority'] == 'critical':
                action = await self._rule_match(item['action'], state)
                if action:
                    decision.actions.append(action)
        decision.reason = f'基于规划引擎的 {len(plan.priority_queue)} 项优先级推荐'
        return decision

    async def _rule_match(self, action_key: str, state: GameState) -> Optional[Action]:
        rule_map = {
            'pause_all': Action(action_type='wait', target='body', reason='安全约束触发，暂停所有操作'),
            'stop_combat': Action(action_type='navigate', target='非战斗技能页', reason='HP过低，停止战斗'),
            'sell_excess': Action(action_type='navigate', target='仓库', reason='仓库空间紧张，出售多余物品'),
        }
        return rule_map.get(action_key)

    async def _llm_decide(self, plan: Plan, state: GameState) -> Optional[Action]:
        if not self.llm_client:
            return None
        return None


class ExecutionEngine:
    """执行引擎：调用适配器执行决策中的操作序列。"""

    def __init__(self, adapter: GameAdapter):
        self.adapter = adapter

    async def execute(self, page, decision: Decision) -> ExecutionResult:
        result = ExecutionResult(
            game_name=decision.game_name,
            decision_id=str(id(decision)),
        )
        for action in decision.actions:
            try:
                ok = await self.adapter.execute_action(page, action)
                if ok:
                    result.actions_executed += 1
                else:
                    result.errors.append(f'操作失败: {action.action_type} -> {action.target}')
            except Exception as e:
                result.errors.append(f'操作异常: {type(e).__name__}: {str(e)[:100]}')
        result.success = len(result.errors) == 0
        return result
