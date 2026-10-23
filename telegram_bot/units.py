# telegram_bot/units.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CommandHandler, CallbackQueryHandler
from sqlalchemy import and_, case, func
from sqlalchemy.orm import sessionmaker
from models import Unit, Word, Student, Result
from db_config import engine
from game import MASTERED_ANSWERS
from words import show_words

Session = sessionmaker(bind=engine)

async def show_units(update: Update, context: CallbackContext) -> None:
    with Session() as session:
        student = session.query(Student).filter_by(
            telegram_user_id=update.effective_user.id).first()
        if student is not None:
            progress = session.query(
                Unit.unit_id, Unit.unit_name,
                func.count(Word.word_id).label('total'),
                func.sum(case((Result.requests > 0, 1), else_=0)).label('attempted'),
                func.sum(case((and_(
                    Result.answers >= MASTERED_ANSWERS,
                    Result.answers * 3 >= Result.requests * 2,
                ), 1), else_=0)).label('mastered'),
            ).outerjoin(Word, Word.unit_id == Unit.unit_id).outerjoin(Result, and_(
                Result.word_id == Word.word_id,
                Result.unit_id == Unit.unit_id,
                Result.student_id == student.student_id,
            )).group_by(Unit.unit_id, Unit.unit_name).order_by(Unit.unit_id).all()

    if student is None:
        await update.effective_message.reply_text(
            'You are not authorized. Please use /start to log in.')
        return
    if not progress:
        await update.effective_message.reply_text('No units available yet.')
        return

    keyboard = []
    for unit in progress:
        if unit.total and unit.mastered == unit.total:
            marker = '🟢'
        elif unit.attempted:
            marker = '🟡'
        else:
            marker = '⚪'
        label = f'{marker} {unit.unit_name}' + (' (empty)' if not unit.total else '')
        keyboard.append([InlineKeyboardButton(label, callback_data=f'unit_{unit.unit_id}')])
    reply_markup = InlineKeyboardMarkup(keyboard)

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
        shown = await show_words(query, context, unit_id, unit.unit_name, user_id)
        if shown:
            context.user_data['selected_unit'] = unit_id

# Handlers
units_handler = CommandHandler('units', show_units)
unit_selection_handler = CallbackQueryHandler(handle_unit_selection, pattern='^unit_')
