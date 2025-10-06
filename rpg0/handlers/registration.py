# -*- coding: utf-8 -*-
"""
/register — вибір класу і передісторії
"""
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from ..models import ensure_player_ud, Player
from ..config import CLASSES, BACKSTORIES

def _kb(options, prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(opt, callback_data=f"{prefix}:{opt}")] for opt in options])

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ensure_player_ud(context.user_data)
    context.user_data['reg'] = {}
    text = ("🏛️ <b>Гільдія авантюристів</b> вітає!\n"
            "Оберіть <b>клас</b>, а потім — <b>передісторію</b>. Кожен вибір дає бонуси.")
    await update.message.reply_html(text, reply_markup=_kb(list(CLASSES.keys()), "reg:class"))

def apply_bonuses(p: Player, cls: str, bs: str) -> None:
    for src in (CLASSES.get(cls, {}), BACKSTORIES.get(bs, {})):
        p.max_hp += src.get("hp", 0)
        p.hp = min(p.max_hp, p.hp + src.get("hp", 0))
        p.atk += src.get("atk", 0)
        p.defense += src.get("defense", 0)
        p.potions += src.get("potions", 0)
        p.gold += src.get("gold", 0)

async def on_reg_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    data = q.data
    reg = context.user_data.get('reg', {})

    if data.startswith("reg:class:"):
        cls = data.split(":", 2)[2]
        reg['class'] = cls
        context.user_data['reg'] = reg
        desc = CLASSES[cls]['desc']
        await q.edit_message_text(f"✅ Клас: <b>{cls}</b> — {desc}.\nТепер оберіть передісторію:",
                                  parse_mode=ParseMode.HTML,
                                  reply_markup=_kb(list(BACKSTORIES.keys()), "reg:back"))
        return

    if data.startswith("reg:back:"):
        bs = data.split(":", 2)[2]
        reg['back'] = bs
        context.user_data['reg'] = reg
        cls = reg.get('class')
        preview = Player()
        apply_bonuses(preview, cls, bs)
        preview_txt = (f"Попередній підсумок бонусів:\n"
                       f"+HP {max(0, preview.max_hp-30)}, "
                       f"+ATK {max(0, preview.atk-6)}, "
                       f"+DEF {max(0, preview.defense-2)}, "
                       f"+Зілля {max(0, preview.potions-2)}, +Золото {preview.gold}")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Підтвердити", callback_data="reg:confirm")],
            [InlineKeyboardButton("↩️ Змінити клас", callback_data="reg:restart")],
        ])
        await q.edit_message_text(
            f"Клас: <b>{cls}</b>\nПередісторія: <b>{bs}</b>\n\n{preview_txt}",
            parse_mode=ParseMode.HTML, reply_markup=kb
        )
        return

    if data == "reg:restart":
        context.user_data['reg'] = {}
        await q.edit_message_text("Оберіть клас:", reply_markup=_kb(list(CLASSES.keys()), "reg:class"))
        return

    if data == "reg:confirm":
        p = ensure_player_ud(context.user_data)
        cls = reg.get('class'); bs = reg.get('back')
        p.class_name = cls; p.backstory = bs; p.registered = True
        apply_bonuses(p, cls, bs)
        context.user_data["player"] = p.asdict()
        context.user_data.pop('reg', None)
        await q.edit_message_text(
            f"🎉 Вітаємо в гільдії!\nКлас: <b>{cls}</b> | Передісторія: <b>{bs}</b>",
            parse_mode=ParseMode.HTML
        )
