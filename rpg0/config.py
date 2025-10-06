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
LOC_CITY   = "Місто"
LOC_ROAD   = "Тракт"
LOC_RUINS  = "Руїни"
LOC_FOREST = "Старий ліс"
LOC_GUILD  = "Гільдія авантюристів"
LOC_SHOP   = "Крамниця (Місто)"

DEFAULT_LOCATION = LOC_ROAD

# Порядок відображення у кнопках
LOCATION_ORDER = [LOC_CITY, LOC_ROAD, LOC_RUINS, LOC_FOREST, LOC_GUILD, LOC_SHOP]

# Граф суміжності (куди можна перейти безпосередньо з поточної локації)
ADJACENT = {
    # З гільдії: лише до Міста або на Тракт
    LOC_GUILD:  [LOC_CITY, LOC_ROAD],

    # Місто — центральний вузол: у Руїни, Старий ліс, на Тракт та в Крамницю (як окрему локацію)
    LOC_CITY:   [LOC_RUINS, LOC_FOREST, LOC_ROAD, LOC_SHOP, LOC_GUILD],

    # Тракт — коридор між Містом і іншими окраїнами
    LOC_ROAD:   [LOC_CITY, LOC_RUINS, LOC_FOREST, LOC_GUILD],

    # Руїни — назад у Місто або на Тракт
    LOC_RUINS:  [LOC_CITY, LOC_ROAD],

    # Старий ліс — назад у Місто або на Тракт
    LOC_FOREST: [LOC_CITY, LOC_ROAD],

    # Крамниця (всередині Міста) — вихід назад лише в Місто
    LOC_SHOP:   [LOC_CITY],
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
# ---- Налаштування вмінь / Гільдії ------------------------------------------
# Скільки умінь можна одночасно тримати в «слотах бою»
SKILL_SLOT_MAX = 3

# Кожні скільки рівнів пропонувати вибір нового уміння
SKILL_OFFER_LEVEL_STEP = 5

# (необов'язково) базова ціна «перевчання»/скидання слотів у Гільдії
GUILD_RESPEC_COST = 25
