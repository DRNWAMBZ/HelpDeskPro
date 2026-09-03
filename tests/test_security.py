"""Safe security regression checks for HelpDesk Pro.

These tests exercise application defences without attacking external systems.
Run with: python -m unittest tests.test_security
"""

import os
import tempfile
import unittest
from pathlib import Path


TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / "helpdesk-pro-security.db"
if TEST_DATABASE_PATH.exists():
    TEST_DATABASE_PATH.unlink()

os.environ["APP_ENV"] = "testing"
os.environ["SECRET_KEY"] = "security-test-secret"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"

from app import KnowledgeArticle, User, app, db  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402


class HelpDeskSecurityTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        with app.app_context():
            db.drop_all()
            db.create_all()
            self.user = User(
                username="Security Staff",
                email="security-staff@example.test",
                password=generate_password_hash("Password123!"),
            )
            self.admin = User(
                username="Security Admin",
                email="security-admin@example.test",
                password=generate_password_hash("Password123!"),
                is_admin=True,
            )
            db.session.add_all([self.user, self.admin])
            db.session.commit()
            self.user_id = self.user.id
            self.admin_id = self.admin.id

    def sign_in(self, client):
        with client.session_transaction() as session:
            session["_user_id"] = str(self.user_id)
            session["_fresh"] = True

    def csrf_token(self, client, path="/dashboard"):
        client.get(path)
        with client.session_transaction() as session:
            return session["_csrf_token"]

    def test_protected_pages_reject_anonymous_access(self):
        client = app.test_client()
        for path in ("/dashboard", "/tickets", "/chat", "/admin"):
            response = client.get(path)
            self.assertEqual(response.status_code, 302, path)
            self.assertIn("/login", response.headers["Location"])

    def test_security_headers_are_present(self):
        response = app.test_client().get("/")
        self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "SAMEORIGIN")
        self.assertEqual(response.headers["Referrer-Policy"], "strict-origin-when-cross-origin")

    def test_post_without_csrf_token_is_rejected(self):
        client = app.test_client()
        self.sign_in(client)
        response = client.post("/create-ticket", data={"subject": "Test"})
        self.assertEqual(response.status_code, 400)

    def test_external_login_redirect_is_rejected(self):
        client = app.test_client()
        token = self.csrf_token(client, "/login")
        response = client.post(
            "/login?next=https://attacker.example",
            data={
                "csrf_token": token,
                "email": "security-staff@example.test",
                "password": "Password123!",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/dashboard"))

    def test_template_escapes_article_content(self):
        with app.app_context():
            db.session.add(
                KnowledgeArticle(
                    title="<script>alert('xss')</script>",
                    content="<img src=x onerror=alert(1)>",
                    category="Security",
                    is_published=True,
                    author_id=self.admin_id,
                )
            )
            db.session.commit()

        client = app.test_client()
        self.sign_in(client)
        response = client.get("/knowledge?search=Security")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"<script>alert", response.data)
        self.assertIn(b"&lt;script&gt;", response.data)


if __name__ == "__main__":
    unittest.main()
