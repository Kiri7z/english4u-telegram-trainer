import os
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('FLASK_SECRET_KEY', 'test-only-flask-secret')
os.environ.setdefault('DB_USER', 'test_user')
os.environ.setdefault('DB_PASSWORD', 'test-only-password')
os.environ.setdefault('DB_NAME', 'test_db')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'my_flask_app'))

from sqlalchemy import create_engine
from werkzeug.security import generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from app import app, db, routes
from app.models import Student, Teacher, Unit, Word
from security_controls.rate_limit import SlidingWindowLimiter


class TokenParser(HTMLParser):
    token = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and attrs.get('name') == 'csrf_token':
            self.token = attrs.get('value')


class WebSecurityTests(unittest.TestCase):
    def setUp(self):
        self.config = {key: app.config.get(key) for key in (
            'TESTING', 'SESSION_COOKIE_SECURE', 'TRUSTED_HOSTS')}
        app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False, TRUSTED_HOSTS=None)
        self.context = app.app_context()
        self.context.push()
        self.original_engine = db.engines[None]
        self.engine = create_engine('sqlite://')
        db.engines[None] = self.engine
        db.create_all()
        db.session.add_all([
            Teacher(teacher_id=1, username='teacher', password=generate_password_hash('test-password')),
            Student(student_id=1, name='Demo Student', token='demo-code'),
            Unit(unit_id=1, unit_name='Demo unit'),
            Word(word_id=1, unit_id=1, word='hello', translation='привет'),
        ])
        db.session.commit()
        db.session.remove()
        self.context.pop()
        self.now = [100.0]
        self.patches = [
            patch.object(routes, 'login_attempts', SlidingWindowLimiter(5, 300, clock=lambda: self.now[0])),
            patch.object(routes, 'login_clients', SlidingWindowLimiter(30, 300, clock=lambda: self.now[0])),
        ]
        for item in self.patches:
            item.start()
        self.client = app.test_client()

    def tearDown(self):
        for item in self.patches:
            item.stop()
        with app.app_context():
            db.session.remove()
            db.engines[None] = self.original_engine
        self.engine.dispose()
        app.config.update(self.config)

    def token(self, path='/login', **kwargs):
        response = self.client.get(path, **kwargs)
        self.assertEqual(response.status_code, 200)
        parser = TokenParser()
        parser.feed(response.get_data(as_text=True))
        self.assertTrue(parser.token)
        return parser.token

    def sign_in(self):
        response = self.client.post('/login', data={
            'csrf_token': self.token(), 'username': 'teacher', 'password': 'test-password'})
        self.assertEqual(response.status_code, 302)

    def test_every_write_route_rejects_missing_and_invalid_csrf(self):
        self.sign_in()
        paths = ('/students', '/words', '/edit_student/1', '/delete_student/1',
                 '/edit_unit/1', '/delete_unit/1', '/logout')
        for path in paths:
            for data in ({}, {'csrf_token': 'invalid'}):
                with self.subTest(path=path, data=data):
                    self.assertEqual(self.client.post(path, data=data).status_code, 400)
        with app.app_context():
            self.assertEqual(db.session.get(Student, 1).name, 'Demo Student')
            self.assertEqual(Unit.query.count(), 1)
        self.assertEqual(self.client.post('/login', data={'username': 'teacher',
                         'password': 'test-password'}).status_code, 400)

    def test_forms_with_valid_csrf_can_create_edit_and_delete(self):
        self.sign_in()
        response = self.client.post('/students', data={'csrf_token': self.token('/students'),
            'name': 'Second demo', 'token': 'second-code'})
        self.assertEqual(response.status_code, 302)
        response = self.client.post('/edit_student/2', data={'csrf_token': self.token('/edit_student/2'),
            'name': 'Edited demo', 'token': 'second-code'})
        self.assertEqual(response.status_code, 302)
        with app.app_context():
            self.assertEqual(db.session.get(Student, 2).name, 'Edited demo')
        response = self.client.post('/delete_student/2', data={
            'csrf_token': self.token('/edit_student/2')})
        self.assertEqual(response.status_code, 302)
        with app.app_context():
            self.assertIsNone(db.session.get(Student, 2))
        response = self.client.post('/words', data={'csrf_token': self.token('/words'),
            'unit_name': 'Second unit', 'words': 'world: мир'})
        self.assertEqual(response.status_code, 302)
        with app.app_context():
            self.assertEqual(Word.query.filter_by(word='world').count(), 1)
        response = self.client.post('/edit_unit/2', data={'csrf_token': self.token('/edit_unit/2'),
            'unit_name': 'Edited unit', 'word_2': 'world', 'translation_2': 'мир'})
        self.assertEqual(response.status_code, 302)
        with app.app_context():
            self.assertEqual(db.session.get(Unit, 2).unit_name, 'Edited unit')

    def test_logout_requires_post_and_valid_csrf(self):
        self.sign_in()
        self.assertEqual(self.client.get('/logout').status_code, 405)
        token = self.token('/')
        self.assertEqual(self.client.post('/logout', data={'csrf_token': token}).status_code, 302)
        self.assertEqual(self.client.get('/students').status_code, 302)

    def test_login_limit_blocks_credentials_then_recovers(self):
        token = self.token()
        for _ in range(5):
            response = self.client.post('/login', data={'csrf_token': token,
                'username': 'teacher', 'password': 'wrong'})
            self.assertEqual(response.status_code, 200)
        response = self.client.post('/login', data={'csrf_token': token,
            'username': 'teacher', 'password': 'test-password'})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers['Retry-After'], '300')
        self.now[0] += 300
        self.assertEqual(self.client.post('/login', data={'csrf_token': token,
            'username': 'teacher', 'password': 'test-password'}).status_code, 302)

    def test_client_limit_prevents_bypass_with_different_usernames(self):
        token = self.token()
        for index in range(30):
            self.assertEqual(self.client.post('/login', data={'csrf_token': token,
                'username': f'unknown-{index}', 'password': 'wrong'}).status_code, 200)
        self.assertEqual(self.client.post('/login', data={'csrf_token': token,
            'username': 'teacher', 'password': 'test-password'}).status_code, 429)

    def test_cookie_flags_and_https_csrf_origin(self):
        app.config['SESSION_COOKIE_SECURE'] = True
        base = 'https://panel.example.com'
        token = self.token(base_url=base)
        other_client = app.test_client()
        cookie = other_client.get('/login', base_url=base).headers['Set-Cookie']
        for flag in ('Secure', 'HttpOnly', 'SameSite=Lax'):
            self.assertIn(flag, cookie)
        payload = {'csrf_token': token, 'username': 'teacher', 'password': 'test-password'}
        self.assertEqual(self.client.post('/login', base_url=base, data=payload,
            headers={'Referer': 'https://unrelated.example/'}).status_code, 400)
        self.assertEqual(self.client.post('/login', base_url=base, data=payload,
            headers={'Referer': base + '/login'}).status_code, 302)

    def test_configured_host_allowlist_rejects_other_hosts(self):
        app.config['TRUSTED_HOSTS'] = ['panel.example.com']
        self.assertEqual(self.client.get('/login', base_url='https://other.example').status_code, 400)
        self.assertEqual(self.client.get('/login', base_url='https://panel.example.com').status_code, 200)

    def test_https_forms_work_through_one_trusted_proxy(self):
        base = 'http://panel.example.com'
        forwarded = {'X-Forwarded-Proto': 'https', 'X-Forwarded-For': '192.0.2.10',
                     'X-Forwarded-Host': 'unrelated.example'}
        with patch.object(app, 'wsgi_app', ProxyFix(app.wsgi_app, x_for=1, x_proto=1,
                          x_host=0, x_port=0, x_prefix=0)):
            token = self.token(base_url=base, headers=forwarded)
            payload = {'csrf_token': token, 'username': 'teacher', 'password': 'test-password'}
            response = self.client.post('/login', base_url=base, data=payload,
                headers={**forwarded, 'Referer': 'https://unrelated.example/login'})
            self.assertEqual(response.status_code, 400)
            response = self.client.post('/login', base_url=base, data=payload,
                headers={**forwarded, 'Referer': 'https://panel.example.com/login'})
            self.assertEqual(response.status_code, 302)


if __name__ == '__main__':
    unittest.main()
