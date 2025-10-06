# -*- coding: utf-8 -*-
"""
/shop — купівля спорядження, продаж луту, ремонт (через інвентар реалізовано, але продублюємо).
"""
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from ..models import ensure_player_ud
from ..utils.loot import price_of_item, sell_value, compute_price


def shop_stock():
    return [
        {"name":"Кинджал ремісника","rarity":"common","title":"⚪ Звичайний","emoji":"⚪","type":"weapon","atk":1,"defense":0,"price":15,"equipped":False,"durability":20},
        {"name":"Шкіряний нагрудник","rarity":"common","title":"⚪ Звичайний","emoji":"⚪","type":"armor","atk":0,"defense":1,"price":15,"equipped":False,"durability":20},
        {"name":"Срібний перстень","rarity":"uncommon","title":"🟢 Незвичайний","emoji":"🟢","type":"accessory","atk":1,"defense":1,"price":35,"equipped":False,"durability":20},
        {"name":"Меч лісника","rarity":"uncommon","title":"🟢 Незвичайний","emoji":"🟢","type":"weapon","atk":2,"defense":0,"price":38,"equipped":False,"durability":20},
        {"name":"Лати стража","rarity":"rare","title":"🔵 Рідкісний","emoji":"🔵","type":"armor","atk":0,"defense":3,"price":70,"equipped":False,"durability":20},
    ]

def kb_shop_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Купити", callback_data="shop:menu:buy")],
        [InlineKeyboardButton("💰 Продати", callback_data="shop:menu:sell")],
        [InlineKeyboardButton("⬅️ Закрити", callback_data="shop:close")],
    ])

def render_shop_buy() -> tuple[str, InlineKeyboardMarkup]:
    goods = shop_stock()
    lines = []
    for i,g in enumerate(goods):
        lines.append(f"{i+1}. {g['emoji']} <b>{g['name']}</b> — {g['title']} [{g['type']}] (+ATK {g.get('atk',0)}, +DEF {g.get('defense',0)}) — {g['price']}з")
    kb = [[InlineKeyboardButton(f"Купити {i+1}", callback_data=f"shop:buygear:{i}")] for i in range(len(goods))]
    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data="shop:menu:main")])
    return "🛒 Товари:\n" + "\n".join(lines), InlineKeyboardMarkup(kb)

def render_shop_sell(p) -> tuple[str, InlineKeyboardMarkup]:
    if not p.inventory:
        return "Нічого продавати.", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="shop:menu:main")]])
    lines, kb = [], []
    for i, it in enumerate(p.inventory):
        lines.append(f"{i+1}. {it['emoji']} <b>{it['name']}</b> — {it['title']} [{it['type']}] (+ATK {it.get('atk',0)}, +DEF {it.get('defense',0)}) — продаж: {sell_value(it)}з")
        kb.append([InlineKeyboardButton(f"Продати {i+1}", callback_data=f"shop:sell:{i}")])
    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data="shop:menu:main")])
    return "💰 Продаж інвентарю:\n" + "\n".join(lines), InlineKeyboardMarkup(kb)

async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    p = ensure_player_ud(context.user_data)
    await update.message.reply_html(f"🏪 Крамниця. У вас <b>{p.gold}</b> золота.", reply_markup=kb_shop_main())

async def on_shop_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    p = ensure_player_ud(context.user_data)
    data = q.data.split(":", 2)
    action = ":".join(data[1:]) if len(data) > 1 else ""

    if action == "menu:main":
        await q.edit_message_text(f"🏪 Крамниця. У вас <b>{p.gold}</b> золота.", parse_mode=ParseMode.HTML, reply_markup=kb_shop_main())
        return
    if action == "menu:buy":
        text, kb = render_shop_buy()
        await q.edit_message_text(text + f"\n\nВаше золото: <b>{p.gold}</b>", parse_mode=ParseMode.HTML, reply_markup=kb)
        return
    if action == "menu:sell":
        text, kb = render_shop_sell(p)
        await q.edit_message_text(text + f"\n\nВаше золото: <b>{p.gold}</b>", parse_mode=ParseMode.HTML, reply_markup=kb)
        return
    if action == "close":
        await q.edit_message_text("Крамницю закрито.")
        return

    if action.startswith("buygear:"):
        idx = int(action.split(":",1)[1])
        goods = shop_stock()
        if idx < 0 or idx >= len(goods):
            await q.edit_message_text("Невірний товар.", reply_markup=kb_shop_main()); return
        item = goods[idx].copy()
        price = item["price"]
        if p.gold < price:
            await q.edit_message_text("Недостатньо золота.", reply_markup=kb_shop_main()); return
        p.gold -= price
        p.inventory.append(item)
        context.user_data["player"] = p.asdict()
        text, kb = render_shop_buy()
        await q.edit_message_text(f"✅ Куплено: {item['emoji']} <b>{item['name']}</b> за {price}з.\n\n" + text + f"\n\nВаше золото: <b>{p.gold}</b>", parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    if action.startswith("sell:"):
        idx = int(action.split(":",1)[1])
        if idx < 0 or idx >= len(p.inventory):
            await q.edit_message_text("Невірний індекс.", reply_markup=kb_shop_main()); return
        it = p.inventory[idx]
        if it.get("equipped"):
            await q.edit_message_text("Зніміть предмет перед продажем.", reply_markup=kb_shop_main()); return
        gain = sell_value(it)
        p.gold += gain
        p.inventory.pop(idx)
        context.user_data["player"] = p.asdict()
        text, kb = render_shop_sell(p)
        await q.edit_message_text(f"💰 Продано: {it['emoji']} <b>{it['name']}</b> за {gain}з.\n\n" + text + f"\n\nВаше золото: <b>{p.gold}</b>", parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    await q.edit_message_text("Невідома дія магазину.", reply_markup=kb_shop_main())
