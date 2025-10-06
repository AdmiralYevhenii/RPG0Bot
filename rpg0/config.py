# -*- coding: utf-8 -*-

import os

# Загальне
BOT_DISPLAY_NAME = os.getenv("BOT_DISPLAY_NAME", "RPG0")
PERSIST_FILE = os.getenv("PERSIST_FILE", "rpgbot.pickle")
DEFAULT_LOCATION = "Тракт"

# Вебхук/пулінг
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()
PORT = int(os.getenv("PORT", "10000"))
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", os.getenv("BOT_TOKEN", ""))

# Баланс умінь
SKILL_SLOT_MAX = 3           # максимум умінь у наборі для бою
SKILL_SELECT_INTERVAL = 5    # як часто пропонувати нове вміння (кожні N рівнів)

# ---- Локації ----
LOC_CITY = "Місто"
LOC_ROAD = "Тракт"
LOC_RUINS = "Руїни"
LOC_OLD_FOREST = "Старий ліс"
LOC_GUILD = "Гільдія авантюристів"
LOC_SHOP = "Крамниця (Місто)"  # окрема внутрішня локація міста

# Граф суміжності — що звідки доступно
ADJACENT = {
    LOC_GUILD: [LOC_CITY, LOC_ROAD],                                  # з гільдії -> тільки Місто/Тракт
    LOC_CITY: [LOC_ROAD, LOC_RUINS, LOC_OLD_FOREST, LOC_SHOP, LOC_GUILD],
    LOC_SHOP: [LOC_CITY],                                             # із крамниці — тільки назад у Місто
    LOC_ROAD: [LOC_CITY, LOC_RUINS, LOC_GUILD, LOC_OLD_FOREST],
    LOC_RUINS: [LOC_CITY, LOC_ROAD],
    LOC_OLD_FOREST: [LOC_CITY, LOC_ROAD],
}

# Дружній порядок відображення (не обов’язково)
LOCATION_ORDER = [LOC_CITY, LOC_ROAD, LOC_RUINS, LOC_OLD_FOREST, LOC_GUILD, LOC_SHOP]
