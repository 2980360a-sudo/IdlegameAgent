#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真实浏览器验证：通用技能动作执行器（selectTree / selectRecipeOnClick+start / studyConstellationOnClick）。"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from adapters.melvor_idle import MelvorIdleAdapter
from core.browser import log


async def cur_action(page):
    return await page.evaluate("() => game.activeAction ? game.activeAction.constructor.name : null")


async def main():
    adapter = MelvorIdleAdapter()
    page = await adapter.login_cloud(os.environ.get('MELVOR_ACCOUNT'), os.environ.get('MELVOR_PASSWORD'))
    chars = await adapter.list_characters(page)
    if not chars:
        log('无角色'); return
    await adapter.select_character(page, 0)
    log(f'初始动作: {await cur_action(page)}')

    # 1) 伐木普通树
    ok1 = await adapter.execute_skill_action(page, 'Woodcutting', '普通树')
    await asyncio.sleep(2)
    log(f'[伐木:普通树] ok={ok1}, 动作={await cur_action(page)}')

    # 2) 锻造青铜锭
    ok2 = await adapter.execute_skill_action(page, 'Smithing', '青铜锭')
    await asyncio.sleep(2)
    log(f'[锻造:青铜锭] ok={ok2}, 动作={await cur_action(page)}')

    # 3) 恢复星象研究海密尔
    ok3 = await adapter.execute_skill_action(page, 'Astrology', '海密尔')
    await asyncio.sleep(2)
    log(f'[星象:海密尔] ok={ok3}, 动作={await cur_action(page)}')

    await adapter.browser.close()


if __name__ == '__main__':
    asyncio.run(main())
