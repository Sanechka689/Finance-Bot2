# services/sheets_service.py — подключение и первичная настройка Google Sheets

import os
from gspread import service_account

def open_finance_and_plans(url: str):
    """
    Открывает документ по URL, настраивает листы и возвращает объекты worksheets.
    Не затирает существующие данные, вставляет шапки при создании,
    фиксирует шапку и ставит фильтр на весь лист.
    """
    creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    sa = service_account(filename=creds)
    doc = sa.open_by_url(url)

    # 1. Удаляем только лист по умолчанию «Лист1» или «Sheet1»
    for default_title in ("Лист1", "Sheet1"):
        try:
            default_ws = doc.worksheet(default_title)
            doc.del_worksheet(default_ws)
        except Exception:
            pass

    # Заголовки для листов
    finance_headers = ["Год", "Месяц", "Банк", "Операция", "Дата", "Сумма", "Классификация", "Конкретика"]
    plans_headers   = ["Год", "Месяц", "Банк", "Операция", "Дата", "Сумма", "Остаток", "Классификация", "Конкретика"]

    # 2. Получаем или создаём лист 'Финансы' (не очищаем существующие данные)
    try:
        finance_ws = doc.worksheet("Финансы")
    except Exception:
        finance_ws = doc.add_worksheet("Финансы", rows="1000", cols="8")
        finance_ws.insert_row(finance_headers, 1)

    # 3. Получаем или создаём лист 'Планы' (не очищаем существующие данные)
    try:
        plans_ws = doc.worksheet("Планы")
    except Exception:
        plans_ws = doc.add_worksheet("Планы", rows="1000", cols="9")
        plans_ws.insert_row(plans_headers, 1)

    # 4. Фиксируем шапку и ставим фильтр
    finance_ws.freeze(rows=1)
    plans_ws.freeze(rows=1)
    try:
        finance_ws.set_basic_filter()
    except Exception:
        pass
    try:
        plans_ws.set_basic_filter()
    except Exception:
        pass

    return finance_ws, plans_ws
