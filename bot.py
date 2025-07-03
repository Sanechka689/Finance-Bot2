import os
from telegram.ext import ApplicationBuilder

from handlers.tariff import register_tariff_handlers
from handlers.sheet  import register_sheet_handlers
from handlers.banks  import register_banks_handlers  # ← новый

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    app   = ApplicationBuilder().token(token).build()

    # Этап 1
    register_tariff_handlers(app)
    # Этап 2
    register_sheet_handlers(app)
    # Этап 3
    register_banks_handlers(app)  # ← регистрация /banks

    app.run_polling()

if __name__ == "__main__":
    main()
