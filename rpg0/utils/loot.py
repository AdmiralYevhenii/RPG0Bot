# rpg0/utils/loot.py
from __future__ import annotations
import random

# Базові ціни за рідкістю (для покупки)
RARITY_PRICE = {
    "common": 12,
    "uncommon": 25,
    "rare": 50,
    "epic": 90,
    "legendary": 150,
}

SELL_RATE = 0.6  # продаємо за 60% від оціночної ціни

def compute_price(rarity: str) -> int:
    """Оціночна ціна предмета за рідкістю з невеликою варіацією."""
    base = RARITY_PRICE.get(rarity, 12)
    return base + random.randint(0, max(1, base // 3))

def price_of_item(it: dict) -> int:
    """Повертає ціну предмета. Якщо в item вже є 'price' — використовуємо її, інакше рахуємо від рідкісності."""
    if isinstance(it.get("price"), int):
        return it["price"]
    rarity = it.get("rarity", "common")
    return compute_price(rarity)

def sell_value(it: dict) -> int:
    """Ціна продажу предмета в магазин: частка від оціночної ціни."""
    return int(price_of_item(it) * SELL_RATE)
