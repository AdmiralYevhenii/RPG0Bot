# -*- coding: utf-8 -*-
"""
Конфіг і константи.
"""
import os

BOT_DISPLAY_NAME = os.getenv("BOT_DISPLAY_NAME", "RPG0")
PERSIST_FILE = os.getenv("PERSIST_FILE", "rpgbot.pickle")
DEFAULT_LOCATION = "Тракт"

# Вебхуки (Render)
WEBHOOK_URL = os.getenv("WEBHOOK_URL")        # типу: https://your-app.onrender.com
PORT = int(os.getenv("PORT", "10000"))
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", os.getenv("BOT_TOKEN"))

# Баланс
CRIT_CHANCE = 0.15        # 15% крит
CRIT_MULTIPLIER = 2.0
SKILL_COOLDOWN_TURNS = 3  # дефолт для загального "вміння", якщо клас не вказав інше
BLEED_TURNS = 3
STUN_TURNS = 1
DURABILITY_MAX = 20
REPAIR_COST_PER_POINT = 2
SELL_RATE = 0.6
SKILL_SLOT_MAX = 3           # скільки умінь можна взяти в бій
SKILL_SELECT_INTERVAL = 5    # кожні 5 рівнів пропонується нове вміння


# Класи/передісторії (для /register)
CLASSES = {
    "Рицар":   {"desc": "важкоозброєний захисник", "hp": 10, "defense": 2, "atk": 1},
    "Стрілець": {"desc": "спритний мисливець",     "atk": 2, "potions": 1},
    "Маг":     {"desc": "володар заклять",         "atk": 3, "potions": 1},
}
BACKSTORIES = {
    "Селянин":        {"desc": "загартований працею",    "hp": 8},
    "Учень алхіміка": {"desc": "вміє варити настоянки",  "potions": 2},
    "Вигнанець":      {"desc": "звик битись за себе",    "atk": 2},
    "Адепт храму":    {"desc": "благословення захисту",  "defense": 2},
    "Шляхтич":        {"desc": "має статки",             "gold": 50},
}

# Локації
LOCATIONS = ["Місто", "Тракт", "Руїни", "Гільдія авантюристів"]
DEFAULT_LOCATION = "Тракт"
