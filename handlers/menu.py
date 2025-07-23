# handlers/menu.py

import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes

from services.sheets_service import open_finance_and_plans
from utils.constants import STATE_OP_MENU  # ваше состояние после /add
from handlers.men_oper import start_men_oper  # импорт ветки «Операции»

from handlers.classification import (
  start_classification, handle_class_period, handle_class_back
)
from utils.constants import STATE_CLASS_MENU

from telegram.ext import MessageHandler
from telegram.ext import filters
from handlers.menu_banks import show_banks_menu
from services.sheets_service import open_finance_and_plans


def _build_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Финансы",       callback_data="menu:finance"),
         InlineKeyboardButton("📝 Операции",      callback_data="menu:men_oper")],
        [InlineKeyboardButton("🏷 Классификация", callback_data="menu:classification"),
         InlineKeyboardButton("🗓 Планы",         callback_data="menu:plans")],
        [InlineKeyboardButton("➕ Добавить Банк", callback_data="menu:add_bank"),
         InlineKeyboardButton("🔗 Показать таблицу", callback_data="menu:show_sheet")],
        [InlineKeyboardButton("✏️ Изменить таблицу", callback_data="menu:edit_table"),
         InlineKeyboardButton("💳 Поменять тариф",   callback_data="menu:change_tariff")],
        [InlineKeyboardButton("💬 Поддержка",        callback_data="menu:support"),
         InlineKeyboardButton("🔙 Назад",            callback_data="menu:back")],
    ])


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отображает главное меню (новым или редактирует текущее сообщение)."""
    kb = _build_main_kb()
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "Выберите раздел меню:", reply_markup=kb
        )
    else:
        await update.message.reply_text(
            "Выберите раздел меню:", reply_markup=kb
        )
    return STATE_OP_MENU


async def handle_menu_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data  # например "menu:finance"

    # — Открыть / перерисовать меню
    if data == "menu:open":
        await show_main_menu(update, context)
        return STATE_OP_MENU

    # — Назад
    if data == "menu:back":
        from handlers.operations import go_main_menu
        return await go_main_menu(update, context)

    # — Финансы
    if data == "menu:finance":
        await query.answer(text="Получаю баланс…", show_alert=False)
        url = context.user_data.get("sheet_url")
        if not url:
            await query.edit_message_text(
                "⚠️ Сначала подключите таблицу: /setup и вставьте ссылку.",
                reply_markup=_build_main_kb()
            )
            return STATE_OP_MENU

        try:
            ws, _ = open_finance_and_plans(url)

            # --- здесь реальная вставка вместо get_all_records ---
            # тянем из столбца C (3-я) — банки, и из F (6-я) — суммы, пропуская заголовок
            bank_list = ws.col_values(3)[1:]
            sum_list  = ws.col_values(6)[1:]

            balances = {}
            for bank, raw in zip(bank_list, sum_list):
                if not bank:
                    # пропускаем пустые строки
                    continue
                # приводим «1 234,56» → «1234.56»
                s = str(raw).replace("\xa0", "").replace(" ", "").replace(",", ".")
                try:
                    amt = float(s)
                except ValueError:
                    # если вдруг не число — пропускаем
                    continue
                balances[bank] = balances.get(bank, 0.0) + amt
            # ------------------------------------------------------------

        except Exception as e:
            await query.edit_message_text(
                f"❌ Ошибка при получении данных:\n{e}",
                reply_markup=_build_main_kb()
            )
            return STATE_OP_MENU

        total = sum(balances.values())
        # helper-функция для форматирования
        def fmt(x: float) -> str:
            s = f"{x:,.2f}"  # e.g. "33,400.00" или "-654.00"
            s = s.replace(",", "X").replace(".", ",").replace("X", " ")
            # результат: "33 400,00" или "-654,00"
            return s

        # сортируем банки по алфавиту
        lines = [
            f"• {bank}: {fmt(balances[bank])}"
            for bank in sorted(balances)
        ]
        text = "💰 *Текущий баланс по банкам:*\n" + "\n".join(lines)
        text += f"\n\n*Общая сумма:* {fmt(total)}"

        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="menu:open")]]))
        return STATE_OP_MENU

    # — Операции
    if data == "menu:men_oper":
        return await start_men_oper(update, context)

    # - Классификация
    if data == "menu:classification":
        return await start_classification(update, context)

    # — Показать таблицу
    if data == "menu:show_sheet":
        url = context.user_data.get("sheet_url")
        if url:
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Открыть таблицу", url=url)],
                [InlineKeyboardButton("🔙 Назад", callback_data="menu:open")]])
            await query.edit_message_text(
                "Нажмите кнопку ниже, чтобы открыть вашу Google-таблицу:",
                reply_markup=markup)
        else:
            await query.edit_message_text(
                "⚠️ Сначала подключите таблицу: /setup",
                reply_markup=_build_main_kb())
        return STATE_OP_MENU
   
    # — Изменить таблицу
    if data == "menu:edit_table":
        await query.edit_message_text("✏️ Пожалуйста, отправьте ссылку на новую Google-таблицу:")
        context.user_data["awaiting_sheet_url"] = True
        return STATE_OP_MENU

    # остальные пункты — заглушки
    responses = {
        "menu:change_tariff":  "💳 Раздел «Поменять тариф» в разработке…",
        "menu:support":        "💬 Раздел «Поддержка» в разработке…",
    }
    text = responses.get(data, "⚠️ Неизвестный пункт меню.")
    await query.edit_message_text(text, reply_markup=_build_main_kb())
    return STATE_OP_MENU

# Изменить табилцу (кнопка)

async def handle_new_sheet_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Ловит текстовое сообщение, если мы ждем ссылку на новую таблицу.
    """
    if not context.user_data.get("awaiting_sheet_url"):
        return  # не наше сообщение
    url = update.message.text.strip()

    # Проверяем только чтение таблицы (без модификаций)
    import os
    from gspread import service_account as gspread_sa

    creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    try:
        sa = gspread_sa(filename=creds)
        sa.open_by_url(url)
    except Exception as e:
        await update.message.reply_text(
            f"❌ Не удалось открыть таблицу на чтение: {e}\n"
            "Пожалуйста, отправьте корректную ссылку."
        )
        return

    # Сохраняем новый URL
    context.user_data["sheet_url"] = url
    # Снимаем флаг ожидания
    context.user_data.pop("awaiting_sheet_url", None)
    # Подтверждаем пользователю
    await update.message.reply_text("✅ Таблица успешно подключена!")

    # 1) Предлагаем сразу войти в раздел «Добавить Банк»
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить Банк", callback_data="menu:add_bank")],
    ])
    await update.message.reply_text(
        "Теперь нажмите кнопку ниже, чтобы добавить стартовые банки:",
        reply_markup=kb
    )
    # 2) Завершаем обработчик
    return




def register_menu_handlers(app):
    """Регистрирует глобальный /menu и все menu:* коллбэки."""
    # 1) Команда /menu
    app.add_handler(CommandHandler("menu", show_main_menu))

    # 2) Раздел «Классификация»
    app.add_handler(CallbackQueryHandler(start_classification,pattern=r"^menu:classification$"))
    app.add_handler(CallbackQueryHandler(handle_class_period,pattern=r"^class_(prev|year|all)$"))
    app.add_handler(CallbackQueryHandler(handle_class_back,pattern=r"^class_back$"))

    # 3) Раздел «Планы»
    #app.add_handler(CallbackQueryHandler(start_plans,pattern=r"^menu:plans$"))

    # 3) Общий хендлер для остальных пунктов menu:*
    app.add_handler(CallbackQueryHandler(handle_menu_selection,pattern=r"^menu:"))

    # 4) Обработчик текстовых сообщений при ожидании ссылки на новую таблицу
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_sheet_response),
        # группа >0, чтобы этот хендлер сработал после коллбеков меню
        group=1)

