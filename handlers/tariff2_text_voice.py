# handlers/tariff2_text_voice.py
# ======================================================
# Этап 4: Тариф 2 (текст + голос) → ИИ → JSON → карточка → запись в Google Sheets
# ======================================================

import os
import io
import json
import re
from datetime import datetime
from typing import Optional, Dict, Any, List
from utils.caps import has_cap


from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler, filters

# Аудио
from pydub import AudioSegment
import speech_recognition as sr

# ИИ (OpenAI SDK 1.x)
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from services.sheets_service import open_finance_and_plans

# -----------------------------
# 0) УТИЛИТЫ: формат, эмодзи, валидация
# -----------------------------

EMOJI = {
    "Дата": "📅",
    "Банк": "🏦",
    "Операция": "⚙️",
    "Сумма": "💸",
    "Классификация": "🏷️",
    "Конкретика": "🔍",
}

RU_MONTHS = [
    "Январь","Февраль","Март","Апрель","Май","Июнь",
    "Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"
]

VALID_OPERATIONS = {"Трата","Пополнение","Перевод","План"}



def _ensure_date_iso(s: str) -> str:
    """
    Принимаем дату в формате ISO или DD.MM.YYYY → приводим к ISO YYYY-MM-DD.
    """
    s = s.strip()
    # ISO?
    try:
        return datetime.fromisoformat(s).date().isoformat()
    except Exception:
        pass
    # DD.MM.YYYY
    m = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$", s)
    if m:
        d, mo, y = map(int, m.groups())
        return datetime(year=y, month=mo, day=d).date().isoformat()
    # Если пусто → сегодня
    return datetime.now().date().isoformat()

def _normalize_op(op: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Приводим одну операцию к правильному виду.
    Если это "Перевод" и пришла единичная запись — НИЖЕ конвертируем в две.
    Если это обычная операция — возвращаем [op].
    """
    # Поля и дефолты:
    op = {k: op.get(k) for k in ["Год","Месяц","Банк","Операция","Дата","Сумма","Классификация","Конкретика"]}

    # Дата → ISO
    op["Дата"] = _ensure_date_iso(op.get("Дата") or datetime.now().date().isoformat())
    dt = datetime.fromisoformat(op["Дата"])
    op["Год"] = op.get("Год") or dt.year
    op["Месяц"] = op.get("Месяц") or RU_MONTHS[dt.month-1]

    # Операция
    if op.get("Операция") not in VALID_OPERATIONS:
        op["Операция"] = "Трата"

    # Сумма
    try:
        amount = float(str(op.get("Сумма","0")).replace(",", "."))
    except Exception:
        amount = 0.0

    if op["Операция"] == "Трата":
        amount = -abs(amount)
    elif op["Операция"] == "Пополнение":
        amount = abs(amount)
    # "План" может быть + или - (как задумано), оставим как есть
    op["Сумма"] = round(amount, 2)

    # Возвращаем список (обычная операция)
    return [op]

def _transfer_to_two_rows(op: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Конвертирует "Перевод" в две строки:
    1) Строка списания: Банк=откуда, Сумма= -X, Конкретика=куда
    2) Строка зачисления: Банк=куда, Сумма= +X, Конкретика=откуда
    Требуемые поля: Банк Отправитель, Банк Получатель, Сумма, Дата.
    Если каких-то нет — попытаемся выдернуть из Конкретики.
    """
    date_iso = _ensure_date_iso(op.get("Дата") or datetime.now().date().isoformat())
    dt = datetime.fromisoformat(date_iso)

    # Попытки достать банки:
    bank_from = op.get("Банк Отправитель") or ""
    bank_to   = op.get("Банк Получатель") or ""
    # Подстраховка через "Конкретика: Банк ХХХ → Банк YYY"
    if not bank_from or not bank_to:
        hint = (op.get("Конкретика") or "").lower()
        # это просто эвристика; лучше хранить явные поля
        # оставим как есть, если не нашли
        _ = hint

    try:
        base_amt = abs(float(str(op.get("Сумма","0")).replace(",", ".")))
    except Exception:
        base_amt = 0.0

    row1 = {
        "Год": dt.year, "Месяц": RU_MONTHS[dt.month-1],
        "Банк": bank_from, "Операция": "Перевод",
        "Дата": date_iso, "Сумма": -round(base_amt, 2),
        "Классификация": "Перевод", "Конкретика": bank_to or "—"
    }
    row2 = {
        "Год": dt.year, "Месяц": RU_MONTHS[dt.month-1],
        "Банк": bank_to, "Операция": "Перевод",
        "Дата": date_iso, "Сумма": round(base_amt, 2),
        "Классификация": "Перевод", "Конкретика": bank_from or "—"
    }
    return [row1, row2]

def format_card(op: Dict[str, Any]) -> str:
    """
    Формат карточки операции с эмодзи.
    """
    def line(k, v):
        em = EMOJI.get(k, "•")
        return f"{em} {k}: {v if v not in [None,''] else '—'}"

    # Особый случай "Перевод" — ожидать, что есть Банк Отправитель/Получатель
    if op.get("Операция") == "Перевод":
        rows = [
            line("Дата", _ensure_date_iso(op.get("Дата",""))),
            f"{EMOJI['Банк']} Банк Отправитель: {op.get('Банк Отправитель','—')}",
            f"{EMOJI['Банк']} Банк Получатель: {op.get('Банк Получатель','—')}",
            line("Сумма", op.get("Сумма","—")),
        ]
        return "🔁 Перевод\n" + "\n".join(rows)

    # Обычная операция
    rows = [
        line("Дата", _ensure_date_iso(op.get("Дата",""))),
        line("Банк", op.get("Банк","")),
        line("Операция", op.get("Операция","")),
        line("Сумма", op.get("Сумма","")),
        line("Классификация", op.get("Классификация","")),
        line("Конкретика", op.get("Конкретика","")),
    ]
    return "🧾 Операция\n" + "\n".join(rows)

# -----------------------------
# 1) GPT: промт и парсинг JSON
# -----------------------------

SYSTEM_PROMPT = (
    "Ты финансовый помощник. Преобразуй пользовательское сообщение об операции в строго валидный JSON, "
    "со следующими полями на русском: Год, Месяц, Банк, Операция, Дата, Сумма, Классификация, Конкретика. "
    "Операция ∈ {Трата, Пополнение, Перевод, План}. "
    "Если операция Перевод, верни JSON-массив из двух объектов (строк): первая — списание со знаком минус, "
    "вторая — зачисление без минуса; в каждой укажи соответствующий Банк и в Конкретика — встречный Банк. "
    "Дата в формате YYYY-MM-DD (если не указана — сегодня). "
    "Месяц — русским словом (Январь..Декабрь), согласованный с датой. "
    "ЧИСЛОВЫЕ значения для суммы, без валюты. "
    "Не добавляй никаких комментариев и текста вне JSON."
)

async def gpt_to_json(user_text: str) -> Any:
    """
    Отправляем текст в OpenAI и возвращаем распарсенный JSON (dict или list).
    """
    if OpenAI is None:
        raise RuntimeError("Библиотека openai не установлена. Установи пакет `openai`.")

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.1,
        messages=[
            {"role":"system","content":SYSTEM_PROMPT},
            {"role":"user","content":user_text}
        ],
        response_format={"type":"json_object"}  # просим ровно JSON-объект; для Перевода ниже подстрахуемся
    )
    content = resp.choices[0].message.content.strip()

    # Страховка: иногда нужно распарсить массив
    # Попробуем сначала как объект, затем как массив
    try:
        data = json.loads(content)
    except Exception:
        # Попробуем найти самый большой JSON от { ... } или [ ... ]
        start_obj = content.find("{")
        start_arr = content.find("[")
        start = min([x for x in [start_obj, start_arr] if x != -1], default=0)
        end = max(content.rfind("}"), content.rfind("]"))
        data = json.loads(content[start:end+1])

    return data

def normalize_result(data: Any) -> List[Dict[str, Any]]:
    """
    Приводим результат GPT к списку операций (1 или 2).
    """
    ops: List[Dict[str,Any]] = []

    if isinstance(data, list):
        # Например, "Перевод" уже пришёл двумя строками
        for item in data:
            # Обычные операции тоже нормализуем (на случай ошибок знака)
            if item.get("Операция") == "Перевод":
                # Если GPT уже прислал 2 строки корректно — оставим как есть, только дату/месяц проверим
                for it in [item]:
                    it["Дата"] = _ensure_date_iso(it.get("Дата",""))
                    dt = datetime.fromisoformat(it["Дата"])
                    it["Год"] = it.get("Год") or dt.year
                    it["Месяц"] = it.get("Месяц") or RU_MONTHS[dt.month-1]
                    ops.append(it)
            else:
                ops.extend(_normalize_op(item))
    elif isinstance(data, dict):
        if data.get("Операция") == "Перевод":
            ops = _transfer_to_two_rows(data)
        else:
            ops = _normalize_op(data)
    else:
        # Невалидно → пусто
        ops = []

    # Финальная чистка: ограничим строки
    for op in ops:
        op["Классификация"] = (op.get("Классификация") or "")[:64]
        op["Конкретика"]     = (op.get("Конкретика") or "")[:128]

    return ops

# -----------------------------
# 2) ХЕНДЛЕРЫ: текст и голос
# -----------------------------

# 2.1 Текст → GPT → карточка
async def tariff2_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Этап 4.1: проверка доступа по тарифу (добавь свою проверку БД здесь при необходимости)
    # if not user_has_tariff2(update.effective_user.id): ...

    # Не перехватываем ввод, если ждём ссылку на таблицу
    if context.user_data.get("awaiting_sheet_url"):
        return
    # Проверка тарифа
    if not has_cap(context, "text"):
        return await update.message.reply_text(
            "✋ Текстовый ввод доступен в тарифах 2 и 3. "
            "Сменить тариф можно через /start → «Поменять тариф»."
        )

    txt = (update.message.text or "").strip()
    if not txt:
        return

    await update.message.reply_chat_action("typing")
    try:
        data = await gpt_to_json(txt)
        ops = normalize_result(data)
        if not ops:
            return await update.message.reply_text("Не удалось распознать операцию. Сформулируй иначе.")

        # Сохраняем в user_data для подтверждения
        context.user_data["t2_ops_pending"] = ops

        # Покажем карточку(и). Если одна — одна карточка; если две (перевод) — покажем обе.
        cards = []
        for op in ops:
            cards.append(format_card(op))
        text_card = "\n\n".join(cards)

        kb = [
            [InlineKeyboardButton("✅ Подтвердить", callback_data="t2_confirm")],
            [InlineKeyboardButton("❌ Отменить", callback_data="t2_cancel")],
        ]
        await update.message.reply_text(text_card, reply_markup=InlineKeyboardMarkup(kb))

    except Exception as e:
        await update.message.reply_text(f"Ошибка обработки: {e}")

# 2.2 Голос → STT → GPT → карточка
async def tariff2_voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Этап 4.2: голос → текст

    if context.user_data.get("awaiting_sheet_url"):
        return
    if not has_cap(context, "voice"):
        return await update.message.reply_text(
            "🎤 Голосовой ввод доступен в тарифах 2 и 3. "
            "Сменить тариф — /start → «Поменять тариф»."
        )

    voice = update.message.voice
    if not voice:
        return
    await update.message.reply_chat_action("record_voice")
    f = await voice.get_file()
    b = await f.download_as_bytearray()

    # ogg → wav (нужен ffmpeg в системе)
    audio = AudioSegment.from_file(io.BytesIO(b), format="ogg")
    wav_io = io.BytesIO()
    audio.export(wav_io, format="wav")
    wav_io.seek(0)

    # SpeechRecognition
    r = sr.Recognizer()
    with sr.AudioFile(wav_io) as source:
        audio_data = r.record(source)
    try:
        text_ru = r.recognize_google(audio_data, language="ru-RU")
    except Exception:
        return await update.message.reply_text("Не удалось распознать голос. Повтори, пожалуйста.")

    # Дальше — как с текстом
    await update.message.reply_chat_action("typing")
    try:
        data = await gpt_to_json(text_ru)
        ops = normalize_result(data)
        if not ops:
            return await update.message.reply_text("Не удалось распознать операцию из речи.")

        context.user_data["t2_ops_pending"] = ops
        cards = [format_card(op) for op in ops]
        kb = [
            [InlineKeyboardButton("✅ Подтвердить", callback_data="t2_confirm")],
            [InlineKeyboardButton("❌ Отменить", callback_data="t2_cancel")],
        ]
        await update.message.reply_text("\n\n".join(cards), reply_markup=InlineKeyboardMarkup(kb))
    except Exception as e:
        await update.message.reply_text(f"Ошибка обработки: {e}")

# 2.3 Фото → (пока заглушка под Тариф 3)
async def tariff3_photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_sheet_url"):
        return
    if not has_cap(context, "photo"):
        return await update.message.reply_text(
            "📷 Обработка фото чеков доступна в Тарифе 3.\n"
            "Сменить тариф — /start → «Поменять тариф»."
        )
    # Здесь позже будет реальная обработка фото/QR/скринов
    return await update.message.reply_text(
        "📷 Фото получено. Обработка чеков будет добавлена на следующем шаге патча."
    )

# -----------------------------
# 3) КОЛЛБЭКИ: подтвердить / отменить
# -----------------------------

async def t2_confirm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    ops: List[Dict[str, Any]] = context.user_data.get("t2_ops_pending") or []
    if not ops:
        return await q.edit_message_text("Нет данных для записи.")

    # Этап 4.3: если у операции пустой Банк → спросить банк (интегрируй сюда свою функцию выбора банка)
    # Если хочешь: если у какой-либо операции нет банка, запускаем ask_bank_show(...) и return.
    if any(not (op.get("Банк") or "").strip() and op.get("Операция") != "Перевод" for op in ops):
        # >>> ВСТАВЬ сюда свою реализацию выбора банка и вернись после выбора <<<
        # await ask_bank_show(update, context, current_value="")
        return await q.edit_message_text("Нужно выбрать банк для операции (добавь вызов своего выбора банка здесь).")

    # Получаем URL таблицы пользователя (где-то ты это сохраняешь при Этапе 2)
    sheet_url = context.user_data.get("sheet_url")
    if not sheet_url:
        return await q.edit_message_text("Сначала подключите таблицу (Этап 2).")

    ws_fin, _ = open_finance_and_plans(sheet_url)

    # Этап 4.4: запись всех строк (учитываем случай «Перевод» — у нас ops уже может быть длиной 2)
    for op in ops:
        row = [
            op.get("Год"), op.get("Месяц"), op.get("Банк"),
            op.get("Операция"), op.get("Дата"), op.get("Сумма"),
            op.get("Классификация"), op.get("Конкретика")
        ]
        ws_fin.append_row(row, value_input_option="USER_ENTERED")

    context.user_data.pop("t2_ops_pending", None)
    await q.edit_message_text(f"✅ Добавлено строк: {len(ops)}")

async def t2_cancel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data.pop("t2_ops_pending", None)
    await q.edit_message_text("Отменено.")

# -----------------------------
# 4) РЕГИСТРАЦИЯ ХЕНДЛЕРОВ
# -----------------------------

def register_tariff2_handlers(app):
    """
    Регистрируем обработчики для Тарифа 2: текст и голос + подтверждение.
    """
    # Текстовые сообщения (кроме команд)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, tariff2_text_handler))
    # Голосовые
    app.add_handler(MessageHandler(filters.VOICE, tariff2_voice_handler))
    # Коллбэки подтверждения
    app.add_handler(CallbackQueryHandler(t2_confirm_cb, pattern=r"^t2_confirm$"))
    app.add_handler(CallbackQueryHandler(t2_cancel_cb,  pattern=r"^t2_cancel$"))
        # Фото (и изображения-документы)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, tariff3_photo_handler))

