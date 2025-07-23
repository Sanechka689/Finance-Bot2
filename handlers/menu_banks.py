# handlers/menu_banks.py

from datetime import datetime
import pytz

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import (
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters,
)
from utils.constants import (
    STATE_BANK_MENU,
    STATE_BANK_CUSTOM,
    STATE_BANK_AMOUNT,
    STATE_BANK_OPTION,
    STATE_BANK_EDIT_CHOICE,
    STATE_BANK_EDIT_INPUT,
)
from services.sheets_service import open_finance_and_plans


# —————— 3.1 Главное меню банков ——————

async def show_banks_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает меню добавления банков.
    """
    # 1) Инициализируем кэш новых банков
    context.user_data.setdefault("pending_banks", [])

    # 2) Поддержка callback_query (редактирование сообщения)
    query = update.callback_query
    if query:
        await query.answer()

    # 3) Проверка подключения таблицы
    if "sheet_url" not in context.user_data:
        if query:
            await query.edit_message_text("⚠️ Сначала подключите таблицу — /setup")
        else:
            await update.effective_message.reply_text("⚠️ Сначала подключите таблицу — /setup")
        return ConversationHandler.END

    # 4) Получаем уже добавленные в Google Sheets банки
    finance_ws, _ = open_finance_and_plans(context.user_data["sheet_url"])
    existing = finance_ws.col_values(3)[1:]
    unique = sorted(set(existing))

    # 5) Готовим список отложенных (новых) банков
    pending = context.user_data["pending_banks"]
    pending_lines = [f"• {e['bank']}: {e['amount']:.2f}" for e in pending]

    # 6) Строим текст сообщения
    text = f"🏦 Ваши текущие банки: {', '.join(unique) if unique else 'нет'}"
    if pending:
        text += "\n\nНовые Банки:\n" + "\n".join(pending_lines)
    text += "\n\nВыберите банк:"

    # 7) Формируем клавиатуру (убрали skip_add, добавили «Назад»)
    keyboard = [
        [InlineKeyboardButton("Сбер",     callback_data="bank_Сбер"),
         InlineKeyboardButton("Тинькофф", callback_data="bank_Тинькофф")],
        [InlineKeyboardButton("Альфа",    callback_data="bank_Альфа"),
         InlineKeyboardButton("МКБ",      callback_data="bank_МКБ")],
        [InlineKeyboardButton("Нал",      callback_data="bank_Нал"),
         InlineKeyboardButton("ВТБ",      callback_data="bank_ВТБ")],
        [InlineKeyboardButton("Свой банк", callback_data="bank_custom")],
    ]
    # 7.1) Кнопка «Готово», если есть pending
    if pending:
        keyboard.append([InlineKeyboardButton("✅ Готово", callback_data="finish_setup")])
    # 7.2) Кнопка «Назад» — возвращение в главное меню
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="menu:open")])

    markup = InlineKeyboardMarkup(keyboard)

    # 8) Выводим или редактируем сообщение
    if query:
        await query.edit_message_text(text, reply_markup=markup)
    else:
        await update.effective_message.reply_text(text, reply_markup=markup)

    return STATE_BANK_MENU



# —————— 3.2 Обработка выбора из главного меню ——————

async def handle_bank_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from handlers.menu import show_main_menu

    query = update.callback_query
    await query.answer()
    data = query.data

    # Назад → в главное меню
    if data == "menu:open":
        await show_main_menu(update, context)
        return ConversationHandler.END

    # Поддержка
    if data == "support":
        await query.edit_message_text("📧 Для поддержки: financebot365@gmail.com")
        return STATE_BANK_MENU

    # Готово → записываем все pending, закрываем текущее окно и открываем главное меню
    if data == "finish_setup":
        # 1) Записываем в Google Sheets
        ws, _ = open_finance_and_plans(context.user_data["sheet_url"])
        pending = context.user_data.get("pending_banks", [])
        for entry in pending:
            ws.append_row(entry["row_data"], value_input_option="USER_ENTERED")

        # 2) Формируем отчёт по всем добавленным банкам
        summary = "\n".join(f"• {e['bank']}: {e['amount']:.2f}" for e in pending) or "– ничего –"

        # 3) Затираем меню банков и выводим отчёт
        await query.edit_message_text(f"🎉 Банки успешно добавлены:\n{summary}")

        # 4) Очищаем кэш
        context.user_data["pending_banks"].clear()

        from handlers.menu import _build_main_kb

        # 5) Показываем главное меню
        await show_main_menu(update, context)
        return ConversationHandler.END

    # Выбор собственного банка
    if data == "bank_custom":
        await query.edit_message_text("✏️ Введите название вашего банка:")
        return STATE_BANK_CUSTOM

    # Выбор из популярных
    if data.startswith("bank_"):
        bank = data.split("_", 1)[1]
        context.user_data["bank_entry"] = {"bank": bank}
        await query.edit_message_text(f"💰 Введите баланс для <b>{bank}</b>:", parse_mode="HTML")
        return STATE_BANK_AMOUNT

    # Любой другой ввод
    await query.message.reply_text("⚠️ Пожалуйста, используйте кнопки.")
    return STATE_BANK_MENU


# —————— 3.3 Обработка ввода названия своего банка ——————

async def handle_bank_custom(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    bank = update.message.text.strip()
    context.user_data["bank_entry"] = {"bank": bank}
    await update.message.reply_text(f"💰 Введите баланс для <b>{bank}</b>:", parse_mode="HTML")
    return STATE_BANK_AMOUNT


# —————— 3.4 Обработка ввода суммы и запись в таблицу ——————

async def handle_bank_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        amount = float(text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("⚠️ Введите число, например: 1000 или -456,67")
        return STATE_BANK_AMOUNT

    entry = context.user_data["bank_entry"]
    entry["amount"] = amount

        # Собираем данные операции
    now = datetime.now(pytz.timezone("Europe/Moscow"))
    year = now.year
    month = {
        1:"Январь",2:"Февраль",3:"Март",4:"Апрель",
        5:"Май",6:"Июнь",7:"Июль",8:"Август",
        9:"Сентябрь",10:"Октябрь",11:"Ноябрь",12:"Декабрь"
    }[now.month]
    date_str = now.strftime("%d.%m.%Y")
    operation = "Пополнение" if amount >= 0 else "Трата"

    row = [
        year, month, entry["bank"], operation,
        date_str, f"{amount:.2f}".replace(".", ","), "Старт", "-"
    ]
    # Вместо прямой записи — кладём в кэш
    pending = context.user_data["pending_banks"]
    pending.append({
        "bank": entry["bank"],
        "amount": amount,
        "row_data": row
    })
    # Запоминаем индекс этой записи для будущего редактирования
    context.user_data["bank_entry"]["index"] = len(pending) - 1

    keyboard = [
        [InlineKeyboardButton("➕ Добавить ещё банк",    callback_data="add_more"),
         InlineKeyboardButton("✏️ Изменить последнюю", callback_data="edit_entry")],
        [InlineKeyboardButton("✅ Готово",               callback_data="finish_setup")],
    ]
    await update.message.reply_text(
        f"✅ {operation} банка <b>{entry['bank']}</b> — <b>{amount:.2f}</b>.",
        parse_mode="HTML",
    )
    await update.message.reply_text("Что дальше?", reply_markup=InlineKeyboardMarkup(keyboard))
    return STATE_BANK_OPTION


# —————— 3.5 Обработка нажатий в меню опций ——————

async def handle_bank_option(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from handlers.menu import show_main_menu

    query = update.callback_query
    await query.answer()
    data = query.data

    # Добавить ещё банк
    if data == "add_more":
        return await show_banks_menu(update, context)

    # Изменить последнюю запись
    if data == "edit_entry":
        keyboard = [
            [InlineKeyboardButton("Изменить банк",  callback_data="edit_bank"),
             InlineKeyboardButton("Изменить сумму", callback_data="edit_amount")],
        ]
        await query.edit_message_text("✏️ Что вы хотите изменить?", reply_markup=InlineKeyboardMarkup(keyboard))
        return STATE_BANK_EDIT_CHOICE

    # Готово — срабатывает и в STATE_BANK_MENU, и в STATE_BANK_OPTION
    if data == "finish_setup":
        # 1) Пишем все отложенные банки в Google Sheets
        ws, _ = open_finance_and_plans(context.user_data["sheet_url"])
        pending = context.user_data.get("pending_banks", [])
        for entry in pending:
            ws.append_row(entry["row_data"], value_input_option="USER_ENTERED")

        # 2) Формируем отчёт по всем банкам
        summary = "\n".join(f"• {e['bank']}: {e['amount']:.2f}" for e in pending) or "– ничего –"

        # 3) Закрываем текущее окно и выводим отчёт
        await query.edit_message_text(f"🎉 Банки успешно добавлены:\n{summary}")

        # 4) Очищаем кэш
        context.user_data["pending_banks"].clear()

        # 5) Открываем главное меню
        await show_main_menu(update, context)
        return ConversationHandler.END

    # Ввод своего банка
    if data == "bank_custom":
        await query.edit_message_text("✏️ Введите название вашего банка:")
        return STATE_BANK_CUSTOM

    # Выбор популярного банка
    if data.startswith("bank_"):
        bank = data.split("_", 1)[1]
        context.user_data["bank_entry"] = {"bank": bank}
        await query.edit_message_text(f"💰 Введите баланс для <b>{bank}</b>:", parse_mode="HTML")
        return STATE_BANK_AMOUNT

    # Всё остальное
    await query.message.reply_text("⚠️ Пожалуйста, используйте кнопки.")
    return STATE_BANK_MENU


# —————— 3.6 Выбор поля для редактирования ——————

async def handle_bank_edit_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    entry = context.user_data["bank_entry"]
    if data == "edit_bank":
        await query.edit_message_text("✏️ Введите новое название банка:")
        context.user_data["editing_field"] = "bank"
        return STATE_BANK_EDIT_INPUT
    if data == "edit_amount":
        await query.edit_message_text("✏️ Введите новую сумму:")
        context.user_data["editing_field"] = "amount"
        return STATE_BANK_EDIT_INPUT

    return await handle_bank_option(update, context)


# —————— 3.7 Ввод нового значения для редактирования ——————

async def handle_bank_edit_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    field = context.user_data.get("editing_field")
    entry = context.user_data["bank_entry"]
    
    # Работаем с последней отложенной записью в кэше
    pending = context.user_data["pending_banks"]
    index = context.user_data["bank_entry"]["index"]
    entry_cache = pending[index]

    if field == "bank":
        entry_cache["bank"] = text
        # столбец 3 в row_data
        entry_cache["row_data"][2] = text
        # Обновляем контекст для consistency
        context.user_data["bank_entry"]["bank"] = text

    elif field == "amount":
        try:
            amount = float(text.replace(",", "."))
        except ValueError:
            await update.message.reply_text("⚠️ Введите число, например: 1000 или -456,67")
            return STATE_BANK_EDIT_INPUT
        entry_cache["amount"] = amount
        # Обновляем сумму в кэше
        entry_cache["amount"] = amount
        # Пересчитываем тип операции: Пополнение или Трата
        operation = "Пополнение" if amount >= 0 else "Трата"
        entry_cache["row_data"][3] = operation  # индекс 3 — это столбец "Операция"
        # Обновляем форматированную сумму в кэше
        formatted = f"{amount:.2f}".replace(".", ",")
        entry_cache["row_data"][5] = formatted  # индекс 5 — это столбец "Сумма"
        # Обновляем контекстовую запись тоже
        context.user_data["bank_entry"]["amount"] = amount

    # Убираем флаг редактирования
    context.user_data.pop("editing_field", None)

    # Ответ пользователю и возвращение меню опций
    formatted_amount = f"{entry_cache['amount']:.2f}".replace(".", ",")
    keyboard = [
        [InlineKeyboardButton("➕ Добавить ещё банк",    callback_data="add_more"),
         InlineKeyboardButton("✏️ Изменить последнюю", callback_data="edit_entry")],
        [InlineKeyboardButton("✅ Готово",               callback_data="finish_setup")],
    ]
    await update.message.reply_text(
        f"✅ Запись обновлена: {entry_cache['bank']} — {formatted_amount}"
    )
    await update.message.reply_text("Что дальше?", reply_markup=InlineKeyboardMarkup(keyboard))
    return STATE_BANK_OPTION


    for e in context.user_data.get("new_banks", []):
        if e.get("row") == row:
            e["bank"] = entry["bank"]
            e["amount"] = entry["amount"]

    formatted_amount = f"{entry['amount']:.2f}".replace(".", ",")

    context.user_data.pop("editing_field", None)

    keyboard = [
        [InlineKeyboardButton("➕ Добавить ещё банк",    callback_data="add_more"),
         InlineKeyboardButton("✏️ Изменить последнюю", callback_data="edit_entry")],
        [InlineKeyboardButton("✅ Готово",               callback_data="finish_setup")],
    ]
    await update.message.reply_text(
        f"✅ Запись обновлена: {entry['bank']} — {formatted_amount}"
    )
    await update.message.reply_text("Что дальше?", reply_markup=InlineKeyboardMarkup(keyboard))
    return STATE_BANK_OPTION


# —————— 3.8 Регистрация хендлера ——————

def register_menu_banks_handlers(app):
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("banks",    show_banks_menu),
            CallbackQueryHandler(show_banks_menu, pattern=r"^menu:add_bank$")],
        states={
            STATE_BANK_MENU:        [CallbackQueryHandler(handle_bank_menu)],
            STATE_BANK_CUSTOM:      [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bank_custom)],
            STATE_BANK_AMOUNT:      [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bank_amount)],
            STATE_BANK_OPTION:      [CallbackQueryHandler(handle_bank_option)],
            STATE_BANK_EDIT_CHOICE: [CallbackQueryHandler(handle_bank_edit_choice)],
            STATE_BANK_EDIT_INPUT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bank_edit_input)],
        },
        fallbacks=[],
        allow_reentry=True,
    )
    app.add_handler(conv)
