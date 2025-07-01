# gsheet_client.py

# ==============================
# Stage 4: Google Sheets Client
# ==============================

# Stage 4.1: импорты для работы с gspread и OAuth2
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Stage 4.2: инициализация клиента по path и URL таблицы
def init_sheets(creds_path: str, sheet_url: str):
    """
    creds_path — путь к credentials.json
    sheet_url  — ссылка Google Sheets из браузера
    возвращает: (fin_ws, plan_ws)
    """
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_url(sheet_url)
    # Stage 4.2.1: листы «Финансы» и «Планы»
    fin_ws  = spreadsheet.worksheet("Финансы")
    plan_ws = spreadsheet.worksheet("Планы")
    return fin_ws, plan_ws

# Stage 4.3: добавить строку в лист «Финансы»
def append_finance_row(ws, row: list):
    """
    ws  — Worksheet объекта gspread
    row — список [Год, Месяц, Банк, Операция, Дата, Сумма, Классификация, Конкретика]
    """
    ws.append_row(row, value_input_option="USER_ENTERED")
