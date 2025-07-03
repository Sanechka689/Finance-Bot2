# handlers/tariff.py — выбор тарифа с подробностями и обходом оплаты

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import (
    ConversationHandler,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from utils.constants import STATE_TARIFF_MENU, STATE_TARIFF_DETAIL

# 3.2 Экран «Меню тарифов»
async def show_tariff_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показываем приветствие и список тарифов
    """
    text = (
        "👋 Добро пожаловать в ФинБот!\n\n"
        "Я помогу вам автоматизировать ввод финансовых операций в Google Sheets.\n"
        "Пожалуйста, выберите тариф:"
    )
    keyboard = [
        [
            InlineKeyboardButton("Бесплатный", callback_data="tariff_free"),
            InlineKeyboardButton("Тариф 1", callback_data="tariff_1"),
            InlineKeyboardButton("Тариф 2", callback_data="tariff_2"),
        ],
        [InlineKeyboardButton("Поддержка", callback_data="support"),
         InlineKeyboardButton("Телеграмм канал", url="https://t.me/your_channel")],
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return STATE_TARIFF_MENU

# 3.3 Обработка нажатий в меню
async def handle_menu_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data

    if choice == "support":
        await query.message.reply_text(
            "📧 Для поддержки напишите: financebot365@gmail.com\n"
            "или @FinanceBotSupport в Telegram."
        )
        return STATE_TARIFF_MENU

    if choice in ("tariff_free", "tariff_1", "tariff_2"):
        # показываем детали выбранного тарифа
        desc = {
            "tariff_free": "✅ Бесплатный тариф: ручной ввод через кнопки, текст и голос.",
            "tariff_1":     "🔓 Тариф 1: всё из бесплатного + автопарсинг текста и голоса.",
            "tariff_2":     "🏷️ Тариф 2: всё из Т1 + парсинг фото чеков.",
        }[choice]

        keyboard = [
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")],
            [InlineKeyboardButton("Выбрать тариф", callback_data=f"select_{choice}")],
        ]
        await query.edit_message_text(desc, reply_markup=InlineKeyboardMarkup(keyboard))
        return STATE_TARIFF_DETAIL

    # на всякий случай
    await query.message.reply_text("⚠️ Пожалуйста, пользуйтесь кнопками меню.")
    return STATE_TARIFF_MENU

# 3.4 Обработка детализации и кнопки «Назад»
async def handle_detail_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back_to_menu":
        # возвращаемся к списку тарифов через редактирование сообщения
        text = (
            "👋 Добро пожаловать в ФинБот!\n\n"
            "Я помогу вам автоматизировать ввод финансовых операций в Google Sheets.\n"
            "Пожалуйста, выберите тариф:"
        )
        keyboard = [
        [
            InlineKeyboardButton("Бесплатный", callback_data="tariff_free"),
            InlineKeyboardButton("Тариф 1", callback_data="tariff_1"),
            InlineKeyboardButton("Тариф 2", callback_data="tariff_2"),
        ],
        [InlineKeyboardButton("Поддержка", callback_data="support"),
         InlineKeyboardButton("Телеграмм канал", url="https://t.me/your_channel")],
    ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return STATE_TARIFF_MENU

    if data.startswith("select_tariff_"):
        tariff = data.split("select_")[1]
        context.user_data["tariff"] = tariff

        if tariff == "tariff_free":
            await query.edit_message_text(
                "🎉 Вы выбрали _Бесплатный_ тариф и сразу переходите к подключению таблицы.",
                parse_mode="Markdown"
            )
            return ConversationHandler.END

        # для платных тарифов — эмуляция оплаты
        keyboard = [
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")],
            [InlineKeyboardButton("Я оплатил ✅", callback_data="paid")],
        ]
        await query.edit_message_text(
            f"💳 Чтобы продолжить, нажмите «Я оплатил ✅» для подтверждения оплаты.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return STATE_TARIFF_DETAIL

    if data == "paid":
        tariff = context.user_data.get("tariff")
        await query.edit_message_text(
            f"🎉 Оплата тарифa *{tariff}* подтверждена!\n"
            "Переходим к подключению Google Sheets...",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    return ConversationHandler.END

# 3.5 Обработка любых не-кнопочных действий
async def invalid_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text(
        "⚠️ Пожалуйста, пользуйтесь только кнопками этого меню."
    )
    # остаёмся на текущем шаге
    return context.user_data.get("current_state", STATE_TARIFF_MENU)

def register_tariff_handlers(app):
    """
    Регистрируем ConversationHandler для выбора тарифа
    """
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", show_tariff_menu)],
        states={
            STATE_TARIFF_MENU: [
                CallbackQueryHandler(handle_menu_selection),
                MessageHandler(filters.ALL, invalid_action),
            ],
            STATE_TARIFF_DETAIL: [
                CallbackQueryHandler(handle_detail_selection),
                MessageHandler(filters.ALL, invalid_action),
            ],
        },
        fallbacks=[],
        allow_reentry=True,
    )
    app.add_handler(conv)
