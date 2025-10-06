# -*- coding: utf-8 -*-
"""
Класові вміння + утиліти для вибору/менеджменту/застосування в бою.
Ефекти: шкода, кровотеча, оглушення, тимчасові бафи, лікування.
"""
from __future__ import annotations
from typing import Dict, List, Tuple
import random

# Опис класових умінь
# type: dmg | bleed | stun | buff_def | buff_atk | heal
CLASS_SKILLS: Dict[str, Dict[str, Dict]] = {
    "Рицар": {
        "Щитова стійка": {"cd": 3, "type": "buff_def", "power": 2, "desc": "На 1 хід +2 до захисту."},
        "Рубаючий удар": {"cd": 2, "type": "dmg", "power": 4, "desc": "Сильний удар (+4 базової шкоди)."},
        "Оглушення": {"cd": 4, "type": "stun", "power": 1, "desc": "Оглушає ворога на 1 хід."},
    },
    "Стрілець": {
        "Прицільний постріл": {"cd": 2, "type": "dmg", "power": 3, "desc": "Точний постріл (+3 базової шкоди)."},
        "Кровоточива стріла": {"cd": 3, "type": "bleed", "power": 2, "desc": "Кровотеча 2 ходи."},
        "Уклон": {"cd": 3, "type": "buff_def", "power": 2, "desc": "На 1 хід +2 до захисту."},
    },
    "Маг": {
        "Вогняний снаряд": {"cd": 2, "type": "dmg", "power": 5, "desc": "Потужний снаряд (+5 базової шкоди)."},
        "Крижане скування": {"cd": 4, "type": "stun", "power": 1, "desc": "Заморожує на 1 хід (оглушення)."},
        "Імпульс сили": {"cd": 3, "type": "buff_atk", "power": 2, "desc": "На 1 хід +2 до атаки."},
    },
}

# ---- Допоміжні довідкові функції ----

def skills_for_class(class_name: str) -> Dict[str, Dict]:
    return CLASS_SKILLS.get(class_name or "", {})

def list_skills_names_for_class(class_name: str) -> List[str]:
    return list(skills_for_class(class_name).keys())

def skill_short_desc(skill_name: str, class_name: str | None = None) -> str:
    """
    Повертає короткий опис уміння.
    Якщо class_name передано — шукаємо лише в ньому, інакше проглядаємо всі класи.
    """
    if class_name:
        sdef = CLASS_SKILLS.get(class_name, {}).get(skill_name)
        return (sdef or {}).get("desc", "Опис відсутній.")
    for _cls, skills in CLASS_SKILLS.items():
        if skill_name in skills:
            return skills[skill_name].get("desc", "Опис відсутній.")
    return "Опис відсутній."

# ---- Навчання/набір ----

def learnable_skills_for_player(p) -> List[str]:
    pool = set(list_skills_names_for_class(p.class_name))
    known = set(p.skills_known or [])
    return sorted(list(pool - known))

def pick_new_skill_options(p, k: int = 3) -> List[str]:
    cand = learnable_skills_for_player(p)
    random.shuffle(cand)
    return cand[:k]

def can_add_to_loadout(p, skill_name: str, slot_max: int) -> Tuple[bool, str]:
    if skill_name not in (p.skills_known or []):
        return False, "Спочатку потрібно вивчити це вміння."
    if skill_name in (p.skills_loadout or []):
        return False, "Вміння вже у наборі."
    if len(p.skills_loadout or []) >= slot_max:
        return False, f"Максимум у наборі: {slot_max}."
    return True, "Окей"

def add_to_loadout(p, skill_name: str, slot_max: int) -> Tuple[bool, str]:
    # гарантуємо список
    if p.skills_loadout is None:
        p.skills_loadout = []
    ok, msg = can_add_to_loadout(p, skill_name, slot_max)
    if not ok:
        return False, msg
    p.skills_loadout.append(skill_name)
    return True, f"Додано до набору: {skill_name}"

def remove_from_loadout(p, skill_name: str) -> Tuple[bool, str]:
    if skill_name not in (p.skills_loadout or []):
        return False, "Цього вміння немає у наборі."
    p.skills_loadout.remove(skill_name)
    return True, f"Прибрано: {skill_name}"

# ---- Бойова частина ----

def apply_skill(player, enemy, skill_name: str, battle_state: dict) -> str:
    """Застосувати вміння. Повертає текст ефекту."""
    sdef = skills_for_class(player.class_name).get(skill_name)
    if not sdef:
        return "Це вміння недоступне."
    cd = sdef["cd"]; stype = sdef["type"]; power = sdef["power"]
    cds = battle_state.setdefault("cooldowns", {})
    if cds.get(skill_name, 0) > 0:
        return "Вміння на перезарядці."
    text = f"✨ {skill_name}: "

    if stype == "dmg":
        # відкладений імпорт, щоб уникнути циклічного імпорту
        from ..handlers.battle import roll_damage
        dmg = max(1, roll_damage(player.atk + power, enemy.defense))
        enemy.hp -= dmg
        text += f"завдаєте {dmg} шкоди."
    elif stype == "bleed":
        est = battle_state.setdefault("e_status", {})
        est["bleed"] = max(est.get("bleed", 0), power)  # тривалість у ходах
        text += f"накладено кровотечу на {power} х."
    elif stype == "stun":
        est = battle_state.setdefault("e_status", {})
        est["stun"] = max(est.get("stun", 0), power)
        text += "ворог оглушений!"
    elif stype == "buff_def":
        pst = battle_state.setdefault("p_status", {})
        pst["def_up"] = 1
        pst["def_up_val"] = power
        text += f"+{power} до захисту на цей раунд."
    elif stype == "buff_atk":
        pst = battle_state.setdefault("p_status", {})
        pst["atk_up"] = 1
        pst["atk_up_val"] = power
        text += f"+{power} до атаки на цей раунд."
    elif stype == "heal":
        healed = min(player.max_hp - player.hp, power)
        player.hp += healed
        text += f"лікування {healed} HP."
    else:
        text += "нічого не сталося…"

    cds[skill_name] = cd
    return text

def consume_player_temp_buffs(player, battle_state: dict) -> Tuple[int, int]:
    """(atk_bonus, def_bonus) на атаку гравця. З’їдає ефект “на 1 хід” для атаки."""
    pst = battle_state.setdefault("p_status", {})
    atk_b = pst.get("atk_up_val", 0) if pst.get("atk_up") else 0
    def_b = pst.get("def_up_val", 0) if pst.get("def_up") else 0
    pst["atk_up"] = 0; pst["atk_up_val"] = 0
    # def_up НЕ скидаємо тут — він впливає на атаку ворога; скиньте після ходу ворога через clear_player_def_buff_after_enemy_turn()
    return atk_b, def_b

def clear_player_def_buff_after_enemy_turn(battle_state: dict) -> None:
    """Скинути одноходовий деф-баф наприкінці ходу ворога."""
    pst = battle_state.setdefault("p_status", {})
    pst["def_up"] = 0
    pst["def_up_val"] = 0

def turn_tick_cooldowns(battle_state: dict) -> None:
    cds = battle_state.setdefault("cooldowns", {})
    for k in list(cds.keys()):
        if cds[k] > 0:
            cds[k] -= 1

def apply_start_of_enemy_turn_effects(enemy, battle_state: dict) -> str:
    """Початок ходу ворога: кровотечі тощо."""
    est = battle_state.setdefault("e_status", {})
    out = []
    if est.get("bleed", 0) > 0:
        bleed_dmg = max(1, int(enemy.max_hp * 0.05))
        enemy.hp -= bleed_dmg
        est["bleed"] -= 1
        out.append(f"🩸 Кровотеча: -{bleed_dmg} HP ворогу.")
    return "\n".join(out)

def enemy_is_stunned(battle_state: dict) -> bool:
    est = battle_state.setdefault("e_status", {})
    if est.get("stun", 0) > 0:
        est["stun"] -= 1
        return True
    return False

__all__ = [
    "CLASS_SKILLS",
    "skills_for_class",
    "list_skills_names_for_class",
    "skill_short_desc",
    "learnable_skills_for_player",
    "pick_new_skill_options",
    "can_add_to_loadout",
    "add_to_loadout",
    "remove_from_loadout",
    "apply_skill",
    "consume_player_temp_buffs",
    "clear_player_def_buff_after_enemy_turn",
    "turn_tick_cooldowns",
    "apply_start_of_enemy_turn_effects",
    "enemy_is_stunned",
]
