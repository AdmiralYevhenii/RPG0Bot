# -*- coding: utf-8 -*-
from __future__ import annotations
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import ContextTypes
from ..config import ADJACENT, LOCATION_ORDER, LOC_CITY, LOC_GUILD, LOC_SHOP
from ..models import ensure_player_ud

def _kb(rows): 
    return InlineKeyboardMarkup(rows)

def _build_travel_kb(current: str) -> InlineKeyboardMarkup:
    """Показує лише суміжні локації з поточною."""
    neighbors = ADJACENT.get(current, [])
    rows = [[InlineKeyboardButton(f"➡️ {loc}", callback_data=f"travel:{loc}")]
            for loc in LOCATION_ORDER if loc in neighbors]
    # Якщо ви в Місті — окремо підсвітити крамницю, але залишаємо її серед сусідів
    if current == LOC_CITY and LOC_SHOP in neighbors:
        rows.append([InlineKeyboardButton("🛒 Перейти в Крамницю (швидко)", callback_data=f"travel:{LOC_SHOP}")])
    return _kb(rows or [[InlineKeyboardButton("Немає доступних переходів", callback_data="travel:none")]])

def _neighbors_table(current: str) -> str:
    """Коротка “табличка переходів” з підказками та обмеженнями для локації."""
    neighbors = ADJACENT.get(current, [])
    if not neighbors:
        return "З цієї локації немає виходів."
    hints = {
        LOC_CITY: "Головний вузол пригод. Звідси є шлях у Руїни, Старий ліс та 🛒 Крамницю.",
        LOC_GUILD: "Місце керування уміннями та реєстрації. Вийти можна лише до Міста або на Тракт.",
        LOC_SHOP: "Локація торгівлі. Щоб продовжити пригоду — поверніться до Міста.",
    }
    lines = []
    if current in hints:
        lines.append(f"📌 <i>{hints[current]}</i>")
    lines.append("Доступні переходи:")
    for loc in neighbors:
        note = ""
        if current == LOC_GUILD and loc not in (LOC_CITY, "Тракт"):
            note = " (недоступно)"  # захисний маркер; фактично й так не буде серед neighbors
        if current == LOC_CITY and loc == LOC_SHOP:
            note = " (крамниця всередині міста)"
        lines.append(f"• {loc}{note}")
    return "\n".join(lines)

async def travel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показати суміжні переходи + табличку-пояснення."""
    ensure_player_ud(context.user_data)  # гарантуємо наявність гравця
    current = context.user_data.get("location") or "Тракт"
    text = (
        f"🧭 Ви знаходитесь: <b>{current}</b>\n\n"
        f"{_neighbors_table(current)}\n\n"
        "Оберіть напрямок:"
    )
    await update.message.reply_html(text, reply_markup=_build_travel_kb(current))

async def on_travel_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    current = context.user_data.get("location") or "Тракт"
    data = q.data
    if data == "travel:none":
        await q.edit_message_text("Немає доступних переходів із цієї локації.")
        return
    target = data.split(":", 1)[1]
    # Перевірка дозволеності переходу
    if target not in ADJACENT.get(current, []):
        await q.edit_message_text(f"❌ Перехід у “{target}” недоступний з “{current}”.")
        return

    context.user_data["location"] = target
    text = (
        f"🧭 Перехід виконано. Нова локація: <b>{target}</b>.\n\n"
        f"{_neighbors_table(target)}\n\n"
        "Оберіть наступний напрямок:"
    )
    await q.edit_message_text(text, reply_markup=_build_travel_kb(target), parse_mode="HTML")
