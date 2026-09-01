from sqlalchemy import text, or_, func
from datetime import datetime, timedelta, timezone
from functools import wraps
from hmac import compare_digest
from secrets import token_urlsafe
from pathlib import Path
from hashlib import sha256
from email.message import EmailMessage
import logging
import os
import smtplib
import warnings
from zoneinfo import ZoneInfo

from flask import (
    Flask,
    abort,
    render_template,
    request,
    redirect,
    jsonify,
    session,
    url_for,
    flash,
)

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)
from werkzeug.middleware.proxy_fix import ProxyFix

from PIL import Image, UnidentifiedImageError


# =========================================================
# APPLICATION SETUP
# =========================================================

app = Flask(__name__)

app_environment = os.environ.get("APP_ENV", "development").lower()
secret_key = os.environ.get("SECRET_KEY")

if app_environment == "production" and not secret_key:
    raise RuntimeError("SECRET_KEY must be set in production.")

database_url = os.environ.get("DATABASE_URL", "sqlite:///helpdesk.db")

if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://",
        "postgresql+psycopg://",
        1,
    )
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1,
    )

app.config["SECRET_KEY"] = secret_key or "local-development-key-only"
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (
    os.environ.get(
        "SESSION_COOKIE_SECURE",
        str(app_environment == "production"),
    ).lower() == "true"
)
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
app.config["PREFERRED_URL_SCHEME"] = (
    "https"
    if app_environment == "production"
    else "http"
)

trusted_proxy_count = int(os.environ.get("TRUSTED_PROXY_COUNT", "0"))

if trusted_proxy_count:
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=trusted_proxy_count,
        x_proto=trusted_proxy_count,
    )

if not app.logger.handlers:
    log_handler = logging.StreamHandler()
    log_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"
        )
    )
    app.logger.addHandler(log_handler)

app.logger.setLevel(logging.INFO)
app.config["RESET_TOKEN_TTL_MINUTES"] = 60
app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER")
app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", "587"))
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")
app.config["MAIL_FROM"] = os.environ.get("MAIL_FROM")
app.config["MAIL_USE_TLS"] = (
    os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
)
app.config["DISPLAY_TIMEZONE"] = os.environ.get(
    "DISPLAY_TIMEZONE",
    "Africa/Lagos",
)

KNOWLEDGE_IMAGE_MAX_BYTES = 5 * 1024 * 1024
KNOWLEDGE_IMAGE_MAX_PIXELS = 25_000_000
KNOWLEDGE_IMAGE_EXTENSIONS = {
    "JPEG": "jpg",
    "PNG": "png",
    "WEBP": "webp",
}

TICKET_CATEGORIES = (
    "Account Access",
    "Hardware",
    "Network & WiFi",
    "Software",
    "Other",
)

TICKET_PROGRESS_UPDATES = {
    "investigating": "Support is investigating your issue.",
    "work_in_progress": "Support is actively working on a resolution.",
    "awaiting_information": "Support needs a little more information to continue.",
    "escalated": "Your issue has been escalated for further review.",
}

db = SQLAlchemy(app)
migrate = Migrate(app, db, compare_type=True)


# =========================================================
# LOGIN MANAGER
# =========================================================

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


# =========================================================
# DATABASE MODELS
# =========================================================

# -------------------------
# USER MODEL
# -------------------------

class User(UserMixin, db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    username = db.Column(
        db.String(100),
        nullable=False,
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False,
    )

    password = db.Column(
        db.String(255),
        nullable=False,
    )

    is_admin = db.Column(
        db.Boolean,
        default=False,
        nullable=False,
    )

    is_active = db.Column(
        db.Boolean,
        default=True,
        nullable=False,
    )

    def __repr__(self):
        return f"<User {self.username}>"


# -------------------------
# PASSWORD RESET TOKEN MODEL
# -------------------------

class PasswordResetToken(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    token_hash = db.Column(
        db.String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    expires_at = db.Column(
        db.DateTime,
        nullable=False,
    )

    used_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
        index=True,
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "password_reset_tokens",
            lazy=True,
            cascade="all, delete-orphan",
        ),
    )

    def __repr__(self):
        return f"<PasswordResetToken {self.id}>"


# -------------------------
# RATE LIMIT EVENT MODEL
# -------------------------

class RateLimitEvent(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    action = db.Column(
        db.String(50),
        nullable=False,
        index=True,
    )

    identifier = db.Column(
        db.String(255),
        nullable=False,
        index=True,
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    def __repr__(self):
        return f"<RateLimitEvent {self.action}>"


# -------------------------
# TICKET MODEL
# -------------------------

class Ticket(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    ticket_number = db.Column(
        db.Integer,
        nullable=False,
    )

    subject = db.Column(
        db.String(200),
        nullable=False,
    )

    description = db.Column(
        db.Text,
        nullable=False,
    )

    priority = db.Column(
        db.String(20),
        nullable=False,
        default="Medium",
    )

    category = db.Column(
        db.String(50),
        nullable=False,
        default="Other",
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="Open",
    )

    due_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "tickets",
            lazy=True,
        ),
    )

    def __repr__(self):
        return f"<Ticket {self.ticket_number}: {self.subject}>"


# -------------------------
# TICKET REPLY MODEL
# -------------------------

class TicketReply(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    message = db.Column(
        db.Text,
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    ticket_id = db.Column(
        db.Integer,
        db.ForeignKey("ticket.id"),
        nullable=False,
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
    )

    ticket = db.relationship(
        "Ticket",
        backref=db.backref(
            "replies",
            lazy=True,
            cascade="all, delete-orphan",
        ),
    )

    author = db.relationship(
        "User",
    )

    def __repr__(self):
        return f"<TicketReply {self.id}>"


class TicketInternalNote(db.Model):
    """Private ticket context visible only to support administrators."""

    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ticket_id = db.Column(db.Integer, db.ForeignKey("ticket.id"), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    ticket = db.relationship(
        "Ticket",
        backref=db.backref("internal_notes", lazy=True, cascade="all, delete-orphan"),
    )
    author = db.relationship("User")


class TicketTag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), nullable=False)
    ticket_id = db.Column(db.Integer, db.ForeignKey("ticket.id"), nullable=False, index=True)
    ticket = db.relationship("Ticket", backref=db.backref("tags", lazy=True, cascade="all, delete-orphan"))

    __table_args__ = (db.UniqueConstraint("ticket_id", "name", name="uq_ticket_tag_name"),)


class TicketStatusHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    previous_status = db.Column(db.String(20), nullable=False)
    new_status = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ticket_id = db.Column(db.Integer, db.ForeignKey("ticket.id"), nullable=False, index=True)
    changed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    ticket = db.relationship("Ticket", backref=db.backref("status_history", lazy=True, cascade="all, delete-orphan"))
    changed_by = db.relationship("User")


# -------------------------
# LIVE CHAT MODELS
# -------------------------

CHAT_INACTIVITY_MINUTES = 24 * 60


class ChatConversation(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
        unique=True,
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    last_message_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    assigned_admin_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=True,
        index=True,
    )

    assigned_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    resolution_requested_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        backref=db.backref(
            "chat_conversation",
            uselist=False,
        ),
    )

    assigned_admin = db.relationship(
        "User",
        foreign_keys=[assigned_admin_id],
        backref=db.backref(
            "assigned_chat_conversations",
            lazy=True,
        ),
    )

    def __repr__(self):
        return f"<ChatConversation {self.id}>"


class ChatMessage(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    message = db.Column(
        db.Text,
        nullable=False,
    )

    is_read = db.Column(
        db.Boolean,
        default=False,
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    conversation_id = db.Column(
        db.Integer,
        db.ForeignKey("chat_conversation.id"),
        nullable=False,
        index=True,
    )

    sender_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
    )

    conversation = db.relationship(
        "ChatConversation",
        backref=db.backref(
            "messages",
            lazy=True,
            cascade="all, delete-orphan",
        ),
    )

    sender = db.relationship("User")

    def __repr__(self):
        return f"<ChatMessage {self.id}>"


class ChatSatisfactionRating(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


def clear_inactive_chat_conversations():
    """Remove chat threads that have been inactive for one full day."""

    cutoff = datetime.utcnow() - timedelta(
        minutes=CHAT_INACTIVITY_MINUTES,
    )

    inactive_conversations = ChatConversation.query.filter(
        ChatConversation.last_message_at < cutoff,
    ).all()

    for conversation in inactive_conversations:
        db.session.delete(conversation)

    if inactive_conversations:
        db.session.commit()


# -------------------------
# NOTIFICATION MODEL
# -------------------------

class Notification(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    recipient_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
        index=True,
    )

    ticket_id = db.Column(
        db.Integer,
        db.ForeignKey("ticket.id"),
        nullable=False,
        index=True,
    )

    message = db.Column(
        db.String(255),
        nullable=False,
    )

    is_read = db.Column(
        db.Boolean,
        default=False,
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    recipient = db.relationship(
        "User",
        backref=db.backref(
            "notifications",
            lazy=True,
            cascade="all, delete-orphan",
        ),
    )

    ticket = db.relationship(
        "Ticket",
        backref=db.backref(
            "notifications",
            lazy=True,
            cascade="all, delete-orphan",
        ),
    )

    def __repr__(self):
        return f"<Notification {self.id}>"


# -------------------------
# KNOWLEDGE ARTICLE MODEL
# -------------------------

class KnowledgeArticle(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    title = db.Column(
        db.String(200),
        nullable=False,
    )

    category = db.Column(
        db.String(100),
        nullable=False,
        default="General",
    )

    content = db.Column(
        db.Text,
        nullable=False,
    )

    is_published = db.Column(
        db.Boolean,
        default=False,
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    author_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
    )

    author = db.relationship(
        "User",
        backref=db.backref(
            "knowledge_articles",
            lazy=True,
        ),
    )

    def __repr__(self):
        return f"<KnowledgeArticle {self.id}: {self.title}>"


# -------------------------
# KNOWLEDGE ARTICLE IMAGE MODEL
# -------------------------

class KnowledgeArticleImage(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    image_path = db.Column(
        db.String(255),
        nullable=False,
    )

    alt_text = db.Column(
        db.String(255),
        nullable=False,
    )

    caption = db.Column(
        db.String(255),
        nullable=True,
    )

    sort_order = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )

    article_id = db.Column(
        db.Integer,
        db.ForeignKey("knowledge_article.id"),
        nullable=False,
    )

    article = db.relationship(
        "KnowledgeArticle",
        backref=db.backref(
            "images",
            lazy=True,
            cascade="all, delete-orphan",
        ),
    )

    def __repr__(self):
        return f"<KnowledgeArticleImage {self.id}>"


# =========================================================
# LOGIN / ACCESS HELPERS
# =========================================================

@login_manager.user_loader
def load_user(user_id):

    user = db.session.get(User, int(user_id))

    if not user:
        return None

    if not user.is_active:
        return None

    return user


def admin_required(f):

    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):

        if not current_user.is_admin:

            flash(
                "You do not have permission to access the admin area.",
                "danger",
            )

            return redirect(
                url_for("dashboard")
            )

        return f(*args, **kwargs)

    return decorated_function


def create_notification(recipient_id, ticket_id, message):

    db.session.add(
        Notification(
            recipient_id=recipient_id,
            ticket_id=ticket_id,
            message=message,
        )
    )


def get_csrf_token():

    csrf_token = session.get("_csrf_token")

    if not csrf_token:
        csrf_token = token_urlsafe(32)
        session["_csrf_token"] = csrf_token

    return csrf_token


def validate_csrf_token():

    csrf_token = session.get("_csrf_token", "")
    submitted_token = request.form.get("csrf_token", "")

    if (
        not csrf_token
        or not submitted_token
        or not compare_digest(csrf_token, submitted_token)
    ):
        abort(400)


@app.before_request
def protect_post_requests():

    if request.method == "POST":
        validate_csrf_token()


@app.after_request
def apply_security_headers(response):

    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' https://cdnjs.cloudflare.com; "
        "font-src 'self' https://cdnjs.cloudflare.com; "
        "img-src 'self' data:; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'self'",
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault(
        "Referrer-Policy",
        "strict-origin-when-cross-origin",
    )
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=()",
    )

    if app_environment == "production":
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )

    if request.endpoint in {
        "login",
        "forgot_password",
        "reset_password",
        "settings",
    }:
        response.headers["Cache-Control"] = "no-store"

    return response


def render_error_page(status_code, title, message):

    return render_template(
        "errors/error.html",
        status_code=status_code,
        title=title,
        message=message,
    ), status_code


@app.errorhandler(400)
def bad_request(error):

    return render_error_page(
        400,
        "Request could not be verified",
        "Please refresh the page and try again.",
    )


@app.errorhandler(404)
def page_not_found(error):

    return render_error_page(
        404,
        "Page not found",
        "The page you requested is unavailable or may have moved.",
    )


@app.errorhandler(413)
def request_too_large(error):

    return render_error_page(
        413,
        "Upload is too large",
        "Choose a smaller file and try again.",
    )


@app.errorhandler(429)
def too_many_requests(error):

    return render_error_page(
        429,
        "Please wait before trying again",
        "Too many requests were made from this device. Try again shortly.",
    )


@app.errorhandler(500)
def internal_server_error(error):

    db.session.rollback()
    app.logger.exception("Unhandled application error")

    return render_error_page(
        500,
        "Something went wrong",
        "Our team has been notified. Please try again shortly.",
    )


def rate_limit_identifiers(email=""):

    remote_address = request.remote_addr or "unknown"
    identifiers = [f"ip:{remote_address}"]

    if email:
        identifiers.append(f"email:{email.strip().lower()}")

    return identifiers


def is_rate_limited(action, identifiers, limit, window_minutes):

    cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)

    for identifier in identifiers:
        attempts = RateLimitEvent.query.filter(
            RateLimitEvent.action == action,
            RateLimitEvent.identifier == identifier,
            RateLimitEvent.created_at >= cutoff,
        ).count()

        if attempts >= limit:
            return True

    return False


def record_rate_limit_attempt(action, identifiers):

    RateLimitEvent.query.filter(
        RateLimitEvent.created_at < (
            datetime.utcnow() - timedelta(days=1)
        )
    ).delete(
        synchronize_session=False,
    )

    for identifier in identifiers:
        db.session.add(
            RateLimitEvent(
                action=action,
                identifier=identifier,
            )
        )

    db.session.commit()


def clear_rate_limit_attempts(action, identifiers):

    RateLimitEvent.query.filter(
        RateLimitEvent.action == action,
        RateLimitEvent.identifier.in_(identifiers),
    ).delete(
        synchronize_session=False,
    )
    db.session.commit()


def hash_reset_token(token):

    return sha256(token.encode("utf-8")).hexdigest()


def get_valid_reset_token(token):

    return PasswordResetToken.query.filter(
        PasswordResetToken.token_hash == hash_reset_token(token),
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.expires_at > datetime.utcnow(),
    ).first()


def send_password_reset_email(user, token):

    if not app.config["MAIL_SERVER"] or not app.config["MAIL_FROM"]:
        return False

    if bool(app.config["MAIL_USERNAME"]) != bool(
        app.config["MAIL_PASSWORD"]
    ):
        return False

    reset_url = url_for(
        "reset_password",
        token=token,
        _external=True,
    )

    email = EmailMessage()
    email["Subject"] = "Reset your HelpDesk Pro password"
    email["From"] = app.config["MAIL_FROM"]
    email["To"] = user.email
    email.set_content(
        "We received a request to reset your HelpDesk Pro password.\n\n"
        f"Use this one-time link within {app.config['RESET_TOKEN_TTL_MINUTES']} "
        f"minutes:\n{reset_url}\n\n"
        "If you did not request this, you can safely ignore this email."
    )

    try:
        with smtplib.SMTP(
            app.config["MAIL_SERVER"],
            app.config["MAIL_PORT"],
            timeout=10,
        ) as smtp:
            if app.config["MAIL_USE_TLS"]:
                smtp.starttls()

            if app.config["MAIL_USERNAME"]:
                smtp.login(
                    app.config["MAIL_USERNAME"],
                    app.config["MAIL_PASSWORD"],
                )

            smtp.send_message(email)
    except (OSError, smtplib.SMTPException):
        return False

    return True


def add_knowledge_article_image(article):

    upload = request.files.get("article_image")

    if not upload or not upload.filename:
        return None, None

    caption = request.form.get(
        "image_caption",
        "",
    ).strip()

    if len(caption) > 255:
        return "The image caption is too long.", None

    try:
        upload.stream.seek(0, 2)
        file_size = upload.stream.tell()
        upload.stream.seek(0)
    except (AttributeError, OSError):
        return "The selected image could not be read.", None

    if file_size > KNOWLEDGE_IMAGE_MAX_BYTES:
        return "Images must be 5 MB or smaller.", None

    try:
        with warnings.catch_warnings():
            warnings.simplefilter(
                "error",
                Image.DecompressionBombWarning,
            )

            with Image.open(upload.stream) as image:
                image.verify()

            upload.stream.seek(0)

            with Image.open(upload.stream) as image:
                image_format = image.format
                image_width, image_height = image.size
    except (
        Image.DecompressionBombWarning,
        OSError,
        UnidentifiedImageError,
    ):
        return "Upload a valid PNG, JPEG, or WebP image.", None

    if image_format not in KNOWLEDGE_IMAGE_EXTENSIONS:
        return "Only PNG, JPEG, and WebP images are supported.", None

    if image_width * image_height > KNOWLEDGE_IMAGE_MAX_PIXELS:
        return "The image is too large. Choose one below 25 megapixels.", None

    upload_directory = Path(app.static_folder) / \
        "images" / "knowledge" / "uploads"
    upload_directory.mkdir(parents=True, exist_ok=True)

    filename = (
        f"article-{article.id}-{token_urlsafe(12)}."
        f"{KNOWLEDGE_IMAGE_EXTENSIONS[image_format]}"
    )
    destination = upload_directory / filename

    upload.stream.seek(0)
    upload.save(destination)

    image = KnowledgeArticleImage(
        article_id=article.id,
        image_path=f"images/knowledge/uploads/{filename}",
        alt_text=(caption or article.title)[:255],
        caption=caption or None,
        sort_order=len(article.images),
    )
    db.session.add(image)

    return None, destination


@app.context_processor
def inject_notification_count():

    if not current_user.is_authenticated:
        return {
            "csrf_token": get_csrf_token(),
            "unread_notification_count": 0,
        }

    unread_notification_count = Notification.query.filter_by(
        recipient_id=current_user.id,
        is_read=False,
    ).count()

    return {
        "csrf_token": get_csrf_token(),
        "unread_notification_count": unread_notification_count,
    }


@app.template_filter("local_datetime")
def local_datetime(value, time_format="%d %b %Y, %H:%M"):
    """Display legacy UTC timestamps in the configured local timezone."""

    if value is None:
        return "—"

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(
        ZoneInfo(app.config["DISPLAY_TIMEZONE"])
    ).strftime(time_format)


# =========================================================
# PUBLIC ROUTES
# =========================================================

# -------------------------
# HOME
# -------------------------

@app.route("/")
def home():

    return render_template(
        "home.html"
    )


# -------------------------
# LOGIN
# -------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            "",
        ).strip().lower()
        password = request.form.get(
            "password",
            "",
        )
        identifiers = rate_limit_identifiers(email)

        if is_rate_limited(
            "login",
            identifiers,
            limit=5,
            window_minutes=15,
        ):
            abort(429)

        user = User.query.filter_by(
            email=email
        ).first()

        if user and check_password_hash(
            user.password,
            password,
        ):

            if not user.is_active:

                flash(
                    "This account has been deactivated. "
                    "Please contact an administrator.",
                    "danger",
                )

                return redirect(
                    url_for("login")
                )

            login_user(user)
            session.permanent = True
            clear_rate_limit_attempts("login", identifiers)

            if user.is_admin:

                return redirect(
                    url_for("admin_dashboard")
                )

            return redirect(
                url_for("dashboard")
            )

        flash(
            "Invalid email or password.",
            "danger",
        )

        record_rate_limit_attempt("login", identifiers)

        return redirect(
            url_for("login")
        )

    return render_template(
        "auth/login.html"
    )


# -------------------------
# FORGOT PASSWORD
# -------------------------

@app.route(
    "/forgot-password",
    methods=["GET", "POST"],
)
def forgot_password():

    if request.method == "POST":

        validate_csrf_token()

        email = request.form.get(
            "email",
            "",
        ).strip().lower()
        identifiers = rate_limit_identifiers(email)

        if is_rate_limited(
            "password_reset",
            identifiers,
            limit=3,
            window_minutes=30,
        ):
            abort(429)

        user = User.query.filter_by(
            email=email,
            is_active=True,
        ).first()

        if user:
            now = datetime.utcnow()
            PasswordResetToken.query.filter_by(
                user_id=user.id,
                used_at=None,
            ).update(
                {"used_at": now},
                synchronize_session=False,
            )

            raw_token = token_urlsafe(32)
            reset_token = PasswordResetToken(
                token_hash=hash_reset_token(raw_token),
                expires_at=now + timedelta(
                    minutes=app.config["RESET_TOKEN_TTL_MINUTES"],
                ),
                user_id=user.id,
            )
            db.session.add(reset_token)
            db.session.commit()

            if not send_password_reset_email(user, raw_token):
                reset_token.used_at = datetime.utcnow()
                db.session.commit()

                flash(
                    "Password reset email is not configured yet. "
                    "Please contact support.",
                    "danger",
                )

                return redirect(
                    url_for("forgot_password")
                )

        record_rate_limit_attempt(
            "password_reset",
            identifiers,
        )

        flash(
            "If an account with that email exists, "
            "a password reset link has been sent. "
            "The link expires in one hour.",
            "success",
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "auth/forgot_password.html"
    )


@app.route("/chat/<int:conversation_id>/availability")
@admin_required
def chat_conversation_availability(conversation_id):

    conversation = ChatConversation.query.filter(
        ChatConversation.id == conversation_id,
        ChatConversation.user.has(User.is_admin.is_(False)),
    ).first()

    if conversation is None:
        return jsonify({"state": "closed"})

    if (
        conversation.assigned_admin_id is not None
        and conversation.assigned_admin_id != current_user.id
    ):
        return jsonify({"state": "taken"})

    if conversation.assigned_admin_id == current_user.id:
        return jsonify({"state": "assigned_to_you"})

    return jsonify({"state": "available"})


@app.route(
    "/reset-password/<token>",
    methods=["GET", "POST"],
)
def reset_password(token):

    reset_token = get_valid_reset_token(token)

    if reset_token is None:
        flash(
            "That password reset link is invalid or has expired. "
            "Request a new one.",
            "danger",
        )

        return redirect(
            url_for("forgot_password")
        )

    if request.method == "POST":
        validate_csrf_token()

        new_password = request.form.get(
            "new_password",
            "",
        )
        confirm_password = request.form.get(
            "confirm_password",
            "",
        )

        if len(new_password) < 8:
            flash(
                "Your new password must be at least 8 characters long.",
                "danger",
            )

            return redirect(
                url_for("reset_password", token=token)
            )

        if new_password != confirm_password:
            flash(
                "New passwords do not match.",
                "danger",
            )

            return redirect(
                url_for("reset_password", token=token)
            )

        if check_password_hash(
            reset_token.user.password,
            new_password,
        ):
            flash(
                "Choose a password different from your current password.",
                "danger",
            )

            return redirect(
                url_for("reset_password", token=token)
            )

        now = datetime.utcnow()
        reset_token.user.password = generate_password_hash(new_password)
        reset_token.used_at = now

        PasswordResetToken.query.filter(
            PasswordResetToken.user_id == reset_token.user_id,
            PasswordResetToken.id != reset_token.id,
            PasswordResetToken.used_at.is_(None),
        ).update(
            {"used_at": now},
            synchronize_session=False,
        )
        db.session.commit()

        flash(
            "Your password has been reset. Please sign in.",
            "success",
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "auth/reset_password.html",
        token=token,
    )


# -------------------------
# REGISTER
# -------------------------

@app.route(
    "/register",
    methods=["GET", "POST"],
)
def register():

    if request.method == "POST":

        username = request.form.get(
            "username",
            "",
        ).strip()
        email = request.form.get(
            "email",
            "",
        ).strip().lower()
        password = request.form.get(
            "password",
            "",
        )
        identifiers = rate_limit_identifiers(email)

        if is_rate_limited(
            "registration",
            identifiers,
            limit=5,
            window_minutes=60,
        ):
            abort(429)

        record_rate_limit_attempt("registration", identifiers)

        if (
            len(username) < 2
            or len(username) > 100
            or len(email) > 120
            or "@" not in email
            or len(password) < 8
        ):
            flash(
                "Use a valid email, a username between 2 and 100 characters, "
                "and a password of at least 8 characters.",
                "danger",
            )

            return redirect(
                url_for("register")
            )

        existing_user = User.query.filter_by(
            email=email
        ).first()

        if existing_user:

            flash(
                "Email already registered. Please login instead.",
                "danger",
            )

            return redirect(
                url_for("register")
            )

        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
            is_admin=False,
            is_active=True,
        )

        db.session.add(new_user)
        db.session.commit()
        clear_rate_limit_attempts("registration", identifiers)

        flash(
            "Registration successful! Please login.",
            "success",
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "auth/register.html"
    )


# =========================================================
# NORMAL USER ROUTES
# =========================================================

# -------------------------
# USER DASHBOARD
# -------------------------

@app.route("/dashboard")
@login_required
def dashboard():

    user_tickets = Ticket.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Ticket.created_at.desc()
    ).all()

    total_tickets = len(user_tickets)

    open_tickets = Ticket.query.filter_by(
        user_id=current_user.id,
        status="Open",
    ).count()

    in_progress_tickets = Ticket.query.filter_by(
        user_id=current_user.id,
        status="In Progress",
    ).count()

    resolved_tickets = Ticket.query.filter_by(
        user_id=current_user.id,
        status="Resolved",
    ).count()

    recent_tickets = user_tickets[:5]

    return render_template(
        "dashboard/dashboard.html",
        total_tickets=total_tickets,
        open_tickets=open_tickets,
        in_progress_tickets=in_progress_tickets,
        resolved_tickets=resolved_tickets,
        recent_tickets=recent_tickets,
    )


# -------------------------
# CREATE TICKET
# -------------------------

@app.route(
    "/create-ticket",
    methods=["GET", "POST"],
)
@login_required
def create_ticket():

    if request.method == "POST":

        subject = request.form["subject"].strip()
        description = request.form["description"].strip()
        priority = request.form["priority"]
        category = request.form.get("category", "").strip()

        allowed_priorities = [
            "Low",
            "Medium",
            "High",
            "Critical",
        ]

        if priority not in allowed_priorities:

            flash(
                "Invalid ticket priority.",
                "danger",
            )

            return redirect(
                url_for("create_ticket")
            )

        if category not in TICKET_CATEGORIES:

            flash(
                "Invalid ticket category.",
                "danger",
            )

            return redirect(
                url_for("create_ticket")
            )

        last_ticket = Ticket.query.order_by(
            Ticket.ticket_number.desc()
        ).first()

        if last_ticket:
            next_ticket_number = last_ticket.ticket_number + 1
        else:
            next_ticket_number = 1

        new_ticket = Ticket(
            ticket_number=next_ticket_number,
            subject=subject,
            description=description,
            priority=priority,
            category=category,
            status="Open",
            user_id=current_user.id,
        )

        db.session.add(new_ticket)
        db.session.commit()

        flash(
            f"Ticket #{next_ticket_number} created successfully!",
            "success",
        )

        return redirect(
            url_for("tickets")
        )

    return render_template(
        "create_ticket.html",
        prefill_subject=request.args.get(
            "subject",
            "",
        )[:200],
        prefill_description=request.args.get(
            "description",
            "",
        )[:5000],
        prefill_category=request.args.get(
            "category",
            "",
        ),
    )


# -------------------------
# MY TICKETS
# -------------------------

@app.route("/tickets")
@login_required
def tickets():

    user_tickets = Ticket.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Ticket.created_at.desc()
    ).all()

    return render_template(
        "tickets.html",
        tickets=user_tickets,
    )


# -------------------------
# USER TICKET DETAILS
# -------------------------

@app.route("/ticket/<int:ticket_id>")
@login_required
def ticket_details(ticket_id):

    ticket = Ticket.query.get_or_404(
        ticket_id
    )

    if ticket.user_id != current_user.id:

        flash(
            "You do not have permission to view this ticket.",
            "danger",
        )

        return redirect(
            url_for("tickets")
        )

    replies = TicketReply.query.filter_by(
        ticket_id=ticket.id
    ).order_by(
        TicketReply.created_at.asc()
    ).all()

    status_history = TicketStatusHistory.query.filter_by(
        ticket_id=ticket.id,
    ).order_by(TicketStatusHistory.created_at.desc()).all()

    if ticket.due_at is None:
        sla_state = "No due date"
    elif ticket.status == "Resolved":
        sla_state = "Resolved"
    elif ticket.due_at < datetime.utcnow():
        sla_state = "Overdue"
    elif ticket.due_at <= datetime.utcnow() + timedelta(hours=24):
        sla_state = "Due soon"
    else:
        sla_state = "On track"

    internal_notes = TicketInternalNote.query.filter_by(
        ticket_id=ticket.id,
    ).order_by(TicketInternalNote.created_at.asc()).all()

    return render_template(
        "ticket_details.html",
        ticket=ticket,
        replies=replies,
        sla_state=sla_state,
        status_history=status_history,
        internal_notes=internal_notes,
    )


# -------------------------
# USER REPLY TO TICKET
# -------------------------

@app.route(
    "/ticket/<int:ticket_id>/reply",
    methods=["POST"],
)
@login_required
def reply_to_ticket(ticket_id):

    ticket = Ticket.query.get_or_404(
        ticket_id
    )

    # Make sure the ticket belongs to the logged-in user
    if ticket.user_id != current_user.id:

        flash(
            "You do not have permission to reply to this ticket.",
            "danger",
        )

        return redirect(
            url_for("tickets")
        )

    # Resolved tickets are read-only for normal users
    if ticket.status == "Resolved":

        flash(
            "This ticket has been resolved and is now read-only.",
            "danger",
        )

        return redirect(
            url_for(
                "ticket_details",
                ticket_id=ticket.id,
            )
        )

    # Get the user's reply
    message = request.form.get(
        "message",
        "",
    ).strip()

    # Prevent empty replies
    if not message:

        flash(
            "Reply cannot be empty.",
            "danger",
        )

        return redirect(
            url_for(
                "ticket_details",
                ticket_id=ticket.id,
            )
        )

    # Save reply
    reply = TicketReply(
        message=message,
        ticket_id=ticket.id,
        user_id=current_user.id,
    )

    db.session.add(reply)

    active_admins = User.query.filter_by(
        is_admin=True,
        is_active=True,
    ).filter(
        User.id != current_user.id
    ).all()

    for admin in active_admins:
        create_notification(
            recipient_id=admin.id,
            ticket_id=ticket.id,
            message=(
                f"{current_user.username} replied to ticket "
                f"HDP-{ticket.ticket_number:04d}."
            ),
        )

    db.session.commit()

    flash(
        "Your reply was added.",
        "success",
    )

    return redirect(
        url_for(
            "ticket_details",
            ticket_id=ticket.id,
        )
    )
# -------------------------
# USER SETTINGS
# -------------------------


@app.route(
    "/settings",
    methods=["GET", "POST"],
)
@login_required
def settings():

    if request.method == "POST":

        current_password = request.form.get(
            "current_password",
            "",
        )

        new_password = request.form.get(
            "new_password",
            "",
        )

        confirm_password = request.form.get(
            "confirm_password",
            "",
        )

        if not check_password_hash(
            current_user.password,
            current_password,
        ):

            flash(
                "Your current password is incorrect.",
                "danger",
            )

            return redirect(
                url_for("settings")
            )

        if len(new_password) < 8:

            flash(
                "Your new password must be at least 8 characters long.",
                "danger",
            )

            return redirect(
                url_for("settings")
            )

        if new_password != confirm_password:

            flash(
                "New passwords do not match.",
                "danger",
            )

            return redirect(
                url_for("settings")
            )

        if check_password_hash(
            current_user.password,
            new_password,
        ):

            flash(
                "Your new password must be different from your current password.",
                "danger",
            )

            return redirect(
                url_for("settings")
            )

        current_user.password = generate_password_hash(
            new_password
        )

        db.session.commit()

        flash(
            "Your password was changed successfully.",
            "success",
        )

        return redirect(
            url_for("settings")
        )

    return render_template(
        "settings.html"
    )


# -------------------------
# NOTIFICATIONS
# -------------------------


@app.route("/notifications")
@login_required
def notifications():

    user_notifications = Notification.query.filter_by(
        recipient_id=current_user.id,
    ).order_by(
        Notification.is_read.asc(),
        Notification.created_at.desc(),
    ).all()

    return render_template(
        "notifications.html",
        notifications=user_notifications,
    )


@app.route(
    "/notifications/<int:notification_id>/open",
    methods=["POST"],
)
@login_required
def open_notification(notification_id):

    validate_csrf_token()

    notification = Notification.query.filter_by(
        id=notification_id,
        recipient_id=current_user.id,
    ).first_or_404()

    if not notification.is_read:
        notification.is_read = True
        db.session.commit()

    if current_user.is_admin:
        return redirect(
            url_for(
                "admin_ticket_details",
                ticket_id=notification.ticket_id,
            )
        )

    return redirect(
        url_for(
            "ticket_details",
            ticket_id=notification.ticket_id,
        )
    )


@app.route(
    "/notifications/mark-all-read",
    methods=["POST"],
)
@login_required
def mark_all_notifications_read():

    validate_csrf_token()

    Notification.query.filter_by(
        recipient_id=current_user.id,
        is_read=False,
    ).update(
        {"is_read": True},
        synchronize_session=False,
    )

    db.session.commit()

    flash(
        "All notifications have been marked as read.",
        "success",
    )

    return redirect(
        url_for("notifications")
    )

# -------------------------
# KNOWLEDGE BASE
# -------------------------


@app.route("/knowledge")
@login_required
def knowledge():

    search = request.args.get(
        "search",
        "",
    ).strip()

    category = request.args.get(
        "category",
        "",
    ).strip()

    articles_query = KnowledgeArticle.query.filter_by(
        is_published=True,
    )

    if search:
        articles_query = articles_query.filter(
            or_(
                KnowledgeArticle.title.ilike(
                    f"%{search}%"
                ),
                KnowledgeArticle.content.ilike(
                    f"%{search}%"
                ),
                KnowledgeArticle.category.ilike(
                    f"%{search}%"
                ),
            )
        )

    if category:
        articles_query = articles_query.filter_by(
            category=category,
        )

    articles = articles_query.order_by(
        KnowledgeArticle.updated_at.desc(),
    ).all()

    categories = [
        row[0]
        for row in db.session.query(
            KnowledgeArticle.category
        ).filter_by(
            is_published=True,
        ).distinct().order_by(
            KnowledgeArticle.category.asc(),
        ).all()
    ]

    return render_template(
        "knowledge.html",
        articles=articles,
        categories=categories,
        search=search,
        selected_category=category,
    )


@app.route("/knowledge/<int:article_id>")
@login_required
def knowledge_article(article_id):

    article = KnowledgeArticle.query.filter_by(
        id=article_id,
        is_published=True,
    ).first_or_404()

    return render_template(
        "knowledge_article.html",
        article=article,
    )


# -------------------------
# ADMIN KNOWLEDGE BASE
# -------------------------


@app.route("/admin/knowledge")
@admin_required
def admin_knowledge():

    articles = KnowledgeArticle.query.order_by(
        KnowledgeArticle.updated_at.desc(),
    ).all()

    return render_template(
        "admin/knowledge.html",
        articles=articles,
    )


@app.route(
    "/admin/knowledge/add",
    methods=["GET", "POST"],
)
@admin_required
def add_knowledge_article():

    if request.method == "POST":
        validate_csrf_token()

        title = request.form.get(
            "title",
            "",
        ).strip()

        category = request.form.get(
            "category",
            "",
        ).strip()

        content = request.form.get(
            "content",
            "",
        ).strip()

        if not title or not category or not content:
            flash(
                "Title, category, and article content are required.",
                "danger",
            )

            return redirect(
                url_for("add_knowledge_article")
            )

        if len(title) > 200 or len(category) > 100:
            flash(
                "The title or category is too long.",
                "danger",
            )

            return redirect(
                url_for("add_knowledge_article")
            )

        article = KnowledgeArticle(
            title=title,
            category=category,
            content=content,
            is_published=request.form.get("is_published") == "on",
            author_id=current_user.id,
        )

        db.session.add(article)
        db.session.flush()

        image_error, image_path = add_knowledge_article_image(article)

        if image_error:
            db.session.rollback()

            flash(
                image_error,
                "danger",
            )

            return redirect(
                url_for("add_knowledge_article")
            )

        db.session.commit()

        flash(
            "Knowledge Base article created successfully.",
            "success",
        )

        return redirect(
            url_for("admin_knowledge")
        )

    return render_template(
        "admin/knowledge_form.html",
        article=None,
    )


@app.route(
    "/admin/knowledge/<int:article_id>/edit",
    methods=["GET", "POST"],
)
@admin_required
def edit_knowledge_article(article_id):

    article = KnowledgeArticle.query.get_or_404(
        article_id
    )

    if request.method == "POST":
        validate_csrf_token()

        title = request.form.get(
            "title",
            "",
        ).strip()

        category = request.form.get(
            "category",
            "",
        ).strip()

        content = request.form.get(
            "content",
            "",
        ).strip()

        if not title or not category or not content:
            flash(
                "Title, category, and article content are required.",
                "danger",
            )

            return redirect(
                url_for(
                    "edit_knowledge_article",
                    article_id=article.id,
                )
            )

        if len(title) > 200 or len(category) > 100:
            flash(
                "The title or category is too long.",
                "danger",
            )

            return redirect(
                url_for(
                    "edit_knowledge_article",
                    article_id=article.id,
                )
            )

        article.title = title
        article.category = category
        article.content = content
        article.is_published = request.form.get(
            "is_published"
        ) == "on"

        image_error, image_path = add_knowledge_article_image(article)

        if image_error:
            db.session.rollback()

            flash(
                image_error,
                "danger",
            )

            return redirect(
                url_for(
                    "edit_knowledge_article",
                    article_id=article.id,
                )
            )

        db.session.commit()

        flash(
            "Knowledge Base article updated successfully.",
            "success",
        )

        return redirect(
            url_for("admin_knowledge")
        )

    return render_template(
        "admin/knowledge_form.html",
        article=article,
    )


# -------------------------
# LIVE CHAT
# -------------------------

@app.route("/chat")
@login_required
def chat():

    conversations = []
    active_conversation = None

    clear_inactive_chat_conversations()

    if current_user.is_admin:
        staff_started_chat = db.session.query(
            ChatMessage.id
        ).filter(
            ChatMessage.conversation_id == ChatConversation.id,
            ChatMessage.sender_id == ChatConversation.user_id,
        ).exists()

        visible_conversations = ChatConversation.query.filter(
            ChatConversation.user.has(User.is_admin.is_(False)),
            ChatConversation.user.has(User.is_active.is_(True)),
            staff_started_chat,
            or_(
                ChatConversation.assigned_admin_id.is_(None),
                ChatConversation.assigned_admin_id == current_user.id,
            ),
        )

        unassigned_conversations = visible_conversations.filter(
            ChatConversation.assigned_admin_id.is_(None),
        ).order_by(
            ChatConversation.last_message_at.desc(),
        ).all()

        assigned_conversations = visible_conversations.filter(
            ChatConversation.assigned_admin_id == current_user.id,
        ).order_by(
            ChatConversation.last_message_at.desc(),
        ).all()

        conversations = unassigned_conversations + assigned_conversations

        conversation_id = request.args.get(
            "conversation",
            type=int,
        )

        if conversation_id:
            active_conversation = visible_conversations.filter(
                ChatConversation.id == conversation_id,
            ).first()

            if active_conversation is None:
                unavailable_conversation = ChatConversation.query.filter(
                    ChatConversation.id == conversation_id,
                    ChatConversation.user.has(User.is_admin.is_(False)),
                ).first()

                if unavailable_conversation is not None:
                    flash(
                        "This chat has been taken by another admin.",
                        "info",
                    )
                    return redirect(url_for("chat"))

                flash("This chat is no longer active.", "info")
                return redirect(url_for("chat"))
        elif conversations:
            active_conversation = conversations[0]
    else:
        active_conversation = ChatConversation.query.filter_by(
            user_id=current_user.id,
        ).first()

        if active_conversation is None:
            active_conversation = ChatConversation(
                user_id=current_user.id,
            )
            db.session.add(active_conversation)
            db.session.commit()

    messages = []
    unread_message_counts = {}

    admin_can_reply = (
        active_conversation is not None
        and active_conversation.resolution_requested_at is None
        and (
            not current_user.is_admin
            or active_conversation.assigned_admin_id == current_user.id
        )
    )

    if active_conversation:
        messages = ChatMessage.query.filter_by(
            conversation_id=active_conversation.id,
        ).order_by(
            ChatMessage.created_at.asc(),
        ).all()

        if admin_can_reply:
            ChatMessage.query.filter(
                ChatMessage.conversation_id == active_conversation.id,
                ChatMessage.sender_id != current_user.id,
                ChatMessage.is_read.is_(False),
            ).update(
                {"is_read": True},
                synchronize_session=False,
            )
            db.session.commit()

    if current_user.is_admin and conversations:
        unread_message_counts = dict(
            db.session.query(
                ChatMessage.conversation_id,
                func.count(ChatMessage.id),
            ).filter(
                ChatMessage.conversation_id.in_(
                    [conversation.id for conversation in conversations]
                ),
                ChatMessage.sender_id != current_user.id,
                ChatMessage.is_read.is_(False),
            ).group_by(
                ChatMessage.conversation_id,
            ).all()
        )

    return render_template(
        "chat.html",
        conversations=conversations,
        active_conversation=active_conversation,
        admin_can_reply=admin_can_reply,
        messages=messages,
        unread_message_counts=unread_message_counts,
    )


@app.route(
    "/chat/<int:conversation_id>/claim",
    methods=["POST"],
)
@admin_required
def claim_chat_conversation(conversation_id):

    conversation = ChatConversation.query.filter(
        ChatConversation.id == conversation_id,
        ChatConversation.user.has(User.is_admin.is_(False)),
    ).first()

    if conversation is None:
        flash("This chat has already been closed.", "info")
        return redirect(url_for("chat"))

    if conversation.assigned_admin_id == current_user.id:
        flash("This chat is already assigned to you.", "info")
    elif conversation.assigned_admin_id is not None:
        flash("Another admin is already attending to this chat.", "danger")
    else:
        claimed = ChatConversation.query.filter(
            ChatConversation.id == conversation.id,
            ChatConversation.assigned_admin_id.is_(None),
        ).update(
            {
                "assigned_admin_id": current_user.id,
                "assigned_at": datetime.utcnow(),
            },
            synchronize_session=False,
        )

        if claimed:
            db.session.commit()
            flash("You are now attending to this chat.", "success")
        else:
            db.session.rollback()
            flash("Another admin claimed this chat first.", "danger")

    if conversation.assigned_admin_id == current_user.id:
        return redirect(url_for("chat", conversation=conversation_id))

    return redirect(url_for("chat"))


@app.route(
    "/chat/<int:conversation_id>/release",
    methods=["POST"],
)
@admin_required
def release_chat_conversation(conversation_id):

    conversation = ChatConversation.query.filter(
        ChatConversation.id == conversation_id,
        ChatConversation.user.has(User.is_admin.is_(False)),
    ).first()

    if conversation is None:
        flash("This chat has already been closed.", "info")
        return redirect(url_for("chat"))

    if conversation.assigned_admin_id != current_user.id:
        flash("Only the assigned admin can release this chat.", "danger")
    else:
        conversation.assigned_admin_id = None
        conversation.assigned_at = None
        db.session.commit()
        flash("This chat is available for another admin.", "success")

    return redirect(
        url_for("chat", conversation=conversation_id)
    )


@app.route("/chat/<int:conversation_id>/request-feedback", methods=["POST"])
@admin_required
def request_chat_feedback(conversation_id):

    conversation = ChatConversation.query.filter(
        ChatConversation.id == conversation_id,
        ChatConversation.user.has(User.is_admin.is_(False)),
    ).first()

    if conversation is None:
        flash("This chat has already been closed.", "info")
        return redirect(url_for("chat"))

    if conversation.assigned_admin_id != current_user.id:
        flash("This chat is being handled by another admin.", "info")
        return redirect(url_for("chat"))

    if conversation.resolution_requested_at is None:
        conversation.resolution_requested_at = datetime.utcnow()
        conversation.last_message_at = datetime.utcnow()
        db.session.commit()
        flash("Feedback requested. The staff member can now rate this support chat.", "success")
    else:
        flash("This chat is already awaiting feedback.", "info")

    return redirect(url_for("chat", conversation=conversation.id))


@app.route("/chat/<int:conversation_id>/close", methods=["POST"])
@admin_required
def close_chat_conversation(conversation_id):
    conversation = ChatConversation.query.filter(
        ChatConversation.id == conversation_id,
        ChatConversation.user.has(User.is_admin.is_(False)),
    ).first()

    # A second tab (or the staff member's rating submission) may have already
    # removed this conversation.  Treat that as a completed action instead of
    # sending the administrator to a 404 page.
    if conversation is None:
        flash("This chat has already been closed.", "info")
        return redirect(url_for("chat"))

    if conversation.assigned_admin_id != current_user.id:
        flash("This chat is being handled by another admin.", "info")
        return redirect(url_for("chat"))

    if conversation.resolution_requested_at is None:
        flash("Request staff feedback before closing this chat.", "info")
        return redirect(url_for("chat", conversation=conversation.id))

    db.session.delete(conversation)
    db.session.commit()
    flash("The completed chat and its messages were deleted.", "success")
    return redirect(url_for("chat"))


@app.route("/chat/<int:conversation_id>/feedback", methods=["POST"])
@login_required
def submit_chat_feedback(conversation_id):

    if current_user.is_admin:
        abort(403)

    rating = request.form.get("rating", type=int)

    if rating not in {1, 2, 3, 4, 5}:
        flash("Please choose a rating from one to five stars.", "danger")
        return redirect(url_for("chat"))

    conversation = ChatConversation.query.filter(
        ChatConversation.id == conversation_id,
        ChatConversation.user_id == current_user.id,
    ).first()

    if conversation is None:
        flash("This chat has already been closed.", "info")
        return redirect(url_for("chat"))

    if (
        conversation.resolution_requested_at is None
        or conversation.assigned_admin_id is None
    ):
        flash(
            "This chat is no longer awaiting feedback.",
            "info",
        )
        return redirect(url_for("chat"))

    db.session.add(ChatSatisfactionRating(
        user_id=current_user.id,
        admin_id=conversation.assigned_admin_id,
        rating=rating,
    ))
    db.session.delete(conversation)
    db.session.commit()

    flash("Thanks for your feedback. This chat has now been closed.", "success")
    return redirect(url_for("chat"))


@app.route("/chat/<int:conversation_id>/continue", methods=["POST"])
@login_required
def continue_chat_conversation(conversation_id):

    if current_user.is_admin:
        abort(403)

    conversation = ChatConversation.query.filter(
        ChatConversation.id == conversation_id,
        ChatConversation.user_id == current_user.id,
    ).first()

    if conversation is None:
        flash("This chat has already been closed.", "info")
        return redirect(url_for("chat"))

    if conversation.resolution_requested_at is None:
        flash("This chat is already open for support.", "info")
        return redirect(url_for("chat", conversation=conversation.id))

    conversation.resolution_requested_at = None
    conversation.last_message_at = datetime.utcnow()
    db.session.commit()

    flash("The chat has been reopened so you can continue with support.", "info")
    return redirect(url_for("chat"))


@app.route(
    "/chat/send",
    methods=["POST"],
)
@login_required
def send_chat_message():

    validate_csrf_token()

    clear_inactive_chat_conversations()

    message = request.form.get(
        "message",
        "",
    ).strip()

    if not message or len(message) > 2000:
        flash(
            "Chat messages must contain between 1 and 2,000 characters.",
            "danger",
        )

        return redirect(
            url_for("chat")
        )

    if current_user.is_admin:
        conversation_id = request.form.get(
            "conversation_id",
            type=int,
        )
        conversation = db.session.get(
            ChatConversation,
            conversation_id,
        )

        if (
            conversation is None
            or conversation.user.is_admin
            or conversation.resolution_requested_at is not None
        ):
            abort(404)

        if conversation.assigned_admin_id != current_user.id:
            flash(
                "Claim this chat before replying.",
                "danger",
            )
            return redirect(
                url_for(
                    "chat",
                    conversation=conversation.id,
                )
            )
    else:
        conversation = ChatConversation.query.filter_by(
            user_id=current_user.id,
        ).first()

        if conversation is None:
            conversation = ChatConversation(
                user_id=current_user.id,
            )
            db.session.add(conversation)
            db.session.flush()

    db.session.add(
        ChatMessage(
            message=message,
            conversation_id=conversation.id,
            sender_id=current_user.id,
        )
    )
    conversation.last_message_at = datetime.utcnow()
    db.session.commit()

    return redirect(
        url_for(
            "chat",
            conversation=(
                conversation.id
                if current_user.is_admin
                else None
            ),
        )
    )


# -------------------------
# GUEST WIFI
# -------------------------

@app.route("/guest")
@login_required
def guest():

    return render_template(
        "guest.html"
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin")
@admin_required
def admin_dashboard():
    now = datetime.utcnow()
    due_soon_cutoff = now + timedelta(hours=24)
    total_tickets = Ticket.query.count()

    open_tickets = Ticket.query.filter_by(
        status="Open"
    ).count()

    in_progress_tickets = Ticket.query.filter_by(
        status="In Progress"
    ).count()

    resolved_tickets = Ticket.query.filter_by(
        status="Resolved"
    ).count()

    overdue_tickets = Ticket.query.filter(
        Ticket.status != "Resolved",
        Ticket.due_at.isnot(None),
        Ticket.due_at < now,
    ).count()

    due_soon_tickets = Ticket.query.filter(
        Ticket.status != "Resolved",
        Ticket.due_at.isnot(None),
        Ticket.due_at >= now,
        Ticket.due_at <= due_soon_cutoff,
    ).count()

    critical_open_tickets = Ticket.query.filter(
        Ticket.priority == "Critical",
        Ticket.status != "Resolved",
    ).count()

    tickets_created_this_week = Ticket.query.filter(
        Ticket.created_at >= now - timedelta(days=7),
    ).count()

    category_breakdown = db.session.query(
        Ticket.category,
        func.count(Ticket.id),
    ).group_by(Ticket.category).order_by(
        func.count(Ticket.id).desc(),
        Ticket.category.asc(),
    ).all()

    satisfaction_count = ChatSatisfactionRating.query.count()
    average_satisfaction = db.session.query(
        func.avg(ChatSatisfactionRating.rating),
    ).scalar()

    recent_tickets = Ticket.query.order_by(
        Ticket.created_at.desc()
    ).limit(10).all()

    return render_template(
        "admin/dashboard.html",
        total_tickets=total_tickets,
        open_tickets=open_tickets,
        in_progress_tickets=in_progress_tickets,
        resolved_tickets=resolved_tickets,
        overdue_tickets=overdue_tickets,
        due_soon_tickets=due_soon_tickets,
        critical_open_tickets=critical_open_tickets,
        tickets_created_this_week=tickets_created_this_week,
        category_breakdown=category_breakdown,
        satisfaction_count=satisfaction_count,
        average_satisfaction=average_satisfaction,
        recent_tickets=recent_tickets,
    )


# =========================================================
# ADMIN TICKET MANAGEMENT
# =========================================================

# -------------------------
# ALL TICKET QUEUES
# -------------------------

@app.route("/admin/tickets")
@admin_required
def admin_tickets():

    # Get filter values from the URL
    search = request.args.get(
        "search",
        "",
    ).strip()

    status_filter = request.args.get(
        "status",
        "",
    ).strip()

    priority_filter = request.args.get(
        "priority",
        "",
    ).strip()

    category_filter = request.args.get(
        "category",
        "",
    ).strip()

    # Start with every ticket
    query = Ticket.query.join(User)

    # ---------------------------------
    # SEARCH
    # ---------------------------------

    if search:

        search_term = f"%{search}%"

        query = query.filter(
            or_(
                Ticket.subject.ilike(search_term),
                User.username.ilike(search_term),
                User.email.ilike(search_term),
            )
        )

    # ---------------------------------
    # PRIORITY FILTER
    # ---------------------------------

    allowed_priorities = [
        "Low",
        "Medium",
        "High",
        "Critical",
    ]

    if priority_filter in allowed_priorities:

        query = query.filter(
            Ticket.priority == priority_filter
        )

    # ---------------------------------
    # CATEGORY FILTER
    # ---------------------------------

    if category_filter in TICKET_CATEGORIES:

        query = query.filter(
            Ticket.category == category_filter
        )

    # ---------------------------------
    # STATUS FILTER
    # ---------------------------------

    allowed_statuses = [
        "Open",
        "In Progress",
        "Resolved",
    ]

    if status_filter in allowed_statuses:

        query = query.filter(
            Ticket.status == status_filter
        )

    # ---------------------------------
    # GET FILTERED TICKETS
    # ---------------------------------

    filtered_tickets = query.order_by(
        Ticket.created_at.desc()
    ).all()

    # Keep your current queue layout
    open_tickets = [
        ticket
        for ticket in filtered_tickets
        if ticket.status == "Open"
    ]

    in_progress_tickets = [
        ticket
        for ticket in filtered_tickets
        if ticket.status == "In Progress"
    ]

    resolved_tickets = [
        ticket
        for ticket in filtered_tickets
        if ticket.status == "Resolved"
    ]

    return render_template(
        "admin/tickets.html",

        open_tickets=open_tickets,
        in_progress_tickets=in_progress_tickets,
        resolved_tickets=resolved_tickets,

        search=search,
        status_filter=status_filter,
        priority_filter=priority_filter,
        category_filter=category_filter,
        ticket_categories=TICKET_CATEGORIES,
    )
# -------------------------
# ADMIN TICKET DETAILS
# -------------------------


@app.route("/admin/ticket/<int:ticket_id>")
@admin_required
def admin_ticket_details(ticket_id):

    ticket = Ticket.query.get_or_404(
        ticket_id
    )

    replies = TicketReply.query.filter_by(
        ticket_id=ticket.id
    ).order_by(
        TicketReply.created_at.asc()
    ).all()

    status_history = TicketStatusHistory.query.filter_by(ticket_id=ticket.id).order_by(
        TicketStatusHistory.created_at.desc(),
    ).all()

    if ticket.due_at is None:
        sla_state = "No due date"
    elif ticket.status == "Resolved":
        sla_state = "Resolved"
    elif ticket.due_at < datetime.utcnow():
        sla_state = "Overdue"
    elif ticket.due_at <= datetime.utcnow() + timedelta(hours=24):
        sla_state = "Due soon"
    else:
        sla_state = "On track"

    return render_template(
        "admin/ticket_details.html",
        ticket=ticket,
        replies=replies,
        status_history=status_history,
        sla_state=sla_state,
    )


# -------------------------
# ADMIN UPDATE TICKET STATUS
# -------------------------

@app.route(
    "/admin/ticket/<int:ticket_id>/status",
    methods=["POST"],
)
@admin_required
def admin_update_ticket_status(ticket_id):

    ticket = Ticket.query.get_or_404(
        ticket_id
    )

    new_status = request.form.get(
        "status"
    )

    allowed_statuses = [
        "Open",
        "In Progress",
        "Resolved",
    ]

    if new_status not in allowed_statuses:

        flash(
            "Invalid ticket status.",
            "danger",
        )

        return redirect(
            url_for(
                "admin_ticket_details",
                ticket_id=ticket.id,
            )
        )

    previous_status = ticket.status

    ticket.status = new_status

    if previous_status != new_status:
        db.session.add(TicketStatusHistory(
            ticket_id=ticket.id,
            changed_by_id=current_user.id,
            previous_status=previous_status,
            new_status=new_status,
        ))

    if (
        new_status == "Resolved"
        and previous_status != "Resolved"
        and ticket.user.is_active
    ):
        create_notification(
            recipient_id=ticket.user_id,
            ticket_id=ticket.id,
            message=(
                f"Your ticket HDP-{ticket.ticket_number:04d} "
                "has been resolved."
            ),
        )

    db.session.commit()

    flash(
        f"Ticket #{ticket.ticket_number:04d} updated to {new_status}.",
        "success",
    )

    return redirect(
        url_for(
            "admin_ticket_details",
            ticket_id=ticket.id,
        )
    )


@app.route("/admin/ticket/<int:ticket_id>/due-date", methods=["POST"])
@admin_required
def update_ticket_due_date(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    value = request.form.get("due_at", "").strip()
    if not value:
        ticket.due_at = None
    else:
        try:
            ticket.due_at = datetime.strptime(value, "%Y-%m-%dT%H:%M")
        except ValueError:
            flash("Choose a valid due date and time.", "danger")
            return redirect(url_for("admin_ticket_details", ticket_id=ticket.id))
    db.session.commit()
    flash("Due date updated.", "success")
    return redirect(url_for("admin_ticket_details", ticket_id=ticket.id))


@app.route(
    "/admin/ticket/<int:ticket_id>/progress-update",
    methods=["POST"],
)
@admin_required
def admin_ticket_progress_update(ticket_id):

    ticket = Ticket.query.get_or_404(ticket_id)
    update_type = request.form.get("update_type", "")
    additional_note = request.form.get("additional_note", "").strip()

    if ticket.status == "Resolved":
        flash("Reopen this ticket before sending a progress update.", "danger")
        return redirect(
            url_for("admin_ticket_details", ticket_id=ticket.id)
        )

    if update_type not in TICKET_PROGRESS_UPDATES:
        flash("Choose a valid progress update.", "danger")
        return redirect(
            url_for("admin_ticket_details", ticket_id=ticket.id)
        )

    if len(additional_note) > 1000:
        flash("Keep the additional note below 1,000 characters.", "danger")
        return redirect(
            url_for("admin_ticket_details", ticket_id=ticket.id)
        )

    message = TICKET_PROGRESS_UPDATES[update_type]

    if additional_note:
        message = f"{message}\n\n{additional_note}"

    db.session.add(
        TicketReply(
            message=message,
            ticket_id=ticket.id,
            user_id=current_user.id,
        )
    )
    ticket.status = "In Progress"

    if ticket.user.is_active:
        create_notification(
            recipient_id=ticket.user_id,
            ticket_id=ticket.id,
            message=(
                f"Support posted a progress update on ticket "
                f"HDP-{ticket.ticket_number:04d}."
            ),
        )

    db.session.commit()
    flash("Progress update sent to the user.", "success")

    return redirect(
        url_for("admin_ticket_details", ticket_id=ticket.id)
    )


# -------------------------
# ADMIN REPLY TO TICKET
# -------------------------

@app.route(
    "/admin/ticket/<int:ticket_id>/reply",
    methods=["POST"],
)
@admin_required
def admin_reply_to_ticket(ticket_id):

    ticket = Ticket.query.get_or_404(
        ticket_id
    )

    message = request.form.get(
        "message",
        "",
    ).strip()

    if not message:

        flash(
            "Reply cannot be empty.",
            "danger",
        )

        return redirect(
            url_for(
                "admin_ticket_details",
                ticket_id=ticket.id,
            )
        )

    reply = TicketReply(
        message=message,
        ticket_id=ticket.id,
        user_id=current_user.id,
    )

    db.session.add(reply)

    if ticket.user_id != current_user.id and ticket.user.is_active:
        create_notification(
            recipient_id=ticket.user_id,
            ticket_id=ticket.id,
            message=(
                f"Support replied to your ticket "
                f"HDP-{ticket.ticket_number:04d}."
            ),
        )

    db.session.commit()

    flash(
        "Reply sent successfully.",
        "success",
    )

    return redirect(
        url_for(
            "admin_ticket_details",
            ticket_id=ticket.id,
        )
    )


@app.route("/admin/ticket/<int:ticket_id>/internal-note", methods=["POST"])
@admin_required
def add_ticket_internal_note(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    message = request.form.get("message", "").strip()

    if not message:
        flash("Internal note cannot be empty.", "danger")
    elif len(message) > 2000:
        flash("Keep internal notes below 2,000 characters.", "danger")
    else:
        db.session.add(TicketInternalNote(
            ticket_id=ticket.id,
            author_id=current_user.id,
            message=message,
        ))
        db.session.commit()
        flash("Internal note saved. Staff cannot see it.", "success")

    return redirect(url_for("admin_ticket_details", ticket_id=ticket.id))


@app.route("/admin/ticket/<int:ticket_id>/tags", methods=["POST"])
@admin_required
def update_ticket_tags(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    requested_tags = {
        tag.strip().lower()
        for tag in request.form.get("tags", "").split(",")
        if tag.strip()
    }

    if any(len(tag) > 40 for tag in requested_tags):
        flash("Each tag must be 40 characters or fewer.", "danger")
        return redirect(url_for("admin_ticket_details", ticket_id=ticket.id))

    TicketTag.query.filter_by(ticket_id=ticket.id).delete()
    db.session.add_all([TicketTag(ticket_id=ticket.id, name=tag) for tag in requested_tags])
    db.session.commit()
    flash("Ticket tags updated.", "success")
    return redirect(url_for("admin_ticket_details", ticket_id=ticket.id))


# =========================================================
# ADMIN USER MANAGEMENT
# =========================================================

# -------------------------
# MANAGE USERS
# -------------------------

@app.route("/admin/users")
@admin_required
def admin_users():

    search = request.args.get("search", "").strip()
    users_query = User.query

    if search:
        search_term = f"%{search}%"
        user_filters = [
            User.username.ilike(search_term),
            User.email.ilike(search_term),
        ]

        if search.isdigit():
            user_filters.append(User.id == int(search))

        users_query = users_query.filter(or_(*user_filters))

    users = users_query.order_by(
        User.id.desc()
    ).all()

    return render_template(
        "admin/users.html",
        users=users,
        search=search,
    )


# -------------------------
# ADD USER
# -------------------------

@app.route(
    "/admin/users/add",
    methods=["GET", "POST"],
)
@admin_required
def add_user():

    if request.method == "POST":

        username = request.form["username"].strip()
        email = request.form["email"].strip()
        password = request.form["password"]
        role = request.form["role"]

        existing_user = User.query.filter_by(
            email=email
        ).first()

        if existing_user:

            flash(
                "An account with that email already exists.",
                "danger",
            )

            return redirect(
                url_for("add_user")
            )

        if role not in ["user", "admin"]:

            flash(
                "Invalid account role.",
                "danger",
            )

            return redirect(
                url_for("add_user")
            )

        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
            is_admin=(role == "admin"),
            is_active=True,
        )

        db.session.add(new_user)
        db.session.commit()

        flash(
            f"{username} was created successfully.",
            "success",
        )

        return redirect(
            url_for("admin_users")
        )

    return render_template(
        "admin/add_user.html"
    )


# -------------------------
# EDIT USER
# -------------------------

@app.route(
    "/admin/users/<int:user_id>/edit",
    methods=["GET", "POST"],
)
@admin_required
def edit_user(user_id):

    user = User.query.get_or_404(
        user_id
    )

    if request.method == "POST":

        username = request.form["username"].strip()
        email = request.form["email"].strip()
        role = request.form["role"]

        new_password = request.form.get(
            "new_password",
            "",
        ).strip()

        existing_user = User.query.filter(
            User.email == email,
            User.id != user.id,
        ).first()

        if existing_user:

            flash(
                "Another account already uses that email.",
                "danger",
            )

            return redirect(
                url_for(
                    "edit_user",
                    user_id=user.id,
                )
            )

        if role not in ["user", "admin"]:

            flash(
                "Invalid account role.",
                "danger",
            )

            return redirect(
                url_for(
                    "edit_user",
                    user_id=user.id,
                )
            )

        new_is_admin = role == "admin"

        # Prevent the system from ending up with zero administrators.
        if user.is_admin and not new_is_admin:

            admin_count = User.query.filter_by(
                is_admin=True
            ).count()

            if admin_count <= 1:

                flash(
                    "You cannot demote the last administrator.",
                    "danger",
                )

                return redirect(
                    url_for(
                        "edit_user",
                        user_id=user.id,
                    )
                )

        user.username = username
        user.email = email
        user.is_admin = new_is_admin

        if new_password:
            user.password = generate_password_hash(
                new_password
            )

        db.session.commit()

        flash(
            f"{user.username}'s account was updated successfully.",
            "success",
        )

        return redirect(
            url_for("admin_users")
        )

    return render_template(
        "admin/edit_user.html",
        user=user,
    )


# -------------------------
# ACTIVATE / DEACTIVATE USER
# -------------------------

@app.route(
    "/admin/users/<int:user_id>/toggle-status",
    methods=["POST"],
)
@admin_required
def toggle_user_status(user_id):

    user = User.query.get_or_404(
        user_id
    )

    # Do not allow the logged-in admin to disable themselves.
    if user.id == current_user.id:

        flash(
            "You cannot deactivate your own account.",
            "danger",
        )

        return redirect(
            url_for("admin_users")
        )

    # If an active admin is being deactivated, ensure another
    # active administrator will remain available.
    if user.is_admin and user.is_active:

        active_admin_count = User.query.filter_by(
            is_admin=True,
            is_active=True,
        ).count()

        if active_admin_count <= 1:

            flash(
                "You cannot deactivate the last active administrator.",
                "danger",
            )

            return redirect(
                url_for("admin_users")
            )

    user.is_active = not user.is_active

    if user.is_admin and not user.is_active:
        ChatConversation.query.filter_by(
            assigned_admin_id=user.id,
        ).update(
            {
                "assigned_admin_id": None,
                "assigned_at": None,
            },
            synchronize_session=False,
        )


    db.session.commit()

    status = (
        "activated"
        if user.is_active
        else "deactivated"
    )

    flash(
        f"{user.username}'s account has been {status}.",
        "success",
    )

    return redirect(
        url_for("admin_users")
    )

# -------------------------
# DELETE USER
# -------------------------


@app.route(
    "/admin/users/<int:user_id>/delete",
    methods=["POST"],
)
@admin_required
def delete_user(user_id):

    user = User.query.get_or_404(
        user_id
    )

    # Never allow an administrator to delete their own account.
    if user.id == current_user.id:

        flash(
            "You cannot delete your own administrator account.",
            "danger",
        )

        return redirect(
            url_for("admin_users")
        )

    # Never allow the final administrator account to be deleted.
    if user.is_admin:

        admin_count = User.query.filter_by(
            is_admin=True
        ).count()

        if admin_count <= 1:

            flash(
                "You cannot delete the last administrator.",
                "danger",
            )

            return redirect(
                url_for("admin_users")
            )

        # If the admin being deleted is active, make sure
        # another active administrator will remain.
        if user.is_active:

            active_admin_count = User.query.filter_by(
                is_admin=True,
                is_active=True,
            ).count()

            if active_admin_count <= 1:

                flash(
                    "You cannot delete the last active administrator.",
                    "danger",
                )

                return redirect(
                    url_for("admin_users")
                )

    username = user.username

    try:

        # ---------------------------------
        # RELEASE CHAT ASSIGNMENTS
        # ---------------------------------

        ChatConversation.query.filter_by(
            assigned_admin_id=user.id,
        ).update(
            {
                "assigned_admin_id": None,
                "assigned_at": None,
            },
            synchronize_session=False,
        )


        # ---------------------------------
        # PASSWORD RESET TOKENS
        # ---------------------------------

        PasswordResetToken.query.filter_by(
            user_id=user.id
        ).delete(
            synchronize_session=False
        )

        ChatSatisfactionRating.query.filter(
            or_(
                ChatSatisfactionRating.user_id == user.id,
                ChatSatisfactionRating.admin_id == user.id,
            )
        ).delete(
            synchronize_session=False
        )

        # ---------------------------------
        # NOTIFICATIONS RECEIVED BY USER
        # ---------------------------------

        Notification.query.filter_by(
            recipient_id=user.id
        ).delete(
            synchronize_session=False
        )

        # ---------------------------------
        # REPLIES AUTHORED BY USER
        # ---------------------------------

        TicketReply.query.filter_by(
            user_id=user.id
        ).delete(
            synchronize_session=False
        )

        # ---------------------------------
        # CHAT MESSAGES SENT BY USER
        # ---------------------------------

        ChatMessage.query.filter_by(
            sender_id=user.id
        ).delete(
            synchronize_session=False
        )

        # ---------------------------------
        # USER'S CHAT CONVERSATION
        # ---------------------------------

        owned_conversations = ChatConversation.query.filter_by(
            user_id=user.id
        ).all()

        for conversation in owned_conversations:
            db.session.delete(conversation)

        # ---------------------------------
        # USER'S TICKETS
        # ---------------------------------

        owned_tickets = Ticket.query.filter_by(
            user_id=user.id
        ).all()

        for ticket in owned_tickets:
            db.session.delete(ticket)

        # ---------------------------------
        # KNOWLEDGE ARTICLES AUTHORED BY USER
        # ---------------------------------

        authored_articles = KnowledgeArticle.query.filter_by(
            author_id=user.id
        ).all()

        for article in authored_articles:
            db.session.delete(article)

        # ---------------------------------
        # DELETE USER ACCOUNT
        # ---------------------------------

        db.session.delete(user)
        db.session.commit()

    except Exception:

        db.session.rollback()

        app.logger.exception(
            "Failed to delete user account ID %s",
            user_id,
        )

        flash(
            "The account could not be deleted. No changes were saved.",
            "danger",
        )

        return redirect(
            url_for("admin_users")
        )

    flash(
        f"{username}'s account was permanently deleted.",
        "success",
    )

    return redirect(
        url_for("admin_users")
    )
# =========================================================
# LOGOUT
# =========================================================


@app.route("/logout")
@login_required
def logout():

    logout_user()

    return redirect(
        url_for("login")
    )


# =========================================================
# DATABASE INITIALIZATION / DEVELOPMENT SERVER
# =========================================================

def ensure_database_schema():

    db.create_all()

    if db.engine.dialect.name != "sqlite":
        return

    schema_changed = False

    ticket_columns = db.session.execute(
        text("PRAGMA table_info(ticket)")
    ).mappings().all()

    if "category" not in {
        column["name"]
        for column in ticket_columns
    }:
        db.session.execute(
            text(
                "ALTER TABLE ticket "
                "ADD COLUMN category VARCHAR(50) "
                "NOT NULL DEFAULT 'Other'"
            )
        )
        schema_changed = True

    chat_columns = db.session.execute(
        text("PRAGMA table_info(chat_conversation)")
    ).mappings().all()

    existing_chat_columns = {
        column["name"]
        for column in chat_columns
    }

    if "assigned_admin_id" not in existing_chat_columns:
        db.session.execute(
            text(
                "ALTER TABLE chat_conversation "
                "ADD COLUMN assigned_admin_id INTEGER "
                "REFERENCES user(id)"
            )
        )
        schema_changed = True

    if "assigned_at" not in existing_chat_columns:
        db.session.execute(
            text(
                "ALTER TABLE chat_conversation "
                "ADD COLUMN assigned_at DATETIME"
            )
        )
        schema_changed = True

    if "resolution_requested_at" not in existing_chat_columns:
        db.session.execute(
            text(
                "ALTER TABLE chat_conversation "
                "ADD COLUMN resolution_requested_at DATETIME"
            )
        )
        schema_changed = True

    if schema_changed:
        db.session.commit()


@app.cli.command("init-db")
def initialize_database():

    ensure_database_schema()

    print("Database tables are ready.")


if __name__ == "__main__":

    with app.app_context():
        ensure_database_schema()

    app.run(debug=True)
