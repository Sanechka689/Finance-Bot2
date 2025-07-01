# main.py

# ==============================
# Stage 6: Точка входа и запуск бота
# ==============================

import os
from telegram.ext import ApplicationBuilder
from sqlalchemy import create_engine

# Stage 6.1: импорт регистрации всех этапов
from handlers_stage1 import register_stage1_handlers
from handlers_stage2 import register_stage2_handlers

# Stage 6.2: импорт репозитория и клиента оплаты
from user_repo import UserRepository
from payment_client import init_payment_client

# Stage 6.3: инициализация БД (SQLite для разработки)
os.environ.setdefault("DATABASE_URL", "sqlite:///users.db")
engine = create_engine(os.getenv("DATABASE_URL"))
user_repo = UserRepository(engine)

# Stage 6.4: инициализация Telegram-бота
app = ApplicationBuilder().token(os.getenv("TELEGRAM_TOKEN")).build()
app.bot_data['user_repo']      = user_repo
app.bot_data['payment_client'] = init_payment_client()

# Stage 6.5: регистрация этапов 1 и 2
register_stage1_handlers(app)
register_stage2_handlers(app)

# Stage 6.6: запуск polling
if __name__ == "__main__":
    app.run_polling()
