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
1) pip install python-telegram-bot==20.*
2) BOT_TOKEN=...  (setx на Windows або export на Linux/macOS)
3) python telegram_rpg_bot.py

Локально працює Long Polling.
На Render — Webhook, якщо задано WEBHOOK_URL (root URL сервісу).
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
from dataclasses import dataclass, asdict
from typing import Dict, Any, Tuple  # Optional не потрібен

# Назва бота у повідомленнях (можна перевизначити змінною BOT_DISPLAY_NAME)
BOT_DISPLAY_NAME = os.getenv("BOT_DISPLAY_NAME", "RPG0")

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    PicklePersistence,
    filters,
)

# ----------------------------- ЛОГУВАННЯ -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOGGER = logging.getLogger("RPG")

# ----------------------------- КОНСТАНТИ СТАНІВ -----------------------------
CHOOSING_ACTION, ENEMY_TURN, LOOTING = range(3)

# ----------------------------- ДАТАКЛАСИ -----------------------------
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

    def is_alive(self) -> bool:
        return self.hp > 0

    def heal(self) -> int:
        if self.potions <= 0:
            return 0
        self.potions -= 1
        heal_amount = min(12, self.max_hp - self.hp)
        self.hp += heal_amount
        return heal_amount

    def gain_exp(self, amount: int) -> Tuple[int, bool]:
        """Повертає (новий рівень, чи відбувся ап)."""
        self.exp += amount
        leveled = False
        while self.exp >= self._exp_to_next():
            self.exp -= self._exp_to_next()
            self.level += 1
            leveled = True
            # Підвищення параметрів
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
def ensure_player(user_data: Dict[str, Any]) -> Player:
    if "player" not in user_data:
        user_data["player"] = asdict(Player())
    # Тримаємо у user_data словник (сумісність із PicklePersistence)
    p = dict_to_player(user_data["player"])
    user_data["player"] = asdict(p)
    return p

def dict_to_player(d: Dict[str, Any]) -> Player:
    return Player(**d)

def dict_to_enemy(d: Dict[str, Any]) -> Enemy:
    return Enemy(**d)

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
    return (
        f"<b>{p.name}</b> — рівень {p.level}\n"
        f"HP: {p.hp}/{p.max_hp} | Атака: {p.atk} | Захист: {p.defense}\n"
        f"EXP: {p.exp}/{20 + (p.level - 1) * 10} | Зілля: {p.potions} | Золото: {p.gold}"
    )

# ----------------------------- КОМАНДИ -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ensure_player(context.user_data)
    welcome = (
        f"👋 Вас вітає <b>{BOT_DISPLAY_NAME}</b> — покрокова RPG у сеттингу середньовічного фентезі!\n\n"
        "Команди:\n"
        "/newgame — почати нову гру (скидає прогрес)\n"
        "/stats — характеристики героя\n"
        "/inventory — інвентар\n"
        "/explore — вирушити у пригоду (шанси на бій/лут/подію)\n"
        "/help — довідка"
    )
    await update.message.reply_html(welcome)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Питання? Напиши /start для списку команд.")

async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["player"] = asdict(Player())
    await update.message.reply_html("🆕 <b>Нова пригода розпочата!</b> Ваш герой створений. Використайте /explore.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    p = ensure_player(context.user_data)
    await update.message.reply_html(format_stats(p))

async def inventory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    p = ensure_player(context.user_data)
    await update.message.reply_html(f"🎒 Інвентар:\n🧪 Зілля: {p.potions}\n💰 Золото: {p.gold}")

# ----------------------------- ДОСЛІДЖЕННЯ/ПРИГОДА -----------------------------
async def explore(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    p = ensure_player(context.user_data)

    roll = random.random()
    if roll < 0.6:
        # Битва
        enemy = spawn_enemy_for(p)
        context.user_data["enemy"] = enemy.__dict__
        context.user_data["defending"] = False
        await update.message.reply_html(
            f"🔪 Ви натрапили на <b>{enemy.name}</b>!\n"
            f"HP ворога: {enemy.hp}/{enemy.max_hp}",
            reply_markup=battle_keyboard(True),
        )
        return CHOOSING_ACTION
    elif roll < 0.85:
        # Лут
        gold = random.randint(5, 20)
        p.gold += gold
        context.user_data["player"] = asdict(p)
        await update.message.reply_html(f"🧰 Ви знайшли скриню з {gold} золотими монетами! Тепер у вас {p.gold}.")
        return ConversationHandler.END
    else:
        # Подія-відновлення
        heal = min(p.max_hp - p.hp, random.randint(5, 12))
        p.hp += heal
        context.user_data["player"] = asdict(p)
        await update.message.reply_html(f"⛺ Ви відпочили біля вогнища та відновили {heal} HP. Тепер {p.hp}/{p.max_hp}.")
        return ConversationHandler.END

# ----------------------------- БИТВА: ХОД ГРАВЦЯ -----------------------------
async def on_battle_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    p = dict_to_player(context.user_data.get("player"))
    e = dict_to_enemy(context.user_data.get("enemy"))

    action = query.data
    context.user_data["defending"] = False
    text = ""

    if action == "attack":
        dmg = roll_damage(p.atk, e.defense)
        e.hp -= dmg
        text = f"⚔️ Ви вдарили {e.name} на {dmg} шкоди."
    elif action == "defend":
        context.user_data["defending"] = True
        text = "🛡️ Ви у стійці захисту — шкода цього ходу по вам зменшена вдвічі."
    elif action == "skill":
        # Просте вміння: потужний удар (демо)
        dmg = roll_damage(p.atk + 3, e.defense)
        e.hp -= dmg
        text = f"✨ Ви застосували вміння: Потужний удар! {e.name} отримує {dmg} шкоди."
    elif action == "potion":
        healed = p.heal()
        context.user_data["player"] = asdict(p)
        if healed == 0:
            text = "🧪 Зілля відсутні або HP повне. Хід втрачено."
        else:
            text = f"🧪 Ви випили зілля та відновили {healed} HP. ({p.hp}/{p.max_hp})"
    elif action == "run":
        if random.random() < 0.5:
            await query.edit_message_text("🏃 Ви успішно втекли від бою.")
            return ConversationHandler.END
        else:
            text = "❌ Втекти не вдалося!"

    # Перевірка смерті ворога
    if e.hp <= 0:
        reward_exp = e.exp_reward
        reward_gold = e.gold_reward
        level, leveled = p.gain_exp(reward_exp)
        p.gold += reward_gold
        context.user_data["player"] = asdict(p)
        context.user_data.pop("enemy", None)
        summary = (
            f"💀 {e.name} переможений!\n"
            f"+{reward_exp} EXP, +{reward_gold} золота.\n"
        )
        if leveled:
            summary += f"⬆️ Рівень підвищено до {level}! HP/Атака/Захист зросли, HP відновлено до {p.max_hp}."
        await query.edit_message_text(
            text + "\n\n" + summary,
            reply_markup=battle_keyboard(in_battle=False),
        )
        return LOOTING

    # Оновлюємо ворога й переходимо до ходу ворога
    context.user_data["enemy"] = e.__dict__

    status = (
        f"<b>{p.name}</b> HP: {p.hp}/{p.max_hp}\n"
        f"<b>{e.name}</b> HP: {e.hp}/{e.max_hp}"
    )
    await query.edit_message_text(
        text + "\n\n" + status + "\n\nХід ворога...",
        parse_mode=ParseMode.HTML,
    )
    return await enemy_turn(update, context)

# ----------------------------- БИТВА: ХІД ВОРОГА -----------------------------
async def enemy_turn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    p = dict_to_player(context.user_data.get("player"))
    e = dict_to_enemy(context.user_data.get("enemy"))

    if not e.is_alive():
        return LOOTING

    # Імовірність особливої атаки 20%
    special = random.random() < 0.2
    atk = e.atk + (3 if special else 0)
    dmg = roll_damage(atk, p.defense)

    if context.user_data.get("defending"):
        dmg = max(1, dmg // 2)

    p.hp -= dmg
    context.user_data["player"] = asdict(p)

    action_text = (
        f"🧟‍♂️ {e.name} {'завдає критичної атаки' if special else 'б'є'} на {dmg} шкоди!\n"
        f"<b>{p.name}</b> HP: {p.hp}/{p.max_hp}\n"
        f"<b>{e.name}</b> HP: {e.hp}/{e.max_hp}"
    )

    if p.hp <= 0:
        context.user_data.pop("enemy", None)
        await update.effective_message.reply_html(
            action_text + "\n\n☠️ Ви загинули. Використайте /newgame, щоб розпочати спочатку."
        )
        return ConversationHandler.END

    await update.effective_message.reply_html(
        action_text + "\n\nВаш хід: оберіть дію.",
        reply_markup=battle_keyboard(True),
    )
    return CHOOSING_ACTION

# ----------------------------- ПОСТ-БИТВА -----------------------------
async def after_loot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("➡️ Продовжуємо пригоду! Використайте /explore.")
    else:
        await update.message.reply_text("➡️ Продовжуємо пригоду! Використайте /explore.")
    return ConversationHandler.END

# ----------------------------- ГЕНЕРАЦІЯ ВОРОГІВ -----------------------------
def spawn_enemy_for(p: Player) -> Enemy:
    # Прості шаблони ворогів, масштабовані за рівнем
    templates = [
        ("Гоблін-набігник", 18, 5, 1, 12, 10),
        ("Вовк лісовий", 20, 6, 2, 14, 12),
        ("Кістяний вартовий", 22, 7, 2, 16, 14),
        ("Розбійник тракту", 24, 8, 3, 18, 16),
        ("Орк-берсерк", 28, 9, 3, 22, 20),
        ("Рицар-відступник", 32, 10, 4, 26, 24),
    ]
    name, base_hp, base_atk, base_def, exp, gold = random.choice(templates)
    # Масштабування з рівнем
    hp = base_hp + (p.level - 1) * 4
    atk = base_atk + (p.level - 1)
    defense = base_def + (p.level // 3)
    exp_reward = exp + (p.level - 1) * 3
    gold_reward = gold + random.randint(0, p.level * 2)
    return Enemy(
        name=name, hp=hp, max_hp=hp, atk=atk, defense=defense,
        exp_reward=exp_reward, gold_reward=gold_reward
    )

# ----------------------------- MAIN -----------------------------
async def on_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Нерозпізнана команда. Спробуйте /help")

def build_app() -> Application:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Не знайдено BOT_TOKEN у змінних оточення.")

    persistence = PicklePersistence(filepath="rpgbot.pickle")
    app = ApplicationBuilder().token(token).persistence(persistence).build()

    # Статичні команди
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("newgame", newgame))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("inventory", inventory))

    # Дослідження/битва як розмова
    battle_conv = ConversationHandler(
        entry_points=[CommandHandler("explore", explore)],
        states={
            CHOOSING_ACTION: [CallbackQueryHandler(on_battle_action)],
            ENEMY_TURN: [],  # переходимо через enemy_turn()
            LOOTING: [CallbackQueryHandler(after_loot)],
        },
        fallbacks=[CommandHandler("stats", stats)],
        name="battle_conv",
        persistent=True,
    )
    app.add_handler(battle_conv)

    # Unknown
    app.add_handler(MessageHandler(filters.COMMAND, on_unknown))

    return app

async def main() -> None:
    app = build_app()

    webhook_url = os.getenv("WEBHOOK_URL")  # наприклад: https://your-app.onrender.com
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
