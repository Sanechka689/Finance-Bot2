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
    STATE_ENTER_CLASSIFICATION,
    STATE_ENTER_SPECIFIC,
    STATE_CONFIRM,
)
from utils.state import init_user_state
from services.sheets_service import open_finance_and_plans

# 4.1 — старт /add
async def start_op(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tariff = context.user_data.get("tariff", "tariff_free")
    if tariff != "tariff_free":
        return await update.message.reply_text(
            "⚠️ Ручной ввод доступен только на бесплатном тарифе."
        )
    init_user_state(context)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("➕ Добавить", callback_data="op_start_add"),
        InlineKeyboardButton("📋 Меню",     callback_data="op_start_menu"),
    ]])
    await update.message.reply_text(
        "✏️ Этап добавления операции: выберите действие",
        reply_markup=kb
    )
    return STATE_OP_MENU

# 4.2 — обработка «Добавить» / «Меню»
async def on_op_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    if q.data == "op_start_add":
        # Ранее было: show_fields_menu(q,...)
        # Теперь правильно передаем весь Update
        return await show_fields_menu(update, context)
    else:
        await q.edit_message_text("Вы вернулись в главное меню.")
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
        [InlineKeyboardButton("❌ Отмена",      callback_data="op_start_add")],
    ]
    op = context.user_data["pending_op"]
    text = "\n".join(f"{k}: {v if v is not None else '—'}" for k,v in op.items())

    if update_or_query.callback_query:
        await update_or_query.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update_or_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    return STATE_OP_FIELD_CHOOSE

# — 4.4 Обработка нажатия на поле
async def choose_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    field = q.data.split("|", 1)[1]
    context.user_data["current_field"] = field

    # Переключаем на соответствующий шаг
    if field == "Дата":
        return await ask_date(update, context)
    if field == "Банк":
        return await ask_bank(update, context)
    if field == "Операция":
        return await ask_operation(update, context)
    if field == "Сумма":
        return await ask_amount(update, context)
    if field == "Классификация":
        await q.edit_message_text("🏷️ Введите классификацию:")
        return STATE_ENTER_CLASSIFICATION
    if field == "Конкретика":
        await q.edit_message_text("🔍 Введите конкретику:")
        return STATE_ENTER_SPECIFIC

# — 4.5 Дата: календарь
# (повторяем функцию create_calendar из предыдущего примера)
def get_prev_year_month(year: int, month: int):
    return (year-1, 12) if month==1 else (year, month-1)
def get_next_year_month(year: int, month: int):
    return (year+1, 1) if month==12 else (year, month+1)

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
            if day==0:
                row.append(InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                ds = f"{year}-{month:02d}-{day:02d}"
                label = f"🔴{day}" if (year,month,day)==(today.year,today.month,today.day) else str(day)
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
    q = update.callback_query; await q.answer()
    data = q.data
    if data.startswith("calendar|"):
        _, y, m = data.split("|")
        cal = create_calendar(int(y), int(m))
        await q.edit_message_reply_markup(cal)
        return STATE_SELECT_DATE
    if data.startswith("select_date|"):
        _, ds = data.split("|")
        context.user_data["pending_op"]["Дата"] = ds
        return await show_fields_menu(update, context)

# — 4.6 Банк: кнопки из Google Sheets
async def ask_bank(update_or_query, context: ContextTypes.DEFAULT_TYPE) -> int:
    # подтягиваем из таблицы
    ws, _ = open_finance_and_plans(context.user_data["sheet_url"])
    banks = sorted(set(ws.col_values(3)[1:]))
    context.user_data["banks"] = banks
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(b, callback_data=f"select_bank|{b}")] for b in banks] + [[InlineKeyboardButton("❌ Отмена", callback_data="op_start_add")]])
    if update_or_query.callback_query:
        await update_or_query.callback_query.edit_message_text("🏦 Выберите банк:", reply_markup=kb)
    else:
        await update_or_query.message.reply_text("🏦 Выберите банк:", reply_markup=kb)
    return STATE_SELECT_BANK

async def handle_bank_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    context.user_data["pending_op"]["Банк"] = q.data.split("|",1)[1]
    return await show_fields_menu(update, context)

# — 4.7 Операция: фиксированные кнопки
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
    context.user_data["pending_op"]["Операция"] = q.data.split("|",1)[1]
    return await show_fields_menu(update, context)

# — 4.8 Сумма: ввод и проверка
async def ask_amount(update_or_query, context: ContextTypes.DEFAULT_TYPE) -> int:
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="op_start_add")]])
    if update_or_query.callback_query:
        await update_or_query.callback_query.edit_message_text("➖ Введите сумму (число):", reply_markup=kb)
    else:
        await update_or_query.message.reply_text("➖ Введите сумму (число):", reply_markup=kb)
    return STATE_ENTER_AMOUNT

async def handle_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip().replace(",",".")
    try:
        amt = float(text)
    except ValueError:
        return await update.message.reply_text("⚠️ Введите число!")
    op = context.user_data["pending_op"]["Операция"]
    if op=="Трата" and amt>=0:
        return await update.message.reply_text("⚠️ Для траты используйте >0!")
    if op=="Пополнение" and amt<0:
        return await update.message.reply_text("⚠️ Для пополнения используйте ≥0!")
    context.user_data["pending_op"]["Сумма"] = amt
    return await show_fields_menu(update, context)

# — 4.9 Классификация
async def input_classification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["pending_op"]["Классификация"] = update.message.text.strip()
    return await show_fields_menu(update, context)

# — 4.10 Конкретика
async def input_specific(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["pending_op"]["Конкретика"] = update.message.text.strip()
    return await show_fields_menu(update, context)

# — 4.11 Подтвердить
async def show_confirm(update_or_query, context: ContextTypes.DEFAULT_TYPE) -> int:
    op = context.user_data["pending_op"]
    if op.get("Конкретика") is None:
        op["Конкретика"] = "-"
    lines = [f"{k}: {v}" for k,v in op.items()]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_op"),
        InlineKeyboardButton("✏️ Изменить",    callback_data="op_start_add"),
    ]])
    if update_or_query.callback_query:
        await update_or_query.callback_query.edit_message_text("📋 Подтвердите:\n"+"\n".join(lines), reply_markup=kb)
    else:
        await update_or_query.message.reply_text("📋 Подтвердите:\n"+"\n".join(lines), reply_markup=kb)
    return STATE_CONFIRM

async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    op = context.user_data["pending_op"]
    dt = datetime.fromisoformat(op["Дата"])
    year = dt.year
    month = dt.strftime("%B")
    # TODO: append_row в Google Sheets
    await q.edit_message_text("✅ Операция добавлена в таблицу.")
    return ConversationHandler.END

# — регистрация всех хэндлеров этапа 4 —
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
            STATE_SELECT_DATE: [
                CallbackQueryHandler(handle_calendar_callback, pattern="^(calendar\\||select_date\\|)"),
            ],
            STATE_SELECT_BANK: [
                CallbackQueryHandler(handle_bank_selection, pattern="^select_bank\\|"),
            ],
            STATE_SELECT_OPERATION: [
                CallbackQueryHandler(handle_operation_selection, pattern="^select_op\\|"),
            ],
            STATE_ENTER_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount_input),
            ],
            STATE_ENTER_CLASSIFICATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_classification),
            ],
            STATE_ENTER_SPECIFIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_specific),
            ],
            STATE_CONFIRM: [
                CallbackQueryHandler(handle_confirm, pattern="^confirm_op$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(lambda u,c: ConversationHandler.END, pattern="^op_start_"),
        ],
        allow_reentry=True,
    )
    app.add_handler(conv)