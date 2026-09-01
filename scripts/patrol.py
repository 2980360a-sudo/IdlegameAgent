#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# IdleAgent v0.2.0 - scripts/patrol.py
# Generated: 2026-09-01

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# IdleAgent v0.2.0 - scripts/patrol.py
# 梅尔沃放置 每小时巡检守卫（脱敏版）

import asyncio
import json
import os
import datetime
from playwright.async_api import async_playwright

ACCOUNT = os.environ.get('MELVOR_ACCOUNT', '')
PASSWORD = os.environ.get('MELVOR_PASSWORD', '')
if not ACCOUNT or not PASSWORD:
    print('错误: 请设置环境变量 MELVOR_ACCOUNT 和 MELVOR_PASSWORD', file=__import__('sys').stderr)
    __import__('sys').exit(1)

BASE = os.path.dirname(os.path.abspath(__file__))
PROFILE = os.environ.get('BROWSER_PROFILE', '/tmp/melvor_profile')
STATE_DIR = os.path.join(BASE, 'state')
SHOT_DIR = os.path.join(BASE, 'shots')
for d in (PROFILE, STATE_DIR, SHOT_DIR):
    os.makedirs(d, exist_ok=True)

GAME_URL = 'https://melvoridle.com/index_game.php'
BLOCK_SUBSTR = [
    'mod.io', 'googlesyndication', 'doubleclick', 'googletagmanager',
    'google-analytics', 'googleadservices', 'facebook.net', 'facebook.com',
    'cloudflareinsights', 'hotjar', 'sentry.io',
]

def log(msg):
    print(f'[{datetime.datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)

def ts_now():
    return datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

# ===== 启动序列（复用 melvor.py 逻辑）=====
async def dismiss_post_load_modals(page, max_rounds=4):
    for _ in range(max_rounds):
        try:
            btn = page.locator(
                'button.swal2-confirm:visible, button:has-text("好"):visible, '
                'button:has-text("关闭"):visible, button:has-text("知道了"):visible, '
                'button:has-text("确定"):visible, button:has-text("OK"):visible, '
                'button:has-text("Close"):visible'
            ).first
            if await btn.count():
                t = (await btn.inner_text()).strip()
                await btn.click(timeout=3000)
                await page.wait_for_timeout(800)
            else:
                return
        except Exception:
            return

async def boot_to_char_select(page, timeout_ms=200000):
    login_done = False
    start = asyncio.get_event_loop().time()
    while True:
        try:
            body = await page.inner_text('body')
            demo = ('这是试玩版本' in body) or ('DEMO VERSION' in body)
            at_char_select = ('选择你的角色' in body) or ('Save Slot' in body)
            if not demo and at_char_select:
                log('到达角色选择页（已登录）')
                return
            if demo and not login_done:
                entry = page.locator('text=云账:visible').first
                if await entry.count():
                    await entry.click(timeout=15000)
                    await page.wait_for_timeout(2500)
                    pwd = page.locator('input[type="password"]:visible').first
                    await pwd.wait_for(state='visible', timeout=60000)
                    user_box = page.locator('input[type="text"]:visible, input[type="email"]:visible').first
                    await user_box.fill(ACCOUNT)
                    await pwd.fill(PASSWORD)
                    await page.wait_for_timeout(600)
                    submit = page.locator('button:has-text("Sign In"):visible, button:has-text("登录"):visible').first
                    if await submit.count():
                        await submit.click()
                    else:
                        await pwd.press('Enter')
                    await page.wait_for_timeout(6000)
                    login_done = True
                    continue
        except Exception as e:
            log(f'boot轮询异常(忽略): {type(e).__name__}')
        if (asyncio.get_event_loop().time() - start) * 1000 > timeout_ms:
            raise TimeoutError('等待角色选择页超时')
        await page.wait_for_timeout(2500)

async def load_newest_save(page):
    deadline = asyncio.get_event_loop().time() + 60
    while asyncio.get_event_loop().time() < deadline:
        body = await page.inner_text('body')
        if ('Save Slot' in body or '存档栏位' in body) and ('最后保存' in body or 'Last Save' in body):
            break
        await page.wait_for_timeout(2000)
    else:
        raise TimeoutError('角色选择页60秒内槽位未就绪')
    slot = page.locator('text=最后保存:visible, text=Last Save:visible').first
    if await slot.count():
        await slot.click(timeout=15000)
        log('点击存档槽')
    await page.wait_for_timeout(3000)
    confirm = page.locator('button:has-text("确认"):visible, button:has-text("Confirm"):visible').first
    if await confirm.count():
        await confirm.click(timeout=15000)
    log('存档加载指令已发出')

async def wait_game_ready(page, timeout_ms=200000):
    deadline = asyncio.get_event_loop().time() + timeout_ms / 1000
    while asyncio.get_event_loop().time() < deadline:
        try:
            body = await page.inner_text('body')
            if '仓库' in body or 'Bank' in body:
                break
        except Exception:
            pass
        await page.wait_for_timeout(3000)
    else:
        raise TimeoutError('等待游戏主界面超时')
    for wait_s in [8, 6, 6]:
        await page.wait_for_timeout(wait_s * 1000)
        await dismiss_post_load_modals(page)
    log('游戏UI就绪')

# ===== 守卫核心 =====
async def guards(page):
    out = {}
    act = await page.evaluate('''() => {
        const o = { action: game.activeAction ? game.activeAction.constructor.name : null, potions: [] };
        for (const [k, v] of game.potions.activePotions)
            o.potions.push(k.id + '=' + (v.item ? v.item.id : '?') + ':' + v.charges);
        return o;
    }''')
    out['before'] = act
    action = act['action']
    astro_potion_ok = any(
        p.startswith('melvorD:Astrology=melvorF:Secret_Stardust_Potion_III')
        for p in act['potions']
    )
    if action not in (None, 'Astrology'):
        out['note'] = f'当前动作={action}，非星象，不干预'
        log(f'[Melvor守卫] {out["note"]}')
        return out
    if not astro_potion_ok:
        log('[Melvor守卫] 星象III级药剂缺失，执行修正')
        await nav_to(page, ['Astrology', '星象学'])
        await page.wait_for_timeout(3000)
        btn = page.locator('#page-header-potions-dropdown')
        if await btn.count():
            await btn.first.click()
            await page.wait_for_timeout(2500)
        out['potion_click'] = await page.evaluate('''(name) => {
            const els = [...document.querySelectorAll('*')].filter(e =>
                e.offsetParent !== null && (e.innerText || '').trim() === name);
            els.sort((a, b) => a.innerHTML.length - b.innerHTML.length);
            for (const el of els) {
                let cur = el;
                for (let i = 0; i < 8 && cur; i++) {
                    const btn = [...cur.querySelectorAll('button')].find(b =>
                        (/^(选择|Select)$/.test((b.innerText || '').trim())) && !b.disabled);
                    if (btn) { btn.click(); return 'clicked'; }
                    cur = cur.parentElement;
                }
            }
            return 'nobtn';
        }''', '秘密星尘药水 III')
        await page.wait_for_timeout(2000)
        await page.keyboard.press('Escape')
        await page.wait_for_timeout(1000)
        after = await page.evaluate('''() => {
            const o = { action: game.activeAction ? game.activeAction.constructor.name : null, potions: [] };
            for (const [k, v] of game.potions.activePotions)
                o.potions.push(k.id + '=' + (v.item ? v.item.id : '?') + ':' + v.charges);
            return o;
        }''')
        out['potion_after'] = after['potions']
        out['potion_ok'] = any(
            p.startswith('melvorD:Astrology=melvorF:Secret_Stardust_Potion_III')
            for p in after['potions']
        )
        log(f'[Melvor守卫] 药剂修正 {out["potion_click"]} -> ok={out["potion_ok"]}')
    else:
        out['potion_ok'] = True
    if action is None:
        log('[Melvor守卫] 动作空转，恢复研究海密尔')
        await nav_to(page, ['Astrology', '星象学'])
        await page.wait_for_timeout(3000)
        cur = await page.evaluate('() => game.activeAction ? game.activeAction.constructor.name : null')
        if cur != 'Astrology':
            out['study_click'] = await page.evaluate('''(name) => {
                const els = [...document.querySelectorAll('*')].filter(e =>
                    e.offsetParent !== null && (e.innerText || '').trim() === name);
                els.sort((a, b) => a.innerHTML.length - b.innerHTML.length);
                for (const el of els) {
                    let cur = el;
                    for (let i = 0; i < 8 && cur; i++) {
                        const btn = [...cur.querySelectorAll('button')].find(b =>
                            (b.innerText || '').trim() === '研究' && !b.disabled);
                        if (btn) { btn.click(); return 'clicked'; }
                        cur = cur.parentElement;
                    }
                }
                return 'nobtn';
            }''', '海密尔')
            await page.wait_for_timeout(2500)
        out['study_after'] = await page.evaluate(
            '() => game.activeAction ? game.activeAction.constructor.name : null')
        log(f'[Melvor守卫] 恢复研究 {out.get("study_click", "already")} -> {out["study_after"]}')
    return out

async def nav_to(page, names, _retried=False):
    for n in names:
        for css in [f'a.nav-link:has-text("{n}"):visible', f'a:has-text("{n}"):visible']:
            loc = page.locator(css).first
            try:
                if await loc.count():
                    await loc.click(timeout=8000)
                    log(f'导航到: {n}')
                    return True
            except Exception:
                continue
    if not _retried:
        log(f'导航受阻，清弹窗后重试: {names}')
        await dismiss_post_load_modals(page, max_rounds=3)
        await page.wait_for_timeout(1200)
        return await nav_to(page, names, _retried=True)
    log(f'导航失败: {names}')
    return False

async def force_save(page):
    try:
        await dismiss_post_load_modals(page)
        for css in ['button:has-text("Force Save"):visible', 'button:has-text("强制保存"):visible']:
            btn = page.locator(css).first
            if await btn.count():
                try:
                    await btn.click(timeout=8000)
                    await page.wait_for_timeout(5000)
                    log('强制保存已点击')
                    return True
                except Exception:
                    pass
        log('强制保存未执行（由自动存档保底）')
        return False
    except Exception as e:
        log(f'强制保存失败: {type(e).__name__}')
        return False

# ===== 主函数 =====
async def run(mode='inspect'):
    started = ts_now()
    log(f'===== patrol.py v0.2.0 {mode} 启动 ({started}) =====')
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            PROFILE, headless=True,
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN', timezone_id='Asia/Shanghai',
            args=['--disable-dev-shm-usage', '--disable-blink-features=AutomationControlled']
        )
        await ctx.route('**/*', lambda route: (
            route.abort() if any(b in route.request.url for b in BLOCK_SUBSTR)
            else route.continue_()
        ))
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        result = {'mode': mode, 'started': started, 'agent': 'patrol.py v0.2.0'}
        try:
            log('打开游戏页...')
            await page.goto(GAME_URL, wait_until='domcontentloaded', timeout=90000)
            await boot_to_char_select(page)
            await load_newest_save(page)
            await wait_game_ready(page)
            if mode == 'guards':
                result['guards'] = await guards(page)
            else:
                state = await page.evaluate('''() => {
                    const g = (fn, d=null) => { try { const v = fn(); return v === undefined ? d : v; } catch(e) { return d; } };
                    return {
                        gp: g(() => game.gp.amount),
                        activeAction: g(() => game.activeAction ? game.activeAction.constructor.name : null),
                        bank: g(() => ({ used: game.bank.occupiedSlots, max: game.bank.maximumSlots })),
                    };
                }''')
                result['state'] = state
            shot = os.path.join(SHOT_DIR, f'{started}.png')
            await page.screenshot(path=shot, full_page=False)
            result['screenshot'] = shot
            result['save_ok'] = await force_save(page)
            result['ok'] = True
        except Exception as e:
            result['ok'] = False
            result['error'] = f'{type(e).__name__}: {e}'
            log(f'!! 异常: {result["error"]}')
        finally:
            payload = json.dumps(result, ensure_ascii=False, indent=2)
            try:
                out = os.path.join(STATE_DIR, f'{started}.json')
                with open(out, 'w', encoding='utf-8') as f:
                    f.write(payload)
                log(f'状态已写入 {out}')
            except Exception as e:
                log(f'状态写入失败: {e}')
            await ctx.close()
            log('===== 运行结束 =====')
    return 0 if result.get('ok') else 1

if __name__ == '__main__':
    mode = __import__('sys').argv[1] if len(__import__('sys').argv) > 1 else 'inspect'
    __import__('sys').exit(asyncio.run(run(mode)))
