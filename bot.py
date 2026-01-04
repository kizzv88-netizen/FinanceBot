from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ConversationHandler, filters, ContextTypes
)
import sqlite3
from datetime import datetime, timedelta

import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# ---------- Состояния ----------
(
    MAIN_MENU,
    ADD_MENU,
    CHOOSING_CATEGORY,
    CHOOSING_CURRENCY,
    TYPING_AMOUNT,
    HISTORY_MENU,
    TYPING_DATE,
    STATS_MENU,
    SETTINGS_MENU,
    CONFIRM_CLEAR,
    CHOOSE_DELETE,
    CHOOSE_EDIT,
    EDIT_AMOUNT,
    CURRENCY_MENU,
    ADD_CURRENCY,
    DELETE_CURRENCY
) = range(16)

# ---------- База ----------
def init_db():
    conn = sqlite3.connect("finance.db")
    cursor = conn.cursor()
    
    # таблица операций
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            amount REAL,
            currency TEXT,
            category TEXT,
            date TEXT
        )
    """)
    
    # таблица валют
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS currencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE
        )
    """)
    
    # таблица категорий
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    """)
    
    # базовые категории, если таблица пустая
    cursor.execute("SELECT COUNT(*) FROM categories")
    if cursor.fetchone()[0] == 0:
        base_categories = ["🍔 Еда", "🚕 Транспорт", "🎮 Развлечения", "🛒 Покупки", "💊 Здоровье", "📦 Другое"]
        cursor.executemany("INSERT INTO categories (name) VALUES (?)", [(c,) for c in base_categories])
    
    conn.commit()
    conn.close()

def add_operation(op_type, amount, currency, category=None, date=None):
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect("finance.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO operations (type, amount, currency, category, date) VALUES (?, ?, ?, ?, ?)",
        (op_type, amount, currency, category, date)
    )
    conn.commit()
    conn.close()

def get_balance():
    conn = sqlite3.connect("finance.db")
    cursor = conn.cursor()
    cursor.execute("SELECT type, amount, currency FROM operations")
    rows = cursor.fetchall()
    conn.close()
    balances = {}
    for t, a, c in rows:
        balances.setdefault(c, 0)
        balances[c] += a if t == "income" else -a
    return balances

def get_operations_by_date(date_str):
    conn = sqlite3.connect("finance.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, type, amount, currency, category FROM operations WHERE date = ?",
        (date_str,)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

def delete_operation(op_id):
    conn = sqlite3.connect("finance.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM operations WHERE id = ?", (op_id,))
    conn.commit()
    conn.close()

def update_operation_amount(op_id, new_amount):
    conn = sqlite3.connect("finance.db")
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE operations SET amount = ? WHERE id = ?",
        (new_amount, op_id)
    )
    conn.commit()
    conn.close()

def clear_db():
    conn = sqlite3.connect("finance.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM operations")
    conn.commit()
    conn.close()

def get_monthly_category_stats(year_month):
    conn = sqlite3.connect("finance.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT category, currency, SUM(amount)
        FROM operations
        WHERE type = 'expense'
        AND date LIKE ?
        GROUP BY category, currency
    """, (f"{year_month}-%",))
    rows = cursor.fetchall()
    conn.close()
    return rows

# валюты
def add_currency(code):
    conn = sqlite3.connect("finance.db")
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO currencies (code) VALUES (?)", (code.upper(),))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

def delete_currency_db(code):
    conn = sqlite3.connect("finance.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM currencies WHERE code = ?", (code.upper(),))
    conn.commit()
    conn.close()

def get_all_currencies():
    conn = sqlite3.connect("finance.db")
    cursor = conn.cursor()
    cursor.execute("SELECT code FROM currencies")
    rows = [r[0] for r in cursor.fetchall()]
    conn.close()
    return rows
def get_all_categories():
    conn = sqlite3.connect("finance.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM categories")
    rows = [r[0] for r in cursor.fetchall()]
    conn.close()
    return rows

def add_category(name):
    conn = sqlite3.connect("finance.db")
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

def delete_category(name):
    conn = sqlite3.connect("finance.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM categories WHERE name = ?", (name,))
    conn.commit()
    conn.close()

# ---------- Кнопки ----------
def main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Добавить")],
        [KeyboardButton("📊 Статистика"), KeyboardButton("📅 История")],
        [KeyboardButton("💱 Валюты"), KeyboardButton("⚙️ Настройки")]
    ], resize_keyboard=True)

def add_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💰 Доход"), KeyboardButton("💸 Расход")],
        [KeyboardButton("⬅️ Назад")]
    ], resize_keyboard=True)

def category_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🍔 Еда"), KeyboardButton("🚕 Транспорт")],
        [KeyboardButton("🎮 Развлечения"), KeyboardButton("🛒 Покупки")],
        [KeyboardButton("💊 Здоровье"), KeyboardButton("📦 Другое")],
        [KeyboardButton("⬅️ Назад")]
    ], resize_keyboard=True)

def history_menu_buttons():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Сегодня"), KeyboardButton("Вчера")],
        [KeyboardButton("🗓 Ввести дату")],
        [KeyboardButton("⬅️ Назад")]
    ], resize_keyboard=True)

def history_actions_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("✏️ Редактировать"), KeyboardButton("🗑 Удалить")],
        [KeyboardButton("⬅️ Назад")]
    ], resize_keyboard=True)

def stats_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💰 Баланс")],
        [KeyboardButton("📊 Расходы по категориям (месяц)")],
        [KeyboardButton("⬅️ Назад")]
    ], resize_keyboard=True)

def settings_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🛠 Категории")],
        [KeyboardButton("🗑 Очистить базу")],
        [KeyboardButton("⬅️ Назад")]
    ], resize_keyboard=True)

def confirm_clear_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("✅ Да"), KeyboardButton("❌ Нет")]
    ], resize_keyboard=True)

def currencies_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Добавить валюту"), KeyboardButton("🗑 Удалить валюту")],
        [KeyboardButton("⬅️ Назад")]
    ], resize_keyboard=True)

def categories_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Добавить категорию"), KeyboardButton("🗑 Удалить категорию")],
        [KeyboardButton("⬅️ Назад")]
    ], resize_keyboard=True)

def category_menu():
    cats = get_all_categories()
    if not cats:
        return ReplyKeyboardMarkup([[KeyboardButton("⬅️ Назад")]], resize_keyboard=True)
    buttons = [[KeyboardButton(c)] for c in cats]
    buttons.append([KeyboardButton("⬅️ Назад")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

# ---------- Старт ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💸 Финансовый бот", reply_markup=main_menu())
    return MAIN_MENU

# ---------- Главное меню ----------
async def main_menu_handler(update: Update, context):
    text = update.message.text

    if text == "➕ Добавить":
        await update.message.reply_text("Выберите тип операции:", reply_markup=add_menu())
        return ADD_MENU

    if text == "📅 История":
        await update.message.reply_text("История операций:", reply_markup=history_menu_buttons())
        return HISTORY_MENU

    if text == "📊 Статистика":
        await update.message.reply_text("Статистика:", reply_markup=stats_menu())
        return STATS_MENU

    if text == "⚙️ Настройки":
        await update.message.reply_text("Настройки:", reply_markup=settings_menu())
        return SETTINGS_MENU

    if text == "💱 Валюты":
        await update.message.reply_text("Управление валютами:", reply_markup=currencies_menu())
        return CURRENCY_MENU

    return MAIN_MENU

# ---------- Валюты ----------
async def currency_menu_handler(update: Update, context):
    text = update.message.text

    if text == "⬅️ Назад":
        return await start(update, context)

    if text == "➕ Добавить валюту":
        await update.message.reply_text("Введите код валюты (например, USD):")
        return ADD_CURRENCY

    if text == "🗑 Удалить валюту":
        currencies = get_all_currencies()
        if not currencies:
            await update.message.reply_text("Список валют пуст.", reply_markup=currencies_menu())
            return CURRENCY_MENU
        buttons = [[KeyboardButton(c)] for c in currencies]
        buttons.append([KeyboardButton("⬅️ Назад")])
        await update.message.reply_text("Выберите валюту для удаления:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
        return DELETE_CURRENCY

    return CURRENCY_MENU

async def add_currency_handler(update: Update, context):
    code = update.message.text.strip().upper()
    if code == "⬅️ Назад":
        return await main_menu_handler(update, context)
    add_currency(code)
    await update.message.reply_text(f"✅ Валюта {code} добавлена.", reply_markup=currencies_menu())
    return CURRENCY_MENU

async def delete_currency_handler(update: Update, context):
    code = update.message.text.strip().upper()
    if code == "⬅️ Назад":
        return await currency_menu_handler(update, context)
    delete_currency_db(code)
    await update.message.reply_text(f"🗑 Валюта {code} удалена.", reply_markup=currencies_menu())
    return CURRENCY_MENU

CATEGORY_MENU = 100
ADD_CATEGORY = 101
DELETE_CATEGORY = 102

async def categories_menu_handler(update: Update, context):
    text = update.message.text
    if text == "⬅️ Назад":
        await update.message.reply_text("Настройки:", reply_markup=settings_menu())
        return SETTINGS_MENU
    if text == "➕ Добавить категорию":
        await update.message.reply_text("Введите название новой категории:")
        return ADD_CATEGORY
    if text == "🗑 Удалить категорию":
        categories = get_all_categories()
        if not categories:
            await update.message.reply_text("Категории отсутствуют.", reply_markup=categories_menu())
            return CATEGORY_MENU
        buttons = [[KeyboardButton(c)] for c in categories]
        buttons.append([KeyboardButton("⬅️ Назад")])
        await update.message.reply_text("Выберите категорию для удаления:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
        return DELETE_CATEGORY
    return CATEGORY_MENU

async def add_category_handler(update: Update, context):
    name = update.message.text.strip()
    if name == "⬅️ Назад":
        await update.message.reply_text("Управление категориями:", reply_markup=categories_menu())
        return CATEGORY_MENU
    add_category(name)
    await update.message.reply_text(f"✅ Категория '{name}' добавлена.", reply_markup=categories_menu())
    return CATEGORY_MENU

async def delete_category_handler(update: Update, context):
    name = update.message.text.strip()
    if name == "⬅️ Назад":
        await update.message.reply_text("Управление категориями:", reply_markup=categories_menu())
        return CATEGORY_MENU
    delete_category(name)
    await update.message.reply_text(f"🗑 Категория '{name}' удалена.", reply_markup=categories_menu())
    return CATEGORY_MENU

# ---------- Добавление ----------
async def add_menu_handler(update: Update, context):
    text = update.message.text

    if text == "⬅️ Назад":
        await update.message.reply_text("Главное меню:", reply_markup=main_menu())
        return MAIN_MENU

    if text == "💰 Доход":
        context.user_data["type"] = "income"
        context.user_data["category"] = None
        # Выбор валюты из БД
        currencies = get_all_currencies()
        if not currencies:
            await update.message.reply_text("Сначала добавьте валюту в разделе Валюты.", reply_markup=main_menu())
            return MAIN_MENU
        buttons = [[KeyboardButton(c)] for c in currencies]
        buttons.append([KeyboardButton("⬅️ Назад")])
        await update.message.reply_text("Выберите валюту:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
        return CHOOSING_CURRENCY

    if text == "💸 Расход":
        context.user_data["type"] = "expense"
        await update.message.reply_text("Выберите категорию:", reply_markup=category_menu())
        return CHOOSING_CATEGORY

    return ADD_MENU

# ---------- Продолжение добавления ----------
async def choosing_category(update: Update, context):
    text = update.message.text
    if text == "⬅️ Назад":
        await update.message.reply_text("Выберите тип операции:", reply_markup=add_menu())
        return ADD_MENU
    context.user_data["category"] = text

    currencies = get_all_currencies()
    buttons = [[KeyboardButton(c)] for c in currencies]
    buttons.append([KeyboardButton("⬅️ Назад")])
    await update.message.reply_text("Выберите валюту:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
    return CHOOSING_CURRENCY

async def choosing_currency(update: Update, context):
    text = update.message.text
    if text == "⬅️ Назад":
        if context.user_data.get("type") == "expense":
            await update.message.reply_text("Выберите категорию:", reply_markup=category_menu())
            return CHOOSING_CATEGORY
        else:
            await update.message.reply_text("Выберите тип операции:", reply_markup=add_menu())
            return ADD_MENU
    context.user_data["currency"] = text
    await update.message.reply_text("Введите сумму:")
    return TYPING_AMOUNT

async def typing_amount(update: Update, context):
    text = update.message.text
    if text == "⬅️ Назад":
        if context.user_data.get("type") == "expense":
            await update.message.reply_text("Выберите категорию:", reply_markup=category_menu())
            return CHOOSING_CATEGORY
        else:
            await update.message.reply_text("Выберите тип операции:", reply_markup=add_menu())
            return ADD_MENU
    try:
        amount = float(text)
    except:
        await update.message.reply_text("Введите число.")
        return TYPING_AMOUNT
    add_operation(
        context.user_data["type"],
        amount,
        context.user_data["currency"],
        context.user_data["category"]
    )
    msg = f"{'💰' if context.user_data['type']=='income' else '💸'} {amount} {context.user_data['currency']} {'добавлено' if context.user_data['type']=='income' else 'потрачено'}"
    await update.message.reply_text(msg, reply_markup=main_menu())
    context.user_data.clear()
    return MAIN_MENU

# ---------- История и редактирование ----------
async def history_handler(update: Update, context):
    text = update.message.text
    today = datetime.now().strftime("%Y-%m-%d")
    if text == "⬅️ Назад":
        await update.message.reply_text("Главное меню:", reply_markup=main_menu())
        return MAIN_MENU
    if text == "Сегодня":
        date = today
    elif text == "Вчера":
        date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    elif text == "🗓 Ввести дату":
        await update.message.reply_text("Введите дату в формате ДД.MM")
        return TYPING_DATE
    elif text == "✏️ Редактировать":
        await update.message.reply_text("Введите номер операции для редактирования:")
        return CHOOSE_EDIT
    elif text == "🗑 Удалить":
        await update.message.reply_text("Введите номер операции для удаления:")
        return CHOOSE_DELETE
    else:
        return HISTORY_MENU

    ops = get_operations_by_date(date)
    await send_history(update, date, ops, context)
    return HISTORY_MENU

async def typing_date(update: Update, context):
    try:
        day, month = map(int, update.message.text.split("."))
        date = datetime(datetime.now().year, month, day).strftime("%Y-%m-%d")
    except:
        await update.message.reply_text("Неверный формат. Введите ДД.MM")
        return TYPING_DATE
    ops = get_operations_by_date(date)
    await send_history(update, date, ops, context)
    return HISTORY_MENU

async def send_history(update, date, ops, context):
    if not ops:
        await update.message.reply_text("Операций нет.", reply_markup=main_menu())
        return MAIN_MENU
    msg = f"📅 Операции за {date}:\n\n"
    numbered_ops = []
    for i, (op_id, t, a, c, cat) in enumerate(ops, start=1):
        sign = "💰" if t == "income" else "💸"
        cat_txt = f" ({cat})" if cat else ""
        msg += f"{i}️⃣ {sign} {a} {c}{cat_txt}\n"
        numbered_ops.append(op_id)
    context.user_data["history_ids"] = numbered_ops
    await update.message.reply_text(msg, reply_markup=history_actions_menu())

async def choose_delete(update: Update, context):
    try:
        index = int(update.message.text) - 1
        op_id = context.user_data["history_ids"][index]
    except:
        await update.message.reply_text("Неверный номер.")
        return CHOOSE_DELETE
    delete_operation(op_id)
    await update.message.reply_text("🗑 Операция удалена", reply_markup=main_menu())
    return MAIN_MENU

async def choose_edit(update: Update, context):
    try:
        index = int(update.message.text) - 1
        context.user_data["edit_op_id"] = context.user_data["history_ids"][index]
    except:
        await update.message.reply_text("Неверный номер.")
        return CHOOSE_EDIT
    await update.message.reply_text("Введите новую сумму:")
    return EDIT_AMOUNT

async def edit_amount(update: Update, context):
    try:
        new_amount = float(update.message.text)
    except:
        await update.message.reply_text("Введите число.")
        return EDIT_AMOUNT
    update_operation_amount(context.user_data["edit_op_id"], new_amount)
    await update.message.reply_text("✏️ Операция обновлена", reply_markup=main_menu())
    context.user_data.clear()
    return MAIN_MENU

# ---------- Статистика ----------
async def stats_handler(update: Update, context):
    text = update.message.text
    if text == "⬅️ Назад":
        await update.message.reply_text("Главное меню:", reply_markup=main_menu())
        return MAIN_MENU
    if text == "💰 Баланс":
        balances = get_balance()
        msg = "💰 Баланс:\n"
        for c, b in balances.items():
            msg += f"{c}: {b}\n"
        await update.message.reply_text(msg, reply_markup=main_menu())
        return MAIN_MENU
    if text == "📊 Расходы по категориям (месяц)":
        year_month = datetime.now().strftime("%Y-%m")
        stats = get_monthly_category_stats(year_month)
        if not stats:
            await update.message.reply_text("📊 В этом месяце расходов нет.", reply_markup=main_menu())
            return MAIN_MENU
        msg = f"📊 Расходы по категориям ({year_month}):\n"
        for cat, cur, total in stats:
            cat_name = cat if cat else "📦 Другое"
            msg += f"{cat_name} — {round(total, 2)} {cur}\n"
        await update.message.reply_text(msg, reply_markup=main_menu())
        return MAIN_MENU
    return STATS_MENU

# ---------- Настройки ----------
async def settings_handler(update: Update, context):
    text = update.message.text

    if text == "⬅️ Назад":
        await update.message.reply_text("Главное меню:", reply_markup=main_menu())
        return MAIN_MENU

    if text == "🛠 Категории":
        await update.message.reply_text(
            "Управление категориями:",
            reply_markup=categories_menu()
        )
        return CATEGORY_MENU

    if text == "🗑 Очистить базу":
        await update.message.reply_text("Вы уверены?", reply_markup=confirm_clear_menu())
        return CONFIRM_CLEAR

    return SETTINGS_MENU

async def confirm_clear(update: Update, context):
    text = update.message.text
    if text == "✅ Да":
        clear_db()
        await update.message.reply_text("База очищена.", reply_markup=main_menu())
    else:
        await update.message.reply_text("Отменено.", reply_markup=main_menu())
    return MAIN_MENU

# ---------- Запуск ----------
init_db()
app = ApplicationBuilder().token(TOKEN).build()

conv = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_handler)],
        ADD_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_menu_handler)],
        CHOOSING_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, choosing_category)],
        CHOOSING_CURRENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, choosing_currency)],
        TYPING_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, typing_amount)],
        HISTORY_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, history_handler)],
        TYPING_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, typing_date)],
        STATS_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, stats_handler)],
        SETTINGS_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, settings_handler)],
        CONFIRM_CLEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_clear)],

        CURRENCY_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, currency_menu_handler)],
        ADD_CURRENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_currency_handler)],
        DELETE_CURRENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_currency_handler)],

        CATEGORY_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, categories_menu_handler)],
        ADD_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_category_handler)],
        DELETE_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_category_handler)],

        CHOOSE_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_delete)],
        CHOOSE_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_edit)],
        EDIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_amount)],
    },
    fallbacks=[CommandHandler("start", start)]
)

app.add_handler(conv)
print("Бот запущен.")
app.run_polling()