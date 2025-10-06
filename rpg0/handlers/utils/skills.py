# -*- coding: utf-8 -*-
"""
Скіли за класами, кд, навчання у Гільдії, вибір активних навичок (до 3).
"""
from typing import Dict, List, Tuple
from ..config import SKILL_COOLDOWN_TURNS

# Базовий пул скілів за класами
SKILLS_BY_CLASS: Dict[str, Dict[str, Dict]] = {
    "Рицар": {
        "shield_bash": {"name": "Удар щитом", "desc": "Стан: оглушення на 1 хід", "cd": 3, "stun": 1, "bleed": 0, "atk_boost": 0},
        "guard_stance": {"name": "Стійка захисту", "desc": "+2 DEF на цей бій", "cd": 4, "stun": 0, "bleed": 0, "def_add": 2},
    },
    "Стрілець": {
        "aimed_shot": {"name": "Прицільний постріл", "desc": "Велика шкода", "cd": 3, "attack_add": 3},
        "bleed_arrow": {"name": "Кровоточива стріла", "desc": "Кровотеча на 3 ходи", "cd": 4, "bleed": 3},
    },
    "Маг": {
        "fire_bolt": {"name": "Вогняний болт", "desc": "Дод. шкода + шанс підпалу (кровотеча як аналог)", "cd": 3, "attack_add": 2, "bleed": 2},
        "time_twist": {"name": "Скрут часу", "desc": "+ініціатива", "cd": 4, "initiative_add": 40},
    },
}

def skills_for_class(cls: str) -> Dict[str, Dict]:
    return SKILLS_BY_CLASS.get(cls, {})

def grant_skill_on_level(p, step: int = 5) -> Tuple[bool, str]:
    """На кожному step-рівні (5,10,15...) пропонуємо вибрати новий скіл з класового пулу."""
    if p.level % step != 0:
        return False, ""
    pool = skills_for_class(p.class_name)
    if not pool:
        return False, ""
    # знайти ті, яких ще немає
    candidates = [sid for sid in pool.keys() if sid not in p.known_skills]
    if not candidates:
        return False, ""
    # Просто автоматично додаємо перший (або зроби меню вибору в Гільдії)
    sid = candidates[0]
    p.known_skills.append(sid)
    return True, f"Ви опанували нове вміння: {pool[sid]['name']}"

def format_skills_list(p) -> str:
    if not p.known_skills:
        return "Немає вивчених вмінь."
    pool = skills_for_class(p.class_name)
    lines = []
    for sid in p.known_skills:
        meta = pool.get(sid, {"name": sid})
        used = "🟩" if sid in p.slotted_skills else "⬜"
        lines.append(f"{used} {meta.get('name', sid)} (/{sid})")
    return "\n".join(lines)
