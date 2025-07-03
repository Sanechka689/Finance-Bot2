# services/sheets_service.py — подключение и первичная настройка Google Sheets

import os
from gspread import service_account

def open_finance_and_plans(url: str):
    """
    Открывает документ по URL, настраивает листы и возвращает объекты worksheets.
    Делает:
      • удаляет стандартный 'Лист1'
      • создаёт (или очищает) листы 'Финансы' и 'Планы'
      • вставляет заголовки
      • фиксирует шапку
      • устанавливает базовый фильтр
    """
    creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    sa = service_account(filename=creds)
    doc = sa.open_by_url(url)

    # 1. Удаляем дефолтный первый лист
    try:
        default = doc.sheet1
        doc.del_worksheet(default)
    except Exception:
        pass

    # 2. Создаём или очищаем лист 'Финансы'
    try:
        finance_ws = doc.worksheet("Финансы")
        finance_ws.clear()
    except Exception:
        finance_ws = doc.add_worksheet("Финансы", rows="1000", cols="8")

    # 3. Создаём или очищаем лист 'Планы'
    try:
        plans_ws = doc.worksheet("Планы")
        plans_ws.clear()
    except Exception:
        plans_ws = doc.add_worksheet("Планы", rows="1000", cols="9")

    # 4. Вставляем шапки
    finance_headers = ["Год", "Месяц", "Банк", "Операция", "Дата", "Сумма", "Классификация", "Конкретика"]
    plans_headers   = ["Год", "Месяц", "Банк", "Операция", "Дата", "Сумма", "Остаток", "Классификация", "Конкретика"]

    finance_ws.insert_row(finance_headers, 1)
    plans_ws.insert_row(plans_headers,   1)

    # 5. Фиксируем шапку
    finance_ws.freeze(rows=1)
    plans_ws.freeze(rows=1)

    # 6. Устанавливаем базовый фильтр на весь диапазон
    try:
        finance_ws.set_basic_filter()
        plans_ws.set_basic_filter()
    except AttributeError:
        # если версия gspread не поддерживает, пропускаем
        pass

    return finance_ws, plans_ws
