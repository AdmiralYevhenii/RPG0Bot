# -*- coding: utf-8 -*-
"""
Генерація луту, рідкісність, назви за локаціями.
"""
import random
from typing import Dict
from .equipment import compute_price
from ..config import SELL_RATE

def generate_loot(location: str) -> dict:
    roll = random.random()
    if roll < 0.60:
        rarity, title, emoji, gold = "common", "⚪ Звичайний", "⚪", random.randint(0, 4)
    elif roll < 0.85:
        rarity, title, emoji, gold = "uncommon", "🟢 Незвичайний", "🟢", random.randint(2, 8)
    elif roll < 0.97:
        rarity, title, emoji, gold = "rare", "🔵 Рідкісний", "🔵", random.randint(5, 12)
    else:
        rarity, title, emoji, gold = "epic", "🟣 Епічний", "🟣", random.randint(10, 20)

    names_by_loc = {
        "Місто": ["Кишеньковий амулет", "Гільдійський жетон", "Срібний перстень"],
        "Тракт": ["Моховитий талісман", "Клинок мандрівника", "Шкіряний тубус"],
        "Руїни": ["Осколок руни", "Іржавий герб", "Кістяний оберіг"],
        "Гільдія авантюристів": ["Пам’ятний знак", "Скринька розрядів", "Лист рекомендації"],
    }

    itype = random.choices(["weapon", "armor", "accessory", "misc"], weights=[4,4,2,1])[0]
    bonus_atk, bonus_def = 0, 0
    scale = {"common":1,"uncommon":2,"rare":3,"epic":4}.get(rarity,1)
    if itype == "weapon":
        bonus_atk = scale
    elif itype == "armor":
        bonus_def = scale
    elif itype == "accessory":
        bonus_atk = max(1, scale-1); bonus_def = max(0, scale-2)

    name = random.choice(names_by_loc.get(location, names_by_loc["Тракт"]))
    price = compute_price(rarity)

    return {
        "name": name, "rarity": rarity, "title": title, "emoji": emoji,
        "type": itype, "atk": bonus_atk, "defense": bonus_def, "price": price,
        "equipped": False, "durability": 20, "set_id": None, "perks": []
    }

def price_of_item(it: Dict) -> int:
    return it.get("price", compute_price(it.get("rarity","common")))

def sell_value(it: Dict) -> int:
    return int(price_of_item(it) * SELL_RATE)
