# 3.6 bot.py — точка входа с обновлённым выбором тарифа

import os
from telegram.ext import ApplicationBuilder

from handlers.tariff import register_tariff_handlers

def main():
    """
    Создаёт приложение, регистрирует хендлеры и запускает polling.
    """
    token = os.getenv("TELEGRAM_TOKEN")
    app = ApplicationBuilder().token(token).build()

    # Регистрируем ConversationHandler этапа выбора тарифа
    register_tariff_handlers(app)

    app.run_polling()

if __name__ == "__main__":
    main()
