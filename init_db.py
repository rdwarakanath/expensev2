import psycopg2
import os
from dotenv import load_dotenv
load_dotenv()
DATABASE_URL = os.environ.get("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL)
cur  = conn.cursor()

# ── Table 1: users ────────────────────────────────────────────────────────────
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# ── Table 2: trips ────────────────────────────────────────────────────────────
cur.execute("""
CREATE TABLE IF NOT EXISTS trips (
    id          SERIAL PRIMARY KEY,
    created_by  INTEGER REFERENCES users(id),
    trip_name   TEXT    NOT NULL,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# ── Table 3: members ──────────────────────────────────────────────────────────
cur.execute("""
CREATE TABLE IF NOT EXISTS members (
    id       SERIAL PRIMARY KEY,
    trip_id  INTEGER NOT NULL REFERENCES trips(id),
    name     TEXT    NOT NULL,
    user_id  INTEGER REFERENCES users(id)
)
""")

# ── Table 4: expenses ─────────────────────────────────────────────────────────
cur.execute("""
CREATE TABLE IF NOT EXISTS expenses (
    id          SERIAL PRIMARY KEY,
    trip_id     INTEGER NOT NULL REFERENCES trips(id),
    payer_id    INTEGER NOT NULL REFERENCES members(id),
    amount      REAL    NOT NULL,
    description TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# ── Table 5: trip_users (invite + access control) ─────────────────────────────
# status: 'accepted' | 'pending' | 'rejected'
cur.execute("""
CREATE TABLE IF NOT EXISTS trip_users (
    trip_id  INTEGER NOT NULL REFERENCES trips(id),
    user_id  INTEGER NOT NULL REFERENCES users(id),
    status   TEXT    NOT NULL DEFAULT 'accepted',
    PRIMARY KEY (trip_id, user_id)
)
""")

# ── Table 6: expense_splits ───────────────────────────────────────────────────
cur.execute("""
CREATE TABLE IF NOT EXISTS expense_splits (
    id           SERIAL PRIMARY KEY,
    expense_id   INTEGER NOT NULL REFERENCES expenses(id),
    member_id    INTEGER NOT NULL REFERENCES members(id),
    share_amount REAL    NOT NULL
)
""")

cur.execute("CREATE INDEX IF NOT EXISTS idx_trip_users_user_id ON trip_users(user_id)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_trip_users_trip_id ON trip_users(trip_id)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_members_trip_id ON members(trip_id)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_members_user_id ON members(user_id)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_expenses_trip_id ON expenses(trip_id)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_expenses_payer_id ON expenses(payer_id)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_expense_splits_expense_id ON expense_splits(expense_id)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_expense_splits_member_id ON expense_splits(member_id)")

conn.commit()
cur.close()
conn.close()

print("PostgreSQL database initialised successfully.")
print("Tables: users, trips, trip_users, members, expenses, expense_splits")
