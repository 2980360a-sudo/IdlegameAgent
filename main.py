# IdleAgent v0.2.0 - main.py
# Generated: 2026-09-01

#!/usr/bin/env python3
# -*- coding: utf-8 -*-'''main.py — IdleAgent 统一入口用法:  python main.py --game melvor --mode auto  python main.py --game melvor --mode inspect  python main.py --game melvor --mode guards  python main.py --config config/rules/melvor_idle.yaml'''
import asyncio
import argparse
import json
import os
import sys
from dotenv 
import load_dotenv
# 加载环境变量load_dotenv()sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.browser 
import BrowserManager, log
from core.engine 
import DiagnosisEngine, PlanningEngine, DecisionEngine, ExecutionEngine
from core.scheduler 
import AgentScheduler
from core.safety 
import dismiss_post_load_modals
from adapters.melvor_idle 
import MelvorIdleAdapterasync 

def run_agent(game_name: str, mode: str = 'auto', config_path: str = None):    '''运行指定游戏的 Agent。    mode: auto | inspect | guards | manual    '''    log(f'===== IdleAgent 启动 | 游戏: {game_name} | 模式: {mode} =====')    
# 加载游戏配置    if config_path is None:        config_path = f'config/rules/{game_name.replace(' ', '_').lower()}.yaml'    
# 创建适配器    if game_name.lower() in ('melvor_idle', 'melvor idle', 'melvor'):        adapter = MelvorIdleAdapter({'name': 'Melvor Idle', 'url': 'https://melvoridle.com/index_game.php'})    else:        raise ValueError(f'不支持的游戏: {game_name}')    
# 启动浏览器    page = await adapter.browser.launch()    await adapter.browser.navigate()    
# 启动序列    await adapter.browser.boot_sequence()    
# 创建引擎    diagnosis_engine = DiagnosisEngine(adapter)    planning_engine = PlanningEngine(adapter)    decision_engine = DecisionEngine(adapter)    execution_engine = ExecutionEngine(adapter)    
# 创建调度器    scheduler = AgentScheduler()    scheduler.start()    
# 定义定时任务    async 

def diagnosis_task():        state = await adapter.read_state(page)        result = await diagnosis_engine.diagnose(state)        log(f'[诊断] 瓶颈: {result.bottlenecks} | 警告: {result.warnings} | 建议: {result.recommendations}')    async 

def decision_task():        state = await adapter.read_state(page)        diagnosis = await diagnosis_engine.diagnose(state)        plan = await planning_engine.plan(diagnosis)        decision = await decision_engine.decide(plan, state)        result = await execution_engine.execute(page, decision)        log(f'[决策] 执行 {result.actions_executed} 个操作 | 成功: {result.success}')    async 

def emergency_task():        events = await adapter.watch_events(page)        for event in events:            if event.severity == 'critical':                log(f'[紧急] {event.event_type}: {event.details}')                
# 触发硬约束响应                
# TODO: 实现紧急暂停逻辑    async 

def patrol_task():        if hasattr(adapter, 'guards'):            result = await adapter.guards(page)            log(f'[巡检] 守卫结果: {json.dumps(result, ensure_ascii=False, default=str)[:200]}')    
# 注册定时任务    if mode == 'auto':        scheduler.schedule_diagnosis(diagnosis_task)        scheduler.schedule_decision(decision_task)        scheduler.schedule_emergency(emergency_task)        scheduler.schedule_patrol(patrol_task)        log('自动模式已启动，按 Ctrl+C 停止')        try:            while True:                await asyncio.sleep(1)        except KeyboardInterrupt:            log('收到停止信号')    elif mode == 'inspect':        state = await adapter.read_state(page)        print(json.dumps(state.model_dump(), ensure_ascii=False, indent=2))    elif mode == 'guards':        if hasattr(adapter, 'guards'):            result = await adapter.guards(page)            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))        else:            log('该游戏适配器不支持 guards 模式')    elif mode == 'manual':        log('手动模式：请通过 Web 控制台操作')        
# TODO: 启动 Web 控制台服务    
# 清理    scheduler.stop()    await adapter.browser.close()    log('===== IdleAgent 已停止 =====')

def main():    parser = argparse.ArgumentParser(description='IdleAgent — 通用挂机游戏 Agent 框架')    parser.add_argument('--game', '-g', default='melvor_idle', help='游戏名称 (默认: melvor_idle)')    parser.add_argument('--mode', '-m', default='auto', choices=['auto', 'inspect', 'guards', 'manual'], help='运行模式')    parser.add_argument('--config', '-c', help='规则配置文件路径')    args = parser.parse_args()    asyncio.run(run_agent(args.game, args.mode, args.config))

if __name__ == '__main__':    main()