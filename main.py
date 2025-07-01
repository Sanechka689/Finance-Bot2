# main.py
import os
from telegram.ext import ApplicationBuilder
from sqlalchemy import create_engine

from handlers_stage1 import register_stage1_handlers
from user_repo import UserRepository
from payment_client import init_payment_client

# Stage1: Подключаем БД (для прототипа sqlite)
os.environ.setdefault("DATABASE_URL", "sqlite:///users.db")
engine = create_engine(os.getenv("DATABASE_URL"))
user_repo = UserRepository(engine)

app = ApplicationBuilder().token(os.getenv("TELEGRAM_TOKEN")).build()
app.bot_data['user_repo']     = user_repo
app.bot_data['payment_client']= init_payment_client()

register_stage1_handlers(app)

if __name__=="__main__":
    app.run_polling()
