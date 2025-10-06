# -*- coding: utf-8 -*-
from __future__ import annotations
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import ContextTypes

async def travel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏘️ Місто", callback_data="travel:Місто")],
        [InlineKeyboardButton("🛤️ Тракт", callback_data="travel:Тракт")],
        [InlineKeyboardButton("🏚️ Руїни", callback_data="travel:Руїни")],
        [InlineKeyboardButton("🏛️ Гільдія авантюристів", callback_data="travel:Гільдія авантюристів")],
    ])
    await update.message.reply_html("🧭 Куди вирушаємо?", reply_markup=kb)

async def on_travel_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    loc = q.data.split(":", 1)[1]
    context.user_data["location"] = loc
    await q.edit_message_text(f"🧭 Місце призначення: {loc}. Тепер /explore врахує цю локацію.")
