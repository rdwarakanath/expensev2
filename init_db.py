import sqlite3

conn = sqlite3.connect("expense.db")
cur  = conn.cursor()

cur.execute("PRAGMA foreign_keys = ON")

# ── Table 1: users (NEW) ─────────────────────────────────────────────────────
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# ── Table 2: trips ───────────────────────────────────────────────────────────
# Created with full structure. If table already exists, we patch it below.
cur.execute("""
CREATE TABLE IF NOT EXISTS trips (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER,
    trip_name   TEXT NOT NULL,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
""")

# ── Patch existing trips table if columns are missing ────────────────────────
# This runs safely even if DB was created before — ALTER TABLE is ignored
# if columns already exist (handled via try/except).
existing_cols = [row[1] for row in cur.execute("PRAGMA table_info(trips)").fetchall()]

if "user_id" not in existing_cols:
    cur.execute("ALTER TABLE trips ADD COLUMN user_id INTEGER REFERENCES users(id)")
    print("Patched trips: added user_id")

if "is_active" not in existing_cols:
    cur.execute("ALTER TABLE trips ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
    print("Patched trips: added is_active")

# ── Table 3: members (unchanged) ─────────────────────────────────────────────
cur.execute("""
CREATE TABLE IF NOT EXISTS members (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id  INTEGER NOT NULL,
    name     TEXT    NOT NULL,
    FOREIGN KEY (trip_id) REFERENCES trips(id)
)
""")

# ── Table 4: expenses (unchanged) ────────────────────────────────────────────
cur.execute("""
CREATE TABLE IF NOT EXISTS expenses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id     INTEGER NOT NULL,
    payer_id    INTEGER NOT NULL,
    amount      REAL    NOT NULL,
    description TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trip_id)  REFERENCES trips(id),
    FOREIGN KEY (payer_id) REFERENCES members(id)
)
""")

# ── Table 5: expense_splits (unchanged) ──────────────────────────────────────
cur.execute("""
CREATE TABLE IF NOT EXISTS expense_splits (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    expense_id   INTEGER NOT NULL,
    member_id    INTEGER NOT NULL,
    share_amount REAL    NOT NULL,
    FOREIGN KEY (expense_id) REFERENCES expenses(id),
    FOREIGN KEY (member_id)  REFERENCES members(id)
)
""")

conn.commit()
conn.close()

print("Database initialised successfully.")
print("Tables: users, trips, members, expenses, expense_splits")
