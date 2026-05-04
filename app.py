from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import sqlite3

# ── DB helper ────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect("expense.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

# ── App setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = "trip_secret_2025"
# Session stores: user_id, username only.
# trip_id now lives in the URL, not the session.


# =========================================================
# ── AUTH DECORATOR ────────────────────────────────────────
# =========================================================

def login_required(f):
    """Redirect to /login if user is not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# =========================================================
# ── HELPER FUNCTIONS (UNCHANGED FROM PREVIOUS VERSION) ────
# =========================================================

def create_trip(trip_name, user_id):
    """Insert a new trip linked to a user and return its id."""
    conn = get_db()
    cur  = conn.cursor()
    # CHANGED: now stores user_id so trip belongs to a user
    cur.execute(
        "INSERT INTO trips (trip_name, user_id, is_active) VALUES (?, ?, 1)",
        (trip_name, user_id)
    )
    conn.commit()
    trip_id = cur.lastrowid
    conn.close()
    return trip_id


def add_members_to_db(trip_id, members):
    """Insert every member for a trip — UNCHANGED."""
    conn = get_db()
    cur  = conn.cursor()
    for m in members:
        cur.execute(
            "INSERT INTO members (trip_id, name) VALUES (?, ?)",
            (trip_id, m)
        )
    conn.commit()
    conn.close()


def process_expense(data, trip_id):
    """
    Parse expense payload and write to expenses + expense_splits.
    COMPLETELY UNCHANGED — same logic as before.
    """
    reason       = data.get("reason")
    total        = float(data.get("amount"))
    payer_name   = data.get("whopaid")
    sharemembers = data.get("members")
    shares       = [float(s) for s in data.get("shares")]

    conn = get_db()
    cur  = conn.cursor()

    cur.execute(
        "SELECT id FROM members WHERE trip_id = ? AND name = ?",
        (trip_id, payer_name)
    )
    payer_row = cur.fetchone()
    if not payer_row:
        conn.close()
        raise ValueError(f"Payer '{payer_name}' not found in trip {trip_id}")
    payer_id = payer_row["id"]

    cur.execute(
        "INSERT INTO expenses (trip_id, payer_id, amount, description) VALUES (?, ?, ?, ?)",
        (trip_id, payer_id, total, reason)
    )
    expense_id = cur.lastrowid

    for person_name, share in zip(sharemembers, shares):
        cur.execute(
            "SELECT id FROM members WHERE trip_id = ? AND name = ?",
            (trip_id, person_name)
        )
        member_row = cur.fetchone()
        if not member_row:
            conn.close()
            raise ValueError(f"Member '{person_name}' not found in trip {trip_id}")
        cur.execute(
            "INSERT INTO expense_splits (expense_id, member_id, share_amount) VALUES (?, ?, ?)",
            (expense_id, member_row["id"], share)
        )

    conn.commit()
    conn.close()


def simplify_debts(balances):
    """
    Greedy debt simplification algorithm.
    Takes the balances dict already computed in calculate_results()
    and returns a minimized list of settlement strings.

    Algorithm:
      1. Compute net balance per person (total owed minus total receivable)
      2. Split into creditors (net > 0) and debtors (net < 0)
      3. Greedily match largest debtor with largest creditor
      4. Settle minimum of the two, advance pointer of whoever hits zero
      5. If all balances cancel out, return empty list
    """
    # Step 1: Net balance per person
    net = {}
    for person in balances:
        for creditor, amount in balances[person].items():
            net[person]   = round(net.get(person, 0) - amount, 2)
            net[creditor] = round(net.get(creditor, 0) + amount, 2)

    # Step 2: Separate, skip near-zero balances
    creditors = []
    debtors   = []
    for person, amt in net.items():
        if amt > 0.01:
            creditors.append([person, amt])
        elif amt < -0.01:
            debtors.append([person, -amt])

    # Edge case: everything cancels out
    if not creditors and not debtors:
        return []

    # Step 3: Sort descending
    creditors.sort(key=lambda x: x[1], reverse=True)
    debtors.sort(key=lambda x: x[1], reverse=True)

    # Step 4: Greedy matching
    result = []
    i, j   = 0, 0

    while i < len(debtors) and j < len(creditors):
        debtor,   debt_amt   = debtors[i]
        creditor, credit_amt = creditors[j]

        if debtor == creditor:
            i += 1
            continue

        settle = round(min(debt_amt, credit_amt), 2)
        result.append(f"{debtor} has to pay ₹{settle:.2f} to {creditor}")

        debtors[i][1]   = round(debtors[i][1]   - settle, 2)
        creditors[j][1] = round(creditors[j][1] - settle, 2)

        if debtors[i][1]   < 0.01: i += 1
        if creditors[j][1] < 0.01: j += 1

    return result


def calculate_results(trip_id):
    """
    Compute settlements, total spent, transactions from DB.
    CHANGED: now also runs simplify_debts() and returns simplified list.
    All other logic completely unchanged.
    """
    conn = get_db()
    cur  = conn.cursor()

    cur.execute("SELECT id, name FROM members WHERE trip_id = ?", (trip_id,))
    member_rows = cur.fetchall()
    if not member_rows:
        conn.close()
        return None, None, None

    members      = [r["name"] for r in member_rows]
    balances     = {m: {x: 0 for x in members if x != m} for m in members}
    total_spent  = {m: 0 for m in members}
    transactions = []

    cur.execute("""
        SELECT e.id, e.description, e.amount, m.name AS payer_name
        FROM   expenses e
        JOIN   members  m ON e.payer_id = m.id
        WHERE  e.trip_id = ?
        ORDER  BY e.created_at
    """, (trip_id,))
    expenses = cur.fetchall()

    for exp in expenses:
        exp_id         = exp["id"]
        reason         = exp["description"]
        total          = exp["amount"]
        payer_name     = exp["payer_name"]
        paymentdetails = [reason, total, payer_name, []]

        cur.execute("""
            SELECT es.share_amount, m.name AS member_name
            FROM   expense_splits es
            JOIN   members        m  ON es.member_id = m.id
            WHERE  es.expense_id = ?
        """, (exp_id,))
        splits = cur.fetchall()

        for split in splits:
            person = split["member_name"]
            share  = split["share_amount"]
            paymentdetails[3].append([person, share])
            if person != payer_name:
                balances[person][payer_name] += share
            total_spent[person] += share

        transactions.append(paymentdetails)

    conn.close()

    printed     = set()
    outputpayto = []

    for p1 in balances:
        for p2 in balances[p1]:
            if (p2, p1) not in printed:
                net = balances[p1][p2] - balances[p2][p1]
                if net > 0:
                    outputpayto.append(f"{p1} has to pay ₹{net:.2f} to {p2}")
                elif net < 0:
                    outputpayto.append(f"{p2} has to pay ₹{abs(net):.2f} to {p1}")
                printed.add((p1, p2))

    totspent = [f"{mem} : ₹{amt:.2f}" for mem, amt in total_spent.items()]

    transactions_final = [
        f"{t[0]} - ₹{t[1]:.2f} paid by {t[2]} -> splits: {t[3]}"
        for t in transactions
    ]

    # Run greedy simplification on the same balances dict
    simplified = simplify_debts(balances)

    return outputpayto, simplified, totspent, transactions_final


def fetch_total_spent_data(trip_id):
    """Return spending summary strings. UNCHANGED."""
    _, _simplified, totspent, _ = calculate_results(trip_id)
    if totspent is None:
        return []
    return [line.replace(" : ", " spent ") for line in totspent]


# =========================================================
# ── AUTH ROUTES ───────────────────────────────────────────
# =========================================================

@app.route('/')
def index():
    """Root: redirect to home if logged in, else to login."""
    if "user_id" in session:
        return redirect(url_for("home"))
    return redirect(url_for("login"))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if "user_id" in session:
        return redirect(url_for("home"))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            error = "Please fill in all fields."
        else:
            conn = get_db()
            cur  = conn.cursor()
            cur.execute("SELECT * FROM users WHERE username = ?", (username,))
            user = cur.fetchone()
            conn.close()

            if not user or not check_password_hash(user['password_hash'], password):
                error = "Invalid username or password."
            else:
                session.clear()
                session['user_id']  = user['id']
                session['username'] = user['username']
                return redirect(url_for("home"))

    return render_template('login.html', error=error)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if "user_id" in session:
        return redirect(url_for("home"))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm', '')

        if not username or not email or not password or not confirm:
            error = "Please fill in all fields."
        elif password != confirm:
            error = "Passwords do not match."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        else:
            conn = get_db()
            cur  = conn.cursor()
            # Check username/email uniqueness
            cur.execute(
                "SELECT id FROM users WHERE username = ? OR email = ?",
                (username, email)
            )
            if cur.fetchone():
                error = "Username or email already taken."
                conn.close()
            else:
                cur.execute(
                    "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                    (username, email, generate_password_hash(password))
                )
                conn.commit()
                user_id = cur.lastrowid
                conn.close()

                session.clear()
                session['user_id']  = user_id
                session['username'] = username
                return redirect(url_for("home"))

    return render_template('signup.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("login"))


# =========================================================
# ── HOME (TRIP LIST + NEW TRIP) ───────────────────────────
# =========================================================

@app.route('/home')
@login_required
def home():
    """
    Shows the user's trip history and the new trip creation flow.
    Trips are fetched fresh from DB filtered by user_id.
    """
    user_id = session['user_id']
    conn    = get_db()
    cur     = conn.cursor()
    cur.execute("""
        SELECT id, trip_name, is_active, created_at
        FROM   trips
        WHERE  user_id = ?
        ORDER  BY created_at DESC
    """, (user_id,))
    trips = [dict(r) for r in cur.fetchall()]
    conn.close()

    return render_template('home.html',
                           username=session['username'],
                           trips=trips)


# =========================================================
# ── TRIP CREATION ROUTES ──────────────────────────────────
# =========================================================

@app.route('/save_trip', methods=['POST'])
@login_required
def save_trip():
    trip_name = request.json.get('tripName')
    user_id   = session['user_id']

    # CHANGED: pass user_id to create_trip
    trip_id = create_trip(trip_name, user_id)

    # Still store in session temporarily for the creation flow
    # (save_members needs it before we redirect to /dashboard/<trip_id>)
    session['pending_trip_id']   = trip_id
    session['pending_trip_name'] = trip_name

    return jsonify({"message": "Trip saved!", "trip_id": trip_id})


@app.route('/save_members', methods=['POST'])
@login_required
def save_members():
    members = request.json.get('members')
    # CHANGED: read from pending_trip_id set during save_trip
    trip_id = session.get('pending_trip_id')

    if not trip_id:
        return jsonify({"error": "Trip not found"}), 400

    add_members_to_db(trip_id, members)

    # Clear pending keys — trip_id now lives in URL from here on
    session.pop('pending_trip_id', None)
    session.pop('pending_trip_name', None)

    return jsonify({"message": "Members saved!", "trip_id": trip_id})


# =========================================================
# ── DASHBOARD — URL-BASED ─────────────────────────────────
# =========================================================

@app.route('/dashboard/<int:trip_id>')
@login_required
def dashboard(trip_id):
    user_id = session['user_id']
    conn    = get_db()
    cur     = conn.cursor()

    # Ownership check: trip must belong to this user
    cur.execute(
        "SELECT trip_name, is_active FROM trips WHERE id = ? AND user_id = ?",
        (trip_id, user_id)
    )
    trip = cur.fetchone()
    if not trip:
        conn.close()
        return "Trip not found.", 404

    # If trip is finished, send straight to results
    if not trip['is_active']:
        conn.close()
        return redirect(url_for('results', trip_id=trip_id))

    cur.execute("SELECT name FROM members WHERE trip_id = ?", (trip_id,))
    members = [r["name"] for r in cur.fetchall()]
    conn.close()

    return render_template('dashboard.html',
                           trip_name=trip['trip_name'],
                           trip_id=trip_id,
                           members=members)


# =========================================================
# ── EXPENSE ROUTES — trip_id from URL ────────────────────
# =========================================================

@app.route('/add_expense/<int:trip_id>', methods=['POST'])
@login_required
def add_expense(trip_id):
    user_id = session['user_id']
    data    = request.get_json() or {}

    if not all(k in data for k in ["reason", "amount", "members", "shares", "whopaid"]):
        return jsonify({"status": "error", "message": "Missing fields"}), 400

    conn = get_db()
    cur  = conn.cursor()

    # Ownership + is_active check
    cur.execute(
        "SELECT is_active FROM trips WHERE id = ? AND user_id = ?",
        (trip_id, user_id)
    )
    trip = cur.fetchone()
    conn.close()

    if not trip:
        return jsonify({"status": "error", "message": "Trip not found"}), 404
    if not trip['is_active']:
        return jsonify({"status": "error", "message": "This trip is finished."}), 403

    try:
        process_expense(data, trip_id)   # UNCHANGED helper
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400

    return jsonify({"status": "success"})


@app.route('/get_data/<int:trip_id>', methods=['GET'])
@login_required
def get_data(trip_id):
    user_id = session['user_id']
    conn    = get_db()
    cur     = conn.cursor()

    cur.execute(
        "SELECT id FROM trips WHERE id = ? AND user_id = ?",
        (trip_id, user_id)
    )
    if not cur.fetchone():
        conn.close()
        return jsonify([])
    conn.close()

    data = fetch_total_spent_data(trip_id)   # UNCHANGED helper
    return jsonify(data)


@app.route('/get_expenses/<int:trip_id>', methods=['GET'])
@login_required
def get_expenses(trip_id):
    """
    Return all expenses for a trip so the dashboard can
    render existing cards on page load.
    """
    user_id = session['user_id']
    conn    = get_db()
    cur     = conn.cursor()

    # Ownership check
    cur.execute(
        "SELECT id FROM trips WHERE id = ? AND user_id = ?",
        (trip_id, user_id)
    )
    if not cur.fetchone():
        conn.close()
        return jsonify([])

    # Fetch each expense with payer name
    cur.execute("""
        SELECT e.id, e.description, e.amount, m.name AS payer_name
        FROM   expenses e
        JOIN   members  m ON e.payer_id = m.id
        WHERE  e.trip_id = ?
        ORDER  BY e.created_at
    """, (trip_id,))
    expenses = cur.fetchall()

    result = []
    for exp in expenses:
        # Fetch splits for this expense
        cur.execute("""
            SELECT m.name AS member_name, es.share_amount
            FROM   expense_splits es
            JOIN   members        m ON es.member_id = m.id
            WHERE  es.expense_id = ?
        """, (exp["id"],))
        splits = cur.fetchall()

        result.append({
            "reason":  exp["description"],
            "amount":  exp["amount"],
            "whopaid": exp["payer_name"],
            "splits":  [{"name": s["member_name"], "share": s["share_amount"]} for s in splits]
        })

    conn.close()
    return jsonify(result)


@app.route('/finish_trip/<int:trip_id>', methods=['POST'])
@login_required
def finish_trip(trip_id):
    """Mark trip as finished (is_active = 0)."""
    user_id = session['user_id']
    conn    = get_db()
    cur     = conn.cursor()

    cur.execute(
        "UPDATE trips SET is_active = 0 WHERE id = ? AND user_id = ?",
        (trip_id, user_id)
    )
    conn.commit()
    conn.close()

    return jsonify({"status": "success"})


# =========================================================
# ── RESULTS — URL-BASED ───────────────────────────────────
# =========================================================

@app.route('/results/<int:trip_id>')
@login_required
def results(trip_id):
    user_id = session['user_id']
    conn    = get_db()
    cur     = conn.cursor()

    # Ownership check
    cur.execute(
        "SELECT trip_name FROM trips WHERE id = ? AND user_id = ?",
        (trip_id, user_id)
    )
    trip = cur.fetchone()
    conn.close()

    if not trip:
        return "Trip not found.", 404

    payday, simplified, totspent, transactions = calculate_results(trip_id)

    if payday is None:
        return render_template('results.html',
                               message='no data available',
                               trip_name=trip['trip_name'],
                               trip_id=trip_id)

    return render_template('results.html',
                           message="summary generated",
                           trip_name=trip['trip_name'],
                           trip_id=trip_id,
                           transactions=transactions,
                           totspent=totspent,
                           payday=payday,
                           simplified=simplified)


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True)
