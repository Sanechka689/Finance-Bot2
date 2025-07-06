# bot.py

import logging

logging.basicConfig(
    format="%(asctime)s %(levelname)s:%(name)s: %(message)s",
    level=logging.DEBUG
)

import os
from telegram.ext import ApplicationBuilder

# Этап 1 — выбор тарифа (/start)
from handlers.tariff import register_tariff_handlers
# Этап 2 — подключение таблицы (/setup)
from handlers.sheet import register_sheet_handlers
# Этап 3 — первоначальное заполнение банков (/banks)
from handlers.banks import register_banks_handlers
# Этап 4 — ручной ввод операций (/add)
from handlers.operations import register_operations_handlers
# Этап 5 - работа кнопки меню (/menu)
from handlers.menu import register_menu_handlers
# Этап 5.1 - Меню - Операции
from handlers.men_oper import start_men_oper, register_men_oper_handlers
# Ловим всё остальное
from handlers.fallback import register_fallback_handler

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    app = ApplicationBuilder().token(token).build()

    # Регистрируем этапы в порядке выполнения
    register_tariff_handlers(app)       # /start
    register_sheet_handlers(app)        # /setup
    register_banks_handlers(app)        # /banks   
    register_menu_handlers(app)         # /menu
    register_men_oper_handlers(app)     # /Операции
    register_operations_handlers(app)   # /add  
    register_fallback_handler(app)      # всё остальное

    app.run_polling()

if __name__ == "__main__":
    main()
