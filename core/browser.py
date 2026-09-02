# IdleAgent v0.6.0 - core/browser.py
# 通用浏览器自动化封装

import asyncio
import json
import os
import re
import datetime
from typing import Optional, Dict, Any, List
from playwright.async_api import async_playwright, Page

# 从环境变量读取配置（脱敏）
PROFILE = os.environ.get('BROWSER_PROFILE', '/tmp/idleagent_profile')
GAME_URL = os.environ.get('GAME_URL', '')
ACCOUNT = os.environ.get('GAME_ACCOUNT', '')
PASSWORD = os.environ.get('GAME_PASSWORD', '')
HEADLESS = os.environ.get('HEADLESS', 'true').lower() == 'true'
BROWSER_WIDTH = int(os.environ.get('BROWSER_WIDTH', '1920'))
BROWSER_HEIGHT = int(os.environ.get('BROWSER_HEIGHT', '1080'))

# 默认拦截的第三方请求（与游戏运行无关）
DEFAULT_BLOCK_SUBSTR = [
    'mod.io', 'googlesyndication', 'doubleclick', 'googletagmanager',
    'google-analytics', 'googleadservices', 'facebook.net', 'facebook.com',
    'cloudflareinsights', 'hotjar', 'sentry.io',
]


def log(msg: str):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def ts_now() -> str:
    return datetime.datetime.now().strftime('%Y%m%d_%H%M%S')


def parse_save_time(text: str) -> Optional[datetime.datetime]:
    """解析存档时间戳：支持中文和英文格式。"""
    text = text or ''

    # 中文格式：最后保存：2026/8/3 22:06:40
    m = re.search(
        r'(?:最后保存|Last Save[d]?)[\s:]*(\d{4})/(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2}):(\d{2})',
        text
    )
    if m:
        y, mo, d, h, mi, s = map(int, m.groups())
        return datetime.datetime(y, mo, d, h, mi, s)

    # 英文格式：M/D/YYYY, h:mm:ss AM/PM
    m = re.search(
        r'(?:最后保存|Last Save[d]?)[\s:]*(\d{1,2})/(\d{1,2})/(\d{4}),?\s+(\d{1,2}):(\d{2}):(\d{2})\s*([AP]M)?',
        text, re.I
    )
    if m:
        mo, d, y, h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3)), \
                              int(m.group(4)), int(m.group(5)), int(m.group(6))
        if (m.group(7) or '').upper() == 'PM' and h < 12:
            h += 12
        if (m.group(7) or '').upper() == 'AM' and h == 12:
            h = 0
        return datetime.datetime(y, mo, d, h, mi, s)
    return None


class BrowserManager:
    """通用浏览器管理器：负责启动、登录、存档加载、页面生命周期。"""

    def __init__(
        self,
        game_url: str = '',
        account: str = '',
        password: str = '',
        profile_dir: str = None,
        block_list: List[str] = None,
        headless: bool = None,
        width: int = None,
        height: int = None
    ):
        self.game_url = game_url or GAME_URL
        self.account = account or ACCOUNT
        self.password = password or PASSWORD
        self.profile_dir = profile_dir or PROFILE
        self.block_list = block_list or DEFAULT_BLOCK_SUBSTR
        self.headless = headless if headless is not None else HEADLESS
        self.width = width or BROWSER_WIDTH
        self.height = height or BROWSER_HEIGHT
        self.ctx = None
        self.page = None
        self.pw = None

    async def launch(self):
        """启动浏览器并创建页面。"""
        # Windows 上 ProactorEventLoop 才支持 spawn 子进程；uvicorn 用 --reload/--workers 时会退回 SelectorEventLoop
        import sys as _sys
        try:
            _loop = asyncio.get_running_loop()
        except RuntimeError:
            _loop = None
        if _sys.platform == 'win32' and _loop is not None and not isinstance(_loop, asyncio.ProactorEventLoop):
            raise RuntimeError(
                f'当前事件循环 {type(_loop).__name__} 不支持启动浏览器（Windows 需 ProactorEventLoop）。'
                '请去掉 uvicorn 的 --reload / --workers 参数后重启：'
                'python -m uvicorn api.app:app --host 0.0.0.0 --port 8000'
            )
        os.makedirs(self.profile_dir, exist_ok=True)
        self.pw = await async_playwright().start()
        self.ctx = await self.pw.chromium.launch_persistent_context(
            self.profile_dir,
            headless=self.headless,
            viewport={'width': self.width, 'height': self.height},
            locale='zh-CN',
            timezone_id='Asia/Shanghai',
            args=[
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--js-flags=--max-old-space-size=4096',
            ],
        )
        # 拦截第三方请求
        await self.ctx.route('**/*', lambda route: (
            route.abort() if any(b in route.request.url for b in self.block_list)
            else route.continue_()
        ))
        self.page = self.ctx.pages[0] if self.ctx.pages else await self.ctx.new_page()
        log('浏览器已启动')
        return self.page

    async def navigate(self, url: str = None):
        """导航到游戏页面。"""
        url = url or self.game_url
        log(f'打开游戏页: {url}')
        try:
            await self.page.goto(url, wait_until='domcontentloaded', timeout=90000)
        except Exception as e:
            log(f'goto 异常（继续等待页面自愈）: {type(e).__name__}')
            await self.page.wait_for_timeout(10000)

    async def close(self):
        """关闭浏览器。"""
        if self.ctx:
            try:
                await self.ctx.close()
            except Exception:
                pass
        if self.pw:
            try:
                await self.pw.stop()
            except Exception:
                pass
        log('浏览器已关闭')

    # ---------- 启动序列 ----------

    async def boot_sequence(self, char_select_timeout: int = 200000, ready_timeout: int = 200000):
        """完整的启动序列：启动 -> 角色选择 -> 加载存档 -> 游戏就绪。"""
        await self._boot_to_char_select(timeout_ms=char_select_timeout)
        await self._load_newest_save()
        await self._wait_game_ready(timeout_ms=ready_timeout)
        log('游戏启动序列完成')

    async def _boot_to_char_select(self, timeout_ms: int = 200000):
        """驱动启动序列直到角色选择页。"""
        stages = [
            '正在获取账户信息', '正在获取云存档', '正在初始化模组管理器',
            'Confirming Expansions', '正在载入游戏数据', 'Fetching', 'Loading'
        ]
        seen = set()
        login_done = False
        lang_switched = False
        start = asyncio.get_event_loop().time()

        while True:
            try:
                body = await self.page.inner_text('body')
                demo = ('这是试玩版本' in body) or ('DEMO VERSION' in body)
                at_char_select = ('选择你的角色' in body) or ('Save Slot' in body)

                if not demo and at_char_select:
                    log('到达角色选择页（已登录）')
                    return

                if 'Select Language' in body:
                    log('选择语言: 简体中文')
                    await self._select_language('简体中文')
                    continue

                if not lang_switched and (
                    ('Save Slot' in body and '存档栏位' not in body) or 'DEMO VERSION' in body
                ):
                    await self._switch_to_chinese()
                    lang_switched = True
                    continue

                if demo and not login_done:
                    entry = await self._find_login_entry()
                    if entry:
                        log('点击云账号登录入口')
                        await entry.click(timeout=15000)
                        await self.page.wait_for_timeout(2500)
                        await self._do_login()
                        login_done = True
                        continue
                    else:
                        log('试玩版页面但未找到登录入口，等待…')

                for s in stages:
                    if s in body and s not in seen:
                        seen.add(s)
                        log(f'启动阶段: {s}')
            except Exception as e:
                log(f'boot轮询异常(忽略): {type(e).__name__}: {str(e)[:120]}')

            if (asyncio.get_event_loop().time() - start) * 1000 > timeout_ms:
                raise TimeoutError('等待角色选择页超时')
            await self.page.wait_for_timeout(2500)

    async def _select_language(self, lang: str):
        """选择语言。"""
        zh = self.page.locator(f'text={lang}').first
        try:
            await zh.click(timeout=8000)
        except Exception:
            try:
                await zh.click(timeout=8000, force=True)
            except Exception:
                js_code = """
                () => {
                    const els = [...document.querySelectorAll('*')]
                        .filter(e => e.innerText === '%s' && e.children.length === 0);
                    if (els.length) els[0].click();
                }
                """ % lang
                await self.page.evaluate(js_code)
        await self.page.wait_for_timeout(3000)

    async def _switch_to_chinese(self):
        """从英文切回中文。"""
        cl = self.page.locator('text=Change Language:visible')
        if await cl.count():
            log('页面为英文，经 Change Language 切换为简体中文')
            await cl.first.click(timeout=15000)
            await self.page.wait_for_timeout(2000)
            zh = self.page.locator('text=简体中文:visible')
            if await zh.count():
                await zh.first.click(timeout=15000)
            await self.page.wait_for_timeout(3000)

    async def _find_login_entry(self):
        """查找登录入口。"""
        for css in [
            'text=云账:visible',
            'text=Sign in to your Cloud Account:visible',
            "button:has-text('Sign In'):visible",
            "button:has-text('登录'):visible"
        ]:
            loc = self.page.locator(css)
            if await loc.count():
                return loc.first
        return None

    async def _do_login(self):
        """执行登录。"""
        log('填写云账号登录表单…')
        pwd = self.page.locator("input[type='password']:visible").first
        await pwd.wait_for(state='visible', timeout=60000)
        user_box = self.page.locator("input[type='text']:visible, input[type='email']:visible").first

        for attempt in range(3):
            await user_box.fill(self.account)
            await pwd.fill(self.password)
            await self.page.wait_for_timeout(600)
            try:
                u = await user_box.input_value()
                p = await pwd.input_value()
            except Exception:
                u = p = ''
            if u == self.account and p == self.password:
                break
            log(f'表单值未保留，等待重渲染后重填（第{attempt + 1}次）')
            await self.page.wait_for_timeout(2000)

        submitted = False
        for label in ['Sign In', 'Sign in', 'Log In', 'Login', '登入', '登录', '登陆']:
            for css in [
                f"button:has-text('{label}'):visible",
                f"a:has-text('{label}'):visible",
                f"input[type='submit'][value*='{label}' i]:visible",
                f"input[type='button'][value*='{label}' i]:visible"
            ]:
                btn = self.page.locator(css).first
                if await btn.count():
                    await btn.click()
                    log(f'点击登录按钮: {css}')
                    submitted = True
                    break
            if submitted:
                break

        if not submitted:
            anysubmit = self.page.locator(
                "input[type='submit']:visible, button[type='submit']:visible"
            ).first
            if await anysubmit.count():
                await anysubmit.click()
                log('点击通用提交按钮')
            else:
                await pwd.press('Enter')
                log('按回车提交登录')
        await self.page.wait_for_timeout(6000)

    async def _load_newest_save(self):
        """加载最新存档。"""
        deadline = asyncio.get_event_loop().time() + 60
        body = ''
        while asyncio.get_event_loop().time() < deadline:
            body = await self.page.inner_text('body')
            if ('Save Slot' in body or '存档栏位' in body) and (
                'Click to create' in body or '点击创建' in body or
                '最后保存' in body or 'Last Save' in body
            ):
                break
            await self.page.wait_for_timeout(2000)
        else:
            raise TimeoutError('角色选择页60秒内槽位未就绪')

        has_cloud = ('EXISTING CLOUD SAVE DETECTED' in body) or ('检测到云存档' in body)
        local_time = parse_save_time(body)
        log(f'本地存档时间: {local_time}；检测到云存档: {has_cloud}')

        if local_time is None:
            await self._cloud_route()
        else:
            slot_loc = await self._find_slot_loc(75)
            if slot_loc is None:
                raise RuntimeError('找不到本地存档槽')
            await slot_loc.click(timeout=15000)
            log('点击本地存档槽')
            await self.page.wait_for_timeout(3000)

            modal_text = await self.page.inner_text('body')
            all_times = re.findall(r'(\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2}:\d{2})', modal_text)
            newer_than_local = False
            for t in all_times:
                tt = parse_save_time('最后保存：' + t)
                if tt and local_time and tt > local_time:
                    newer_than_local = True

            has_modal = (
                await self.page.locator("button:has-text('取消'):visible").count() or
                await self.page.locator("button:has-text('Cancel'):visible").count()
            )
            if has_modal and newer_than_local:
                log('⚠️ 云存档比本地新——取消，改走云存档下载路线（安全方向）')
                for css in [
                    "button:has-text('取消'):visible",
                    "button:has-text('Cancel'):visible"
                ]:
                    loc = self.page.locator(css)
                    if await loc.count():
                        await loc.first.click(timeout=15000)
                        break

    async def _cloud_route(self):
        """显示云存档并下载。"""
        show_btn = None
        for _ in range(20):
            for css in [
                "button:has-text('显示云存档'):visible",
                "button:has-text('Show Cloud Saves'):visible",
                'text=显示云存档:visible',
                'text=Show Cloud Saves:visible'
            ]:
                loc = self.page.locator(css)
                if await loc.count():
                    show_btn = loc.first
                    break
            if show_btn is not None:
                break
            await self.page.wait_for_timeout(1500)

        if show_btn is None:
            raise RuntimeError("找不到'显示云存档'按钮")

        await show_btn.click(timeout=15000)
        log('点击: 显示云存档')

        slot_loc = await self._find_slot_loc(90)
        if slot_loc is None:
            raise RuntimeError('云存档列表90秒内没有出现存档槽')
        await slot_loc.click(timeout=15000)
        log('点击云存档槽')
        await self.page.wait_for_timeout(2500)
        await self._confirm_if_modal()

    async def _find_slot_loc(self, timeout_s: int = 75):
        """等待并返回带时间戳的存档槽可点元素。"""
        deadline = asyncio.get_event_loop().time() + timeout_s
        while asyncio.get_event_loop().time() < deadline:
            for css in ['text=最后保存:visible', 'text=Last Save:visible']:
                loc = self.page.locator(css)
                if await loc.count():
                    return loc.first
            try:
                if parse_save_time(await self.page.inner_text('body')):
                    for css in ['text=最后保存', 'text=Last Save']:
                        loc = self.page.locator(css)
                        if await loc.count():
                            return loc.first
            except Exception:
                pass
            await self.page.wait_for_timeout(1500)
        return None

    async def _confirm_if_modal(self):
        """若弹出确认框则点确认（安全词）。"""
        for css in [
            "button:has-text('确认'):visible",
            "button:has-text('Confirm'):visible",
            "button:has-text('Yes'):visible",
            "button:has-text('是'):visible"
        ]:
            loc = self.page.locator(css)
            if await loc.count():
                await loc.first.click(timeout=15000)
                log(f'确认覆盖弹窗: {css}')
                return True
        return False

    async def _wait_game_ready(self, timeout_ms: int = 200000):
        """等待游戏主界面就绪。"""
        deadline = asyncio.get_event_loop().time() + timeout_ms / 1000
        seen = set()
        while asyncio.get_event_loop().time() < deadline:
            try:
                body = await self.page.inner_text('body')
                if '仓库' in body or 'Bank' in body:
                    break
                for s in ['正在下载', 'Downloading', '正在载入', 'Loading', '离线', 'Offline']:
                    if s in body and s not in seen:
                        seen.add(s)
                        log(f'载入阶段: {s}')
            except Exception:
                pass
            await self.page.wait_for_timeout(3000)
        else:
            raise TimeoutError('等待游戏主界面超时')

        from .safety import dismiss_post_load_modals
        for wait_s in [8, 6, 6]:
            await self.page.wait_for_timeout(wait_s * 1000)
            await dismiss_post_load_modals(self.page)
        log('游戏UI就绪')

    async def force_save(self) -> bool:
        """顶栏强制保存。"""
        from .safety import dismiss_post_load_modals
        try:
            await dismiss_post_load_modals(self.page)
            for css in [
                "button:has-text('Force Save'):visible",
                "button:has-text('强制保存'):visible"
            ]:
                btn = self.page.locator(css).first
                if await btn.count():
                    try:
                        await btn.click(timeout=8000)
                        await self.page.wait_for_timeout(5000)
                        body = await self.page.inner_text('body')
                        ok = (
                            '保存成功' in body or '云保存成功' in body or
                            'Save Successful' in body or 'Cloud Save Successful' in body
                        )
                        log(f'强制保存已点击（成功提示检出={ok}）')
                        return True
                    except Exception:
                        pass

            body = await self.page.inner_text('body')
            m = re.search(r'Last Cloud Save\s*\n?\s*(\d+)h (\d+)m (\d+)s', body)
            if m:
                secs = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
                log(f'顶栏上次云保存: {secs}秒前')
                if secs <= 120:
                    log('云存档刚刚同步过，视为保存成功')
                    return True

            m = re.search(r'上次云保存\s*[\s:]?\s*(\d+)\s*小时\s*(\d+)\s*分\s*(\d+)\s*秒', body)
            if m:
                secs = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
                log(f'顶栏上次云保存: {secs}秒前')
                if secs <= 120:
                    log('云存档刚刚同步过，视为保存成功')
                    return True

            log('强制保存未执行（由自动存档保底）')
            return False
        except Exception as e:
            log(f'强制保存失败（由自动存档保底）: {type(e).__name__}')
            return False

    async def nav_to(self, names: List[str], _retried: bool = False) -> bool:
        """侧边栏导航到指定页（双语候选）。"""
        for n in names:
            for css in [
                f"a.nav-link:has-text('{n}'):visible",
                f"a:has-text('{n}'):visible",
                rf"text=/^\s*{n}\s*$/:visible"
            ]:
                loc = self.page.locator(css).first
                try:
                    if await loc.count():
                        await loc.click(timeout=8000)
                        log(f'导航到: {n}')
                        return True
                except Exception:
                    continue

        if not _retried:
            log(f'导航受阻，清弹窗后重试: {names}')
            from .safety import dismiss_post_load_modals
            await dismiss_post_load_modals(self.page, max_rounds=3)
            await self.page.wait_for_timeout(1200)
            return await self.nav_to(names, _retried=True)

        log(f'导航失败: {names}')
        return False
