# IdleAgent v0.4.0 - core/engine.py
# 四层引擎：诊断 / 规划 / 决策 / 执行

from typing import List, Dict, Any, Optional
from datetime import datetime
from .state import (
    GameState, DiagnosisResult, Plan, Decision, ExecutionResult, Action, ActionType,
)
from .adapter import GameAdapter
from .llm import LLMClient


class DiagnosisEngine:
    """诊断引擎：定期全面盘点游戏状态，识别瓶颈和风险。"""

    def __init__(self, adapter: GameAdapter, storage=None):
        self.adapter = adapter
        self.storage = storage

    async def diagnose(self, state: GameState) -> DiagnosisResult:
        result = DiagnosisResult(
            game_name=state.game_name,
            current_state=state
        )

        # 安全约束检查（硬约束）
        safety_rules = self.adapter.get_safety_rules()
        for rule in safety_rules.get('hard_constraints', []):
            if self._check_condition(state, rule.get('condition', '')):
                warning = f"[硬约束] {rule.get('description', '')}"
                result.warnings.append(warning)
                action = rule.get('action', 'pause_all')
                result.recommendations.append(action)
                result.bottlenecks.append(rule.get('id', 'hard_constraint'))

        # 软约束检查（仅告警，不强制）
        for rule in safety_rules.get('soft_constraints', []):
            if self._check_condition(state, rule.get('condition', '')):
                result.warnings.append(f"[软约束] {rule.get('description', '')}")
                result.recommendations.append(rule.get('action', 'suggest_sell_excess'))

        # 通用资源上限检查
        bank_used = state.bank_used or 0
        bank_max = state.bank_max or 1
        if bank_used / bank_max > 0.9:
            result.warnings.append('仓库空间紧张')
            result.recommendations.append('sell_excess')

        # 通用战斗安全检查
        if state.combat_active:
            if state.hp and state.max_hp and state.hp / state.max_hp < 0.2:
                result.warnings.append('角色HP过低，建议立即停止战斗')
                result.recommendations.append('stop_combat')

        # 死亡检测
        if state.death_popup_visible:
            result.warnings.append('检测到死亡弹窗，暂停所有操作')
            result.recommendations.append('pause_all')

        # 游戏专用诊断
        custom = await self.adapter.diagnose_custom(state)
        result.warnings.extend(custom.get('warnings', []))
        result.recommendations.extend(custom.get('recommendations', []))

        if self.storage is not None:
            self.storage.save_diagnosis(result)
        return result

    def _build_condition_namespace(self, state: GameState) -> Dict[str, Any]:
        """把 GameState 映射为规则条件可用的一等公民变量。"""
        hp = state.hp or 0
        max_hp = state.max_hp or 1
        bank_used = state.bank_used or 0
        bank_max = state.bank_max or 1
        food_count = 0
        for r in state.resources.values():
            if r.name.lower() in ('food', '食物', 'shrimp', 'shrimps'):
                food_count = int(r.quantity)
                break
        return {
            'hp': hp,
            'max_hp': max_hp,
            'bank_used': bank_used,
            'bank_max': bank_max,
            'gold': state.gold or 0,
            'slayer_coins': state.slayer_coins or 0,
            'food_count': food_count,
            'combat_active': state.combat_active,
            'death_popup_visible': state.death_popup_visible,
            'completion_percent': state.completion_percent or 0.0,
        }

    def _check_condition(self, state: GameState, condition: str) -> bool:
        """在受限命名空间内安全地求值规则条件。

        只暴露基础运算所需的变量，且禁用全部内置函数，防止任意代码执行。
        """
        if not condition:
            return False
        namespace = self._build_condition_namespace(state)
        try:
            return bool(eval(condition, {'__builtins__': {}}, namespace))
        except Exception:
            return False


class PlanningEngine:
    """规划引擎：根据诊断结果生成目标队列。"""

    def __init__(self, adapter: GameAdapter, storage=None):
        self.adapter = adapter
        self.storage = storage

    async def plan(self, diagnosis: DiagnosisResult) -> Plan:
        plan = Plan(game_name=diagnosis.game_name)
        priorities = self.adapter.get_priority_rules()
        plan.short_term_goals = list(priorities.get('short_term', []))
        plan.mid_term_goals = list(priorities.get('mid_term', []))
        plan.long_term_goals = list(priorities.get('long_term', []))

        # 诊断建议以最高优先级插队
        for rec in diagnosis.recommendations:
            if rec not in plan.short_term_goals:
                plan.short_term_goals.insert(0, rec)
        plan.priority_queue = [
            {'action': rec, 'priority': 'critical', 'reason': '诊断推荐'}
            for rec in diagnosis.recommendations
        ]
        return plan


class DecisionEngine:
    """决策引擎：根据规划生成具体操作序列，支持规则匹配 + LLM 辅助。"""

    def __init__(self, adapter: GameAdapter, llm_client: Optional[LLMClient] = None, storage=None):
        self.adapter = adapter
        self.llm_client = llm_client
        self.storage = storage

    async def decide(self, plan: Plan, state: GameState) -> Decision:
        decision = Decision(
            game_name=plan.game_name,
            plan_id=str(id(plan))
        )

        # 1. 规则驱动：处理关键优先级动作
        for item in plan.priority_queue:
            if item.get('priority') == 'critical':
                action = await self._rule_match(item.get('action'), state)
                if action:
                    decision.actions.append(action)

        # 2. LLM 辅助：在规则无法覆盖时补充更优决策
        if self.llm_client is not None and not decision.actions:
            llm_actions = await self._llm_decide(plan, state)
            if llm_actions:
                decision.actions.extend(llm_actions)

        if decision.actions:
            decision.reason = (
                f'基于规划引擎的 {len(plan.priority_queue)} 项优先级推荐，'
                f'生成 {len(decision.actions)} 个操作'
            )
        else:
            decision.reason = '无紧急操作，维持现状'

        if self.storage is not None:
            self.storage.save_decision(decision, state)
        return decision

    async def _rule_match(self, action_key: Optional[str], state: GameState) -> Optional[Action]:
        if not action_key:
            return None
        rule_map = {
            'pause_all': Action(
                action_type=ActionType.WAIT.value, target='body',
                params={'duration': 60}, reason='安全约束触发，暂停所有操作'
            ),
            'stop_combat': Action(
                action_type=ActionType.NAVIGATE.value, target='非战斗技能页',
                reason='HP过低，停止战斗'
            ),
            'sell_excess': Action(
                action_type=ActionType.NAVIGATE.value, target='仓库',
                reason='仓库空间紧张，出售多余物品'
            ),
            'emergency_fish': Action(
                action_type=ActionType.CLICK.value, target='Fishing',
                reason='食物存量不足，紧急钓鱼补充'
            ),
            'pause_gathering': Action(
                action_type=ActionType.WAIT.value, target='body',
                params={'duration': 30}, reason='仓库空间不足，暂停采集'
            ),
            'suggest_sell_excess': Action(
                action_type=ActionType.NAVIGATE.value, target='仓库',
                reason='仓库空间超过阈值，建议出售低价值物品'
            ),
        }
        return rule_map.get(action_key)

    async def _llm_decide(self, plan: Plan, state: GameState) -> List[Action]:
        """调用 LLM 生成操作序列（DeepSeek / OpenAI 兼容接口）。"""
        if not self.llm_client:
            return []

        prompt = self._build_llm_prompt(plan, state)
        try:
            raw = await self.llm_client.chat([
                {'role': 'system', 'content': '你是挂机游戏自动化决策助手，只输出 JSON。'},
                {'role': 'user', 'content': prompt},
            ])
            return self._parse_llm_actions(raw)
        except Exception as e:
            print(f'[Decision] LLM 决策失败（回退规则）: {e}')
            return []

    def _build_llm_prompt(self, plan: Plan, state: GameState) -> str:
        goals = ' | '.join(plan.short_term_goals) or '无'
        skills = ', '.join(
            f'{k}={v.level}' for k, v in list(state.skills.items())[:20]
        ) or '无'
        return (
            '请根据当前游戏状态给出下一步操作。\n'
            f'短期目标: {goals}\n'
            f'金币: {state.gold or 0}, 仓库: {state.bank_used or 0}/{state.bank_max or 0}\n'
            f'战斗: {"是" if state.combat_active else "否"} '
            f'HP: {state.hp or 0}/{state.max_hp or 0}\n'
            f'技能等级: {skills}\n'
            '请严格输出 JSON，格式: {"actions": [{"action_type": "click|navigate|wait", '
            '"target": "目标", "reason": "理由"}]}'
        )

    def _parse_llm_actions(self, raw: str) -> List[Action]:
        import json
        import re

        text = (raw or '').strip()
        # 去掉可能的 markdown 代码块包裹
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text, flags=re.IGNORECASE)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r'\{.*\}', text, re.DOTALL)
            if not m:
                return []
            data = json.loads(m.group(0))

        actions: List[Action] = []
        for item in data.get('actions', []):
            try:
                actions.append(Action(
                    action_type=str(item.get('action_type', 'wait')),
                    target=str(item.get('target', '')),
                    params=item.get('params', {}) or {},
                    reason=str(item.get('reason', 'LLM 决策')),
                ))
            except Exception:
                continue
        return actions


class ExecutionEngine:
    """执行引擎：调用适配器执行决策中的操作序列。"""

    def __init__(self, adapter: GameAdapter, storage=None):
        self.adapter = adapter
        self.storage = storage

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

        if self.storage is not None:
            self.storage.save_execution(result)
        return result
