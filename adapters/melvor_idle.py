# IdleAgent v0.2.0 - adapters/melvor_idle.py
# Generated: 2026-09-01

# adapters/melvor_idle.py — Melvor Idle 专用适配器
import asyncio
import json
import os
import re
import datetime
from typing 
import List, Dict, Any, Optional
from playwright.async_api 
import Page
from core.adapter 
import GameAdapter
from core.state 
import GameState, GameEvent, Action, DOMMap, SkillInfo
from core.browser 
import BrowserManager, log, parse_save_time
from core.safety 
import dismiss_post_load_modals, safe_confirm, click_text_btn
# 从环境变量读取账号（脱敏）
MELVOR_ACCOUNT = os.environ.get('MELVOR_ACCOUNT', '')
MELVOR_PASSWORD = os.environ.get('MELVOR_PASSWORD', '')

class MelvorIdleAdapter(GameAdapter):    '''Melvor Idle 游戏适配器。    封装了 melvor.py 中所有 Melvor 专用逻辑：    - 状态抓取（JS 全局对象深度探测）    - 城镇维护自动化    - 药剂修正守卫    - 战斗安全检查    - 农务管理    '''    

def __init__(self, config: Dict[str, Any]):        super().__init__(config)        self.browser = BrowserManager(            game_url='https://melvoridle.com/index_game.php',            account=MELVOR_ACCOUNT,            password=MELVOR_PASSWORD,        )    
# ========== GameAdapter 接口实现 ==========    async 

def read_state(self, page: Page) -> GameState:        '''从 Melvor Idle 页面提取统一状态。'''        state = GameState(game_name='Melvor Idle', captured_at=datetime.datetime.now())        body = await page.inner_text('body')        
# 金币        m = re.search(r'(d+(?:.d+)?)s*(百万|亿)s*n仓库', body)        if m:            
# 简化处理，实际需要更精确的解析            state.gold = 0        
# 仓库        m = re.search(r'仓库s*?n?s*(d+)s*/s*(d+)', body)        if m:            state.bank_used, state.bank_max = int(m.group(1)), int(m.group(2))        
# 屠杀币        m = re.search(r'屠杀者s*?n?s*([d,]+)', body)        if m:            state.slayer_coins = int(m.group(1).replace(',', ''))        
# JS 全局探测        probe = await page.evaluate('() => ({ hasGame: (typeof game !== ''undefined'') })')        if probe.get('hasGame'):            js_dump = await page.evaluate(self._DUMP_STATE_JS)            state.raw_probe = js_dump            
# 解析技能            if 'skills' in js_dump:                for sid, info in js_dump['skills'].items():                    state.skills[sid] = SkillInfo(                        name=sid, level=info.get('lv', 0), xp=info.get('xp', 0)                    )            
# 解析战斗状态            if 'combat' in js_dump:                c = js_dump['combat']                state.combat_active = c.get('isActive', False)                state.hp = c.get('hp')            
# 当前动作            state.active_action = js_dump.get('activeAction')            
# 星象            if 'astro' in js_dump:                state.skills['astrology'] = SkillInfo(                    name='astrology',                    level=js_dump['astro'].get('lv', 0),                    xp=js_dump['astro'].get('xp', 0),                )            
# 药剂            state.active_potions = js_dump.get('potions', [])            
# 城镇            state.township = {'level': js_dump.get('township', {}).get('lv')}        return state    async 

def execute_action(self, page: Page, action: Action) -> bool:        '''执行 Melvor 专用操作。'''        if action.action_type == 'navigate':            return await self.browser.nav_to([action.target])        elif action.action_type == 'click':            result = await click_text_btn(page, [action.target])            return result is not None        elif action.action_type == 'js':            
# 执行自定义 JS            await page.evaluate(action.target, action.params.get('arg'))            return True        elif action.action_type == 'wait':            await page.wait_for_timeout(action.params.get('ms', 2000))            return True        return False    

def map_dom(self, raw_html: str) -> DOMMap:        '''Melvor Idle DOM 映射。'''        return DOMMap(            game_name='Melvor Idle',            selectors={                'skill_label': '.nav-link .nav-main-link-name',                'bank_slot': '.bank-item',                'combat_hp': '#combat-player-hitpoints',                'force_save_btn': 'button:has-text(''Force Save''), button:has-text(''强制保存'')',                'modal_confirm': 'button.swal2-confirm',                'modal_cancel': 'button.swal2-cancel',            }        )    async 

def watch_events(self, page: Page) -> List[GameEvent]:        '''监听 Melvor 游戏事件。'''        events = []        body = await page.inner_text('body')        
# 检测弹窗        modal = await page.locator('.swal2-popup:visible').count()        if modal > 0:            events.append(GameEvent(                event_type='modal', severity='warning',                details={'body': body[:200]}            ))        
# 检测死亡        if '你死了' in body or 'You died' in body:            events.append(GameEvent(                event_type='death', severity='critical',                details={'message': '角色死亡 detected'}            ))        
# 检测战斗状态        combat_active = await page.evaluate('() => game.combat ? game.combat.isActive : false')        if combat_active:            hp = await page.evaluate('() => game.combat.player ? game.combat.player.hitpoints : 0')            max_hp = await page.evaluate('() => game.combat.player ? game.combat.player.maxHitpoints : 1')            if hp / max_hp < 0.2:                events.append(GameEvent(                    event_type='low_hp', severity='critical',                    details={'hp': hp, 'max_hp': max_hp}                ))        return events    
# ========== 游戏专用诊断扩展 ==========    async 

def diagnose_custom(self, state: GameState) -> Dict[str, Any]:        '''Melvor 专用诊断。'''        result = {'warnings': [], 'recommendations': []}        
# 药剂检查        potions = state.active_potions        astro_ok = any('Astrology=melvorF:Secret_Stardust_Potion_III' in str(p) for p in potions)        if not astro_ok and state.active_action == 'Astrology':            result['warnings'].append('星象III级药剂缺失')            result['recommendations'].append('activate_astro_potion')        
# 动作空转检查        if state.active_action is None:            result['warnings'].append('动作空转')            result['recommendations'].append('resume_study')        return result    
# ========== 守卫操作 ==========    async 

def guards(self, page: Page) -> Dict[str, Any]:        '''巡检守卫：①动作空转→恢复研究 ②星象药剂≠III级→修正。'''        out = {}        act = await page.evaluate(self._READ_ACTION_POTIONS_JS)        out['before'] = act        action = act['action']        astro_potion_ok = any(            p.startswith('melvorD:Astrology=melvorF:Secret_Stardust_Potion_III')            for p in act['potions']        )        if action not in (None, 'Astrology'):            out['note'] = f'当前动作={action}，非星象，不干预'            log(f'[Melvor守卫] {out[''note'']}')            return out        if not astro_potion_ok:            log('[Melvor守卫] 星象III级药剂缺失，执行修正')            await self._fix_potion(page, '秘密星尘药水 III', out)        else:            out['potion_ok'] = True        if action is None:            log('[Melvor守卫] 动作空转，恢复研究海密尔')            await self._resume_study(page, '海密尔', out)        return out    async 

def _fix_potion(self, page: Page, potion_name: str, out: Dict):        '''修正药剂激活。'''        await self.browser.nav_to(['Astrology', '星象学'])        await page.wait_for_timeout(3000)        btn = page.locator('#page-header-potions-dropdown')        if await btn.count():            await btn.first.click()            await page.wait_for_timeout(2500)        out['potion_click'] = await page.evaluate(self._POTION_ACTIVATE_JS, potion_name)        await page.wait_for_timeout(2000)        await page.keyboard.press('Escape')        await page.wait_for_timeout(1000)        after = await page.evaluate(self._READ_ACTION_POTIONS_JS)        out['potion_after'] = after['potions']        out['potion_ok'] = any(            p.startswith('melvorD:Astrology=melvorF:Secret_Stardust_Potion_III')            for p in after['potions']        )        log(f'[Melvor守卫] 药剂修正 {out[''potion_click'']} -> ok={out[''potion_ok'']}')    async 

def _resume_study(self, page: Page, constellation: str, out: Dict):        '''恢复星象研究。'''        await self.browser.nav_to(['Astrology', '星象学'])        await page.wait_for_timeout(3000)        cur = await page.evaluate('() => game.activeAction ? game.activeAction.constructor.name : null')        if cur != 'Astrology':            out['study_click'] = await page.evaluate(self._STUDY_CLICK_JS, constellation)            await page.wait_for_timeout(2500)        out['study_after'] = await page.evaluate(            '() => game.activeAction ? game.activeAction.constructor.name : null')        log(f'[Melvor守卫] 恢复研究 {out.get(''study_click'', ''already'')} -> {out[''study_after'']}')    
# ========== 城镇维护 ==========    async 

def township_repair_all(self, page: Page) -> Dict[str, Any]:        '''城镇一键修复：维修全部 + 建造链。'''        out = {}        await self.browser.nav_to(['Township', '城镇'])        await page.wait_for_timeout(3500)        
# 维修全部        t = await click_text_btn(page, ['维修全部', 'Repair All'])        log(f'[城镇] 点击维修全部: {t}')        await page.wait_for_timeout(2000)        await safe_confirm(page)        await page.wait_for_timeout(2500)        
# 建造链（简化版，实际需要更复杂的逻辑）        return out    
# ========== JS 代码片段 ==========    _
DUMP_STATE_JS = r'''() => {  const g = (fn, d=null) => { try { const v = fn(); return v === undefined ? d : v; } catch(e) { return d; } };  const out = {};  out.gp = g(() => game.gp.amount);  out.slayerCoins = g(() => game.currencies.registeredObjects.get('melvorD:SlayerCoins').amount);  out.skills = {};  g(() => {    for (const [id, s] of game.skills.registeredObjects)      out.skills[id.replace(/^melvorw*:/, '')] =        { lv: s.level, xp: Math.floor(s.xp) };  });  out.bank = {    occupiedSlots: g(() => game.bank.occupiedSlots),    maximumSlots: g(() => game.bank.maximumSlots),  };  out.activeAction = g(() => game.activeAction ? game.activeAction.constructor.name : null);  out.astro = {    lv: g(() => game.astrology.level),    xp: g(() => Math.floor(game.astrology.xp)),    studying: g(() => game.astrology.studiedConstellation ? game.astrology.studiedConstellation.id : null),  };  out.potions = g(() => {    const o = [];    for (const [k, v] of game.potions.activePotions)      o.push({ action: k && k.id ? k.id : String(k), item: v && v.item ? v.item.id : null, charges: v && v.charges !== undefined ? v.charges : null });    return o;  }, []);  out.combat = {    isActive: g(() => game.combat.isActive),    hp: g(() => game.combat.player ? game.combat.player.hitpoints : null),  };  out.township = { lv: g(() => game.township.level) };  out.lastCloudUpdate = g(() => game._lastCloudUpdate);  out.characterName = g(() => game.characterName);  return out;}'''    _
STUDY_CLICK_JS = r'''(name) => {  const els = [...document.querySelectorAll(''*'')].filter(e => e.offsetParent !== null &&    (e.innerText || '').trim() === name);  els.sort((a, b) => a.innerHTML.length - b.innerHTML.length);  for (const el of els) {    let cur = el;    for (let i = 0; i < 8 && cur; i++) {      const btn = [...cur.querySelectorAll('button')].find(b => (b.innerText || '').trim() === '研究' && !b.disabled);      if (btn) { btn.click(); return 'clicked'; }      cur = cur.parentElement;    }  }  return 'nobtn';}'''    _
POTION_ACTIVATE_JS = r'''(name) => {  const els = [...document.querySelectorAll(''*'')].filter(e => e.offsetParent !== null &&    (e.innerText || '').trim() === name);  els.sort((a, b) => a.innerHTML.length - b.innerHTML.length);  for (const el of els) {    let cur = el;    for (let i = 0; i < 8 && cur; i++) {      const btn = [...cur.querySelectorAll('button')].find(b => /^(选择|Select)$/.test((b.innerText || '').trim()) && !b.disabled);      if (btn) { btn.click(); return 'clicked'; }      cur = cur.parentElement;    }  }  return 'nobtn';}'''    _
READ_ACTION_POTIONS_JS = r'''() => {  const o = { action: game.activeAction ? game.activeAction.constructor.name : null, potions: [] };  for (const [k, v] of game.potions.activePotions)    o.potions.push(k.id + '=' + (v.item ? v.item.id : '?') + ':' + v.charges);  return o;}'''