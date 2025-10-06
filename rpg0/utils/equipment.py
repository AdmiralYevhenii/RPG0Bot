# rpg0/utils/equipment.py
from __future__ import annotations
from typing import Tuple
from ..models import Player

# Базова міцність за рідкістю
BASE_DUR_BY_RARITY = {
    "common": 20,
    "uncommon": 30,
    "rare": 45,
    "epic": 60,
    "legendary": 80,
}

def ensure_durability(item: dict) -> None:
    """Проставляє поле 'dur' (міцність), якщо його немає."""
    if item is None:
        return
    if "dur" not in item or not isinstance(item["dur"], int):
        rarity = item.get("rarity", "common")
        item["dur"] = BASE_DUR_BY_RARITY.get(rarity, 20)

def _apply_item_bonuses(p: Player, item: dict, sign: int) -> None:
    """Застосувати/зняти бонуси предмета (sign: +1 або -1)."""
    if not item:
        return
    p.atk += sign * int(item.get("atk", 0))
    p.defense += sign * int(item.get("def", 0))

def _is_equippable(item: dict) -> bool:
    return item and item.get("type") in ("weapon", "armor", "accessory")

def equip_item(p: Player, idx: int) -> Tuple[bool, str]:
    """
    Надягти предмет з інвентаря за індексом (1-based або 0-based — обидва приймаємо).
    Повертає (успіх, повідомлення).
    """
    if idx >= 1:
        idx0 = idx - 1
    else:
        idx0 = idx

    if idx0 < 0 or idx0 >= len(p.inventory):
        return False, "Невірний індекс предмета."

    item = p.inventory[idx0]
    if not _is_equippable(item):
        return False, "Цей предмет не можна надягти."

    slot = item["type"]
    if p.equipment.get(slot):
        return False, f"Слот {slot} вже зайнятий. Спершу зніміть поточний предмет."

    # гарантуємо наявність міцності
    ensure_durability(item)
    # застосовуємо бонуси та переміщаємо у слот
    _apply_item_bonuses(p, item, +1)
    item["equipped"] = True
    p.equipment[slot] = item
    p.inventory.pop(idx0)

    return True, f"Надягнено: {item.get('emoji','')} {item.get('name','')} (+ATK {item.get('atk',0)}, +DEF {item.get('def',0)})."

def unequip_slot(p: Player, slot: str) -> Tuple[bool, str]:
    """
    Зняти предмет із зазначеного слоту ('weapon'/'armor'/'accessory').
    Повертає (успіх, повідомлення).
    """
    slot = (slot or "").strip().lower()
    if slot not in ("weapon", "armor", "accessory"):
        return False, "Невірний слот."

    item = p.equipment.get(slot)
    if not item:
        return False, "Нічого знімати."

    # зняти бонуси й повернути в інвентар
    _apply_item_bonuses(p, item, -1)
    item["equipped"] = False
    ensure_durability(item)
    p.inventory.append(item)
    p.equipment[slot] = None

    return True, f"Знято: {item.get('emoji','')} {item.get('name','')}."

def damage_durability_on_hit(p: Player, slot: str = "weapon", amount: int = 1) -> str:
    """
    Зменшує міцність предмета у слоті (weapon/armor/accessory).
    Якщо міцність падає до 0 — предмет знімається та повертається в інвентар, бонуси з героя знімаються.
    Повертає коротке повідомлення для бою (або порожній рядок).
    """
    slot = (slot or "weapon").lower()
    if slot not in ("weapon", "armor", "accessory"):
        return ""

    it = p.equipment.get(slot)
    if not it:
        return ""

    ensure_durability(it)
    it["dur"] = max(0, it["dur"] - max(1, amount))

    if it["dur"] == 0:
        # item “ламається” — зняти бонуси й повернути в інвентар
        _apply_item_bonuses(p, it, -1)
        it["equipped"] = False
        p.inventory.append(it)
        p.equipment[slot] = None
        return f"⚠️ Ваш {slot} зламався і був знятий!"

    return ""

def repair_item(item: dict, full: bool = True, amount: int = 10) -> int:
    """
    Ремонт предмета: або повний до базового значення, або +amount.
    Повертає, скільки одиниць міцності відновлено.
    """
    if not item:
        return 0
    ensure_durability(item)
    rarity = item.get("rarity", "common")
    max_dur = BASE_DUR_BY_RARITY.get(rarity, 20)
    before = item["dur"]
    if full:
        item["dur"] = max_dur
    else:
        item["dur"] = min(max_dur, item["dur"] + max(1, amount))
    return item["dur"] - before

def item_repair_price(item: dict, per_point_cost: int = 1) -> int:
    """
    Вартість ремонту (спрощено): (максимум - поточна міцність) * коефіцієнт за рідкістю * per_point_cost.
    """
    if not item:
        return 0
    ensure_durability(item)
    rarity = item.get("rarity", "common")
    max_dur = BASE_DUR_BY_RARITY.get(rarity, 20)
    missing = max(0, max_dur - item["dur"])
    rarity_mult = {"common":1, "uncommon":2, "rare":3, "epic":5, "legendary":8}.get(rarity, 1)
    return missing * rarity_mult * max(1, per_point_cost)

__all__ = [
    "ensure_durability",
    "equip_item",
    "unequip_slot",
    "damage_durability_on_hit",
    "repair_item",
    "item_repair_price",
    "BASE_DUR_BY_RARITY",
]
