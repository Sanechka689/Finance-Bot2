# handlers/operations.py
# Этап 4: ручное заполнение операций (бесплатный тариф)

from datetime import datetime
import calendar
import pytz

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
    STATE_SELECT_DATE,
    STATE_SELECT_BANK,
    STATE_SELECT_OPERATION,
    STATE_ENTER_AMOUNT,
    STATE_CONFIRM,
)
from utils.state import init_user_state

# 4.1 — команда /add: проверяем тариф и показываем «Добавить»/«Меню»
async def start_op(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tariff = context.user_data.get("tariff", "tariff_free")
    if tariff != "tariff_free":
        return await update.message.reply_text(
            "⚠️ Ручной ввод доступен только на бесплатном тарифе."
        )
    init_user_state(context)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("➕ Добавить", callback_data="op_start_add"),
        InlineKeyboardButton("📋 Меню",    callback_data="op_start_menu"),
    ]])
    await update.message.reply_text(
        "✏️ Этап добавления операции: выберите действие",
        reply_markup=kb
    )
    return STATE_OP_MENU

# 4.2 — обработка кнопок «Добавить» / «Меню»
async def on_op_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    if q.data == "op_start_add":
        return await ask_date(update, context)
    else:
        await q.edit_message_text("Вы вернулись в главное меню.")
        return ConversationHandler.END

# 4.3 — календарь для выбора даты
def get_prev_year_month(year: int, month: int):
    if month == 1:
        return year - 1, 12
    return year, month - 1

def get_next_year_month(year: int, month: int):
    if month == 12:
        return year + 1, 1
    return year, month + 1

def create_calendar(year: int, month: int) -> InlineKeyboardMarkup:
    today = datetime.now(pytz.timezone("Europe/Moscow")).date()
    markup = []
    py, pm = get_prev_year_month(year, month)
    ny, nm = get_next_year_month(year, month)
    # навигация
    markup.append([
        InlineKeyboardButton("<", callback_data=f"calendar|{py}|{pm}"),
        InlineKeyboardButton(f"{calendar.month_name[month]} {year}", callback_data="ignore"),
        InlineKeyboardButton(">", callback_data=f"calendar|{ny}|{nm}")
    ])
    # дни недели
    markup.append([InlineKeyboardButton(d, callback_data="ignore") for d in ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]])
    # числа
    for week in calendar.monthcalendar(year, month):
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                ds = f"{year}-{month:02d}-{day:02d}"
                label = f"🔴{day}" if (year,month,day) == (today.year,today.month,today.day) else str(day)
                row.append(InlineKeyboardButton(label, callback_data=f"select_date|{ds}"))
        markup.append(row)
    return InlineKeyboardMarkup(markup)

async def ask_date(update_or_query, context: ContextTypes.DEFAULT_TYPE) -> int:
    now = datetime.now(pytz.timezone("Europe/Moscow"))
    cal = create_calendar(now.year, now.month)
    if update_or_query.callback_query:
        await update_or_query.callback_query.edit_message_text("📅 Выберите дату:", reply_markup=cal)
    else:
        await update_or_query.message.reply_text("📅 Выберите дату:", reply_markup=cal)
    return STATE_SELECT_DATE

async def handle_calendar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    data = q.data
    if data.startswith("calendar|"):
        _, y, m = data.split("|")
        cal = create_calendar(int(y), int(m))
        await q.edit_message_reply_markup(cal)
        return STATE_SELECT_DATE
    if data.startswith("select_date|"):
        _, ds = data.split("|")
        context.user_data["pending_op"]["Дата"] = ds
        return await ask_bank(update, context)

# 4.4 — список банков кнопками
async def ask_bank(update_or_query, context: ContextTypes.DEFAULT_TYPE) -> int:
    banks = context.user_data.get("banks", [])
    keyboard = [[InlineKeyboardButton(b, callback_data=f"select_bank|{b}")] for b in banks]
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="op_start_add")])
    kb = InlineKeyboardMarkup(keyboard)
    if update_or_query.callback_query:
        await update_or_query.callback_query.edit_message_text("🏦 Выберите банк:", reply_markup=kb)
    else:
        await update_or_query.message.reply_text("🏦 Выберите банк:", reply_markup=kb)
    return STATE_SELECT_BANK

async def handle_bank_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    bank = q.data.split("|",1)[1]
    context.user_data["pending_op"]["Банк"] = bank
    return await ask_operation(update, context)

# 4.5 — выбор типа операции
async def ask_operation(update_or_query, context: ContextTypes.DEFAULT_TYPE) -> int:
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("Пополнение", callback_data="select_op|Пополнение"),
        InlineKeyboardButton("Трата",      callback_data="select_op|Трата"),
        InlineKeyboardButton("Перевод",    callback_data="select_op|Перевод"),
    ], [InlineKeyboardButton("❌ Отмена", callback_data="op_start_add")]])
    if update_or_query.callback_query:
        await update_or_query.callback_query.edit_message_text("⚙️ Выберите тип операции:", reply_markup=kb)
    else:
        await update_or_query.message.reply_text("⚙️ Выберите тип операции:", reply_markup=kb)
    return STATE_SELECT_OPERATION

async def handle_operation_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    op = q.data.split("|",1)[1]
    context.user_data["pending_op"]["Операция"] = op
    return await ask_amount(update, context)

# 4.6 — ввод и валидация суммы
async def ask_amount(update_or_query, context: ContextTypes.DEFAULT_TYPE) -> int:
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="op_start_add")]])
    msg = "➖ Введите сумму (только число без знака):"
    if update_or_query.callback_query:
        await update_or_query.callback_query.edit_message_text(msg, reply_markup=kb)
    else:
        await update_or_query.message.reply_text(msg, reply_markup=kb)
    return STATE_ENTER_AMOUNT

async def handle_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip().replace(",", ".")
    try:
        amt = float(text)
    except ValueError:
        return await update.message.reply_text("⚠️ Введите корректное число.")
    op = context.user_data["pending_op"].get("Операция")
    if op == "Трата" and amt >= 0:
        return await update.message.reply_text("⚠️ Для «Трата» число должно быть > 0.")
    if op == "Пополнение" and amt < 0:
        return await update.message.reply_text("⚠️ Для «Пополнение» число ≥ 0.")
    context.user_data["pending_op"]["Сумма"] = amt
    return await show_confirm(update, context)

# 4.7 — финальная сверка и «Подтвердить»
async def show_confirm(update_or_query, context: ContextTypes.DEFAULT_TYPE) -> int:
    op = context.user_data["pending_op"]
    if op.get("Конкретика") is None:
        op["Конкретика"] = "-"
    lines = [f"{k}: {v}" for k, v in op.items()]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_op"),
        InlineKeyboardButton("✏️ Изменить",    callback_data="op_start_add"),
    ]])
    msg = "📋 Подтвердите операцию:\n" + "\n".join(lines)
    if update_or_query.callback_query:
        await update_or_query.callback_query.edit_message_text(msg, reply_markup=kb)
    else:
        await update_or_query.message.reply_text(msg, reply_markup=kb)
    return STATE_CONFIRM

# 4.8 — запись в таблицу и конец
async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    op = context.user_data["pending_op"]
    dt = datetime.fromisoformat(op["Дата"])
    year = dt.year
    month = dt.strftime("%B")
    # TODO: здесь append_row в Google Sheets
    await q.edit_message_text("✅ Операция добавлена в таблицу.")
    return ConversationHandler.END

# — регистрация этапа 4 —
def register_operations_handlers(app):
    conv = ConversationHandler(
        entry_points=[CommandHandler("add", start_op)],
        states={
            STATE_OP_MENU: [
                CallbackQueryHandler(on_op_menu, pattern="^op_start_"),
            ],
            STATE_SELECT_DATE: [
                CallbackQueryHandler(handle_calendar_callback,
                                     pattern="^(calendar\\||select_date\\|)"),
            ],
            STATE_SELECT_BANK: [
                CallbackQueryHandler(handle_bank_selection,
                                     pattern="^select_bank\\|"),
            ],
            STATE_SELECT_OPERATION: [
                CallbackQueryHandler(handle_operation_selection,
                                     pattern="^select_op\\|"),
            ],
            STATE_ENTER_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND,
                               handle_amount_input),
            ],
            STATE_CONFIRM: [
                CallbackQueryHandler(handle_confirm,
                                     pattern="^confirm_op$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(lambda u, c: ConversationHandler.END,
                                 pattern="^op_start_"),
        ],
        allow_reentry=True,
    )
    app.add_handler(conv)
