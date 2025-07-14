# handlers/plans.py

import calendar
from datetime import date, datetime
from typing import Optional, Dict

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

from services.sheets_service import open_finance_and_plans
from utils.constants import (
    STATE_PLAN_MENU,
    STATE_PLAN_ADD,
    STATE_PLAN_DATE,
    STATE_PLAN_AMOUNT,
    STATE_PLAN_CLASSIFICATION,
    STATE_PLAN_SPECIFIC,
    STATE_PLAN_CONFIRM,
    STATE_PLAN_COPY,
    STATE_OP_MENU,
)
from handlers.classification import parse_sheet_date


def init_pending_plan(context):
    """
    Сбрасывает черновик нового плана.
    """
    context.user_data["pending_plan"] = {
        "Год":           None,
        "Месяц":         None,
        "Банк":          None,
        "Операция":      "План",
        "Дата":          None,
        "Сумма":         None,
        "Классификация": None,
        "Конкретика":    None,
    }


async def start_plans(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Шаг 1: показываем пользователю планы на текущий месяц.
    """
    q = update.callback_query
    await q.answer()

    url = context.user_data.get("sheet_url")
    if not url:
        return await q.edit_message_text("⚠️ Сначала подключите таблицу: /setup")

    # Открываем лист «Планы»
    _, ws_plans = open_finance_and_plans(url)
    rows = ws_plans.get_all_values()[1:]

    today = date.today()
    # Фильтруем по текущему месяцу/году
    plans = []
    for r in rows:
        dt = parse_sheet_date(r[4])
        if dt and dt.year == today.year and dt.month == today.month:
            plans.append({
                "Сумма":         r[5],
                "Классификация": r[7] or "—",
                "Конкретика":    r[8] or "—"
            })

    if not plans:
        body = "— нет планов на этот месяц —"
    else:
        body = "\n".join(
            f"{i+1}. {p['Сумма']} — {p['Классификация']} — {p['Конкретика']}"
            for i, p in enumerate(plans)
        )

    text = f"🗓 *Планы на {today.strftime('%B %Y').lower()}:*\n{body}"

    kb = [
        [InlineKeyboardButton("➕ Добавить",        callback_data="plans:add")],
        [InlineKeyboardButton("🔄 Перенести планы", callback_data="plans:copy")],
        [InlineKeyboardButton("🔙 Назад",           callback_data="plans:back")],
    ]
    await q.edit_message_text(text, parse_mode="Markdown",
                              reply_markup=InlineKeyboardMarkup(kb))
    return STATE_PLAN_MENU

# Добавление
async def handle_plan_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Шаг 2: пользователь нажал «➕ Добавить».
    Спрашиваем дату плана.
    """
    q = update.callback_query
    await q.answer()

    # 1) Сбрасываем черновик
    init_pending_plan(context)

    # 2) Локальный импорт календаря
    from handlers.operations import create_calendar
    today = date.today()
    kb = create_calendar(today.year, today.month)

    await q.edit_message_text(
        "📅 *Выберите дату плана:*",
        parse_mode="Markdown",
        reply_markup=kb
    )
    return STATE_PLAN_DATE

# Дата
async def handle_plan_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    После клика по календарю сохраняем дату и спрашиваем сумму.
    """
    q = update.callback_query
    await q.answer()

    # получаем ISO-дату
    _, iso = q.data.split("|", 1)
    dt = datetime.fromisoformat(iso).date()
    # сохраняем в черновик
    pending = context.user_data["pending_plan"]
    pending["Дата"]  = f"{dt.day:02d}.{dt.month:02d}.{dt.year}"
    pending["Год"]   = str(dt.year)
    pending["Месяц"] = dt.strftime("%B")

    # спрашиваем сумму
    await q.edit_message_text(
        f"💰 Введите *сумму* плана за {pending['Месяц']} {pending['Год']}, "
        "только положительное число:",
        parse_mode="Markdown"
    )
    return STATE_PLAN_AMOUNT

# Сумма
async def handle_plan_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Парсим введённую сумму и спрашиваем классификацию.
    """
    text = update.message.text.strip()
    try:
        amt = float(text.replace(",", "."))
        if amt <= 0:
            raise ValueError
    except ValueError:
        return await update.message.reply_text(
            "⚠️ Пожалуйста, введите *положительное* число, например `5000`.",
            parse_mode="Markdown"
        )

    context.user_data["pending_plan"]["Сумма"] = str(amt)

    # Спрашиваем классификацию
    # (используем кэш популярных из классификаций операций, аналогично вашему коду)
    banksheet = open_finance_and_plans(context.user_data["sheet_url"])[0]
    # вытаскиваем последние 5 уникальных классификаций
    rows = banksheet.get_all_values()[1:]
    popular = []
    for r in rows:
        cls = r[6]
        if cls and cls not in popular:
            popular.append(cls)
        if len(popular) >= 5:
            break

    kb = [[InlineKeyboardButton(c, callback_data=f"plans:class_{c}")] for c in popular]
    kb.append([InlineKeyboardButton("Другое", callback_data="plans:class_other")])

    await update.message.reply_text(
        "🏷️ *Выберите классификацию* или нажмите «Другое»:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return STATE_PLAN_CLASSIFICATION

# Классификация
async def handle_plan_class_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    data = q.data.split("_", 2)[2]  # после "plans:class_"
    if data == "other":
        await q.edit_message_text("📄 Введите текст *конкретики* для новой классификации:", parse_mode="Markdown")
        return STATE_PLAN_SPECIFIC
    else:
        pending = context.user_data["pending_plan"]
        pending["Классификация"] = data
        # даже когда выбрана из списка, спрашиваем конкретику
        await q.edit_message_text("📄 Введите *конкретику* для плана:", parse_mode="Markdown")
        return STATE_PLAN_SPECIFIC

async def handle_plan_specific(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    context.user_data["pending_plan"]["Конкретика"] = text

    # Показываем карточку на подтверждение
    p = context.user_data["pending_plan"]
    detail = (
        f"📋 *Новый план:*\n"
        f"📅 Дата: {p['Дата']}\n"
        f"💰 Сумма: {p['Сумма']}\n"
        f"🏷️ Классификация: {p['Классификация']}\n"
        f"📄 Конкретика: {p['Конкретика']}"
    )
    kb = [
        [InlineKeyboardButton("✅ Подтвердить", callback_data="plans:confirm"),
         InlineKeyboardButton("🔙 Отменить",    callback_data="plans:back")]
    ]
    await update.message.reply_text(detail, parse_mode="Markdown",
                                    reply_markup=InlineKeyboardMarkup(kb))
    return STATE_PLAN_CONFIRM

# Подтверждение в Google записи
async def handle_plan_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()

    url = context.user_data.get("sheet_url")
    _, ws_plans = open_finance_and_plans(url)

    row = context.user_data["pending_plan"]
    new_row = [
        row["Год"], row["Месяц"], row["Банк"],
        row["Операция"], row["Дата"], row["Сумма"],
        "",  # Остаток — формула листа
        row["Классификация"], row["Конкретика"]
    ]
    ws_plans.append_row(new_row, value_input_option="USER_ENTERED")

    await q.edit_message_text("✅ План успешно добавлен.")
    return await start_plans(update, context)


async def handle_plan_copy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Шаг 3: копируем планы прошлого месяца на текущий.
    """
    q = update.callback_query
    await q.answer()

    url = context.user_data.get("sheet_url")
    _, ws_plans = open_finance_and_plans(url)
    rows = ws_plans.get_all_values()[1:]

    today = date.today()
    pm = today.month - 1 or 12
    py = today.year if today.month > 1 else today.year - 1
    last_day = calendar.monthrange(today.year, today.month)[1]
    new_date = f"{last_day:02d}.{today.month:02d}.{today.year}"

    to_copy = []
    for r in rows:
        dt = parse_sheet_date(r[4])
        if dt and dt.year == py and dt.month == pm:
            new_row = [
                r[0],  # Год
                r[1],  # Месяц
                r[2],  # Банк
                r[3],  # Операция ("План")
                new_date,
                r[5],  # Сумма
                "",    # Остаток (формула на листе)
                r[7],  # Классификация
                r[8],  # Конкретика
            ]
            to_copy.append(new_row)

    if to_copy:
        ws_plans.append_rows(to_copy, value_input_option="USER_ENTERED")
        await q.edit_message_text("🔄 Планы скопированы на текущий месяц.")
    else:
        await q.edit_message_text("ℹ️ Нет прошлых планов для копирования.")

    return await start_plans(update, context)


async def handle_plan_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Шаг 4: кнопка «🔙 Назад» возвращает в главное меню.
    """
    q = update.callback_query
    await q.answer()
    from handlers.menu import show_main_menu
    return await show_main_menu(update, context)


from telegram.ext import ConversationHandler

def register_plans_handlers(app):
    """Регистрирует раздел «Планы» полноценным ConversationHandler."""
    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_plans, pattern=r"^menu:plans$")
        ],
        states={
            STATE_PLAN_MENU: [
                CallbackQueryHandler(handle_plan_add,   pattern=r"^plans:add$"),
                CallbackQueryHandler(handle_plan_copy,  pattern=r"^plans:copy$"),
                CallbackQueryHandler(handle_plan_back,  pattern=r"^plans:back$")
            ],
            STATE_PLAN_DATE: [
                CallbackQueryHandler(handle_plan_date, pattern=r"^select_date\|\d{4}-\d{2}-\d{2}$")
            ],
            STATE_PLAN_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_plan_amount)
            ],
            STATE_PLAN_CLASSIFICATION: [
                CallbackQueryHandler(handle_plan_class_choice, pattern=r"^plans:class_.+$")
            ],
            STATE_PLAN_SPECIFIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_plan_specific)
            ],
            STATE_PLAN_CONFIRM: [
                CallbackQueryHandler(handle_plan_confirm, pattern=r"^plans:confirm$")
            ],
        },
        fallbacks=[
            CallbackQueryHandler(handle_plan_back, pattern=r"^plans:back$")
        ],
        allow_reentry=True,
    )
    app.add_handler(conv)
