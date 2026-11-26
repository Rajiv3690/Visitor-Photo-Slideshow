
import os
import sqlite3
import secrets
from functools import wraps

from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "visitor-slideshow-development-secret"
)

app.config["UPLOAD_FOLDER"] = "static/uploads"
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

# Fixed admin credentials (local assignment demo)
ADMIN_EMAIL = "admin@gmail.com"
ADMIN_PASSWORD = "Admin@123"


# ---------------- DATABASE ----------------

def get_db():
    os.makedirs("database", exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    conn = sqlite3.connect("database/visitors.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            visitor_name TEXT NOT NULL,
            filename TEXT NOT NULL,
            user_id INTEGER REFERENCES users(id)
        )
    """)

    columns = [
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(photos)"
        ).fetchall()
    ]

    if "user_id" not in columns:
        conn.execute(
            "ALTER TABLE photos ADD COLUMN user_id INTEGER"
        )

    conn.commit()
    conn.close()


# ---------------- HELPERS ----------------

def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def save_photos(user_id, visitor_name, files, conn):
    count = 0

    for file in files:
        if file and file.filename and allowed_file(file.filename):
            safe_name = secure_filename(file.filename)

            unique_name = (
                secrets.token_hex(8) + "_" + safe_name
            )

            path = os.path.join(
                app.config["UPLOAD_FOLDER"],
                unique_name
            )

            file.save(path)

            conn.execute("""
                INSERT INTO photos
                (visitor_name, filename, user_id)
                VALUES (?, ?, ?)
            """, (
                visitor_name,
                unique_name,
                user_id
            ))

            count += 1

    return count


def admin_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("admin_login"))

        return function(*args, **kwargs)

    return wrapper


# ---------------- VISITOR HOME ----------------

@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template("index.html")


# ---------------- REGISTER ----------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("visitor_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("Please fill in all fields.")
            return redirect(url_for("register"))

        if len(password) < 8:
            flash("Password must contain at least 8 characters.")
            return redirect(url_for("register"))

        conn = get_db()

        try:
            conn.execute("""
                INSERT INTO users (name, email, password)
                VALUES (?, ?, ?)
            """, (
                name,
                email,
                generate_password_hash(password)
            ))

            conn.commit()
            conn.close()

            flash("Account created successfully! Please login.")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            conn.rollback()
            conn.close()

            flash("This email is already registered.")
            return redirect(url_for("register"))

    return render_template("register.html")


# ---------------- VISITOR LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db()

        user = conn.execute("""
            SELECT * FROM users WHERE email = ?
        """, (email,)).fetchone()

        conn.close()

        if user and check_password_hash(user["password"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            return redirect(url_for("home"))

        flash("Incorrect email or password.")

    return render_template("login.html")


# ---------------- PHOTO UPLOAD ----------------

@app.route("/upload", methods=["POST"])
def upload():
    if "user_id" not in session:
        return redirect(url_for("login"))

    files = request.files.getlist("photos")

    conn = get_db()

    try:
        count = save_photos(
            session["user_id"],
            session["user_name"],
            files,
            conn
        )

        conn.commit()

    finally:
        conn.close()

    if count == 0:
        flash("Please select valid image files.")
        return redirect(url_for("home"))

    flash(f"{count} photo(s) uploaded successfully.")
    return redirect(url_for("slideshow"))


# ---------------- VISITOR SLIDESHOW ----------------

@app.route("/slideshow")
def slideshow():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    photos = conn.execute("""
        SELECT id, visitor_name, filename
        FROM photos
        WHERE user_id = ?
        ORDER BY id DESC
    """, (session["user_id"],)).fetchall()

    conn.close()

    return render_template(
        "slideshow.html",
        photos=photos
    )


# ---------------- VISITOR DELETE PHOTO ----------------

@app.route("/delete-photo/<int:photo_id>", methods=["POST"])
def delete_photo(photo_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    photo = conn.execute("""
        SELECT filename
        FROM photos
        WHERE id = ? AND user_id = ?
    """, (
        photo_id,
        session["user_id"]
    )).fetchone()

    if photo:
        filename = photo["filename"]

        conn.execute("""
            DELETE FROM photos
            WHERE id = ? AND user_id = ?
        """, (
            photo_id,
            session["user_id"]
        ))

        conn.commit()

        file_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )

        if os.path.isfile(file_path):
            os.remove(file_path)

        flash("Photo deleted successfully.")
    else:
        flash("Photo not found.")

    conn.close()

    return redirect(url_for("slideshow"))


# ==================================================
#                    ADMIN LOGIN
# ==================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if (
            email == ADMIN_EMAIL
            and password == ADMIN_PASSWORD
        ):
            session.clear()
            session["admin_id"] = 1
            session["admin_email"] = ADMIN_EMAIL

            return redirect(url_for("admin_dashboard"))

        flash("Incorrect admin email or password.")

    return render_template("admin_login.html")


# ==================================================
#                  ADMIN DASHBOARD
# ==================================================

@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = get_db()

    total_visitors = conn.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    total_photos = conn.execute(
        "SELECT COUNT(*) FROM photos"
    ).fetchone()[0]

    visitors = conn.execute("""
        SELECT
            users.id,
            users.name,
            users.email,
            COUNT(photos.id) AS photo_count
        FROM users
        LEFT JOIN photos
            ON users.id = photos.user_id
        GROUP BY users.id
        ORDER BY users.id DESC
    """).fetchall()

    photos = conn.execute("""
        SELECT
            photos.id,
            photos.filename,
            photos.visitor_name,
            users.email
        FROM photos
        LEFT JOIN users
            ON photos.user_id = users.id
        ORDER BY photos.id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_visitors=total_visitors,
        total_photos=total_photos,
        visitors=visitors,
        photos=photos
    )


# ---------------- ADMIN DELETE PHOTO ----------------

@app.route("/admin/delete-photo/<int:photo_id>", methods=["POST"])
@admin_required
def admin_delete_photo(photo_id):
    conn = get_db()

    photo = conn.execute("""
        SELECT filename
        FROM photos
        WHERE id = ?
    """, (photo_id,)).fetchone()

    if photo:
        filename = photo["filename"]

        conn.execute(
            "DELETE FROM photos WHERE id = ?",
            (photo_id,)
        )

        conn.commit()

        file_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )

        if os.path.isfile(file_path):
            os.remove(file_path)

        flash("Photo deleted successfully.")
    else:
        flash("Photo not found.")

    conn.close()

    return redirect(url_for("admin_dashboard"))


# ---------------- ADMIN LOGOUT ----------------

@app.route("/admin/logout")
@admin_required
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


# ---------------- VISITOR LOGOUT ----------------

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------- RUN APPLICATION ----------------

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
