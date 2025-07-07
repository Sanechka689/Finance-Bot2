# handlers/men_oper.py

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import (
    CallbackQueryHandler, ConversationHandler,
    ContextTypes
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
    context.user_data["editing_op"] = {"index": idx, "data": row}

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

    # уведомление в виде небольшого toast’а
    await query.answer("🗑 Операция удалена.", show_alert=False)
    # сразу перерисовываем обновлённый список последних 10 операций
    return await start_men_oper(update, context)



async def handle_op_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """«Назад» — просто переходим на список последних операций."""
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
                CallbackQueryHandler(lambda u,c: STATE_OP_EDIT_CHOICE, pattern=r"^op_edit$"),
                CallbackQueryHandler(handle_op_back,     pattern=r"^op_back$")
            ],
        },
        fallbacks=[ CallbackQueryHandler(exit_to_main_menu, pattern=r"^menu:open$") ],
        allow_reentry=True
    )
    app.add_handler(conv)
