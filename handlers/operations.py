# handlers/operations.py
# Этап 4: ручное заполнение операций (бесплатный тариф)

from datetime import datetime
import calendar
import pytz

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram import Update
from telegram.ext import (
    ConversationHandler,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from handlers.menu import show_main_menu, handle_menu_selection

from utils.constants import (
    STATE_OP_MENU,
    STATE_OP_FIELD_CHOOSE,
    STATE_SELECT_DATE,
    STATE_SELECT_BANK,
    STATE_SELECT_OPERATION,
    STATE_ENTER_AMOUNT,
    STATE_ENTER_CLASSIFICATION,
    STATE_ENTER_SPECIFIC,
)
from utils.state import init_user_state
from services.sheets_service import open_finance_and_plans

# Месяцы по-русски
RU_MONTHS = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
}

# Главная клавиатура "Добавить/Меню"
def main_menu_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("➕ Добавить", callback_data="op_start_add"),
        InlineKeyboardButton("📋 Меню",     callback_data="menu:open"),
    ]])

# 1. Формат текста черновика, учитываем Перевод
def format_op(op: dict) -> str:
    lines = []
    if op.get("Операция") == "Перевод":
        for k in ["Дата", "Банк Отправитель", "Банк Получатель", "Сумма"]:
            v = op.get(k)
            if k == "Дата" and v:
                dt = datetime.fromisoformat(v)
                v = dt.strftime("%d.%m.%Y")
            lines.append(f"{k}: {v if v is not None else '—'}")
    else:
        for k in ["Дата", "Банк", "Операция", "Сумма", "Классификация", "Конкретика"]:
            v = op.get(k)
            if k == "Дата" and v:
                dt = datetime.fromisoformat(v)
                v = dt.strftime("%d.%m.%Y")
            lines.append(f"{k}: {v if v is not None else '—'}")
    return "\n".join(lines)

# 4.1 — команда /add
async def start_op(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tariff = context.user_data.get("tariff", "tariff_free")
    if tariff != "tariff_free":
        return await update.message.reply_text("⚠️ Ручной ввод доступен только на бесплатном тарифе.")
    init_user_state(context)
    await update.message.reply_text(
        "✏️ Этап добавления операции: выберите действие",
        reply_markup=main_menu_kb()
    )
    return STATE_OP_MENU

# общий хэндлер отмены / возврата в главное меню
async def go_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    init_user_state(context)
    await q.edit_message_text(
        "✏️ Этап добавления операции: выберите действие",
        reply_markup=main_menu_kb()
    )
    return STATE_OP_MENU

# 4.2 — обработка «Добавить» / «Меню»
async def on_op_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if q.data == "op_start_add":
        return await show_fields_menu(update, context)
    init_user_state(context)
    await q.edit_message_text("Вы в главном меню.", reply_markup=main_menu_kb())
    return STATE_OP_MENU

# 4.3 — меню полей, учёт Перевод
async def show_fields_menu(update_or_query, context: ContextTypes.DEFAULT_TYPE) -> int:
    op = context.user_data["pending_op"]
    if op.get("Операция") == "Перевод":
        keyboard = [
            [InlineKeyboardButton("📅 Дата",            callback_data="field|Дата"),
             InlineKeyboardButton("🏦 Отправитель",     callback_data="field|Банк Отправитель")],
            [InlineKeyboardButton("🏦 Получатель",      callback_data="field|Банк Получатель"),
             InlineKeyboardButton("➖ Сумма",           callback_data="field|Сумма")],
            [InlineKeyboardButton("❌ Отмена",          callback_data="op_cancel")],
        ]
        if all(op.get(k) is not None for k in ["Дата","Банк Отправитель","Банк Получатель","Сумма"]):
            keyboard.append([InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_op")])
    else:
        keyboard = [
            [InlineKeyboardButton("📅 Дата",       callback_data="field|Дата"),
             InlineKeyboardButton("🏦 Банк",       callback_data="field|Банк")],
            [InlineKeyboardButton("⚙️ Операция",   callback_data="field|Операция"),
             InlineKeyboardButton("➖ Сумма",      callback_data="field|Сумма")],
            [InlineKeyboardButton("🏷️ Классификация", callback_data="field|Классификация"),
             InlineKeyboardButton("🔍 Конкретика",     callback_data="field|Конкретика")],
            [InlineKeyboardButton("❌ Отмена",      callback_data="op_cancel")],
        ]
        if all(op.get(k) is not None for k in ["Дата","Банк","Операция","Сумма","Классификация"]):
            keyboard.append([InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_op")])

    text = format_op(op)
    if update_or_query.callback_query:
        await update_or_query.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update_or_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return STATE_OP_FIELD_CHOOSE

# 4.4 — обработка выбора поля / confirm / cancel
async def choose_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if q.data == "op_cancel":
        return await go_main_menu(update, context)
    if q.data == "confirm_op":
        return await handle_confirm(update, context)

    field = q.data.split("|",1)[1]
    context.user_data["current_field"] = field

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
    if field == "Банк Отправитель":
        return await ask_bank(update, context)
    if field == "Банк Получатель":
        return await ask_bank(update, context)

# 4.5 — календарь с RU_MONTHS
def get_prev_year_month(y,m): return (y-1,12) if m==1 else (y,m-1)
def get_next_year_month(y,m): return (y+1,1) if m==12 else (y,m+1)

def create_calendar(year:int,month:int)->InlineKeyboardMarkup:
    today = datetime.now(pytz.timezone("Europe/Moscow")).date()
    markup=[]; py,pm=get_prev_year_month(year,month); ny,nm=get_next_year_month(year,month)
    markup.append([
        InlineKeyboardButton("<",callback_data=f"calendar|{py}|{pm}"),
        InlineKeyboardButton(f"{RU_MONTHS[month]} {year}",callback_data="ignore"),
        InlineKeyboardButton(">",callback_data=f"calendar|{ny}|{nm}")
    ])
    markup.append([InlineKeyboardButton(d,callback_data="ignore") for d in ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]])
    for week in calendar.monthcalendar(year,month):
        row=[]
        for day in week:
            if day==0:
                row.append(InlineKeyboardButton(" ",callback_data="ignore"))
            else:
                ds=f"{year}-{month:02d}-{day:02d}"
                label=f"🔴{day}" if (year,month,day)==(today.year,today.month,today.day) else str(day)
                row.append(InlineKeyboardButton(label,callback_data=f"select_date|{ds}"))
        markup.append(row)
    return InlineKeyboardMarkup(markup)

async def ask_date(update_or_query, context: ContextTypes.DEFAULT_TYPE) -> int:
    now=datetime.now(pytz.timezone("Europe/Moscow"))
    cal=create_calendar(now.year,now.month)
    if update_or_query.callback_query:
        await update_or_query.callback_query.edit_message_text("📅 Выберите дату:",reply_markup=cal)
    else:
        await update_or_query.message.reply_text("📅 Выберите дату:",reply_markup=cal)
    return STATE_SELECT_DATE

async def handle_calendar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q=update.callback_query; await q.answer(); data=q.data
    if data.startswith("calendar|"):
        _,y,m=data.split("|"); cal=create_calendar(int(y),int(m))
        await q.edit_message_reply_markup(cal); return STATE_SELECT_DATE
    if data.startswith("select_date|"):
        _,ds=data.split("|"); context.user_data["pending_op"]["Дата"]=ds
        return await show_fields_menu(update, context)

# 4.6 — выбор банка
async def ask_bank(update_or_query, context: ContextTypes.DEFAULT_TYPE) -> int:
    ws,_=open_finance_and_plans(context.user_data["sheet_url"])
    banks=sorted(set(ws.col_values(3)[1:]))
    kb=InlineKeyboardMarkup([[InlineKeyboardButton(b,callback_data=f"select_bank|{b}")] for b in banks])
    if update_or_query.callback_query:
        await update_or_query.callback_query.edit_message_text("🏦 Выберите банк:",reply_markup=kb)
    else:
        await update_or_query.message.reply_text("🏦 Выберите банк:",reply_markup=kb)
    return STATE_SELECT_BANK

async def handle_bank_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q=update.callback_query; await q.answer()
    bank=q.data.split("|",1)[1]
    field=context.user_data["current_field"]
    if field=="Банк Отправитель":
        context.user_data["pending_op"]["Банк Отправитель"]=bank
    elif field=="Банк Получатель":
        context.user_data["pending_op"]["Банк Получатель"]=bank
    else:
        context.user_data["pending_op"]["Банк"]=bank
    return await show_fields_menu(update, context)

# 4.7 — выбор операции + возвращаем жёсткую валидацию суммы если уже введена
async def ask_operation(update_or_query, context: ContextTypes.DEFAULT_TYPE) -> int:
    kb=InlineKeyboardMarkup([[
        InlineKeyboardButton("Пополнение",callback_data="select_op|Пополнение"),
        InlineKeyboardButton("Трата",     callback_data="select_op|Трата"),
        InlineKeyboardButton("Перевод",   callback_data="select_op|Перевод"),
    ]])
    if update_or_query.callback_query:
        await update_or_query.callback_query.edit_message_text("⚙️ Выберите тип операции:",reply_markup=kb)
    else:
        await update_or_query.message.reply_text("⚙️ Выберите тип операции:",reply_markup=kb)
    return STATE_SELECT_OPERATION

async def handle_operation_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q=update.callback_query; await q.answer()
    op_type=q.data.split("|",1)[1]
    pending=context.user_data["pending_op"]
    pending["Операция"]=op_type
    if op_type=="Перевод":
        pending["Классификация"]="Перевод"
    # жёсткая проверка уже введённой суммы
    amt=pending.get("Сумма")
    if amt is not None:
        if op_type=="Пополнение" and amt<0:
            await q.message.reply_text("⚠️ Для пополнения введите ≥0.")
            return await ask_amount(update, context)
        if op_type=="Трата" and amt>=0:
            await q.message.reply_text("⚠️ Для траты введите отрицательное число.")
            return await ask_amount(update, context)
        if op_type=="Перевод" and amt<=0:
            await q.message.reply_text("⚠️ Для перевода введите >0.")
            return await ask_amount(update, context)
    return await show_fields_menu(update, context)

# 4.8 — ввод суммы + жёсткая валидация
async def ask_amount(update_or_query, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg="➖ Введите сумму (только число):"
    if update_or_query.callback_query:
        await update_or_query.callback_query.edit_message_text(msg)
    else:
        await update_or_query.message.reply_text(msg)
    return STATE_ENTER_AMOUNT

async def handle_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text=update.message.text.strip().replace(",",".")
    try:
        amt=float(text)
    except:
        await update.message.reply_text("⚠️ Введите корректное число.")
        return STATE_ENTER_AMOUNT
    op=context.user_data["pending_op"].get("Операция")
    if op=="Пополнение" and amt<0:
        await update.message.reply_text("⚠️ Для пополнения введите ≥0.")
        return STATE_ENTER_AMOUNT
    if op=="Трата" and amt>=0:
        await update.message.reply_text("⚠️ Для траты введите отрицательное число.")
        return STATE_ENTER_AMOUNT
    if op=="Перевод" and amt<=0:
        await update.message.reply_text("⚠️ Для перевода введите >0.")
        return STATE_ENTER_AMOUNT
    context.user_data["pending_op"]["Сумма"]=amt
    return await show_fields_menu(update, context)

# 4.9 — ввод классификации
async def input_classification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["pending_op"]["Классификация"]=update.message.text.strip()
    return await show_fields_menu(update, context)

# 4.10 — ввод конкретики
async def input_specific(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["pending_op"]["Конкретика"]=update.message.text.strip()
    return await show_fields_menu(update, context)

# 4.11 — запись и возврат, учёт Перевод
async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q=update.callback_query; await q.answer()
    op=context.user_data["pending_op"]
    dt=datetime.fromisoformat(op["Дата"])
    year, month=dt.year, RU_MONTHS[dt.month]
    date_str=dt.strftime("%d.%m.%Y")
    ws, _ = open_finance_and_plans(context.user_data["sheet_url"])

    if op["Операция"]=="Перевод":
        src=op["Банк Отправитель"]; dst=op["Банк Получатель"]; amt=op["Сумма"]
        ws.append_row([year,month,src,"Перевод",date_str,-amt,"Перевод",dst], value_input_option="USER_ENTERED")
        ws.append_row([year,month,dst,"Перевод",date_str,amt,"Перевод",src],  value_input_option="USER_ENTERED")
    else:
        cls=op["Классификация"]; spec=op.get("Конкретика") or "-"
        ws.append_row([year,month,op["Банк"],op["Операция"],date_str,op["Сумма"],cls,spec], value_input_option="USER_ENTERED")

    # ←————— СОРТИРОВКИ ПО ДАТЕ —————→
    # 1. Получаем ID листа
    sheet_id = ws._properties['sheetId']
    # 2. Формируем запрос
    sort_request = {
        "requests": [{
            "sortRange": {
                "range": {
                    "sheetId":           sheet_id,
                    "startRowIndex":     1,  # пропускаем заголовок
                    "startColumnIndex":  0,  # А начинаес с столбца
                    "endColumnIndex":    8,  # до H не включительно → столбец H имеет индекс 7, но endColumnIndex = 8
                },
                "sortSpecs": [{
                    "dimensionIndex": 4,     # колонка E (нулевой индекс A=0, B=1, … E=4)
                    "sortOrder":      "DESCENDING"
                }]
            }
        }]
    }
    # 3. Отправляем запрос в API
    ws.spreadsheet.batch_update(sort_request)

    await q.edit_message_text("✅ Операция добавлена в таблицу.")
    init_user_state(context)
    await q.message.reply_text(
        "✏️ Этап добавления операции: выберите действие",
        reply_markup=main_menu_kb()
    )
    return STATE_OP_MENU

# — регистрация этапа 4 —
def register_operations_handlers(app):
    conv = ConversationHandler(
        entry_points=[CommandHandler("add", start_op)],
        states={
            STATE_OP_MENU: [
                # 1) Все menu:* коллбэки обрабатываем в handlers.menu
                CallbackQueryHandler(handle_menu_selection, pattern="^menu:"),
                # 2) Далее — ваша логика «➕ Добавить / Меню»  
                CallbackQueryHandler(on_op_menu,        pattern="^op_"),
            ],
            STATE_OP_FIELD_CHOOSE: [
                CallbackQueryHandler(choose_field, pattern="^(field\\||confirm_op|op_cancel)"),
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
        },
        fallbacks=[
            CallbackQueryHandler(go_main_menu, pattern="^op_cancel$"),
        ],
        allow_reentry=True,
    )
    app.add_handler(conv)
