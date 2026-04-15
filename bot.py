import logging
import os
import json
from dotenv import load_dotenv
logging.basicConfig(level=logging.INFO)

import gspread
from google.oauth2.service_account import Credentials

from telegram import ReplyKeyboardMarkup, KeyboardButton, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
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

    await update.message.reply_text(
        f"Номер отримано: {contact.phone_number}"
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
    await update.message.reply_text("Напиши /start")

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
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Бот запущений...")
    app.run_polling()

if __name__ == "__main__":
    main()
