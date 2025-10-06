# rpg0/utils/equipment.py
from dataclasses import asdict
from ..models import Player

# Базова міцність за рідкістю (можеш підкрутити)
BASE_DUR_BY_RARITY = {
    "common": 20,
    "uncommon": 30,
    "rare": 45,
    "epic": 60,
    "legendary": 80,
}

def ensure_durability(item: dict) -> None:
    """Проставляє поле 'dur' (міцність), якщо його немає."""
    if "dur" not in item or not isinstance(item["dur"], int):
        rarity = item.get("rarity", "common")
        item["dur"] = BASE_DUR_BY_RARITY.get(rarity, 20)

def damage_durability_on_hit(p: Player, slot: str = "weapon", amount: int = 1) -> str:
    """
    Зменшує міцність предмета у слоті (weapon/armor/accessory).
    Якщо міцність падає до 0 — предмет знімається та повертається в інвентар (зі значенням 0),
    а бонуси з героя знімаються.
    Повертає коротке повідомлення для бою (або порожній рядок).
    """
    it = p.equipment.get(slot)
    if not it:
        return ""

    ensure_durability(it)
    it["dur"] = max(0, it["dur"] - max(1, amount))

    # якщо зламалось — зняти й забрати бонуси
    if it["dur"] == 0:
        # зняти бонуси
        p.atk -= it.get("atk", 0)
        p.defense -= it.get("def", 0)
        it["equipped"] = False

        # повернути до інвентаря (із dur=0, щоб було видно що потребує ремонту)
        p.inventory.append(it)
        p.equipment[slot] = None

        return f"⚠️ Ваш {slot} зламався і був знятий!"

    return ""

def repair_item(item: dict, full: bool = True, amount: int = 10) -> int:
    """
    Ремонт предмета: або повний до базового значення, або +amount.
    Повертає, скільки одиниць міцності відновлено.
    """
    ensure_durability(item)
    rarity = item.get("rarity", "common")
    max_dur = BASE_DUR_BY_RARITY.get(rarity, 20)
    before = item["dur"]
    if full:
        item["dur"] = max_dur
    else:
        item["dur"] = min(max_dur, item["dur"] + amount)
    return item["dur"] - before

def item_repair_price(item: dict, per_point_cost: int = 1) -> int:
    """
    Орієнтовна вартість ремонту: (максимум - поточна міцність) * пер-поінт ціна.
    Можна ускладнити залежно від рідкісності.
    """
    ensure_durability(item)
    rarity = item.get("rarity", "common")
    max_dur = BASE_DUR_BY_RARITY.get(rarity, 20)
    missing = max(0, max_dur - item["dur"])
    # приклад коефіцієнтів за рідкістю
    mult = {"common":1, "uncommon":2, "rare":3, "epic":5, "legendary":8}.get(rarity,1)
    return missing * per_point_cost * mult
