
import sqlite3
import os

db_path = "database/visitors.db"

print("Database file exists:", os.path.exists(db_path))

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("\n========== TABLES ==========")

tables = cursor.execute(
    "SELECT name FROM sqlite_master WHERE type='table'"
).fetchall()

print(tables)

print("\n========== USERS ==========")

try:
    users = cursor.execute(
        "SELECT id, name, email FROM users"
    ).fetchall()

    for user in users:
        print(user)

except Exception as e:
    print("Users error:", e)

print("\n========== PHOTOS ==========")

try:
    photos = cursor.execute(
        "SELECT id, visitor_name, filename, user_id FROM photos"
    ).fetchall()

    for photo in photos:
        print(photo)

except Exception as e:
    print("Photos error:", e)

conn.close()

print("\n========== CHECK COMPLETE ==========")
