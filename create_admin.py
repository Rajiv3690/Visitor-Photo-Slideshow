
import sqlite3
import getpass
import os

from werkzeug.security import generate_password_hash

os.makedirs("database", exist_ok=True)

email = input("Enter admin email: ").strip().lower()
password = getpass.getpass("Enter admin password: ")

if not email or len(password) < 8:
    print("Email is required and password must be at least 8 characters.")
    raise SystemExit

conn = sqlite3.connect("database/visitors.db")

conn.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
""")

try:
    conn.execute(
        "INSERT INTO admins (email, password) VALUES (?, ?)",
        (email, generate_password_hash(password))
    )
    conn.commit()
    print("Admin account created successfully!")

except sqlite3.IntegrityError:
    print("An admin account with this email already exists.")

finally:
    conn.close()
