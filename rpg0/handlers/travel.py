# -*- coding: utf-8 -*-
"""
/travel — вибір локації
"""
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from ..config import LOCATIONS

async def travel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{loc}", callback_data=f"travel:{loc}")] for loc in LOCATIONS])
    await update.message.reply_html("🧭 Куди вирушаємо?", reply_markup=kb)

async def on_travel_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    loc = q.data.split(":", 1)[1]
    context.user_data["location"] = loc
    await q.edit_message_text(f"🧭 Місце призначення: {loc}. Тепер /explore врахує цю локацію.")
