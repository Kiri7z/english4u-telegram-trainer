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

    def add_practice_words(self, count):
        with self.sessions() as session:
            session.add_all(Word(word_id=3 + i, unit_id=1,
                word=f'word{i}', translation=f'translation{i}') for i in range(count))
            session.commit()

    async def unit_buttons(self):
        await units.show_units(self.update, self.context)
        markup = self.message.reply_text.call_args.kwargs['reply_markup']
        return {row[0].callback_data: row[0].text for row in markup.inline_keyboard}

    async def test_unit_list_shows_complete_started_unstarted_and_empty(self):
        with self.sessions() as session:
            session.add_all([
                Unit(unit_id=2, unit_name='Completed unit'),
                Unit(unit_id=3, unit_name='Unstarted unit'),
                Unit(unit_id=4, unit_name='Empty unit'),
                Word(word_id=3, unit_id=2, word='done', translation='done'),
                Word(word_id=4, unit_id=3, word='new', translation='new'),
                Result(student_id=1, unit_id=2, word_id=3, requests=15, answers=10),
            ])
            session.commit()
        self.assertEqual(await self.unit_buttons(), {
            'unit_1': '🟡 Example unit', 'unit_2': '🟢 Completed unit',
            'unit_3': '⚪ Unstarted unit', 'unit_4': '⚪ Empty unit (empty)',
        })

    async def test_unit_status_uses_exact_mastery_threshold(self):
        with self.sessions() as session:
            session.add(Result(student_id=1, unit_id=1, word_id=2, requests=15, answers=10))
            session.commit()
        for requests, answers, marker in ((15,10,'🟢'), (16,10,'🟡'),
                                          (9,9,'🟡'), (30,20,'🟢')):
            with self.subTest(requests=requests, answers=answers):
                with self.sessions() as session:
                    result = session.query(Result).filter_by(word_id=2).one()
                    result.requests, result.answers = requests, answers
                    session.commit()
                self.assertEqual((await self.unit_buttons())['unit_1'], marker + ' Example unit')

    async def test_incorrect_attempt_starts_unit_but_zero_attempts_do_not(self):
        with self.sessions() as session:
            session.query(Result).delete()
            session.add(Result(student_id=1, unit_id=1, word_id=2, requests=0, answers=0))
            session.commit()
        self.assertEqual((await self.unit_buttons())['unit_1'], '⚪ Example unit')
        with self.sessions() as session:
            session.query(Result).one().requests = 1
            session.commit()
        self.assertEqual((await self.unit_buttons())['unit_1'], '🟡 Example unit')

    async def test_unit_progress_is_personal_to_each_student(self):
        with self.sessions() as session:
            session.add(Student(student_id=2, name='Second example', token='second-code',
                                telegram_user_id=200))
            session.add_all(Result(student_id=2, unit_id=1, word_id=word_id,
                                   requests=10, answers=10) for word_id in (1,2))
            session.commit()
        self.assertEqual((await self.unit_buttons())['unit_1'], '🟡 Example unit')
        self.message.from_user.id = 200
        self.assertEqual((await self.unit_buttons())['unit_1'], '🟢 Example unit')
        self.message.from_user.id = 100
        self.assertEqual((await self.unit_buttons())['unit_1'], '🟡 Example unit')

    async def test_adding_word_changes_completed_unit_to_started(self):
        with self.sessions() as session:
            session.add(Result(student_id=1, unit_id=1, word_id=2, requests=10, answers=10))
            session.commit()
        self.assertEqual((await self.unit_buttons())['unit_1'], '🟢 Example unit')
        self.add_practice_words(1)
        self.assertEqual((await self.unit_buttons())['unit_1'], '🟡 Example unit')

    async def test_unit_list_requires_authorization(self):
        for user_id in (200,100):
            with self.subTest(user_id=user_id):
                self.message.from_user.id = user_id
                if user_id == 100:
                    with self.sessions() as session:
                        session.get(Student,1).telegram_user_id = None
                        session.commit()
                await units.show_units(self.update, self.context)
                self.assertIn('/start', self.message.reply_text.call_args.args[0])
                self.assertNotIn('reply_markup', self.message.reply_text.call_args.kwargs)

    async def test_back_button_shows_personal_unit_status(self):
        self.update.callback_query = SimpleNamespace(answer=AsyncMock())
        await words.back_to_units_callback(self.update, self.context)
        self.update.callback_query.answer.assert_awaited_once()
        markup = self.message.reply_text.call_args.kwargs['reply_markup']
        self.assertEqual(markup.inline_keyboard[0][0].text, '🟡 Example unit')
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, 'unit_1')

    async def test_viewing_unit_status_preserves_game_and_results(self):
        self.add_practice_words(2)
        await game.run_current_game(self.update,self.context)
        state = game.game_state[100]
        question = state['current_word']
        queue = list(state['round_queue'])
        with self.sessions() as session:
            before = [(r.result_id,r.requests,r.answers) for r in session.query(Result)]
        await self.unit_buttons()
        self.assertIs(game.game_state[100],state)
        self.assertIs(state['current_word'],question)
        self.assertEqual(state['round_queue'],queue)
        self.assertEqual(self.context.user_data['selected_unit'],1)
        with self.sessions() as session:
            self.assertEqual([(r.result_id,r.requests,r.answers) for r in session.query(Result)],before)
            self.assertEqual(session.get(Student,1).telegram_user_id,100)

    async def test_unit_list_handles_no_units(self):
        with self.sessions() as session:
            session.query(Result).delete()
            session.query(Word).delete()
            session.query(Unit).delete()
            session.commit()
        await units.show_units(self.update,self.context)
        self.assertEqual(self.message.reply_text.call_args.args[0],'No units available yet.')
        self.assertNotIn('reply_markup',self.message.reply_text.call_args.kwargs)

    async def test_shuffled_rounds_cover_every_remaining_word_once(self):
        self.add_practice_words(9)
        expected = set(range(2, 12))
        shown = []
        with patch.object(game.random, 'shuffle', side_effect=game.random.Random(42).shuffle):
            await game.run_current_game(self.update, self.context)
            for _ in range(30):
                shown.append(game.game_state[100]['current_word'].word_id)
                self.message.text = 'incorrect-test-answer'
                await game.check_answer(self.update, self.context)
        for start in (0, 10, 20):
            self.assertEqual(set(shown[start:start + 10]), expected)
        shown.append(game.game_state[100]['current_word'].word_id)
        self.assertTrue(all(a != b for a, b in zip(shown, shown[1:])))
        with self.sessions() as session:
            results = session.query(Result).filter(Result.word_id.in_(expected)).all()
            self.assertEqual(sum(result.requests for result in results), 30)
            self.assertEqual(sum(result.answers for result in results), 0)
            mastered = session.query(Result).filter_by(word_id=1).one()
            self.assertEqual((mastered.requests, mastered.answers), (15, 10))

    async def test_round_boundary_does_not_repeat_the_previous_word(self):
        self.add_practice_words(1)
        reverse_order = iter((False, True))
        def shuffle(queue):
            queue.sort(key=lambda word: word.word_id, reverse=next(reverse_order))
        shown = []
        with patch.object(game.random, 'shuffle', side_effect=shuffle):
            await game.run_current_game(self.update, self.context)
            shown.append(game.game_state[100]['current_word'].word_id)
            for _ in range(2):
                self.message.text = 'incorrect-test-answer'
                await game.check_answer(self.update, self.context)
                shown.append(game.game_state[100]['current_word'].word_id)
        self.assertEqual(shown, [3, 2, 3])

    async def test_mastered_word_leaves_future_rounds(self):
        self.add_practice_words(1)
        with self.sessions() as session:
            session.add(Result(student_id=1, unit_id=1, word_id=2, requests=9, answers=9))
            session.commit()
        with patch.object(game.random, 'shuffle',
                          side_effect=lambda queue: queue.sort(key=lambda word: -word.word_id)):
            await game.run_current_game(self.update, self.context)
            self.assertEqual(game.game_state[100]['current_word'].word_id, 2)
            self.message.text = 'hello'
            await game.check_answer(self.update, self.context)
            self.assertEqual([word.word_id for word in game.game_state[100]['words']], [3])
            self.assertEqual(game.game_state[100]['current_word'].word_id, 3)
            self.message.text = 'incorrect-test-answer'
            await game.check_answer(self.update, self.context)
            self.assertEqual(game.game_state[100]['current_word'].word_id, 3)
        with self.sessions() as session:
            mastered = session.query(Result).filter_by(word_id=2).one()
            self.assertEqual((mastered.requests, mastered.answers), (10, 10))

    async def test_mastering_last_word_ends_game_and_removes_queue(self):
        with self.sessions() as session:
            session.add(Result(student_id=1, unit_id=1, word_id=2, requests=9, answers=9))
            session.commit()
        await game.run_current_game(self.update, self.context)
        self.message.text = 'hello'
        await game.check_answer(self.update, self.context)
        self.assertNotIn(100, game.game_state)
        self.assertIn('mastered all words', self.message.reply_text.call_args.args[0])

    async def test_single_remaining_word_repeats_with_bounded_queue(self):
        await game.run_current_game(self.update, self.context)
        for _ in range(4):
            self.assertEqual(game.game_state[100]['current_word'].word_id, 2)
            self.assertEqual(game.game_state[100]['round_queue'], [])
            self.message.text = 'incorrect-test-answer'
            await game.check_answer(self.update, self.context)
        with self.sessions() as session:
            result = session.query(Result).filter_by(word_id=2).one()
            self.assertEqual((result.requests, result.answers), (4, 0))

    async def test_new_run_replaces_round_and_preserves_saved_progress(self):
        self.add_practice_words(9)
        await game.run_current_game(self.update, self.context)
        self.message.text = 'incorrect-test-answer'
        await game.check_answer(self.update, self.context)
        previous = game.game_state[100]
        previous_queue = list(previous['round_queue'])
        await game.run_current_game(self.update, self.context)
        current = game.game_state[100]
        self.assertIsNot(current, previous)
        self.assertIsNot(current['round_queue'], previous['round_queue'])
        self.assertEqual(previous['round_queue'], previous_queue)
        self.assertEqual(len(current['round_queue']), 9)
        self.assertEqual({word.word_id for word in current['round_queue']} |
                         {current['current_word'].word_id}, set(range(2, 12)))
        with self.sessions() as session:
            self.assertEqual(sum(result.requests for result in session.query(Result)
                                 .filter(Result.word_id != 1)), 1)

    async def test_round_queues_are_isolated_between_students(self):
        self.add_practice_words(2)
        with self.sessions() as session:
            session.add(Student(student_id=2, name='Second example', token='second-code',
                                telegram_user_id=200))
            session.commit()
        await game.run_current_game(self.update, self.context)
        other_message = SimpleNamespace(reply_text=AsyncMock(), from_user=SimpleNamespace(id=200))
        other_query = SimpleNamespace(message=other_message, from_user=other_message.from_user)
        await game.start_game(other_query, SimpleNamespace(user_data={}), 1)
        other = game.game_state[200]
        other_queue = list(other['round_queue'])
        other_question = other['current_word']
        self.message.text = 'incorrect-test-answer'
        await game.check_answer(self.update, self.context)
        self.assertEqual(other['round_queue'], other_queue)
        self.assertIs(other['current_word'], other_question)
        with self.sessions() as session:
            self.assertEqual(session.query(Result).filter_by(student_id=2).count(), 0)

    async def test_empty_unit_does_not_create_game_or_queue(self):
        with self.sessions() as session:
            session.add(Unit(unit_id=2, unit_name='Empty unit'))
            session.commit()
        self.context.user_data['selected_unit'] = 2
        await game.run_current_game(self.update, self.context)
        self.assertNotIn(100, game.game_state)

    async def test_game_skips_mastered_words_and_records_answers(self):
        await game.start_game(self.query, self.context, 1)
        self.assertEqual(game.game_state[100]["current_word"].word_id, 2)
        await game.check_answer(self.update, self.context)
        with self.sessions() as session:
            result = session.query(Result).filter_by(word_id=2).one()
            self.assertEqual((result.requests, result.answers), (1, 1))

    async def test_words_command_preserves_current_question(self):
        self.add_practice_words(2)
        await game.start_game(self.query, self.context, 1)
        question = game.game_state[100]["current_word"]
        queue = list(game.game_state[100]['round_queue'])
        await words.show_current_words(self.update, self.context)
        self.assertIs(game.game_state[100]["current_word"], question)
        self.assertEqual(game.game_state[100]['round_queue'], queue)
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

    def test_latin_accent_normalization_preserves_other_spelling(self):
        for plain, accented in [('fiance', 'fiancé'), ('fiancee', 'fiance\u0301e'),
                                ('cafe', 'café'), ('resume', 'résumé')]:
            self.assertEqual(game.normalize_answer(plain), game.normalize_answer(accented))
        self.assertNotEqual(game.normalize_answer('fiance'), game.normalize_answer('fiancée'))
        self.assertNotEqual(game.normalize_answer('й'), game.normalize_answer('и'))
        self.assertNotEqual(game.normalize_answer('well-known'), game.normalize_answer('wellknown'))

    async def test_unaccented_answer_records_correct_result(self):
        with self.sessions() as session:
            session.query(Word).filter_by(word_id=2).one().word = 'fiancée'
            session.commit()
        await game.start_game(self.query, self.context, 1)
        self.message.text = 'FIANCEE!'
        await game.check_answer(self.update, self.context)
        with self.sessions() as session:
            result = session.query(Result).filter_by(word_id=2).one()
            self.assertEqual((result.requests, result.answers), (1, 1))
            self.assertEqual(session.get(Word, 2).word, 'fiancée')

    async def test_words_and_stats_show_separate_content(self):
        await words.show_current_words(self.update, self.context)
        vocabulary = self.message.reply_text.call_args.args[0]
        self.assertIn('already: mastered', vocabulary)
        self.assertIn('hello: greeting', vocabulary)
        self.assertNotIn('✅', vocabulary)
        self.assertNotIn('(A-', vocabulary)
        await words.show_current_stats(self.update, self.context)
        statistics = self.message.reply_text.call_args.args[0]
        self.assertIn('already - ✅', statistics)
        self.assertIn('hello', statistics)
        self.assertNotIn(': mastered', statistics)
        self.assertNotIn('greeting', statistics)
        with self.sessions() as session:
            session.add(Result(student_id=1, unit_id=1, word_id=2, requests=4, answers=2))
            session.commit()
        await words.show_current_stats(self.update, self.context)
        self.assertIn('hello - 0.50 (A-2)', self.message.reply_text.call_args.args[0])

    async def test_stats_preserves_game_queue_and_personal_results(self):
        self.add_practice_words(2)
        await game.start_game(self.query, self.context, 1)
        state = game.game_state[100]
        question, queue = state['current_word'], list(state['round_queue'])
        await words.show_current_stats(self.update, self.context)
        self.assertIs(state['current_word'], question)
        self.assertEqual(state['round_queue'], queue)
        self.assertIn('Back to the game', self.message.reply_text.call_args.args[0])
        with self.sessions() as session:
            self.assertEqual(session.query(Result).count(), 1)
        self.message.from_user.id = 200
        await words.show_current_stats(self.update, self.context)
        self.assertIn('not authorized', self.message.reply_text.call_args.args[0])

    async def test_unit_view_buttons_and_callbacks_preserve_active_game(self):
        await game.start_game(self.query, self.context, 1)
        state = game.game_state[100]
        self.update.callback_query = SimpleNamespace(
            answer=AsyncMock(), data='stats_unit_1', message=self.message,
            from_user=self.message.from_user)
        await words.unit_view_callback(self.update, self.context)
        self.assertIs(game.game_state[100], state)
        buttons = self.message.reply_text.call_args.kwargs['reply_markup'].inline_keyboard
        self.assertEqual([[b.text for b in row] for row in buttons],
                         [['📊 Stats'], ['⬅️ Back', '▶️ Run']])
        self.assertEqual([[b.callback_data for b in row] for row in buttons],
                         [['stats_unit_1'], ['back_units', 'run_game_1']])
        self.assertIn('already - ✅', self.message.reply_text.call_args_list[-2].args[0])
        self.update.callback_query.data = 'words_unit_1'
        await words.unit_view_callback(self.update, self.context)
        self.assertIn('already: mastered', self.message.reply_text.call_args_list[-2].args[0])
        self.assertIs(game.game_state[100], state)

    async def test_views_handle_missing_selection_empty_and_deleted_unit(self):
        self.context.user_data.clear()
        await words.show_current_stats(self.update, self.context)
        self.assertIn('/units', self.message.reply_text.call_args.args[0])
        with self.sessions() as session:
            session.add(Unit(unit_id=2, unit_name='Empty'))
            session.commit()
        self.context.user_data['selected_unit'] = 2
        await words.show_current_stats(self.update, self.context)
        self.assertIn('No words', self.message.reply_text.call_args.args[0])
        self.context.user_data['selected_unit'] = 999
        await words.show_current_stats(self.update, self.context)
        self.assertIn('not found', self.message.reply_text.call_args.args[0])

    async def test_stats_do_not_show_another_students_progress(self):
        with self.sessions() as session:
            session.add(Student(student_id=2, name='Other', token='other-code', telegram_user_id=200))
            session.add(Result(student_id=2, unit_id=1, word_id=2, requests=30, answers=20))
            session.commit()
        await words.show_current_stats(self.update, self.context)
        first = self.message.reply_text.call_args.args[0]
        self.assertIn('already - ✅', first)
        self.assertNotIn('hello - ✅', first)
        self.message.from_user.id = 200
        await words.show_current_stats(self.update, self.context)
        second = self.message.reply_text.call_args.args[0]
        self.assertIn('hello - ✅', second)
        self.assertNotIn('already - ✅', second)

    async def test_vocabulary_html_is_escaped(self):
        with self.sessions() as session:
            session.get(Word, 2).word = '<hello>'
            session.get(Word, 2).translation = 'a & b'
            session.commit()
        await words.show_current_words(self.update, self.context)
        self.assertIn('&lt;hello&gt;: a &amp; b', self.message.reply_text.call_args.args[0])

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
