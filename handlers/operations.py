# handlers/operations.py
# 2.1 Определение хэндлеров этапа 4 (ручной ввод операций)

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

# === 2.1.1: Точка входа — команда /add ===
async def start_op(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # 2.1.1.1: Сбрасываем состояние и черновик
    init_user_state(context)
    # 2.1.1.2: Показываем меню полей
    return await show_fields_menu(update, context)

# === 2.1.2: Показываем меню полей для заполнения ===
async def show_fields_menu(update_or_query, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
        [
            InlineKeyboardButton("📅 Дата", callback_data="field|Дата"),
            InlineKeyboardButton("🏦 Банк", callback_data="field|Банк"),
        ],
        [
            InlineKeyboardButton("⚙️ Операция", callback_data="field|Операция"),
            InlineKeyboardButton("➖ Сумма", callback_data="field|Сумма"),
        ],
        [
            InlineKeyboardButton("🏷️ Классификация", callback_data="field|Классификация"),
            InlineKeyboardButton("🔍 Конкретика", callback_data="field|Конкретика"),
        ],
        [
            InlineKeyboardButton("❌ Отмена", callback_data="cancel_op"),
        ],
    ]
    text = render_pending_op(context.user_data["pending_op"])

    # Редактируем существующее сообщение или отправляем новое
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

# === 2.1.3: Рендер черновика операции ===
def render_pending_op(op: dict) -> str:
    lines = []
    for k, v in op.items():
        lines.append(f"{k}: {v if v is not None else '—'}")
    return "\n".join(lines)

# === 2.1.4: Регистрация ConversationHandler ===
def register_operations_handlers(app):
    conv = ConversationHandler(
        entry_points=[CommandHandler("add", start_op)],
        states={
            STATE_OP_FIELD_CHOOSE: [
                CallbackQueryHandler(lambda u, c: None, pattern="^field\\|"),
            ],
            # позже добавим STATE_OP_FIELD_INPUT
        },
        fallbacks=[
            CallbackQueryHandler(lambda u, c: ConversationHandler.END, pattern="cancel_op")
        ],
        allow_reentry=True,
    )
    app.add_handler(conv)
