# handlers_stage1.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# ==============================
# Этап 1: Выбор тарифа
# ==============================

# 1.1 Команда /start
# 👉 Показывает клавиатуру с тарифами и кнопками «Поддержка» и «Группа в Telegram»
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Stage 1.1.1: Формируем клавиатуру
    keyboard = [
        [
            InlineKeyboardButton("Бесплатный", callback_data="tariff_free_info"),
            InlineKeyboardButton("Тариф 1",    callback_data="tariff_1_info"),
            InlineKeyboardButton("Тариф 2",    callback_data="tariff_2_info"),
        ],
        [
            InlineKeyboardButton("Поддержка",  callback_data="support_info"),
            InlineKeyboardButton("Группа в Telegram", url="https://t.me/your_group_link"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    # Stage 1.1.2: Сохраняем клавиатуру для фолбэка
    context.bot_data['stage1_keyboard'] = reply_markup
    # Stage 1.1.3: Отправляем сообщение с клавиатурой
    await update.message.reply_text(
        "👋 Добро пожаловать! Выберите тариф или нажмите «Поддержка»:",
        reply_markup=reply_markup
    )

# 1.2 Показ информации о тарифе или поддержке
async def tariff_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Stage 1.2.1: Обработка колбэк
    query = update.callback_query
    await query.answer()
    code = query.data
    # Stage 1.2.2: Описания тарифов и поддержки
    descriptions = {
        "tariff_free_info": "Бесплатный тариф:\n- Ручной ввод через кнопки\n\nСтоимость: 0 ₽",
        "tariff_1_info":    "Тариф 1:\n- Текст/голос → AI → JSON\n\nСтоимость: 300 ₽/мес",
        "tariff_2_info":    "Тариф 2:\n- Текст/голос/фото/QR → AI → JSON\n\nСтоимость: 500 ₽/мес",
        "support_info":     "✉️ Поддержка:\n- @your_support_bot\n- support@example.com"
    }
    text = descriptions.get(code, "Неизвестный выбор")
    # Stage 1.2.3: Формируем кнопки «Назад» и «Выбрать тариф» (для тарифов)
    buttons = [InlineKeyboardButton("◀️ Назад", callback_data="back_to_start")]
    if code.startswith("tariff_"):
        tariff = code.replace("_info", "")
        buttons.append(InlineKeyboardButton("✅ Выбрать тариф", callback_data=f"confirm_{tariff}"))
    reply_markup = InlineKeyboardMarkup([buttons])
    await query.edit_message_text(text, reply_markup=reply_markup)

# 1.3 Подтверждение выбора тарифа
async def confirm_tariff_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Stage 1.3.1: Обработка колбэк
    query = update.callback_query
    await query.answer()
    tariff = query.data.replace("confirm_", "")
    user_id = update.effective_user.id
    # Stage 1.3.2: Сохраняем выбор тарифа
    context.bot_data['user_repo'].save_tariff(user_id, tariff, paid=(tariff == "tariff_free"))
    # Stage 1.3.3: Отправка результата пользователю
    if tariff == "tariff_free":
        await query.edit_message_text(
            "✅ Бесплатный тариф активирован.\n"
            "Теперь отправьте ссылку на вашу Google-таблицу."
        )
    else:
        checkout_url = context.bot_data['payment_client'].create_checkout_session(user_id=user_id, tariff=tariff)
        await query.edit_message_text(
            f"Перейдите по ссылке для оплаты:\n{checkout_url}\n\n"
            "После оплаты бот разблокирует следующий этап."
        )

# 1.4 Возврат в главное меню
async def back_to_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Stage 1.4.1: Обработка колбэк
    query = update.callback_query
    await query.answer()
    # Stage 1.4.2: Возвращаем главное меню
    await query.edit_message_text(
        "👋 Вернулись в главное меню. Выберите тариф или нажмите «Поддержка»:",
        reply_markup=context.bot_data['stage1_keyboard']
    )

# 1.5 Фолбэк для всего остального
async def stage1_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Stage 1.5.1: Информируем пользователя о текущем этапе
    await update.message.reply_text(
        "⚠️ Вы на этапе выбора тарифа.\n"
        "Пожалуйста, используйте кнопки ниже для навигации.",
        reply_markup=context.bot_data['stage1_keyboard']
    )

# Регистрация хендлеров этапа 1
def register_stage1_handlers(app):
    """
    Stage 1: Регистрируем хендлеры выбор тарифа, информации, подтверждения, возврата и фолбэка
    """
    # Stage 1.1: Команда /start
    app.add_handler(CommandHandler("start", start_handler))
    # Stage 1.2: Показ информации о тарифах и поддержке
    app.add_handler(CallbackQueryHandler(tariff_info_callback, pattern=r"^(tariff_(free|1|2)_info|support_info)$"))
    # Stage 1.3: Подтверждение тарифа
    app.add_handler(CallbackQueryHandler(confirm_tariff_callback, pattern=r"^confirm_(tariff_free|tariff_1|tariff_2)$"))
    # Stage 1.4: Кнопка «Назад»
    app.add_handler(CallbackQueryHandler(back_to_start_callback, pattern=r"^back_to_start$"))
    # Stage 1.5: Фолбэк на любые другие сообщения
    app.add_handler(MessageHandler(filters.ALL, stage1_fallback), group=1)
