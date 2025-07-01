# payment_client.py
class DummyPaymentClient:
    def create_checkout_session(self, user_id: int, tariff: str) -> str:
        return f"https://example.com/pay?user={user_id}&tariff={tariff}"

def init_payment_client():
    return DummyPaymentClient()
