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

import logging
logger = logging.getLogger(__name__)


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
            f"{i}. {row['Банк']}  {row['Сумма']}  {row['Классификация']}, {row['Дата']}"
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
        f"*Операция #{idx}:*\n"
        f"Банк: {row['Банк']}\n"
        f"Операция: {row['Операция']}\n"
        f"Дата: {row['Дата']}\n"
        f"Сумма: {row['Сумма']}\n"
        f"Классификация: {row['Классификация']}\n"
        f"Конкретика: {row['Конкретика'] or '—'}"
    )

    # Кнопки
    buttons = []
    # «Подтвердить» — только если нет «Конкретики»
    required = ["Банк","Операция","Дата","Сумма","Классификация"]
    if all(row.get(f) for f in required):
        buttons.append(InlineKeyboardButton("✅ Подтвердить", callback_data="op_confirm"))
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
    """Удаляем старую строку и создаём новую (подтверждение)."""
    query = update.callback_query
    await query.answer("Подтверждаю…", show_alert=False)

    url = context.user_data["sheet_url"]
    ws, _ = open_finance_and_plans(url)
    edit = context.user_data["editing_op"]
    row = edit["data"]

    # 1) находим номер строки в листе (по уникальному сочетанию)
    all_values = ws.get_all_values()
    # первой строкой — шапка, потом data:
    row_number = None
    for i, values in enumerate(all_values[1:], start=2):
        if (values[2], values[4], values[5]) == (row["Банк"], row["Дата"], str(row["Сумма"])):
            row_number = i
            break
    if row_number:
        ws.delete_rows(row_number)
    # 2) дописываем её же
    new_row = [
        row["Год"], row["Месяц"], row["Банк"], row["Операция"],
        row["Дата"], row["Сумма"], row["Классификация"], row.get("Конкретика") or "-"
    ]
    ws.append_row(new_row, value_input_option="USER_ENTERED")

    await query.edit_message_text("✅ Операция подтверждена.")
    # Возвращаем в главное меню
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
        f"*Операция #{idx}:*\n"
        f"Банк: {row['Банк']}\n"
        f"Операция: {row['Операция']}\n"
        f"Дата: {row['Дата']}\n"
        f"Сумма: {row['Сумма']}\n"
        f"Классификация: {row['Классификация']}\n"
        f"Конкретика: {row['Конкретика'] or '—'}\n\n"
    )

    # Кнопки редактирования
    kb = [
        [InlineKeyboardButton("Банк",           callback_data="edit_bank"),
         InlineKeyboardButton("Операция",       callback_data="edit_operation")],
        [InlineKeyboardButton("Дата",           callback_data="edit_date"),
         InlineKeyboardButton("Сумма",          callback_data="edit_sum")],
        [InlineKeyboardButton("Классификация",  callback_data="edit_classification"),
         InlineKeyboardButton("Конкретика",     callback_data="edit_specific")],
        [InlineKeyboardButton("✅ Сохранить",  callback_data="op_save"),
        InlineKeyboardButton("🔙 Назад",        callback_data="op_back")],
    ]

    await update.callback_query.edit_message_text(
        detail + "Выберите поле для редактирования:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return STATE_OP_EDIT_CHOICE

async def handle_edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пользователь выбрал конкретное поле — перенаправляем на ask_*."""
    logger.debug("🔧 handle_edit_field called (data=%s)", update.callback_query.data)
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
        input_classification as ask_classification,
        input_specific as ask_specific,
        ask_date,)

    from .men_oper import ask_sum_edit

    # 4) Формируем маппинг «ключ → (ОтображаемоеИмя, Функция-опросник)»
    mapping = {
        "bank":           ("Банк",           ask_bank),
        "operation":      ("Операция",       ask_operation_edit),
        "date":           ("Дата",            ask_date_edit),
        "sum":            ("Сумма",           ask_sum_edit),
        "classification": ("Классификация",  ask_classification),
        "specific":       ("Конкретика",      ask_specific),
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

    logger.debug("🔧 ask_bank called, current_value=%s", current_value) #Логи

    # Загружаем список банков пользователя (кэшируем)
    banks = context.user_data.get("user_banks")
    if banks is None:
        ws, _ = open_finance_and_plans(context.user_data["sheet_url"])
        rows = ws.get_all_values()[1:]
        banks = sorted({ row[2] for row in rows if row[2] })
        context.user_data["user_banks"] = banks
        
    logger.debug("🔧 available banks for user: %s", banks) #Логи

    # Строим клавиатуру
    kb = [[InlineKeyboardButton(b, callback_data=f"edit_bank_choice_{b}")] for b in banks]
    kb.append([InlineKeyboardButton("❌ Отмена", callback_data="op_back")])

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
    Спрашиваем у пользователя тип операции, показываем кнопки Пополнение/Трата/Перевод.
    """
    # убираем «часики»
    if update.callback_query:
        await update.callback_query.answer()
        query = update.callback_query
    else:
        query = update.message

    # строим клавиатуру со списком типов операций
    kb = [
        [InlineKeyboardButton("Пополнение", callback_data="edit_operation_choice_Пополнение"),
         InlineKeyboardButton("Трата",       callback_data="edit_operation_choice_Трата")],
        [InlineKeyboardButton("❌ Отмена",    callback_data="op_back")],  # вернуться назад
    ]

    # показываем текущий выбор
    text = (
        f"Как вы хотите поменять поле *Операция* — текущее значение: "
        f"`{current_value or '—'}`?\n\n"
        "Выберите тип операции:"
    )
    await query.edit_message_text(text, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(kb))

    # переходим в состояние ввода/выбора (STATE_OP_EDIT_INPUT)
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

    # 🚀 ЗАПОМИНАЕМ этот message, чтобы потом его отредактировать:
    context.user_data["last_edit_message"] = query.message

    # Текст с подсказкой
    text = (
        f"➖ Введите новую *Сумму* — текущее значение: `{current_value}`\n\n"
        "Отправьте число, например `1234.56` или `-1234.56`."
    )
    await query.edit_message_reply_markup(reply_markup=None)
    await query.edit_message_text(text, parse_mode="Markdown")
    # Перехватываем следующий ввод в STATE_OP_EDIT_INPUT
    return STATE_OP_EDIT_INPUT


async def handle_edit_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Сохраняем ввод пользователя для любого поля, включая Сумму.
    """
    text = update.message.text.strip()
    field = context.user_data["edit_field"]
    rev_map = {
        "bank":           "Банк",
        "operation":      "Операция",
        "date":           "Дата",
        "sum":            "Сумма",
        "classification": "Классификация",
        "specific":       "Конкретика"
    }
    col = rev_map[field]

    if field == "sum":
        # жёсткая проверка ― только число
        try:
            val = float(text.replace(",", "."))
        except ValueError:
            await update.message.reply_text(
                "⚠️ Пожалуйста, введите корректное число для суммы, например `1234.56` или `-1234.56`."
            )
            return STATE_OP_EDIT_INPUT

        # Сохраняем новое значение
        context.user_data["editing_op"]["data"][col] = val

        # 🖋️ Ручками «перерисовываем» то же самое сообщение, в котором спрашивали сумму
        msg = context.user_data.get("last_edit_message")
        row = context.user_data["editing_op"]["data"]

        # Собираем текст детализации операции
        detail = (
            f"*Операция #{context.user_data['editing_op']['index']}:*\n"
            f"Банк: {row['Банк']}\n"
            f"Операция: {row['Операция']}\n"
            f"Дата: {row['Дата']}\n"
            f"Сумма: {row['Сумма']}\n"
            f"Классификация: {row['Классификация']}\n"
            f"Конкретика: {row['Конкретика'] or '—'}"
        )

        # Кнопки: аналогично STATE_OP_CONFIRM + кнопки «Сохранить» и «Назад»
        buttons = []
        # только если все поля заполнены, можно «Подтвердить»
        required = ["Банк","Операция","Дата","Сумма","Классификация"]
        if all(row.get(f) for f in required):
            buttons.append(InlineKeyboardButton("✅ Подтвердить", callback_data="op_confirm"))
        buttons += [
            InlineKeyboardButton("✏️ Изменить", callback_data="op_edit"),
            InlineKeyboardButton("🗑 Удалить", callback_data="op_delete"),
            InlineKeyboardButton("🔙 Назад",   callback_data="op_back"),
        ]

        # заменяем текст и клавиатуру в исходном сообщении
        await msg.edit_text(
            detail,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([buttons])
        )
        return STATE_OP_CONFIRM

    # для всех остальных полей — просто сохраняем и возвращаемся к карточке:
    context.user_data["editing_op"]["data"][col] = text
    return await handle_op_select(update, context)


async def handle_op_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """«Назад» — просто переходим на список последних операций."""
    return await start_men_oper(update, context)

async def handle_save_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняем все изменённые поля операции в Google Sheets и возвращаемся к списку."""
    q = update.callback_query
    await q.answer()

    # 1) Достаём оригинальные и новые данные
    edit = context.user_data.get("editing_op", {})
    orig = edit.get("original")
    new  = edit.get("data")
    url  = context.user_data.get("sheet_url")
    if not orig or not new or not url:
        await q.edit_message_text("⚠️ Нет данных для сохранения.")
        return await start_men_oper(update, context)

    # 2) Открываем лист
    ws, _ = open_finance_and_plans(url)

    # 3) Ищем номер строки по оригинальным данным (банк, дата, сумма)
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
        await q.edit_message_text("⚠️ Не удалось найти строку для обновления.")
        return await start_men_oper(update, context)

    # 4) Составляем новый список из 8 значений в порядке столбцов A–H
    sum_val = new.get("Сумма")
    if isinstance(sum_val, str):
        sum_val = float(sum_val.replace(",", "."))
    new_row = [
        new.get("Год"),
        new.get("Месяц"),
        new.get("Банк"),
        new.get("Операция"),
        new.get("Дата"),
        sum_val,
        new.get("Классификация"),
        new.get("Конкретика") or "-"
    ]

    # 5) Перезаписываем диапазон A{row_number}:H{row_number}
    cell_range = f"A{row_number}:H{row_number}"
    ws.update(cell_range, [new_row], value_input_option="USER_ENTERED")

    # 6) Уведомляем пользователя и очищаем временные данные
    await q.edit_message_text("✅ Операция успешно обновлена.")
    context.user_data.pop("editing_op", None)

    # 7) Возвращаемся к списку последних операций
    return await start_men_oper(update, context)


# (далее можно добавить handle_op_edit_* точно по той же схеме, что и в /add)

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
                CallbackQueryHandler(handle_op_confirm, pattern=r"^op_confirm$"),
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
                # сначала – выбор банка, операции, даты…
                CallbackQueryHandler(handle_bank_choice,      pattern=r"^edit_bank_choice_.+$"),
                CallbackQueryHandler(handle_operation_choice, pattern=r"^edit_operation_choice_.+$"),
                CallbackQueryHandler(handle_date_choice,      pattern=r"^select_date\|[\d\-]+$"),
                
                # 1) Ловим **только число** (с точкой или запятой) — валидируем ввод суммы:
                MessageHandler(
                    filters.Regex(r"^-?\d+(?:[.,]\d+)?$"),
                    handle_edit_input
                ),
                # 2) Всё остальное — спрашиваем повторно:
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    ask_sum_invalid  # ваш небольшой handler, см. ниже
                ),
            ],
        },
        fallbacks=[ CallbackQueryHandler(exit_to_main_menu, pattern=r"^menu:open$") ],
        allow_reentry=True,
    )
    app.add_handler(conv)

    # вспомогательный handler, когда пользователь ввёл что-то нечисловое
async def ask_sum_invalid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "⚠️ Пожалуйста, введите корректное число для суммы, "
        "например `1234.56` или `-1234.56`."
    )
    return STATE_OP_EDIT_INPUT