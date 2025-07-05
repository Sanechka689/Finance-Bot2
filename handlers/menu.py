# handlers/menu.py

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes
from services.sheets_service import open_finance_and_plans
from utils.constants import STATE_OP_MENU  # ваше состояние после /add

import logging
logger = logging.getLogger(__name__)


def _build_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Финансы",         callback_data="menu:finance"),
         InlineKeyboardButton("📝 Операции",        callback_data="menu:operations")],
        [InlineKeyboardButton("🏷 Классификация",   callback_data="menu:classification"),
         InlineKeyboardButton("🗓 Планы",           callback_data="menu:plans")],
        [InlineKeyboardButton("➕ Добавить Банк",   callback_data="menu:add_bank"),
         InlineKeyboardButton("➖ Удалить Банк",    callback_data="menu:del_bank")],
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
        logger.debug("🏷 Branch FINANCE start")
        await query.answer(text="Получаю баланс…", show_alert=False)

        url = context.user_data.get("sheet_url")
        logger.debug("🏷 sheet_url = %r", url)

        if not url:
            logger.debug("⚠️ sheet_url пуст, рисуем меню заново")
            await query.edit_message_text(
                "⚠️ Сначала подключите таблицу: /setup и вставьте ссылку.",
                reply_markup=_build_main_kb()
            )
            return STATE_OP_MENU

        try:
            ws, _ = open_finance_and_plans(url)
            records = ws.get_all_records()
            logger.debug("🏷 Получено %d записей из Sheets", len(records))
        except Exception as e:
            logger.exception("❌ Ошибка при open_finance_and_plans")
            await query.edit_message_text(
                f"❌ Ошибка при получении данных:\n{e}",
                reply_markup=_build_main_kb()
            )
            return STATE_OP_MENU

        # Группируем
        balances = {}
        for row in records:
            bank = row.get("Банк") or "Неизвестно"
            raw = row.get("Сумма", 0)
            # Убираем все пробелы (в том числе неразрывные) и заменяем запятую на точку
            s = str(raw).replace('\xa0', '').replace(' ', '').replace(',', '.')
            try:
                amt = float(s)
            except ValueError:
                # на всякий случай пропускаем неконвертируемое значение
                continue
            balances[bank] = balances.get(bank, 0.0) + amt
        logger.debug("🏷 balances = %r", balances)

        total = sum(balances.values())
        lines = [f"• {b}: {balances[b]:.2f}" for b in balances]
        text = "💰 *Текущий баланс по банкам:*\n" + "\n".join(lines)
        text += f"\n\n*Общая сумма:* {total:.2f}"

        logger.debug("🏷 Финальная строка текста: %r", text)

        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="menu:open")]
            ])
        )
        logger.debug("🏷 FINANCE branch finished")
        return STATE_OP_MENU

    # остальные пункты — заглушки
    logger.debug("🏷 Branch OTHER: %r", data)
    responses = {
        "menu:operations":    "📝 Раздел «Операции» в разработке…",
        "menu:classification":"🏷 Раздел «Классификация» в разработке…",
        "menu:plans":         "🗓 Раздел «Планы» в разработке…",
        "menu:add_bank":      "➕ Раздел «Добавить Банк» в разработке…",
        "menu:del_bank":      "➖ Раздел «Удалить Банк» в разработке…",
        "menu:edit_table":    "✏️ Раздел «Изменить таблицу» в разработке…",
        "menu:change_tariff": "💳 Раздел «Поменять тариф» в разработке…",
        "menu:show_sheet":    "🔗 Раздел «Показать таблицу» в разработке…",
        "menu:support":       "💬 Раздел «Поддержка» в разработке…",
    }
    text = responses.get(data, "⚠️ Неизвестный пункт меню.")
    await query.edit_message_text(text, reply_markup=_build_main_kb())
    return STATE_OP_MENU

def register_menu_handlers(app):
    """Регистрирует глобальный /menu и все menu:* коллбэки."""
    app.add_handler(CommandHandler("menu", show_main_menu))
    app.add_handler(CallbackQueryHandler(handle_menu_selection, pattern=r"^menu:"))
