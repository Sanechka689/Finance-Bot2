# utils/caps.py
CAP_MATRIX = {
    "tariff_free": {"manual": True,  "text": False, "voice": False, "photo": False},
    "tariff_2":    {"manual": True,  "text": True,  "voice": True,  "photo": False},
    "tariff_3":    {"manual": True,  "text": True,  "voice": True,  "photo": True},
}

def get_user_tariff(context) -> str:
    return context.user_data.get("tariff", "tariff_free")

def has_cap(context, cap: str) -> bool:
    t = get_user_tariff(context)
    return CAP_MATRIX.get(t, {}).get(cap, False)

