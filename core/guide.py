# IdleAgent - core/guide.py
# 攻略知识库检索：从 guides/ 目录加载成熟攻略（官方 Wiki + 社区），作为决策方针。
# 设计目标：不再硬编码「7 个操作」，而是把攻略原文交给 LLM，让它对照当前状态判断下一步。

import os
from typing import Dict, List, Optional

from core.state import GameState

# guides/ 目录：相对本文件上级目录
GUIDE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'guides')


def _list_guides() -> List[str]:
    """返回所有攻略文件路径（按名称排序）。"""
    if not os.path.isdir(GUIDE_DIR):
        return []
    return sorted(
        os.path.join(GUIDE_DIR, f)
        for f in os.listdir(GUIDE_DIR)
        if f.lower().endswith(('.md', '.txt'))
    )


def load_guides() -> Dict[str, str]:
    """加载全部攻略：{文件名: 正文}。"""
    guides: Dict[str, str] = {}
    for path in _list_guides():
        try:
            with open(path, 'r', encoding='utf-8') as f:
                guides[os.path.basename(path)] = f.read()
        except OSError:
            continue
    return guides


def list_guide_meta() -> List[Dict[str, str]]:
    """返回攻略元信息列表（供仪表盘展示）：文件名、标题、来源、字数。"""
    metas: List[Dict[str, str]] = []
    for name, content in load_guides().items():
        title, source = name, ''
        lines = content.splitlines()
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('# '):
                title = stripped.lstrip('# ').strip()
                break
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('> 来源'):
                source = stripped.lstrip('>').strip()
                break
        metas.append({
            'file': name,
            'title': title,
            'source': source,
            'chars': str(len(content)),
        })
    return metas


def get_policy(state: Optional[GameState] = None, max_chars: int = 9000) -> str:
    """返回注入 LLM 的「方针」文本。

    当前策略：按相关度排序后拼接全部攻略（截断到 max_chars）。
    后续可在此扩展为真正的检索（基于 state 的等级/进度选取相关章节）。
    """
    guides = load_guides()
    if not guides:
        return ''

    # 排序：训练顺序（开局方针）优先，其余按名称。
    def _priority(name: str) -> int:
        if 'training_order' in name or '开局' in name or '训练' in name:
            return 0
        if 'combat' in name or '战斗' in name:
            return 1
        if 'township' in name or '城镇' in name:
            return 2
        if 'money' in name or '赚钱' in name:
            return 3
        return 4

    ordered = sorted(guides.items(), key=lambda kv: (_priority(kv[0]), kv[0]))
    parts = [f'### 攻略：{name}\n{content}' for name, content in ordered]
    text = '\n\n'.join(parts)
    if len(text) > max_chars:
        text = text[:max_chars] + '\n\n(攻略过长，已截断)'
    return text


def format_action_catalog(catalog: Optional[Dict] = None, max_chars: int = 4000) -> str:
    """把动作目录格式化为紧凑文本，供 LLM 选择动作。

    目录结构（来自 adapter.probe_action_catalog）:
      {skills: [{key, name, lv, acts: [{id, name, lv}]}], areas, dungeons, slayerAreas}
    """
    if not catalog:
        return ''
    lines: List[str] = []

    skills = catalog.get('skills') or []
    for s in skills:
        name = s.get('name') or s.get('key')
        lv = s.get('lv')
        acts = s.get('acts') or []
        # 已解锁动作（lv<=技能等级）单独标出，未来动作括注需求等级
        unlocked = [a for a in acts if (a.get('lv') or 0) <= (lv or 0)]
        upcoming = [a for a in acts if (a.get('lv') or 0) > (lv or 0)][:4]
        parts = [f"{a.get('name')}({a.get('lv')})" for a in unlocked[:25]]
        txt = f'- {name} Lv{lv}: ' + (', '.join(parts) if parts else '(无已解锁动作)')
        if upcoming:
            txt += '；临近解锁: ' + ', '.join(f"{a.get('name')}({a.get('lv')})" for a in upcoming)
        lines.append(txt)

    areas = catalog.get('areas') or []
    if areas:
        lines.append('- 战斗区域: ' + ', '.join(f"{a.get('name')}({a.get('lv')})" for a in areas[:30]))
    dungeons = catalog.get('dungeons') or []
    if dungeons:
        lines.append('- 地牢: ' + ', '.join(f"{d.get('name')}({d.get('diff')})" for d in dungeons[:20]))
    slayer = catalog.get('slayerAreas') or []
    if slayer:
        lines.append('- 屠杀区域: ' + ', '.join(f"{a.get('name')}({a.get('lv')})" for a in slayer[:20]))
    buildings = catalog.get('buildings') or []
    if buildings:
        lines.append('- 城镇建筑: ' + ', '.join(f"{b.get('name')}" for b in buildings[:40]))

    text = '\n'.join(lines)
    if len(text) > max_chars:
        text = text[:max_chars] + '\n(动作目录过长，已截断)'
    return text
