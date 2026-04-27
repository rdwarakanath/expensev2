import sqlite3

conn = sqlite3.connect("expense.db")
cur = conn.cursor()

# Enable foreign key enforcement
cur.execute("PRAGMA foreign_keys = ON")

# ── Table 1: trips ──────────────────────────────────────────────────────────
cur.execute("""
CREATE TABLE IF NOT EXISTS trips (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_name   TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# ── Table 2: members ────────────────────────────────────────────────────────
cur.execute("""
CREATE TABLE IF NOT EXISTS members (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id  INTEGER NOT NULL,
    name     TEXT    NOT NULL,
    FOREIGN KEY (trip_id) REFERENCES trips(id)
)
""")

# ── Table 3: expenses ───────────────────────────────────────────────────────
# payer_id references members.id so we can JOIN back to get the payer's name
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

# ── Table 4: expense_splits ─────────────────────────────────────────────────
# One row per (expense, member) – stores how much that member owes for that expense
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
print("Tables created: trips, members, expenses, expense_splits")
