"""
Melvor Idle 适配器 - v0.6.0
游戏网址: https://melvoridle.com
实现方式: 优先注入 JS 读取 window.game 对象，失败时回退到 DOM 解析
"""
import re
import os
import json
import asyncio
from typing import List, Dict, Any, Optional

from playwright.async_api import Page

from core.adapter import GameAdapter
from core.browser import BrowserManager, log
from core.safety import click_text_btn, safe_confirm, dismiss_post_load_modals
from core.state import (
    GameState, GameEvent, Action, DOMMap,
    ActionType, EventType, SkillInfo, ResourceInfo, EquipmentInfo,
)


# ====================================================================
# 操作 JS 辅助（移植自 melvor222.py 的验证逻辑）
# ====================================================================
_JS_STUDY_CLICK = r"""(name) => {
  const els = [...document.querySelectorAll('*')].filter(e => e.offsetParent !== null &&
    (e.innerText || '').trim() === name);
  els.sort((a, b) => a.innerHTML.length - b.innerHTML.length);
  for (const el of els) {
    let cur = el;
    for (let i = 0; i < 8 && cur; i++) {
      const btn = [...cur.querySelectorAll('button')].find(b => (b.innerText || '').trim() === '研究' && !b.disabled);
      if (btn) { btn.click(); return 'clicked'; }
      cur = cur.parentElement;
    }
  }
  return 'nobtn';
}"""

_JS_POTION_ACTIVATE = r"""(name) => {
  const els = [...document.querySelectorAll('*')].filter(e => e.offsetParent !== null &&
    (e.innerText || '').trim() === name);
  els.sort((a, b) => a.innerHTML.length - b.innerHTML.length);
  for (const el of els) {
    let cur = el;
    for (let i = 0; i < 8 && cur; i++) {
      const btn = [...cur.querySelectorAll('button')].find(b => /^(选择|Select)$/.test((b.innerText || '').trim()) && !b.disabled);
      if (btn) { btn.click(); return 'clicked'; }
      cur = cur.parentElement;
    }
  }
  return 'nobtn';
}"""

_JS_CARD_CLICK = r"""(name) => {
  const els = [...document.querySelectorAll('span,div')].filter(e =>
    e.children.length === 0 && (e.innerText || '').trim() === name && e.offsetParent !== null);
  if (!els.length) return 'notfound:' + name;
  for (const el of els) {
    let card = el;
    for (let i = 0; i < 10 && card; i++) {
      const b = [...card.querySelectorAll('button.btn-success')].find(x =>
        !x.disabled && x.offsetParent !== null && x.querySelector('i.fa-hammer'));
      if (b) { b.click(); return 'clicked'; }
      card = card.parentElement;
    }
  }
  return 'nobtn:' + name + ':' + els.length;
}"""

_JS_HEAL_CLICK = r"""() => {
  // 城镇健康恢复按钮文案形如「+10费用：-2,880」（+1/+5/+10 三档）
  const btns = [...document.querySelectorAll('button')].filter(b => {
    const t = (b.innerText || '').trim().replace(/\s/g, '');
    return /^\+\d+费用/.test(t) && b.offsetParent !== null && !b.disabled;
  });
  if (!btns.length) return 'nobtn';
  const pick = (p) => btns.find(b => (b.innerText || '').trim().replace(/\s/g, '').startsWith(p));
  const target = pick('+10') || pick('+5') || btns[0];
  target.click();
  return 'clicked:' + (target.innerText || '').trim().slice(0, 30);
}"""

_JS_TAB_CLICK = r"""(name) => {
  const els = [...document.querySelectorAll('span,div,h1,h2,h3,h4,h5,h6,p,a,button')].filter(e =>
    e.children.length === 0 && (e.innerText || '').trim() === name && e.offsetParent !== null);
  if (!els.length) return 'notfound:' + name;
  for (const el of els) {
    let t = el;
    for (let i = 0; i < 7 && t; i++) {
      const cs = getComputedStyle(t);
      if (t.tagName === 'BUTTON' || t.tagName === 'A' || cs.cursor === 'pointer') {
        const cls = (t.className || '').toString();
        if (/nav-link|sidebar/i.test(cls)) break;
        t.click();
        return 'clicked:' + t.tagName + ':' + cls.slice(0, 50);
      }
      t = t.parentElement;
    }
  }
  return 'nobtn:' + els.length;
}"""

_JS_SEED_SELECT = r"""(seedName) => {
  const els = [...document.querySelectorAll('div,span,a,button,li')].filter(e =>
    (e.innerText || '').trim() === seedName && e.offsetParent !== null);
  if (!els.length) return 'notfound:' + seedName;
  els.sort((a, b) => (a.innerHTML.length - b.innerHTML.length));
  const el = els[0];
  let t = el;
  for (let i = 0; i < 6 && t; i++) {
    const cls = (t.className || '').toString();
    if (t.tagName === 'BUTTON' || t.tagName === 'A' || /btn|list-group-item|clickable/i.test(cls) ||
        getComputedStyle(t).cursor === 'pointer') { t.click(); return 'clicked-row:' + cls.slice(0, 40); }
    t = t.parentElement;
  }
  el.click();
  return 'clicked-leaf';
}"""

_JS_PLANT_CONFIRM = r"""() => {
  const btns = [...document.querySelectorAll('button')].filter(b =>
    (b.innerText || '').trim() === '种植' && b.offsetParent !== null && !b.disabled);
  if (!btns.length) return 'nobtn';
  btns.sort((a, b) => {
    const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
    return Math.abs(ra.left - 1000) - Math.abs(rb.left - 1000);
  });
  btns[0].click();
  return 'clicked:' + btns.length;
}"""

_JS_PER_PLOT_BTN = r"""() => {
  const btns = [...document.querySelectorAll('button')].filter(b =>
    (b.innerText || '').trim() === '栽培种子' && b.offsetParent !== null && !b.disabled);
  if (!btns.length) return 0;
  btns[0].click();
  return btns.length;
}"""

_JS_BANKSLOT_BUY = r"""() => {
  const leaves = [...document.querySelectorAll('*')].filter(e => e.offsetParent !== null &&
    e.children.length === 0 && /额外仓库栏位|Bank Slot/i.test((e.innerText || '').trim()));
  for (const el of leaves) {
    let cur = el;
    for (let i = 0; i < 8 && cur; i++) {
      if (getComputedStyle(cur).cursor === 'pointer' || cur.tagName === 'BUTTON' ||
          cur.getAttribute('role') === 'button') {
        cur.click();
        return 'clicked-pointer-ancestor';
      }
      cur = cur.parentElement;
    }
  }
  return 'nobtn';
}"""

_JS_BANKSLOT_CONFIRM = r"""() => {
  const pops = [...document.querySelectorAll('.swal2-popup')].filter(p => p.offsetParent !== null);
  if (!pops.length) return 'no-modal';
  const pop = pops[pops.length - 1];
  const txt = (pop.innerText || '');
  if (!/额外仓库栏位/.test(txt)) return 'wrong-modal:' + txt.slice(0, 60).replace(/\n/g, '|');
  const btn = pop.querySelector('.swal2-confirm');
  if (!btn) return 'no-confirm-btn';
  btn.click();
  return 'confirmed';
}"""


class MelvorIdleAdapter(GameAdapter):
    """Melvor Idle 专用适配器。"""

    # ------------------------------------------------------------
    # 初始化：加载规则 + 创建浏览器管理器
    # ------------------------------------------------------------
    def __init__(self, config: Dict[str, Any] = None):
        config = config or {}
        rules = GameAdapter.load_rules('melvor_idle')
        merged = dict(rules)
        merged.update(config)  # 调用方显式传入的配置优先
        merged.setdefault('name', 'Melvor Idle')
        merged.setdefault('url', 'https://melvoridle.com/index_game.php')
        super().__init__(merged)

        # 账号优先取 MELVOR_* 环境变量，兼容 GAME_* 通用变量
        account = os.environ.get('MELVOR_ACCOUNT', '') or os.environ.get('GAME_ACCOUNT', '')
        password = os.environ.get('MELVOR_PASSWORD', '') or os.environ.get('GAME_PASSWORD', '')
        self.browser = BrowserManager(game_url=self.url, account=account, password=password)

    # ------------------------------------------------------------
    # 1. DOM 映射
    # ------------------------------------------------------------
    def map_dom(self, raw_html: str) -> DOMMap:
        """将游戏原始 DOM 映射为统一选择器（DOM 解析兜底用）。"""
        return DOMMap(
            game_name=self.name,
            selectors={
                'gold': '#resource-gold .amount, .resource-gold .amount',
                'slayer_coins': '#resource-slayer-coins .amount',
                'bank_used': '.bank-slots .occupied, #bank-slots-used',
                'bank_max': '.bank-slots .total, #bank-slots-total',
                'hp_text': '#combat-hp-text, .hp-text, .health-text',
                'active_action': '.active-action-name',
            }
        )

    # ------------------------------------------------------------
    # 2. 读取状态（JS 注入优先，DOM 解析兜底）
    # ------------------------------------------------------------
    async def read_state(self, page: Page) -> GameState:
        """纯 JS 注入读取 window.game（先等待游戏就绪，不用 DOM 解析）。"""
        await self._wait_game_ready(page)

        try:
            data = await page.evaluate("""() => {
                const g = (fn, d = null) => {
                    try {
                        const v = fn();
                        return (v === undefined || (typeof v === 'number' && isNaN(v))) ? d : v;
                    } catch (e) { return d; }
                };
                const out = {};
                out.gold = g(() => Math.floor(game.gp.amount));
                out.slayerCoins = g(() => {
                    const c = game.currencies && game.currencies.registeredObjects
                        ? game.currencies.registeredObjects.get('melvorD:SlayerCoins') : null;
                    return c ? Math.floor(c.amount) : null;
                });
                out.currencies = g(() => {
                    const o = {};
                    for (const [id, c] of game.currencies.registeredObjects) {
                        if (c && c.amount) o[id.replace(/^melvor[A-Za-z0-9]*:/, '')] = Math.floor(c.amount);
                    }
                    return o;
                }, {});
                out.bank = {
                    used: g(() => game.bank.occupiedSlots),
                    max: g(() => game.bank.maximumSlots),
                    itemCount: g(() => game.bank.items.size),
                    lockedCount: g(() => { let n = 0; game.bank.items.forEach((bi) => { if (bi && bi.locked) n++; }); return n; }),
                };
                out.combat = {
                    active: g(() => game.combat ? game.combat.isActive : false),
                    hp: g(() => (game.combat && game.combat.player) ? Math.floor(game.combat.player.hitpoints) : null),
                    maxHp: g(() => {
                        const p = game.combat && game.combat.player;
                        if (!p) return null;
                        // 最大生命在 player.stats 子对象（getter maxHitpoints / 私有 _maxHitpoints）
                        const st = p.stats;
                        if (st) {
                            for (const k of ['maxHitpoints', '_maxHitpoints', 'maxHitPoints', 'maxHP']) {
                                const v = st[k];
                                if (typeof v === 'number' && isFinite(v)) return Math.floor(v);
                            }
                        }
                        for (const k of ['maxHitpoints', 'maxHitPoints', 'hitpointsMax', 'maxHP', 'maxHealth']) {
                            const v = p[k];
                            if (typeof v === 'number' && isFinite(v)) return Math.floor(v);
                        }
                        return null;
                    }),
                    food: g(() => {
                        const f = game.combat && game.combat.player && game.combat.player.food;
                        if (!f || !f.slots) return null;
                        const slot = f.slots[f.selectedSlot] || f.slots[0];
                        return slot && slot.item ? { name: slot.item.name, qty: slot.quantity } : null;
                    }),
                    autoEatTier: g(() => game.autoEatTier),
                    slayerTask: g(() => {
                        const t = game.combat && game.combat.slayerTask;
                        return t && t.monster ? { monster: t.monster.name, killsLeft: t.killsLeft } : null;
                    }),
                    prayerPoints: g(() => game.combat.player ? game.combat.player.prayerPoints : null),
                    activePrayers: g(() => { const a = game.combat.player && game.combat.player.activePrayers; return a ? a.map(p => p.name) : []; }, []),
                    autoEatThreshold: g(() => game.combat.player ? game.combat.player.autoEatHPThreshold : null),
                };
                out.combatLevel = g(() => {
                    const p = game.combat && game.combat.player;
                    // 1) 直接字段候选
                    const candidates = [
                        game.combatLevel,
                        p && p.combatLevel,
                        p && p.stats && p.stats.combatLevel,
                        p && p.stats && p.stats.character && p.stats.character.combatLevel,
                        game.combat && game.combat.combatLevel,
                    ];
                    for (const v of candidates) {
                        if (typeof v === 'number' && isFinite(v) && v > 0) return Math.floor(v);
                    }
                    // 2) 按 Melvor 战斗等级公式计算
                    const lv = p && (p.levels || (p.stats && p.stats.character && p.stats.character.levels));
                    if (lv) {
                        const get = (k) => { const v = lv[k]; return typeof v === 'number' ? v : 0; };
                        const atk = get('Attack'), str = get('Strength'), def = get('Defence'),
                              hp = get('Hitpoints'), rng = get('Ranged'), mag = get('Magic'), pray = get('Prayer');
                        const base = 0.25 * (def + hp + Math.floor(pray / 2));
                        const best = Math.max(atk + str, Math.floor(rng * 1.5), Math.floor(mag * 2));
                        return Math.floor(base + 0.325 * best);
                    }
                    return null;
                });
                out.activeAction = g(() => game.activeAction ? game.activeAction.constructor.name : null);
                out.skills = {};
                g(() => {
                    for (const [id, s] of game.skills.registeredObjects) {
                        out.skills[id.replace(/^melvor[A-Za-z0-9]*:/, '')] = {
                            name: s.name || '',
                            level: s.level || 0,
                            xp: Math.floor(s.xp || 0),
                            mastery: s.masteryLevel !== undefined ? s.masteryLevel : null,
                            masteryPool: s.masteryPoolXP !== undefined ? Math.floor(s.masteryPoolXP) : null,
                        };
                    }
                });
                out.potions = g(() => {
                    const o = [];
                    for (const [k, v] of game.potions.activePotions) {
                        o.push({
                            action: k && k.id ? k.id : String(k),
                            item: v && v.item ? v.item.id : null,
                            charges: v && v.charges !== undefined ? v.charges : null,
                        });
                    }
                    return o;
                }, []);
                out.characterName = g(() => game.characterName);
                out.totalLevel = g(() => { let t = 0; for (const [, s] of game.skills.registeredObjects) t += s.level || 0; return t; });
                out.activeActionTimeLeft = g(() => game.activeAction && game.activeAction.timeLeft !== undefined ? Math.floor(game.activeAction.timeLeft) : null);
                out.lastCloudSave = g(() => game._lastCloudUpdate);
                out.astrology = {
                    level: g(() => game.astrology.level),
                    xp: g(() => Math.floor(game.astrology.xp)),
                    pool: g(() => Math.floor(game.astrology.masteryPoolXP)),
                    studying: g(() => game.astrology.studiedConstellation ? game.astrology.studiedConstellation.name : null),
                };
                out.farming = {
                    level: g(() => game.farming.level),
                    pool: g(() => Math.floor(game.farming.masteryPoolXP)),
                };
                out.township = {
                    level: g(() => game.township.level),
                    health: g(() => game.township.townData ? game.township.townData.healthPercent : null),
                    happiness: g(() => game.township.townData ? game.township.townData.happiness : null),
                    population: g(() => game.township.townData ? game.township.townData.population : null),
                    storage: g(() => game.township.townData ? game.township.townData.buildingStorage : null),
                    resources: g(() => {
                        const o = {};
                        const r = game.township.resources;
                        const reg = (r && r.registeredObjects) ? r.registeredObjects : r;
                        if (reg && typeof reg.forEach === 'function') {
                            reg.forEach((v, k) => {
                                const id = (k && k.id) ? k.id : String(k);
                                const amt = (v && v.amount !== undefined) ? v.amount : v;
                                if (typeof amt === 'number') o[id.replace(/^melvor[A-Za-z0-9]*:/, '')] = Math.floor(amt);
                            });
                        }
                        return o;
                    }, {}),
                };
                out.township.storageUsed = g(() => { let s = 0; for (const k in out.township.resources) { if (k !== 'GP') s += out.township.resources[k]; } return s; });
                out.equipment = g(() => {
                    const res = [];
                    game.equipmentSlots.registeredObjects.forEach((slot, id) => {
                        const it = g(() => game.combat.player.equipment.getItemInSlot(id), null);
                        if (it) res.push({ slot: id.replace(/^melvor[A-Za-z0-9]*:/, ''), item: (it.name || '').replace(/^melvor[A-Za-z0-9]*:/, '') });
                    });
                    return res;
                }, []);
                out.summoning = g(() => {
                    const marks = [];
                    game.summoning.actions.registeredObjects.forEach(a => {
                        const ml = g(() => game.summoning.getMarkLevel(a), 0);
                        if (ml > 0) marks.push({ name: a.name, markLevel: ml });
                    });
                    return { marksDiscovered: marks.length, marks: marks.slice(0, 24) };
                }, { marksDiscovered: 0, marks: [] });
                out.agility = {
                    obstaclesBuilt: g(() => {
                        const v = game.agility.obstacleBuildCount;
                        if (typeof v === 'number') return v;
                        if (v && typeof v.size === 'number') return v.size;
                        if (v && typeof v === 'object') return Object.keys(v).length;
                        return 0;
                    }),
                    activeObstacle: g(() => game.agility.currentlyActiveObstacle ? game.agility.currentlyActiveObstacle.name : null),
                };
                out.pets = g(() => {
                    let unlocked = 0, total = 0;
                    game.pets.registeredObjects.forEach(p => { total++; if (game.petManager.unlocked.has(p)) unlocked++; });
                    return { unlocked, total };
                }, { unlocked: 0, total: 0 });
                out._debug = g(() => {
                    const p = game.combat && game.combat.player;
                    const st = p && p.stats;
                    const ch = st && st.character;
                    const sample = {};
                    if (st) {
                        for (const k of ['maxHitpoints', '_maxHitpoints', 'hitpoints', 'combatLevel', 'levels']) {
                            if (st[k] !== undefined) sample[k] = st[k];
                        }
                    }
                    const chSample = {};
                    if (ch) {
                        for (const k of ['combatLevel', 'levels', 'hitpoints', 'maxHitpoints']) {
                            if (ch[k] !== undefined) chSample[k] = ch[k];
                        }
                    }
                    const levelsSample = {};
                    if (p && p.levels) {
                        for (const k of ['Attack', 'Strength', 'Defence', 'Hitpoints', 'Ranged', 'Magic', 'Prayer', 'combatLevel', 'combat_level']) {
                            if (p.levels[k] !== undefined) levelsSample[k] = p.levels[k];
                        }
                    }
                    return {
                        playerKeys: p ? Object.keys(p).slice(0, 60) : [],
                        combatKeys: game.combat ? Object.keys(game.combat).slice(0, 50) : [],
                        statsKeys: st ? Object.keys(st).slice(0, 60) : [],
                        statsSample: sample,
                        characterKeys: ch ? Object.keys(ch).slice(0, 40) : [],
                        characterSample: chSample,
                        levelsSample: levelsSample,
                        gameCombatLevel: typeof game.combatLevel !== 'undefined' ? game.combatLevel : 'undefined',
                    };
                });
                return out;
            }""")

            log(f'[Adapter] JS 抓取: 金币={data.get("gold")}, 技能数={len(data.get("skills") or {})}, '
                f'银行={data.get("bank")}, HP={data.get("combat", {}).get("hp")}, '
                f'maxHp={data.get("combat", {}).get("maxHp")}, 战斗等级={data.get("combatLevel")}')
            return self._build_state(data)

        except Exception as e:
            log(f'[Adapter] JS 注入异常: {e}')
            return GameState(game_name=self.name)

    async def _wait_game_ready(self, page: Page, timeout_s: int = 90) -> bool:
        """轮询直到 window.game 核心对象加载完成。"""
        deadline = asyncio.get_event_loop().time() + timeout_s
        while asyncio.get_event_loop().time() < deadline:
            try:
                ready = await page.evaluate(
                    "() => typeof game !== 'undefined' && game.gp !== undefined "
                    "&& game.bank !== undefined && game.skills !== undefined"
                )
                if ready:
                    return True
            except Exception:
                pass
            await asyncio.sleep(2)
        log('[Adapter] 等待 window.game 就绪超时')
        return False

    @staticmethod
    def _num(v):
        """把 NaN / None / 非数字清洗为 None，其余转 int（防 Pydantic finite_number 校验失败）。"""
        try:
            if v is None or v == '':
                return None
            f = float(v)
            if f != f:  # NaN
                return None
            return int(f)
        except (TypeError, ValueError):
            return None

    def _build_state(self, data: Dict[str, Any]) -> GameState:
        """把 JS 注入的原始字典转换为统一 GameState。"""
        skills: Dict[str, SkillInfo] = {}
        for key, s in (data.get('skills') or {}).items():
            try:
                skills[key] = SkillInfo(
                    name=s.get('name') or key,
                    level=self._num(s.get('level')) or 0,
                    xp=self._num(s.get('xp')) or 0,
                    mastery_level=self._num(s.get('mastery')),
                    mastery_pool=self._num(s.get('masteryPool')),
                )
            except Exception:
                continue

        resources: Dict[str, ResourceInfo] = {}
        if self._num(data.get('gold')) is not None:
            resources['gold'] = ResourceInfo(name='gold', quantity=self._num(data['gold']))
        if self._num(data.get('slayerCoins')) is not None:
            resources['slayer_coins'] = ResourceInfo(
                name='slayer_coins', quantity=self._num(data['slayerCoins'])
            )

        bank = data.get('bank') or {}
        combat = data.get('combat') or {}

        return GameState(
            game_name=self.name,
            gold=self._num(data.get('gold')),
            slayer_coins=self._num(data.get('slayerCoins')),
            bank_used=self._num(bank.get('used')),
            bank_max=self._num(bank.get('max')),
            skills=skills,
            resources=resources,
            active_action=data.get('activeAction'),
            combat_active=bool(combat.get('active')),
            hp=self._num(combat.get('hp')),
            max_hp=self._num(combat.get('maxHp')),
            combat_level=self._num(data.get('combatLevel')),
            food=combat.get('food'),
            auto_eat_tier=self._num(combat.get('autoEatTier')),
            slayer_task=combat.get('slayerTask'),
            active_potions=data.get('potions') or [],
            township=data.get('township'),
            farming=data.get('farming'),
            astrology=data.get('astrology'),
            bank_item_count=self._num(bank.get('itemCount')),
            bank_locked_count=self._num(bank.get('lockedCount')),
            raw_probe=data,
        )

    async def _read_state_from_dom(self, page: Page) -> GameState:
        """通过 DOM 元素解析状态（较慢但兼容性好）。"""
        resources: Dict[str, ResourceInfo] = {}
        hp: Optional[int] = None
        max_hp: Optional[int] = None

        dom_map = self.map_dom('')

        # 资源数值
        for key in ('gold', 'slayer_coins'):
            for sel in (dom_map.selectors.get(key, '') or '').split(', '):
                sel = sel.strip()
                if not sel:
                    continue
                try:
                    el = await page.query_selector(sel)
                    if el:
                        text = await el.text_content()
                        cleaned = re.sub(r'[^\d.]', '', (text or '').strip())
                        if cleaned:
                            resources[key] = ResourceInfo(name=key, quantity=float(cleaned))
                            break
                except Exception:
                    continue

        # HP
        for sel in (dom_map.selectors.get('hp_text', '') or '').split(', '):
            sel = sel.strip()
            if not sel:
                continue
            try:
                el = await page.query_selector(sel)
                if el:
                    text = (await el.text_content()) or ''
                    m = re.search(r'(\d+)\s*/\s*(\d+)', text)
                    if m:
                        hp, max_hp = int(m.group(1)), int(m.group(2))
                        break
            except Exception:
                continue

        combat_active = False
        try:
            for sel in ('.combat-active', '.in-combat', "button:has-text('战斗')"):
                if await page.query_selector(sel):
                    combat_active = True
                    break
        except Exception:
            pass

        return GameState(
            game_name=self.name,
            resources=resources,
            hp=hp,
            max_hp=max_hp,
            combat_active=combat_active,
        )

    # ------------------------------------------------------------
    # 3. 执行动作
    # ------------------------------------------------------------
    async def execute_action(self, page: Page, action: Action) -> bool:
        try:
            action_type = action.action_type
            target = action.target or ''
            params = action.params or {}

            if action_type == ActionType.CLICK.value:
                if target.startswith('#') or target.startswith('.') or target.startswith('['):
                    loc = page.locator(target)
                    if await loc.count() > 0:
                        await loc.first.click(timeout=8000)
                        return True
                else:
                    loc = page.get_by_text(target, exact=False)
                    if await loc.count() > 0:
                        await loc.first.click(timeout=8000)
                        return True
                return False

            elif action_type == ActionType.NAVIGATE.value:
                # 优先尝试侧边栏导航（双语），失败则按 URL 跳转
                if await self.browser.nav_to([target]):
                    return True
                if target.startswith('http'):
                    await page.goto(target, timeout=15000)
                    await page.wait_for_load_state('domcontentloaded')
                    return True
                return False

            elif action_type == ActionType.SELECT.value:
                loc = page.locator(target)
                value = params.get('value', '')
                await loc.select_option(value)
                return True

            elif action_type == ActionType.INPUT.value:
                loc = page.locator(target)
                await loc.fill(params.get('value', ''))
                return True

            elif action_type == ActionType.WAIT.value:
                await asyncio.sleep(float(params.get('duration', 1.0)))
                return True

            elif action_type == ActionType.SCROLL.value:
                y = params.get('y', target or 0)
                await page.evaluate(f'window.scrollTo(0, {y})')
                return True

            log(f'[Adapter] 未知动作类型: {action_type}')
            return False

        except Exception as e:
            log(f'[Adapter] 执行动作失败: {e}')
            return False

    # ------------------------------------------------------------
    # 4. 事件监听
    # ------------------------------------------------------------
    async def watch_events(self, page: Page) -> List[GameEvent]:
        events: List[GameEvent] = []

        # 死亡弹窗
        death_selectors = [
            '.death-modal', '.death-screen',
            "div:has-text('You have died')",
            "button:has-text('Respawn')",
        ]
        for sel in death_selectors:
            try:
                if await page.locator(sel).count() > 0:
                    events.append(GameEvent(
                        event_type=EventType.DEATH.value,
                        severity='critical',
                        details={'selector': sel},
                    ))
                    break
            except Exception:
                pass

        # 低血量警告
        try:
            state = await self.read_state(page)
            if state.hp and state.max_hp and state.max_hp > 0:
                ratio = state.hp / state.max_hp
                if ratio < 0.3:
                    events.append(GameEvent(
                        event_type=EventType.LOW_HP.value,
                        severity='warning' if ratio > 0.2 else 'critical',
                        details={'hp': state.hp, 'max_hp': state.max_hp, 'ratio': ratio},
                    ))
        except Exception:
            pass

        # 通用弹窗
        try:
            if await page.locator('.modal:visible, .popup:visible').count() > 0:
                events.append(GameEvent(
                    event_type=EventType.POPUP.value,
                    severity='info',
                    details={},
                ))
        except Exception:
            pass

        return events

    # ------------------------------------------------------------
    # 5. 游戏专用诊断（引擎会调用）
    # ------------------------------------------------------------
    async def diagnose_custom(self, state: GameState) -> Dict[str, Any]:
        warnings: List[str] = []
        recommendations: List[str] = []

        # 食物存量（Melvor 战斗/钓鱼关键资源）
        food = next(
            (r for r in state.resources.values() if r.name.lower() in ('food', '食物', 'shrimp', 'shrimps')),
            None,
        )
        if food is not None and food.quantity < 10:
            warnings.append('食物存量低于 10，可能无法持续战斗')
            recommendations.append('emergency_fish')

        # 空转检测：无活跃动作时建议推进技能
        if state.active_action is None and not state.combat_active:
            recommendations.append('突破当前技能瓶颈')

        return {'warnings': warnings, 'recommendations': recommendations}

    # ------------------------------------------------------------
    # 6. 守卫（药剂修正 + 动作恢复）
    # ------------------------------------------------------------
    async def guards(self, page: Page) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        try:
            act = await page.evaluate("""() => {
                const o = { action: game.activeAction ? game.activeAction.constructor.name : null, potions: [] };
                for (const [k, v] of game.potions.activePotions)
                    o.potions.push(k.id + '=' + (v.item ? v.item.id : '?') + ':' + v.charges);
                return o;
            }""")
        except Exception as e:
            return {'ok': False, 'error': f'guards 读取失败: {e}'}

        out['before'] = act
        action = act.get('action')
        astro_potion_ok = any(
            str(p).startswith('melvorD:Astrology=melvorF:Secret_Stardust_Potion_III')
            for p in act.get('potions', [])
        )

        if action not in (None, 'Astrology'):
            out['note'] = f'当前动作={action}，非星象，不干预'
            return out

        # 药剂修正
        if not astro_potion_ok:
            log('[Melvor守卫] 星象III级药剂缺失，执行修正')
            await self.browser.nav_to(['Astrology', '星象学'])
            await page.wait_for_timeout(3000)
            btn = page.locator('#page-header-potions-dropdown')
            if await btn.count():
                await btn.first.click()
                await page.wait_for_timeout(2500)
            out['potion_click'] = await page.evaluate("""(name) => {
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
            }""", '秘密星尘药水 III')
            await page.wait_for_timeout(2000)
            await page.keyboard.press('Escape')
            await page.wait_for_timeout(1000)
            after = await page.evaluate("""() => {
                const o = { action: game.activeAction ? game.activeAction.constructor.name : null, potions: [] };
                for (const [k, v] of game.potions.activePotions)
                    o.potions.push(k.id + '=' + (v.item ? v.item.id : '?') + ':' + v.charges);
                return o;
            }""")
            out['potion_after'] = after.get('potions')
            out['potion_ok'] = any(
                str(p).startswith('melvorD:Astrology=melvorF:Secret_Stardust_Potion_III')
                for p in after.get('potions', [])
            )
        else:
            out['potion_ok'] = True

        # 空转恢复
        if action is None:
            log('[Melvor守卫] 动作空转，恢复研究海密尔')
            await self.browser.nav_to(['Astrology', '星象学'])
            await page.wait_for_timeout(3000)
            cur = await page.evaluate("() => game.activeAction ? game.activeAction.constructor.name : null")
            if cur != 'Astrology':
                out['study_click'] = await page.evaluate("""(name) => {
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
                }""", '海密尔')
                await page.wait_for_timeout(2500)
            out['study_after'] = await page.evaluate(
                "() => game.activeAction ? game.activeAction.constructor.name : null"
            )
        return out


# ------------------------------------------------------------
# 7. 云账号登录与角色管理
# ------------------------------------------------------------
    async def set_credentials(self, account: str = None, password: str = None):
        """动态设置浏览器登录凭证（用于仪表盘内登录 Melvor 云账号）。"""
        if account is not None:
            self.browser.account = account
        if password is not None:
            self.browser.password = password

    async def login_cloud(self, account: str = None, password: str = None):
        """启动浏览器并登录云账号，停在角色选择页（不加载存档）。"""
        await self.set_credentials(account, password)
        if self.browser.page is None:
            await self.browser.launch()
        await self.browser.navigate()
        # 登录 + 语言切换，停在角色选择页（不自动加载存档）
        await self.browser._boot_to_char_select()
        return self.browser.page

    async def list_characters(self, page: Page) -> List[Dict[str, Any]]:
        """枚举角色选择页的存档槽（角色）。等待存档槽时间戳加载，必要时显示云存档。"""
        # 1. 等待存档槽带时间戳出现（云存档拉取可能较慢）；本地无存档时点「显示云存档」
        deadline = asyncio.get_event_loop().time() + 90
        while asyncio.get_event_loop().time() < deadline:
            try:
                body = await page.inner_text('body')
                if re.search(r'(最后保存|Last Save)[^\n]{0,30}\d{4}/\d{1,2}/\d{1,2}', body) or \
                   re.search(r'(最后保存|Last Save)[^\n]{0,30}\d{1,2}/\d{1,2}/\d{4}', body):
                    break
                # 本地无存档时，云存档需要手动点开
                show = page.locator(
                    "button:has-text('显示云存档'):visible, button:has-text('Show Cloud Saves'):visible"
                )
                if await show.count():
                    await show.first.click(timeout=8000)
                    await page.wait_for_timeout(3000)
            except Exception:
                pass
            await asyncio.sleep(2)

        # 2. 从 body 文本提取存档槽（「最后保存：时间戳」格式；标签与日期可能在不同元素，正则最稳）
        try:
            body = await page.inner_text('body')
            labels = re.findall(r'最后保存[：:]\s*([^\n]+)', body)
            if not labels:
                labels = re.findall(r'Last Save[d]?[：:]\s*([^\n]+)', body, re.I)
            slots = [{'index': i, 'label': f'最后保存： {t.strip()}'} for i, t in enumerate(labels)]
            log(f'[Adapter] 枚举到 {len(slots)} 个角色: {[s["label"] for s in slots]}')
            return slots
        except Exception as e:
            log(f'[Adapter] 提取存档槽失败: {e}')
            return []

    async def select_character(self, page: Page, index: int) -> bool:
        """选择第 index 个存档槽并等待游戏就绪（Playwright 文本定位 + JS 点击双兜底）。"""
        if page is None:
            log('[Adapter] select_character: page 为 None（未登录），跳过')
            return False
        deadline = asyncio.get_event_loop().time() + 90
        clicked = False
        while asyncio.get_event_loop().time() < deadline and not clicked:
            try:
                loc = page.locator('text=最后保存:visible, text=Last Save:visible')
                if await loc.count() > index:
                    await loc.nth(index).click(timeout=10000)
                    clicked = True
                else:
                    # 新 profile 无本地存档时，云存档未显示，先点「显示云存档」
                    show = page.locator(
                        "button:has-text('显示云存档'):visible, button:has-text('Show Cloud Saves'):visible"
                    )
                    if await show.count():
                        await show.first.click(timeout=8000)
                        await page.wait_for_timeout(3000)
                        continue
                    # JS 兜底：找「最后保存」最小元素，向上爬到可点击祖先再点
                    r = await page.evaluate("""(idx) => {
                        const hits = [...document.querySelectorAll('span,div')].filter(e =>
                            e.offsetParent !== null && /最后保存|Last Save/.test(e.innerText || '')
                            && e.children.length <= 2);
                        hits.sort((a, b) => (a.innerText || '').length - (b.innerText || '').length);
                        if (hits.length <= idx) return 'nofound:' + hits.length;
                        let el = hits[idx];
                        for (let i = 0; i < 12 && el; i++) {
                            const cs = getComputedStyle(el);
                            if (el.tagName === 'BUTTON' || el.tagName === 'A'
                                || el.getAttribute('role') === 'button' || cs.cursor === 'pointer') {
                                el.click();
                                return 'clicked:' + el.tagName + ':' + (el.className || '').toString().slice(0, 50);
                            }
                            el = el.parentElement;
                        }
                        hits[idx].click();
                        return 'clicked-leaf';
                    }""", index)
                    log(f'[Adapter] JS 点击存档槽: {r}')
                    if str(r).startswith('clicked'):
                        clicked = True
            except Exception as e:
                log(f'[Adapter] 点击存档槽异常: {e}')
            if not clicked:
                await asyncio.sleep(2)

        if not clicked:
            try:
                await page.screenshot(path=os.path.join('state', 'char_select_debug.png'))
                body = await page.inner_text('body')
                log(f'[Adapter] 选角色失败，body 前 400 字: {body[:400]}')
            except Exception:
                pass
            return False

        await self.browser._confirm_if_modal()
        await self.browser._wait_game_ready()
        log(f'[Adapter] 已选择角色 #{index} 并加载存档')
        return True


    # ------------------------------------------------------------
    # 命名维护操作（供「用户脚本」模式调用）
    # ------------------------------------------------------------
    async def _op_resume_astrology(self, page: Page) -> Dict[str, Any]:
        """恢复星象研究海密尔 + 激活星尘药水 III。"""
        out: Dict[str, Any] = {}
        await self.browser.nav_to(['Astrology', '星象学'])
        await page.wait_for_timeout(3000)
        btn = page.locator('#page-header-potions-dropdown')
        if await btn.count():
            await btn.first.click()
            await page.wait_for_timeout(2000)
        out['potion'] = await page.evaluate(_JS_POTION_ACTIVATE, '秘密星尘药水 III')
        await page.wait_for_timeout(2000)
        await page.keyboard.press('Escape')
        await page.wait_for_timeout(800)
        cur = await page.evaluate("() => game.activeAction ? game.activeAction.constructor.name : null")
        if cur == 'Astrology':
            out['study'] = 'already'
        else:
            out['study'] = await page.evaluate(_JS_STUDY_CLICK, '海密尔')
            await page.wait_for_timeout(2000)
        out['action'] = await page.evaluate("() => game.activeAction ? game.activeAction.constructor.name : null")
        log(f'[操作] 恢复星象: 药水={out.get("potion")} 研究={out.get("study")} 动作={out.get("action")}')
        return out

    async def _read_township_storage(self, page: Page) -> Dict[str, Any]:
        """读取城镇仓储容量与已用（已用排除 GP 城镇金币）。"""
        try:
            return await page.evaluate(r"""() => {
                const td = game.township.townData;
                let used = 0;
                const r = game.township.resources;
                const reg = (r && r.registeredObjects) ? r.registeredObjects : r;
                if (reg && typeof reg.forEach === 'function') {
                    reg.forEach((v, k) => {
                        const id = (k && k.id) ? k.id : String(k);
                        if (/GP$/i.test(id)) return;  // 城镇金币不计入仓储
                        used += (v && v.amount !== undefined) ? v.amount : (typeof v === 'number' ? v : 0);
                    });
                }
                return { capacity: td ? Math.floor(td.buildingStorage) : 0, used: Math.floor(used) };
            }""")
        except Exception:
            return {'capacity': 0, 'used': 0}

    async def _op_township_repair(self, page: Page) -> Dict[str, Any]:
        """城镇维护：维修全部 + 健康恢复至 100% + 建仓储基地/屋邨。"""
        out: Dict[str, Any] = {}
        await self.browser.nav_to(['Township', '城镇'])
        await page.wait_for_timeout(3500)
        t = await click_text_btn(page, ['维修全部', 'Repair All'])
        out['repair'] = t
        await page.wait_for_timeout(2000)
        await safe_confirm(page)
        await page.wait_for_timeout(2000)

        def parse_health(text):
            m = re.search(r'健康[\s:：]*\n?\s*([\d.]+)\s*%', text)
            return float(m.group(1)) if m else None

        # 健康恢复至 100%（优先 +10 档）
        out['health_before'] = parse_health(await page.inner_text('body'))
        clicks = []
        for _ in range(30):
            h = parse_health(await page.inner_text('body'))
            if h is not None and h >= 100:
                break
            r = await page.evaluate(_JS_HEAL_CLICK)
            if str(r).startswith('clicked'):
                clicks.append(r)
                await page.wait_for_timeout(1800)
                continue
            break
        out['heal_clicks'] = clicks
        out['health_after'] = parse_health(await page.inner_text('body'))

        # 建筑：屋邨
        out['build'] = {}
        for nm, max_clicks in [('屋邨', 6)]:
            built = 0
            for _ in range(max_clicks):
                r = await page.evaluate(_JS_CARD_CLICK, nm)
                if not str(r).startswith('clicked'):
                    break
                built += 1
                await page.wait_for_timeout(1300)
                await safe_confirm(page)
            out['build'][nm] = built

        # 仓储扩建：满仓(≥95%)则持续建「仓储基地→大型仓储基地」，直到不满或上限
        out['storage_before'] = await self._read_township_storage(page)
        for nm in ['仓储基地', '大型仓储基地']:
            built = 0
            for _ in range(12):
                st = await self._read_township_storage(page)
                if st['capacity'] and st['used'] / st['capacity'] < 0.95:
                    break
                r = await page.evaluate(_JS_CARD_CLICK, nm)
                if not str(r).startswith('clicked'):
                    break
                built += 1
                await page.wait_for_timeout(1300)
                await safe_confirm(page)
            out['build'][nm] = built
        out['storage_after'] = await self._read_township_storage(page)
        log(f'[操作] 城镇维护: 维修={t} 健康 {out["health_before"]}->{out["health_after"]} '
            f'建筑={out["build"]} 仓储 {out["storage_before"]}->{out["storage_after"]}')
        return out

    async def _op_farming_plant_harvest(self, page: Page) -> Dict[str, Any]:
        """农务：三类地收获 + 逐块补种。"""
        out: Dict[str, Any] = {}
        await self.browser.nav_to(['Farming', '农务'])
        await page.wait_for_timeout(3500)
        for tab, seed in [('农作物', '胡萝卜种子'), ('草药', '巴伦托尔草种子'), ('树木', '苹果树种子')]:
            r: Dict[str, Any] = {'planted': 0}
            r['tab'] = await page.evaluate(_JS_TAB_CLICK, tab)
            await page.wait_for_timeout(2200)
            r['harvest'] = await click_text_btn(page, ['收获所有农田', 'Harvest All'])
            await page.wait_for_timeout(2000)
            await safe_confirm(page)
            await page.wait_for_timeout(2000)
            for _ in range(20):
                n = await page.evaluate(_JS_PER_PLOT_BTN)
                if not n:
                    break
                await page.wait_for_timeout(2000)
                sel = await page.evaluate(_JS_SEED_SELECT, seed)
                if not str(sel).startswith('clicked'):
                    await page.keyboard.press('Escape')
                    await page.wait_for_timeout(800)
                    continue
                await page.wait_for_timeout(1600)
                pc = await page.evaluate(_JS_PLANT_CONFIRM)
                await page.wait_for_timeout(1600)
                await page.keyboard.press('Escape')
                await page.wait_for_timeout(800)
                if str(pc).startswith('clicked'):
                    r['planted'] += 1
            out[tab] = r
        log(f'[操作] 农务种植: {out}')
        return out

    async def _op_bank_buy_slots(self, page: Page) -> Dict[str, Any]:
        """买仓库格（空闲<15 触发，x1 倍数安全）。"""
        await self.browser.nav_to(['Shop', '商店'])
        await page.wait_for_timeout(3500)
        st = await page.evaluate(
            "() => ({ slots: game.bank.maximumSlots, free: game.bank.maximumSlots - game.bank.occupiedSlots, gp: game.gp.amount })"
        )
        if st.get('free', 0) >= 15:
            return {'note': f"空闲 {st['free']} ≥ 15，无需购买"}
        out: Dict[str, Any] = {'before': st}
        out['buy'] = await page.evaluate(_JS_BANKSLOT_BUY)
        await page.wait_for_timeout(1500)
        out['confirm'] = await page.evaluate(_JS_BANKSLOT_CONFIRM)
        await page.wait_for_timeout(2000)
        log(f'[操作] 买仓库格: {out}')
        return out

    async def _op_brew_stardust(self, page: Page) -> Dict[str, Any]:
        """切换草药学配方到秘密星尘药水并开工。"""
        await self.browser.nav_to(['Herblore', '草药学'])
        await page.wait_for_timeout(3500)
        r = await page.evaluate(_JS_TAB_CLICK, '秘密星尘药水')
        await page.wait_for_timeout(2500)
        c = await click_text_btn(page, ['创造', 'Create'])
        await page.wait_for_timeout(2500)
        log(f'[操作] 制作星尘药水: 配方={r} 创造={c}')
        return {'click': r, 'create': c}

    async def execute_operation(self, page: Page, name: str) -> bool:
        """执行命名维护操作（供「用户脚本」模式调用）。"""
        name = (name or '').strip().lower()
        try:
            if name in ('resume_astrology', 'astro', 'study', '研究星象'):
                await self._op_resume_astrology(page)
            elif name in ('force_save', 'save', '保存'):
                await self.browser.force_save()
            elif name in ('township_repair', 'township', '城镇维护'):
                await self._op_township_repair(page)
            elif name in ('farming_plant_harvest', 'farming', '农务'):
                await self._op_farming_plant_harvest(page)
            elif name in ('bank_buy_slots', 'bankbuy', '买仓库格'):
                await self._op_bank_buy_slots(page)
            elif name in ('brew_stardust', 'brew', '制药'):
                await self._op_brew_stardust(page)
            elif name in ('combat_probe', 'combat', '战斗'):
                await self.browser.nav_to(['Combat', '战斗'])
            else:
                log(f'[Adapter] 未知操作: {name}')
                return False
            return True
        except Exception as e:
            log(f'[Adapter] 操作 {name} 失败: {e}')
            return False


# ------------------------------------------------------------
# 独立调试入口
# ------------------------------------------------------------
if __name__ == '__main__':
    async def test_adapter():
        adapter = MelvorIdleAdapter()
        page = await adapter.browser.launch()
        await adapter.browser.navigate()
        # Melvor 需要登录，此处留给用户手动登录
        print('请手动登录 Melvor Idle... 15 秒后自动读取状态')
        await asyncio.sleep(15)
        state = await adapter.read_state(page)
        print('读取到的状态:', state.model_dump())
        await adapter.browser.close()

    asyncio.run(test_adapter())
