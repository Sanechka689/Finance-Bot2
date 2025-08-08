# handlers/plans.py

import calendar
from datetime import date, datetime
from typing import Optional, Dict
from utils.constants import STATE_PLAN_DATE

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters
from telegram.ext import ConversationHandler
import math

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
from handlers.operations import RU_MONTHS

import asyncio
from gspread.exceptions import APIError

import logging #_____Логи
logger = logging.getLogger(__name__) #_____Логи

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
        "💰 *Введите сумму плана* :",
        parse_mode="Markdown"
    )
    return STATE_PLAN_AMOUNT


# 3) Обработчик выбора классификации — выводим до 9 кнопок в 3 ряда
async def handle_plan_fill_classification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()

    # Собираем до 9 уникальных классификаций, отсортированных по алфавиту
    _, ws_plans = open_finance_and_plans(context.user_data["sheet_url"])
    rows = ws_plans.get_all_values()[1:]
    all_cls = {r[7] for r in rows if r[7]}
    popular = sorted(all_cls)[:9]  # первые 9

    # Формируем три ряда по 3 кнопки
    buttons = [
        InlineKeyboardButton(c, callback_data=f"plans:class_{c}")
        for c in popular
    ]
    kb_rows = [buttons[i:i+3] for i in range(0, len(buttons), 3)]
    kb = InlineKeyboardMarkup(kb_rows)

    # Редактируем сообщение и одновременно сохраняем его chat_id/message_id
    await q.edit_message_text(
        "🏷️ *Выберите классификацию* из списка (или введите свою текстом):",
        parse_mode="Markdown",
        reply_markup=kb
    )
    context.user_data["last_plan_kb"] = {
        "chat_id": q.message.chat.id,
        "message_id": q.message.message_id
    }
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
    edit_buttons = [
        InlineKeyboardButton(f"{emojis[name]} {name}", callback_data=f"plans:{action}")
        for name, _, action in fields
    ]
    kb = [
        edit_buttons[0:2],  # первая пара: Дата + Сумма
        edit_buttons[2:4],  # вторая пара: Классификация + Конкретика
    ]

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
    Показываем планы на текущий месяц.
    """
    q = update.callback_query

    # ⚠️ Этот вызов часто падает "повторно отвечено".
    if q:
        try:
            await q.answer()
        except Exception as e:
            logger.debug("start_plans: q.answer() skipped: %s", e)

    url = context.user_data.get("sheet_url")
    if not url:
        # если пришли без callback (редкий случай) — отправим новое сообщение
        if q:
            return await q.edit_message_text("⚠️ Сначала подключите таблицу: /setup")
        else:
            await update.message.reply_text("⚠️ Сначала подключите таблицу: /setup")
            return STATE_PLAN_MENU

    # 1) Открываем лист «Планы» (он второй в кортеже)
    _, ws_plans = open_finance_and_plans(url)
    all_plans = ws_plans.get_all_values()[1:]  # пропускаем заголовок

    today = date.today()
    year, month = today.year, today.month

    # 2) Фильтруем планы по дате; колонки:
    #    0:Год, 1:Месяц, 4:Дата, 5:Сумма, 6:Остаток, 7:Классификация
    display = []
    for r in all_plans:
        dt = parse_sheet_date(r[4])
        if dt and dt.year == year and dt.month == month:
            display.append({
                "Классификация":  r[7] or "—",
                "Сумма":          r[5] or "0",
                "Остаток":        r[6] or "0"
            })

    # 3) Формируем тело сообщения
    if not display:
        body = "— нет планов на этот месяц —"
    else:
        lines = [
            f"{i}. {p['Классификация']} — {p['Сумма']} — {p['Остаток']}"
            for i, p in enumerate(display, 1)
        ]
        body = "\n".join(lines)

    # 4) Заголовок с русским месяцем
    header = f"🗓 *Планы на {RU_MONTHS[month]} {year}:*\n{body}"

    # —— Сводка по планам и факту для текущего месяца ——

    def fmt(x: float) -> str:
        s = f"{x:,.2f}"
        s = s.replace(",", "X").replace(".", ",").replace("X", " ")
        return s

    # считаем суммы, предобрабатывая пробелы и NBSP
    def to_float(s: str) -> float:
        clean = s.replace("\xa0", "").replace(" ", "").replace(",", ".")
        return float(clean or "0")

    plan_sum  = sum(to_float(p["Сумма"])   for p in display)
    fact_sum  = sum(to_float(p["Остаток"]) for p in display)

    fin_ws, _   = open_finance_and_plans(url)
    fin_rows    = fin_ws.get_all_values()[1:]
    bank_total  = sum(to_float(r[5])      for r in fin_rows if r[5])

    combined = bank_total + fact_sum

    summary = (
        "\n\n💡 *Сводка по планам и факту:*\n"
        f"📝 По плану: *{fmt(plan_sum)}* ₽\n"
        f"📈 По факту: *{fmt(fact_sum)}* ₽\n"
        f"💰 Итоговый остаток: *{fmt(combined)}* ₽"
    )

    # 5) Кнопки
    kb = [
        [InlineKeyboardButton("➕ Добавить",        callback_data="plans:add")],
        [InlineKeyboardButton("🔄 Перенести планы", callback_data="plans:copy")],
        [InlineKeyboardButton("🔙 Назад",           callback_data="plans:cancel")],
    ]

    # 6) Выводим список + сводку + клавиатуру
    text = header + summary
    markup = InlineKeyboardMarkup(kb)

    if q:
        try:
            await q.edit_message_text(
                text,
                parse_mode="Markdown",
                reply_markup=markup
            )
        except Exception as e:
            # если не получилось отредактировать (например, callback уже "закрыт"),
            # отправим новую карточку, чтобы пользователь всё равно вернулся к "Планам"
            logger.warning("start_plans: edit_message_text failed, sending new message: %s", e)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text,
                parse_mode="Markdown",
                reply_markup=markup
            )
    else:
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=markup
        )

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
    pending["Месяц"] = RU_MONTHS[dt.month]
    return await show_plan_card(update, context)

# Календарь
async def change_plan_calendar_month(update: Update,context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает нажатие на стрелки < и > в календаре плана.
    Ожидает callback_data вида 'calendar|YYYY|M' или 'calendar|YYYY|MM'.
    """
    q = update.callback_query
    await q.answer()

    # q.data: 'calendar|2025|6' или 'calendar|2025|12'
    _, year_str, month_str = q.data.split("|")
    year, month = int(year_str), int(month_str)

    from handlers.operations import create_calendar
    kb = create_calendar(year, month)

    await q.edit_message_text(
        "📅 *Выберите дату плана:*",
        parse_mode="Markdown",
        reply_markup=kb
    )
    return STATE_PLAN_DATE


# Сумма
async def handle_plan_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    После ввода суммы сохраняем её (любое число: + или -) и возвращаем карточку.
    Если введено не число — остаёмся в этом же шаге и просим повторить ввод.
    """
    text = update.message.text.strip()
    try:
        # конвертируем ввод в число, допускаем запятую
        amt = float(text.replace(",", "."))
    except ValueError:
        # если не получилось — уведомляем и остаёмся в STATE_PLAN_AMOUNT
        await update.message.reply_text(
            "⚠️ Введите **корректное число** (например `-5000` или `2500`).",
            parse_mode="Markdown"
        )
        return STATE_PLAN_AMOUNT

    # сохраняем как число (для вычислений в дальнейшем)
    context.user_data["pending_plan"]["Сумма"] = amt

    # показываем обновлённую карточку
    return await show_plan_card(update, context)



# Классификация
async def handle_plan_class_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает нажатие на одну из кнопок «plans:class_<значение>»:
    - Если выбран 'other' — просим текстовый ввод классификации.
    - Иначе сохраняем выбранную и возвращаем карточку.
    """
    q = update.callback_query
    await q.answer()

    # извлекаем часть после "plans:class_"
    _, cls = q.data.split("_", 1)  

    if cls == "other":
        # Просим пользователя вписать свою классификацию
        await q.edit_message_text(
            "🏷️ *Введите свою классификацию* для плана:",
            parse_mode="Markdown"
        )
        # остаться в том же состоянии, чтобы поймать текстовый ввод
        return STATE_PLAN_CLASSIFICATION

    # Сохраняем выбранную классификацию
    context.user_data["pending_plan"]["Классификация"] = cls
    # Показываем обновлённую карточку
    return await show_plan_card(update, context)


# 4) Обработчик текстового ввода своей классификации
async def handle_plan_custom_class(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # 1) Удаляем старое сообщение‑кнопок (если было)
    kb = context.user_data.pop("last_plan_kb", None)
    if kb:
        try:
            await context.bot.delete_message(
                chat_id=kb["chat_id"],
                message_id=kb["message_id"]
            )
        except:
            pass

    # 2) Сохраняем введённую классификацию
    text = update.message.text.strip() or "-"
    context.user_data["pending_plan"]["Классификация"] = text

    # 3) Показываем обновлённую карточку плана
    return await show_plan_card(update, context)


# Конкретика
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
    logger.info(
        "handle_plan_save: callback_data=%s, user_data.sheet_url=%s",
        q.data, context.user_data.get("sheet_url")
    )

    url = context.user_data.get("sheet_url")
    _, ws_plans = open_finance_and_plans(url)

    row = context.user_data["pending_plan"]

    # 1) Формула для колонки "Остаток"
    formula = (
        f'=SUMIFS(Финансы!$F:$F;Финансы!$G:$G;INDIRECT("H"&ROW());'
        f'Финансы!$B:$B;INDIRECT("B"&ROW());Финансы!$A:$A;INDIRECT("A"&ROW()))'
        f'-INDIRECT("F"&ROW())'
    )

    # 2) Новая строка
    new_row = [
        row["Год"], row["Месяц"], row["Банк"],
        row["Операция"], row["Дата"], row["Сумма"],
        formula,
        row["Классификация"], row["Конкретика"]
    ]

    # 3) Добавляем и сразу сортируем лист "Планы" по дате (5-й столбец, E)
    ws_plans.append_row(new_row, value_input_option="USER_ENTERED")
    try:
        # gspread: сортируем по колонке E (index=5) возрастанию
        ws_plans.sort((5, 'asc'))
    except Exception as e:
        logger.error(f"Ошибка сортировки листа «Планы»: {e}")

        # 4) Сообщение-подтверждение (отдельное новое сообщение)
    await q.message.reply_text("✅ План успешно добавлен.")

    # 4.1) Сразу «закрываем» карточку, чтобы убрать клавиатуру
    try:
        await q.edit_message_text("⏳ Обновляю планы…")
    except Exception as e:
        logger.warning("Не удалось скрыть карточку плана: %s", e)

    # 4.2) Небольшая пауза — даём таблице/сортировке примениться
    await asyncio.sleep(0.8)

    # 4.3) Отправляем «Планы» ОТДЕЛЬНЫМ сообщением (чтобы оно было ПОСЛЕДНИМ)
    async def send_plans_fresh():
        url = context.user_data.get("sheet_url")
        _, ws_plans = open_finance_and_plans(url)
        all_plans = ws_plans.get_all_values()[1:]

        today = date.today()
        year, month = today.year, today.month

        # соберём строки текущего месяца
        display = []
        for r in all_plans:
            dt = parse_sheet_date(r[4])
            if dt and dt.year == year and dt.month == month:
                display.append({
                    "Классификация":  r[7] or "—",
                    "Сумма":          r[5] or "0",
                    "Остаток":        r[6] or "0"
                })

        # тело списка
        if not display:
            body = "— нет планов на этот месяц —"
        else:
            lines = [
                f"{i}. {p['Классификация']} — {p['Сумма']} — {p['Остаток']}"
                for i, p in enumerate(display, 1)
            ]
            body = "\n".join(lines)

        # заголовок
        header = f"🗓 *Планы на {RU_MONTHS[month]} {year}:*\n{body}"

        # сводка
        def fmt(x: float) -> str:
            s = f"{x:,.2f}"
            return s.replace(",", "X").replace(".", ",").replace("X", " ")

        def to_float(s: str) -> float:
            clean = s.replace("\xa0", "").replace(" ", "").replace(",", ".")
            return float(clean or "0")

        fin_ws, _ = open_finance_and_plans(url)
        fin_rows   = fin_ws.get_all_values()[1:]
        plan_sum   = sum(to_float(p["Сумма"])   for p in display)
        fact_sum   = sum(to_float(p["Остаток"]) for p in display)
        bank_total = sum(to_float(r[5]) for r in fin_rows if r[5])
        combined   = bank_total + fact_sum

        summary = (
            "\n\n💡 *Сводка по планам и факту:*\n"
            f"📝 По плану: *{fmt(plan_sum)}* ₽\n"
            f"📈 По факту: *{fmt(fact_sum)}* ₽\n"
            f"💰 Итоговый остаток: *{fmt(combined)}* ₽"
        )

        # клавиатура «Планов»
        kb = [
            [InlineKeyboardButton("➕ Добавить",        callback_data="plans:add")],
            [InlineKeyboardButton("🔄 Перенести планы", callback_data="plans:copy")],
            [InlineKeyboardButton("🔙 Назад",           callback_data="plans:cancel")],
        ]

        # отправляем НОВОЕ сообщение (а не редактируем старое)
        await context.bot.send_message(
            chat_id=q.message.chat.id,
            text=header + summary,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    # Аккуратные ретраи на случай 429 от Google Sheets
    for delay in (0.0, 1.0, 2.0):
        try:
            await send_plans_fresh()
            break
        except APIError as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            if code == 429:
                logger.warning("Sheets 429, повтор через %.1fs", max(delay, 1.0))
                await asyncio.sleep(max(delay, 1.0))
                continue
            raise
        except Exception as e:
            logger.exception("Не удалось отправить «Планы»: %s", e)
            break

    return STATE_PLAN_MENU



# Копирвание Планов
async def handle_plan_copy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Шаг 3: копируем планы прошлого месяца на текущий,
    обновляем год/месяц и вбрасываем формулу остатка.
    """
    q = update.callback_query
    await q.answer()

    url = context.user_data.get("sheet_url")
    _, ws_plans = open_finance_and_plans(url)
    rows = ws_plans.get_all_values()[1:]

    today = date.today()
    prev_month = today.month - 1 or 12
    prev_year  = today.year if today.month > 1 else today.year - 1

    # дата нового плана — последний день текущего месяца
    last_day = calendar.monthrange(today.year, today.month)[1]
    new_date = f"{last_day:02d}.{today.month:02d}.{today.year}"
    new_year  = str(today.year)
    new_month = RU_MONTHS[today.month]  # по‑русски

    to_copy = []
    for r in rows:
        old_dt = parse_sheet_date(r[4])
        if not (old_dt and old_dt.year == prev_year and old_dt.month == prev_month):
            continue

        cls   = r[7]  # классификация
        plan  = r[5]  # плановая сумма как строка
        spec  = r[8]  # конкретика

        # Формула остатка: SUMIFS по "Финансы" минус INDIRECT("F"&ROW())
        formula = (
            f'=SUMIFS(Финансы!$F:$F;Финансы!$G:$G;INDIRECT("H"&ROW());'
            f'Финансы!$B:$B;INDIRECT("B"&ROW());Финансы!$A:$A;INDIRECT("A"&ROW()))'
            f'-INDIRECT("F"&ROW())'
        )

        new_row = [
            new_year,         # год текущего месяца
            new_month,        # месяц текущего месяца
            r[2],             # банк
            r[3],             # Операция ("План")
            new_date,         # дата — последний день текущего месяца
            plan,             # сумма (строка или число)
            formula,          # остаток — динамическая формула
            cls,              # классификация
            spec,             # конкретика
        ]
        to_copy.append(new_row)

    if to_copy:
        ws_plans.append_rows(to_copy, value_input_option="USER_ENTERED")
        # краткое уведомление (можно опустить, если не нужно)
        await q.edit_message_text("🔄 Планы перенесены на текущий месяц.")
    else:
        await q.edit_message_text("ℹ️ Нет прошлых планов для копирования.")

    # и сразу показываем обновлённую карточку «Планы на …»
    return await start_plans(update, context)



async def handle_plan_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Шаг 4: кнопка «🔙 Назад» возвращает в главное меню.
    """
    q = update.callback_query
    await q.answer()
    from handlers.menu import show_main_menu
    return await show_main_menu(update, context)

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
                CallbackQueryHandler(change_plan_calendar_month, pattern=r"^calendar\|\d{4}\|\d{1,2}$"),
                CallbackQueryHandler(handle_plan_date, pattern=r"^select_date\|\d{4}-\d{2}-\d{2}$")
            ],
            STATE_PLAN_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_plan_amount)
            ],
            STATE_PLAN_CLASSIFICATION: [
                CallbackQueryHandler(handle_plan_class_choice, pattern=r"^plans:class_.+$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_plan_custom_class)
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
