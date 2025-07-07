# handlers/menu.py

import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes

from services.sheets_service import open_finance_and_plans
from utils.constants import STATE_OP_MENU  # ваше состояние после /add
from handlers.men_oper import start_men_oper  # импорт ветки «Операции»

logger = logging.getLogger(__name__)


def _build_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Финансы",       callback_data="menu:finance"),
         InlineKeyboardButton("📝 Операции",      callback_data="menu:men_oper")],
        [InlineKeyboardButton("🏷 Классификация", callback_data="menu:classification"),
         InlineKeyboardButton("🗓 Планы",         callback_data="menu:plans")],
        [InlineKeyboardButton("➕ Добавить Банк", callback_data="menu:add_bank"),
         InlineKeyboardButton("➖ Удалить Банк",  callback_data="menu:del_bank")],
        [InlineKeyboardButton("✏️ Изменить таблицу", callback_data="menu:edit_table"),
         InlineKeyboardButton("💳 Поменять тариф",   callback_data="menu:change_tariff")],
        [InlineKeyboardButton("🔗 Показать таблицу", callback_data="menu:show_sheet"),
         InlineKeyboardButton("💬 Поддержка",        callback_data="menu:support")],
        [InlineKeyboardButton("🔙 Назад",            callback_data="menu:back")],
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
    logger.debug("🏷 handle_menu_selection called, data=%r", data)

    # — Открыть / перерисовать меню
    if data == "menu:open":
        logger.debug("🏷 Branch OPEN")
        await show_main_menu(update, context)
        return STATE_OP_MENU

    # — Назад
    if data == "menu:back":
        logger.debug("🏷 Branch BACK")
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
                [InlineKeyboardButton("🔙 Назад", callback_data="menu:open")]
            ])
        )
        return STATE_OP_MENU

    # — Операции
    if data == "menu:men_oper":
        logger.debug("🏷 Branch OPERATIONS")
        return await start_men_oper(update, context)

    # остальные пункты — заглушки
    logger.debug("🏷 Branch OTHER: %r", data)
    responses = {
        "menu:classification": "🏷 Раздел «Классификация» в разработке…",
        "menu:plans":          "🗓 Раздел «Планы» в разработке…",
        "menu:add_bank":       "➕ Раздел «Добавить Банк» в разработке…",
        "menu:del_bank":       "➖ Раздел «Удалить Банк» в разработке…",
        "menu:edit_table":     "✏️ Раздел «Изменить таблицу» в разработке…",
        "menu:change_tariff":  "💳 Раздел «Поменять тариф» в разработке…",
        "menu:show_sheet":     "🔗 Раздел «Показать таблицу» в разработке…",
        "menu:support":        "💬 Раздел «Поддержка» в разработке…",
    }
    text = responses.get(data, "⚠️ Неизвестный пункт меню.")
    await query.edit_message_text(text, reply_markup=_build_main_kb())
    return STATE_OP_MENU


def register_menu_handlers(app):
    """Регистрирует глобальный /menu и все menu:* коллбэки."""
    app.add_handler(CommandHandler("menu", show_main_menu))
    # потом — общий хэндлер для всех остальных menu:*
    app.add_handler(CallbackQueryHandler(handle_menu_selection, pattern=r"^menu:"))
