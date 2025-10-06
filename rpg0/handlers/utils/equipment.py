# -*- coding: utf-8 -*-
"""
Екіпірування, durability, сет-бонуси.
"""
from typing import Dict, Tuple, Optional
from ..config import DURABILITY_MAX, RARITY_PRICE if False else 0  # doc-hint
from ..config import REPAIR_COST_PER_POINT

RARITY_PRICE = {"common": 12, "uncommon": 25, "rare": 50, "epic": 90, "legendary": 160}

def compute_price(rarity: str) -> int:
    base = RARITY_PRICE.get(rarity, 12)
    import random
    return base + random.randint(0, base//3)

def equip_item(p, idx: int) -> Tuple[bool, str]:
    if idx < 0 or idx >= len(p.inventory):
        return False, "Невірний індекс предмета."
    it = p.inventory[idx]
    if it.get("equipped"):
        return False, "Предмет вже надягнений."
    itype = it.get("type")
    if itype not in ("weapon","armor","accessory"):
        return False, "Цей предмет не можна надягти."
    # якщо слот зайнятий
    if p.equipment.get(itype):
        return False, f"Слот {itype} вже зайнятий. Зніміть попередній предмет."

    # застосовуємо бонуси
    p.atk += it.get("atk", 0)
    p.defense += it.get("defense", 0)
    it["equipped"] = True
    # durability стартує як є
    p.equipment[itype] = it
    p.inventory.pop(idx)
    return True, f"Надягнено: {it['emoji']} {it['name']} (+ATK {it.get('atk',0)}, +DEF {it.get('defense',0)})."

def unequip_slot(p, slot: str) -> Tuple[bool, str]:
    cur = p.equipment.get(slot)
    if not cur:
        return False, "Нічого знімати."
    # зняти бонуси
    p.atk -= cur.get("atk", 0)
    p.defense -= cur.get("defense", 0)
    cur["equipped"] = False
    p.inventory.append(cur)
    p.equipment[slot] = None
    return True, f"Знято: {cur['emoji']} {cur['name']}."

def damage_durability_on_hit(p) -> None:
    """Кожен удар трохи ламає екіп."""
    for slot in ("weapon","armor","accessory"):
        it = p.equipment.get(slot)
        if it:
            it["durability"] = max(0, it.get("durability", DURABILITY_MAX) - 1)
            # якщо durability = 0 — віднімаємо бонуси, але предмет лишається надягненим (поламаний)
            if it["durability"] == 0:
                p.atk -= it.get("atk",0)
                p.defense -= it.get("defense",0)
                it["atk_broken"] = it.get("atk",0)
                it["def_broken"] = it.get("defense",0)
                it["atk"] = 0
                it["defense"] = 0

def repair_item(p, idx: int) -> Tuple[bool, str]:
    """Ремонт предмета з інвентаря. Платимо за кожен відновлений пункт durability."""
    if idx < 0 or idx >= len(p.inventory):
        return False, "Невірний індекс."
    it = p.inventory[idx]
    max_d = DURABILITY_MAX
    cur_d = it.get("durability", max_d)
    if cur_d >= max_d:
        return False, "Предмет не потребує ремонту."
    need = max_d - cur_d
    cost = need * REPAIR_COST_PER_POINT
    if p.gold < cost:
        return False, f"Бракує золота. Потрібно {cost}з."
    p.gold -= cost
    it["durability"] = max_d
    # повернемо бонуси, якщо були поламані
    if "atk_broken" in it or "def_broken" in it:
        it["atk"] = it.pop("atk_broken", it.get("atk",0))
        it["defense"] = it.pop("def_broken", it.get("defense",0))
    return True, f"Відремонтовано: {it['name']} (+{need} од. міцності) за {cost}з."

def set_bonus_summary(p) -> str:
    """Простий підсумок сетів (поки що — лише підрахунок однакових set_id)."""
    from collections import Counter
    ids = []
    for slot in ("weapon","armor","accessory"):
        it = p.equipment.get(slot)
        if it and it.get("set_id"):
            ids.append(it["set_id"])
    if not ids:
        return "Немає сет-бонусів."
    cnt = Counter(ids).most_common()
    parts = []
    for sid, n in cnt:
        # приклад: за 2+ предмети сету даємо +1 atk, за 3 — +1 def
        bonus = []
        if n >= 2: bonus.append("+1 ATK")
        if n >= 3: bonus.append("+1 DEF")
        parts.append(f"Сет {sid}: {n} шт. ({', '.join(bonus)})")
    return "\n".join(parts)
