# -*- coding: utf-8 -*-
from __future__ import annotations

import random
from typing import Tuple

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler

from ..models import dict_to_player, dict_to_enemy
from ..utils.loot import generate_loot
from ..utils.skills import (
    apply_skill,
    turn_tick_cooldowns,
    apply_start_of_enemy_turn_effects,
    enemy_is_stunned,
    consume_player_temp_buffs,
    clear_player_def_buff_after_enemy_turn,
)

# Стани розмови
CHOOSING_ACTION, ENEMY_TURN, LOOTING = range(3)

# ----- Кубики -----

def roll_damage(atk: int, defense: int) -> int:
    """Базовий підрахунок шкоди: (atk - def) з невеликою варіацією, мінімум 1."""
    base = max(0, atk - defense)
    variance = random.randint(-2, 2)
    return max(1, base + variance)

def roll_player_attack(atk: int, defense: int) -> Tuple[int, bool]:
    """Атака гравця з 15% критом (×2)."""
    crit = random.random() < 0.15
    dmg = roll_damage(atk, defense)
    if crit:
        dmg *= 2
    return dmg, crit


# ----- Допоміжні рендери та клавіатури -----

def _render_battle_header(p, e) -> str:
    return (
        f"⚔️ <b>БІЙ</b>\n"
        f"👤 Ви: {p.name} — HP {p.hp}/{p.max_hp} | ATK {p.atk} DEF {p.defense}\n"
        f"👹 Ворог: {e.name} — HP {e.hp}/{e.max_hp} | ATK {e.atk} DEF {e.defense}\n"
    )

def _skill_cd_label(bstate: dict, name: str) -> str:
    cd = bstate.setdefault("cooldowns", {}).get(name, 0) or 0
    return f"✨ {name} (КД {int(cd)})" if cd > 0 else f"✨ {name}"

def battle_keyboard(p=None, in_battle: bool = True, battle_state: dict | None = None) -> InlineKeyboardMarkup:
    """
    Головна бойова клавіатура. Показує до 3х умінь з лоадауту гравця з КД.
    """
    rows = [
        [InlineKeyboardButton("🗡️ Атака", callback_data="battle:attack")],
        [InlineKeyboardButton("🛡️ Захист", callback_data="battle:defend")],
        [InlineKeyboardButton("🧪 Зілля", callback_data="battle:potion")],
        [InlineKeyboardButton("🏃 Втекти", callback_data="battle:run")],
    ]

    if p is not None:
        load = list(getattr(p, "skills_loadout", []) or [])[:3]
        if load:
            skill_buttons = []
            for name in load:
                label = _skill_cd_label(battle_state or {}, name)
                skill_buttons.append([InlineKeyboardButton(label, callback_data=f"battle:skill:{name}")])
            # Вставимо блок умінь на друге місце, щоб були одразу під атакою
            rows = [rows[0]] + skill_buttons + rows[1:]

    return InlineKeyboardMarkup(rows)


# ----- Головний хендлер дій гравця -----

async def on_battle_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обробляє всі callback'и 'battle:*' у хід гравця.
    ПІСЛЯ КОЖНОЇ ДІЇ ГРАВЦЯ переходимо в enemy_turn(update, context),
    де В КІНЦІ відбудеться ЄДИНИЙ тік кулдаунів.
    """
    q = update.callback_query
    data = q.data if q else None
    if q:
        await q.answer()

    p = dict_to_player(context.user_data.get("player"))
    e = dict_to_enemy(context.user_data.get("enemy"))
    b = context.user_data.setdefault("battle_state", {})

    header = _render_battle_header(p, e)

    if not data or not data.startswith("battle:"):
        # Невідомо — просто оновимо основне меню
        kb = battle_keyboard(p, True, b)
        if q:
            await q.edit_message_text(header + "\nВаш хід — оберіть дію.", parse_mode=ParseMode.HTML, reply_markup=kb)
        else:
            await update.message.reply_html(header + "\nВаш хід — оберіть дію.", reply_markup=kb)
        return CHOOSING_ACTION

    _, action, *rest = data.split(":", 2)

    # ---- Атака ----
    if action == "attack":
        atk_b, _def_b = consume_player_temp_buffs(p, b)
        dmg, crit = roll_player_attack(p.atk + atk_b, e.defense)
        e.hp -= dmg
        context.user_data["player"] = p.asdict()
        context.user_data["enemy"] = e.asdict()

        text = header + f"\n🗡️ Ви атакуєте ворога та завдаєте {dmg} шкоди{' (КРИТ!)' if crit else ''}."

        # Перевірка смерті ворога від удару гравця
        if e.hp <= 0:
            return await _on_enemy_defeated(update, context, text)

        # ПЕРЕХІД НА ХІД ВОРОГА (без тіку КД тут)
        context.user_data["last_log"] = text
        return await enemy_turn(update, context)

    # ---- Захист ----
    if action == "defend":
        pst = b.setdefault("p_status", {})
        pst["def_up"] = 1
        pst["def_up_val"] = max(2, int(p.level / 2) + 1)
        context.user_data["battle_state"] = b

        text = header + f"\n🛡️ Ви займаєте оборонну стійку: +{pst['def_up_val']} до захисту на цей раунд."
        context.user_data["last_log"] = text
        return await enemy_turn(update, context)

    # ---- Зілля ----
    if action == "potion":
        healed = min(p.max_hp - p.hp, 8)
        p.hp += healed
        context.user_data["player"] = p.asdict()

        text = header + f"\n🧪 Ви випиваєте зілля та відновлюєте {healed} HP."
        context.user_data["last_log"] = text
        return await enemy_turn(update, context)

    # ---- Втеча ----
    if action == "run":
        if random.random() < 0.5:
            msg = header + "\n🏃 Ви успішно втекли з бою."
            if q:
                await q.edit_message_text(msg, parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_html(msg)
            return ConversationHandler.END
        else:
            text = header + "\n🏃 Спроба втечі невдала!"
            context.user_data["last_log"] = text
            return await enemy_turn(update, context)

    # ---- Уміння ----
    if action == "skill":
        skill_name = (rest[0] if rest else "").strip()
        if not skill_name:
            # Якщо натиснули кнопку без назви (не повинно статись) — повертаємося до меню
            kb = battle_keyboard(p, True, b)
            if q:
                await q.edit_message_text(header + "\nВаш хід — оберіть дію.", parse_mode=ParseMode.HTML, reply_markup=kb)
            else:
                await update.message.reply_html(header + "\nВаш хід — оберіть дію.", reply_markup=kb)
            return CHOOSING_ACTION

        # Перевірка: чи в лоадауті
        load = list(getattr(p, "skills_loadout", []) or [])
        if skill_name not in load:
            txt = header + "\nЦе уміння не входить до вашого активного набору."
            kb = battle_keyboard(p, True, b)
            if q:
                await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
            else:
                await update.message.reply_html(txt, reply_markup=kb)
            return CHOOSING_ACTION

        # Виконуємо уміння (ставить КД всередині)
        effect_text = apply_skill(p, e, skill_name, b)
        context.user_data["player"] = p.asdict()
        context.user_data["enemy"] = e.asdict()
        context.user_data["battle_state"] = b

        text = header + f"\n{effect_text}"

        # Якщо ворог помер одразу
        if e.hp <= 0:
            return await _on_enemy_defeated(update, context, text)

        # ПЕРЕХІД НА ХІД ВОРОГА (без тіку КД тут)
        context.user_data["last_log"] = text
        return await enemy_turn(update, context)

    # Фолбек
    kb = battle_keyboard(p, True, b)
    if q:
        await q.edit_message_text(header + "\nНевідома бойова дія.", parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.message.reply_html(header + "\nНевідома бойова дія.", reply_markup=kb)
    return CHOOSING_ACTION


# ----- Хід ворога -----

async def enemy_turn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Повний хід ворога:
    1) старт-ефекти (кровотеча тощо)
    2) перевірка оглушення
    3) атака ворога
    4) скидання одноходового DEF-бафу
    5) ЄДИНИЙ тік кулдаунів наприкінці
    """
    q = update.callback_query
    if q:
        await q.answer()

    p = dict_to_player(context.user_data.get("player"))
    e = dict_to_enemy(context.user_data.get("enemy"))
    b = context.user_data.setdefault("battle_state", {})

    header = _render_battle_header(p, e)
    info = []

    # Додамо лог попереднього повідомлення (дія гравця), якщо є
    prev = context.user_data.pop("last_log", "")
    if prev:
        # При редагуванні старого меседжа prev вже містить header, тому виведемо тільки коментар без повторного header
        # але простіше (і чистіше) виводити свіжий header та коротку суть
        # Тож лишаємо info тільки з короткими рядками поточного ходу ворога
        pass

    # (1) стартовi ефекти ворога
    start_txt = apply_start_of_enemy_turn_effects(e, b)
    if start_txt:
        info.append(start_txt)
    context.user_data["enemy"] = e.asdict()

    if e.hp <= 0:
        text = header + ("\n".join(info) + "\n\n💀 Ворог переможений!" if info else "\n\n💀 Ворог переможений!")
        return await _on_enemy_defeated(update, context, text, already_formatted=True)

    # (2) оглушення
    if enemy_is_stunned(b):
        # Кінець раунду — ТІЛЬКИ ТУТ тік кулдаунів
        turn_tick_cooldowns(b)
        context.user_data["battle_state"] = b
        text = header + ("\n".join(info) + "\n\n😵 Ворог оглушений і пропускає хід!" if info else "\n😵 Ворог оглушений і пропускає хід!")
        kb = battle_keyboard(p, True, b)
        if q:
            await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        else:
            await update.message.reply_html(text, reply_markup=kb)
        return CHOOSING_ACTION

    # (3) атака ворога (враховуємо одноходовий DEF-баф)
    def_up = b.get("p_status", {}).get("def_up_val", 0) if b.get("p_status", {}).get("def_up") else 0
    dmg = max(1, roll_damage(e.atk, p.defense + def_up))
    p.hp -= dmg
    context.user_data["player"] = p.asdict()
    info.append(f"🗡️ Ворог атакує вас та завдає {dmg} шкоди.")

    # (4) кінець ходу ворога — скинемо одноходовий DEF-баф
    clear_player_def_buff_after_enemy_turn(b)

    # (5) ЄДИНИЙ тік кулдаунів
    turn_tick_cooldowns(b)
    context.user_data["battle_state"] = b

    # Перевірка смерті гравця
    if p.hp <= 0:
        text = header + ("\n".join(info) + "\n\n💀 Ви впали в бою…" if info else "\n\n💀 Ви впали в бою…")
        if q:
            await q.edit_message_text(text, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_html(text)
        return ConversationHandler.END

    # Повертаємо хід гравцеві
    text = header + ("\n".join(info) + "\n\nВаш хід — оберіть дію." if info else "\nВаш хід — оберіть дію.")
    kb = battle_keyboard(p, True, b)
    if q:
        await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.message.reply_html(text, reply_markup=kb)
    return CHOOSING_ACTION


# ----- Перемога / Лут -----

async def _on_enemy_defeated(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, already_formatted: bool = False) -> int:
    """Екран перемоги + лут."""
    q = update.callback_query

    loot = generate_loot(context.user_data.get("location", ""))
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎒 Забрати лут", callback_data="battle:take_loot")],
        [InlineKeyboardButton("➡️ Далі", callback_data="battle:after_loot")],
    ])
    context.user_data["loot_pending"] = loot

    if q:
        await q.edit_message_text(text if already_formatted else (text + "\n\n💀 Ворог переможений!"),
                                  parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.message.reply_html(text if already_formatted else (text + "\n\n💀 Ворог переможений!"),
                                        reply_markup=kb)
    return LOOTING


# Після лута / завершення бою

async def after_loot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    if q:
        await q.answer()
        await q.edit_message_text("➡️ Продовжуємо пригоду! Використайте /explore.")
    else:
        await update.message.reply_text("➡️ Продовжуємо пригоду! Використайте /explore.")
    return ConversationHandler.END
