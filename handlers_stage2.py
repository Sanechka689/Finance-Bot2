# handlers_stage2.py

# ==============================
# Stage 5: Handlers для Этапа 2 (Google Sheets)
# ==============================

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from gsheet_client import init_sheets

# Stage 5.1: приём ссылки от пользователя и подключение таблицы
async def sheet_url_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Stage 5.1.1: извлекаем текст и ID
    text = update.message.text.strip()
    user_id = update.effective_user.id

    # Stage 5.1.2: проверяем, что это ссылка Google Sheets
    if not text.startswith("https://docs.google.com/"):
        await update.message.reply_text(
            "❌ Неправильный формат. Отправьте ссылку, начинающуюся с https://docs.google.com/…"
        )
        return

    # Stage 5.1.3: пробуем инициализировать клиента
    try:
        fin_ws, plan_ws = init_sheets("credentials.json", text)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Ошибка подключения к Google Sheets:\n{e}")
        return

    # Stage 5.1.4: сохраняем объекты ws в bot_data по user_id
    context.bot_data.setdefault("sheets", {})[user_id] = {
        "fin_ws": fin_ws,
        "plan_ws": plan_ws,
        "url": text
    }

    # Stage 5.1.5: уведомляем пользователя об успешном подключении
    await update.message.reply_text(
        "✅ Google Sheets подключена!\n"
        "Далее — первоначальное заполнение банков (Этап 3)."
    )

# Stage 5.2: регистрация хендлера Этапа 2
def register_stage2_handlers(app):
    """
    Регистрирует MessageHandler для обработки текстовых сообщений
    на этапе подключения Google Sheets (Stage 2).
    """
    app.add_handler(
        MessageHandler(filters.TEXT & (~filters.COMMAND), sheet_url_handler),
        group=1
    )
