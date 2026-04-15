import logging
import os
import json
import re
from dotenv import load_dotenv
from datetime import date
logging.basicConfig(level=logging.INFO)

import gspread
from google.oauth2.service_account import Credentials

from telegram import (
    ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton,
    InlineKeyboardButton, InlineKeyboardMarkup, Update
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
SHEET_ID = os.getenv("SHEET_ID")

def get_worksheet():
    creds_dict = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(credentials)

    spreadsheet = client.open_by_key(SHEET_ID)
    worksheet = spreadsheet.get_worksheet(0)

    return worksheet

def get_list_sheet_titles():
    creds_dict = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(credentials)

    spreadsheet = client.open_by_key(SHEET_ID)
    worksheets = spreadsheet.worksheets()

    pattern = re.compile(r"^\d{2}\.\d{2}\.\d{4}_\d+$")

    titles = []
    for ws in worksheets:
        if pattern.match(ws.title):
            titles.append(ws.title)

    return titles

def get_products_by_tt(sheet_title, tt_number):
    creds_dict = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(credentials)

    spreadsheet = client.open_by_key(SHEET_ID)
    worksheet = spreadsheet.worksheet(sheet_title)

    rows = worksheet.get_all_values()

    products = []

    for i, row in enumerate(rows[1:], start=2):  # пропускаємо заголовок
        product_name = row[0].strip() if len(row) > 0 else ""
        tt = row[1].strip() if len(row) > 1 else ""
        stock = row[2].strip() if len(row) > 2 else ""

        if tt == tt_number:
            products.append({
                "row_number": i,
                "product_name": product_name,
                "stock": stock,
            })

    return products

def _month_days(year: int, month: int):
    import calendar
    first_weekday, days_count = calendar.monthrange(year, month)
    return first_weekday, days_count


def build_calendar(year: int = None, month: int = None):
    today = date.today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month

    first_wd, days = _month_days(year, month)

    row1 = [
        InlineKeyboardButton("«", callback_data=f"calnav:{year}:{month}:prev"),
        InlineKeyboardButton(f"{month:02d}.{year}", callback_data="noop"),
        InlineKeyboardButton("»", callback_data=f"calnav:{year}:{month}:next"),
    ]

    row2 = [
        InlineKeyboardButton("Пн", callback_data="noop"),
        InlineKeyboardButton("Вт", callback_data="noop"),
        InlineKeyboardButton("Ср", callback_data="noop"),
        InlineKeyboardButton("Чт", callback_data="noop"),
        InlineKeyboardButton("Пт", callback_data="noop"),
        InlineKeyboardButton("Сб", callback_data="noop"),
        InlineKeyboardButton("Нд", callback_data="noop"),
    ]

    buttons = [row1, row2]
    row = []

    pad = first_wd
    for _ in range(pad):
        row.append(InlineKeyboardButton(" ", callback_data="noop"))

    for d in range(1, days + 1):
        row.append(
            InlineKeyboardButton(
                str(d),
                callback_data=f"calpick:{year}-{month:02d}-{d:02d}"
            )
        )
        if len(row) == 7:
            buttons.append(row)
            row = []

    if row:
        while len(row) < 7:
            row.append(InlineKeyboardButton(" ", callback_data="noop"))
        buttons.append(row)

    return InlineKeyboardMarkup(buttons)
    
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("Поділитися номером", request_contact=True)]
    ]
    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await update.message.reply_text(
        "Натисни кнопку нижче, щоб поділитися номером.",
        reply_markup=reply_markup
    )

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"CONTACT UPDATE: {update}")

    if not update.message:
        logging.info("Нема update.message")
        return

    contact = update.message.contact

    if not contact:
        logging.info("Контакт не прийшов")
        await update.message.reply_text("Контакт не отримано. Натисни кнопку ще раз.")
        return

    context.user_data["phone"] = contact.phone_number
    logging.info(f"Телефон отримано: {contact.phone_number}")

    titles = get_list_sheet_titles()

    if not titles:
        await update.message.reply_text("Доступних списків не знайдено.")
        return

    keyboard = []
    for title in titles:
        keyboard.append([title])

    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await update.message.reply_text(
        "Обери список:",
        reply_markup=reply_markup
    )
async def test_sheet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        worksheet = get_worksheet()
        await update.message.reply_text(
            f"Таблиця підключена.\n"
            f"Вкладка: {worksheet.title}\n"
            f"Рядків: {len(worksheet.get_all_values())}"
        )
    except Exception as e:
        await update.message.reply_text(f"Помилка:\n{e}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    titles = get_list_sheet_titles()

    if text in titles:
        context.user_data["selected_sheet"] = text

        await update.message.reply_text(
            f"Список обрано: {text}\nВведи номер ТТ у форматі 006, 054, 123:",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    if context.user_data.get("selected_sheet"):
        if text.isdigit() and len(text) == 3:
            context.user_data["tt_number"] = text

            products = get_products_by_tt(
                context.user_data["selected_sheet"],
                text
            )

            if not products:
                await update.message.reply_text(
                    f"Для ТТ {text} товари не знайдено."
                )
                return

            context.user_data["products"] = products
            context.user_data["current_product_index"] = 0

            first_product = products[0]

            context.user_data["awaiting"] = "term1_date"

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Товар відсутній", callback_data="no_product")]
            ])

            await update.message.reply_text(
                f"Товар: {first_product['product_name']}\n"
                f"Залишок обліковий: {first_product['stock']}\n\n"
                f"Найближчий термін закінчення придатності:",
                reply_markup=InlineKeyboardMarkup(
                    build_calendar().inline_keyboard + keyboard.inline_keyboard
                )
            )
            return

    await update.message.reply_text("Напиши /start")

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
def main():
    if not BOT_TOKEN:
        raise ValueError("Не знайдено BOT_TOKEN")
    if not GOOGLE_SERVICE_ACCOUNT_JSON:
        raise ValueError("Не знайдено GOOGLE_SERVICE_ACCOUNT_JSON")
    if not SHEET_ID:
        raise ValueError("Не знайдено SHEET_ID")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("testsheet", test_sheet))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Бот запущений...")
    app.run_polling()

if __name__ == "__main__":
    main()
