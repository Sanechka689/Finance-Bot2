# handlers/classification.py

import calendar
import re
from datetime import datetime, date
from typing import Optional, Dict

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from services.sheets_service import open_finance_and_plans
from utils.constants import STATE_CLASS_MENU

# Карта родительного падежа месяцев на номер
GENITIVE_MONTHS = {
    "января":   1, "февраля":  2, "марта":    3, "апреля": 4,
    "мая":      5, "июня":     6, "июля":     7, "августа":8,
    "сентября": 9, "октября": 10, "ноября":  11, "декабря":12,
}

# Названия месяцев для заголовков
RUS_MONTHS = [
    None, "январь","февраль","март","апрель","май","июнь",
          "июль","август","сентябрь","октябрь","ноябрь","декабрь"
]


def parse_sheet_date(s: str) -> Optional[date]:
    """
    Пробуем распарсить строку даты из Google Sheets:
      - DD.MM.YYYY
      - YYYY-MM-DD
      - MM/DD/YYYY
      - «DD месяц, ...» (русский родительный падеж, без года → текущий год)
    """
    s = s.strip()
    # DD.MM.YYYY
    if re.match(r"^\d{2}\.\d{2}\.\d{4}$", s):
        d, m, y = map(int, s.split("."))
        return date(y, m, d)

    # YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        y, m, d = map(int, s.split("-"))
        return date(y, m, d)

    # MM/DD/YYYY
    try:
        return datetime.strptime(s, "%m/%d/%Y").date()
    except:
        pass

    # Русский формат «13 июля, вс» или «13 июля»
    m = re.match(r"^(\d{1,2})\s+([А-Яа-я]+)(?:\,.*)?$", s)
    if m:
        day = int(m.group(1))
        month_name = m.group(2).lower()
        month = GENITIVE_MONTHS.get(month_name)
        if month:
            year = date.today().year
            return date(year, month, day)
    # ISO-формат
    try:
        return datetime.fromisoformat(s).date()
    except:
        return None


def aggregate_by_period(
    rows: list,
    start: Optional[date],
    end:   Optional[date]
) -> Dict[str, float]:
    """
    Считает сумму по каждой Классификации (столбец G, индекс 6)
    в диапазоне [start, end] включительно. Если граница None — без фильтра.
    """
    data: Dict[str, float] = {}
    for r in rows:
        dt = parse_sheet_date(r[4])
        if not dt:
            continue
        if start and dt < start:
            continue
        if end   and dt > end:
            continue

        cls = r[6].strip() or "—"
        raw = str(r[5]).replace("\xa0", "").replace(" ", "").replace(",", ".")
        try:
            amt = float(raw)
        except:
            continue

        data[cls] = data.get(cls, 0.0) + amt
    return data


async def start_classification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показываем пользователю агрегированную статистику за текущий месяц."""
    q = update.callback_query
    await q.answer()

    url = context.user_data.get("sheet_url")
    if not url:
        return await q.edit_message_text("⚠️ Сначала подключите таблицу: /setup")

    # Читаем все строки листа «Финансы»
    ws, _ = open_finance_and_plans(url)
    rows = ws.get_all_values()[1:]

    today = date.today()
    # Границы текущего месяца
    first = date(today.year, today.month, 1)
    last_day = calendar.monthrange(today.year, today.month)[1]
    last  = date(today.year, today.month, last_day)

    data = aggregate_by_period(rows, first, last)
    items = sorted(data.items(), key=lambda x: x[1])

    header = f"🏷️ *Классификации за {RUS_MONTHS[today.month]} {today.year}:*"
    if not items:
        body = "— нет данных за этот месяц —"
    else:
        # форматируем с пробелами и запятой
        body = "\n".join(
            f"{i+1}. {cls} — {amt:,.2f}"
            .replace(",", "X").replace(".", ",").replace("X", " ")
            for i, (cls, amt) in enumerate(items)
        )

    text = f"{header}\n{body}"

    kb = [
        [
            InlineKeyboardButton("За предыдущий месяц", callback_data="class_prev"),
            InlineKeyboardButton("За год"               , callback_data="class_year"),
        ],
        [
            InlineKeyboardButton("За всё время"         , callback_data="class_all"),
            InlineKeyboardButton("🔙 Назад"             , callback_data="class_back"),
        ],
    ]
    await q.edit_message_text(text, parse_mode="Markdown",
                              reply_markup=InlineKeyboardMarkup(kb))
    return STATE_CLASS_MENU


async def handle_class_period(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает class_prev / class_year / class_all и перерисовывает."""
    q = update.callback_query
    await q.answer()

    period = q.data  # class_prev / class_year / class_all
    url = context.user_data.get("sheet_url")
    ws, _ = open_finance_and_plans(url)
    rows = ws.get_all_values()[1:]

    today = date.today()
    if period == "class_prev":
        # предыдущий месяц
        pm = today.month - 1 or 12
        py = today.year if today.month > 1 else today.year - 1
        first = date(py, pm, 1)
        last_day = calendar.monthrange(py, pm)[1]
        last  = date(py, pm, last_day)
        period_name = f"предыдущий месяц ({RUS_MONTHS[pm]} {py})"

    elif period == "class_year":
        first = date(today.year, 1, 1)
        last  = today
        period_name = f"текущий год ({today.year})"

    else:  # class_all
        first = None
        last  = None
        period_name = "всё время"

    data = aggregate_by_period(rows, first, last)
    items = sorted(data.items(), key=lambda x: x[1])

    header = f"🏷️ *Классификации за {period_name}:*"
    if not items:
        body = "— нет данных —"
    else:
        body = "\n".join(
            f"{i+1}. {cls} — {amt:,.2f}"
            .replace(",", "X").replace(".", ",").replace("X", " ")
            for i, (cls, amt) in enumerate(items)
        )

    text = f"{header}\n{body}"

    kb = [
        [
            InlineKeyboardButton("За предыдущий месяц", callback_data="class_prev"),
            InlineKeyboardButton("За год"               , callback_data="class_year"),
        ],
        [
            InlineKeyboardButton("За всё время"         , callback_data="class_all"),
            InlineKeyboardButton("🔙 Назад"             , callback_data="class_back"),
        ],
    ]
    await q.edit_message_text(text, parse_mode="Markdown",
                              reply_markup=InlineKeyboardMarkup(kb))
    return STATE_CLASS_MENU


async def handle_class_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Кнопка «Назад» возвращает в главное меню."""
    q = update.callback_query
    await q.answer()
    from handlers.menu import show_main_menu
    return await show_main_menu(update, context)
