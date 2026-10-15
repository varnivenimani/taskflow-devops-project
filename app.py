from datetime import datetime, date

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    flash,
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config


app = Flask(__name__)
app.config.from_object(Config)

if not app.config.get("SECRET_KEY"):
    raise RuntimeError("SECRET_KEY is missing from .env")

if not app.config.get("SQLALCHEMY_DATABASE_URI"):
    raise RuntimeError("DATABASE_URL is missing from .env")


db = SQLAlchemy(app)
csrf = CSRFProtect(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    tasks = db.relationship(
        "Task",
        backref="owner",
        lazy=True,
        cascade="all, delete-orphan",
    )


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")

    priority = db.Column(db.String(20), default="Medium")
    status = db.Column(db.String(30), default="Pending")

    due_date = db.Column(db.Date, nullable=True)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
    )

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description or "",
            "priority": self.priority,
            "status": self.status,
            "due_date": (
                self.due_date.isoformat()
                if self.due_date
                else ""
            ),
            "created_at": self.created_at.isoformat(),
        }


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (ValueError, TypeError):
        return None


@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not email or not password:
            flash("Please fill in all fields.", "error")
            return redirect(url_for("register"))

        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("register"))

        existing_user = db.session.execute(
            db.select(User).filter_by(email=email)
        ).scalar_one_or_none()

        if existing_user:
            flash("This email is already registered.", "error")
            return redirect(url_for("register"))

        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
        )

        db.session.add(user)
        db.session.commit()

        flash("Account created successfully. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = db.session.execute(
            db.select(User).filter_by(email=email)
        ).scalar_one_or_none()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    tasks = db.session.execute(
        db.select(Task)
        .filter_by(user_id=current_user.id)
        .order_by(Task.created_at.desc())
    ).scalars().all()

    total_tasks = len(tasks)
    pending_tasks = sum(t.status == "Pending" for t in tasks)
    progress_tasks = sum(t.status == "In Progress" for t in tasks)
    completed_tasks = sum(t.status == "Completed" for t in tasks)

    return render_template(
        "dashboard.html",
        username=current_user.username,
        tasks=tasks,
        total_tasks=total_tasks,
        pending_tasks=pending_tasks,
        progress_tasks=progress_tasks,
        completed_tasks=completed_tasks,
    )


@app.route("/api/tasks", methods=["GET", "POST"])
@login_required
def tasks_api():
    if request.method == "GET":
        tasks = db.session.execute(
            db.select(Task)
            .filter_by(user_id=current_user.id)
            .order_by(Task.created_at.desc())
        ).scalars().all()

        return jsonify([task.to_dict() for task in tasks])

    data = request.get_json(silent=True) or {}

    title = str(data.get("title", "")).strip()
    description = str(data.get("description", "")).strip()
    priority = data.get("priority", "Medium")
    status = data.get("status", "Pending")
    due_date_value = data.get("due_date", "")

    if not title:
        return jsonify({"error": "Task title is required"}), 400

    if len(title) > 200:
        return jsonify({"error": "Title is too long"}), 400

    if priority not in ["Low", "Medium", "High"]:
        return jsonify({"error": "Invalid priority"}), 400

    if status not in ["Pending", "In Progress", "Completed"]:
        return jsonify({"error": "Invalid status"}), 400

    due_date = None

    if due_date_value:
        try:
            due_date = date.fromisoformat(due_date_value)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid due date"}), 400

    task = Task(
        title=title,
        description=description,
        priority=priority,
        status=status,
        due_date=due_date,
        user_id=current_user.id,
    )

    db.session.add(task)
    db.session.commit()

    return jsonify(task.to_dict()), 201


@app.route("/api/tasks/<int:task_id>", methods=["PUT", "DELETE"])
@login_required
def task_detail(task_id):
    task = db.session.execute(
        db.select(Task).filter_by(
            id=task_id,
            user_id=current_user.id,
        )
    ).scalar_one_or_none()

    if not task:
        return jsonify({"error": "Task not found"}), 404

    if request.method == "DELETE":
        db.session.delete(task)
        db.session.commit()

        return jsonify({"message": "Task deleted successfully"})

    data = request.get_json(silent=True) or {}

    title = str(data.get("title", "")).strip()
    description = str(data.get("description", "")).strip()
    priority = data.get("priority", "Medium")
    status = data.get("status", "Pending")
    due_date_value = data.get("due_date", "")

    if not title:
        return jsonify({"error": "Task title is required"}), 400

    if len(title) > 200:
        return jsonify({"error": "Title is too long"}), 400

    if priority not in ["Low", "Medium", "High"]:
        return jsonify({"error": "Invalid priority"}), 400

    if status not in ["Pending", "In Progress", "Completed"]:
        return jsonify({"error": "Invalid status"}), 400

    due_date = None

    if due_date_value:
        try:
            due_date = date.fromisoformat(due_date_value)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid due date"}), 400

    task.title = title
    task.description = description
    task.priority = priority
    task.status = status
    task.due_date = due_date

    db.session.commit()

    return jsonify(task.to_dict())


@app.route("/health")
def health():
    return jsonify({"status": "healthy"}), 200


def initialize_database():
    with app.app_context():
        db.create_all()


if __name__ == "__main__":
    initialize_database()
    app.run(host="127.0.0.1", port=5000, debug=False)