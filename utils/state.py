# utils/state.py

from utils.constants import STATE_IDLE

def init_user_state(context):
    """
    # 1.2.1: Сбрасываем FSM и заготовку под новую операцию
    """
    # 1.2.2: Устанавливаем state = STATE_IDLE
    context.user_data["state"] = STATE_IDLE

    # 1.2.3: Создаём пустой «черновик» операции
    context.user_data["pending_op"] = {
        "Дата":          None,  # 1.2.3.1
        "Банк":          None,  # 1.2.3.2
        "Операция":      None,  # 1.2.3.3
        "Сумма":         None,  # 1.2.3.4
        "Классификация": None,  # 1.2.3.5
        "Конкретика":    None,  # 1.2.3.6
    }

    # 1.2.4: Текущее поле ввода не задано
    context.user_data["current_field"] = None
