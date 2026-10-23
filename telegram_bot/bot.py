import logging
from telegram.ext import Application
from db_config import required_env
from authorization import start_handler, reset_handler, check_token_handler
from units import units_handler, unit_selection_handler
from words import words_handler, stats_handler, unit_view_handler, back_units_handler, run_game_handler
from game import game_handler, check_answer_handler, stop_game_handler


def build_application():
    # HTTP request logs can contain the Telegram token in the URL.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    application = Application.builder().token(required_env("TELEGRAM_TOKEN")).concurrent_updates(False).build()
    for handler in (
        start_handler, reset_handler, check_token_handler, units_handler,
        unit_selection_handler, words_handler, stats_handler, unit_view_handler, back_units_handler,
        run_game_handler, game_handler, stop_game_handler, check_answer_handler,
    ):
        application.add_handler(handler)
    return application


if __name__ == "__main__":
    build_application().run_polling()
