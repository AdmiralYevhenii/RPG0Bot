# telegram_rpg_bot.py
# -*- coding: utf-8 -*-
"""
Покрокова RPG-гра для Telegram на Python з використанням python-telegram-bot v20+.
Особливості:
- /start, /help, /newgame, /stats, /inventory, /explore (рандом події/битви)
- Пошаговий бій з кнопками: Атака, Захист, Вміння, Зілля, Втекти
- Збереження стану через PicklePersistence (файл rpgbot.pickle)
- Простий баланс і приклад розширюваної архітектури

Запуск:
1) Встановіть залежності:  pip install python-telegram-bot==20.*
2) Встановіть токен бота:  setx BOT_TOKEN "123:ABC"  (Windows) або  export BOT_TOKEN="123:ABC" (Linux/macOS)
3) Запустіть:  python telegram_rpg_bot.py

Порада: спочатку використовується Long Polling. Для продакшену на вебхуках додайте WebhookApp/Flask.
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    PicklePersistence,
    filters,
)

# Назва бота для відображення у повідомленнях
BOT_DISPLAY_NAME = os.getenv("BOT_DISPLAY_NAME", "RPG0")

# ----------------------------- ЛОГУВАННЯ -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOGGER = logging.getLogger("RPG")

# ----------------------------- КОНСТАНТИ СТАНІВ -----------------------------
CHOOSING_ACTION, ENEMY_TURN, LOOTING = range(3)

# ----------------------------- ДАТАКЛАСИ -----------------------------


def _get(data: Dict[str, Any], key: str, default: Any) -> Any:
    value = data.get(key, default)
    return default if value is None else value


@dataclass
class Player:
    name: str = "Мандрівник"
    level: int = 1
    exp: int = 0
    hp: int = 30
    max_hp: int = 30
    atk: int = 6
    defense: int = 2
    potions: int = 2
    gold: int = 0
    inventory: list[Dict[str, Any]] = field(default_factory=list)
    upgrades: Dict[str, int] = field(default_factory=dict)

    def is_alive(self) -> bool:
        return self.hp > 0

    def heal(self) -> int:
        if self.potions <= 0 or self.hp >= self.max_hp:
            return 0
        self.potions -= 1
        heal_amount = min(12, self.max_hp - self.hp)
        self.hp += heal_amount
        return heal_amount

    def gain_exp(self, amount: int) -> tuple[int, bool]:
        """Повертає (поточний рівень, чи стався ап)."""
        self.exp += amount
        leveled = False
        while self.exp >= self._exp_to_next():
            self.exp -= self._exp_to_next()
            self.level += 1
            leveled = True
            self.max_hp += 5
            self.atk += 2
            self.defense += 1
            self.hp = self.max_hp
        return self.level, leveled

    def _exp_to_next(self) -> int:
        return 20 + (self.level - 1) * 10


@dataclass
class Enemy:
    name: str
    hp: int
    max_hp: int
    atk: int
    defense: int
    exp_reward: int
    gold_reward: int

    def is_alive(self) -> bool:
        return self.hp > 0


# ----------------------------- УТИЛІТИ -----------------------------


def dict_to_player(data: Optional[Dict[str, Any]]) -> Player:
    if not data:
        return Player()
    return Player(
        name=_get(data, "name", Player.name),
        level=_get(data, "level", Player.level),
        exp=_get(data, "exp", Player.exp),
        hp=_get(data, "hp", Player.hp),
        max_hp=_get(data, "max_hp", Player.max_hp),
        atk=_get(data, "atk", Player.atk),
        defense=_get(data, "defense", Player.defense),
        potions=_get(data, "potions", Player.potions),
        gold=_get(data, "gold", Player.gold),
        inventory=list(_get(data, "inventory", [])),
        upgrades=dict(_get(data, "upgrades", {})),
    )


def dict_to_enemy(data: Optional[Dict[str, Any]]) -> Enemy:
    if not data:
        raise ValueError("Ворог не знайдений у даних користувача")
    return Enemy(
        name=data.get("name", "Невідомий ворог"),
        hp=data.get("hp", data.get("max_hp", 1)),
        max_hp=data.get("max_hp", data.get("hp", 1)),
        atk=data.get("atk", 1),
        defense=data.get("defense", 0),
        exp_reward=data.get("exp_reward", 5),
        gold_reward=data.get("gold_reward", 3),
    )


def ensure_player(user_data: Dict[str, Any]) -> Player:
    raw = user_data.get("player")
    player = dict_to_player(raw)
    user_data["player"] = asdict(player)
    return player


def roll_damage(atk: int, defense: int) -> int:
    base = max(0, atk - defense)
    variance = random.randint(-2, 2)
    dmg = max(1, base + variance)
    return dmg


def battle_keyboard(in_battle: bool = True) -> InlineKeyboardMarkup:
    if in_battle:
        buttons = [
            [InlineKeyboardButton("⚔️ Атака", callback_data="attack"),
             InlineKeyboardButton("🛡️ Захист", callback_data="defend")],
            [InlineKeyboardButton("✨ Вміння", callback_data="skill"),
             InlineKeyboardButton("🧪 Зілля", callback_data="potion")],
            [InlineKeyboardButton("🏃 Втекти", callback_data="run")],
        ]
    else:
        buttons = [[InlineKeyboardButton("➡️ Продовжити", callback_data="continue")]]
    return InlineKeyboardMarkup(buttons)


def format_stats(p: Player) -> str:
    inv_counts = {"⚪Звичайні": 0, "🟢Незвичайні": 0, "🔵Рідкісні": 0, "🟣Епічні": 0}
    for item in p.inventory:
        rarity = item.get("rarity", "common")
        if rarity == "common":
            inv_counts["⚪Звичайні"] += 1
        elif rarity == "uncommon":
            inv_counts["🟢Незвичайні"] += 1
        elif rarity == "rare":
            inv_counts["🔵Рідкісні"] += 1
        elif rarity == "epic":
            inv_counts["🟣Епічні"] += 1
    inv_str = ", ".join(f"{k}: {v}" for k, v in inv_counts.items() if v) or "порожньо"
    return (
        f"<b>{p.name}</b> — рівень {p.level}\n"
        f"HP: {p.hp}/{p.max_hp} | Атака: {p.atk} | Захист: {p.defense}\n"
        f"EXP: {p.exp}/{p._exp_to_next()} | Зілля: {p.potions} | Золото: {p.gold}\n"
        f"Інвентар: {inv_str}"
    )


# ----------------------------- КОМАНДИ -----------------------------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    player = ensure_player(context.user_data)
    welcome = (
        f"👋 Вас вітає <b>{BOT_DISPLAY_NAME}</b> — покрокова RPG у сеттингу середньовічного фентезі!\n\n"
        "Команди:\n"
        "• /newgame — почати спочатку\n"
        "• /stats — показати характеристики\n"
        "• /inventory — показати інвентар\n"
        "• /explore — вирушити на пригоду\n"
        "• /shop — торгова лавка\n"
        "• /travel — змінити локацію\n"
        "• /quest — взяти простий квест\n"
    )
    if update.message:
        await update.message.reply_html(welcome + "\n" + format_stats(player))


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Питання? Напишіть /start для списку команд.")


async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    player = Player()
    context.user_data["player"] = asdict(player)
    context.user_data.pop("enemy", None)
    context.user_data.pop("quest", None)
    await update.message.reply_html("🆕 <b>Нова пригода розпочата!</b> Використайте /explore.")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    player = ensure_player(context.user_data)
    await update.message.reply_html(format_stats(player))


async def inventory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    player = ensure_player(context.user_data)
    if not player.inventory:
        text = "🎒 Інвентар порожній."
    else:
        items = "\n".join(
            f"• {item['emoji']} {item['name']} ({item['title']})" for item in player.inventory
        )
        text = f"🎒 Інвентар:\n🧪 Зілля: {player.potions}\n💰 Золото: {player.gold}\n{items}"
    await update.message.reply_html(text)


# ----------------------------- ЛОКАЦІЇ ТА МАГАЗИН -----------------------------

LOCATIONS = ["Місто", "Тракт", "Руїни"]
SHOP_ITEMS = [
    {"id": "potion", "name": "Зілля лікування", "price": 12, "info": "Відновлює 12 HP"},
    {"id": "upgrade_weapon", "name": "Полірований клинок", "price": 30, "info": "+1 атака"},
]


async def travel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    buttons = [
        [InlineKeyboardButton(loc, callback_data=f"travel:{loc}")]
        for loc in LOCATIONS
    ]
    markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("Оберіть локацію для подорожі:", reply_markup=markup)


async def on_travel_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    _, location = query.data.split(":", 1)
    context.user_data["location"] = location
    await query.edit_message_text(f"🧭 Ви вирушили до локації <b>{location}</b>.", parse_mode=ParseMode.HTML)


async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    buttons = [
        [InlineKeyboardButton(f"Купити: {item['name']} — {item['price']} золота", callback_data=f"shop:{item['id']}")]
        for item in SHOP_ITEMS
    ]
    markup = InlineKeyboardMarkup(buttons)
    info = "\n".join(f"• {item['name']}: {item['info']}" for item in SHOP_ITEMS)
    await update.message.reply_html(f"🛒 <b>Лавка</b>:\n{info}", reply_markup=markup)


async def on_shop_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    item_id = query.data.split(":", 1)[1]
    player = ensure_player(context.user_data)

    item = next((it for it in SHOP_ITEMS if it["id"] == item_id), None)
    if not item:
        await query.edit_message_text("Товар не знайдено.")
        return

    if player.gold < item["price"]:
        await query.answer("Не вистачає золота", show_alert=True)
        return

    player.gold -= item["price"]
    if item_id == "potion":
        player.potions += 1
        feedback = "Ви купили зілля лікування."
    elif item_id == "upgrade_weapon":
        player.atk += 1
        player.upgrades["weapon"] = player.upgrades.get("weapon", 0) + 1
        feedback = "Ваш меч гостріший! Атака +1."
    else:
        feedback = "Товар додано до інвентарю."

    context.user_data["player"] = asdict(player)
    await query.edit_message_text(f"🛒 {feedback}\nЗалишок золота: {player.gold}")


# ----------------------------- КВЕСТ -----------------------------

QUESTS = {
    "hunt": {
        "title": "Полювання на гобліна",
        "reward_exp": 12,
        "reward_gold": 10,
    },
    "scout": {
        "title": "Розвідка руїн",
        "reward_exp": 16,
        "reward_gold": 14,
    },
}


async def quest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get("quest"):
        await update.message.reply_text("У вас вже є активний квест. Виконайте його під час бою!")
        return
    buttons = [
        [InlineKeyboardButton(data["title"], callback_data=f"quest:{qid}")]
        for qid, data in QUESTS.items()
    ]
    await update.message.reply_text(
        "Оберіть квест:", reply_markup=InlineKeyboardMarkup(buttons)
    )


async def on_quest_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    quest_id = query.data.split(":", 1)[1]
    quest_data = QUESTS.get(quest_id)
    if not quest_data:
        await query.edit_message_text("Квест не знайдено.")
        return
    context.user_data["quest"] = quest_id
    await query.edit_message_text(
        f"📜 Ви взяли квест: <b>{quest_data['title']}</b>. Перемагайте ворогів під час пригод!",
        parse_mode=ParseMode.HTML,
    )


# ----------------------------- ДОСЛІДЖЕННЯ/ПРИГОДА -----------------------------


def get_location(user_data: Dict[str, Any]) -> str:
    return user_data.get("location", "Тракт")


def spawn_enemy_for(player: Player, location: str = "Тракт") -> Enemy:
    tables: Dict[str, Iterable[tuple[str, int, int, int, int, int]]] = {
        "Місто": [
            ("П'яний хуліган", 18, 5, 1, 10, 8),
            ("Кишеньковий злодій", 20, 6, 2, 12, 12),
            ("Шибайголова", 22, 7, 2, 14, 14),
        ],
        "Тракт": [
            ("Гоблін-набігник", 18, 5, 1, 12, 10),
            ("Вовк лісовий", 20, 6, 2, 14, 12),
            ("Розбійник тракту", 24, 8, 3, 18, 16),
        ],
        "Руїни": [
            ("Кістяний вартовий", 22, 7, 2, 16, 14),
            ("Орк-берсерк", 28, 9, 3, 22, 20),
            ("Рицар-відступник", 32, 10, 4, 26, 24),
        ],
    }
    templates = list(tables.get(location, tables["Тракт"]))
    name, base_hp, base_atk, base_def, exp, gold = random.choice(templates)
    hp = base_hp + (player.level - 1) * 4
    atk = base_atk + (player.level - 1)
    defense = base_def + (player.level // 3)
    exp_reward = exp + (player.level - 1) * 3
    gold_reward = gold + random.randint(0, player.level * 2)
    return Enemy(
        name=name,
        hp=hp,
        max_hp=hp,
        atk=atk,
        defense=defense,
        exp_reward=exp_reward,
        gold_reward=gold_reward,
    )


def generate_loot(location: str) -> Dict[str, Any]:
    roll = random.random()
    if roll < 0.60:
        rarity, title, emoji, gold = "common", "⚪ Звичайний", "⚪", random.randint(3, 8)
    elif roll < 0.85:
        rarity, title, emoji, gold = "uncommon", "🟢 Незвичайний", "🟢", random.randint(6, 14)
    elif roll < 0.97:
        rarity, title, emoji, gold = "rare", "🔵 Рідкісний", "🔵", random.randint(10, 22)
    else:
        rarity, title, emoji, gold = "epic", "🟣 Епічний", "🟣", random.randint(18, 35)

    names_by_loc = {
        "Місто": ["Кишеньковий амулет", "Гільдійський жетон", "Срібний перстень"],
        "Тракт": ["Моховитий талісман", "Клинок мандрівника", "Шкіряний тубус"],
        "Руїни": ["Осколок руни", "Іржавий герб", "Кістяний оберіг"],
    }
    name = random.choice(names_by_loc.get(location, names_by_loc["Тракт"]))
    return {"name": name, "rarity": rarity, "title": title, "emoji": emoji, "gold": gold}


async def explore(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    player = ensure_player(context.user_data)
    location = get_location(context.user_data)

    roll = random.random()
    if roll < 0.6:
        enemy = spawn_enemy_for(player, location)
        context.user_data["enemy"] = asdict(enemy)
        context.user_data["defending"] = False
        if update.message:
            await update.message.reply_html(
                f"🔪 [{location}] Ви натрапили на <b>{enemy.name}</b>!\n"
                f"HP ворога: {enemy.hp}/{enemy.max_hp}",
                reply_markup=battle_keyboard(True),
            )
        return CHOOSING_ACTION
    elif roll < 0.85:
        item = generate_loot(location)
        player.inventory.append(item)
        player.gold += item.get("gold", 0)
        context.user_data["player"] = asdict(player)
        extra = f" (+{item['gold']} золота)" if item.get("gold") else ""
        if update.message:
            await update.message.reply_html(
                f"🧰 Знахідка у локації <b>{location}</b>: {item['emoji']} <b>{item['name']}</b> — {item['title']}{extra}!"
            )
        return ConversationHandler.END
    else:
        heal = min(player.max_hp - player.hp, random.randint(5, 12))
        player.hp += heal
        context.user_data["player"] = asdict(player)
        if update.message:
            await update.message.reply_html(
                f"⛺ Ви відпочили біля вогнища та відновили {heal} HP. Тепер {player.hp}/{player.max_hp}."
            )
        return ConversationHandler.END


# ----------------------------- БИТВА: ХІД ГРАВЦЯ -----------------------------


async def on_battle_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    player = dict_to_player(context.user_data.get("player"))
    enemy = dict_to_enemy(context.user_data.get("enemy"))

    action = query.data
    context.user_data["defending"] = False
    text = ""

    if action == "attack":
        dmg = roll_damage(player.atk, enemy.defense)
        enemy.hp -= dmg
        text = f"⚔️ Ви вдарили {enemy.name} на {dmg} шкоди."
    elif action == "defend":
        context.user_data["defending"] = True
        text = "🛡️ Ви у стійці захисту — шкода цього ходу по вам зменшена вдвічі."
    elif action == "skill":
        dmg = roll_damage(player.atk + 3, enemy.defense)
        enemy.hp -= dmg
        text = f"✨ Ви застосували вміння: Потужний удар! {enemy.name} отримує {dmg} шкоди."
    elif action == "potion":
        healed = player.heal()
        if healed == 0:
            text = "🧪 Зілля відсутні або HP повне. Хід втрачено."
        else:
            text = f"🧪 Ви випили зілля та відновили {healed} HP. ({player.hp}/{player.max_hp})"
    elif action == "run":
        if random.random() < 0.5:
            await query.edit_message_text("🏃 Ви успішно втекли від бою.")
            context.user_data.pop("enemy", None)
            context.user_data["player"] = asdict(player)
            return ConversationHandler.END
        text = "❌ Втекти не вдалося!"

    if not enemy.is_alive():
        reward_exp = enemy.exp_reward
        reward_gold = enemy.gold_reward
        level_before = player.level
        level, leveled = player.gain_exp(reward_exp)
        player.gold += reward_gold
        quest_id = context.user_data.pop("quest", None)
        if quest_id:
            quest_data = QUESTS.get(quest_id)
            if quest_data:
                player.gold += quest_data["reward_gold"]
                player.exp += quest_data["reward_exp"]
                level, leveled2 = player.gain_exp(0)
                leveled = leveled or leveled2
                text += (
                    "\n\n📜 Квест виконано! Нагорода: "
                    f"+{quest_data['reward_exp']} EXP, +{quest_data['reward_gold']} золота."
                )
        context.user_data["player"] = asdict(player)
        context.user_data.pop("enemy", None)
        summary = (
            f"💀 {enemy.name} переможений!\n"
            f"+{reward_exp} EXP, +{reward_gold} золота.\n"
        )
        if leveled:
            summary += (
                f"⬆️ Рівень підвищено до {level}! HP/Атака/Захист зросли, HP відновлено до {player.max_hp}."
            )
        await query.edit_message_text(
            text + "\n\n" + summary,
            reply_markup=battle_keyboard(in_battle=False),
            parse_mode=ParseMode.HTML,
        )
        return LOOTING

    context.user_data["enemy"] = asdict(enemy)
    context.user_data["player"] = asdict(player)

    status = (
        f"<b>{player.name}</b> HP: {player.hp}/{player.max_hp}\n"
        f"<b>{enemy.name}</b> HP: {enemy.hp}/{enemy.max_hp}"
    )
    await query.edit_message_text(
        text + "\n\n" + status + "\n\nХід ворога...",
        parse_mode=ParseMode.HTML,
    )
    return await enemy_turn(update, context)


# ----------------------------- БИТВА: ХІД ВОРОГА -----------------------------


async def enemy_turn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    player = dict_to_player(context.user_data.get("player"))
    enemy = dict_to_enemy(context.user_data.get("enemy"))

    if not enemy.is_alive():
        return LOOTING

    special = random.random() < 0.2
    atk = enemy.atk + (3 if special else 0)
    dmg = roll_damage(atk, player.defense)

    if context.user_data.get("defending"):
        dmg = max(1, dmg // 2)

    player.hp -= dmg
    context.user_data["player"] = asdict(player)

    if player.hp <= 0:
        context.user_data.pop("enemy", None)
        await update.callback_query.edit_message_text(
            f"💀 {enemy.name} завдає {dmg} шкоди. Ви повалені...",
            parse_mode=ParseMode.HTML,
        )
        return ConversationHandler.END

    text = f"{enemy.name} завдає {dmg} шкоди." + (" Особлива атака!" if special else "")
    status = (
        f"<b>{player.name}</b> HP: {player.hp}/{player.max_hp}\n"
        f"<b>{enemy.name}</b> HP: {enemy.hp}/{enemy.max_hp}"
    )
    await update.callback_query.edit_message_text(
        text + "\n\n" + status,
        parse_mode=ParseMode.HTML,
        reply_markup=battle_keyboard(True),
    )
    return CHOOSING_ACTION


# ----------------------------- ПІСЛЯ ЛУТУ -----------------------------


async def after_loot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("➡️ Продовжуємо пригоду! Використайте /explore.")
    return ConversationHandler.END


# ----------------------------- UNKNOWN -----------------------------


async def on_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Нерозпізнана команда. Спробуйте /help")


# ----------------------------- APP BUILDER -----------------------------


def build_app() -> Application:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Не знайдено BOT_TOKEN у змінних оточення.")

    persistence = PicklePersistence(filepath="rpgbot.pickle")
    app = ApplicationBuilder().token(token).persistence(persistence).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("newgame", newgame))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("inventory", inventory))
    app.add_handler(CommandHandler("shop", shop))
    app.add_handler(CommandHandler("travel", travel))
    app.add_handler(CommandHandler("quest", quest))

    battle_conv = ConversationHandler(
        entry_points=[CommandHandler("explore", explore)],
        states={
            CHOOSING_ACTION: [CallbackQueryHandler(on_battle_action)],
            ENEMY_TURN: [],
            LOOTING: [CallbackQueryHandler(after_loot, pattern="^continue$")],
        },
        fallbacks=[CommandHandler("stats", stats)],
        name="battle_conv",
        persistent=True,
    )
    app.add_handler(battle_conv)

    app.add_handler(CallbackQueryHandler(on_shop_action, pattern=r"^shop:"))
    app.add_handler(CallbackQueryHandler(on_travel_select, pattern=r"^travel:"))
    app.add_handler(CallbackQueryHandler(on_quest_action, pattern=r"^quest:"))

    app.add_handler(MessageHandler(filters.COMMAND, on_unknown))

    return app


async def main() -> None:
    app = build_app()

    webhook_url = os.getenv("WEBHOOK_URL")
    port = int(os.getenv("PORT", "10000"))
    url_path = os.getenv("WEBHOOK_PATH", os.getenv("BOT_TOKEN"))

    if webhook_url:
        LOGGER.info("RPG Bot: режим Webhook (Render)...")
        await app.initialize()
        await app.start()
        try:
            await app.run_webhook(
                listen="0.0.0.0",
                port=port,
                url_path=url_path,
                webhook_url=f"{webhook_url.rstrip('/')}/{url_path}",
                drop_pending_updates=True,
            )
        finally:
            await app.stop()
            await app.shutdown()
    else:
        LOGGER.info("RPG Bot: режим Long Polling (локально)...")
        await app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Зупинено.")
