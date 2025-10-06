# -*- coding: utf-8 -*-
"""
Бій (ConversationHandler): атака/захист/вміння/зілля/втекти, статуси, ініціатива.
"""
import random
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, CommandHandler
from ..models import ensure_player_ud, dict_to_enemy, Enemy
from ..utils.equipment import damage_durability_on_hit
from ..config import BLEED_TURNS, STUN_TURNS

CHOOSING_ACTION, ENEMY_TURN, LOOTING = range(3)

def battle_keyboard(in_battle: bool = True) -> InlineKeyboardMarkup:
    if in_battle:
        buttons = [
            [InlineKeyboardButton("⚔️ Атака", callback_data="battle:attack"),
             InlineKeyboardButton("🛡️ Захист", callback_data="battle:defend")],
            [InlineKeyboardButton("✨ Вміння", callback_data="battle:skill"),
             InlineKeyboardButton("🧪 Зілля", callback_data="battle:potion")],
            [InlineKeyboardButton("🏃 Втекти", callback_data="battle:run")],
        ]
    else:
        buttons = [[InlineKeyboardButton("➡️ Продовжити", callback_data="battle:continue")]]
    return InlineKeyboardMarkup(buttons)

def roll_damage(atk: int, defense: int) -> int:
    base = max(1, atk - defense + random.randint(-2, 2))
    return base

async def explore_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Викликається з /explore у зовнішньому модулі — тут лише клавіатура, все інше робиться там."""
    # резерв, якщо треба
    return ConversationHandler.END

async def on_battle_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    p = ensure_player_ud(context.user_data)
    e = dict_to_enemy(context.user_data.get("enemy"))

    data = q.data.split(":",1)[1]
    context.user_data["defending"] = False
    txt = ""

    if data == "attack":
        dmg, crit = p.roll_player_attack(e.defense)
        e.hp -= dmg
        damage_durability_on_hit(p)
        txt = f"⚔️ Ви вдарили {e.name} на {dmg} шкоди." + (" <b>Крит!</b>" if crit else "")
    elif data == "defend":
        context.user_data["defending"] = True
        txt = "🛡️ Ви в стійці захисту — отримана шкода цього ходу зменшена."
    elif data == "skill":
        # поки що простий шаблон: якщо є слотові навички — додаємо +3 атаки
        dmg, crit = p.roll_player_attack(e.defense)
        bonus = 3 if p.slotted_skills else 0
        e.hp -= (dmg + bonus)
        damage_durability_on_hit(p)
        txt = f"✨ Ви застосували вміння! {e.name} отримує {dmg + bonus} шкоди."
    elif data == "potion":
        healed = p.heal()
        context.user_data["player"] = p.asdict()
        if healed == 0:
            txt = "🧪 Зілля відсутні або HP повне. Хід втрачено."
        else:
            txt = f"🧪 Ви випили зілля та відновили {healed} HP. ({p.hp}/{p.max_hp})"
    elif data == "run":
        if random.random() < 0.5:
            await q.edit_message_text("🏃 Ви успішно втекли від бою.")
            context.user_data.pop("enemy", None)
            return ConversationHandler.END
        else:
            txt = "❌ Втекти не вдалося!"
    elif data == "continue":
        await q.edit_message_text("➡️ Продовжуємо пригоду! Використайте /explore.")
        return ConversationHandler.END

    # Перевірка смерті ворога
    if e.hp <= 0:
        reward_exp = e.exp_reward; reward_gold = e.gold_reward
        lvl_before = p.level
        level, leveled = p.gain_exp(reward_exp)
        p.gold += reward_gold
        context.user_data["player"] = p.asdict()
        context.user_data.pop("enemy", None)
        summary = f"💀 {e.name} переможений!\n+{reward_exp} EXP, +{reward_gold} золота.\n"
        if leveled:
            summary += f"⬆️ Рівень підвищено до {level}! Параметри зросли, HP відновлено до {p.max_hp}.\n"
        await q.edit_message_text(txt + "\n\n" + summary, reply_markup=battle_keyboard(False), parse_mode=ParseMode.HTML)
        return LOOTING

    # Оновимо ворога і хід ворога
    context.user_data["enemy"] = e.__dict__
    status = f"<b>{p.name}</b> HP: {p.hp}/{p.max_hp}\n<b>{e.name}</b> HP: {e.hp}/{e.max_hp}"
    await q.edit_message_text(txt + "\n\n" + status + "\n\nХід ворога...", parse_mode=ParseMode.HTML)
    return await enemy_turn(update, context)

async def enemy_turn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    p = ensure_player_ud(context.user_data)
    e = dict_to_enemy(context.user_data.get("enemy"))

    if not e.is_alive():
        return LOOTING

    special = random.random() < 0.2
    atk = e.atk + (3 if special else 0)
    dmg = roll_damage(atk, p.defense)
    if context.user_data.get("defending"):
        dmg = max(1, dmg // 2)

    p.hp -= dmg
    context.user_data["player"] = p.asdict()

    act = "завдає критичної атаки" if special else "б'є"
    text = (f"🧟‍♂️ {e.name} {act} на {dmg} шкоди!\n"
            f"<b>{p.name}</b> HP: {p.hp}/{p.max_hp}\n<b>{e.name}</b> HP: {e.hp}/{e.max_hp}")

    if p.hp <= 0:
        context.user_data.pop("enemy", None)
        await update.effective_message.reply_html(text + "\n\n☠️ Ви загинули. /newgame — щоб почати спочатку.")
        return ConversationHandler.END

    await update.effective_message.reply_html(text + "\n\nВаш хід: оберіть дію.", reply_markup=battle_keyboard(True))
    return CHOOSING_ACTION

async def after_loot(update, context):
    q = update.callback_query
    if q:
        await q.answer()
        await q.edit_message_text("➡️ Продовжуємо пригоду! Використайте /explore.")
    else:
        await update.message.reply_text("➡️ Продовжуємо пригоду! Використайте /explore.")
    return ConversationHandler.END
