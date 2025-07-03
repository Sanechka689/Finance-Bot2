# handlers/fallback.py — ловим все нераспознанные сообщения

from telegram import Update
from telegram.ext import MessageHandler, filters, ContextTypes

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ Я не понял. Доступные команды:\n"
        "/start  — выбор тарифа\n"
        "/setup  — подключение таблицы (после оплаты)\n"
        "/banks  — ввод стартовых банков (после подключения таблицы)"
    )

def register_fallback_handler(app):
    # Нужен после всех других хендлеров
    app.add_handler(MessageHandler(filters.ALL, unknown))
