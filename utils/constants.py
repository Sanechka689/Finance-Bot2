# utils/constants.py — FSM-состояния для этапов бота

# Этап 1: выбор тарифа
STATE_TARIFF_MENU   = 1  # экран с перечнем тарифов
STATE_TARIFF_DETAIL = 2  # экран с описанием выбранного тарифа

# Этап 2: подключение Google Sheets
STATE_SHEET         = 3  # ожидание ссылки на Google Sheets

# Этап 3: первоначальное заполнение банков
STATE_BANK_CHOOSE   = 4  # выбор банка
STATE_BANK_AMOUNT   = 5  # ввод стартового баланса
