"""Critical user and administrator regression checks."""

import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path


TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / "helpdesk-pro-regression.db"
TEST_ATTACHMENT_DIRECTORY = Path(tempfile.gettempdir()) / "helpdesk-pro-test-attachments"

if TEST_DATABASE_PATH.exists():
    TEST_DATABASE_PATH.unlink()

os.environ["APP_ENV"] = "testing"
os.environ["SECRET_KEY"] = "regression-test-secret"
os.environ["DATABASE_URL"] = (
    f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"
)

from app import (  # noqa: E402
    ChatConversation,
    ChatMessage,
    ChatSatisfactionRating,
    Notification,
    Ticket,
    TicketAttachment,
    TicketReply,
    User,
    app,
    db,
)
from werkzeug.security import generate_password_hash  # noqa: E402


class HelpDeskRegressionTests(unittest.TestCase):

    def setUp(self):
        app.config["TESTING"] = True
        app.config["TICKET_ATTACHMENT_FOLDER"] = str(TEST_ATTACHMENT_DIRECTORY)
        shutil.rmtree(TEST_ATTACHMENT_DIRECTORY, ignore_errors=True)

        with app.app_context():
            db.drop_all()
            db.create_all()

            self.admin = User(
                username="Admin One",
                email="admin-one@example.test",
                password=generate_password_hash("Password123!"),
                is_admin=True,
            )
            self.second_admin = User(
                username="Admin Two",
                email="admin-two@example.test",
                password=generate_password_hash("Password123!"),
                is_admin=True,
            )
            self.user = User(
                username="Search Target",
                email="staff@example.test",
                password=generate_password_hash("Password123!"),
                is_admin=False,
            )
            self.fresh_user = User(
                username="Fresh Staff",
                email="fresh-staff@example.test",
                password=generate_password_hash("Password123!"),
                is_admin=False,
            )
            db.session.add_all([
                self.admin,
                self.second_admin,
                self.user,
                self.fresh_user,
            ])
            db.session.commit()

            self.admin_id = self.admin.id
            self.second_admin_id = self.second_admin.id
            self.user_id = self.user.id

    def test_new_staff_chat_appears_after_first_message(self):
        fresh_user_client = app.test_client()
        admin_client = app.test_client()

        self.sign_in(fresh_user_client, "fresh-staff@example.test")
        response = fresh_user_client.get("/chat")
        self.assertEqual(response.status_code, 200)

        self.sign_in(admin_client, "admin-one@example.test")
        response = admin_client.get("/chat")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"Fresh Staff", response.data)

        token = self.csrf_token(fresh_user_client, "/chat")
        response = fresh_user_client.post(
            "/chat/send",
            data={
                "csrf_token": token,
                "message": "I need help with a new issue.",
            },
        )
        self.assertEqual(response.status_code, 302)

        response = admin_client.get("/chat")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Fresh Staff", response.data)
        self.assertIn(b"New", response.data)

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()
        shutil.rmtree(TEST_ATTACHMENT_DIRECTORY, ignore_errors=True)

    @classmethod
    def tearDownClass(cls):
        with app.app_context():
            db.session.remove()
            db.engine.dispose()

        if TEST_DATABASE_PATH.exists():
            TEST_DATABASE_PATH.unlink()

    @staticmethod
    def csrf_token(client, page):
        response = client.get(page)
        if response.status_code not in {200, 302}:
            raise AssertionError(f"Could not open {page} for a CSRF token.")

        with client.session_transaction() as session:
            return session["_csrf_token"]

    def sign_in(self, client, email):
        token = self.csrf_token(client, "/login")
        response = client.post(
            "/login",
            data={
                "csrf_token": token,
                "email": email,
                "password": "Password123!",
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_user_search_and_progress_update(self):
        user_client = app.test_client()
        admin_client = app.test_client()

        self.sign_in(user_client, "staff@example.test")
        token = self.csrf_token(user_client, "/create-ticket")
        response = user_client.post(
            "/create-ticket",
            data={
                "csrf_token": token,
                "subject": "WiFi cannot connect",
                "description": "The guest WiFi page does not complete sign-in.",
                "priority": "High",
                "category": "Network & WiFi",
            },
        )
        self.assertEqual(response.status_code, 302)

        with app.app_context():
            ticket = Ticket.query.one()
            ticket_id = ticket.id

        self.sign_in(admin_client, "admin-one@example.test")
        response = admin_client.get("/admin/users?search=Target")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"staff@example.test", response.data)

        response = admin_client.get("/admin/users?sort=id_asc")
        self.assertEqual(response.status_code, 200)
        self.assertLess(response.data.index(b"#1"), response.data.index(b"#4"))

        token = self.csrf_token(
            admin_client,
            f"/admin/ticket/{ticket_id}",
        )
        response = admin_client.post(
            f"/admin/ticket/{ticket_id}/progress-update",
            data={
                "csrf_token": token,
                "update_type": "investigating",
                "additional_note": "We are checking the router now.",
            },
        )
        self.assertEqual(response.status_code, 302)

        with app.app_context():
            ticket = db.session.get(Ticket, ticket_id)
            self.assertEqual(ticket.status, "In Progress")
            self.assertEqual(TicketReply.query.count(), 1)
            self.assertEqual(Notification.query.count(), 1)

    def test_admin_dashboard_shows_reporting_snapshot(self):
        with app.app_context():
            overdue_ticket = Ticket(
                ticket_number=1,
                subject="Overdue router replacement",
                description="The replacement router has not arrived.",
                priority="Critical",
                category="Network & WiFi",
                status="Open",
                due_at=datetime.utcnow() - timedelta(hours=1),
                user_id=self.user_id,
            )
            db.session.add(overdue_ticket)
            db.session.add(ChatSatisfactionRating(
                user_id=self.user_id,
                admin_id=self.admin_id,
                rating=5,
            ))
            db.session.commit()
            overdue_ticket_id = overdue_ticket.id

        admin_client = app.test_client()
        self.sign_in(admin_client, "admin-one@example.test")
        response = admin_client.get("/admin")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Due-date watch", response.data)
        self.assertIn(b"Overdue", response.data)
        self.assertIn(b"Live chat satisfaction", response.data)
        self.assertIn(b"Network &amp; WiFi", response.data)

        today = datetime.utcnow().date().isoformat()
        response = admin_client.get(
            f"/admin?date_from={today}&date_to={today}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Reporting period", response.data)
        self.assertIn(today.encode(), response.data)

        response = admin_client.get(
            f"/admin/reports/tickets.csv?date_from={today}&date_to={today}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Ticket number,Subject,Requester", response.data)
        self.assertIn(b"Overdue router replacement", response.data)
        self.assertIn(b"attachment; filename=helpdeskpro-tickets", response.headers["Content-Disposition"].encode())

        response = admin_client.get("/admin/tickets?due=overdue&sort=ticket_asc")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Overdue router replacement", response.data)

        token = self.csrf_token(
            admin_client,
            f"/admin/ticket/{overdue_ticket_id}",
        )
        response = admin_client.post(
            f"/admin/ticket/{overdue_ticket_id}/due-date",
            data={
                "csrf_token": token,
                "due_at": "2026-01-01T09:00",
            },
        )
        self.assertEqual(response.status_code, 302)

        with app.app_context():
            ticket = db.session.get(Ticket, overdue_ticket_id)
            self.assertEqual(ticket.status, "Open")

    def test_ticket_attachment_is_private_and_validated(self):
        with app.app_context():
            ticket = Ticket(
                ticket_number=1,
                subject="Screenshot needed",
                description="I need to share a PDF error report.",
                priority="Medium",
                category="Software",
                status="Open",
                user_id=self.user_id,
            )
            db.session.add(ticket)
            db.session.commit()
            ticket_id = ticket.id

        owner_client = app.test_client()
        self.sign_in(owner_client, "staff@example.test")
        token = self.csrf_token(owner_client, f"/ticket/{ticket_id}")
        response = owner_client.post(
            f"/ticket/{ticket_id}/attachments",
            data={
                "csrf_token": token,
                "attachment": (BytesIO(b"%PDF-1.4\nTest attachment"), "error-report.pdf"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 302)

        with app.app_context():
            attachment = TicketAttachment.query.one()
            attachment_id = attachment.id
            self.assertTrue(
                (TEST_ATTACHMENT_DIRECTORY / attachment.stored_filename).is_file()
            )

        response = owner_client.get(f"/ticket/attachments/{attachment_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"%PDF-1.4\nTest attachment")
        response.close()

        other_user_client = app.test_client()
        self.sign_in(other_user_client, "fresh-staff@example.test")
        response = other_user_client.get(f"/ticket/attachments/{attachment_id}")
        self.assertEqual(response.status_code, 403)

    def test_chat_claim_feedback_and_close(self):
        user_client = app.test_client()
        first_admin_client = app.test_client()
        second_admin_client = app.test_client()

        self.sign_in(user_client, "staff@example.test")
        token = self.csrf_token(user_client, "/chat")
        response = user_client.post(
            "/chat/send",
            data={
                "csrf_token": token,
                "message": "I need help with my account.",
            },
        )
        self.assertEqual(response.status_code, 302)

        with app.app_context():
            conversation = ChatConversation.query.one()
            conversation_id = conversation.id
            self.assertEqual(ChatMessage.query.count(), 1)

        self.sign_in(first_admin_client, "admin-one@example.test")
        token = self.csrf_token(
            first_admin_client,
            f"/chat?conversation={conversation_id}",
        )
        response = first_admin_client.post(
            f"/chat/{conversation_id}/claim",
            data={"csrf_token": token},
        )
        self.assertEqual(response.status_code, 302)

        self.sign_in(second_admin_client, "admin-two@example.test")
        response = second_admin_client.get(
            f"/chat?conversation={conversation_id}",
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"This chat has been taken by another admin.", response.data)

        response = second_admin_client.get(
            f"/chat/{conversation_id}/availability",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"state": "taken"})

        token = self.csrf_token(
            first_admin_client,
            f"/chat?conversation={conversation_id}",
        )
        response = first_admin_client.post(
            f"/chat/{conversation_id}/request-feedback",
            data={"csrf_token": token},
        )
        self.assertEqual(response.status_code, 302)

        token = self.csrf_token(user_client, "/chat")
        response = user_client.post(
            f"/chat/{conversation_id}/feedback",
            data={"csrf_token": token, "rating": "5"},
        )
        self.assertEqual(response.status_code, 302)

        with app.app_context():
            self.assertIsNone(db.session.get(ChatConversation, conversation_id))
            self.assertEqual(ChatSatisfactionRating.query.count(), 1)

    def test_admin_closing_a_completed_chat_never_returns_404(self):
        user_client = app.test_client()
        admin_client = app.test_client()

        self.sign_in(user_client, "staff@example.test")
        token = self.csrf_token(user_client, "/chat")
        response = user_client.post(
            "/chat/send",
            data={"csrf_token": token, "message": "Please close this chat."},
        )
        self.assertEqual(response.status_code, 302)

        with app.app_context():
            conversation_id = ChatConversation.query.one().id

        self.sign_in(admin_client, "admin-one@example.test")
        token = self.csrf_token(
            admin_client,
            f"/chat?conversation={conversation_id}",
        )
        response = admin_client.post(
            f"/chat/{conversation_id}/claim",
            data={"csrf_token": token},
        )
        self.assertEqual(response.status_code, 302)

        token = self.csrf_token(
            admin_client,
            f"/chat?conversation={conversation_id}",
        )
        response = admin_client.post(
            f"/chat/{conversation_id}/request-feedback",
            data={"csrf_token": token},
        )
        self.assertEqual(response.status_code, 302)

        token = self.csrf_token(
            admin_client,
            f"/chat?conversation={conversation_id}",
        )
        response = admin_client.post(
            f"/chat/{conversation_id}/close",
            data={"csrf_token": token},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"completed chat and its messages were deleted", response.data)

        # A delayed duplicate submission should show a useful notice too.
        token = self.csrf_token(admin_client, "/chat")
        response = admin_client.post(
            f"/chat/{conversation_id}/close",
            data={"csrf_token": token},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"This chat has already been closed.", response.data)

        # A stale browser tab must be sent back to the chat inbox, never a 404.
        response = admin_client.get(
            f"/chat?conversation={conversation_id}",
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"This chat is no longer active.", response.data)


if __name__ == "__main__":
    unittest.main()
