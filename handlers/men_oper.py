# handlers/men_oper.py

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import (
    CallbackQueryHandler, ConversationHandler,
    ContextTypes, MessageHandler, filters
)
from services.sheets_service import open_finance_and_plans
from utils.constants import (
    STATE_OP_MENU,
    STATE_OP_LIST, STATE_OP_SELECT,
    STATE_OP_CONFIRM, STATE_OP_EDIT_CHOICE,
    STATE_OP_EDIT_INPUT
)

# — сортировка по дате «Я → А»
SORT_REQUEST = {
    "requests":[{ "sortRange": {
        "range": {
            "sheetId":           None,  # заполним динамически
            "startRowIndex":     1,
            "startColumnIndex":  0,
            "endColumnIndex":    8,
        },
        "sortSpecs":[{ "dimensionIndex":4, "sortOrder":"DESCENDING" }]
    }}]
}

# — точные заголовки «Финансы»
EXPECTED_HEADERS = ["Год","Месяц","Банк","Операция","Дата","Сумма","Классификация","Конкретика"]

import re

# Для распознавания «7 июня, пт» и т.п.
GENITIVE_MONTHS = {
    "января": 1, "февраля": 2, "марта": 3,   "апреля": 4,
    "мая":    5, "июня":    6, "июля":   7,   "августа": 8,
    "сентября":9, "октября":10, "ноября":11, "декабря":12,
}


# Правельный выход в меню
async def exit_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Выход из ветки операций в главное меню.
    """
    # отвечаем на коллбэк, чтобы убрать часики
    if update.callback_query:
        await update.callback_query.answer()

    # Локальный импорт, чтобы не было циклической зависимости на уровне модуля
    from handlers.menu import show_main_menu

    # вызываем функцию показа главного меню
    return await show_main_menu(update, context)

# Ветка Операции
async def start_men_oper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запуск ветки «Операции»."""
    query = update.callback_query
    await query.answer()
    url = context.user_data.get("sheet_url")
    if not url:
        return await query.edit_message_text("⚠️ Сначала подключите таблицу: /setup")
    
    ws, _ = open_finance_and_plans(url)
    # 1) Отсортировать лист
    sheet_id = ws._properties["sheetId"]
    SORT_REQUEST["requests"][0]["sortRange"]["range"]["sheetId"] = sheet_id
    ws.spreadsheet.batch_update(SORT_REQUEST)
    
    # 2) Забрать все записи
    all_values = ws.get_all_values()   # возвращает header + строки данных
    data_rows = all_values[1:1+10]     # первые 10 записей, пропуская заголовок
    last_ops = []
    for row_values in data_rows:
        last_ops.append({
            "Год":             row_values[0],
            "Месяц":           row_values[1],
            "Банк":            row_values[2],
            "Операция":        row_values[3],
            "Дата":            row_values[4],
            "Сумма":           row_values[5],
            "Классификация":   row_values[6],
            "Конкретика":      row_values[7] or "",
        })
    context.user_data["last_ops"] = last_ops

    # 3) Сформировать сообщение
    lines = []
    for i, row in enumerate(last_ops):
        lines.append(
            f"{i}. {row['Банк']}   {row['Сумма']}   {row['Классификация']}   {row['Дата']}"
        )
    text = "📝 *Последние 10 операций:*\n" + "\n".join(lines)

    # 4) Кнопки: по каждой операции — её номер, и «Назад» в меню
    kb = [
        [InlineKeyboardButton(str(i), callback_data=f"op_select_{i}") for i in [1, 2, 3] if i < len(last_ops)],
        [InlineKeyboardButton(str(i), callback_data=f"op_select_{i}") for i in [4, 5, 6] if i < len(last_ops)],
        [InlineKeyboardButton(str(i), callback_data=f"op_select_{i}") for i in [7, 8, 9] if i < len(last_ops)],
    ]
    # «0» в отдельном ряду, если есть операция с индексом 0
    if len(last_ops) > 0:
        kb.append([InlineKeyboardButton("0", callback_data="op_select_0")])
    # в самом низу большая кнопка «Назад»
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="menu:open")])

    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return STATE_OP_SELECT


async def handle_op_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пользователь нажал на номер 0–9 — показываем детали + кнопки действий."""
    query = update.callback_query
    await query.answer()
    idx = int(query.data.split("_")[-1])
    row = context.user_data["last_ops"][idx]
        # row — это dict с полями из листа
    context.user_data["editing_op"] = {
        "index":    idx,
        "original": row.copy(),   # скопируем исходную строку для поиска на листе
        "data":     row           # сюда будем записывать изменения
    }

    # Собираем подробный текст
    detail = (
        f"📋 *Операция #{idx}:*\n"
        f"🏦 Банк: {row['Банк']}\n"
        f"⚙️ Операция: {row['Операция']}\n"
        f"📅 Дата: {row['Дата']}\n"
        f"💰 Сумма: {row['Сумма']}\n"
        f"🏷️ Классификация: {row['Классификация']}\n"
        f"📄 Конкретика: {row['Конкретика'] or '—'}"
    )

    # Кнопки
    buttons = []
    buttons += [
        InlineKeyboardButton("✏️ Изменить", callback_data="op_edit"),
        InlineKeyboardButton("🗑 Удалить", callback_data="op_delete"),
        InlineKeyboardButton("🔙 Назад",   callback_data="op_back"),
    ]

    await query.edit_message_text(
        detail, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([buttons])
    )
    return STATE_OP_CONFIRM


async def handle_op_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняем изменения в той же строке."""
    query = update.callback_query
    await query.answer("Сохраняю…", show_alert=False)

    # 1) Достаём URL и данные
    url = context.user_data.get("sheet_url")
    edit = context.user_data.get("editing_op", {})
    orig = edit.get("original")   # СТАРЫЕ значения
    new  = edit.get("data")       # НОВЫЕ значения

    if not url or not orig or not new:
        await query.edit_message_text("⚠️ Нет данных для сохранения.")
        return await start_men_oper(update, context)

    # 2) Открываем таблицу
    ws, _ = open_finance_and_plans(url)

    # 3) Ищем номер строки по оригинальным Банк/Дата/Сумма
    all_vals = ws.get_all_values()
    row_number = None
    for i, values in enumerate(all_vals[1:], start=2):
        if (
            values[2] == orig["Банк"] and
            values[4] == orig["Дата"] and
            values[5] == str(orig["Сумма"])
        ):
            row_number = i
            break

    if not row_number:
        await query.edit_message_text("⚠️ Не удалось найти строку для обновления.")
        return await start_men_oper(update, context)

    # 4) Собираем список новых значений по столбцам A–H
    # ——— Нормализация даты в DD.MM.YYYY ———
    raw_date = new.get("Дата")
    # если уже в ISO-формате YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw_date):
        y, m, d = raw_date.split("-")
        date_for_sheet = f"{d}.{m}.{y}"
    else:
        # ожидаем вид "11 июля, пт" или "11 июля"
        day_month = raw_date.split(",", 1)[0].strip()   # "11 июля"
        parts = day_month.split()
        try:
            day = int(parts[0])
            gen_month = parts[1].lower()
            month = GENITIVE_MONTHS.get(gen_month, 0)
            year = int(new.get("Год"))
            date_for_sheet = f"{day:02d}.{month:02d}.{year}"
        except Exception:
            # не удалось распарсить — оставляем как есть
            date_for_sheet = raw_date
            
    # 5) Собираем список новых значений по столбцам A–H        
    new_row = [
        new.get("Год"),
        new.get("Месяц"),
        new.get("Банк"),
        new.get("Операция"),
        date_for_sheet,
        new.get("Сумма"),
        new.get("Классификация"),
        new.get("Конкретика") or "-"
    ]

    # 5) Перезаписываем эту же строку одним вызовом
    cell_range = f"A{row_number}:H{row_number}"
    ws.update(cell_range, [new_row], value_input_option="USER_ENTERED")

    # 6) Уведомляем и возвращаемся к списку операций
    await query.edit_message_text("✅ Операция успешно обновлена.")
    context.user_data.pop("editing_op", None)
    return await start_men_oper(update, context)


async def handle_op_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query

    await query.answer()
    # показываем пользователю pop-up об удалении
    await query.edit_message_text("🗑 Операция удалена.")

    # удаляем строку в Google Sheets
    ws, _ = open_finance_and_plans(context.user_data["sheet_url"])
    row = context.user_data["editing_op"]["data"]

    # парсим сумму из выбранной операции
    try:
        target_sum = float(
            str(row["Сумма"])
            .replace("\xa0","")
            .replace(" ","")
            .replace(",",".")
        )
    except (KeyError, ValueError):
        target_sum = None  # на всякий случай

    all_vals = ws.get_all_values()
    for idx, values in enumerate(all_vals[1:], start=2):
        bank_cell = values[2]
        date_cell = values[4]
        # нормализуем сумму из листа
        try:
            sum_cell = float(
                str(values[5])
                .replace("\xa0","")
                .replace(" ","")
                .replace(",",".")
            )
        except ValueError:
            continue

        if (
            bank_cell == row["Банк"] and
            date_cell == row["Дата"] and
            (target_sum is None or sum_cell == target_sum)
        ):
            ws.delete_rows(idx)
            break

    # сразу перерисовываем обновлённый список последних 10 операций
    return await start_men_oper(update, context)

async def handle_op_edit_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()

    edit = context.user_data["editing_op"]
    idx = edit["index"]
    row = edit["data"]

    # Собираем detail-card так же, как в handle_op_select
    detail = (
        f"📋 *Операция #{idx}:*\n"
        f"🏦 Банк: {row['Банк']}\n"
        f"⚙️ Операция: {row['Операция']}\n"
        f"📅 Дата: {row['Дата']}\n"
        f"💰 Сумма: {row['Сумма']}\n"
        f"🏷️ Классификация: {row['Классификация']}\n"
        f"📄 Конкретика: {row['Конкретика'] or '—'}\n\n"
    )

    # Кнопки редактирования
    kb = [
    [InlineKeyboardButton("🏦 Банк",           callback_data="edit_bank"),
     InlineKeyboardButton("⚙️ Операция",       callback_data="edit_operation")],
    [InlineKeyboardButton("📅 Дата",           callback_data="edit_date"),
     InlineKeyboardButton("💰 Сумма",          callback_data="edit_sum")],
    [InlineKeyboardButton("🏷️ Классификация",  callback_data="edit_classification"),
     InlineKeyboardButton("📄 Конкретика",     callback_data="edit_specific")],
    ]

    # ——— строка «Сохранить» + «Назад»:
    required = ["Банк", "Операция", "Дата", "Сумма", "Классификация"]
    last_row = []
    if all(row.get(f) for f in required):
        last_row.append(InlineKeyboardButton("✅ Сохранить", callback_data="op_save"))
    last_row.append(InlineKeyboardButton("🔙 Назад", callback_data="op_back"))
    kb.append(last_row)

    await update.callback_query.edit_message_text(
        detail + "Выберите поле для редактирования:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return STATE_OP_EDIT_CHOICE

async def handle_edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пользователь выбрал конкретное поле — перенаправляем на ask_*."""
    query = update.callback_query
    await query.answer()

    # 1) Достаём, какое поле правим:
    field = query.data.split("_", 1)[1]  # например "bank", "operation" и т.п.
    context.user_data["edit_field"] = field

    # 2) Текущие данные
    row = context.user_data["editing_op"]["data"]

    # 3) Локально импортируем все нужные ask_* чтобы разорвать циклическую зависимость
    from handlers.operations import (
        ask_operation,
        ask_amount as ask_sum,
        ask_date,)
    from .men_oper import (
        ask_classification_edit,
        ask_specific_edit,)

    # 4) Формируем маппинг «ключ → (ОтображаемоеИмя, Функция-опросник)»
    mapping = {
        "bank":           ("Банк",           ask_bank),
        "operation":      ("Операция",       ask_operation_edit),
        "date":           ("Дата",           ask_date_edit),
        "sum":            ("Сумма",          ask_sum_edit),
        "classification": ("Классификация",  ask_classification_edit),
        "specific":       ("Конкретика",     ask_specific_edit),
    }
    display_name, handler = mapping[field]

    # 5) Вызываем именно тот обработчик
    current = row.get(display_name) or ""
    return await handler(update, context, current)


# ——— Шаг 1: спрашиваем новый Банк ———
async def ask_bank(update: Update, context: ContextTypes.DEFAULT_TYPE, current_value: str) -> int:
    """
    Спрашиваем у пользователя новый Банк, показываем только кнопки из его списка банков.
    """
    # Снимаем «часики»
    if update.callback_query:
        await update.callback_query.answer()
        query = update.callback_query
    else:
        query = update.message

    # Загружаем список банков пользователя (кэшируем)
    banks = context.user_data.get("user_banks")
    if banks is None:
        ws, _ = open_finance_and_plans(context.user_data["sheet_url"])
        rows = ws.get_all_values()[1:]
        banks = sorted({ row[2] for row in rows if row[2] })
        context.user_data["user_banks"] = banks

    # Строим клавиатуру
    kb = [[InlineKeyboardButton(b, callback_data=f"edit_bank_choice_{b}")] for b in banks]

    text = (
        f"Как вы хотите поменять поле *Банк* — текущее значение: "
        f"`{current_value or '—'}`?\n\n"
        "Выберите банк из списка:"
    )
    await query.edit_message_text(text, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(kb))
    # Переходим в состояние ввода (обработаем выбор кнопкой)
    return STATE_OP_EDIT_INPUT


async def handle_bank_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатываем выбор банка из списка. 
    Сохраняем и возвращаемся к карточке операции.
    """
    await update.callback_query.answer()
    # Получаем выбранный банк из callback_data
    _, _, _, selected = update.callback_query.data.split("_", 3)

    # Проверяем, что выбор допустим
    banks = context.user_data.get("user_banks", [])
    if selected not in banks:
        await update.callback_query.edit_message_text("⚠️ Пожалуйста, выберите банк *только* из списка!", parse_mode="Markdown")
        return STATE_OP_EDIT_INPUT

    # Сохраняем новый банк в текущей операции
    context.user_data["editing_op"]["data"]["Банк"] = selected

    # Возвращаемся к просмотру деталей операции (с уже обновлённым банком)
    return await handle_op_edit_choice(update, context)

# ——— Шаг 2: спрашиваем новое значение для поля «Операция» — аналогично ask_bank ———
async def ask_operation_edit(update: Update, context: ContextTypes.DEFAULT_TYPE, current_value: str) -> int:
    """
    Спрашиваем у пользователя тип операции.
    """
    # Убираем «часики»
    if update.callback_query:
        await update.callback_query.answer()
        query = update.callback_query
    else:
        query = update.message

    # Текст с текущим значением
    text = (
        f"⚙️ *Выберите тип операции* — текущее значение: "
        f"`{current_value or '—'}`\n\n"
        "Нажмите на одну из кнопок:"
    )

    # Клавиатура: две кнопки в одном ряду
    kb = [[
        InlineKeyboardButton("🔼 Пополнение", callback_data="edit_operation_choice_Пополнение"),
        InlineKeyboardButton("🔽 Трата",       callback_data="edit_operation_choice_Трата"),
    ]]

    # Рисуем сообщение с клавиатурой
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )

    return STATE_OP_EDIT_INPUT


async def handle_operation_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатываем выбор типа операции из списка.
    Сохраняем в editing_op и возвращаемся в меню редактирования.
    """
    await update.callback_query.answer()
    # извлекаем выбранное значение после последнего _
    selected = update.callback_query.data.rsplit("_", 1)[-1]

    # обновляем поле «Операция» в текущей операции
    context.user_data["editing_op"]["data"]["Операция"] = selected

    # возвращаемся в меню редактирования (STATE_OP_EDIT_CHOICE)
    return await handle_op_edit_choice(update, context)

# ——— Шаг 3: спрашиваем новую Дату — аналогично ask_bank и ask_operation_edit ———
async def ask_date_edit(update: Update, context: ContextTypes.DEFAULT_TYPE, current_value: str) -> int:
    """
    Спрашиваем у пользователя новую Дату — показываем мини-календарь.
    """
    # убираем «часики»
    if update.callback_query:
        await update.callback_query.answer()
        query = update.callback_query
    else:
        query = update.message

    # импортируем локально функцию построения календаря из handlers.operations
    from handlers.operations import create_calendar

    # парсим текущую дату, чтобы показать её в календаре (если есть)
    # если current_value в формате "YYYY-MM-DD", возьмём год/месяц, иначе — сегодня
    try:
        year, month, _ = map(int, current_value.split("-"))
    except:
        from datetime import datetime
        now = datetime.now()
        year, month = now.year, now.month

    # строим клавиатуру-календарь
    cal = create_calendar(year, month)

    # выводим сообщение
    await query.edit_message_text(
        "📅 Выберите новую дату:",
        reply_markup=cal
    )

    # после выбора календарь отдаёт callback_data вида select_date|YYYY-MM-DD
    # мы будем обрабатывать это в STATE_OP_EDIT_INPUT
    return STATE_OP_EDIT_INPUT

async def handle_date_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатываем callback_data 'select_date|YYYY-MM-DD' из календаря.
    Сохраняем дату и возвращаемся в меню редактирования.
    """
    q = update.callback_query
    await q.answer()

    # получаем дата-строку
    _, ds = q.data.split("|", 1)

    # сохраняем в editing_op
    context.user_data["editing_op"]["data"]["Дата"] = ds

    # возвращаемся в меню редактирования деталей (STATE_OP_EDIT_CHOICE)
    return await handle_op_edit_choice(update, context)

# ——— Шаг 4: спрашиваем новую Сумму ———
async def ask_sum_edit(update: Update, context: ContextTypes.DEFAULT_TYPE, current_value: str) -> int:
    """
    Спрашиваем у пользователя новую Сумму.
    """
    # Убираем «часики»
    if update.callback_query:
        await update.callback_query.answer()
        query = update.callback_query
    else:
        query = update.message

    # 🚀 Запоминаем сообщение, чтобы потом его отредактировать
    context.user_data["last_edit_message"] = query.message

    text = (
        f"➖ Введите новую *Сумму* — текущее значение: `{current_value}`\n\n"
        "Отправьте число, например `1234.56` или `-1234.56`."
    )
    # Убираем на время старую клавиатуру и меняем текст
    await query.edit_message_reply_markup(reply_markup=None)
    await query.edit_message_text(text, parse_mode="Markdown")
    return STATE_OP_EDIT_INPUT

# ——— Шаг 5: спрашиваем новую «Классификацию» ———
async def ask_classification_edit(update: Update, context: ContextTypes.DEFAULT_TYPE, current_value: str) -> int:
    """
    Спрашиваем у пользователя новую Классификацию.
    """
    if update.callback_query:
        await update.callback_query.answer()
        query = update.callback_query
    else:
        query = update.message
    # 🚀 Запомним сообщение, чтобы потом его перерисовать
    context.user_data["last_edit_message"] = query.message

    text = (
        f"➖ Введите новую *Классификацию* — текущее значение: `{current_value or '—'}`\n\n"
        "Отправьте текстовое значение."
    )
    await query.edit_message_reply_markup(reply_markup=None)
    await query.edit_message_text(text, parse_mode="Markdown")
    return STATE_OP_EDIT_INPUT

# ——— Шаг 6: спрашиваем новую «Конкретику» ———
async def ask_specific_edit(update: Update, context: ContextTypes.DEFAULT_TYPE, current_value: str) -> int:
    """
    Спрашиваем у пользователя новую Конкретику.
    """
    if update.callback_query:
        await update.callback_query.answer()
        query = update.callback_query
    else:
        query = update.message
    # 🚀 Запомним сообщение, чтобы потом его перерисовать
    context.user_data["last_edit_message"] = query.message

    text = (
        f"➖ Введите новую *Конкретику* — текущее значение: `{current_value or '—'}`\n\n"
        "Отправьте текстовое значение."
    )
    await query.edit_message_reply_markup(reply_markup=None)
    await query.edit_message_text(text, parse_mode="Markdown")
    return STATE_OP_EDIT_INPUT


async def handle_edit_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Сохраняем ввод пользователя для любого поля, включая Сумму.
    После изменения Суммы показываем все кнопки редактирования.
    """
    text = update.message.text.strip()
    field = context.user_data["edit_field"]
    # Соответствие состояния → имя столбца
    rev_map = {
        "bank":           "Банк",
        "operation":      "Операция",
        "date":           "Дата",
        "sum":            "Сумма",
        "classification": "Классификация",
        "specific":       "Конкретика"
    }
    col = rev_map[field]
    row = context.user_data["editing_op"]["data"]

    # ====== СУММА ======
    if field == "sum":
        # валидация числа
        try:
            val = float(text.replace(",", "."))
        except ValueError:
            await update.message.reply_text(
                "⚠️ Пожалуйста, введите корректное число для суммы, "
                "например `1234.56` или `-1234.56`."
            )
            return STATE_OP_EDIT_INPUT
        
        # 2) Достаем тип операции
        op_type = row.get("Операция", "")
        # 3) Специальная валидация по типу
        if op_type == "Пополнение" and val <= 0:
            await update.message.reply_text(
                "⚠️ Для *Пополнения* сумма должна быть положительной."
                "\n\nВведите число вида `1234.56`."
                , parse_mode="Markdown"
            )
            return STATE_OP_EDIT_INPUT
        if op_type == "Трата" and val >= 0:
            await update.message.reply_text(
                "⚠️ Для *Траты* сумма должна быть отрицательной."
                "\n\nВведите число вида `-1234.56`."
                , parse_mode="Markdown"
            )
            return STATE_OP_EDIT_INPUT

        # сохраняем новое значение
        row[col] = val

        # формируем текст карточки
        detail = (
            f"📋 *Операция #{context.user_data['editing_op']['index']}:*\n"
            f"🏦 Банк: {row['Банк']}\n"
            f"⚙️ Операция: {row['Операция']}\n"
            f"📅 Дата: {row['Дата']}\n"
            f"💰 Сумма: {row['Сумма']}\n"
            f"🏷️ Классификация: {row['Классификация']}\n"
            f"📄 Конкретика: {row.get('Конкретика') or '—'}\n\n"
        )

        # собираем те же кнопки, что и в STATE_OP_EDIT_CHOICE
        kb = [
            [InlineKeyboardButton("🏦 Банк",           callback_data="edit_bank"),
             InlineKeyboardButton("⚙️ Операция",       callback_data="edit_operation")],
            [InlineKeyboardButton("📅 Дата",           callback_data="edit_date"),
             InlineKeyboardButton("💰 Сумма",          callback_data="edit_sum")],
            [InlineKeyboardButton("🏷️ Классификация",  callback_data="edit_classification"),
             InlineKeyboardButton("📄 Конкретика",     callback_data="edit_specific")],
        ]
        # строка «Сохранить» + «Назад»
        required = ["Банк", "Операция", "Дата", "Сумма", "Классификация"]
        last_row = []
        if all(row.get(f) for f in required):
            last_row.append(InlineKeyboardButton("✅ Сохранить", callback_data="op_save"))
        last_row.append(InlineKeyboardButton("🔙 Назад", callback_data="op_back"))
        kb.append(last_row)

        # отправляем под вводом пользователя
        await update.message.reply_text(
            detail + "Выберите поле для редактирования:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return STATE_OP_EDIT_CHOICE

    # ——— Обработка «Классификации» и «Конкретики» ———
    if field in ("classification", "specific"):
        # Сохраняем новый текст
        row[col] = text

        # Собираем карточку и клавиатуру
        detail = (
            f"📋 *Операция #{context.user_data['editing_op']['index']}:*\n"
            f"🏦 Банк: {row['Банк']}\n"
            f"⚙️ Операция: {row['Операция']}\n"
            f"📅 Дата: {row['Дата']}\n"
            f"💰 Сумма: {row['Сумма']}\n"
            f"🏷️ Классификация: {row['Классификация']}\n"
            f"📄 Конкретика: {row.get('Конкретика') or '—'}\n\n"
        )
        kb = [
            [InlineKeyboardButton("🏦 Банк",           callback_data="edit_bank"),
             InlineKeyboardButton("⚙️ Операция",       callback_data="edit_operation")],
            [InlineKeyboardButton("📅 Дата",           callback_data="edit_date"),
             InlineKeyboardButton("💰 Сумма",          callback_data="edit_sum")],
            [InlineKeyboardButton("🏷️ Классификация",  callback_data="edit_classification"),
             InlineKeyboardButton("📄 Конкретика",     callback_data="edit_specific")],
        ]
        # Сохраняем/Назад
        required = ["Банк", "Операция", "Дата", "Сумма", "Классификация"]
        last_row = []
        if all(row.get(f) for f in required):
            last_row.append(InlineKeyboardButton("✅ Сохранить", callback_data="op_save"))
        last_row.append(InlineKeyboardButton("🔙 Назад", callback_data="op_back"))
        kb.append(last_row)

        await update.message.reply_text(
            detail + "Выберите поле для редактирования:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return STATE_OP_EDIT_CHOICE

    # ——— Остальные поля (банк, операция, дата) — просто обновляем и показываем меню редактирования ———
    row[col] = text
    return await handle_op_edit_choice(update, context)

    # ——— Остальные поля (банк, операция, дата) — просто обновляем и показываем меню редактирования ———
    row[col] = text
    return await handle_op_edit_choice(update, context)



async def handle_op_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    «🔙 Назад» — если мы в меню редактирования поля, то возвращаемся к карточке
    текущей операции, иначе — к списку операций.
    """
    q = update.callback_query
    await q.answer()  # убираем часики

    edit = context.user_data.get("editing_op")
    if edit:
        idx = edit["index"]
        row = edit["data"]
        # Собираем текст карточки точно как в handle_op_select
        text = (
            f"📋 *Операция #{idx}:*\n"
            f"🏦 Банк: {row['Банк']}\n"
            f"⚙️ Операция: {row['Операция']}\n"
            f"📅 Дата: {row['Дата']}\n"
            f"💰 Сумма: {row['Сумма']}\n"
            f"🏷️ Классификация: {row['Классификация']}\n"
            f"📄 Конкретика: {row['Конкретика'] or '—'}"
        )
        # Кнопки те же, что и при первом показе карточки
        buttons = [
            InlineKeyboardButton("✏️ Изменить", callback_data="op_edit"),
            InlineKeyboardButton("🗑 Удалить",  callback_data="op_delete"),
            InlineKeyboardButton("🔙 Назад",    callback_data="op_back"),
        ]
        await q.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([buttons])
        )
        return STATE_OP_CONFIRM

    # если editing_op нет — возвращаемся к списку операций
    return await start_men_oper(update, context)


async def handle_save_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняем все изменённые поля операции в Google Sheets и возвращаемся к списку."""
    q = update.callback_query
    await q.answer()

    # 1) Берём оригинал и новые данные
    edit = context.user_data.get("editing_op", {})
    orig = edit.get("original")
    new  = edit.get("data")
    url  = context.user_data.get("sheet_url")
    if not orig or not new or not url:
        await q.edit_message_text("⚠️ Нет данных для сохранения.")
        return await start_men_oper(update, context)

    # 2) Открываем лист
    ws, _ = open_finance_and_plans(url)

    # 3) Находим строку по оригинальным полям (Банк, Дата, Сумма)
    all_vals = ws.get_all_values()
    row_number = None
    for i, values in enumerate(all_vals[1:], start=2):
        if (
            values[2] == orig["Банк"] and
            values[4] == orig["Дата"] and
            values[5] == str(orig["Сумма"]) and
            values[6] == orig.get("Классификация", "")
        ):
            row_number = i
            break

    if not row_number:
        await q.edit_message_text("⚠️ Не удалось найти строку для обновления.")
        return await start_men_oper(update, context)

    # 4) Нормализуем дату в ISO (YYYY-MM-DD), даже если её не трогали
    date_val = new.get("Дата")
    # если уже в формате ISO — оставляем
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_val):
        # ожидаем вид "7 июня, пт" или "7 июня"
        day_month = date_val.split(",", 1)[0].strip()  # "7 июня"
        parts = day_month.split()
        try:
            day = int(parts[0])
            gen = parts[1].lower()
            month = GENITIVE_MONTHS.get(gen)
            year = int(new.get("Год"))
            date_val = f"{year}-{month:02d}-{day:02d}"
        except Exception:
            # если не удалось распарсить, оставляем исход
            pass

    # 5) Собираем новый список A–H
    new_row = [
        new.get("Год"),
        new.get("Месяц"),
        new.get("Банк"),
        new.get("Операция"),
        date_val,
        new.get("Сумма"),
        new.get("Классификация"),
        new.get("Конкретика") or "-"
    ]

    # 6) Обновляем эту же строку одним вызовом
    cell_range = f"A{row_number}:H{row_number}"
    ws.update(cell_range, [new_row], value_input_option="USER_ENTERED")

    # 7) Уведомляем и чистим временные данные
    await q.edit_message_text("✅ Операция успешно обновлена.")
    context.user_data.pop("editing_op", None)

    # 8) Возвращаемся к списку последних операций
    return await start_men_oper(update, context)



def register_men_oper_handlers(app):
    conv = ConversationHandler(
        entry_points=[ CallbackQueryHandler(start_men_oper, pattern=r"^menu:men_oper$") ],
        states={
            STATE_OP_LIST: [
                CallbackQueryHandler(start_men_oper, pattern=r"^menu:men_oper$")
            ],
            STATE_OP_SELECT: [
                CallbackQueryHandler(handle_op_select, pattern=r"^op_select_\d+$"),
                CallbackQueryHandler(exit_to_main_menu, pattern=r"^menu:open$")
            ],
            STATE_OP_CONFIRM: [
                CallbackQueryHandler(handle_op_delete,  pattern=r"^op_delete$"),
                CallbackQueryHandler(handle_op_edit_choice, pattern=r"^op_edit$"),
                CallbackQueryHandler(handle_op_back,     pattern=r"^op_back$")
            ],
            STATE_OP_EDIT_CHOICE: [
                CallbackQueryHandler(handle_edit_field,
                                     pattern=r"^edit_(bank|operation|date|sum|classification|specific)$"),
                CallbackQueryHandler(handle_save_edit, pattern=r"^op_save$"),                     
                CallbackQueryHandler(handle_op_back, pattern=r"^op_back$")
            ],
            # этот этап обрабатывают сами ask_* из handlers/operations и они должны вернуть STATE_OP_EDIT_INPUT
            STATE_OP_EDIT_INPUT: [
                # сюда попадут сообщения-последний ввод пользователя
                CallbackQueryHandler(handle_bank_choice, pattern=r"^edit_bank_choice_.+$"),
                CallbackQueryHandler(handle_operation_choice, pattern=r"^edit_operation_choice_.+$"),
                CallbackQueryHandler(handle_date_choice,      pattern=r"^select_date\|[\d\-]+$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_input),
            ],
        },
        fallbacks=[ CallbackQueryHandler(exit_to_main_menu, pattern=r"^menu:open$") ],
        allow_reentry=True,
    )
    app.add_handler(conv)
