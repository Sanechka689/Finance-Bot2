# handlers/menu.py

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes
from services.sheets_service import open_finance_and_plans

# 1. состояния
STATE_MAIN_MENU = 100

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """# 1.1 — Показываем главное меню бота."""
    # 1.2 — клавиатура с эмодзи
    keyboard = [
        [InlineKeyboardButton("💰 Финансы",       callback_data="menu:finance"),
         InlineKeyboardButton("📝 Операции",      callback_data="menu:operations")],
        [InlineKeyboardButton("🏷 Классификация", callback_data="menu:classification"),
         InlineKeyboardButton("🗓 Планы",         callback_data="menu:plans")],
        [InlineKeyboardButton("➕ Добавить Банк", callback_data="menu:add_bank"),
         InlineKeyboardButton("➖ Удалить Банк",  callback_data="menu:del_bank")],
        [InlineKeyboardButton("✏️ Изменить таблицу",   callback_data="menu:edit_table"),
         InlineKeyboardButton("💳 Поменять тариф",     callback_data="menu:change_tariff")],
        [InlineKeyboardButton("🔗 Показать таблицу",   callback_data="menu:show_sheet"),
         InlineKeyboardButton("💬 Поддержка",          callback_data="menu:support")],
        # 1.3 — одна большая кнопка «Назад»
        [InlineKeyboardButton("🔙 Назад", callback_data="menu:back")],
    ]

    # вместо update.message используем effective_message,
    # чтобы работало и при callback_query
    target = update.effective_message  
    await target.reply_text(
        "Выберите раздел меню:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    # если вызов из коллбэка — редактируем существующее сообщение,
    # иначе — отправляем новое
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "Выберите раздел меню:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            "Выберите раздел меню:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    return STATE_MAIN_MENU

async def handle_menu_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """# 2.1 — Обработка пунктов меню."""
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":", 1)[1]

    # 2.2 — если нажали «Меню» из /add
    if choice == "open":
        return await show_main_menu(update, context)

    # 2.3 — «Назад» возвращает на этап добавления операции
    if choice == "back":
        # Возвращаемся к экрану операций (/add)
        from handlers.operations import go_main_menu
        return await go_main_menu(update, context)

    # 2.4 — Финансы
    if choice == "finance":
        url = context.user_data.get("sheet_url")
        if not url:
            await query.edit_message_text(
                "⚠️ Сначала подключите таблицу: /setup и укажите ссылку."
            )
            return STATE_MAIN_MENU

        finance_ws, _ = open_finance_and_plans(url)
        records = finance_ws.get_all_records()
        balances = {}
        for row in records:
            bank = row.get("Банк") or "Неизвестно"
            raw = row.get("Сумма", 0)
            try:
                amt = float(raw)
            except (TypeError, ValueError):
                amt = float(str(raw).replace(",", "."))
            balances[bank] = balances.get(bank, 0.0) + amt

        total = sum(balances.values())
        lines = [f"• {b}: {balances[b]:.2f}" for b in balances]
        text = "💰 *Текущий баланс по банкам:*\n" + "\n".join(lines)
        text += f"\n\n*Общая сумма:* {total:.2f}"

        # заменяем меню на результат
        await query.edit_message_text(text, parse_mode="Markdown")
        return STATE_MAIN_MENU

    # 2.5 — остальные пункты (заглушки)
    responses = {
        "operations":    "📝 «Операции» в разработке…",
        "classification":"🏷 «Классификация» в разработке…",
        "plans":         "🗓 «Планы» в разработке…",
        "add_bank":      "➕ «Добавить Банк» в разработке…",
        "del_bank":      "➖ «Удалить Банк» в разработке…",
        "edit_table":    "✏️ «Изменить таблицу» в разработке…",
        "change_tariff": "💳 «Поменять тариф» в разработке…",
        "show_sheet":    "🔗 «Показать таблицу» в разработке…",
        "support":       "💬 «Поддержка» в разработке…",
    }
    text = responses.get(choice, "⚠️ Неизвестный пункт меню.")
    await query.edit_message_text(text)
    return STATE_MAIN_MENU

def register_menu_handlers(app):
    """# 3 — Регистрация меню."""
    app.add_handler(CommandHandler("menu", show_main_menu))
    app.add_handler(CallbackQueryHandler(handle_menu_selection, pattern=r"^menu:"))
