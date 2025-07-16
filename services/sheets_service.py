# services/sheets_service.py — подключение и первичная настройка Google Sheets

import os
from gspread import service_account

import gspread
from oauth2client.service_account import ServiceAccountCredentials

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

    # —————— Автодополнение строк и расширение фильтра ——————
    _ensure_capacity_and_filter(finance_ws, min_remaining=20, add_rows=500, max_col='H')
    _ensure_capacity_and_filter(plans_ws,   min_remaining=20, add_rows=500, max_col='I')
    
    # —————— Новая часть: выравнивание колонок ——————
    # Финансы
    max_row = finance_ws.row_count  # общее число строк
    # A–D и G–H: слева по горизонтали, по центру по вертикали
    finance_ws.format(f"A1:D{max_row}", {
        "horizontalAlignment": "LEFT",
        "verticalAlignment":   "MIDDLE",
    })
    finance_ws.format(f"G1:H{max_row}", {
        "horizontalAlignment": "LEFT",
        "verticalAlignment":   "MIDDLE",
    })
    # E–F: по центру горизонтально и вертикально
    finance_ws.format(f"E1:F{max_row}", {
        "horizontalAlignment": "CENTER",
        "verticalAlignment":   "MIDDLE",
    })
    # — форматирование даты в колонке E:
    finance_ws.format(f"E2:E{max_row}", {
        "numberFormat": {
            "type":    "DATE",
            "pattern": "d mmmm, ddd"
        }
    })

    # Планы
    max_row = plans_ws.row_count  # общее число строк
    # A–D и G–H: слева по горизонтали, по центру по вертикали
    plans_ws.format(f"A1:D{max_row}", {
        "horizontalAlignment": "LEFT",
        "verticalAlignment":   "MIDDLE",
    })
    plans_ws.format(f"G1:H{max_row}", {
        "horizontalAlignment": "LEFT",
        "verticalAlignment":   "MIDDLE",
    })
    # E–G: по центру горизонтально и вертикально
    plans_ws.format(f"E1:G{max_row}", {
        "horizontalAlignment": "CENTER",
        "verticalAlignment":   "MIDDLE",
    })
    # — форматирование даты в колонке E:
    plans_ws.format(f"E2:E{max_row}", {
        "numberFormat": {
            "type":    "DATE",
            "pattern": "d mmmm, ddd"
        }
    })
    # ─── форматируем колонки F(5) и G(6) как числа с двумя десятичными ───
    for ws in (finance_ws, plans_ws):
        sheet_id = ws._properties["sheetId"]
        requests = [{
            "repeatCell": {
                "range": {
                    "sheetId":           sheet_id,
                    "startRowIndex":     1,    # пропускаем заголовок
                    "startColumnIndex":  5,    # колонка F (0‑based индекс)
                    "endColumnIndex":    7     # до G включительно
                },
                "cell": {
                    "userEnteredFormat": {
                        "numberFormat": {
                            "type":    "NUMBER",
                            "pattern": "#,##0.00"
                        }
                    }
                },
                "fields": "userEnteredFormat.numberFormat"
            }
        }]
        ws.spreadsheet.batch_update({"requests": requests})

    # ─── сортировка по дате (E) по убыванию ───
    for ws in (finance_ws, plans_ws):
        sheet_id = ws._properties["sheetId"]
        sort_request = {
            "requests": [{
                "sortRange": {
                    "range": {
                        "sheetId":           sheet_id,
                        "startRowIndex":     1,            # пропускаем заголовок
                        "startColumnIndex":  0,            # от колонки A
                        "endColumnIndex":    ws.col_count, # до последней колонки
                        "endRowIndex":       ws.row_count  # до последней строки
                    },
                    "sortSpecs": [{
                        "dimensionIndex": 4,           # колонка E (0‑based)
                        "sortOrder":      "DESCENDING" # от новых к старым
                    }]
                }
            }]
        }
        ws.spreadsheet.batch_update(sort_request)

    # Возвращаем обработанные листы
    return finance_ws, plans_ws


def _ensure_capacity_and_filter(ws, min_remaining: int = 20, add_rows: int = 500, max_col: str = 'H'):
    """
    У листа ws:
     - если (ws.row_count - фактическое_количество_строк) < min_remaining
       — добавить add_rows пустых строк;
     - затем установить BasicFilter на диапазон от A1 до <max_col><новое_количество_строк>.
    """
    # текущее количество строк в листе
    total_rows = ws.row_count
    # сколько уже занято (по первой колонке, пропуская заголовок)
    used_rows  = len(ws.col_values(1))

    if total_rows - used_rows < min_remaining:
        # ДОБАВЛЯЕМ пустые строки
        ws.add_rows(add_rows)
        total_rows += add_rows

    # ПЕРЕПРИМЕНИТЬ фильтр на весь диапазон
    filter_range = f"A1:{max_col}{total_rows}"
    try:
        ws.set_basic_filter(filter_range)
    except Exception:
        pass
