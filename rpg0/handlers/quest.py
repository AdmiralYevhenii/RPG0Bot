# -*- coding: utf-8 -*-
"""
/quest — простий ланцюжок: вбий 3 ворогів -> нагорода.
"""
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from ..models import ensure_player_ud

async def quest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    qst = context.user_data.get("quest")
    if not qst or qst.get("state") in ("completed", "rewarded"):
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Прийняти квест: Перемогти 3 ворогів", callback_data="quest:accept")]])
        await update.message.reply_html("📜 Доступний квест: <b>Зачистка околиць</b> — переможи 3 ворогів. Нагорода: 50з і 1 зілля.", reply_markup=kb)
    elif qst.get("state") == "active":
        await update.message.reply_html(f"📜 Прогрес квесту: {qst.get('progress', 0)}/3. Переможіть ще {3 - qst.get('progress', 0)} ворогів.")
    elif qst.get("state") == "turnin":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Отримати нагороду", callback_data="quest:reward")]])
        await update.message.reply_html("✅ Квест виконано! Отримайте нагороду.", reply_markup=kb)

async def on_quest_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    data = q.data.split(":", 1)[1]
    p = ensure_player_ud(context.user_data)
    quest_state = context.user_data.get("quest")

    if data == "accept":
        context.user_data["quest"] = {"id": "clear-3", "state": "active", "progress": 0}
        await q.edit_message_text("📜 Квест прийнято: перемогти 3 ворогів.")
        return

    if data == "reward":
        if quest_state and quest_state.get("state") == "turnin":
            p.gold += 50; p.potions += 1
            context.user_data["player"] = p.asdict()
            quest_state["state"] = "rewarded"
            context.user_data["quest"] = quest_state
            await q.edit_message_text("💰 +50 золота, 🧪 +1 зілля. Дякуємо за службу!")
        else:
            await q.edit_message_text("Нагорода недоступна.")
