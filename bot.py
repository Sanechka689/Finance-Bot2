import os
from telegram.ext import ApplicationBuilder
from handlers.tariff import register_tariff_handlers
from handlers.sheet import register_sheet_handlers
from handlers.banks import register_banks_handlers
# === Этап 4: регистрация ручного ввода операций ===
from handlers.operations import register_operations_handlers
from handlers.fallback import register_fallback_handler

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    app = ApplicationBuilder().token(token).build()

    # Этап 1: выбор тарифа
    register_tariff_handlers(app)
    # Этап 2: подключение таблицы
    register_sheet_handlers(app)
    # Этап 3: добавление банков
    register_banks_handlers(app)
    # Этап 4: ручной ввод операций через /add и меню полей
    register_operations_handlers(app)
    # Этап 4bis: fallback для всего остального
    register_fallback_handler(app)

    app.run_polling()

if __name__ == "__main__":
    main()
