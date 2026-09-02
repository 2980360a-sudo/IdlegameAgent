#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# IdleAgent v0.4.0 - scripts/melvor.py
# Melvor Idle 完整巡检脚本（基于框架，脱敏版）
#
# 用法:
#   python scripts/melvor.py inspect   # 巡检：读取状态 + 截图 + 强制保存
#   python scripts/melvor.py probe     # 深度探测 window.game 结构

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
    log(f'===== melvor.py v0.4.0 {mode} 启动 ({started}) =====')

    adapter = MelvorIdleAdapter()
    page = await adapter.browser.launch()
    result = {'mode': mode, 'started': started, 'agent': 'melvor.py v0.4.0'}

    try:
        await adapter.browser.navigate()
        await adapter.browser.boot_sequence()

        state = await adapter.read_state(page)
        result['state'] = state.model_dump()

        if mode == 'probe':
            # 深度探测 window.game 顶层结构
            result['game_deep'] = await page.evaluate("""() => {
                const o = {};
                try { o.currentAction = game.activeAction ? game.activeAction.constructor.name : null; } catch(e){}
                try { o.gameKeys = Object.keys(game).slice(0, 150); } catch(e){ o.keysErr = String(e); }
                try { o.bankCount = game.bank ? game.bank.items.length : null; } catch(e){}
                return o;
            }""")

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
        payload = json.dumps(result, ensure_ascii=False, indent=2, default=str)
        with open(os.path.join(STATE_DIR, f'{started}.json'), 'w', encoding='utf-8') as f:
            f.write(payload)
        with open(os.path.join(STATE_DIR, 'latest.json'), 'w', encoding='utf-8') as f:
            f.write(payload)
        log(f'状态已写入 {STATE_DIR}/{started}.json')

        await adapter.browser.close()
        log('===== 运行结束 =====')
        print('RESULT_JSON_BEGIN' + json.dumps(result, ensure_ascii=False, default=str) + 'RESULT_JSON_END', flush=True)

    return 0 if result.get('ok') else 1


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'inspect'
    sys.exit(asyncio.run(run(mode)))
