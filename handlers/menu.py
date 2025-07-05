# handlers/menu.py

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes
from services.sheets_service import open_finance_and_plans
from utils.constants import STATE_OP_MENU  # ваше состояние после /add

def _build_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Финансы",         callback_data="menu:finance"),
         InlineKeyboardButton("📝 Операции",        callback_data="menu:operations")],
        [InlineKeyboardButton("🏷 Классификация",   callback_data="menu:classification"),
         InlineKeyboardButton("🗓 Планы",           callback_data="menu:plans")],
        [InlineKeyboardButton("➕ Добавить Банк",   callback_data="menu:add_bank"),
         InlineKeyboardButton("➖ Удалить Банк",    callback_data="menu:del_bank")],
        [InlineKeyboardButton("✏️ Изменить таблицу", callback_data="menu:edit_table"),
         InlineKeyboardButton("💳 Поменять тариф",   callback_data="menu:change_tariff")],
        [InlineKeyboardButton("🔗 Показать таблицу", callback_data="menu:show_sheet"),
         InlineKeyboardButton("💬 Поддержка",        callback_data="menu:support")],
        [InlineKeyboardButton("🔙 Назад",            callback_data="menu:back")],
    ])

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отображает главное меню (новым или редактирует текущее сообщение)."""
    kb = _build_main_kb()
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "Выберите раздел меню:", reply_markup=kb
        )
    else:
        await update.message.reply_text(
            "Выберите раздел меню:", reply_markup=kb
        )
    return STATE_OP_MENU

async def handle_menu_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает все menu:* коллбэки, в том числе Финансы."""
    query = update.callback_query
    await query.answer()  # скрываем «часики»

    data = query.data  # например "menu:finance"

    # открыть/перерисовать меню
    if data == "menu:open":
        await show_main_menu(update, context)
        return STATE_OP_MENU

    # назад — вернуть на этап /add
    if data == "menu:back":
        from handlers.operations import go_main_menu
        return await go_main_menu(update, context)

    # финансы — посчитать и показать баланс
    if data == "menu:finance":
        await query.answer(text="Получаю баланс…", show_alert=False)

        url = context.user_data.get("sheet_url")
        if not url:
            # если не подключена таблица — перерисовать меню
            await query.edit_message_text(
                "⚠️ Сначала подключите таблицу: отправьте /setup и вставьте ссылку.",
                reply_markup=_build_main_kb()
            )
            return STATE_OP_MENU

        # попробуем считать записи
        try:
            ws, _ = open_finance_and_plans(url)
            records = ws.get_all_records()
        except Exception as e:
            await query.edit_message_text(
                f"❌ Ошибка при получении данных:\n{e}",
                reply_markup=_build_main_kb()
            )
            return STATE_OP_MENU

        # группировка по банкам
        balances = {}
        for row in records:
            bank = row.get("Банк") or "Неизвестно"
            raw  = row.get("Сумма", 0)
            try:
                amt = float(raw)
            except (TypeError, ValueError):
                amt = float(str(raw).replace(",", "."))
            balances[bank] = balances.get(bank, 0.0) + amt

        total = sum(balances.values())
        lines = [f"• {b}: {balances[b]:.2f}" for b in balances]
        text = "💰 *Текущий баланс по банкам:*\n" + "\n".join(lines)
        text += f"\n\n*Общая сумма:* {total:.2f}"

        # выводим в том же сообщении с кнопкой «Назад»
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="menu:open")]
            ])
        )
        return STATE_OP_MENU

    # остальные пункты — заглушки
    responses = {
        "menu:operations":    "📝 Раздел «Операции» в разработке…",
        "menu:classification":"🏷 Раздел «Классификация» в разработке…",
        "menu:plans":         "🗓 Раздел «Планы» в разработке…",
        "menu:add_bank":      "➕ Раздел «Добавить Банк» в разработке…",
        "menu:del_bank":      "➖ Раздел «Удалить Банк» в разработке…",
        "menu:edit_table":    "✏️ Раздел «Изменить таблицу» в разработке…",
        "menu:change_tariff": "💳 Раздел «Поменять тариф» в разработке…",
        "menu:show_sheet":    "🔗 Раздел «Показать таблицу» в разработке…",
        "menu:support":       "💬 Раздел «Поддержка» в разработке…",
    }
    text = responses.get(data, "⚠️ Неизвестный пункт меню.")
    await query.edit_message_text(text, reply_markup=_build_main_kb())
    return STATE_OP_MENU

def register_menu_handlers(app):
    """Регистрирует глобальный /menu и все menu:* коллбэки."""
    app.add_handler(CommandHandler("menu", show_main_menu))
    app.add_handler(CallbackQueryHandler(handle_menu_selection, pattern=r"^menu:"))
