# -*- coding: utf-8 -*-
"""
Глобальні конфіги/константи гри.
"""

import os

# ---- Бот / збереження -------------------------------------------------------
BOT_DISPLAY_NAME = os.getenv("BOT_DISPLAY_NAME", "RPG0")
PERSIST_FILE = os.getenv("PERSIST_FILE", "rpgbot.pickle")

# ---- Webhook / Render -------------------------------------------------------
WEBHOOK_URL = os.getenv("WEBHOOK_URL")             # наприклад: https://your-app.onrender.com
PORT = int(os.getenv("PORT", "10000"))
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", os.getenv("BOT_TOKEN", "bot"))

# ---- Локації та переходи ----------------------------------------------------
LOC_GUILD       = "Гільдія авантюристів"
LOC_CITY        = "Місто"
LOC_TRACT       = "Тракт"
LOC_RUINS       = "Руїни"
LOC_OLD_FOREST  = "Старий ліс"
LOC_SHOP        = "Крамниця"  # локація-магазин у Місті

DEFAULT_LOCATION = LOC_TRACT

# Порядок відображення у кнопках
LOCATION_ORDER = [LOC_CITY, LOC_RUINS, LOC_OLD_FOREST, LOC_GUILD, LOC_SHOP]

TRAVEL_GRAPH = {
    LOC_GUILD:      [LOC_CITY, LOC_TRACT],
    LOC_CITY:       [LOC_GUILD, LOC_TRACT, LOC_RUINS, LOC_OLD_FOREST, LOC_SHOP],
    LOC_SHOP:       [LOC_CITY],            # магазин — кімната в Місті
    LOC_TRACT:      [LOC_CITY, LOC_RUINS, LOC_OLD_FOREST],
    LOC_RUINS:      [LOC_CITY, LOC_TRACT],
    LOC_OLD_FOREST: [LOC_CITY, LOC_TRACT],
}

# ---- Класи і передісторії (для реєстрації) ---------------------------------
CLASSES = {
    "Рицар":   {"desc": "важкоозброєний захисник", "hp": 10, "defense": 2, "atk": 1},
    "Стрілець":{"desc": "спритний мисливець",       "atk": 2, "potions": 1},
    "Маг":     {"desc": "володар заклять",          "atk": 3, "potions": 1},
}

BACKSTORIES = {
    "Селянин":        {"desc": "загартований працею",      "hp": 8},
    "Учень алхіміка": {"desc": "вміє варити настоянки",    "potions": 2},
    "Вигнанець":      {"desc": "звик битись за себе",      "atk": 2},
    "Адепт храму":    {"desc": "благословення захисту",     "defense": 2},
    "Шляхтич":        {"desc": "має статки",               "gold": 50},
}
# ---- Гільдія / вміння ------------------------------------------------------
SKILL_SLOT_MAX = 3
SKILL_OFFER_LEVEL_STEP = 5
GUILD_RESPEC_COST = 25
