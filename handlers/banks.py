# handlers/banks.py — этап 3: первоначальное заполнение банков

from datetime import datetime
import calendar
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
    STATE_BANK_CHOOSE,
    STATE_BANK_CUSTOM,
    STATE_BANK_AMOUNT,
    STATE_BANK_OPTION,
)
from services.sheets_service import open_finance_and_plans

async def show_banks_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    3.7 Показать меню банков и существующие записи
    """
    # Проверяем, что таблица подключена
    if "sheet_url" not in context.user_data:
        await update.effective_message.reply_text("⚠️ Сначала подключите таблицу — /setup")
        return ConversationHandler.END

    # Получаем список уже добавленных банков
    finance_ws, _ = open_finance_and_plans(context.user_data["sheet_url"])
    banks = finance_ws.col_values(3)[1:]  # колонка «Банк», пропускаем заголовок
    unique_banks = sorted(set(banks))
    banks_list = ", ".join(unique_banks) if unique_banks else "нет"

    text = (
        f"🏦 Ваши текущие банки: {banks_list}\n\n"
        "Выберите банк или нажмите «▶️ Продолжить»:"
    )
    keyboard = [
        [InlineKeyboardButton("Сбер",     callback_data="bank_Сбер"),
         InlineKeyboardButton("Тинькофф", callback_data="bank_Тинькофф")],
        [InlineKeyboardButton("Альфа",    callback_data="bank_Альфа"),
         InlineKeyboardButton("МКБ",      callback_data="bank_МКБ")],
        [InlineKeyboardButton("Нал",      callback_data="bank_Нал"),
         InlineKeyboardButton("ВТБ",      callback_data="bank_ВТБ")],
        [InlineKeyboardButton("Свой вариант", callback_data="bank_custom")],
        [
         InlineKeyboardButton("➕ Добавить ещё", callback_data="add_more"),
         InlineKeyboardButton("▶️ Продолжить",   callback_data="skip_add"),
        ],
        [InlineKeyboardButton("Готово",          callback_data="finish_setup")],
        [InlineKeyboardButton("📞 Поддержка",    callback_data="support")],
    ]
    await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return STATE_BANK_CHOOSE

async def handle_bank_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    3.8 Логика меню банков: поддержка, переходы, «свой банк»
    """
    query = update.callback_query
    await query.answer()
    data = query.data

    # Поддержка
    if data == "support":
        await query.message.reply_text("📧 Для поддержки: financebot365@gmail.com")
        return STATE_BANK_CHOOSE

    # Продолжить без новых — только если есть хотя бы один
    if data == "skip_add":
        finance_ws, _ = open_finance_and_plans(context.user_data["sheet_url"])
        if len(finance_ws.col_values(3)) > 1:
            await query.edit_message_text("▶️ Продолжаем далее без добавления новых банков.")
            return ConversationHandler.END
        else:
            await query.message.reply_text("⚠️ Добавьте хотя бы один банк.")
            return STATE_BANK_CHOOSE

    # Завершить этап
    if data == "finish_setup":
        await query.edit_message_text("🎉 Первоначальное заполнение банков завершено!")
        return ConversationHandler.END

    # Добавить ещё — перезапускаем меню
    if data == "add_more":
        await query.edit_message_text("➕ Добавление нового банка:")
        return await show_banks_menu(update, context)

    # Свой вариант
    if data == "bank_custom":
        await query.edit_message_text("✏️ Введите название вашего банка:")
        return STATE_BANK_CUSTOM

    # Выбор готового банка
    if data.startswith("bank_"):
        bank = data.split("_", 1)[1]
        context.user_data["bank"] = bank
        await query.edit_message_text(
            f"💰 Введите стартовый баланс для <b>{bank}</b>:",
            parse_mode="HTML",
        )
        return STATE_BANK_AMOUNT

    # Остальные случаи
    await query.message.reply_text("⚠️ Пожалуйста, используйте кнопки.")
    return STATE_BANK_CHOOSE

async def handle_bank_custom(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    3.8а Обработка ввода названия своего банка
    """
    bank = update.message.text.strip()
    context.user_data["bank"] = bank
    await update.message.reply_text(
        f"💰 Введите стартовый баланс для <b>{bank}</b>:",
        parse_mode="HTML",
    )
    return STATE_BANK_AMOUNT

async def handle_bank_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    3.9 Обработка ввода суммы — и различие Пополнение/Трата
    """
    text = update.message.text.strip()
    try:
        amount = float(text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("⚠️ Введите число, например: 1000 или -456,67")
        return STATE_BANK_AMOUNT

    # Определяем тип операции по знаку
    operation = "Пополнение" if amount >= 0 else "Трата"
    # Форматируем сумму с двумя десятичными
    amount_str = f"{amount:.2f}".replace(".", ",")

    # Достаем таблицу
    finance_ws, _ = open_finance_and_plans(context.user_data["sheet_url"])

    # Дата по Москве
    now = datetime.now(pytz.timezone("Europe/Moscow"))
    year = now.year
    month = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
        5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
        9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
    }[now.month]
    date_str = now.strftime("%d.%m.%Y")

    # Сборка строки
    row = [
        year,
        month,
        context.user_data["bank"],
        operation,
        date_str,
        amount_str,
        "Старт",
        "-",
    ]
    finance_ws.append_row(row, value_input_option="USER_ENTERED")

    # Предлагаем дальше
    keyboard = [
        [
            InlineKeyboardButton("➕ Добавить ещё", callback_data="add_more"),
            InlineKeyboardButton("Готово",         callback_data="finish_setup"),
        ]
    ]
    await update.message.reply_text(
        f"✅ {operation} банка <b>{context.user_data['bank']}</b> — <b>{amount_str}</b>.",
        parse_mode="HTML",
    )
    # Переходим в опции
    return STATE_BANK_OPTION

def register_banks_handlers(app):
    """
    Регистрируем ConversationHandler для этапа банков (/banks)
    """
    conv = ConversationHandler(
        entry_points=[CommandHandler("banks", show_banks_menu)],
        states={
            STATE_BANK_CHOOSE: [
                CallbackQueryHandler(handle_bank_choice)
            ],
            STATE_BANK_CUSTOM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bank_custom)
            ],
            STATE_BANK_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bank_amount)
            ],
            STATE_BANK_OPTION: [
                CallbackQueryHandler(handle_bank_choice)
            ],
        },
        fallbacks=[],
        allow_reentry=True,
    )
    app.add_handler(conv)
