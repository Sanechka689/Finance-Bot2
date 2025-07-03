# handlers/banks.py — этап 3: первоначальное заполнение банков

from datetime import datetime
import calendar

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import (
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters,
)
from utils.constants import STATE_BANK_CHOOSE, STATE_BANK_AMOUNT
from services.sheets_service import open_finance_and_plans

# 3.7 Показать меню банков
async def show_banks_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = "🏦 Выберите банк для ввода стартового баланса:"
    keyboard = [
        [
            InlineKeyboardButton("Сбер", callback_data="bank_Сбер"),
            InlineKeyboardButton("Тинькофф", callback_data="bank_Тинькофф"),
        ],
        [
            InlineKeyboardButton("Альфа", callback_data="bank_Альфа"),
            InlineKeyboardButton("МКБ", callback_data="bank_МКБ"),
        ],
        [
            InlineKeyboardButton("Свой вариант", callback_data="bank_custom"),
        ],
        [
            InlineKeyboardButton("Поддержка", callback_data="support"),
        ],
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return STATE_BANK_CHOOSE

# 3.8 Обработать нажатие на банк
async def handle_bank_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data

    if choice == "support":
        await query.message.reply_text("📧 Для поддержки: financebot365@gmail.com")
        return STATE_BANK_CHOOSE

    if choice.startswith("bank_"):
        bank = choice.split("_", 1)[1]
        context.user_data["bank"] = bank
        await query.edit_message_text(
            f"💰 Введите стартовый баланс для банка <b>{bank}</b>:",
            parse_mode="HTML"
        )
        return STATE_BANK_AMOUNT

    # Неправильное действие
    await query.message.reply_text("⚠️ Пожалуйста, используйте кнопки.")
    return STATE_BANK_CHOOSE

# 3.9 Обработать ввод суммы
async def handle_bank_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        amount = float(text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("⚠️ Введите число, например: 1000")
        return STATE_BANK_AMOUNT

    bank = context.user_data["bank"]
    sheet_url = context.user_data.get("sheet_url")
    if not sheet_url:
        await update.message.reply_text("❌ Ссылка на таблицу не найдена. Сначала выполните /setup.")
        return ConversationHandler.END

    # Получаем лист «Финансы»
    finance_ws, _ = open_finance_and_plans(sheet_url)

    now = datetime.now()
    year = now.year
    month = calendar.month_name[now.month]
    date_str = now.strftime("%d.%m.%Y")

    # Вставляем новую строку
    row = [year, month, bank, "Первые данные", date_str, amount, "Первые данные", "-"]
    finance_ws.append_row(row, value_input_option="USER_ENTERED")

    # Предлагаем добавить ещё или закончить
    keyboard = [
        [InlineKeyboardButton("Добавить ещё банк", callback_data="add_more")],
        [InlineKeyboardButton("Завершить", callback_data="finish_setup")],
    ]
    await update.message.reply_text(
        f"✅ Банк <b>{bank}</b> добавлен с балансом <b>{amount}</b>.",
        parse_mode="HTML"
    )
    await update.message.reply_text("Что дальше?", reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

# 3.10 Обработка «Добавить ещё» / «Завершить»
async def handle_after_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "add_more":
        return await show_banks_menu(update, context)
    if query.data == "finish_setup":
        await query.edit_message_text("🎉 Первоначальное заполнение банков завершено!")
        return ConversationHandler.END
    return ConversationHandler.END

def register_banks_handlers(app):
    """
    Регистрируем ConversationHandler для этапа заполнения банков (/banks).
    """
    conv = ConversationHandler(
        entry_points=[CommandHandler("banks", show_banks_menu)],
        states={
            STATE_BANK_CHOOSE: [CallbackQueryHandler(handle_bank_choice)],
            STATE_BANK_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bank_amount)],
        },
        fallbacks=[CallbackQueryHandler(handle_after_add)],
        allow_reentry=True,
    )
    app.add_handler(conv)
