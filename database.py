import sqlite3
from datetime import date, datetime, timedelta

def get_connection():
    return sqlite3.connect("bugblock.db")

def setup():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY,
            name TEXT,
            xp INTEGER DEFAULT 0,
            streak INTEGER DEFAULT 0,
            last_active TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bugs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            error_type TEXT,
            hints_used INTEGER,
            understood INTEGER,
            date TEXT
        )
    """)

    conn.commit()
    conn.close()

def get_user():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "name": row[1],
        "xp": row[2],
        "streak": row[3],
        "last_active": row[4]
    }

def create_user(name):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user (id, name, xp, streak, last_active)
        VALUES (1, ?, 0, 1, ?)
    """, (name, str(date.today())))
    conn.commit()
    conn.close()

def add_xp(amount):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE user SET xp = xp + ? WHERE id = 1", (amount,))
    conn.commit()
    conn.close()

def update_streak():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT last_active, streak FROM user WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    last_active = row[0]
    streak = row[1]
    today = str(date.today())
    yesterday = str(date.today() - timedelta(days=1))

    conn = get_connection()
    cursor = conn.cursor()

    if last_active == today:
        conn.close()
        return streak
    elif last_active == yesterday:
        streak += 1
    else:
        streak = 1

    cursor.execute("""
        UPDATE user SET streak = ?, last_active = ? WHERE id = 1
    """, (streak, today))
    conn.commit()
    conn.close()
    return streak

def log_bug(error_type, hints_used, understood):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO bugs (error_type, hints_used, understood, date)
        VALUES (?, ?, ?, ?)
    """, (error_type, hints_used, understood, str(date.today())))
    conn.commit()
    conn.close()

def get_weak_spots():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT error_type, COUNT(*) as total, SUM(hints_used) as total_hints
        FROM bugs
        GROUP BY error_type
        HAVING total_hints > 2
        ORDER BY total_hints DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    weak_spots = []
    for row in rows:
        weak_spots.append({
            "error_type": row[0],
            "total_bugs": row[1],
            "total_hints": row[2]
        })
    return weak_spots

def get_xp_for_bug(hints_used, understood):
    if understood and hints_used == 0:
        return 100
    elif understood and hints_used <= 2:
        return 75
    elif understood:
        return 50
    else:
        return 25

setup()