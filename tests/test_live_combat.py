#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真实浏览器验证：战斗执行（区域/屠杀）用正确中文名。"""
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


async def state(page):
    return await page.evaluate("""() => ({
        action: game.activeAction ? game.activeAction.constructor.name : null,
        combatActive: game.combat ? game.combat.isActive : false,
        combatMonster: game.combat && game.combat.selectedMonster ? game.combat.selectedMonster.name : null,
    })""")


async def main():
    adapter = MelvorIdleAdapter()
    page = await adapter.login_cloud(os.environ.get('MELVOR_ACCOUNT'), os.environ.get('MELVOR_PASSWORD'))
    chars = await adapter.list_characters(page)
    if not chars:
        log('无角色'); return
    await adapter.select_character(page, 0)
    log(f'初始: {await state(page)}')

    ok = await adapter.execute_combat_action(page, 'area', '农庄')
    await asyncio.sleep(2)
    log(f'[战斗:area 农庄] ok={ok}, {await state(page)}')

    ok = await adapter.execute_combat_action(page, 'slayer', '半影之间')
    await asyncio.sleep(2)
    log(f'[战斗:slayer 半影之间] ok={ok}, {await state(page)}')

    ok = await adapter.execute_skill_action(page, 'Astrology', '海密尔')
    await asyncio.sleep(2)
    log(f'[星象:海密尔] ok={ok}, {await state(page)}')

    await adapter.browser.close()


if __name__ == '__main__':
    asyncio.run(main())
