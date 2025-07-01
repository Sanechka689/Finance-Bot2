# handlers_stage1.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# ==============================
# Этап 1: Выбор тарифа
# ==============================

# 1.1: Главное меню тарифов
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("Бесплатный", callback_data="tariff_free_info"),
            InlineKeyboardButton("Тариф 1",    callback_data="tariff_1_info"),
            InlineKeyboardButton("Тариф 2",    callback_data="tariff_2_info"),
        ],
        [
            InlineKeyboardButton("Поддержка", callback_data="support_info"),
            InlineKeyboardButton("Группа в Telegram", url="https://t.me/your_group_link"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Добро пожаловать! Выберите тариф или получите помощь:\n\n"
        "• Бесплатный\n"
        "• Тариф 1 (текст/голос → AI → JSON)\n"
        "• Тариф 2 (+ фото/QR)\n\n"
        "Или нажмите «Поддержка».",
        reply_markup=reply_markup
    )

# 1.2: Показ описания выбранного тарифа
async def tariff_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    code = query.data  # tariff_free_info / tariff_1_info / tariff_2_info

    # Описания и стоимости
    descriptions = {
        "tariff_free_info": ("Бесплатный тариф:\n"
                             "- Ручной ввод через кнопки\n"
                             "- Формирование JSON-сообщения\n"
                             "Стоимость: 0 ₽"),
        "tariff_1_info":    ("Тариф 1:\n"
                             "- Текст/голос → AI → JSON\n"
                             "Стоимость: 300 ₽/мес"),
        "tariff_2_info":    ("Тариф 2:\n"
                             "- Текст/голос/фото/QR → AI → JSON\n"
                             "Стоимость: 500 ₽/мес"),
        "support_info":     ("✉️ Поддержка:\n"
                             "- @your_support_bot\n"
                             "- support@example.com")
    }
    text = descriptions.get(code, "Неизвестный выбор")

    # Кнопки «Назад» и «Выбрать тариф»
    keyboard = []
    if code.startswith("tariff_"):
        # для тарифов — добавляем «Выбрать этот тариф»
        tariff = code.replace("_info", "")
        keyboard.append([
            InlineKeyboardButton("◀️ Назад", callback_data="back_to_start"),
            InlineKeyboardButton("✅ Выбрать этот тариф", callback_data=f"confirm_{tariff}")
        ])
    else:
        # для поддержки — только «Назад»
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_start")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

# 1.3: Подтверждение тарифа
async def confirm_tariff_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # confirm_tariff_free / confirm_tariff_1 / confirm_tariff_2
    tariff = data.replace("confirm_", "")
    user_id = update.effective_user.id

    # Сохраняем выбор тарифа
    context.bot_data['user_repo'].save_tariff(
        user_id, tariff, paid=(tariff == "tariff_free")
    )

    if tariff == "tariff_free":
        # Бесплатный — сразу этап 2
        await query.edit_message_text(
            "✅ Вы активировали бесплатный тариф.\n"
            "Пожалуйста, отправьте ссылку на Google-таблицу."
        )
    else:
        # Платные — даём ссылку на оплату
        checkout_url = context.bot_data['payment_client'].create_checkout_session(
            user_id=user_id, tariff=tariff
        )
        await query.edit_message_text(
            f"Перейдите по ссылке для оплаты:\n{checkout_url}\n\n"
            "После успешной оплаты бот откроет следующий этап."
        )

# 1.4: Возврат в главное меню
async def back_to_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Просто вызываем start_handler, но через edit_message_text
    # Собираем клавиатуру заново:
    keyboard = [
        [
            InlineKeyboardButton("Бесплатный", callback_data="tariff_free_info"),
            InlineKeyboardButton("Тариф 1",    callback_data="tariff_1_info"),
            InlineKeyboardButton("Тариф 2",    callback_data="tariff_2_info"),
        ],
        [
            InlineKeyboardButton("Поддержка", callback_data="support_info"),
            InlineKeyboardButton("Группа в Telegram", url="https://t.me/your_group_link"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "👋 Возврат в главное меню. Выберите тариф или «Поддержка»:",
        reply_markup=reply_markup
    )

# В register_stage1_handlers:
app.add_handler(MessageHandler(filters.TEXT | filters.COMMAND | filters.ALL, stage1_fallback), group=1)


def register_stage1_handlers(app):
    # Stage 1.1: /start
    app.add_handler(CommandHandler("start", start_handler))

    # Stage 1.2: показ описания
    app.add_handler(CallbackQueryHandler(tariff_info_callback,
                                         pattern=r"^(tariff_(free|1|2)_info|support_info)$"))

    # Stage 1.3: подтверждение тарифа
    app.add_handler(CallbackQueryHandler(confirm_tariff_callback,
                                         pattern=r"^confirm_tariff_(free|1|2)$"))

    # Stage 1.4: кнопка «Назад»
    app.add_handler(CallbackQueryHandler(back_to_start_callback,
                                         pattern=r"^back_to_start$"))

# Stage 1.5: Фолбэк — всё, что не кнопки
async def stage1_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚠️ Сейчас вы на этапе выбора тарифа.\n"
        "Пожалуйста, нажмите одну из кнопок ниже, чтобы продолжить.",
        reply_markup=context.bot_data['stage1_keyboard']
    )

