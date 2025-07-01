# user_repo.py

# ==============================
# Stage 2: User Repository
# ==============================

# Stage 2.1: импорт фабрики сессий и модели User
from sqlalchemy.orm import sessionmaker
from models import User

# Stage 2.2: класс-репозиторий для CRUD-операций над User
class UserRepository:
    # Stage 2.2.1: инициализация с привязкой к SQLAlchemy engine
    def __init__(self, engine):
        self.Session = sessionmaker(bind=engine)

    # Stage 2.3: сохранить или обновить тариф и статус оплаты
    def save_tariff(self, user_id: int, tariff: str, paid: bool = False):
        session = self.Session()
        user = session.query(User).get(user_id)
        if not user:
            # Stage 2.3.1: новый пользователь
            user = User(id=user_id, tariff=tariff, paid=paid)
            session.add(user)
        else:
            # Stage 2.3.2: обновление существующего
            user.tariff = tariff
            user.paid   = paid
        session.commit()
        session.close()

    # Stage 2.4: отметить пользователя как оплатившего тариф
    def mark_paid(self, user_id: int):
        session = self.Session()
        user = session.query(User).get(user_id)
        if user:
            user.paid = True
            session.commit()
        session.close()

    # Stage 2.5: получить объект пользователя по ID
    def get(self, user_id: int):
        session = self.Session()
        user = session.query(User).get(user_id)
        session.close()
        return user
