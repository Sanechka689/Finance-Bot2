# utils/constants.py — FSM-состояния для этапов бота

# Этап 1: выбор тарифа
STATE_TARIFF_MENU   = 1  # экран с перечнем тарифов
STATE_TARIFF_DETAIL = 2  # экран с описанием выбранного тарифа

# Этап 2: подключение Google Sheets
STATE_SHEET         = 3  # ожидание ссылки на Google Sheets

# Этап 3: первоначальное заполнение банков
STATE_BANK_MENU         = 4  # показ основного меню банков
STATE_BANK_CUSTOM       = 5  # ввод своего названия банка
STATE_BANK_AMOUNT       = 6  # ввод суммы (новой или редактируемой)
STATE_BANK_OPTION       = 7  # кнопки «Добавить ещё» / «Изменить» / «Готово»
STATE_BANK_EDIT_CHOICE  = 8  # выбор, что редактировать: банк или сумму
STATE_BANK_EDIT_INPUT   = 9  # ввод нового значения поля для редактирования