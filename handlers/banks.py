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
    if "sheet_url" not in context.user_data:
        await update.effective_message.reply_text("⚠️ Сначала подключите таблицу — /setup")
        return ConversationHandler.END

    # Читаем из таблицы все уже добавленные банки
    finance_ws, _ = open_finance_and_plans(context.user_data["sheet_url"])
    existing = finance_ws.col_values(3)[1:]  # колонка «Банк», пропускаем заголовок
    unique = sorted(set(existing))
    current = ", ".join(unique) if unique else "нет"

    text = (
        f"🏦 Ваши текущие банки: {current}\n\n"
        "Выберите банк или нажмите «▶️ Продолжить без заполнения банков»:"
    )
    keyboard = [
        [
            InlineKeyboardButton("Сбер",     callback_data="bank_Сбер"),
            InlineKeyboardButton("Тинькофф", callback_data="bank_Тинькофф"),
        ],
        [
            InlineKeyboardButton("Альфа", callback_data="bank_Альфа"),
            InlineKeyboardButton("МКБ",   callback_data="bank_МКБ"),
        ],
        [
            InlineKeyboardButton("Нал", callback_data="bank_Нал"),
            InlineKeyboardButton("ВТБ", callback_data="bank_ВТБ"),
        ],
        [InlineKeyboardButton("Свой банк", callback_data="bank_custom")],
        [InlineKeyboardButton("▶️ Продолжить без заполнения банков", callback_data="skip_add")],
        [InlineKeyboardButton("📞 Поддержка", callback_data="support")],
    ]
    await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return STATE_BANK_MENU


# —————— 3.2 Обработка выбора из главного меню ——————

async def handle_bank_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    # Поддержка
    if data == "support":
        await query.message.reply_text("📧 Для поддержки: financebot365@gmail.com")
        return STATE_BANK_MENU

    # Пропустить без добавления — только если есть хотя бы одна строка
    if data == "skip_add":
        ws, _ = open_finance_and_plans(context.user_data["sheet_url"])
        if len(ws.col_values(3)) > 1:
            await query.edit_message_text("▶️ Продолжаем без заполнения банков.")
            return ConversationHandler.END
        else:
            await query.message.reply_text("⚠️ Добавьте хотя бы один банк.")
            return STATE_BANK_MENU

    # Свой банк — переходим к вводу названия
    if data == "bank_custom":
        await query.edit_message_text("✏️ Введите название вашего банка:")
        return STATE_BANK_CUSTOM

    # Выбор готового банка
    if data.startswith("bank_"):
        bank = data.split("_", 1)[1]
        context.user_data["bank_entry"] = {"bank": bank}
        await query.edit_message_text(f"💰 Введите баланс для <b>{bank}</b>:", parse_mode="HTML")
        return STATE_BANK_AMOUNT

    # Непредусмотренный случай
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

    # Открываем лист и вставляем строку
    ws, _ = open_finance_and_plans(context.user_data["sheet_url"])

    # Московское время
    now = datetime.now(pytz.timezone("Europe/Moscow"))
    year = now.year
    month = {
        1:"Январь",2:"Февраль",3:"Март",4:"Апрель",
        5:"Май",6:"Июнь",7:"Июль",8:"Август",
        9:"Сентябрь",10:"Октябрь",11:"Ноябрь",12:"Декабрь"
    }[now.month]
    date_str = now.strftime("%d.%m.%Y")

    # Определяем тип операции
    operation = "Пополнение" if amount >= 0 else "Трата"

    row = [
        year,
        month,
        entry["bank"],
        operation,
        date_str,
        f"{amount:.2f}".replace(".", ","),  # сохраняем с 2 знаками
        "Старт",
        "-",
    ]
    # Добавляем строку
    ws.append_row(row, value_input_option="USER_ENTERED")

    # Запоминаем индекс вставленной строки для возможного редактирования
    entry_row = len(ws.col_values(1))  # номер последней строки
    context.user_data["bank_entry"]["row"] = entry_row

    # Добавляем в список новых банков
    context.user_data.setdefault("new_banks", []).append(entry.copy())

    # Предлагаем опции: Добавить ещё, Изменить, Готово
    keyboard = [
        [
            InlineKeyboardButton("➕ Добавить ещё банк",    callback_data="add_more"),
            InlineKeyboardButton("✏️ Изменить последнюю", callback_data="edit_entry"),
        ],
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

    # Добавить ещё — возвращаемся в главное меню
    if data == "add_more":
        return await show_banks_menu(update, context)

    # Редактировать последнюю запись
    if data == "edit_entry":
        # Предлагаем что редактировать
        keyboard = [
            [
                InlineKeyboardButton("Изменить банк", callback_data="edit_bank"),
                InlineKeyboardButton("Изменить сумму", callback_data="edit_amount"),
            ]
        ]
        await query.edit_message_text("✏️ Что вы хотите изменить?", reply_markup=InlineKeyboardMarkup(keyboard))
        return STATE_BANK_EDIT_CHOICE

    # Закончить этап
    if data == "finish_setup":
        # Формируем список только что добавленных
        lines = []
        for e in context.user_data.get("new_banks", []):
            amt = f"{e['amount']:.2f}"
            lines.append(f"• {e['bank']}: {amt}")
        summary = "\n".join(lines) or "– ничего –"
        await query.edit_message_text(
            "🎉 Банки успешно добавлены:\n" + summary
        )
        return ConversationHandler.END

    # Пропустить — то же, что finish
    if data == "skip_add":
        return await handle_bank_option(update, context)

    # Нераспознанное
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

    # Возврат в опции
    return await handle_bank_option(update, context)


# —————— 3.7 Ввод нового значения для редактирования ——————

async def handle_bank_edit_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    field = context.user_data.get("editing_field")
    entry = context.user_data["bank_entry"]
    ws, _ = open_finance_and_plans(context.user_data["sheet_url"])
    row = entry["row"]

    if field == "bank":
        # Обновляем только название банка
        entry["bank"] = text
        ws.update_cell(row, 3, text)

    elif field == "amount":
        # Парсим новое значение
        try:
            amount = float(text.replace(",", "."))
        except ValueError:
            await update.message.reply_text("⚠️ Введите число, например: 1000 или -456,67")
            return STATE_BANK_EDIT_INPUT

        # Сохраняем в entry и в таблицу как число
        entry["amount"] = amount
        ws.update_cell(row, 6, amount)  # передаём float, Google Sheets сохранит число

    # Дублируем изменения в списке new_banks, чтобы итоговый отчёт брал обновлённые данные
    for e in context.user_data.get("new_banks", []):
        if e.get("row") == row:
            e["bank"]   = entry["bank"]
            e["amount"] = entry["amount"]

    # Форматируем сумму для показа пользователю
    formatted_amount = f"{entry['amount']:.2f}".replace(".", ",")

    # Убираем флаг редактирования
    context.user_data.pop("editing_field", None)

    # Снова показываем опции
    keyboard = [
        [
            InlineKeyboardButton("➕ Добавить ещё банк",    callback_data="add_more"),
            InlineKeyboardButton("✏️ Изменить последнюю", callback_data="edit_entry"),
        ],
        [InlineKeyboardButton("✅ Готово",               callback_data="finish_setup")],
    ]
    # Теперь показываем и банк, и актуальную сумму
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
