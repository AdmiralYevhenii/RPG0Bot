# -*- coding: utf-8 -*-
from __future__ import annotations
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from ..models import ensure_player_ud
from ..utils.loot import price_of_item, sell_value
from ..utils.equipment import equip_item, unequip_slot
from ..config import LOC_SHOP, LOC_CITY

def _kb(rows): 
    return InlineKeyboardMarkup(rows)

def kb_shop_main() -> InlineKeyboardMarkup:
    return _kb([
        [InlineKeyboardButton("🛒 Купити спорядження", callback_data="shop:menu:buy")],
        [InlineKeyboardButton("🧪 Купити зілля (+1 за 10з)", callback_data="shop:buy_potion")],
        [InlineKeyboardButton("💰 Продати з рюкзака", callback_data="shop:menu:sell")],
        [InlineKeyboardButton("⬅️ Вийти до Міста", callback_data="shop:leave")],
    ])

def shop_stock() -> list[dict]:
    # Статичний набір — можна розширювати
    return [
        {"name":"Кинджал ремісника","rarity":"common","title":"⚪ Звичайний","emoji":"⚪","type":"weapon","atk":1,"defense":0,"price":15,"equipped":False,"durability":20,"durability_max":20},
        {"name":"Шкіряний нагрудник","rarity":"common","title":"⚪ Звичайний","emoji":"⚪","type":"armor","atk":0,"defense":1,"price":15,"equipped":False,"durability":25,"durability_max":25},
        {"name":"Срібний перстень","rarity":"uncommon","title":"🟢 Незвичайний","emoji":"🟢","type":"accessory","atk":1,"defense":1,"price":35,"equipped":False,"durability":30,"durability_max":30},
        {"name":"Меч лісника","rarity":"uncommon","title":"🟢 Незвичайний","emoji":"🟢","type":"weapon","atk":2,"defense":0,"price":38,"equipped":False,"durability":35,"durability_max":35},
        {"name":"Лати стража","rarity":"rare","title":"🔵 Рідкісний","emoji":"🔵","type":"armor","atk":0,"defense":3,"price":70,"equipped":False,"durability":50,"durability_max":50},
    ]

def format_item_line(it: dict, idx: int | None = None, with_price: bool = False, sell_mode: bool = False) -> str:
    t = f"{it['emoji']} <b>{it['name']}</b> — {it['title']} [{it['type']}] (+ATK {it.get('atk',0)}, +DEF {it.get('defense',0)})"
    if "durability" in it and ("durability_max" in it or isinstance(it.get("durability"), int)):
        # показуємо тільки 'durability', або 'durability/durability_max' коли є обидва
        if "durability_max" in it:
            t += f" | ⚙️{it['durability']}/{it['durability_max']}"
        else:
            t += f" | ⚙️{it['durability']}"
    if with_price and it.get("price"):
        t += f" — ціна: {it['price']}з"
    if sell_mode:
        t += f" — продаж: {sell_value(it)}з"
    if idx is not None:
        t = f"{idx}. " + t
    return t


def render_shop_buy() -> tuple[str, InlineKeyboardMarkup]:
    goods = shop_stock()
    lines = [format_item_line(g, idx=i+1, with_price=True) for i,g in enumerate(goods)]
    kb = [[InlineKeyboardButton(f"Купити {i+1}", callback_data=f"shop:buygear:{i}")] for i in range(len(goods))]
    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data="shop:menu:main")])
    return "🛒 Товари:\n" + "\n".join(lines), InlineKeyboardMarkup(kb)

def render_shop_sell(p) -> tuple[str, InlineKeyboardMarkup]:
    if not p.inventory:
        return "Нічого продавати.", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="shop:menu:main")]])
    lines, kb = [], []
    for i, it in enumerate(p.inventory):
        lines.append(format_item_line(it, idx=i+1, sell_mode=True))
        kb.append([InlineKeyboardButton(f"Продати #{i+1} за {sell_value(it)}з", callback_data=f"shop:sell:{i}")])
    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data="shop:menu:main")])
    return "💰 Продаж інвентарю:\n" + "\n".join(lines), InlineKeyboardMarkup(kb)

async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Тепер /shop — це ЛОКАЦІЯ. 
    - Якщо ви ВЖЕ у “Крамниця (Місто)” — показуємо меню.
    - Якщо ви у “Місто” — пропонуємо швидко перейти в крамницю (без /travel).
    - В інших локаціях — підказуємо перейти в Місто -> Крамниця через /travel.
    """
    p = ensure_player_ud(context.user_data)
    loc = context.user_data.get("location")
    if loc == LOC_SHOP:
        await update.message.reply_html(f"🏪 Крамниця. Ваше золото: <b>{p.gold}</b>.", reply_markup=kb_shop_main())
        return
    if loc == LOC_CITY:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Увійти до Крамниці зараз", callback_data="shop:enter")],
            [InlineKeyboardButton("⬅️ Залишитись у Місті", callback_data="shop:cancel")],
        ])
        await update.message.reply_html("Ви в Місті. Перейти до <b>Крамниця (Місто)</b>?", reply_markup=kb)
        return
    await update.message.reply_html(
        f"🏪 Крамниця — це локація в Місті.\nСпершу перейдіть у <b>{LOC_CITY}</b> ➜ <b>{LOC_SHOP}</b> через /travel."
    )

async def on_shop_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    p = ensure_player_ud(context.user_data)
    loc = context.user_data.get("location")

    data = q.data.split(":", 1)
    action = data[1] if len(data) > 1 else ""

    # Швидкий вхід із Міста
    if action == "enter":
        if loc != LOC_CITY:
            await q.edit_message_text("❌ Швидкий перехід доступний лише з Міста.")
            return
        context.user_data["location"] = LOC_SHOP
        await q.edit_message_text(f"🏪 Увійшли до Крамниці. Ваше золото: <b>{p.gold}</b>.", parse_mode=ParseMode.HTML, reply_markup=kb_shop_main())
        return

    if action == "cancel":
        await q.edit_message_text("Залишилися в Місті.")
        return

    # Далі діє класична логіка магазину — тільки якщо ми вже в крамниці
    if context.user_data.get("location") != LOC_SHOP:
        await q.edit_message_text("❌ Ви не в крамниці. Перейдіть у Місто ➜ Крамниця через /travel, або скористайтесь /shop у Місті.")
        return

    if action == "menu:main":
        await q.edit_message_text(f"🏪 Крамниця. Ваше золото: <b>{p.gold}</b>.", reply_markup=kb_shop_main(), parse_mode=ParseMode.HTML)
        return

    if action == "menu:buy":
        text, kb = render_shop_buy()
        await q.edit_message_text(text + f"\n\nВаше золото: <b>{p.gold}</b>", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    if action == "menu:sell":
        text, kb = render_shop_sell(p)
        await q.edit_message_text(text + f"\n\nВаше золото: <b>{p.gold}</b>", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    if action == "leave":
        # миттєво повертаємо в Місто
        context.user_data["location"] = LOC_CITY
        await q.edit_message_text("↩️ Повернення до Міста виконано. Використайте /travel для подальшого шляху.")
        return

    # Купівля спорядження зі стоку
    if action.startswith("buygear:"):
        idx = int(action.split(":",1)[1])
        goods = shop_stock()
        if idx < 0 or idx >= len(goods):
            await q.edit_message_text("Невірний товар.", reply_markup=kb_shop_main())
            return
        item = goods[idx].copy()
        price = item["price"]
        if p.gold < price:
            await q.edit_message_text("Недостатньо золота.", reply_markup=kb_shop_main())
            return
        p.gold -= price
        p.inventory.append(item)
        context.user_data["player"] = p.asdict()
        text, kb = render_shop_buy()
        await q.edit_message_text(
            f"✅ Куплено: {item['emoji']} <b>{item['name']}</b> за {price}з.\n\n" + text + f"\n\nВаше золото: <b>{p.gold}</b>",
            reply_markup=kb, parse_mode=ParseMode.HTML
        )
        return

    # Зілля
    if action == "buy_potion":
        if p.gold >= 10:
            p.gold -= 10
            p.potions += 1
            context.user_data["player"] = p.asdict()
            await q.edit_message_text(f"🧪 Придбано зілля за 10з. Тепер золота: <b>{p.gold}</b>.", parse_mode=ParseMode.HTML, reply_markup=kb_shop_main())
        else:
            await q.edit_message_text("Недостатньо золота.", reply_markup=kb_shop_main())
        return

    # Продаж предмета з інвентаря
    if action.startswith("sell:"):
        idx = int(action.split(":",1)[1])
        if idx < 0 or idx >= len(p.inventory):
            await q.edit_message_text("Невірний індекс.", reply_markup=kb_shop_main())
            return
        it = p.inventory[idx]
        if it.get("equipped"):
            await q.edit_message_text("Зніміть предмет перед продажем.", reply_markup=kb_shop_main())
            return
        gain = sell_value(it)
        p.gold += gain
        p.inventory.pop(idx)
        context.user_data["player"] = p.asdict()
        text, kb = render_shop_sell(p)
        await q.edit_message_text(
            f"💰 Продано: {it['emoji']} <b>{it['name']}</b> за {gain}з.\n\n" + text + f"\n\nВаше золото: <b>{p.gold}</b>",
            reply_markup=kb, parse_mode=ParseMode.HTML
        )
        return

    await q.edit_message_text("Невідома дія магазину.", reply_markup=kb_shop_main())
