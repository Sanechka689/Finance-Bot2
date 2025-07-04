# handlers/operations.py
# Этап 4: ручной ввод операций (бесплатный тариф)

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ConversationHandler,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from utils.constants import STATE_OP_FIELD_CHOOSE, STATE_OP_FIELD_INPUT
from utils.state import init_user_state

# 4.1 — команда /add
async def start_op(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # 4.1.1 Сбрасываем состояние и «черновик»
    init_user_state(context)
    # 4.1.2 Показываем меню полей
    return await show_fields_menu(update, context)

# 4.2 — меню полей для заполнения
async def show_fields_menu(update_or_query, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
        [
            InlineKeyboardButton("📅 Дата",       callback_data="field|Дата"),
            InlineKeyboardButton("🏦 Банк",       callback_data="field|Банк"),
        ],
        [
            InlineKeyboardButton("⚙️ Операция",   callback_data="field|Операция"),
            InlineKeyboardButton("➖ Сумма",      callback_data="field|Сумма"),
        ],
        [
            InlineKeyboardButton("🏷️ Классификация", callback_data="field|Классификация"),
            InlineKeyboardButton("🔍 Конкретика",     callback_data="field|Конкретика"),
        ],
        [
            InlineKeyboardButton("❌ Отмена",      callback_data="cancel_op"),
        ],
    ]
    text = render_pending_op(context.user_data["pending_op"])

    if hasattr(update_or_query, "callback_query"):
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

# 4.3 — сборка текста «черновика»
def render_pending_op(op: dict) -> str:
    lines = []
    for k, v in op.items():
        lines.append(f"{k}: {v if v is not None else '—'}")
    return "\n".join(lines)

# 4.4 — обработка нажатия на поле
async def choose_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    data = update.callback_query.data

    if data == "cancel_op":
        await update.callback_query.edit_message_text("❌ Операция отменена.")
        return ConversationHandler.END

    _, field = data.split("|", 1)
    context.user_data["current_field"] = field

    prompts = {
        "Дата":          "📅 Введите дату в формате ДД.MM.ГГГГ",
        "Банк":          "🏦 Введите или выберите название банка",
        "Операция":      "⚙️ Введите: Пополнение, Трата или Перевод",
        "Сумма":         "➖ Введите сумму (только цифры)",
        "Классификация": "🏷️ Введите категорию (пример: Продукты)",
        "Конкретика":    "🔍 Введите конкретику (пример: Пятёрочка)",
    }
    await update.callback_query.edit_message_text(prompts[field])
    context.user_data["state"] = STATE_OP_FIELD_INPUT
    return STATE_OP_FIELD_INPUT

# 4.5 — приём введённого текста для поля
async def input_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    field = context.user_data["current_field"]
    value = update.message.text.strip()
    context.user_data["pending_op"][field] = value
    context.user_data["current_field"] = None
    return await show_fields_menu(update, context)

# 4.6 — регистрация ConversationHandler
def register_operations_handlers(app):
    conv = ConversationHandler(
        entry_points=[CommandHandler("add", start_op)],
        states={
            STATE_OP_FIELD_CHOOSE: [
                CallbackQueryHandler(choose_field, pattern="^field\\|"),
            ],
            STATE_OP_FIELD_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_field),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(lambda u, c: ConversationHandler.END, pattern="cancel_op"),
        ],
        allow_reentry=True,
    )
    app.add_handler(conv)
