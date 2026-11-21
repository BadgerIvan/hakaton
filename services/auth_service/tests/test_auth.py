import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.engine import make_url

from app.config import Settings
from app.database import User, UserSession
from app.main import create_app
from app.migrate import upgrade


class AuthTests(unittest.TestCase):
    def setUp(self):
        url = os.getenv("TEST_DATABASE_URL")
        if not url:
            self.skipTest("Set TEST_DATABASE_URL to a dedicated PostgreSQL database")
        admin = create_engine(url)
        schema = "test_auth_" + uuid4().hex
        with admin.begin() as db:
            db.execute(text(f'CREATE SCHEMA "{schema}"'))
        def cleanup():
            with admin.begin() as db:
                db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin.dispose()
        self.addCleanup(cleanup)
        target = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
        self.settings = Settings(database_url=target.render_as_string(hide_password=False))
        upgrade(self.settings.database_url)
        self.app = create_app(self.settings)
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.headers = {
            "X-Requested-With": "PartnerAgent",
            "Origin": "http://localhost:5173",
        }
        self.account = {
            "name": "Вова",
            "email": "vova@example.com",
            "password": "test-password-123",
        }

    def register(self):
        return self.client.post(
            "/api/v1/auth/register", json=self.account, headers=self.headers
        )

    def test_registration_hash_cookie_and_current_user(self):
        response = self.register()
        self.assertEqual(response.status_code, 201, response.text)
        self.assertIn("httponly", response.headers["set-cookie"].lower())
        self.assertIn("samesite=lax", response.headers["set-cookie"].lower())
        self.assertEqual(
            self.client.get("/api/v1/auth/me").json()["user"]["name"], "Вова"
        )
        with self.app.state.sessions() as database:
            user = database.scalar(select(User))
            self.assertTrue(user.password_hash.startswith("$argon2id$"))
            self.assertNotEqual(user.password_hash, self.account["password"])
            session = database.scalar(select(UserSession))
            self.assertNotEqual(
                session.token_hash, self.client.cookies.get("partner_session")
            )
        self.assertNotIn("password_hash", response.text)

    def test_duplicate_case_insensitive_email_and_concurrent_registration(self):
        def submit(_):
            return self.client.post(
                "/api/v1/auth/register", json=self.account, headers=self.headers
            ).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = sorted(pool.map(submit, range(2)))
        self.assertEqual(statuses, [201, 409])
        duplicate = self.client.post(
            "/api/v1/auth/register",
            json={**self.account, "email": "VOVA@EXAMPLE.COM"},
            headers=self.headers,
        )
        self.assertEqual(duplicate.status_code, 409)

    def test_invalid_credentials_and_cookie_forgery(self):
        self.register()
        for email in [self.account["email"], "unknown@example.com"]:
            response = self.client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "wrong-password"},
                headers=self.headers,
            )
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json()["detail"], "Неверная почта или пароль")
        self.client.cookies.clear()
        self.client.cookies.set("partner_session", "forged-token")
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)

    def test_csrf_origin_and_logout_revoke_the_server_session(self):
        session = self.register().json()
        self.assertEqual(
            self.client.post("/api/v1/auth/logout", headers=self.headers).status_code,
            403,
        )
        foreign = {
            **self.headers,
            "Origin": "https://attacker.example",
            "X-CSRF-Token": session["csrf_token"],
        }
        self.assertEqual(
            self.client.post("/api/v1/auth/logout", headers=foreign).status_code, 403
        )
        malformed = [
            (b"X-Requested-With", b"PartnerAgent"),
            (b"Origin", b"http://localhost:5173"),
            (b"X-CSRF-Token", bytes([233])),
        ]
        self.assertEqual(
            self.client.post("/api/v1/auth/logout", headers=malformed).status_code, 403
        )
        token = self.client.cookies.get("partner_session")
        response = self.client.post(
            "/api/v1/auth/logout",
            headers={**self.headers, "X-CSRF-Token": session["csrf_token"]},
        )
        self.assertEqual(response.status_code, 204)
        self.client.cookies.set("partner_session", token)
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)
        self.assertEqual(
            self.client.post("/api/v1/auth/login", json=self.account).status_code, 403
        )

    def test_expiry_and_login_session_rotation(self):
        self.register()
        old_token = self.client.cookies.get("partner_session")
        logged_in = self.client.post(
            "/api/v1/auth/login", json=self.account, headers=self.headers
        )
        self.assertEqual(logged_in.status_code, 200)
        new_token = self.client.cookies.get("partner_session")
        self.assertNotEqual(old_token, new_token)
        self.client.cookies.clear()
        self.client.cookies.set("partner_session", old_token)
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)
        self.client.cookies.set("partner_session", new_token)
        with self.app.state.sessions() as database:
            database.execute(
                update(UserSession).values(expires_at=int(time.time()) - 1)
            )
            database.commit()
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)

    def test_user_and_session_survive_application_restart(self):
        self.register()
        cookie = self.client.cookies.get("partner_session")
        with TestClient(create_app(self.settings)) as restarted:
            restarted.cookies.set("partner_session", cookie)
            response = restarted.get("/api/v1/auth/me")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["user"]["email"], self.account["email"])

    def test_rate_limit_is_persistent(self):
        limited = replace(self.settings, login_email_limit=2)
        with TestClient(create_app(limited)) as client:
            for _ in range(2):
                response = client.post(
                    "/api/v1/auth/login", json=self.account, headers=self.headers
                )
                self.assertEqual(response.status_code, 401)
        with TestClient(create_app(limited)) as restarted:
            response = restarted.post(
                "/api/v1/auth/login", json=self.account, headers=self.headers
            )
            self.assertEqual(response.status_code, 429)
            self.assertIn("retry-after", response.headers)


if __name__ == "__main__":
    unittest.main()
