# telegram_bot/authorization.py

from telegram import Update
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, filters
from sqlalchemy.orm import sessionmaker
from models import Student
from db_config import engine
from security_controls.rate_limit import SlidingWindowLimiter
import time

Session = sessionmaker(bind=engine)

# Глобальный набор для отслеживания пользователей, ожидающих ввода токена
awaiting_token_users = set()
token_attempts = SlidingWindowLimiter(limit=5, window_seconds=300)

async def start_authorization(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    session = Session()

    student = session.query(Student).filter_by(telegram_user_id=user_id).first()
    if student:
        await update.message.reply_text(
            f"Hello {student.name}!\n\n"
            "Available commands:\n"
            "/start -> Show this guide or authorize\n"
            "/units -> Choose a unit\n"
            "/words -> Show words\n"
            "/stats -> Show word stats\n"
            "/run -> Start the game\n"
            "/stop -> Stop the game\n"
            "/reset -> Sign out and enter a new token\n"
        )
    else:
        await update.message.reply_text(
            "Welcome! I can help you learn English words.\n\n"
            "Available commands:\n"
            "/start -> Show this guide or authorize\n"
            "/units -> Choose a unit\n"
            "/words -> Show words\n"
            "/stats -> Show word stats\n"
            "/run -> Start the game\n"
            "/stop -> Stop the game\n"
            "/reset -> Sign out and enter a new token\n"
            "Enter your token:"
        )
        # Устанавливаем флаг ожидания токена
        context.user_data['awaiting_token'] = True
        awaiting_token_users.add(user_id)

    session.close()

async def check_token(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id

    # Проверяем, ожидаем ли мы ввода токена от пользователя
    if not context.user_data.get('awaiting_token'):
        # Если нет, игнорируем это сообщение
        return

    wait = token_attempts.consume(user_id)
    if wait:
        now = time.monotonic()
        if now >= context.user_data.get('token_limit_notice_until', 0):
            await update.message.reply_text(
                f'Too many authorization attempts. Please try again in {wait} seconds.'
            )
            context.user_data['token_limit_notice_until'] = now + wait
        return

    user_token = update.message.text
    session = Session()

    student = session.query(Student).filter_by(token=user_token).first()
    if student and student.telegram_user_id in (None, user_id):
        token_attempts.reset(user_id)
        context.user_data.pop('token_limit_notice_until', None)
        student.telegram_user_id = user_id
        session.commit()
        await update.message.reply_text(f"Hello {student.name}! You are now authorized.")
        # Сбрасываем флаг ожидания токена
        context.user_data['awaiting_token'] = False
        awaiting_token_users.discard(user_id)
    else:
        await update.message.reply_text("Token not found. Please try again.")

    session.close()

async def reset_authorization(update: Update, context: CallbackContext) -> None:
    from game import game_state

    user_id = update.message.from_user.id
    game_state.pop(user_id, None)
    context.user_data.pop('selected_unit', None)

    with Session() as session:
        student = session.query(Student).filter_by(telegram_user_id=user_id).first()
        if student:
            student.telegram_user_id = None
            session.commit()
            message = "Token reset. Please enter a new token."
        else:
            message = "You have not logged in yet. Please enter a token."

    context.user_data['awaiting_token'] = True
    awaiting_token_users.add(user_id)
    await update.message.reply_text(message)

# Пользовательский фильтр для ожидания токена
class AwaitingTokenFilter(filters.MessageFilter):
    def filter(self, message):
        user_id = message.from_user.id
        return user_id in awaiting_token_users

awaiting_token_filter = AwaitingTokenFilter()

# Обработчики команд
start_handler = CommandHandler('start', start_authorization)
reset_handler = CommandHandler('reset', reset_authorization)
check_token_handler = MessageHandler(filters.TEXT & ~filters.COMMAND & awaiting_token_filter, check_token)
