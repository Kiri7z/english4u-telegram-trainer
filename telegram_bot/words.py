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

async def show_words(query, context: CallbackContext, unit_id, unit_name, user_id, show_actions=True) -> bool:
    session = Session()
    student = session.query(Student).filter_by(telegram_user_id=user_id).first()

    if student:
        words = session.query(Word).filter_by(unit_id=unit_id).all()
        if words:
            # Добавляем название юнита перед списком слов
            words_list = [f"📘 <b>{unit_name}</b>"]  # Название юнита в формате с рамкой (используем HTML-форматирование)
            
            for word in words:
                result = session.execute(text(f"""
                    SELECT score, answers, requests FROM results_view
                    WHERE student_id = :student_id AND word_id = :word_id
                """), {'student_id': student.student_id, 'word_id': word.word_id}).fetchone()

                if result and result.score is not None:
                    if is_mastered(result.answers, result.requests):
                        words_list.append(f"{word.word}: {word.translation} - ✅")
                    else:
                        words_list.append(f"{word.word}: {word.translation} - {result.score:.2f} (A-{result.answers})")
                else:
                    words_list.append(f"{word.word}: {word.translation}")
            
            # Отправляем список слов с названием юнита вверху
            await query.message.reply_text('\n'.join(words_list), parse_mode='HTML')
        else:
            await query.message.reply_text('No words found for this unit.')

        if show_actions:
            # Добавляем кнопки Back и Run
            keyboard = [
                [InlineKeyboardButton("Back", callback_data='back_units')],
                [InlineKeyboardButton("Run", callback_data=f'run_game_{unit_id}')]  # Передаем unit_id в callback_data
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text('Choose an action:', reply_markup=reply_markup)

        session.close()
        return True
    else:
        await query.message.reply_text('You are not authorized. Please use /start to log in.')

    session.close()
    return False


async def show_current_words(update: Update, context: CallbackContext) -> None:
    """Show words for the active game without interrupting its current question."""
    from game import game_state

    user_id = update.effective_user.id
    state = game_state.get(user_id)

    if not state:
        await update.effective_message.reply_text(
            "No game is currently running. Choose a unit with /units first."
        )
        return

    session = Session()
    unit = session.query(Unit).filter_by(unit_id=state['unit_id']).first()
    session.close()

    if not unit:
        await update.effective_message.reply_text(
            "The current unit was not found. Choose it again with /units."
        )
        return

    shown = await show_words(
        update,
        context,
        unit.unit_id,
        unit.unit_name,
        user_id,
        show_actions=False,
    )

    current_word = state.get('current_word')
    if shown and current_word:
        await update.effective_message.reply_text(
            f"Back to the game:\nTranslate:\n🖌 {current_word.translation}"
        )

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
back_units_handler = CallbackQueryHandler(back_to_units_callback, pattern='^back_units$')
run_game_handler = CallbackQueryHandler(run_game_callback, pattern='^run_game_')
