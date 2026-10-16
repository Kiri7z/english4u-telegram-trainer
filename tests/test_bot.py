import inspect
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

os.environ.setdefault("DB_USER", "test_user")
os.environ.setdefault("DB_PASSWORD", "test-only-password")
os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("TELEGRAM_TOKEN", "123456:unit-test-placeholder")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "telegram_bot"))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import authorization
import bot
import game
import units
import words
from models import Base, Student, Unit, Word, Result
from security_controls.rate_limit import SlidingWindowLimiter


class BotTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            connection.execute(text("""CREATE VIEW results_view AS
                SELECT *, CASE WHEN requests=0 THEN 0
                ELSE ROUND(CAST(answers AS REAL)/requests,2) END AS score
                FROM results"""))
        self.sessions = sessionmaker(bind=self.engine)
        self.patches = [patch.object(module, "Session", self.sessions)
                        for module in (authorization, game, units, words)]
        self.now = [100.0]
        self.patches.append(patch.object(authorization, 'token_attempts',
            SlidingWindowLimiter(5, 300, clock=lambda: self.now[0])))
        for item in self.patches:
            item.start()
        with self.sessions() as session:
            session.add_all([
                Student(student_id=1, name="Example", token="test-code", telegram_user_id=100),
                Unit(unit_id=1, unit_name="Example unit"),
                Word(word_id=1, unit_id=1, word="already", translation="mastered"),
                Word(word_id=2, unit_id=1, word="hello", translation="greeting"),
                Result(student_id=1, unit_id=1, word_id=1, requests=15, answers=10),
            ])
            session.commit()
        game.game_state.clear()
        authorization.awaiting_token_users.clear()
        self.message = SimpleNamespace(reply_text=AsyncMock(), text="hello!",
                                       from_user=SimpleNamespace(id=100))
        self.update = SimpleNamespace(message=self.message, effective_message=self.message,
                                      effective_user=self.message.from_user)
        self.query = SimpleNamespace(message=self.message, from_user=self.message.from_user)
        self.context = SimpleNamespace(user_data={"selected_unit": 1})

    def tearDown(self):
        for item in self.patches:
            item.stop()
        self.engine.dispose()

    async def test_game_skips_mastered_words_and_records_answers(self):
        await game.start_game(self.query, self.context, 1)
        self.assertEqual(game.game_state[100]["current_word"].word_id, 2)
        await game.check_answer(self.update, self.context)
        with self.sessions() as session:
            result = session.query(Result).filter_by(word_id=2).one()
            self.assertEqual((result.requests, result.answers), (1, 1))

    async def test_words_command_preserves_current_question(self):
        await game.start_game(self.query, self.context, 1)
        question = game.game_state[100]["current_word"]
        await words.show_current_words(self.update, self.context)
        self.assertIs(game.game_state[100]["current_word"], question)
        self.assertIn("Back to the game", self.message.reply_text.call_args.args[0])

    async def test_known_code_cannot_rebind_another_telegram_account(self):
        self.message.from_user.id = 200
        self.message.text = "test-code"
        self.context.user_data["awaiting_token"] = True
        await authorization.check_token(self.update, self.context)
        with self.sessions() as session:
            self.assertEqual(session.get(Student, 1).telegram_user_id, 100)

    async def test_unbound_code_can_authorize(self):
        with self.sessions() as session:
            session.get(Student, 1).telegram_user_id = None
            session.commit()
        self.context.user_data["awaiting_token"] = True
        self.message.text = "test-code"
        await authorization.check_token(self.update, self.context)
        with self.sessions() as session:
            self.assertEqual(session.get(Student, 1).telegram_user_id, 100)
        self.assertFalse(self.context.user_data["awaiting_token"])

    async def test_new_sixteen_character_code_preserves_existing_code_and_binding(self):
        code = '00010f107f80feff'
        with self.sessions() as session:
            session.add(Student(student_id=2, name='New example', token=code))
            session.commit()
        self.message.from_user.id = 200
        self.message.text = code
        self.context.user_data['awaiting_token'] = True
        await authorization.check_token(self.update, self.context)
        with self.sessions() as session:
            existing = session.get(Student, 1)
            self.assertEqual((existing.token, existing.telegram_user_id), ('test-code', 100))
            self.assertEqual(session.get(Student, 2).telegram_user_id, 200)
            result = session.query(Result).filter_by(student_id=1).one()
            self.assertEqual((result.requests, result.answers), (15, 10))

    async def test_token_attempts_are_limited_and_recover(self):
        with self.sessions() as session:
            session.get(Student, 1).telegram_user_id = None
            session.commit()
        self.context.user_data['awaiting_token'] = True
        self.message.text = 'wrong-code'
        for _ in range(5):
            await authorization.check_token(self.update, self.context)
        self.message.text = 'test-code'
        await authorization.check_token(self.update, self.context)
        self.assertIn('Too many authorization attempts', self.message.reply_text.call_args.args[0])
        with self.sessions() as session:
            self.assertIsNone(session.get(Student, 1).telegram_user_id)
        # /start and /reset cannot erase the attempt limit.
        await authorization.reset_authorization(self.update, self.context)
        await authorization.start_authorization(self.update, self.context)
        await authorization.check_token(self.update, self.context)
        with self.sessions() as session:
            self.assertIsNone(session.get(Student, 1).telegram_user_id)
        self.now[0] += 300
        await authorization.check_token(self.update, self.context)
        with self.sessions() as session:
            self.assertEqual(session.get(Student, 1).telegram_user_id, 100)

    async def test_run_command_and_stop(self):
        await game.run_current_game(self.update, self.context)
        self.assertIn(100, game.game_state)
        await game.stop_game(self.update, self.context)
        self.assertNotIn(100, game.game_state)

    async def test_reset_ends_game_and_preserves_student_and_results(self):
        await game.run_current_game(self.update, self.context)
        other_game = {'unit_id': 2}
        game.game_state[200] = other_game
        await authorization.reset_authorization(self.update, self.context)
        self.assertNotIn(100, game.game_state)
        self.assertIs(game.game_state[200], other_game)
        self.assertNotIn('selected_unit', self.context.user_data)
        self.assertTrue(self.context.user_data['awaiting_token'])
        self.assertIn(100, authorization.awaiting_token_users)
        self.assertFalse(game.in_game_filter.filter(self.message))
        with self.sessions() as session:
            student = session.get(Student, 1)
            self.assertEqual((student.name, student.token), ('Example', 'test-code'))
            self.assertIsNone(student.telegram_user_id)
            result = session.query(Result).one()
            self.assertEqual((result.requests, result.answers), (15, 10))
            self.assertEqual(session.query(Student).count(), 1)

    async def test_reset_clears_stale_game_for_unbound_user(self):
        await game.run_current_game(self.update, self.context)
        with self.sessions() as session:
            session.get(Student, 1).telegram_user_id = None
            session.commit()
        await authorization.reset_authorization(self.update, self.context)
        self.assertNotIn(100, game.game_state)
        self.assertNotIn('selected_unit', self.context.user_data)
        self.assertTrue(self.context.user_data['awaiting_token'])
        self.assertIn(100, authorization.awaiting_token_users)
        with self.sessions() as session:
            self.assertEqual(session.query(Student).count(), 1)
            self.assertEqual(session.query(Result).count(), 1)

    async def test_answer_after_binding_removed_stops_game_without_writes(self):
        await game.run_current_game(self.update, self.context)
        with self.sessions() as session:
            session.get(Student, 1).telegram_user_id = None
            session.commit()
        await game.check_answer(self.update, self.context)
        self.assertNotIn(100, game.game_state)
        self.assertNotIn('selected_unit', self.context.user_data)
        self.assertIn('/start', self.message.reply_text.call_args.args[0])
        with self.sessions() as session:
            result = session.query(Result).one()
            self.assertEqual((result.requests, result.answers), (15, 10))
        self.message.reply_text.reset_mock()
        await game.check_answer(self.update, self.context)
        self.message.reply_text.assert_not_awaited()

    async def test_answer_after_student_deleted_stops_game(self):
        await game.run_current_game(self.update, self.context)
        with self.sessions() as session:
            session.query(Result).filter_by(student_id=1).delete()
            session.delete(session.get(Student, 1))
            session.commit()
        await game.check_answer(self.update, self.context)
        self.assertNotIn(100, game.game_state)
        self.assertNotIn('selected_unit', self.context.user_data)
        self.assertIn('/start', self.message.reply_text.call_args.args[0])
        with self.sessions() as session:
            self.assertEqual(session.query(Result).count(), 0)

    async def test_authorizing_another_student_does_not_resume_previous_game(self):
        with self.sessions() as session:
            session.add(Student(student_id=2, name='Second example', token='second-test-code'))
            session.commit()
        await game.run_current_game(self.update, self.context)
        await authorization.reset_authorization(self.update, self.context)
        self.message.text = 'second-test-code'
        await authorization.check_token(self.update, self.context)
        self.assertFalse(self.context.user_data['awaiting_token'])
        self.assertNotIn(100, game.game_state)
        self.assertNotIn('selected_unit', self.context.user_data)
        self.message.reply_text.reset_mock()
        self.message.text = 'hello'
        await game.check_answer(self.update, self.context)
        self.message.reply_text.assert_not_awaited()
        with self.sessions() as session:
            self.assertIsNone(session.get(Student, 1).telegram_user_id)
            self.assertEqual(session.get(Student, 2).telegram_user_id, 100)
            self.assertEqual(session.query(Result).filter_by(student_id=2).count(), 0)
            self.assertEqual(session.query(Result).filter_by(student_id=1).one().answers, 10)

    async def test_reset_of_bound_student_keeps_authorization_attempt_limit(self):
        await game.run_current_game(self.update, self.context)
        for _ in range(5):
            self.assertEqual(authorization.token_attempts.consume(100), 0)
        await authorization.reset_authorization(self.update, self.context)
        self.message.text = 'test-code'
        await authorization.check_token(self.update, self.context)
        self.assertIn('Too many authorization attempts', self.message.reply_text.call_args.args[0])
        with self.sessions() as session:
            self.assertIsNone(session.get(Student, 1).telegram_user_id)
        self.now[0] += 300
        await authorization.check_token(self.update, self.context)
        with self.sessions() as session:
            self.assertEqual(session.get(Student, 1).telegram_user_id, 100)
        self.assertNotIn('selected_unit', self.context.user_data)
        await game.run_current_game(self.update, self.context)
        self.assertNotIn(100, game.game_state)
        self.context.user_data['selected_unit'] = 1
        await game.run_current_game(self.update, self.context)
        self.assertIn(100, game.game_state)

    def test_all_registered_callbacks_are_async(self):
        application = bot.build_application()
        for handlers in application.handlers.values():
            for handler in handlers:
                self.assertTrue(inspect.iscoroutinefunction(handler.callback))

    def test_mastery_boundary_preserved(self):
        self.assertTrue(game.is_mastered(10, 15))
        self.assertFalse(game.is_mastered(10, 16))
        self.assertFalse(game.is_mastered(9, 9))


if __name__ == "__main__":
    unittest.main()
