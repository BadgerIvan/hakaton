import pytest
pytestmark = pytest.mark.integration

import hashlib
import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from uuid import uuid4

from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.config import Settings
from app.main import create_app
from app.migrate_sqlite import migrate


class MigrationTests(unittest.TestCase):
    def setUp(self):
        url = os.getenv('TEST_DATABASE_URL')
        if not url:
            self.skipTest('Set TEST_DATABASE_URL to a dedicated PostgreSQL database')
        self.admin = create_engine(url)
        schema = 'test_migration_' + uuid4().hex
        with self.admin.begin() as db:
            db.execute(text(f'CREATE SCHEMA "{schema}"'))
        def cleanup():
            with self.admin.begin() as db:
                db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            self.admin.dispose()
        self.addCleanup(cleanup)
        self.url = make_url(url).update_query_dict({'options': f'-csearch_path={schema}'}).render_as_string(hide_password=False)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.source = Path(self.directory.name) / 'auth.db'
        self.user_id, self.token = str(uuid4()), 'legacy-session-cookie'
        self.password_hash = PasswordHasher().hash('test-password-123')
        with sqlite3.connect(self.source) as db:
            db.executescript('''
                CREATE TABLE auth_users (id TEXT PRIMARY KEY, name TEXT, email TEXT UNIQUE, password_hash TEXT, created_at INTEGER);
                CREATE TABLE auth_sessions (token_hash TEXT PRIMARY KEY, user_id TEXT, csrf_token TEXT, expires_at INTEGER);
                CREATE TABLE auth_rate_limits (key TEXT PRIMARY KEY, count INTEGER, expires_at INTEGER);
            ''')
            db.execute('INSERT INTO auth_users VALUES (?, ?, ?, ?, ?)', (self.user_id, 'Вова', 'vova@example.com', self.password_hash, int(time.time())))
            db.execute('INSERT INTO auth_sessions VALUES (?, ?, ?, ?)', (hashlib.sha256(self.token.encode()).hexdigest(), self.user_id, 'legacy-csrf', int(time.time()) + 1000))
            db.execute('INSERT INTO auth_rate_limits VALUES (?, ?, ?)', ('rate-key', 3, int(time.time()) + 1000))

    def test_import_is_idempotent_preserves_password_session_and_rate_limits(self):
        before = self.source.read_bytes()
        expected = {'auth_users': 1, 'auth_sessions': 1, 'auth_rate_limits': 1}
        self.assertEqual(migrate(self.source, self.url, dry_run=True), expected)
        self.assertEqual(migrate(self.source, self.url), expected)
        self.assertEqual(migrate(self.source, self.url), expected)
        self.assertEqual(self.source.read_bytes(), before)
        engine = create_engine(self.url)
        with engine.connect() as db:
            self.assertEqual(db.scalar(text('SELECT password_hash FROM auth_users')), self.password_hash)
            self.assertEqual(db.scalar(text('SELECT count FROM auth_rate_limits')), 3)
        engine.dispose()
        with TestClient(create_app(Settings(database_url=self.url))) as client:
            client.cookies.set('partner_session', self.token)
            self.assertEqual(client.get('/api/v1/auth/me').json()['user']['id'], self.user_id)
            response = client.post('/api/v1/auth/login', json={'email': 'vova@example.com', 'password': 'test-password-123'},
                headers={'X-Requested-With': 'PartnerAgent'})
            self.assertEqual(response.status_code, 200)

    def test_conflict_rolls_back_all_imported_rows(self):
        migrate(self.source, self.url)
        new_id = str(uuid4())
        with sqlite3.connect(self.source) as db:
            db.execute('INSERT INTO auth_users VALUES (?, ?, ?, ?, ?)', (new_id, 'Новый', 'new@example.com', self.password_hash, 100))
            db.execute('UPDATE auth_rate_limits SET count=99')
        with self.assertRaises(ValueError):
            migrate(self.source, self.url)
        engine = create_engine(self.url)
        with engine.connect() as db:
            self.assertEqual(db.scalar(text('SELECT count(*) FROM auth_users')), 1)
            self.assertEqual(db.scalar(text('SELECT count FROM auth_rate_limits')), 3)
        engine.dispose()
