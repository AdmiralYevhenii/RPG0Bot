# -*- coding: utf-8 -*-
"""
/inventory — перегляд, надягти/зняти, ремонт через інвентар.
"""
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from ..models import ensure_player_ud
from ..utils.equipment import equip_item, unequip_slot, repair_item

def render_inventory(p) -> tuple[str, InlineKeyboardMarkup]:
    eq_lines = []
    for slot in ("weapon","armor","accessory"):
        cur = p.equipment.get(slot)
        if cur:
            eq_lines.append(f"• {slot}: {cur['emoji']} <b>{cur['name']}</b> (+ATK {cur.get('atk',0)}, +DEF {cur.get('defense',0)}, 🔧 {cur.get('durability',0)})")
        else:
            eq_lines.append(f"• {slot}: — порожньо —")

    inv_lines, kb_rows = [], []
    for i, it in enumerate(p.inventory):
        inv_lines.append(f"{i+1}. {it['emoji']} <b>{it['name']}</b> — {it['title']} [{it['type']}] (+ATK {it.get('atk',0)}, +DEF {it.get('defense',0)}, 🔧 {it.get('durability',0)})")
        if it.get("type") in ("weapon","armor","accessory"):
            kb_rows.append([InlineKeyboardButton(f"Надягти #{i+1}", callback_data=f"inv:equip:{i}")])
        kb_rows.append([InlineKeyboardButton(f"Ремонт #{i+1}", callback_data=f"inv:repair:{i}")])

    undress = []
    for slot in ("weapon","armor","accessory"):
        if p.equipment.get(slot):
            undress.append(InlineKeyboardButton(f"Зняти {slot}", callback_data=f"inv:unequip:{slot}"))
    if undress:
        kb_rows.append(undress)

    text = (f"🎒 Інвентар:\n🧪 Зілля: {p.potions}\n💰 Золото: {p.gold}\n\n"
            "Екіпірування:\n" + ("\n".join(eq_lines) if eq_lines else "—") + "\n\n"
            "Речі в рюкзаку:\n" + ("\n".join(inv_lines) if inv_lines else "— немає предметів —"))
    return text, InlineKeyboardMarkup(kb_rows or [[InlineKeyboardButton("Оновити", callback_data="inv:refresh")]])

async def inventory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    p = ensure_player_ud(context.user_data)
    text, kb = render_inventory(p)
    await update.message.reply_html(text, reply_markup=kb)

async def on_inv_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    p = ensure_player_ud(context.user_data)
    parts = q.data.split(":", 2)
    action = parts[1] if len(parts) > 1 else ""

    if action == "equip":
        idx = int(parts[2])
        ok, msg = equip_item(p, idx)
        context.user_data["player"] = p.asdict()
        text, kb = render_inventory(p)
        await q.edit_message_text(msg + "\n\n" + text, reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    if action == "unequip":
        slot = parts[2]
        ok, msg = unequip_slot(p, slot)
        context.user_data["player"] = p.asdict()
        text, kb = render_inventory(p)
        await q.edit_message_text(msg + "\n\n" + text, reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    if action == "repair":
        idx = int(parts[2])
        ok, msg = repair_item(p, idx)
        context.user_data["player"] = p.asdict()
        text, kb = render_inventory(p)
        await q.edit_message_text(msg + "\n\n" + text, reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    if action == "refresh":
        text, kb = render_inventory(p)
        await q.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    text, kb = render_inventory(p)
    await q.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
