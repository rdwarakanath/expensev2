from flask import Flask, render_template, request, jsonify, session
import sqlite3

# ── DB helper ───────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect("expense.db")
    conn.row_factory = sqlite3.Row          # rows behave like dicts
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

# ── App setup ────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = "trip"
# Session now only carries trip_id + trip_name for navigation.
# All expense data lives in SQLite.


# =========================================================
# ── HELPER FUNCTIONS ─────────────────────────────────────
# =========================================================

def create_trip(trip_name):
    """Insert a new trip and return its auto-generated id."""
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("INSERT INTO trips (trip_name) VALUES (?)", (trip_name,))
    conn.commit()
    trip_id = cur.lastrowid
    conn.close()
    return trip_id


# ── CHANGED: session data removed; members are only written to DB ──────────
def add_members_to_db(trip_id, members):
    """Insert every member for a trip into the members table."""
    conn = get_db()
    cur  = conn.cursor()
    for m in members:
        cur.execute(
            "INSERT INTO members (trip_id, name) VALUES (?, ?)",
            (trip_id, m)
        )
    conn.commit()
    conn.close()


# ── CHANGED: was process_expense(data, session_data) mutating session dicts ─
#            now writes directly to expenses + expense_splits tables          ─
def process_expense(data, trip_id):
    """
    Parse the incoming expense payload and persist it to the DB.

    Inserts one row into `expenses` (with payer_id resolved from members table)
    and one row per split member into `expense_splits`.
    """
    reason       = data.get("reason")
    total        = float(data.get("amount"))
    payer_name   = data.get("whopaid")
    sharemembers = data.get("members")
    shares       = [float(s) for s in data.get("shares")]

    conn = get_db()
    cur  = conn.cursor()

    # Resolve payer's member_id from name + trip_id
    cur.execute(
        "SELECT id FROM members WHERE trip_id = ? AND name = ?",
        (trip_id, payer_name)
    )
    payer_row = cur.fetchone()
    if not payer_row:
        conn.close()
        raise ValueError(f"Payer '{payer_name}' not found in trip {trip_id}")
    payer_id = payer_row["id"]

    # Insert the expense record
    cur.execute(
        "INSERT INTO expenses (trip_id, payer_id, amount, description) VALUES (?, ?, ?, ?)",
        (trip_id, payer_id, total, reason)
    )
    expense_id = cur.lastrowid

    # Insert one split row per member involved in this expense
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


# ── CHANGED: was calculate_results(session_data) reading session dicts ──────
#            now recomputes everything fresh from the DB                 ──────
def calculate_results(trip_id):
    """
    Read all expenses + splits for a trip from the DB and compute:
      - net settlement lines  (who pays whom)
      - per-member total spent
      - human-readable transaction list

    Logic is identical to the original session-based version.
    """
    conn = get_db()
    cur  = conn.cursor()

    # Fetch all member names for this trip
    cur.execute("SELECT id, name FROM members WHERE trip_id = ?", (trip_id,))
    member_rows = cur.fetchall()
    if not member_rows:
        conn.close()
        return None, None, None

    members      = [r["name"] for r in member_rows]
    member_by_id = {r["id"]: r["name"] for r in member_rows}

    # Initialise the same data structures the original code used
    # balances[person][creditor] = amount person owes creditor
    balances    = {m: {x: 0 for x in members if x != m} for m in members}
    total_spent = {m: 0 for m in members}
    transactions = []   # list of [reason, total, payer_name, [[person, share], ...]]

    # Fetch every expense for this trip, joined with payer name
    cur.execute("""
        SELECT e.id, e.description, e.amount, m.name AS payer_name
        FROM   expenses e
        JOIN   members  m ON e.payer_id = m.id
        WHERE  e.trip_id = ?
        ORDER  BY e.created_at
    """, (trip_id,))
    expenses = cur.fetchall()

    for exp in expenses:
        exp_id      = exp["id"]
        reason      = exp["description"]
        total       = exp["amount"]
        payer_name  = exp["payer_name"]
        paymentdetails = [reason, total, payer_name, []]

        # Fetch all splits for this expense
        cur.execute("""
            SELECT es.share_amount, m.name AS member_name
            FROM   expense_splits es
            JOIN   members        m  ON es.member_id = m.id
            WHERE  es.expense_id = ?
        """, (exp_id,))
        splits = cur.fetchall()

        # Reproduce the original process_expense logic exactly
        for split in splits:
            person = split["member_name"]
            share  = split["share_amount"]

            paymentdetails[3].append([person, share])

            # person owes the payer their share (unless person IS the payer)
            if person != payer_name:
                balances[person][payer_name] += share

            total_spent[person] += share

        transactions.append(paymentdetails)

    conn.close()

    # ── Net-settlement calculation (identical to original) ──────────────────
    printed      = set()
    outputpayto  = []

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

    return outputpayto, totspent, transactions_final


# ── CHANGED: was fetch_total_spent_data(session_data) reading session ────────
#            now reads from the DB via calculate_results                ────────
def fetch_total_spent_data(trip_id):
    """
    Return a list of 'member spent ₹X till now' strings by
    re-using calculate_results which reads directly from the DB.
    """
    _, totspent, _ = calculate_results(trip_id)
    if totspent is None:
        return []
    # totspent is already ['Name : ₹X.XX', ...]; reformat to match original output
    return [line.replace(" : ", " spent ") for line in totspent]


# =========================================================
# ── ROUTES ───────────────────────────────────────────────
# =========================================================

@app.route('/')
def home():
    # CHANGED: clear only session navigation keys, not DB data
    session.clear()
    return render_template('base.html')


@app.route('/save_trip', methods=['POST'])
def save_trip():
    trip_name = request.json.get('tripName')
    trip_id   = create_trip(trip_name)

    # Session carries only lightweight navigation state
    session['trip_id']   = trip_id
    session['trip_name'] = trip_name

    return jsonify({
        "message": "Trip saved successfully!",
        "trip_id": trip_id
    })


@app.route('/save_members', methods=['POST'])
def save_members():
    members  = request.json.get('members')
    trip_id  = session.get('trip_id')

    if not trip_id:
        return jsonify({"error": "Trip not found"}), 400

    # CHANGED: members are persisted to DB only (no session dicts any more)
    add_members_to_db(trip_id, members)

    return jsonify({"message": "Members saved successfully!"})


@app.route('/dashboard')
def dashboard():
    trip_name = session.get('trip_name', 'Unknown Trip')
    trip_id   = session.get('trip_id')

    # CHANGED: fetch member names from DB instead of session
    members = []
    if trip_id:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("SELECT name FROM members WHERE trip_id = ?", (trip_id,))
        members = [r["name"] for r in cur.fetchall()]
        conn.close()

    return render_template('dashboard.html', trip_name=trip_name, members=members)


@app.route('/add_expense', methods=['POST'])
def add_expense():
    data = request.get_json() or {}

    if not all(k in data for k in ["reason", "amount", "members", "shares", "whopaid"]):
        return jsonify({"status": "error", "message": "Missing fields"}), 400

    trip_id = session.get('trip_id')
    if not trip_id:
        return jsonify({"status": "error", "message": "Trip not found"}), 400

    try:
        # CHANGED: writes to expenses + expense_splits tables; no session mutation
        process_expense(data, trip_id)
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400

    return jsonify({"status": "success"})


@app.route('/results')
def results():
    trip_id = session.get('trip_id')
    if not trip_id:
        return render_template('results.html', message='no data available')

    # CHANGED: results computed fresh from DB on every request
    payday, totspent, transactions = calculate_results(trip_id)

    if payday is None:
        return render_template('results.html', message='no data available')

    return render_template(
        'results.html',
        message="summary generated",
        transactions=transactions,
        totspent=totspent,
        payday=payday
    )


@app.route('/get_data', methods=['GET'])
def get_data():
    trip_id = session.get('trip_id')
    if not trip_id:
        return jsonify([])

    # CHANGED: reads from DB instead of session
    data = fetch_total_spent_data(trip_id)
    return jsonify(data)


@app.route('/clear_session', methods=['POST'])
def clear_session():
    # CHANGED: only clears the lightweight session; DB data is preserved
    session.clear()
    return '', 204


# ── Run ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True)
