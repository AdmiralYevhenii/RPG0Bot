# -*- coding: utf-8 -*-
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..config import LOC_GUILD, SKILL_SLOT_MAX, GUILD_RESPEC_COST
from ..models import ensure_player_ud
from ..utils.skills import CLASS_SKILLS, skill_short_desc


def _kb(options, prefix: str | None = None) -> InlineKeyboardMarkup:
    """
    Будує одноколонкову Inline-клавіатуру.
    options: iterable[(text, data)]
    Якщо prefix передано — додає його як "prefix:data", інакше бере data як є.
    """
    def cb(data: str) -> str:
        return f"{prefix}:{data}" if prefix else data

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(txt, callback_data=cb(data))]
        for txt, data in options
    ])


def _render_loadout(p) -> str:
    load = list(getattr(p, "skills_loadout", []) or [])
    if not load:
        return "— не вибрано —"
    out = []
    for i, name in enumerate(load[:SKILL_SLOT_MAX], start=1):
        out.append(f"{i}. <b>{name}</b> — {skill_short_desc(name)}")
    return "\n".join(out)


def _render_known(p) -> str:
    known = list(getattr(p, "skills_known", []) or [])
    if not known:
        return "— немає вивчених умінь —"
    return "\n".join([f"• <b>{s}</b> — {skill_short_desc(s)}" for s in known])


def _in_guild(context) -> bool:
    return context.user_data.get("location") == LOC_GUILD


async def guild(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Головне меню Гільдії: вибір та керування уміннями."""
    p = ensure_player_ud(context.user_data)

    if not _in_guild(context):
        await update.message.reply_html(
            f"🏛️ Ви не в <b>{LOC_GUILD}</b>. Зайдіть туди через /travel.",
        )
        return

    known = getattr(p, "skills_known", []) or []
    loadout = list(getattr(p, "skills_loadout", []) or [])
    pending = bool(getattr(p, "pending_skill_choice", False))

    text = [
        "🏛️ <b>Гільдія авантюристів</b>",
        "Тут ви керуєте переліком умінь і набором активних умінь у бою.",
        "",
        f"Активні слоти ({len(loadout)}/{SKILL_SLOT_MAX}):",
        _render_loadout(p),
        "",
        "Відомі уміння:",
        _render_known(p),
    ]

    rows = []
    # Додати/зняти з лоадауту
    if known:
        rows.append([InlineKeyboardButton("➕ Додати в лоадаут", callback_data="guild:add")])
    if loadout:
        rows.append([InlineKeyboardButton("➖ Зняти з лоадауту", callback_data="guild:remove")])

    # Навчитися новому (якщо є право вибору)
    if pending:
        rows.append([InlineKeyboardButton("🆕 Вивчити нове вміння", callback_data="guild:learn")])

    # Скинути лоадаут (платно/за ресурс, опційно)
    rows.append([InlineKeyboardButton(f"♻️ Скинути лоадаут (−{GUILD_RESPEC_COST}з)", callback_data="guild:respec")])

    kb = InlineKeyboardMarkup(rows) if rows else None
    await update.message.reply_html("\n".join(text), reply_markup=kb)


async def on_guild_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback-логіка гільдії."""
    q = update.callback_query
    await q.answer()
    p = ensure_player_ud(context.user_data)
    data = q.data  # guild:*

    if not _in_guild(context):
        await q.edit_message_text(f"Ви не в {LOC_GUILD}. Зайдіть туди через /travel.")
        return

    # Підменю додавання до лоадауту
    if data == "guild:add":
        known = list(getattr(p, "skills_known", []) or [])
        loadout = list(getattr(p, "skills_loadout", []) or [])
        free = [s for s in known if s not in loadout]
        if not free:
            await q.edit_message_text("Немає доступних умінь, які можна додати.", parse_mode=ParseMode.HTML)
            return
        opts = [(f"➕ {s}", f"guild:addpick:{s}") for s in free]
        await q.edit_message_text(
            "Оберіть уміння для додавання до активного набору:",
            reply_markup=_kb(opts),  # без префікса — callback_data залишаються як у opts
        )
        return

    if data.startswith("guild:addpick:"):
        name = data.split(":", 2)[2]
        loadout = list(getattr(p, "skills_loadout", []) or [])
        if name in loadout:
            await q.edit_message_text("Це уміння вже в наборі.", parse_mode=ParseMode.HTML)
            return
        if len(loadout) >= SKILL_SLOT_MAX:
            await q.edit_message_text(f"Досягнуто ліміт {SKILL_SLOT_MAX} активних умінь.", parse_mode=ParseMode.HTML)
            return
        loadout.append(name)
        p.skills_loadout = loadout
        context.user_data["player"] = p.asdict()
        await q.edit_message_text(f"✅ Додано в лоадаут: <b>{name}</b>.", parse_mode=ParseMode.HTML)
        return

    # Підменю зняття з лоадауту
    if data == "guild:remove":
        loadout = list(getattr(p, "skills_loadout", []) or [])
        if not loadout:
            await q.edit_message_text("Лоадаут порожній.", parse_mode=ParseMode.HTML)
            return
        opts = [(f"➖ {s}", f"guild:rempick:{s}") for s in loadout]
        await q.edit_message_text(
            "Оберіть уміння для зняття з активного набору:",
            reply_markup=_kb(opts),
        )
        return

    if data.startswith("guild:rempick:"):
        name = data.split(":", 2)[2]
        loadout = list(getattr(p, "skills_loadout", []) or [])
        if name not in loadout:
            await q.edit_message_text("Уміння відсутнє в наборі.", parse_mode=ParseMode.HTML)
            return
        loadout = [s for s in loadout if s != name]
        p.skills_loadout = loadout
        context.user_data["player"] = p.asdict()
        await q.edit_message_text(f"✅ Знято з лоадауту: <b>{name}</b>.", parse_mode=ParseMode.HTML)
        return

    # Вивчення нового уміння (коли pending_skill_choice=True)
    if data == "guild:learn":
        cls = getattr(p, "class_name", None)
        pool = list(CLASS_SKILLS.get(cls, {}).keys())
        known = set(getattr(p, "skills_known", []) or [])
        choices = [s for s in pool if s not in known]
        if not getattr(p, "pending_skill_choice", False):
            await q.edit_message_text("Зараз у вас немає нового вибору уміння.", parse_mode=ParseMode.HTML)
            return
        if not choices:
            await q.edit_message_text("Для вашого класу нових умінь немає.", parse_mode=ParseMode.HTML)
            p.pending_skill_choice = False
            context.user_data["player"] = p.asdict()
            return
        opts = [(f"🆕 {s}", f"guild:learnpick:{s}") for s in choices[:6]]  # показуємо до 6
        await q.edit_message_text(
            "Оберіть нове уміння для вивчення:",
            reply_markup=_kb(opts),
        )
        return

    if data.startswith("guild:learnpick:"):
        name = data.split(":", 2)[2]
        known = list(getattr(p, "skills_known", []) or [])
        if name in known:
            await q.edit_message_text("Це уміння вже відоме.", parse_mode=ParseMode.HTML)
            return
        known.append(name)
        p.skills_known = known
        p.pending_skill_choice = False
        context.user_data["player"] = p.asdict()
        await q.edit_message_text(f"🎓 Вивчено нове уміння: <b>{name}</b>!", parse_mode=ParseMode.HTML)
        return

    # Скидання лоадауту за золото
    if data == "guild:respec":
        if p.gold < GUILD_RESPEC_COST:
            await q.edit_message_text("Недостатньо золота для скидання лоадауту.", parse_mode=ParseMode.HTML)
            return
        p.gold -= GUILD_RESPEC_COST
        p.skills_loadout = []
        context.user_data["player"] = p.asdict()
        await q.edit_message_text("♻️ Лоадаут скинуто. Ви можете знову обрати уміння.", parse_mode=ParseMode.HTML)
        return

    # Фолбек
    await q.edit_message_text("Невідома дія гільдії.")
