# -*- coding: utf-8 -*-
from __future__ import annotations
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from ..models import ensure_player_ud
from ..config import SKILL_SLOT_MAX
from ..utils.skills import (
    skills_for_class, pick_new_skill_options, add_to_loadout, remove_from_loadout
)

GUILD_LOC_NAME = "Гільдія авантюристів"

def _kb(rows): return InlineKeyboardMarkup(rows)

def _guild_text(p) -> str:
    known = ", ".join(p.skills_known) if p.skills_known else "— немає —"
    load = ", ".join(p.skills_loadout) if p.skills_loadout else "— порожньо —"
    return (f"🏛️ <b>Гільдія авантюристів</b>\n"
            f"Клас: {p.class_name or '—'}\n"
            f"Відомі вміння: {known}\n"
            f"Набір (до {SKILL_SLOT_MAX}): {load}\n"
            f"{'🆕 Доступний вибір нового вміння!' if p.pending_skill_choice else ''}")

async def guild(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    p = ensure_player_ud(context.user_data)
    if context.user_data.get("location") != GUILD_LOC_NAME:
        await update.message.reply_html(
            f"🏛️ Ви не в гільдії. Перейдіть у локацію “{GUILD_LOC_NAME}” через /travel."
        )
        return
    await update.message.reply_html(
        _guild_text(p),
        reply_markup=_kb([
            [InlineKeyboardButton("📚 Мої вміння", callback_data="guild:skills")],
            [InlineKeyboardButton("🎒 Набір у бій", callback_data="guild:loadout")],
            [InlineKeyboardButton("✨ Вивчити нове", callback_data="guild:learn")],
        ])
    )

async def on_guild_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    p = ensure_player_ud(context.user_data)
    if context.user_data.get("location") != GUILD_LOC_NAME:
        await q.edit_message_text("Сюди можна заходити лише перебуваючи в локації Гільдії.")
        return

    data = q.data.split(":", 1)[1]

    if data == "skills":
        pool = skills_for_class(p.class_name)
        lines = [f"• <b>{name}</b> (КД {spec['cd']}): {spec['desc']}" for name, spec in pool.items()]
        await q.edit_message_text(
            "📚 Класові вміння:\n" + ("\n".join(lines) if lines else "— немає —"),
            parse_mode=ParseMode.HTML,
            reply_markup=_kb([[InlineKeyboardButton("⬅️ Назад", callback_data="guild:menu")]])
        )
        return

    if data == "loadout":
        rows = []
        for name in (p.skills_known or []):
            if name not in (p.skills_loadout or []):
                rows.append([InlineKeyboardButton(f"➕ Додати: {name}", callback_data=f"guild:add:{name}")])
        for name in (p.skills_loadout or []):
            rows.append([InlineKeyboardButton(f"➖ Прибрати: {name}", callback_data=f"guild:rem:{name}")])
        await q.edit_message_text(
            _guild_text(p), parse_mode=ParseMode.HTML,
            reply_markup=_kb(rows or [[InlineKeyboardButton("⬅️ Назад", callback_data="guild:menu")]])
        )
        return

    if data.startswith("add:"):
        name = data.split(":", 1)[1]
        ok, msg = add_to_loadout(p, name, SKILL_SLOT_MAX)
        context.user_data["player"] = p.asdict()
        await q.edit_message_text(
            f"{msg}\n\n" + _guild_text(p), parse_mode=ParseMode.HTML,
            reply_markup=_kb([[InlineKeyboardButton("⬅️ Назад", callback_data="guild:loadout")]])
        )
        return

    if data.startswith("rem:"):
        name = data.split(":", 1)[1]
        ok, msg = remove_from_loadout(p, name)
        context.user_data["player"] = p.asdict()
        await q.edit_message_text(
            f"{msg}\n\n" + _guild_text(p), parse_mode=ParseMode.HTML,
            reply_markup=_kb([[InlineKeyboardButton("⬅️ Назад", callback_data="guild:loadout")]])
        )
        return

    if data == "learn":
        if not p.pending_skill_choice:
            await q.edit_message_text(
                "Наразі нові вміння не доступні. Підвищуйте рівень!",
                reply_markup=_kb([[InlineKeyboardButton("⬅️ Назад", callback_data="guild:menu")]])
            )
            return
        options = pick_new_skill_options(p)
        if not options:
            await q.edit_message_text(
                "Усі вміння вашого класу вже вивчені!",
                reply_markup=_kb([[InlineKeyboardButton("⬅️ Назад", callback_data="guild:menu")]])
            )
            return
        rows = [[InlineKeyboardButton(f"Вивчити: {n}", callback_data=f"guild:take:{n}")] for n in options]
        rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="guild:menu")])
        await q.edit_message_text("Оберіть нове вміння:", reply_markup=_kb(rows))
        return

    if data.startswith("take:"):
        name = data.split(":", 1)[1]
        if name not in (p.skills_known or []):
            p.skills_known.append(name)
        p.pending_skill_choice = False
        context.user_data["player"] = p.asdict()
        await q.edit_message_text(
            f"🎉 Вивчено нове вміння: <b>{name}</b>\n\n" + _guild_text(p),
            parse_mode=ParseMode.HTML,
            reply_markup=_kb([[InlineKeyboardButton("Додати в набір", callback_data=f"guild:add:{name}")],
                              [InlineKeyboardButton("⬅️ Назад", callback_data="guild:menu")]])
        )
        return

    if data == "menu":
        await q.edit_message_text(
            _guild_text(p), parse_mode=ParseMode.HTML,
            reply_markup=_kb([
                [InlineKeyboardButton("📚 Мої вміння", callback_data="guild:skills")],
                [InlineKeyboardButton("🎒 Набір у бій", callback_data="guild:loadout")],
                [InlineKeyboardButton("✨ Вивчити нове", callback_data="guild:learn")],
            ])
        )
        return
