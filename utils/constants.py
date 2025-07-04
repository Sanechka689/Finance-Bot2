# utils/constants.py

# Этап 1: выбор тарифа
STATE_TARIFF_MENU   = 1   # экран с перечнем тарифов
STATE_TARIFF_DETAIL = 2   # экран с описанием выбранного тарифа

# Этап 2: подключение Google Sheets
STATE_SHEET         = 3   # ожидание ссылки на Google Sheets

# Этап 3: первоначальное заполнение банков
STATE_BANK_MENU         = 4  # показ основного меню банков
STATE_BANK_CUSTOM       = 5  # ввод своего названия банка
STATE_BANK_AMOUNT       = 6  # ввод суммы банка
STATE_BANK_OPTION       = 7  # меню опций: добавить/изменить/готово
STATE_BANK_EDIT_CHOICE  = 8  # выбор, что редактировать: банк или сумму
STATE_BANK_EDIT_INPUT   = 9  # ввод нового значения для редактирования

# Этап 4: ручное заполнение операций
STATE_IDLE               = 0   # не используется прямо, но зарезервировано
STATE_OP_MENU            = 10  # показ кнопок «Добавить» / «Меню»
STATE_OP_FIELD_CHOOSE    = 11  # выбор конкретного поля (дата, банк, ...)
STATE_OP_FIELD_INPUT     = 12  # ввод значения выбранного поля
STATE_SELECT_DATE        = 13  # выбор даты из календаря
STATE_SELECT_BANK        = 14  # выбор банка из списка кнопок
STATE_SELECT_OPERATION   = 15  # выбор типа операции
STATE_ENTER_AMOUNT       = 16  # ввод суммы
STATE_CONFIRM            = 17  # подтверждение перед записью
