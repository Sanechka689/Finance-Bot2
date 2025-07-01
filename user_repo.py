# user_repo.py
from sqlalchemy.orm import sessionmaker
from models import User

class UserRepository:
    def __init__(self, engine):
        self.Session = sessionmaker(bind=engine)

    def save_tariff(self, user_id, tariff, paid=False):
        session = self.Session()
        user = session.query(User).get(user_id)
        if not user:
            user = User(id=user_id, tariff=tariff, paid=paid)
            session.add(user)
        else:
            user.tariff = tariff
            user.paid   = paid
        session.commit()
        session.close()

    def mark_paid(self, user_id):
        session = self.Session()
        user = session.query(User).get(user_id)
        if user:
            user.paid = True
            session.commit()
        session.close()

    def get(self, user_id):
        session = self.Session()
        user = session.query(User).get(user_id)
        session.close()
        return user
