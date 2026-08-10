from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash


# =========================================================
# Flask Application
# =========================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = "helpdeskpro_secret_key"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///helpdesk.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


# =========================================================
# Database
# =========================================================

db = SQLAlchemy(app)


# =========================================================
# Flask Login
# =========================================================

login_manager = LoginManager()

login_manager.init_app(app)

login_manager.login_view = "login"


# =========================================================
# User Model
# =========================================================

class User(UserMixin, db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    username = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(255),
        nullable=False
    )

    def __repr__(self):

        return f"<User {self.username}>"
    is_admin = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )


# =========================================================
# Ticket Model
# =========================================================

class Ticket(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    subject = db.Column(
        db.String(200),
        nullable=False
    )

    description = db.Column(
        db.Text,
        nullable=False
    )

    priority = db.Column(
        db.String(20),
        nullable=False,
        default="Medium"
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="Open"
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "tickets",
            lazy=True
        )
    )

    def __repr__(self):

        return f"<Ticket {self.id}: {self.subject}>"


# =========================================================
# Flask-Login User Loader
# =========================================================

@login_manager.user_loader
def load_user(user_id):

    return User.query.get(int(user_id))


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template(
        "home.html"
    )


# =========================================================
# LOGIN
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form["email"]

        password = request.form["password"]

        # Find user by email
        user = User.query.filter_by(
            email=email
        ).first()

        # Verify password
        if user and check_password_hash(
            user.password,
            password
        ):

            login_user(user)

            return redirect(
                url_for("dashboard")
            )

        flash(
            "Invalid email or password.",
            "danger"
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "auth/login.html"
    )


# =========================================================
# FORGOT PASSWORD
# =========================================================

@app.route(
    "/forgot-password",
    methods=["GET", "POST"]
)
def forgot_password():

    if request.method == "POST":

        email = request.form["email"]

        # Actual email reset functionality
        # will be added later.

        flash(
            "If an account with that email exists, "
            "a password reset link has been sent.",
            "success"
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "auth/forgot_password.html"
    )


# =========================================================
# REGISTER
# =========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        username = request.form["username"]

        email = request.form["email"]

        password = request.form["password"]

        confirm_password = request.form.get(
            "confirm_password"
        )

        # Check passwords match
        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "danger"
            )

            return redirect(
                url_for("register")
            )

        # Check if email already exists
        existing_user = User.query.filter_by(
            email=email
        ).first()

        if existing_user:

            flash(
                "Email already registered. Please login instead.",
                "danger"
            )

            return redirect(
                url_for("login")
            )

        # Hash password
        hashed_password = generate_password_hash(
            password
        )

        # Create user
        new_user = User(
            username=username,
            email=email,
            password=hashed_password
        )

        # Save to database
        db.session.add(new_user)

        db.session.commit()

        flash(
            "Registration successful! Please login.",
            "success"
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "auth/register.html"
    )


# =========================================================
# GUEST
# =========================================================

@app.route("/guest")
def guest():

    return render_template(
        "guest.html"
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
@login_required
def dashboard():

    # Get current user's tickets
    tickets = Ticket.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Ticket.created_at.desc()
    ).all()

    # Total tickets
    total_tickets = Ticket.query.filter_by(
        user_id=current_user.id
    ).count()

    # Open tickets
    open_tickets = Ticket.query.filter_by(
        user_id=current_user.id,
        status="Open"
    ).count()

    # In-progress tickets
    in_progress_tickets = Ticket.query.filter_by(
        user_id=current_user.id,
        status="In Progress"
    ).count()

    # Resolved tickets
    resolved_tickets = Ticket.query.filter_by(
        user_id=current_user.id,
        status="Resolved"
    ).count()

    return render_template(
        "dashboard/dashboard.html",
        tickets=tickets,
        total_tickets=total_tickets,
        open_tickets=open_tickets,
        in_progress_tickets=in_progress_tickets,
        resolved_tickets=resolved_tickets
    )


# =========================================================
# CREATE TICKET
# =========================================================

@app.route("/create-ticket", methods=["GET", "POST"])
@login_required
def create_ticket():

    if request.method == "POST":

        subject = request.form["subject"]
        description = request.form["description"]
        priority = request.form["priority"]

        new_ticket = Ticket(
            subject=subject,
            description=description,
            priority=priority,
            status="Open",
            user_id=current_user.id
        )

        db.session.add(new_ticket)
        db.session.commit()

        flash(
            "Ticket created successfully!",
            "success"
        )

        return redirect(url_for("tickets"))

    return render_template("create_ticket.html")

# =========================================================
# CHAT
# =========================================================


@app.route("/chat")
def chat():

    return render_template(
        "chat.html"
    )


# =========================================================
# TICKETS
# =========================================================

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
        tickets=user_tickets
    )


@app.route("/ticket/<int:ticket_id>")
@login_required
def ticket_details(ticket_id):

    ticket = Ticket.query.get_or_404(ticket_id)

    # Only allow the ticket owner to view their ticket
    if ticket.user_id != current_user.id:

        flash(
            "You do not have permission to view this ticket.",
            "danger"
        )

        return redirect(url_for("tickets"))

    return render_template(
        "ticket_details.html",
        ticket=ticket
    )


@app.route("/ticket/<int:ticket_id>/status", methods=["POST"])
@login_required
def update_ticket_status(ticket_id):

    ticket = Ticket.query.get_or_404(ticket_id)

    # Only the ticket owner can update their ticket for now
    if ticket.user_id != current_user.id:

        flash(
            "You do not have permission to update this ticket.",
            "danger"
        )

        return redirect(url_for("tickets"))

    new_status = request.form.get("status")

    allowed_statuses = [
        "Open",
        "In Progress",
        "Resolved"
    ]

    if new_status not in allowed_statuses:

        flash(
            "Invalid ticket status.",
            "danger"
        )

        return redirect(
            url_for("ticket_details", ticket_id=ticket.id)
        )

    ticket.status = new_status

    db.session.commit()

    flash(
        f"Ticket #{ticket.id} status updated to {new_status}.",
        "success"
    )

    return redirect(
        url_for("ticket_details", ticket_id=ticket.id)
    )
# =========================================================
# KNOWLEDGE BASE
# =========================================================


@app.route("/knowledge")
def knowledge():

    return render_template(
        "knowledge.html"
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
# SETTINGS
# =========================================================


@app.route("/settings")
@login_required
def settings():

    return render_template(
        "settings.html"
    )
# =========================================================
# data base deleter
# =========================================================


# @app.route("/clear-tickets")
# @login_required
# def clear_tickets():

    Ticket.query.delete()

    db.session.commit()

    flash("All test tickets have been deleted.", "success")

    return redirect(url_for("tickets"))

# =========================================================
# DATABASE INITIALIZATION
# =========================================================


if __name__ == "__main__":

    with app.app_context():

        db.create_all()

    app.run(
        debug=True
    )
