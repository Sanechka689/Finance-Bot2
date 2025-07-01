# payment_client.py

# ==============================
# Stage 3: Payment Client Stub
# ==============================

# Stage 3.1: dummy-класс для создания URL оплаты
class DummyPaymentClient:
    # Stage 3.1.1: сформировать тестовый checkout-ссылку
    def create_checkout_session(self, user_id: int, tariff: str) -> str:
        # здесь позже подключим реальный SDK (Stripe, YooMoney и т.д.)
        return f"https://example.com/checkout?user={user_id}&tariff={tariff}"

# Stage 3.2: фабрика для инициализации клиента оплаты
def init_payment_client():
    return DummyPaymentClient()
