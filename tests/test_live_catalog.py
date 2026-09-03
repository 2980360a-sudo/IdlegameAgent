#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真实浏览器验证：动作目录枚举 + 通用技能动作执行（只读探测优先）。"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 加载 .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from adapters.melvor_idle import MelvorIdleAdapter
from core.browser import log


async def main():
    adapter = MelvorIdleAdapter()
    account = os.environ.get('MELVOR_ACCOUNT') or os.environ.get('GAME_ACCOUNT')
    password = os.environ.get('MELVOR_PASSWORD') or os.environ.get('GAME_PASSWORD')
    log(f'账号: {account}')

    page = await adapter.login_cloud(account, password)
    chars = await adapter.list_characters(page)
    log(f'角色: {chars}')
    if not chars:
        log('无角色，退出')
        return
    ok = await adapter.select_character(page, 0)
    log(f'选角色: {ok}')

    # 只读：动作目录
    catalog = await adapter.probe_action_catalog(page)
    skills = catalog.get('skills') or []
    log(f'技能动作目录: {len(skills)} 个技能')
    for s in skills[:12]:
        log(f"  - {s.get('name')}(Lv{s.get('lv')}): {len(s.get('acts', []))} 个动作, 示例={[a.get('name') for a in s.get('acts', [])[:5]]}")
    log(f'战斗区域: {len(catalog.get("areas") or [])}, 地牢: {len(catalog.get("dungeons") or [])}, 屠杀区域: {len(catalog.get("slayerAreas") or [])}')

    # 记录当前动作（用于测试后判断）
    cur = await page.evaluate("() => game.activeAction ? game.activeAction.constructor.name : null")
    log(f'测试前当前动作: {cur}')

    # 冒烟：测试通用技能动作执行——选一个低风险技能（伐木普通树）
    # 注意：这会改变账号当前动作
    r = await adapter.execute_skill_action(page, 'Woodcutting', '普通树')
    log(f'execute_skill_action(Woodcutting, 普通树) → {r}')
    after = await page.evaluate("() => game.activeAction ? game.activeAction.constructor.name : null")
    log(f'测试后当前动作: {after}')

    await adapter.browser.close()


if __name__ == '__main__':
    asyncio.run(main())
