# telegram_bot/game.py

from telegram import Update
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, filters
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text  # Импортируем text для выполнения сырых SQL-запросов
from models import Word, Result, Student, Unit
from db_config import engine
import random
import string  # Для работы с пунктуацией

Session = sessionmaker(bind=engine)

MASTERED_ANSWERS = 10


def is_mastered(answers, requests):
    """A word is mastered after 10 correct answers with at least 2/3 accuracy."""
    return answers >= MASTERED_ANSWERS and answers * 3 >= requests * 2

# Глобальный словарь для хранения состояния игры пользователей
game_state = {}

# Пользовательский фильтр для пользователей в игре
class InGameFilter(filters.MessageFilter):
    def filter(self, message):
        user_id = message.from_user.id
        return user_id in game_state

in_game_filter = InGameFilter()

async def start_game(query, context: CallbackContext, unit_id) -> None:
    user_id = query.from_user.id
    session = Session()

    # Получаем студента из БД
    student = session.query(Student).filter_by(telegram_user_id=user_id).first()
    if not student:
        await query.message.reply_text("You are not authorized. Please use /start to log in.")
        session.close()
        return

    # Получаем word_id, которые нужно исключить, из представления results_view
    exclude_word_ids = session.execute(text("""
        SELECT word_id FROM results
        WHERE student_id = :student_id
          AND answers >= :mastered_answers
          AND answers * 3 >= requests * 2
    """), {
        'student_id': student.student_id,
        'mastered_answers': MASTERED_ANSWERS
    }).fetchall()

    # Преобразуем результат в список word_id
    exclude_word_ids = [row.word_id for row in exclude_word_ids]

    # Отладка: выводим исключаемые word_id
    print("Excluded word IDs:", exclude_word_ids)

    # Получаем все слова для указанного юнита, исключая освоенные слова
    words = session.query(Word).filter(
        Word.unit_id == unit_id,
        ~Word.word_id.in_(exclude_word_ids)
    ).all()

    # Отладка: выводим оставшиеся слова для практики
    print("Words to practice:", [word.word for word in words])

    if not words:
        await query.message.reply_text("No words found for this unit that need practice. You have mastered all words!")
        session.close()
        return

    # Инициализируем состояние игры
    game_state[user_id] = {
        'unit_id': unit_id,
        'words': words,
        'current_word': None
    }

    # Запускаем игру
    await ask_next_word(query, context)

    session.close()

async def ask_next_word(query, context: CallbackContext) -> None:
    user_id = query.from_user.id

    if user_id not in game_state:
        await query.message.reply_text("Game not started. Use /run to start.")
        return

    state = game_state[user_id]
    words = state['words']

    if not words:
        await query.message.reply_text("No more words to practice. You can /stop the game.")
        return

    # Выбираем случайное слово
    word = random.choice(words)
    state['current_word'] = word

    # Спрашиваем пользователя
    await query.message.reply_text(f"Translate:\n🖌 {word.translation}")

async def check_answer(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    session = Session()

    if user_id not in game_state:
        # Пользователь не находится в игре, игнорируем сообщение
        session.close()
        return

    state = game_state[user_id]
    current_word = state['current_word']
    student = session.query(Student).filter_by(telegram_user_id=user_id).first()

    # Форматируем ответ пользователя и слово из БД для сравнения
    user_answer = update.message.text.strip().lower()
    correct_answer = current_word.word.strip().lower()

    # Создаем набор знаков препинания без дефиса
    punctuation_without_hyphen = string.punctuation.replace('-', '')

    # Удаляем знаки препинания (кроме дефиса) из обоих ответов
    translator = str.maketrans('', '', punctuation_without_hyphen)
    user_answer_clean = user_answer.translate(translator)
    correct_answer_clean = correct_answer.translate(translator)

    # Увеличиваем requests в таблице Result
    result = session.query(Result).filter_by(student_id=student.student_id, word_id=current_word.word_id).first()
    if not result:
        # Если запись отсутствует, создаем новую
        result = Result(student_id=student.student_id, unit_id=current_word.unit_id, word_id=current_word.word_id, requests=1, answers=0)
        session.add(result)
    else:
        result.requests += 1

    # Проверяем ответ
    if user_answer_clean == correct_answer_clean:
        # Если ответ верный
        result.answers += 1

        # Проверяем, нужно ли исключить слово из игры
        if is_mastered(result.answers, result.requests):
            # Удаляем слово из списка слов для текущего пользователя
            state['words'] = [w for w in state['words'] if w.word_id != current_word.word_id]
            # Поздравляем пользователя
            await update.message.reply_text(f"🎉 Great job! You've mastered '{current_word.word}'!")
    else:
        # Если ответ неверный
        await update.message.reply_text(f"Correct word is: {current_word.word}")

    # Сохраняем изменения в БД
    session.commit()

    # Проверяем, остались ли слова для практики
    if not state['words']:
        await update.message.reply_text("No more words to practice. You have mastered all words in this unit!")
        del game_state[user_id]
    else:
        # Продолжаем игру
        # Создаем фиктивный объект query для передачи в ask_next_word
        class DummyQuery:
            def __init__(self, message):
                self.message = message
                self.from_user = message.from_user

        dummy_query = DummyQuery(update.message)
        await ask_next_word(dummy_query, context)

    session.close()

async def stop_game(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    if user_id in game_state:
        # Получаем unit_id перед удалением game_state
        unit_id = game_state[user_id]['unit_id']
        del game_state[user_id]
        await update.message.reply_text("🔴 Game stopped.")

        # Показываем слова для юнита
        from words import show_words
        from units import Session  # Импортируем сессию для запроса имени юнита

        session = Session()
        unit = session.query(Unit).filter_by(unit_id=unit_id).first()
        session.close()

        if unit:
            # Создаем фиктивный объект query
            class DummyQuery:
                def __init__(self, message):
                    self.message = message
                    self.from_user = message.from_user

            dummy_query = DummyQuery(update.message)
            # Передаем unit_name в show_words
            await show_words(dummy_query, context, unit_id, unit.unit_name, user_id)
    else:
        await update.message.reply_text("No game is currently running.")

# Handlers
async def run_current_game(update: Update, context: CallbackContext) -> None:
    from types import SimpleNamespace
    unit_id = context.user_data.get("selected_unit")
    if unit_id is None:
        await update.effective_message.reply_text("Choose a unit with /units first.")
        return
    query = SimpleNamespace(message=update.effective_message, from_user=update.effective_user)
    await start_game(query, context, unit_id)


game_handler = CommandHandler('run', run_current_game)
check_answer_handler = MessageHandler(filters.TEXT & ~filters.COMMAND & in_game_filter, check_answer)
stop_game_handler = CommandHandler('stop', stop_game)
