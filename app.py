from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.config["SECRET_KEY"] = "helpdeskpro_secret_key"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///helpdesk.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager()

login_manager.init_app(app)

login_manager.login_view = "login"

# ===========================
# User Model
# ===========================


class User(UserMixin, db.Model):

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(100), nullable=False)

    email = db.Column(db.String(120), unique=True, nullable=False)

    password = db.Column(db.String(255), nullable=False)

    def __repr__(self):

        return f"<User {self.username}>"


@login_manager.user_loader
def load_user(user_id):

    return User.query.get(int(user_id))


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        # Find user by email
        user = User.query.filter_by(email=email).first()

        # Verify password
        if user and check_password_hash(user.password, password):

            login_user(user)

            return redirect(url_for("dashboard"))

        return "Invalid email or password."

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]

        email = request.form["email"]

        password = request.form["password"]

        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()

        if existing_user:

            return "Email already registered. Please login instead"

        # Hash password
        hashed_password = generate_password_hash(password)

        # Create user
        new_user = User(

            username=username,

            email=email,

            password=hashed_password

        )

        # Save to database
        db.session.add(new_user)

        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/guest")
def guest():
    return render_template("guest.html")


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/chat")
def chat():
    return render_template("chat.html")


@app.route("/tickets")
def tickets():
    return render_template("tickets.html")


@app.route("/knowledge")
def knowledge():
    return render_template("knowledge.html")


@app.route("/logout")
@login_required
def logout():

    logout_user()

    return redirect(url_for("home"))


if __name__ == "__main__":

    with app.app_context():

        db.create_all()

    app.run(debug=True)
