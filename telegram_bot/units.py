# telegram_bot/units.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CommandHandler, CallbackQueryHandler
from sqlalchemy.orm import sessionmaker
from models import Unit
from db_config import engine
from words import show_words

Session = sessionmaker(bind=engine)

async def show_units(update: Update, context: CallbackContext) -> None:
    session = Session()
    units = session.query(Unit).all()
    session.close()

    # Создаем кнопки для каждого Unit
    keyboard = [[InlineKeyboardButton(unit.unit_name, callback_data=f'unit_{unit.unit_id}')] for unit in units]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Используем update.effective_message для отправки сообщения
    await update.effective_message.reply_text('Choose a Unit:', reply_markup=reply_markup)

async def handle_unit_selection(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    # Получаем unit_id из callback_data
    unit_id = int(query.data.split('_')[1])

    # Получаем информацию о юните из базы данных
    session = Session()
    unit = session.query(Unit).filter_by(unit_id=unit_id).first()
    session.close()

    user_id = query.from_user.id  # Получаем user_id безопасно

    # Вызываем show_words и передаем unit_name
    if unit:
        await show_words(query, context, unit_id, unit.unit_name, user_id)

# Handlers
units_handler = CommandHandler('units', show_units)
unit_selection_handler = CallbackQueryHandler(handle_unit_selection, pattern='^unit_')
