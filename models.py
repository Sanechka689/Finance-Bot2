# models.py

# ==============================
# Stage 1: Data Model
# ==============================

# Stage 1.1: импорт декларативной базы и типов столбцов
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime

# Stage 1.2: базовый класс для всех моделей
Base = declarative_base()

# Stage 1.3: определение таблицы users
class User(Base):
    __tablename__ = "users"
    
    # Stage 1.3.1: Telegram user_id — первичный ключ
    id = Column(Integer, primary_key=True)
    # Stage 1.3.2: выбранный тариф: "tariff_free", "tariff_1" или "tariff_2"
    tariff = Column(String, nullable=False)
    # Stage 1.3.3: флаг оплаты тарифа (True — после оплаты или для бесплатного)
    paid = Column(Boolean, default=False)
    # Stage 1.3.4: ссылка на Google Sheets, указана пользователем
    sheet_url = Column(String, nullable=True)
    # Stage 1.3.5: дата и время создания записи (UTC)
    created_at = Column(DateTime, default=datetime.utcnow)
