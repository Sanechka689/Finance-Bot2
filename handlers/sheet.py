# handlers/sheet.py — этап 2: подключение и инициализация Google Sheets

import re
from telegram import Update
from telegram.ext import (
    MessageHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    filters
)
from utils.constants           import STATE_SHEET
from services.sheets_service   import open_finance_and_plans

async def show_sheet_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        # Если тариф не выбран — не даём перейти на этот этап
    if not context.user_data.get("tariff"):
        await update.message.reply_text(
            "⚠️ Сначала выберите тариф через /start и нажмите «Выбрать тариф»."
        )
        return ConversationHandler.END
    
    """
    #6.2 Просим пользователя прислать ссылку на Google Sheets
    """
    await update.message.reply_text(
        "📑 Пожалуйста, отправьте мне ссылку на вашу пустую Google Sheets-таблицу.\n\n"
        "Бот автоматически удалит лист 'Лист1', создаст в ней два листа —\n"
        "• 'Финансы' с колонками Год, Месяц, Банк, Операция, Дата, Сумма, Классификация, Конкретика\n"
        "• 'Планы'   с колонками Год, Месяц, Банк, Операция, Дата, Сумма, Остаток, Классификация, Конкретика\n\n"
        "И установит фильтр и зафиксирует шапку на обоих листах.\n"
        "Не забудьте дать права на редактирование сервисному аккаунту."
    )
    context.user_data["current_state"] = STATE_SHEET
    return STATE_SHEET

async def handle_sheet_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    #6.3 Обработка присланной ссылки — подключаем и инициализируем.
    """
    url = update.message.text.strip()
    if not re.match(r'https://docs\.google\.com/spreadsheets/.+', url):
        await update.message.reply_text(
            "⚠️ Это не похоже на ссылку Google Sheets. Попробуйте снова."
        )
        return STATE_SHEET

    try:
        finance_ws, plans_ws = open_finance_and_plans(url)
    except Exception as e:
        # Показываем реальную ошибку для диагностики
        await update.message.reply_text(
            f"❌ Не удалось подключить и инициализировать таблицу:\n{e}\n\n"
            "Убедитесь, что:\n"
            "• Вы дали сервисному аккаунту права на редактирование\n"
            "• Таблица действительно пуста и содержит 'Лист1'\n"
            "  (он будет удалён автоматически)\n"
            "• У вас есть листы 'Финансы' и 'Планы' после операции"
        )
        return STATE_SHEET

    context.user_data["sheet_url"] = url
    await update.message.reply_text(
        "✅ Таблица успешно подключена и инициализирована!\n"
        "Переходим к этапу первоначального заполнения банков. Нажмите /banks"
    )
    return ConversationHandler.END

async def invalid_sheet_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    #6.4 Обработка любых не-текстовых сообщений на этом этапе
    """
    await update.effective_message.reply_text(
        "⚠️ Пожалуйста, отправьте ссылку на новую Google Sheets-таблицу."
    )
    return context.user_data.get("current_state", STATE_SHEET)

def register_sheet_handlers(app):
    """
    #6.5 Регистрируем ConversationHandler для этапа подключения/инициализации таблицы
    """
    conv = ConversationHandler(
        entry_points=[CommandHandler("setup", show_sheet_prompt)],
        states={
            STATE_SHEET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_sheet_url),
                MessageHandler(filters.ALL, invalid_sheet_action),
            ],
        },
        fallbacks=[],
        allow_reentry=True,
    )
    app.add_handler(conv)
