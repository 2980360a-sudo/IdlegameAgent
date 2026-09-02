# IdleAgent v0.5.0 - core/safety.py
# 弹窗安全系统：危险词 / 交易词 / 损失警告黑名单

import re
from playwright.async_api import Page

# 危险词黑名单
DANGEROUS_WORDS = [
    '覆盖', '删除', '重置', '确认覆盖',
    'Overwrite', 'Delete', 'Reset',
]

# 交易按钮黑名单
TRADE_WORDS = [
    '购买', '出售', '买入', '卖出',
    'Buy', 'Sell',
]

# 损失警告关键词
LOSS_WORDS = [
    '稍安勿躁', '损失', '失去', 'lose', 'losing',
]


async def dismiss_post_load_modals(page: Page, max_rounds: int = 4):
    """进游戏后关闭欢迎回来/更新公告等安全弹窗。

    只点 好/关闭/知道了/OK 类按钮。危险词/交易词/损失警告绝不点。
    """
    for _ in range(max_rounds):
        try:
            btn = page.locator(
                'button.swal2-confirm:visible, '
                'button:has-text("好"):visible, button:has-text("关闭"):visible, '
                'button:has-text("知道了"):visible, button:has-text("确定"):visible, '
                'button:has-text("OK"):visible, button:has-text("Close"):visible'
            ).first
            if await btn.count():
                t = (await btn.inner_text()).strip()
                if re.search(r'|'.join(DANGEROUS_WORDS), t, re.I):
                    return
                if re.search(r'|'.join(TRADE_WORDS), t, re.I):
                    cancel = page.locator(
                        'button.swal2-cancel:visible, button:has-text("取消"):visible, '
                        'button:has-text("Cancel"):visible'
                    ).first
                    if await cancel.count():
                        await cancel.click(timeout=3000)
                    return
                try:
                    dlg = await page.locator(
                        '.swal2-popup:visible, [role=dialog]:visible'
                    ).first.inner_text()
                except Exception:
                    dlg = ''
                if re.search(r'|'.join(LOSS_WORDS), dlg, re.I):
                    cancel = page.locator(
                        'button.swal2-cancel:visible, button:has-text("取消"):visible, '
                        'button:has-text("Cancel"):visible'
                    ).first
                    if await cancel.count():
                        await cancel.click(timeout=3000)
                    return
                await btn.click(timeout=3000)
                await page.wait_for_timeout(800)
            else:
                return
        except Exception:
            return


async def safe_confirm(page: Page) -> bool:
    """若弹出 SweetAlert 确认框则点确认（非危险词）。"""
    try:
        btn = page.locator('button.swal2-confirm:visible').first
        if await btn.count():
            t = (await btn.inner_text()).strip()
            if re.search(r'|'.join(DANGEROUS_WORDS), t, re.I):
                return False
            await btn.click(timeout=5000)
            return True
    except Exception:
        pass
    return False


async def click_text_btn(page: Page, texts: list, timeout: int = 8000) -> str:
    """点击包含任一候选文字的可见按钮/链接。"""
    for t in texts:
        for css in [
            f'button:has-text("{t}"):visible',
            f'a:has-text("{t}"):visible'
        ]:
            loc = page.locator(css).first
            try:
                if await loc.count():
                    await loc.click(timeout=timeout)
                    return t
            except Exception:
                continue
    return None
