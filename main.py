#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""main.py — IdleAgent 统一入口

用法:
  python main.py --game melvor_idle --mode auto
  python main.py --game melvor_idle --mode inspect
  python main.py --game melvor_idle --mode guards
  python main.py --game melvor_idle --mode manual
"""
import asyncio
import argparse
import json
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.engine import DiagnosisEngine, PlanningEngine, DecisionEngine, ExecutionEngine
from core.scheduler import AgentScheduler
from core.llm import LLMClient
from core.storage import Storage
from core.state import Action
from core.browser import log
from adapters.melvor_idle import MelvorIdleAdapter

# 游戏名 -> 适配器工厂
GAME_FACTORY = {
    'melvor_idle': MelvorIdleAdapter,
    'melvor idle': MelvorIdleAdapter,
    'melvor': MelvorIdleAdapter,
}

GAME_URLS = {
    'melvor_idle': 'https://melvoridle.com/index_game.php',
    'melvor idle': 'https://melvoridle.com/index_game.php',
    'melvor': 'https://melvoridle.com/index_game.php',
}


async def run_agent(game_name: str, mode: str = 'auto', config_path: str = None):
    log(f'===== IdleAgent 启动 | 游戏: {game_name} | 模式: {mode} =====')

    key = game_name.lower()
    adapter_cls = GAME_FACTORY.get(key)
    if adapter_cls is None:
        raise ValueError(f'不支持的游戏: {game_name}')

    adapter = adapter_cls({
        'name': 'Melvor Idle',
        'url': GAME_URLS.get(key, 'https://melvoridle.com/index_game.php'),
    })

    # 持久化 + 可选 LLM
    storage = Storage()
    llm = LLMClient() if LLMClient().configured else None

    # 启动浏览器
    page = await adapter.browser.launch()
    await adapter.browser.navigate()
    await adapter.browser.boot_sequence()

    # 四层引擎
    diagnosis_engine = DiagnosisEngine(adapter, storage=storage)
    planning_engine = PlanningEngine(adapter, storage=storage)
    decision_engine = DecisionEngine(adapter, llm_client=llm, storage=storage)
    execution_engine = ExecutionEngine(adapter, storage=storage)

    try:
        if mode == 'inspect':
            state = await adapter.read_state(page)
            storage.save_state(state)
            print(json.dumps(state.model_dump(), ensure_ascii=False, indent=2, default=str))

        elif mode == 'guards':
            if hasattr(adapter, 'guards'):
                result = await adapter.guards(page)
                print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
            else:
                log('该游戏适配器不支持 guards 模式')

        elif mode == 'manual':
            log('手动模式：请通过 Web 控制台操作')
            log('  启动 API: python -m uvicorn api.app:app --host 0.0.0.0 --port 8000')

        else:  # auto
            scheduler = AgentScheduler()
            scheduler.start()
            paused = {'flag': False}

            async def diagnosis_task():
                state = await adapter.read_state(page)
                storage.save_state(state)
                result = await diagnosis_engine.diagnose(state)
                log(f'[诊断] 警告: {result.warnings} | 建议: {result.recommendations}')

            async def decision_task():
                if paused['flag']:
                    return
                state = await adapter.read_state(page)
                diagnosis = await diagnosis_engine.diagnose(state)
                plan = await planning_engine.plan(diagnosis)
                decision = await decision_engine.decide(plan, state)
                result = await execution_engine.execute(page, decision)
                log(f'[决策] 执行 {result.actions_executed} 个操作 | 成功: {result.success}')

            async def emergency_task():
                events = await adapter.watch_events(page)
                for event in events:
                    if event.severity == 'critical':
                        log(f'[紧急] {event.event_type}: {event.details}')
                        storage.add_log('critical', 'monitor', f'紧急事件: {event.event_type}', event.details)
                        if event.event_type == 'death':
                            paused['flag'] = True
                            await adapter.execute_action(page, Action(
                                action_type='wait', target='body',
                                params={'duration': 300}, reason='角色死亡，暂停操作'
                            ))

            async def patrol_task():
                if hasattr(adapter, 'guards'):
                    result = await adapter.guards(page)
                    log(f'[巡检] 守卫结果: {json.dumps(result, ensure_ascii=False, default=str)[:200]}')

            scheduler.schedule_diagnosis(diagnosis_task)
            scheduler.schedule_decision(decision_task)
            scheduler.schedule_emergency(emergency_task)
            scheduler.schedule_patrol(patrol_task)
            log('自动模式已启动，按 Ctrl+C 停止')

            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                log('收到停止信号')
            finally:
                scheduler.stop()

    finally:
        await adapter.browser.close()
        storage.close()

    log('===== IdleAgent 已停止 =====')


def main():
    parser = argparse.ArgumentParser(description='IdleAgent — 通用挂机游戏 Agent 框架')
    parser.add_argument('--game', '-g', default='melvor_idle', help='游戏名称 (默认: melvor_idle)')
    parser.add_argument('--mode', '-m', default='auto',
                        choices=['auto', 'inspect', 'guards', 'manual'], help='运行模式')
    parser.add_argument('--config', '-c', help='规则配置文件路径（可选，适配器默认自动加载）')
    args = parser.parse_args()
    asyncio.run(run_agent(args.game, args.mode, args.config))


if __name__ == '__main__':
    main()
