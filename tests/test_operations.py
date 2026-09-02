#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真实账号操作实测（需已安装 chromium + 有效 .env）。

用法: python tests/test_operations.py
逐个执行命名操作并打印结果，便于验证移植的 melvor222.py 逻辑。
"""
import asyncio
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv

load_dotenv()

from adapters.melvor_idle import MelvorIdleAdapter
from core.browser import log


async def main():
    adapter = MelvorIdleAdapter()
    adapter.browser.headless = True
    adapter.browser.profile_dir = os.path.join('state', 'test_profile')

    page = await adapter.login_cloud(
        os.environ.get('MELVOR_ACCOUNT', ''), os.environ.get('MELVOR_PASSWORD', '')
    )
    chars = await adapter.list_characters(page)
    log(f'角色: {chars}')
    await adapter.select_character(page, 0)
    log('已加载存档')

    results = {}

    log('\n=== force_save ===')
    results['force_save'] = await adapter.browser.force_save()

    log('\n=== resume_astrology ===')
    results['resume_astrology'] = await adapter._op_resume_astrology(page)

    log('\n=== farming_plant_harvest ===')
    results['farming_plant_harvest'] = await adapter._op_farming_plant_harvest(page)

    log('\n=== township_repair ===')
    results['township_repair'] = await adapter._op_township_repair(page)

    log('\n=== bank_buy_slots ===')
    results['bank_buy_slots'] = await adapter._op_bank_buy_slots(page)

    log('\n=== brew_stardust ===')
    results['brew_stardust'] = await adapter._op_brew_stardust(page)

    print('\n===== 结果汇总 =====')
    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))

    await adapter.browser.close()


if __name__ == '__main__':
    asyncio.run(main())
