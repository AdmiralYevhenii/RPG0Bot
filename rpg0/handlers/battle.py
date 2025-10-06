# -*- coding: utf-8 -*-
from __future__ import annotations

import random
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler

from ..models import dict_to_player, dict_to_enemy

# Стани розмови
CHOOSING_ACTION, ENEMY_TURN, LOOTING = range(3)


# ----- Кубики -----

def roll_damage(atk: int, defense: int) -> int:
    base = max(0, atk - defense)
    variance = random.randint(-2, 2)
    return max(1, base + variance)

def roll_player_attack(atk: int, defense: int) -> tuple[int, bool]:
    crit = random.random() < 0.15
    dmg = roll_damage(atk, defense)
    if crit:
        dmg *= 2
    return dmg, crit


# ----- Клавіатура -----

def battle_keyboard(p=None, in_battle: bool = True, battle_state: dict | None = None) -> InlineKeyboardMarkup:
    """
    Під час бою всі callback_data мають префікс 'battle:'.
    Після бою повертаємо одну кнопку 'continue' (без префікса) — її ловить LOOTING handler з pattern="^continue$".
    """
    if not in_battle:
        return InlineKeyboardMarkup([[InlineKeyboardButton("➡️ Продовжити", callback_data="continue")]])

    rows = [
        [
            InlineKeyboardButton("⚔️ Атака",  callback_data="battle:attack"),
            InlineKeyboardButton("🛡️ Захист", callback_data="battle:defend"),
        ],
        [
            InlineKeyboardButton("🧪 Зілля",  callback_data="battle:potion"),
            InlineKeyboardButton("🏃 Втекти", callback_data="battle:run"),
        ],
    ]

    # Кнопки умінь із КД (до 3), усі з префіксом battle:
    if p:
        cds = (battle_state or {}).get("cooldowns", {})
        line = []
        for name in (getattr(p, "skills_loadout", []) or [])[:3]:
            cd = cds.get(name, 0)
            label = f"✨ {name}{' ['+str(cd)+']' if cd > 0 else ''}"
            line.append(InlineKeyboardButton(label, callback_data=f"battle:skill:{name}"))
            if len(line) == 2:
                rows.append(line)
                line = []
        if line:
            rows.append(line)

    return InlineKeyboardMarkup(rows)


# ----- Хід гравця -----

async def on_battle_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    p = dict_to_player(context.user_data.get("player"))
    e = dict_to_enemy(context.user_data.get("enemy"))
    battle_state = context.user_data.setdefault("battle", {"cooldowns": {}, "e_status": {}, "p_status": {}})

    data = query.data  # "battle:attack" / "battle:defend" / "battle:skill:<name>" / "battle:potion" / "battle:run"
    parts = data.split(":", 2)
    action = parts[1] if len(parts) > 1 else data

    context.user_data["defending"] = False
    text = ""

    if action == "attack":
        from ..utils.skills import consume_player_temp_buffs, turn_tick_cooldowns
        atk_b, _ = consume_player_temp_buffs(p, battle_state)
        dmg, crit = roll_player_attack(p.atk + atk_b, e.defense)
        e.hp -= dmg
        text = f"⚔️ Ви вдарили {e.name} на {dmg} шкоди." + (" <b>Крит!</b>" if crit else "")
        turn_tick_cooldowns(battle_state)

    elif action == "defend":
        context.user_data["defending"] = True
        text = "🛡️ Ви у стійці захисту — шкода цього ходу по вам зменшена вдвічі."
        from ..utils.skills import turn_tick_cooldowns
        turn_tick_cooldowns(battle_state)

    elif action == "skill":
        sname = parts[2] if len(parts) > 2 else ""
        from ..utils.skills import apply_skill, turn_tick_cooldowns
        text = apply_skill(p, e, sname, battle_state)
        turn_tick_cooldowns(battle_state)

    elif action == "potion":
        healed = p.heal()
        context.user_data["player"] = p.asdict()
        if healed == 0:
            text = "🧪 Зілля відсутні або HP повне. Хід втрачено."
        else:
            text = f"🧪 Ви випили зілля та відновили {healed} HP. ({p.hp}/{p.max_hp})"
        from ..utils.skills import turn_tick_cooldowns
        turn_tick_cooldowns(battle_state)

    elif action == "run":
        if random.random() < 0.5:
            # Скидаємо стан бою
            context.user_data.pop("enemy", None)
            context.user_data.pop("battle", None)
            await query.edit_message_text("🏃 Ви успішно втекли від бою.")
            return ConversationHandler.END
        else:
            text = "❌ Втекти не вдалося!"
            from ..utils.skills import turn_tick_cooldowns
            turn_tick_cooldowns(battle_state)

    # Перевірка смерті ворога
    if e.hp <= 0:
        reward_exp = e.exp_reward
        reward_gold = e.gold_reward
        level, leveled = p.gain_exp(reward_exp)
        p.gold += reward_gold

        context.user_data["player"] = p.asdict()
        context.user_data.pop("enemy", None)
        context.user_data.pop("battle", None)  # закриваємо стан бою

        summary = f"💀 {e.name} переможений!\n+{reward_exp} EXP, +{reward_gold} золота.\n"
        if leveled:
            summary += f"⬆️ Рівень підвищено до {level}! HP/Атака/Захист зросли, HP відновлено до {p.max_hp}."
            if getattr(p, "pending_skill_choice", False):
                summary += "\n🆕 Доступний вибір нового вміння у Гільдії (/guild)."

        await query.edit_message_text(
            text + "\n\n" + summary,
            reply_markup=battle_keyboard(in_battle=False),
            parse_mode=ParseMode.HTML,
        )
        return LOOTING

    # Оновити ворога, перейти до ходу ворога
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


# ----- Хід ворога -----

async def enemy_turn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    p = dict_to_player(context.user_data.get("player"))
    e = dict_to_enemy(context.user_data.get("enemy"))
    battle_state = context.user_data.setdefault("battle", {"cooldowns": {}, "e_status": {}, "p_status": {}})

    if not e.is_alive():
        return LOOTING

    # Ефекти на початку ходу ворога
    from ..utils.skills import apply_start_of_enemy_turn_effects, enemy_is_stunned, turn_tick_cooldowns
    start_txt = apply_start_of_enemy_turn_effects(e, battle_state)
    if not e.is_alive():
        context.user_data["enemy"] = e.__dict__
        turn_tick_cooldowns(battle_state)
        await update.effective_message.reply_html(
            (start_txt + "\n" if start_txt else "") + "Ворог стік кров’ю та впав!",
            reply_markup=battle_keyboard(in_battle=False),
        )
        return LOOTING

    if enemy_is_stunned(battle_state):
        context.user_data["enemy"] = e.__dict__
        turn_tick_cooldowns(battle_state)
        await update.effective_message.reply_html(
            (start_txt + "\n" if start_txt else "") + f"😵 {e.name} оглушений і пропускає хід!\n\nВаш хід:",
            reply_markup=battle_keyboard(p, True, battle_state),
        )
        return CHOOSING_ACTION

    # Базова атака ворога
    special = random.random() < 0.2
    atk = e.atk + (3 if special else 0)

    # Врахувати тимчасовий баф захисту гравця (від умінь/стійки)
    pst = battle_state.setdefault("p_status", {})
    def_up_val = pst.get("def_up_val", 0) if pst.get("def_up") else 0

    dmg = roll_damage(atk, max(0, p.defense + def_up_val))
    if context.user_data.get("defending"):
        dmg = max(1, dmg // 2)

    p.hp -= dmg
    context.user_data["player"] = p.asdict()
    context.user_data["enemy"] = e.__dict__

    # Баф захисту спрацьовує на один вхідний удар і гаситься
    pst["def_up"] = 0
    pst["def_up_val"] = 0

    action_text = (
        (start_txt + "\n" if start_txt else "") +
        f"🧟‍♂️ {e.name} {'завдає критичної атаки' if special else 'б\'є'} на {dmg} шкоди!\n"
        f"<b>{p.name}</b> HP: {p.hp}/{p.max_hp}\n"
        f"<b>{e.name}</b> HP: {e.hp}/{e.max_hp}"
    )

    if p.hp <= 0:
        context.user_data.pop("enemy", None)
        context.user_data.pop("battle", None)
        await update.effective_message.reply_html(
            action_text + "\n\n☠️ Ви загинули. /newgame — щоб розпочати спочатку."
        )
        return ConversationHandler.END

    # Кінець ходу ворога: тік КД
    from ..utils.skills import turn_tick_cooldowns
    turn_tick_cooldowns(battle_state)

    await update.effective_message.reply_html(
        action_text + "\n\nВаш хід: оберіть дію.",
        reply_markup=battle_keyboard(p, True, battle_state),
    )
    return CHOOSING_ACTION


# ----- Пост-битва -----

async def after_loot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("➡️ Продовжуємо пригоду! Використайте /explore.")
    else:
        await update.message.reply_text("➡️ Продовжуємо пригоду! Використайте /explore.")
    return ConversationHandler.END
