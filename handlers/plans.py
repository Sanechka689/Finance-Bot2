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
        "Банк":          "Планы",
        "Операция":      "План",
        "Дата":          None,
        "Сумма":         None,
        "Классификация": None,
        "Конкретика":    None,
    }


async def handle_plan_fill_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Пользователь нажал «📅 Дата» — открываем календарь.
    """
    q = update.callback_query
    await q.answer()
    from handlers.operations import create_calendar
    today = date.today()
    kb = create_calendar(today.year, today.month)
    await q.edit_message_text(
        "📅 *Выберите дату плана:*",
        parse_mode="Markdown",
        reply_markup=kb
    )
    return STATE_PLAN_DATE


async def handle_plan_fill_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Пользователь нажал «💰 Сумма» — просим ввести значение.
    """
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "💰 *Введите сумму плана* (только положительное число):",
        parse_mode="Markdown"
    )
    return STATE_PLAN_AMOUNT


async def handle_plan_fill_classification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Пользователь нажал «🏷️ Классификация» — показываем топ-10 и ручной ввод.
    """
    q = update.callback_query
    await q.answer()
    banksheet = open_finance_and_plans(context.user_data["sheet_url"])[0]
    rows = banksheet.get_all_values()[1:]
    popular = []
    for r in rows:
        cls = r[6]
        if cls and cls not in popular:
            popular.append(cls)
        if len(popular) >= 10:
            break
    kb = [[InlineKeyboardButton(c, callback_data=f"plans:class_{c}")] for c in popular]
    kb.append([InlineKeyboardButton("Впишите своё", callback_data="plans:class_other")])
    await q.edit_message_text(
        "🏷️ *Выберите классификацию* из списка или впишите своё:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return STATE_PLAN_CLASSIFICATION


async def handle_plan_fill_specific(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Пользователь нажал «📄 Конкретика» — просим ввести текст.
    """
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "📄 *Введите конкретику* для плана:",
        parse_mode="Markdown"
    )
    return STATE_PLAN_SPECIFIC


# Показывает карточку нового плана с полями и кнопками
async def show_plan_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Поддерживаем как callback_query, так и текстовые вызовы
    if update.callback_query:
        q = update.callback_query
        await q.answer()
        send = q.edit_message_text
    else:
        send = update.message.reply_text

    pending = context.user_data.setdefault("pending_plan", {})
    text = "📋 *Новый план:*\n"
    # Список полей: (Имя, текущее значение, callback-action)
    fields = [
        ("Дата",           pending.get("Дата")          or "—", "fill_date"),
        ("Сумма",          pending.get("Сумма")         or "—", "fill_amount"),
        ("Классификация",  pending.get("Классификация") or "—", "fill_classification"),
        ("Конкретика",     pending.get("Конкретика")    or "—", "fill_specific"),
    ]
    emojis = {"Дата":"📅","Сумма":"💰","Классификация":"🏷️","Конкретика":"📄"}

    # Формируем текст карточки
    for name, val, _ in fields:
        text += f"{emojis[name]} *{name}:* {val}\n"

    # Формируем клавиатуру
    kb = []
    for name, _, action in fields:
        label = f"{emojis[name]} {name}"
        kb.append([InlineKeyboardButton(label, callback_data=f"plans:{action}")])

    # Кнопки Назад и Сохранить (если заполнены обязательные поля)
    btns = [InlineKeyboardButton("🔙 Назад", callback_data="plans:cancel")]
    if pending.get("Дата") and pending.get("Сумма") and pending.get("Классификация"):
        btns.append(InlineKeyboardButton("✅ Сохранить", callback_data="plans:save"))
    kb.append(btns)

    await send(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    return STATE_PLAN_ADD


# Обработчик «Отменить» (назад к списку планов)
async def handle_plan_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    from handlers.menu import show_main_menu
    return await show_main_menu(update, context)


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
        # Кнопка «Добавить» запускает STATE_PLAN_ADD
        [InlineKeyboardButton("➕ Добавить",        callback_data="plans:add")],
        # Кнопка «Перенести планы» запускает STATE_PLAN_COPY
        [InlineKeyboardButton("🔄 Перенести планы", callback_data="plans:copy")],
        # Кнопка «Назад» должна совпадать с plans:cancel, а не plans:back
        [InlineKeyboardButton("🔙 Назад",           callback_data="plans:cancel")],
    ]
    await q.edit_message_text(text, parse_mode="Markdown",
                              reply_markup=InlineKeyboardMarkup(kb))
    return STATE_PLAN_MENU

# Добавление
async def handle_plan_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Шаг 2: пользователь нажал «➕ Добавить».
    Инициализируем черновик и показываем карточку.
    """
    init_pending_plan(context)
    return await show_plan_card(update, context)

# Дата
async def handle_plan_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    После выбора даты сохраняем её и возвращаем карточку.
    """
    q = update.callback_query
    await q.answer()
    _, iso = q.data.split("|", 1)
    dt = datetime.fromisoformat(iso).date()
    pending = context.user_data["pending_plan"]
    pending["Дата"]  = f"{dt.day:02d}.{dt.month:02d}.{dt.year}"
    pending["Год"]   = str(dt.year)
    pending["Месяц"] = dt.strftime("%B")
    return await show_plan_card(update, context)

async def change_plan_calendar_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает стрелки < и > в календаре плана.
    """
    q = update.callback_query
    await q.answer()
    action, ym = q.data.split("|", 1)       # e.g. "prev_month|2025-07"
    y, m = map(int, ym.split("-"))
    from handlers.operations import create_calendar
    kb = create_calendar(y, m)
    await q.edit_message_text(
        "📅 *Выберите дату плана:*",
        parse_mode="Markdown",
        reply_markup=kb
    )
    return STATE_PLAN_DATE


# Сумма
async def handle_plan_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    После ввода суммы сохраняем её и возвращаем карточку.
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
    return await show_plan_card(update, context)


# Классификация
async def handle_plan_class_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    data = q.data.split("_", 2)[2]  # после "plans:class_"
    pending = context.user_data["pending_plan"]
    if data == "other":
        await q.edit_message_text("📄 Введите *конкретику* для новой классификации:", parse_mode="Markdown")
        return STATE_PLAN_SPECIFIC
    pending["Классификация"] = data
    return await show_plan_card(update, context)

async def handle_plan_specific(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Сохраняем введённую конкретику и возвращаем карточку.
    """
    text = update.message.text.strip()
    context.user_data["pending_plan"]["Конкретика"] = text or "-"
    return await show_plan_card(update, context)

# Подтверждение в Google записи
async def handle_plan_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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

from telegram.ext import ConversationHandler

def register_plans_handlers(app):
    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_plans, pattern=r"^menu:plans$")
        ],
        states={
            STATE_PLAN_MENU: [
                # ➕ Добавить
                CallbackQueryHandler(handle_plan_add,     pattern=r"^plans:add$"),
                # 🔄 Перенести планы
                CallbackQueryHandler(handle_plan_copy,    pattern=r"^plans:copy$"),
                # 🔙 Назад — теперь plans:cancel
                CallbackQueryHandler(handle_plan_cancel,  pattern=r"^plans:cancel$"),
                # резервно обрабатываем старый plans:back
                CallbackQueryHandler(handle_plan_cancel,  pattern=r"^plans:back$")
            ],
            STATE_PLAN_ADD: [
                CallbackQueryHandler(handle_plan_fill_date,           pattern=r"^plans:fill_date$"),
                CallbackQueryHandler(handle_plan_fill_amount,         pattern=r"^plans:fill_amount$"),
                CallbackQueryHandler(handle_plan_fill_classification, pattern=r"^plans:fill_classification$"),
                CallbackQueryHandler(handle_plan_fill_specific,       pattern=r"^plans:fill_specific$"),
                CallbackQueryHandler(handle_plan_save,                pattern=r"^plans:save$"),
                CallbackQueryHandler(handle_plan_cancel,              pattern=r"^plans:cancel$")
            ],
            STATE_PLAN_DATE: [
                CallbackQueryHandler(change_plan_calendar_month,pattern=r"^(prev_month|next_month)\|\d{4}-\d{2}$"),
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
        },
        fallbacks=[
            CallbackQueryHandler(handle_plan_cancel, pattern=r"^plans:cancel$")
        ],
        allow_reentry=True,
    )
    app.add_handler(conv)
