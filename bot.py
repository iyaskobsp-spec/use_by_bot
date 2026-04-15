import os
from dotenv import load_dotenv

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
    contact = update.message.contact

    if not contact:
        await update.message.reply_text("Надішли номер кнопкою нижче.")
        return

    context.user_data["phone"] = contact.phone_number

    await update.message.reply_text(
        f"Номер отримано: {contact.phone_number}\n"
        f"Далі тут буде вибір списку."
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Напиши /start"
    )


def main():
    if not BOT_TOKEN:
        raise ValueError("Не знайдено BOT_TOKEN в .env")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Бот запущений...")
    app.run_polling()


if __name__ == "__main__":
    main()
