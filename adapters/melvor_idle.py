"""
Melvor Idle 适配器 - v0.2.1
游戏网址: https://melvoridle.com
实现方式: 优先注入 JS 读取 window.game 对象，失败时回退到 DOM 解析
"""
import re
import asyncio
from typing import List, Dict, Any, Optional
from playwright.async_api import Page, Locator

from core.adapter import GameAdapter
from core.state import GameState, GameEvent, Action, DOMMap, EventType, ActionType


class MelvorIdleAdapter(GameAdapter):
    """Melvor Idle 专用适配器"""

    # ============================================================
    # 1. DOM 映射（用于 UI 解析的兜底方案）
    # ============================================================
    async def map_dom(self, raw_html: str) -> DOMMap:
        """
        将游戏原始 DOM 映射为统一选择器（暂未深度使用，保留接口）
        """
        return DOMMap(
            resources={
                "gold": "#resource-gold .amount",
                "wood": "#resource-wood .amount",
                "stone": "#resource-stone .amount",
            },
            combat={
                "hp_bar": "#combat-hp-bar",
                "hp_text": "#combat-hp-text",
            }
        )

    # ============================================================
    # 2. 核心：读取游戏状态（read_state）
    # ============================================================
    async def read_state(self, page: Page) -> GameState:
        """
        从 Melvor Idle 页面提取完整状态
        策略：优先使用 window.game API (最精确)，失败时解析 DOM
        """
        # 等待页面核心元素加载完成（至少等待 3 秒，确保 React 渲染）
        try:
            await page.wait_for_selector("#app", timeout=10000)
        except:
            # 如果找不到 #app，可能页面未完全加载，尝试等待 body
            await page.wait_for_selector("body", timeout=5000)

        # ---- 方案 A：JS 注入读取 window.game（最优） ----
        try:
            data = await page.evaluate("""() => {
                // 检查游戏全局对象是否存在
                if (typeof window.game === 'undefined' && typeof window.__GAME__ === 'undefined') {
                    return { error: 'GAME_NOT_FOUND' };
                }
                const game = window.game || window.__GAME__ || {};

                // 1. 提取资源（资源名可能是动态的，这里取常见的前几个）
                const resources = {};
                if (game.resources) {
                    for (const key of ['gold', 'wood', 'stone', 'iron', 'steel', 'fish', 'food']) {
                        if (game.resources[key] !== undefined) {
                            resources[key] = game.resources[key];
                        }
                    }
                }

                // 2. 提取战斗状态
                let combat = { hp: 0, max_hp: 0, in_combat: false };
                if (game.combat) {
                    combat.hp = game.combat.hp || 0;
                    combat.max_hp = game.combat.max_hp || 0;
                    combat.in_combat = game.combat.in_combat || false;
                }

                // 3. 提取技能等级（可选）
                const skills = {};
                if (game.skills) {
                    for (const key of ['attack', 'strength', 'defence', 'fishing', 'woodcutting', 'mining']) {
                        if (game.skills[key] !== undefined) {
                            skills[key] = game.skills[key];
                        }
                    }
                }

                return { resources, combat, skills };
            }""")

            if data and "error" not in data:
                # 成功从 window.game 读取
                return GameState(
                    resources=data.get("resources", {}),
                    combat=data.get("combat", {"hp": 0, "max_hp": 0, "in_combat": False}),
                    skills=data.get("skills", {}),
                    timestamp=await self._get_timestamp(page)
                )

            print("[Adapter] window.game 不可用，降级到 DOM 解析")

        except Exception as e:
            print(f"[Adapter] JS 注入失败: {e}，降级到 DOM 解析")

        # ---- 方案 B：DOM 解析（兜底方案） ----
        return await self._read_state_from_dom(page)

    # ============================================================
    # 3. DOM 解析兜底实现
    # ============================================================
    async def _read_state_from_dom(self, page: Page) -> GameState:
        """通过 DOM 元素解析状态（较慢但兼容性好）"""
        resources = {}
        combat = {"hp": 0, "max_hp": 0, "in_combat": False}

        # 3.1 尝试抓取资源数值（根据常见的 Melvor 类名）
        resource_selectors = {
            "gold": ["#resource-gold .amount", ".resource-gold .amount", "[data-resource='gold']"],
            "wood": ["#resource-wood .amount", ".resource-wood .amount", "[data-resource='wood']"],
            "stone": ["#resource-stone .amount", ".resource-stone .amount", "[data-resource='stone']"],
        }

        for key, selectors in resource_selectors.items():
            for sel in selectors:
                try:
                    el = await page.query_selector(sel)
                    if el:
                        text = await el.text_content()
                        if text:
                            # 移除千位分隔符等，只取数字
                            cleaned = re.sub(r"[^\d.]", "", text.strip())
                            if cleaned:
                                resources[key] = float(cleaned)
                                break
                except:
                    continue

        # 3.2 抓取 HP（战斗状态）
        hp_selectors = ["#combat-hp-text", ".hp-text", ".health-text"]
        for sel in hp_selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    text = await el.text_content()
                    if text:
                        # 匹配 "850 / 1000" 格式
                        match = re.search(r"(\d+)\s*/\s*(\d+)", text)
                        if match:
                            combat["hp"] = float(match.group(1))
                            combat["max_hp"] = float(match.group(2))
                            break
                        # 也可能是单独的数值
                        nums = re.findall(r"\d+", text)
                        if len(nums) >= 2:
                            combat["hp"] = float(nums[0])
                            combat["max_hp"] = float(nums[1])
                            break
            except:
                continue

        # 3.3 检测是否在战斗中（通过查找战斗按钮或状态文字）
        try:
            combat_indicators = [".combat-active", ".in-combat", "button:has-text('战斗')"]
            for sel in combat_indicators:
                if await page.query_selector(sel):
                    combat["in_combat"] = True
                    break
        except:
            pass

        return GameState(
            resources=resources,
            combat=combat,
            skills={},
            timestamp=await self._get_timestamp(page)
        )

    # ============================================================
    # 4. 执行动作（execute_action）
    # ============================================================
    async def execute_action(self, page: Page, action: Action) -> bool:
        """
        执行原子操作：click / navigate / select / wait / scroll
        """
        try:
            if action.type == ActionType.CLICK:
                # 支持 CSS 选择器或文本定位
                target = action.target
                if target.startswith("#") or target.startswith(".") or target.startswith("["):
                    # CSS 选择器
                    locator = page.locator(target)
                    if await locator.count() > 0:
                        await locator.first.click()
                        return True
                else:
                    # 按文本查找（模糊匹配）
                    locator = page.get_by_text(target, exact=False)
                    if await locator.count() > 0:
                        await locator.first.click()
                        return True
                return False

            elif action.type == ActionType.NAVIGATE:
                await page.goto(action.target, timeout=15000)
                await page.wait_for_load_state("networkidle")
                return True

            elif action.type == ActionType.SELECT:
                # 下拉选择
                locator = page.locator(action.target)
                await locator.select_option(action.value or "")
                return True

            elif action.type == ActionType.WAIT:
                await asyncio.sleep(action.duration or 1.0)
                return True

            elif action.type == ActionType.SCROLL:
                await page.evaluate(f"window.scrollTo(0, {action.target})")
                return True

            else:
                print(f"[Adapter] 未知动作类型: {action.type}")
                return False

        except Exception as e:
            print(f"[Adapter] 执行动作失败: {e}")
            return False

    # ============================================================
    # 5. 事件监听（watch_events）
    # ============================================================
    async def watch_events(self, page: Page) -> List[GameEvent]:
        """
        监听需要即时响应的事件：死亡弹窗、低HP警告、升级通知等
        """
        events = []

        # 5.1 检查死亡弹窗（Melvor 常见的死亡模态框）
        death_selectors = [
            ".death-modal",
            ".death-screen",
            "div:has-text('You have died')",
            "button:has-text('Respawn')",
        ]
        for sel in death_selectors:
            try:
                if await page.locator(sel).count() > 0:
                    events.append(GameEvent(
                        type=EventType.DEATH,
                        message="角色已死亡！",
                        data={"selector": sel}
                    ))
                    break
            except:
                pass

        # 5.2 检查低血量警告（HP < 30%）
        try:
            # 尝试从 DOM 读取当前 HP（复用 read_state 的部分逻辑）
            status = await self.read_state(page)
            if status.combat and status.combat.get("hp", 0) > 0:
                max_hp = status.combat.get("max_hp", 1)
                hp_ratio = status.combat.get("hp", 0) / max_hp
                if hp_ratio < 0.3:
                    events.append(GameEvent(
                        type=EventType.LOW_HP,
                        message=f"血量过低: {hp_ratio:.0%}",
                        data={"hp": status.combat.get("hp"), "max_hp": max_hp}
                    ))
        except:
            pass

        # 5.3 检测弹窗（通用）
        try:
            if await page.locator(".modal:visible, .popup:visible").count() > 0:
                events.append(GameEvent(
                    type=EventType.POPUP,
                    message="检测到弹窗",
                    data={}
                ))
        except:
            pass

        return events

    # ============================================================
    # 6. 辅助工具
    # ============================================================
    async def _get_timestamp(self, page: Page) -> float:
        """获取当前时间戳（秒）"""
        try:
            return await page.evaluate("Date.now() / 1000")
        except:
            import time
            return time.time()


# ============================================================
# 7. 测试入口（方便独立调试）
# ============================================================
if __name__ == "__main__":
    import asyncio
    from playwright.async_api import async_playwright

    async def test_adapter():
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            await page.goto("https://melvoridle.com")

            # 等待用户手动登录（因为 Melvor 需要登录，这里给 15 秒手动操作）
            print("请手动登录 Melvor Idle... 15 秒后自动读取状态")
            await asyncio.sleep(15)

            adapter = MelvorIdleAdapter()
            state = await adapter.read_state(page)
            print("读取到的状态:", state)

            await browser.close()

    asyncio.run(test_adapter())
