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
cur.execute("""
CREATE TABLE IF NOT EXISTS trips (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_by  INTEGER,
    trip_name   TEXT NOT NULL,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id)
)
""")

# ── Patch trips table safely ─────────────────────────────────────────────────
existing_cols = [row[1] for row in cur.execute("PRAGMA table_info(trips)").fetchall()]

if "user_id" not in existing_cols and "created_by" not in existing_cols:
    cur.execute("ALTER TABLE trips ADD COLUMN created_by INTEGER REFERENCES users(id)")
    print("Patched trips: added created_by")
elif "user_id" in existing_cols and "created_by" not in existing_cols:
    # Rename user_id → created_by for existing DBs
    # SQLite does not support RENAME COLUMN before 3.25, so we add created_by and copy
    cur.execute("ALTER TABLE trips ADD COLUMN created_by INTEGER REFERENCES users(id)")
    cur.execute("UPDATE trips SET created_by = user_id")
    print("Patched trips: migrated user_id → created_by")

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

# ── Table: trip_users (invite + access control) ──────────────────────────────
# status: 'accepted' | 'pending' | 'rejected'
cur.execute("""
CREATE TABLE IF NOT EXISTS trip_users (
    trip_id  INTEGER NOT NULL,
    user_id  INTEGER NOT NULL,
    status   TEXT    NOT NULL DEFAULT 'accepted',
    PRIMARY KEY (trip_id, user_id),
    FOREIGN KEY (trip_id) REFERENCES trips(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
)
""")

# ── Patch trip_users — add status column if missing (existing rows = accepted) ─
tu_cols = [row[1] for row in cur.execute("PRAGMA table_info(trip_users)").fetchall()]
if "status" not in tu_cols:
    cur.execute("ALTER TABLE trip_users ADD COLUMN status TEXT NOT NULL DEFAULT 'accepted'")
    print("Patched trip_users: added status column (existing rows default to accepted)")

# ── Patch members table — add user_id column (nullable) ──────────────────────
member_cols = [row[1] for row in cur.execute("PRAGMA table_info(members)").fetchall()]
if "user_id" not in member_cols:
    cur.execute("ALTER TABLE members ADD COLUMN user_id INTEGER REFERENCES users(id)")
    print("Patched members: added user_id")

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
print("Tables: users, trips, trip_users, members, expenses, expense_splits")
