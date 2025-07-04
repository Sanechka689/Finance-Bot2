# handlers/operations.py
# Этап 4: ручное заполнение операций (бесплатный тариф)

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ConversationHandler,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from utils.constants import (
    STATE_OP_MENU,
    STATE_OP_FIELD_CHOOSE,
    STATE_OP_FIELD_INPUT,
)
from utils.state import init_user_state

# 4.1 — команда /add
async def start_op(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # 1) Получаем текущий тариф, если его нет — считаем бесплатным
    tariff = context.user_data.get("tariff")
    if tariff is None:
        context.user_data["tariff"] = "tariff_free"
        tariff = "tariff_free"

    # 2) Разрешаем ручное заполнение только для тарифов tariff_free
    if tariff != "tariff_free":
        return await update.message.reply_text(
            "⚠️ Ручной ввод через кнопки доступен только на бесплатном тарифе."
        )

    # 3) Инициализируем FSM и показываем кнопки “Добавить”/“Меню”
    init_user_state(context)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить", callback_data="op_start_add")],
        [InlineKeyboardButton("📋 Меню",     callback_data="op_start_menu")],
    ])
    await update.message.reply_text(
        "✏️ Вы на этапе добавления операций. Выберите действие:",
        reply_markup=kb
    )
    return STATE_OP_MENU


# 4.2 — обработка кнопок “Добавить” / “Меню”
async def on_op_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    if q.data == "op_start_add":
        # Переходим к обычному меню полей
        return await show_fields_menu(update, context)
    else:
        # Меню — завершаем разговор и вызываем ваш главный Menu-handler
        await q.edit_message_text("Вы в главном меню.")
        return ConversationHandler.END

# 4.3 — меню полей
async def show_fields_menu(update_or_query, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
        [InlineKeyboardButton("📅 Дата",       callback_data="field|Дата"),
         InlineKeyboardButton("🏦 Банк",       callback_data="field|Банк")],
        [InlineKeyboardButton("⚙️ Операция",   callback_data="field|Операция"),
         InlineKeyboardButton("➖ Сумма",      callback_data="field|Сумма")],
        [InlineKeyboardButton("🏷️ Классификация", callback_data="field|Классификация"),
         InlineKeyboardButton("🔍 Конкретика",     callback_data="field|Конкретика")],
        [InlineKeyboardButton("❌ Отмена",      callback_data="cancel_op")],
    ]
    text = render_pending_op(context.user_data["pending_op"])

    # проверяем, реальный ли это CallbackQuery или новое сообщение
    if update_or_query.callback_query:
        await update_or_query.callback_query.edit_message_text(
            text or "✏️ Добавление операции: выберите поле",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        await update_or_query.message.reply_text(
            text or "✏️ Добавление операции: выберите поле",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    context.user_data["state"] = STATE_OP_FIELD_CHOOSE
    return STATE_OP_FIELD_CHOOSE

# 4.4 — сборка черновика
def render_pending_op(op: dict) -> str:
    return "\n".join(f"{k}: {v if v is not None else '—'}" for k, v in op.items())

# 4.5 — выбор поля
async def choose_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    field = update.callback_query.data.split("|",1)[1]
    context.user_data["current_field"] = field

    prompts = {
        "Дата":          "📅 Введите дату ДД.MM.ГГГГ",
        "Банк":          "🏦 Введите или выберите банк",
        "Операция":      "⚙️ Введите: Пополнение/Трата/Перевод",
        "Сумма":         "➖ Введите сумму (только цифры)",
        "Классификация": "🏷️ Введите категорию",
        "Конкретика":    "🔍 Введите конкретику",
    }
    await update.callback_query.edit_message_text(prompts[field])
    context.user_data["state"] = STATE_OP_FIELD_INPUT
    return STATE_OP_FIELD_INPUT

# 4.6 — ввод поля
async def input_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    field = context.user_data["current_field"]
    context.user_data["pending_op"][field] = update.message.text.strip()
    context.user_data["current_field"] = None
    return await show_fields_menu(update, context)

# 4.7 — регистрация ConversationHandler
def register_operations_handlers(app):
    conv = ConversationHandler(
        entry_points=[CommandHandler("add", start_op)],
        states={
            STATE_OP_MENU: [
                CallbackQueryHandler(on_op_menu, pattern="^op_start_"),
            ],
            STATE_OP_FIELD_CHOOSE: [
                CallbackQueryHandler(choose_field, pattern="^field\\|"),
            ],
            STATE_OP_FIELD_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_field),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(lambda u,c: ConversationHandler.END, pattern="cancel_op"),
        ],
        allow_reentry=True,
    )
    app.add_handler(conv)
