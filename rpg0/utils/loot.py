# -*- coding: utf-8 -*-
import random

# Базові ціни за рідкістю
RARITY_PRICE = {
    "common": 12,
    "uncommon": 25,
    "rare": 50,
    "epic": 90,
    "legendary": 180,
}
SELL_RATE = 0.6  # продаємо за 60%

def compute_price(rarity: str) -> int:
    """Орієнтовна ціна предмета за рідкістю з невеликою розбіжністю."""
    rarity = rarity if rarity in RARITY_PRICE else "common"
    base = RARITY_PRICE[rarity]
    return base + random.randint(0, max(1, base // 3))

def price_of_item(it: dict) -> int:
    """Ціна предмета: якщо вказана в it['price'] — беремо її, інакше рахуємо від рідкісності."""
    if isinstance(it.get("price"), int):
        return it["price"]
    return compute_price(it.get("rarity", "common"))

def sell_value(it: dict) -> int:
    """Скільки отримаємо за продаж предмета."""
    return int(price_of_item(it) * SELL_RATE)

# Імена предметів за локаціями (для flavor)
NAMES_BY_LOC = {
    "Місто": ["Кишеньковий амулет", "Гільдійський жетон", "Срібний перстень"],
    "Тракт": ["Моховитий талісман", "Клинок мандрівника", "Шкіряний тубус"],
    "Руїни": ["Осколок руни", "Іржавий герб", "Кістяний оберіг"],
    "Гільдія авантюристів": ["Значок учня", "Пам’ятна бляшка", "Пробний жетон"],
}

def _roll_item_type() -> str:
    return random.choices(["weapon", "armor", "accessory"], weights=[4, 4, 2], k=1)[0]

def _item_bonus_for(rarity: str, itype: str) -> dict:
    scale = {"common": 1, "uncommon": 2, "rare": 3, "epic": 4, "legendary": 6}.get(rarity, 1)
    if itype == "weapon":
        return {"atk": scale, "def": 0}
    if itype == "armor":
        return {"atk": 0, "def": scale}
    # accessory — змішаний бонус
    return {"atk": max(1, scale - 1), "def": max(0, scale - 2)}

def generate_loot(location: str) -> dict:
    """Згенерувати предмет з рідкісністю, типом, бонусами та (опційно) золотом."""
    r = random.random()
    if r < 0.60:
        rarity, title, emoji, gold = "common", "⚪ Звичайний", "⚪", random.randint(0, 4)
    elif r < 0.85:
        rarity, title, emoji, gold = "uncommon", "🟢 Незвичайний", "🟢", random.randint(2, 8)
    elif r < 0.97:
        rarity, title, emoji, gold = "rare", "🔵 Рідкісний", "🔵", random.randint(5, 12)
    else:
        rarity, title, emoji, gold = "epic", "🟣 Епічний", "🟣", random.randint(10, 20)

    names = NAMES_BY_LOC.get(location, NAMES_BY_LOC["Тракт"])
    name = random.choice(names)

    itype = _roll_item_type()
    bonus = _item_bonus_for(rarity, itype)
    price = compute_price(rarity)

    return {
        "name": name,
        "rarity": rarity,
        "title": title,
        "emoji": emoji,
        "gold": gold,
        "type": itype,
        "atk": bonus["atk"],
        "def": bonus["def"],
        "price": price,
        "equipped": False,
        # durability можуть додавати інші модулі під час екіпування/битви
    }
