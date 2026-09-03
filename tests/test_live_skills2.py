#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真实浏览器验证：扒窃/灵巧 执行（修正后）。"""
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
    return await page.evaluate("() => ({ action: game.activeAction ? game.activeAction.constructor.name : null })")


async def main():
    adapter = MelvorIdleAdapter()
    page = await adapter.login_cloud(os.environ.get('MELVOR_ACCOUNT'), os.environ.get('MELVOR_PASSWORD'))
    chars = await adapter.list_characters(page)
    if not chars:
        log('无角色'); return
    await adapter.select_character(page, 0)
    log(f'初始: {await state(page)}')

    ok = await adapter.execute_skill_action(page, 'Thieving', '男人')
    await asyncio.sleep(2)
    log(f'[扒窃:男人] ok={ok}, {await state(page)}')

    ok = await adapter.execute_skill_action(page, 'Agility', '任意')
    await asyncio.sleep(2)
    log(f'[灵巧] ok={ok}, {await state(page)}')

    ok = await adapter.execute_skill_action(page, 'Astrology', '海密尔')
    await asyncio.sleep(2)
    log(f'[恢复星象] ok={ok}, {await state(page)}')

    await adapter.browser.close()


if __name__ == '__main__':
    asyncio.run(main())
