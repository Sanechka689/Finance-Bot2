# utils/constants.py

# Этап 1: выбор тарифа
STATE_TARIFF_MENU            = 1
STATE_TARIFF_DETAIL          = 2

# Этап 2: подключение Google Sheets
STATE_SHEET                  = 3

# Этап 3: первоначальное заполнение банков
STATE_BANK_MENU              = 4
STATE_BANK_CUSTOM            = 5
STATE_BANK_AMOUNT            = 6
STATE_BANK_OPTION            = 7
STATE_BANK_EDIT_CHOICE       = 8
STATE_BANK_EDIT_INPUT        = 9

# Этап 4: ручное заполнение операций
STATE_IDLE                   = 0   # зарезервировано
STATE_OP_MENU                = 10  # после /add — «Добавить»/«Меню»
STATE_OP_FIELD_CHOOSE        = 11  # меню полей: Дата, Банк, …
STATE_OP_FIELD_INPUT         = 12  # ввод текстового значения для любого поля
STATE_SELECT_DATE            = 13  # календарь
STATE_SELECT_BANK            = 14  # выбор банка
STATE_SELECT_OPERATION       = 15  # выбор типа операции
STATE_ENTER_AMOUNT           = 16  # ввод суммы
STATE_ENTER_CLASSIFICATION   = 17  # ввод классификации
STATE_ENTER_SPECIFIC         = 18  # ввод конкретики
STATE_CONFIRM                = 19  # подтверждение перед записью
STATE_OP_LIST                = 20   # показ списка последних операций
STATE_OP_SELECT              = 21   # пользователь выбрал номер операции
STATE_OP_CONFIRM             = 22   # пользователь нажал «Подтвердить» / «Изменить» / «Удалить»
STATE_OP_EDIT_CHOICE         = 23   # пользователь выбрал, какое поле править
STATE_OP_EDIT_INPUT          = 24   # ввод нового значения поля

# Этап 5 — раздел «Классификация»
STATE_CLASS_MENU   = 25  # показ агрегации за выбранный период

