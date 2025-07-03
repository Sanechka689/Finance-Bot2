# bot.py — точка входа с этапами 1 и 2

import os
from telegram.ext import ApplicationBuilder

from handlers.tariff import register_tariff_handlers
from handlers.sheet  import register_sheet_handlers  # ← Импорт обработки /setup

def main():
    """
    Создаёт приложение, регистрирует хендлеры и запускает polling.
    """
    token = os.getenv("TELEGRAM_TOKEN")
    app   = ApplicationBuilder().token(token).build()

    # Этап 1: выбор тарифа
    register_tariff_handlers(app)

    # Этап 2: подключение Google Sheets (/setup)
    register_sheet_handlers(app)  # ← Регистрация ConversationHandler для /setup

    app.run_polling()

if __name__ == "__main__":
    main()
