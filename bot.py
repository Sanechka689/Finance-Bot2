# bot.py

import os
from telegram.ext import ApplicationBuilder

# Этап 1 — выбор тарифа (/start)
from handlers.tariff import register_tariff_handlers
# Этап 2 — подключение Google Sheets (/setup)
from handlers.sheet import register_sheet_handlers
# Этап 3 — первоначальное заполнение банков (/banks)
from handlers.banks import register_banks_handlers
# Этап 4 — ручной ввод операций (/add и меню полей)
from handlers.operations import register_operations_handlers
# Фоллбэк — всё остальное
from handlers.fallback import register_fallback_handler

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    app = ApplicationBuilder().token(token).build()

    # Регистрируем этапы в порядке их выполнения
    register_tariff_handlers(app)       # /start и выбор тарифа
    register_sheet_handlers(app)        # /setup и подключение таблицы
    register_banks_handlers(app)        # /banks и ввод банков
    register_operations_handlers(app)   # /add и ручной ввод операций
    register_fallback_handler(app)      # fallback на всё остальное

    app.run_polling()

if __name__ == "__main__":
    main()
