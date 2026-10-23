# telegram_bot/words.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CommandHandler, CallbackQueryHandler
from sqlalchemy.orm import sessionmaker
from models import Unit, Word, Student
from db_config import engine
from sqlalchemy import text

Session = sessionmaker(bind=engine)

MASTERED_ANSWERS = 10


def is_mastered(answers, requests):
    return answers >= MASTERED_ANSWERS and answers * 3 >= requests * 2

def format_stats(answers, requests):
    """Present accuracy separately from the unchanged mastery rule."""
    if not requests:
        return 'No attempts'
    if is_mastered(answers, requests):
        marker = '✅'
    elif answers * 2 < requests:
        marker = '🟥'
    elif answers * 4 < requests * 3:
        marker = '🟨🟨'
    else:
        marker = '🟩🟩🟩'
    percent = round(answers * 100 / requests)
    return f'{answers}/{requests} · {marker} · {percent}%'


async def show_words(query, context: CallbackContext, unit_id, unit_name, user_id,
                     show_actions=True, stats=False) -> bool:
    from html import escape

    with Session() as session:
        student = session.query(Student).filter_by(telegram_user_id=user_id).first()
        lines = []
        if student:
            vocabulary = session.query(Word).filter_by(unit_id=unit_id).order_by(Word.word_id).all()
            lines = [f"📘 <b>{escape(unit_name)}</b>"]
            for word in vocabulary:
                if stats:
                    result = session.execute(text("""
                        SELECT answers, requests FROM results_view
                        WHERE student_id = :student_id AND word_id = :word_id
                    """), {'student_id': student.student_id,
                           'word_id': word.word_id}).fetchone()
                    summary = format_stats(result.answers, result.requests) if result else 'No attempts'
                    lines.append(f"{escape(word.word)} — {summary}")
                else:
                    lines.append(f"{escape(word.word)}: {escape(word.translation)}")

    if student is None:
        await query.message.reply_text('You are not authorized. Please use /start to log in.')
        return False
    if vocabulary:
        await query.message.reply_text('\n'.join(lines), parse_mode='HTML')
    else:
        await query.message.reply_text('No words found for this unit.')
    if show_actions:
        keyboard = [
            [InlineKeyboardButton('📊 Stats', callback_data=f'stats_unit_{unit_id}')],
            [InlineKeyboardButton('⬅️ Back', callback_data='back_units'),
             InlineKeyboardButton('▶️ Run', callback_data=f'run_game_{unit_id}')],
        ]
        await query.message.reply_text('Choose an action:',
                                       reply_markup=InlineKeyboardMarkup(keyboard))
    return True


async def show_current_view(update: Update, context: CallbackContext, stats=False) -> None:
    """Show the active or selected unit, preserving the current question and queue."""
    from game import game_state
    from types import SimpleNamespace

    user_id = update.effective_user.id
    state = game_state.get(user_id)
    unit_id = state['unit_id'] if state else context.user_data.get('selected_unit')
    if unit_id is None:
        await update.effective_message.reply_text('Choose a unit with /units first.')
        return
    with Session() as session:
        unit = session.query(Unit).filter_by(unit_id=unit_id).first()
    if unit is None:
        await update.effective_message.reply_text(
            'The current unit was not found. Choose it again with /units.')
        return
    shown = await show_words(
        SimpleNamespace(message=update.effective_message), context,
        unit.unit_id, unit.unit_name, user_id, show_actions=False, stats=stats)
    current_word = state.get('current_word') if state else None
    if shown and current_word:
        await update.effective_message.reply_text(
            f"Back to the game:\nTranslate:\n🖌 {current_word.translation}")


async def show_current_words(update: Update, context: CallbackContext) -> None:
    await show_current_view(update, context)


async def show_current_stats(update: Update, context: CallbackContext) -> None:
    await show_current_view(update, context, stats=True)


async def unit_view_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    unit_id = int(query.data.rsplit('_', 1)[1])
    with Session() as session:
        unit = session.query(Unit).filter_by(unit_id=unit_id).first()
    if unit is None:
        await query.message.reply_text('Unit not found. Choose a unit with /units.')
        return
    shown = await show_words(query, context, unit.unit_id, unit.unit_name,
                             query.from_user.id, stats=query.data.startswith('stats_'))
    if shown:
        context.user_data['selected_unit'] = unit_id


# Обработчик для кнопки "Back"
async def back_to_units_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    # Вызываем функцию show_units напрямую
    from units import show_units  # Импортируем функцию show_units
    await show_units(update, context)  # Передаем update и context

# Обработчик для кнопки "Run"
async def run_game_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    # Извлекаем unit_id из callback_data
    unit_id = int(query.data.split('_')[-1])
    context.user_data['selected_unit'] = unit_id

    # Вызываем функцию start_game и передаем unit_id
    from game import start_game  # Импортируем функцию start_game
    await start_game(query, context, unit_id)  # Передаем query вместо update

# Handlers
words_handler = CommandHandler('words', show_current_words)
stats_handler = CommandHandler('stats', show_current_stats)
unit_view_handler = CallbackQueryHandler(unit_view_callback, pattern=r'^(words|stats)_unit_[0-9]+$')
back_units_handler = CallbackQueryHandler(back_to_units_callback, pattern='^back_units$')
run_game_handler = CallbackQueryHandler(run_game_callback, pattern='^run_game_')
