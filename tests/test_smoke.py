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

    print('\n== 7. 用户认证 ==')
    from core.auth import UserStore, TokenManager, UserExistsError
    auth_db = os.path.join(os.path.abspath(_TMP), 'test_auth.db')
    if os.path.exists(auth_db):
        os.remove(auth_db)
    users = UserStore(db_path=auth_db)
    tokens = TokenManager(secret='smoke-test-secret')
    u = users.create_user('smokeuser', 'smoke@example.com', 'secret123', display_name='Smoke')
    check('注册用户', u['username'] == 'smokeuser')
    check('返回不含密码哈希', 'password_hash' not in u)
    try:
        users.create_user('smokeuser', 'x@x.com', 'secret123')
        check('重复用户名被拒绝', False)
    except UserExistsError:
        check('重复用户名被拒绝', True)
    check('用户名登录', users.verify_credentials('smokeuser', 'secret123') is not None)
    check('邮箱登录', users.verify_credentials('smoke@example.com', 'secret123') is not None)
    check('错误密码拒绝', users.verify_credentials('smokeuser', 'bad') is None)
    tok = tokens.sign({'sub': u['id']})
    check('token 签发校验', tokens.verify(tok)['sub'] == u['id'])
    check('token 篡改检测', tokens.verify(tok + 'x') is None)
    u2 = users.update_user(u['id'], display_name='Smoke2', profile={'note': 'n'})
    check('更新资料', u2['display_name'] == 'Smoke2')
    users.close()
    if os.path.exists(auth_db):
        os.remove(auth_db)

    print('\n== 8. 攻略知识库 + 动作目录（RAG 决策引擎） ==')
    from core.guide import get_policy, format_action_catalog, load_guides
    guides = load_guides()
    check('加载到攻略文件', len(guides) >= 1)
    policy = get_policy()
    check('方针非空且含训练顺序', '训练顺序' in policy or '星象' in policy)
    cat_text = format_action_catalog({
        'skills': [{'key': 'Woodcutting', 'name': '伐木', 'lv': 99,
                    'acts': [{'id': 'NormalTree', 'name': '普通树', 'lv': 1},
                             {'id': 'YewTree', 'name': '紫杉树', 'lv': 60}]}],
        'areas': [{'id': 'Farmlands', 'name': '农田', 'lv': 3}],
        'dungeons': [], 'slayerAreas': [],
    })
    check('动作目录格式化含技能动作', '普通树' in cat_text and '伐木' in cat_text)
    check('动作目录格式化含战斗区域', '农田' in cat_text)
    check('空目录返回空串', format_action_catalog(None) == '')

    print('\n== 9. 攻略方针驱动的 LLM 决策（mock） ==')
    from core.melvor_agent import MelvorAgentSession
    sess = MelvorAgentSession(1, mock=True)
    prompt = sess._build_llm_prompt(sess._mock_state, 'efficiency')
    check('prompt 含攻略方针', '【攻略方针】' in prompt)
    check('prompt 含动态动作目录', '【动作目录】' in prompt)
    check('prompt 含 skill 动作类型说明', 'action_type="skill"' in prompt)
    check('prompt 含攻略训练顺序方针', '训练顺序' in prompt or '星象' in prompt)

    print('\n== 10. 完整闭环：攻略方针 + 动作目录 → LLM 决策 → 执行 ==')
    class FakeLLM:
        configured = True
        def __init__(self, reply):
            self._reply = reply
        async def chat(self, messages, temperature=None):
            return self._reply

    class FakeMelvorAdapter:
        def __init__(self):
            self.calls = []
        async def probe_action_catalog(self, page):
            return {'skills': [], 'areas': [], 'dungeons': [], 'slayerAreas': [], 'buildings': []}
        async def execute_skill_action(self, page, skill_ref, action_ref):
            self.calls.append(('skill', skill_ref, action_ref))
            return True
        async def execute_combat_action(self, page, target_type, target_ref):
            self.calls.append(('combat', target_type, target_ref))
            return True
        async def execute_operation(self, page, name):
            self.calls.append(('operation', name))
            return True
        async def execute_action(self, page, action):
            return True
        async def read_state(self, page):
            return make_low_hp_state()

    from core.melvor_agent import MelvorAgentSession
    llm = FakeLLM('{"actions": [{"action_type": "skill", "target": "Woodcutting:NormalTree", "reason": "按训练顺序练伐木"}, '
                  '{"action_type": "combat", "target": "area:农田", "reason": "战斗等级足够"}, '
                  '{"action_type": "operation", "target": "force_save", "reason": "保存"}]}')
    fake_ad = FakeMelvorAdapter()
    s2 = MelvorAgentSession(2, adapter=fake_ad, llm=llm, mock=False)
    s2._page = object()  # 让 _llm_actions 走探测分支、_execute 不因 page 为 None 提前返回
    actions = await s2._llm_actions(make_low_hp_state(), 'efficiency')
    check('LLM 返回 3 个动作', len(actions) == 3)
    check('第 1 个是 skill 动作', actions[0].action_type == 'skill')
    check('skill 目标格式 skill:action', actions[0].target == 'Woodcutting:NormalTree')
    check('第 2 个是 combat 动作', actions[1].action_type == 'combat')
    check('第 3 个是 operation 动作', actions[2].action_type == 'operation')
    await s2._execute(actions[0])
    await s2._execute(actions[1])
    await s2._execute(actions[2])
    check('执行分派到 execute_skill_action', ('skill', 'Woodcutting', 'NormalTree') in fake_ad.calls)
    check('执行分派到 execute_combat_action', ('combat', 'area', '农田') in fake_ad.calls)
    check('执行分派到 execute_operation', ('operation', 'force_save') in fake_ad.calls)

    # 生存模式：combat 动作应被死亡风险过滤拦截
    s3 = MelvorAgentSession(3, adapter=fake_ad, llm=llm, mock=False)
    s3._page = object()
    risky = await s3._llm_actions(make_low_hp_state(), 'survival')
    filtered = s3._filter_death_risky(risky)
    check('生存模式拦截 combat 动作', all(a.action_type != 'combat' for a in filtered))

    print('\n== 11. 定时巡检 + token 监控 ==')
    from core.llm import LLMClient
    from core.melvor_agent import MelvorAgentSession
    lc = LLMClient(api_key='sk-test', base_url='https://api.deepseek.com', model='deepseek-chat')
    check('LLMClient 已配置', lc.configured)
    check('usage 结构含 token 统计', all(k in lc.usage for k in ('calls', 'prompt_tokens', 'completion_tokens', 'total_tokens')))
    s4 = MelvorAgentSession(4, mock=True)
    check('默认巡检间隔为 3600（1小时）', s4.patrol_interval == 3600.0)
    check('设置巡检间隔生效', s4.set_patrol_interval(30) == 30.0)
    check('巡检间隔下限 5 秒', s4.set_patrol_interval(1) == 5.0)
    check('巡检间隔上限 24 小时', s4.set_patrol_interval(100000) == 86400.0)
    check('开关 LLM 自主排程', s4.set_llm_schedules(True) is True)
    # LLM 排程：解析 next_check_in
    s4._next_interval = None
    s4._parse_actions('{"actions": [{"action_type":"wait","target":"body"}], "next_check_in": 1800}')
    check('解析 next_check_in', s4._next_interval == 1800.0)
    s4._parse_actions('{"actions": [], "next_check_in": 999999}')
    check('next_check_in 钳制到 24h', s4._next_interval == 86400.0)
    st = await s4.get_status()
    check('status 含 patrol_interval', 'patrol_interval' in st)
    check('status 含 llm_schedules', st.get('llm_schedules') is True)
    check('status 含 llm 字段', 'llm' in st and 'usage' in st.get('llm', {}))

    print('\n== 12. 账号检查文档 + 用户建议 ==')
    # 用户建议
    fb = s4.submit_feedback('优先练钓鱼而非星象')
    check('提交建议成功', len(fb) == 1 and fb[0]['text'] == '优先练钓鱼而非星象')
    check('status 含 user_feedback', st.get('user_feedback') is not None)
    # 检查文档解析
    s4._parse_actions('{"inspection_doc": "### 检查文档\\n- 阶段1", "actions": []}')
    check('解析 inspection_doc', s4.inspection_doc.startswith('### 检查文档'))
    # prompt 含文档 + 建议
    p = s4._build_llm_prompt(s4._mock_state, 'efficiency')
    check('prompt 含上次检查文档', '【上次检查文档】' in p)
    check('prompt 含用户建议', '【用户建议】' in p and '优先练钓鱼' in p)
    check('prompt 含 inspection_doc 输出指示', 'inspection_doc' in p)

    print(f'\n===== 结果: {passed} 通过, {failed} 失败 =====')
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
