# -*- coding: utf-8 -*-
from __future__ import annotations

import random
from typing import Tuple, List

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


# ----- Рендери та клавіатури -----

def _render_battle_header(p, e) -> str:
    return (
        f"⚔️ <b>БІЙ</b>\n"
        f"👤 Ви: {p.name} — HP {p.hp}/{p.max_hp} | ATK {p.atk} DEF {p.defense}\n"
        f"👹 Ворог: {e.name} — HP {e.hp}/{e.max_hp} | ATK {e.atk} DEF {e.defense}\n"
    )

def _kb_main(battle_state: dict) -> InlineKeyboardMarkup:
    """Головне бойове меню (включає кнопку Вміння)."""
    rows = [
        [InlineKeyboardButton("🗡️ Атака",  callback_data="battle:attack")],
        [InlineKeyboardButton("🌀 Вміння", callback_data="battle:skill")],
        [InlineKeyboardButton("🛡️ Захист", callback_data="battle:defend")],
        [InlineKeyboardButton("🧪 Зілля",   callback_data="battle:potion")],
        [InlineKeyboardButton("🏃 Втекти",  callback_data="battle:run")],
    ]
    return InlineKeyboardMarkup(rows)

def _skill_cd(bstate: dict, name: str) -> int:
    cds = bstate.setdefault("cooldowns", {})
    return int(cds.get(name, 0) or 0)

def _kb_skills(p, bstate: dict) -> InlineKeyboardMarkup:
    """Меню вибору умінь з показом КД, + кнопка Назад."""
    loadout = list(getattr(p, "skills_loadout", []) or [])
    rows: List[List[InlineKeyboardButton]] = []
    for s in loadout:
        cd = _skill_cd(bstate, s)
        label = f"🌀 {s} (КД {cd})" if cd > 0 else f"🌀 {s}"
        rows.append([InlineKeyboardButton(label, callback_data=f"battle:skilluse:{s}")])
    rows.append([InlineKeyboardButton("↩️ Назад", callback_data="battle:back")])
    return InlineKeyboardMarkup(rows)


# ----- Головний хендлер бою -----

async def on_battle_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка усіх callback'ів з префіксом 'battle:'."""
    q = update.callback_query
    data = q.data if q else None

    if q:
        await q.answer()

    # Витягуємо поточні об'єкти
    p = dict_to_player(context.user_data.get("player"))
    e = dict_to_enemy(context.user_data.get("enemy"))
    b = context.user_data.setdefault("battle_state", {})

    # Базовий вивід (хедер)
    header = _render_battle_header(p, e)

    # ---- Головне меню / Навігація ----
    if data == "battle:back":
        # Повернення до основного меню бою
        if q:
            await q.edit_message_text(header + "\nВаш хід — оберіть дію.", reply_markup=_kb_main(b), parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_html(header + "\nВаш хід — оберіть дію.", reply_markup=_kb_main(b))
        return CHOOSING_ACTION

    if data == "battle:skill":
        # Відкриваємо підменю умінь
        loadout = list(getattr(p, "skills_loadout", []) or [])
        if not loadout:
            txt = header + "\nУ вас немає активних умінь у лоодауті. Додайте їх у /guild."
            if q:
                await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=_kb_main(b))
            else:
                await update.message.reply_html(txt, reply_markup=_kb_main(b))
            return CHOOSING_ACTION

        if q:
            await q.edit_message_text(header + "\nОберіть уміння:", reply_markup=_kb_skills(p, b), parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_html(header + "\nОберіть уміння:", reply_markup=_kb_skills(p, b))
        return CHOOSING_ACTION

    # ---- Атака ----
    if data == "battle:attack":
        # З’їдаємо тимчасові бафи атаки/захисту гравця на цей удар
        atk_b, def_b = consume_player_temp_buffs(p, b)
        dmg, crit = roll_player_attack(p.atk + atk_b, e.defense)
        e.hp -= dmg

        # Оновлюємо стейти
        context.user_data["player"] = p.asdict()
        context.user_data["enemy"] = e.asdict()

        text = header + f"\n🗡️ Ви атакуєте ворога та завдаєте {dmg} шкоди{' (КРИТ!)' if crit else ''}."

        # Перевірка смерті ворога
        if e.hp <= 0:
            loot = generate_loot(context.user_data.get("location", ""))
            # Перехід у лут-екран
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎒 Забрати лут", callback_data="battle:take_loot")],
                [InlineKeyboardButton("➡️ Далі", callback_data="battle:after_loot")],
            ])
            context.user_data["loot_pending"] = loot
            if q:
                await q.edit_message_text(text + "\n\n💀 Ворог переможений!", parse_mode=ParseMode.HTML, reply_markup=kb)
            else:
                await update.message.reply_html(text + "\n\n💀 Ворог переможений!", reply_markup=kb)
            return LOOTING

        # Хід ворога
        return await _enemy_turn_after_player_action(update, context, prefix_text=text)

    # ---- Захист ----
    if data == "battle:defend":
        # Простий одноходовий баф захисту (+2)
        pst = b.setdefault("p_status", {})
        pst["def_up"] = 1
        pst["def_up_val"] = max(2, int(p.level / 2) + 1)  # трішки масштабуємо з рівнем
        context.user_data["battle_state"] = b
        text = header + f"\n🛡️ Ви займаєте оборонну стійку: +{pst['def_up_val']} до захисту на цей раунд."
        return await _enemy_turn_after_player_action(update, context, prefix_text=text)

    # ---- Зілля ----
    if data == "battle:potion":
        healed = min(p.max_hp - p.hp, 8)  # просте лікування
        p.hp += healed
        context.user_data["player"] = p.asdict()
        text = header + f"\n🧪 Ви випиваєте зілля та відновлюєте {healed} HP."
        return await _enemy_turn_after_player_action(update, context, prefix_text=text)

    # ---- Втеча ----
    if data == "battle:run":
        # 50% на втечу
        if random.random() < 0.5:
            msg = header + "\n🏃 Ви успішно втекли з бою."
            if q:
                await q.edit_message_text(msg, parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_html(msg)
            return ConversationHandler.END
        else:
            text = header + "\n🏃 Спроба втечі невдала!"
            return await _enemy_turn_after_player_action(update, context, prefix_text=text)

    # ---- Використання уміння ----
    if data and data.startswith("battle:skilluse:"):
        skill_name = data.split(":", 2)[2]
        loadout = list(getattr(p, "skills_loadout", []) or [])
        if skill_name not in loadout:
            txt = header + "\nЦе уміння не входить до вашого активного набору."
            if q:
                await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=_kb_main(b))
            else:
                await update.message.reply_html(txt, reply_markup=_kb_main(b))
            return CHOOSING_ACTION

        # Перевірка КД
        if _skill_cd(b, skill_name) > 0:
            txt = header + "\nВміння на перезарядці."
            if q:
                await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=_kb_skills(p, b))
            else:
                await update.message.reply_html(txt, reply_markup=_kb_skills(p, b))
            return CHOOSING_ACTION

        # Виконуємо уміння (apply_skill сам поставить КД)
        effect_text = apply_skill(p, e, skill_name, b)

        # Оновлення моделей
        context.user_data["player"] = p.asdict()
        context.user_data["enemy"] = e.asdict()
        context.user_data["battle_state"] = b

        text = header + f"\n{effect_text}"

        # Якщо ворог впав від ефекту одразу
        if e.hp <= 0:
            loot = generate_loot(context.user_data.get("location", ""))
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎒 Забрати лут", callback_data="battle:take_loot")],
                [InlineKeyboardButton("➡️ Далі", callback_data="battle:after_loot")],
            ])
            context.user_data["loot_pending"] = loot
            if q:
                await q.edit_message_text(text + "\n\n💀 Ворог переможений!", parse_mode=ParseMode.HTML, reply_markup=kb)
            else:
                await update.message.reply_html(text + "\n\n💀 Ворог переможений!", reply_markup=kb)
            return LOOTING

        # Хід ворога
        return await _enemy_turn_after_player_action(update, context, prefix_text=text)

    # ---- Лут / Після бою ----
    if data == "battle:take_loot":
        loot = context.user_data.pop("loot_pending", [])
        # Кладемо в інвентар гравця
        inv = list(getattr(p, "inventory", []) or [])
        inv.extend(loot)
        p.inventory = inv
        context.user_data["player"] = p.asdict()
        msg = "🎒 Ви забрали лут:\n" + "\n".join([f"• {it.get('name','?')}" for it in loot]) if loot else "🎒 Лут порожній."
        if q:
            await q.edit_message_text(msg + "\n\n➡️ Продовжуйте /explore", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_html(msg + "\n\n➡️ Продовжуйте /explore")
        return ConversationHandler.END

    if data == "battle:after_loot":
        if q:
            await q.edit_message_text("➡️ Продовжуємо пригоду! Використайте /explore.", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text("➡️ Продовжуємо пригоду! Використайте /explore.")
        return ConversationHandler.END

    # Фолбек
    if q:
        await q.edit_message_text(header + "\nНевідома бойова дія.", parse_mode=ParseMode.HTML, reply_markup=_kb_main(b))
    else:
        await update.message.reply_html(header + "\nНевідома бойова дія.", reply_markup=_kb_main(b))
    return CHOOSING_ACTION


# ----- Внутрішня логіка ходу ворога -----

async def _enemy_turn_after_player_action(update: Update, context: ContextTypes.DEFAULT_TYPE, prefix_text: str = "") -> int:
    """Обробляє повний хід ворога після дії гравця (ефекти, оглушення, атака, тік КД)."""
    q = update.callback_query
    p = dict_to_player(context.user_data.get("player"))
    e = dict_to_enemy(context.user_data.get("enemy"))
    b = context.user_data.setdefault("battle_state", {})

    # Хедер
    header = _render_battle_header(p, e)
    info_lines: List[str] = []
    if prefix_text:
        info_lines.append(prefix_text)

    # 1) Старт ходу ворога: дот-ефекти (кровотеча тощо)
    start_txt = apply_start_of_enemy_turn_effects(e, b)
    if start_txt:
        info_lines.append(start_txt)
    context.user_data["enemy"] = e.asdict()

    # Якщо ворог помер від ефектів на старті
    if e.hp <= 0:
        loot = generate_loot(context.user_data.get("location", ""))
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎒 Забрати лут", callback_data="battle:take_loot")],
            [InlineKeyboardButton("➡️ Далі", callback_data="battle:after_loot")],
        ])
        context.user_data["loot_pending"] = loot
        text = header + "\n".join(info_lines) + "\n\n💀 Ворог переможений!"
        if q:
            await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        else:
            await update.message.reply_html(text, reply_markup=kb)
        return LOOTING

    # 2) Чи оглушений ворог
    if enemy_is_stunned(b):
        # Наприкінці раунду: тік кулдаунів
        turn_tick_cooldowns(b)
        context.user_data["battle_state"] = b
        text = header + "\n".join(info_lines) + "\n\n😵 Ворог оглушений і пропускає хід!"
        if q:
            await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=_kb_main(b))
        else:
            await update.message.reply_html(text, reply_markup=_kb_main(b))
        return CHOOSING_ACTION

    # 3) Атака ворога
    # Вплив одноходового деф-бафу гравця обробляється в roll_damage через модифікатор defense
    def_up = b.get("p_status", {}).get("def_up_val", 0) if b.get("p_status", {}).get("def_up") else 0
    dmg = max(1, roll_damage(e.atk, p.defense + def_up))
    p.hp -= dmg
    context.user_data["player"] = p.asdict()

    info_lines.append(f"🗡️ Ворог атакує вас та завдає {dmg} шкоди.")

    # 4) Кінець ходу ворога: скинути одноходовий деф-баф
    clear_player_def_buff_after_enemy_turn(b)

    # 5) Наприкінці раунду: тік КД умінь
    turn_tick_cooldowns(b)
    context.user_data["battle_state"] = b

    # Якщо гравець загинув
    if p.hp <= 0:
        text = header + "\n".join(info_lines) + "\n\n💀 Ви впали в бою…"
        if q:
            await q.edit_message_text(text, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_html(text)
        return ConversationHandler.END

    # Інакше — знову хід гравця
    text = header + "\n".join(info_lines) + "\n\nВаш хід — оберіть дію."
    if q:
        await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=_kb_main(b))
    else:
        await update.message.reply_html(text, reply_markup=_kb_main(b))
    return CHOOSING_ACTION


# ----- Пост-битва (залишено для сумісності, якщо викликається з інших місць) -----

async def after_loot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("➡️ Продовжуємо пригоду! Використайте /explore.")
    else:
        await update.message.reply_text("➡️ Продовжуємо пригоду! Використайте /explore.")
    return ConversationHandler.END
