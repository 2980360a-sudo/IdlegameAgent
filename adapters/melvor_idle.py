"""
Melvor Idle 适配器 - v0.6.0
游戏网址: https://melvoridle.com
实现方式: 优先注入 JS 读取 window.game 对象，失败时回退到 DOM 解析
"""
import re
import os
import asyncio
from typing import List, Dict, Any, Optional

from playwright.async_api import Page

from core.adapter import GameAdapter
from core.browser import BrowserManager, log
from core.state import (
    GameState, GameEvent, Action, DOMMap,
    ActionType, EventType, SkillInfo, ResourceInfo, EquipmentInfo,
)


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
        try:
            await page.wait_for_selector('#app, body', timeout=10000)
        except Exception:
            pass

        # ---- 方案 A：JS 注入读取 window.game（最优） ----
        try:
            data = await page.evaluate("""() => {
                const g = (fn, d = null) => {
                    try { const v = fn(); return v === undefined ? d : v; } catch (e) { return d; }
                };
                if (typeof game === 'undefined') return { error: 'GAME_NOT_FOUND' };

                const out = {};
                out.gold = g(() => Math.floor(game.gp.amount));
                out.slayerCoins = g(() => {
                    const c = game.currencies && game.currencies.registeredObjects
                        ? game.currencies.registeredObjects.get('melvorD:SlayerCoins') : null;
                    return c ? Math.floor(c.amount) : null;
                });
                out.bank = {
                    used: g(() => game.bank.occupiedSlots),
                    max: g(() => game.bank.maximumSlots),
                    itemCount: g(() => game.bank.items.size),
                    lockedCount: g(() => { let n = 0; game.bank.items.forEach((bi) => { if (bi && bi.locked) n++; }); return n; }),
                };
                out.combat = {
                    active: g(() => game.combat ? game.combat.isActive : false),
                    hp: g(() => (game.combat && game.combat.player) ? Math.floor(game.combat.player.hitpoints) : null),
                    maxHp: g(() => (game.combat && game.combat.player) ? Math.floor(game.combat.player.maxHitpoints) : null),
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
                };
                out.combatLevel = g(() => game.combatLevel);
                out.activeAction = g(() => game.activeAction ? game.activeAction.constructor.name : null);
                out.skills = {};
                g(() => {
                    for (const [id, s] of game.skills.registeredObjects) {
                        out.skills[id] = {
                            level: s.level,
                            xp: Math.floor(s.xp),
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
                    health: g(() => game.township.health),
                    happiness: g(() => game.township.happiness),
                    population: g(() => game.township.citizens),
                    storage: g(() => game.township.townData ? game.township.townData.buildingStorage : null),
                };
                return out;
            }""")

            if data and 'error' not in data:
                return self._build_state(data)
            log('[Adapter] window.game 不可用，降级到 DOM 解析')

        except Exception as e:
            log(f'[Adapter] JS 注入失败: {e}，降级到 DOM 解析')

        # ---- 方案 B：DOM 解析（兜底） ----
        return await self._read_state_from_dom(page)

    def _build_state(self, data: Dict[str, Any]) -> GameState:
        """把 JS 注入的原始字典转换为统一 GameState。"""
        skills: Dict[str, SkillInfo] = {}
        for raw_id, s in (data.get('skills') or {}).items():
            name = re.sub(r'^melvor\w*:', '', str(raw_id))
            try:
                skills[name] = SkillInfo(
                    name=name,
                    level=int(s.get('level', 0)),
                    xp=int(s.get('xp', 0)),
                    mastery_level=s.get('mastery'),
                    mastery_pool=s.get('masteryPool'),
                )
            except Exception:
                continue

        resources: Dict[str, ResourceInfo] = {}
        if data.get('gold') is not None:
            resources['gold'] = ResourceInfo(name='gold', quantity=int(data['gold']))
        if data.get('slayerCoins') is not None:
            resources['slayer_coins'] = ResourceInfo(
                name='slayer_coins', quantity=int(data['slayerCoins'])
            )

        bank = data.get('bank') or {}
        combat = data.get('combat') or {}

        return GameState(
            game_name=self.name,
            gold=data.get('gold'),
            slayer_coins=data.get('slayerCoins'),
            bank_used=bank.get('used'),
            bank_max=bank.get('max'),
            skills=skills,
            resources=resources,
            active_action=data.get('activeAction'),
            combat_active=bool(combat.get('active')),
            hp=combat.get('hp'),
            max_hp=combat.get('maxHp'),
            combat_level=data.get('combatLevel'),
            food=combat.get('food'),
            auto_eat_tier=combat.get('autoEatTier'),
            slayer_task=combat.get('slayerTask'),
            active_potions=data.get('potions') or [],
            township=data.get('township'),
            farming=data.get('farming'),
            astrology=data.get('astrology'),
            bank_item_count=bank.get('itemCount'),
            bank_locked_count=bank.get('lockedCount'),
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
        """枚举角色选择页的存档槽（角色）。"""
        slots: List[Dict[str, Any]] = []
        try:
            slots = await page.evaluate("""() => {
                const out = [];
                const seen = new Set();
                const els = [...document.querySelectorAll('*')].filter(e =>
                    e.children.length === 0 && /最后保存|Last Save/i.test(e.innerText || ''));
                els.forEach((el) => {
                    const txt = (el.innerText || '').trim();
                    if (seen.has(txt)) return;
                    seen.add(txt);
                    out.push({ label: txt });
                });
                return out;
            }""")
            for i, s in enumerate(slots):
                s['index'] = i
            return slots
        except Exception as e:
            log(f'[Adapter] JS 枚举角色失败，回退 DOM: {e}')

        # DOM 兜底
        loc = page.locator('text=最后保存:visible, text=Last Save:visible')
        count = await loc.count()
        for i in range(count):
            try:
                text = await loc.nth(i).inner_text()
                slots.append({'index': i, 'label': text.strip()})
            except Exception:
                continue
        return slots

    async def select_character(self, page: Page, index: int) -> bool:
        """选择第 index 个存档槽并等待游戏就绪。"""
        loc = page.locator('text=最后保存:visible, text=Last Save:visible')
        try:
            if await loc.count() <= index:
                return False
            await loc.nth(index).click(timeout=15000)
            await page.wait_for_timeout(2500)
            await self.browser._confirm_if_modal()
            await self.browser._wait_game_ready()
            log(f'[Adapter] 已选择角色 #{index} 并加载存档')
            return True
        except Exception as e:
            log(f'[Adapter] 选择角色失败: {e}')
            return False


    async def execute_operation(self, page: Page, name: str) -> bool:
        """执行命名维护操作（供「用户脚本」模式调用）。"""
        name = (name or '').strip().lower()
        if name in ('resume_astrology', 'astro', 'study', '研究星象'):
            # 复用守卫逻辑：激活星尘药水 III + 恢复研究海密尔
            try:
                result = await self.guards(page)
                return bool(result and not result.get('error'))
            except Exception as e:
                log(f'[Adapter] 恢复星象失败: {e}')
                return False
        if name in ('force_save', 'save', '保存'):
            return await self.browser.force_save()
        if name in ('township_repair', 'township', '城镇维护'):
            await self.browser.nav_to(['Township', '城镇'])
            return True
        if name in ('farming_plant_harvest', 'farming', '农务'):
            await self.browser.nav_to(['Farming', '农务'])
            return True
        if name in ('combat_probe', 'combat', '战斗'):
            await self.browser.nav_to(['Combat', '战斗'])
            return True
        log(f'[Adapter] 未知操作: {name}')
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
