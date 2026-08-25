from sqlalchemy import text, or_
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
)

from flask_sqlalchemy import SQLAlchemy

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


# =========================================================
# APPLICATION SETUP
# =========================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = "helpdeskpro_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///helpdesk.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


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

    status = db.Column(
        db.String(20),
        nullable=False,
        default="Open",
    )

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

        email = request.form["email"]
        password = request.form["password"]

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

        # Placeholder flow only.
        # Real email/token password reset can be added later.
        email = request.form["email"]

        flash(
            "If an account with that email exists, "
            "a password reset link has been sent.",
            "success",
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "auth/forgot_password.html"
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

        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

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
        "create_ticket.html"
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

    return render_template(
        "ticket_details.html",
        ticket=ticket,
        replies=replies,
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
# KNOWLEDGE BASE
# -------------------------


@app.route("/knowledge")
@login_required
def knowledge():

    return render_template(
        "knowledge.html"
    )


# -------------------------
# LIVE CHAT
# -------------------------

@app.route("/chat")
@login_required
def chat():

    return render_template(
        "chat.html"
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

    recent_tickets = Ticket.query.order_by(
        Ticket.created_at.desc()
    ).limit(10).all()

    return render_template(
        "admin/dashboard.html",
        total_tickets=total_tickets,
        open_tickets=open_tickets,
        in_progress_tickets=in_progress_tickets,
        resolved_tickets=resolved_tickets,
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

    return render_template(
        "admin/ticket_details.html",
        ticket=ticket,
        replies=replies,
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

    ticket.status = new_status

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


# =========================================================
# ADMIN USER MANAGEMENT
# =========================================================

# -------------------------
# MANAGE USERS
# -------------------------

@app.route("/admin/users")
@admin_required
def admin_users():

    users = User.query.order_by(
        User.id.desc()
    ).all()

    return render_template(
        "admin/users.html",
        users=users,
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

if __name__ == "__main__":

    with app.app_context():
        db.create_all()

    app.run(debug=True)
