#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# IdleAgent v0.6.0 - scripts/patrol.py
# Melvor Idle 每小时巡检守卫（基于框架适配器，脱敏版）
#
# 用法:
#   python scripts/patrol.py guards   # 守卫：药剂修正 + 动作恢复
#   python scripts/patrol.py inspect  # 巡检：读取状态 + 截图 + 强制保存

import asyncio
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.melvor_idle import MelvorIdleAdapter
from core.browser import log, ts_now

BASE = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.environ.get('STATE_DIR', os.path.join(BASE, 'state'))
SHOT_DIR = os.environ.get('SHOT_DIR', os.path.join(BASE, 'shots'))


async def run(mode: str = 'inspect') -> int:
    started = ts_now()
    log(f'===== patrol.py v0.6.0 {mode} 启动 ({started}) =====')

    adapter = MelvorIdleAdapter()
    page = await adapter.browser.launch()
    result = {'mode': mode, 'started': started, 'agent': 'patrol.py v0.6.0'}

    try:
        await adapter.browser.navigate()
        await adapter.browser.boot_sequence()

        if mode == 'guards':
            result['guards'] = await adapter.guards(page)
        else:
            state = await adapter.read_state(page)
            result['state'] = state.model_dump()

        os.makedirs(SHOT_DIR, exist_ok=True)
        shot = os.path.join(SHOT_DIR, f'{started}.png')
        await page.screenshot(path=shot, full_page=False)
        result['screenshot'] = shot
        result['save_ok'] = await adapter.browser.force_save()
        result['ok'] = True
    except Exception as e:
        result['ok'] = False
        result['error'] = f'{type(e).__name__}: {e}'
        log(f'!! 异常: {result["error"]}')
    finally:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(os.path.join(STATE_DIR, f'{started}.json'), 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        log(f'状态已写入 {STATE_DIR}/{started}.json')

        await adapter.browser.close()
        log('===== 运行结束 =====')

    return 0 if result.get('ok') else 1


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'inspect'
    sys.exit(asyncio.run(run(mode)))
