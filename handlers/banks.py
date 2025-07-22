# handlers/banks.py — этап 3: первоначальное заполнение банков

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
    Показывает текущее состояние банков и кнопки для добавления/пропуска.
    """
    # 1) Инициализируем кэш отложенных банков
    context.user_data.setdefault("pending_banks", [])

    # 2) Поддержка редактирования при callback_query
    query = update.callback_query
    if query:
        await query.answer()

    # 3) Проверяем подключение таблицы
    if "sheet_url" not in context.user_data:
        if query:
            await query.edit_message_text("⚠️ Сначала подключите таблицу — /setup")
        else:
            await update.effective_message.reply_text("⚠️ Сначала подключите таблицу — /setup")
        return ConversationHandler.END

    # 4) Читаем уже добавленные в таблицу банки
    finance_ws, _ = open_finance_and_plans(context.user_data["sheet_url"])
    existing = finance_ws.col_values(3)[1:]
    unique = sorted(set(existing))

    # 5) Готовим список новых (отложенных) банков с суммами
    pending = context.user_data["pending_banks"]
    pending_names = [e["bank"] for e in pending]
    pending_lines = [f"• {e['bank']}: {e['amount']:.2f}" for e in pending]

    # 6) Собираем текст сообщения
    text = f"🏦 Ваши текущие банки: {', '.join(unique) if unique else 'нет'}"
    if pending:
        text += "\n\nНовые Банки:\n" + "\n".join(pending_lines)
    text += "\n\nВыберите банк или нажмите «▶️ Продолжить без заполнения банков»:"

    # 7) Клавиатура
    keyboard = [
        [InlineKeyboardButton("Сбер",     callback_data="bank_Сбер"),
         InlineKeyboardButton("Тинькофф", callback_data="bank_Тинькофф")],
        [InlineKeyboardButton("Альфа",    callback_data="bank_Альфа"),
         InlineKeyboardButton("МКБ",      callback_data="bank_МКБ")],
        [InlineKeyboardButton("Нал",      callback_data="bank_Нал"),
         InlineKeyboardButton("ВТБ",      callback_data="bank_ВТБ")],
        [InlineKeyboardButton("Свой банк", callback_data="bank_custom")],
        [InlineKeyboardButton("▶️ Продолжить без заполнения банков", callback_data="skip_add")],
        [InlineKeyboardButton("📞 Поддержка", callback_data="support")],
    ]
    # Если есть отложенные — добавляем кнопку "Готово"
    if pending:
        keyboard.append([InlineKeyboardButton("✅ Готово", callback_data="finish_setup")])

    # 8) Выводим или редактируем сообщение
    markup = InlineKeyboardMarkup(keyboard)
    if query:
        await query.edit_message_text(text, reply_markup=markup)
    else:
        await update.effective_message.reply_text(text, reply_markup=markup)

    return STATE_BANK_MENU


# —————— 3.2 Обработка выбора из главного меню ——————

async def handle_bank_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    # Помощь
    if data == "support":
        await query.message.reply_text("📧 Для поддержки: financebot365@gmail.com")
        return STATE_BANK_MENU

    # Пропустить добавление
    if data == "skip_add":
        ws, _ = open_finance_and_plans(context.user_data["sheet_url"])
        # Если уже есть записи в таблице или отложенные банки — завершаем
        if len(ws.col_values(3)) > 1 or context.user_data.get("pending_banks"):
            await query.edit_message_text(
                "▶️ Продолжаем без заполнения банков.\n\n"
                "Теперь вы можете вводить операции командой /add"
            )
            # Очищаем отложенные (если были)
            context.user_data["pending_banks"].clear()
            return ConversationHandler.END
        else:
            await query.message.reply_text("⚠️ Добавьте хотя бы один банк.")
            return STATE_BANK_MENU

    # Финиш: записать все отложенные банки
    if data == "finish_setup":
        ws, _ = open_finance_and_plans(context.user_data["sheet_url"])
        pending = context.user_data.get("pending_banks", [])
        for entry in pending:
            ws.append_row(entry["row_data"], value_input_option="USER_ENTERED")
        lines = [f"• {e['bank']}: {e['amount']:.2f}" for e in pending] or ["– ничего –"]
        summary = "\n".join(lines)
        await query.edit_message_text(
            "🎉 Банки успешно добавлены:\n" + summary + "\n\n"
            "Теперь вы можете вводить операции командой /add"
        )
        context.user_data["pending_banks"].clear()
        return ConversationHandler.END

    # Пользовательский банк
    if data == "bank_custom":
        await query.edit_message_text("✏️ Введите название вашего банка:")
        return STATE_BANK_CUSTOM

    # Выбор одного из популярных
    if data.startswith("bank_"):
        bank = data.split("_", 1)[1]
        context.user_data["bank_entry"] = {"bank": bank}
        await query.edit_message_text(f"💰 Введите баланс для <b>{bank}</b>:", parse_mode="HTML")
        return STATE_BANK_AMOUNT

    # Любая другая ситуация
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
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "add_more":
        return await show_banks_menu(update, context)

    if data == "edit_entry":
        keyboard = [
            [InlineKeyboardButton("Изменить банк", callback_data="edit_bank"),
             InlineKeyboardButton("Изменить сумму", callback_data="edit_amount")],
        ]
        await query.edit_message_text("✏️ Что вы хотите изменить?", reply_markup=InlineKeyboardMarkup(keyboard))
        return STATE_BANK_EDIT_CHOICE

    if data == "finish_setup":
        # 3.1 Получаем ссылку на Google Sheets
        ws, _ = open_finance_and_plans(context.user_data["sheet_url"])
        # 3.2 Записываем в таблицу все отложенные банки
        pending = context.user_data.get("pending_banks", [])
        for entry in pending:
           ws.append_row(entry["row_data"], value_input_option="USER_ENTERED")
        # 3.3 Формируем текст-отчёт
        lines = [f"• {e['bank']}: {e['amount']:.2f}" for e in pending] or ["– ничего –"]
        summary = "\n".join(lines)
        # 3.4 Отправляем пользователю результат и закрываем Conversation
        await query.edit_message_text(
            "🎉 Банки успешно добавлены:\n" + summary + "\n\n"
            "Теперь вы можете вводить операции командой /add")
        # 3.5 Очищаем кэш
        context.user_data["pending_banks"].clear()
        return ConversationHandler.END


    if data == "skip_add":
        return await handle_bank_option(update, context)

    await query.message.reply_text("⚠️ Пожалуйста, используйте кнопки.")
    return STATE_BANK_OPTION


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

def register_banks_handlers(app):
    conv = ConversationHandler(
        entry_points=[CommandHandler("banks", show_banks_menu)],
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
