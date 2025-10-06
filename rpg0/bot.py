# -*- coding: utf-8 -*-
"""
Збирання Application і команд.
"""
import logging
import os
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, PicklePersistence, ContextTypes, filters,
)
from telegram.constants import ParseMode

from .config import BOT_DISPLAY_NAME, PERSIST_FILE, DEFAULT_LOCATION
from .models import ensure_player_ud, Enemy
from .handlers.registration import register, on_reg_action
from .handlers.battle import (
    CHOOSING_ACTION, ENEMY_TURN, LOOTING,
    on_battle_action, enemy_turn, after_loot, battle_keyboard
)
from .handlers.shop import shop, on_shop_action
from .handlers.travel import travel, on_travel_select
from .handlers.quest import quest, on_quest_action
from .handlers.inventory import inventory, on_inv_action
from .utils.loot import generate_loot

LOGGER = logging.getLogger("RPG")

def format_stats(p) -> str:
    inv_counts = {"⚪Звичайні": 0, "🟢Незвичайні": 0, "🔵Рідкісні": 0, "🟣Епічні": 0}
    for it in p.inventory:
        r = it.get("rarity", "common")
        if r == "common": inv_counts["⚪Звичайні"] += 1
        elif r == "uncommon": inv_counts["🟢Незвичайні"] += 1
        elif r == "rare": inv_counts["🔵Рідкісні"] += 1
        elif r == "epic": inv_counts["🟣Епічні"] += 1
        elif r == "legendary":
            inv_counts.setdefault("🟡Легендарні", 0)
            inv_counts["🟡Легендарні"] += 1
    inv_str = ", ".join([f"{k}:{v}" for k, v in inv_counts.items() if v]) or "порожньо"

    eq_short = []
    for slot in ("weapon", "armor", "accessory"):
        cur = p.equipment.get(slot)
        if cur:
            eq_short.append(f"{slot}:{cur['name']}")
    eq_str = ", ".join(eq_short) if eq_short else "немає"

    cls = f"\nКлас: {p.class_name}" if p.class_name else ""
    bs = f"\nПередісторія: {p.backstory}" if p.backstory else ""

    return (
        f"<b>{p.name}</b> — рівень {p.level}{cls}{bs}\n"
        f"HP: {p.hp}/{p.max_hp} | Атака: {p.atk} | Захист: {p.defense}\n"
        f"EXP: {p.exp}/{20 + (p.level - 1) * 10} | Зілля: {p.potions} | Золото: {p.gold}\n"
        f"🧩 Екіп: {eq_str}\n"
        f"🧰 Лут: {inv_str}"
    )

async def start(update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_ud(context.user_data)
    first = update.effective_user.first_name or "Мандрівник"
    welcome = (
        f"👋 {first}, вас вітає <b>{BOT_DISPLAY_NAME}</b> — покрокова RPG у сеттингу середньовічного фентезі!\n\n"
        "✨ Якщо ви вперше тут — зареєструйтесь у гільдії: /register\n\n"
        "Команди:\n"
        "/register — реєстрація в гільдії\n"
        "/newgame — почати нову гру\n"
        "/stats — характеристики героя\n"
        "/inventory — інвентар\n"
        "/explore — вирушити у пригоду\n"
        "/travel — локації\n"
        "/shop — крамниця\n"
        "/quest — квести\n"
        "/help — довідка"
    )
    await update.message.reply_html(welcome)

async def help_cmd(update, context):
    await update.message.reply_text("Питання? Напиши /start для списку команд.")

async def newgame(update, context):
    from .models import Player
    context.user_data["player"] = Player().asdict()
    await update.message.reply_html(
        "🆕 <b>Нова пригода розпочата!</b> Ваш герой створений. /register — щоб обрати клас."
    )

async def stats(update, context):
    p = ensure_player_ud(context.user_data)
    await update.message.reply_html(format_stats(p))

def get_location(ud):
    return ud.get("location", DEFAULT_LOCATION)

def spawn_enemy_for(p, location="Тракт") -> Enemy:
    tables = {
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
        "Гільдія авантюристів": [
            ("Сторож гільдії (спаринг)", 18, 6, 2, 8, 0),
        ],
    }
    import random
    name, base_hp, base_atk, base_def, exp, gold = random.choice(tables.get(location, tables["Тракт"]))
    hp = base_hp + (p.level - 1) * 4
    atk = base_atk + (p.level - 1)
    defense = base_def + (p.level // 3)
    exp_reward = exp + (p.level - 1) * 3
    gold_reward = gold + random.randint(0, p.level * 2)
    return Enemy(
        name=name, hp=hp, max_hp=hp, atk=atk, defense=defense,
        exp_reward=exp_reward, gold_reward=gold_reward
    )

async def explore(update, context):
    from telegram.ext import ConversationHandler
    p = ensure_player_ud(context.user_data)
    if not p.registered:
        await update.message.reply_html("Спершу зареєструйтесь у гільдії: /register")
        return ConversationHandler.END

    location = get_location(context.user_data)
    import random as R
    roll = R.random()
    if roll < 0.6:
        enemy = spawn_enemy_for(p, location)
        context.user_data["enemy"] = enemy.__dict__
        context.user_data["defending"] = False
        await update.message.reply_html(
            f"🔪 [{location}] Ви натрапили на <b>{enemy.name}</b>!\nHP ворога: {enemy.hp}/{enemy.max_hp}",
            reply_markup=battle_keyboard(True)
        )
        return CHOOSING_ACTION
    elif roll < 0.85:
        item = generate_loot(location)
        p.inventory.append(item)
        p.gold += item.get("gold", 0)
        context.user_data["player"] = p.asdict()
        extra = f" (+{item['gold']} золота)" if item.get("gold") else ""
        await update.message.reply_html(
            f"🧰 Знахідка у локації <b>{location}</b>: {item['emoji']} <b>{item['name']}</b> — {item['title']}{extra}!"
        )
        return ConversationHandler.END
    else:
        import random
        healed = min(p.max_hp - p.hp, random.randint(5, 12))
        p.hp += healed
        context.user_data["player"] = p.asdict()
        await update.message.reply_html(f"⛺ Відпочинок: +{healed} HP. Тепер {p.hp}/{p.max_hp}.")
        return ConversationHandler.END

async def on_unknown(update, context):
    await update.message.reply_text("Нерозпізнана команда. Спробуйте /help")

async def on_error(update, context):
    LOGGER.exception("Помилка в обробнику", exc_info=context.error)

def build_app() -> Application:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Не знайдено BOT_TOKEN у змінних оточення.")

    persistence = PicklePersistence(filepath=PERSIST_FILE)
    app = ApplicationBuilder().token(token).persistence(persistence).build()

    # Команди
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("newgame", newgame))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("inventory", inventory))
    app.add_handler(CommandHandler("shop", shop))
    app.add_handler(CommandHandler("travel", travel))
    app.add_handler(CommandHandler("quest", quest))
    app.add_handler(CommandHandler("register", register))

    # Інвентар callbacks
    app.add_handler(CallbackQueryHandler(on_inv_action, pattern=r"^inv:"))

    # Магазин callbacks
    app.add_handler(CallbackQueryHandler(on_shop_action, pattern=r"^shop:"))

    # Реєстрація callbacks
    app.add_handler(CallbackQueryHandler(on_reg_action, pattern=r"^reg:"))

    # Подорож callbacks
    app.add_handler(CallbackQueryHandler(on_travel_select, pattern=r"^travel:"))

    # Квести callbacks
    app.add_handler(CallbackQueryHandler(on_quest_action, pattern=r"^quest:"))

    # Битва як розмова
    battle_conv = ConversationHandler(
        entry_points=[CommandHandler("explore", explore)],
        states={
            CHOOSING_ACTION: [CallbackQueryHandler(on_battle_action)],
            ENEMY_TURN: [],
            LOOTING: [CallbackQueryHandler(after_loot)],
        },
        fallbacks=[CommandHandler("stats", stats)],
        name="battle_conv",
        persistent=True,
    )
    app.add_handler(battle_conv)

    # Unknown + errors
    app.add_handler(MessageHandler(filters.COMMAND, on_unknown))
    app.add_error_handler(on_error)
    return app
