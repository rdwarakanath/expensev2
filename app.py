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
# ── ACCESS CONTROL HELPER ────────────────────────────────
# =========================================================

def check_trip_access(trip_id, user_id, conn=None):
    """
    Returns trip row only if user has ACCEPTED access via trip_users.
    Pending and rejected users are blocked.
    """
    close_after = False
    if conn is None:
        conn = get_db()
        close_after = True
    cur = conn.cursor()
    cur.execute("""
        SELECT t.id, t.trip_name, t.is_active, t.created_by
        FROM   trips      t
        JOIN   trip_users tu ON tu.trip_id = t.id
        WHERE  t.id = ? AND tu.user_id = ? AND tu.status = 'accepted'
    """, (trip_id, user_id))
    row = cur.fetchone()
    if close_after:
        conn.close()
    return row


def is_trip_creator(trip_id, user_id, conn=None):
    """Returns True if user is the creator of the trip."""
    close_after = False
    if conn is None:
        conn = get_db()
        close_after = True
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM trips WHERE id = ? AND created_by = ?",
        (trip_id, user_id)
    )
    row = cur.fetchone()
    if close_after:
        conn.close()
    return row is not None


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
    return expense_id   # returned so route can pass it to JS


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
    Shows accepted trips and pending invites separately.
    Accepted trips: user can access dashboard/results.
    Pending invites: shown in a separate section with Accept/Reject buttons.
    """
    user_id = session['user_id']
    conn    = get_db()
    cur     = conn.cursor()

    # Accepted trips only
    cur.execute("""
        SELECT t.id, t.trip_name, t.is_active, t.created_at, t.created_by
        FROM   trips      t
        JOIN   trip_users tu ON tu.trip_id = t.id
        WHERE  tu.user_id = ? AND tu.status = 'accepted'
        ORDER  BY t.created_at DESC
    """, (user_id,))
    trips = [dict(r) for r in cur.fetchall()]

    # Pending invites — trips this user was invited to but hasn't responded
    cur.execute("""
        SELECT t.id, t.trip_name, t.created_at,
               u.username AS invited_by
        FROM   trips      t
        JOIN   trip_users tu  ON tu.trip_id  = t.id
        JOIN   users      u   ON u.id        = t.created_by
        WHERE  tu.user_id = ? AND tu.status = 'pending'
        ORDER  BY t.created_at DESC
    """, (user_id,))
    pending_invites = [dict(r) for r in cur.fetchall()]

    conn.close()

    return render_template('home.html',
                           username=session['username'],
                           user_id=user_id,
                           creator_username=session['username'],
                           trips=trips,
                           pending_invites=pending_invites)


# =========================================================
# ── TRIP CREATION ROUTES ──────────────────────────────────
# =========================================================


@app.route('/search_users')
@login_required
def search_users():
    """
    Returns usernames matching the query string (for dropdown suggestions).
    Excludes the current user since they are already the creator.
    """
    q       = request.args.get('q', '').strip().lower()
    user_id = session['user_id']
    if len(q) < 1:
        return jsonify([])
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        SELECT username FROM users
        WHERE  LOWER(username) LIKE ?
        LIMIT  8
    """, (f'%{q}%',))
    results = [r['username'] for r in cur.fetchall()]
    conn.close()
    return jsonify(results)

@app.route('/create_trip', methods=['POST'])
@login_required
def create_trip_route():
    """
    Atomic trip creation with multi-user support.
    Receives: tripName, members = [{alias, username}]
    - Creates trip with created_by = current user
    - Inserts creator into trip_users
    - For each member: looks up username in users table
        - Found → sets members.user_id, inserts into trip_users
        - Not found → alias only, no access granted
    - Validates: alias required, no duplicate aliases,
                 no duplicate usernames in same trip
    """
    data      = request.get_json() or {}
    trip_name = data.get('tripName', '').strip()
    members   = data.get('members', [])   # [{alias, username}]
    user_id   = session['user_id']

    if not trip_name:
        return jsonify({"error": "Trip name is required"}), 400
    if not members or len(members) < 1:
        return jsonify({"error": "At least one member is required"}), 400

    # Validate all aliases present and unique (case-insensitive)
    aliases = [m.get('alias', '').strip().lower() for m in members]
    if any(a == '' for a in aliases):
        return jsonify({"error": "All members must have an alias"}), 400
    if len(set(aliases)) != len(aliases):
        return jsonify({"error": "Duplicate alias names are not allowed"}), 400

    # Validate usernames unique among those provided (ignore blank ones)
    usernames_provided = [m.get('username', '').strip().lower()
                          for m in members if m.get('username', '').strip()]
    if len(set(usernames_provided)) != len(usernames_provided):
        return jsonify({"error": "Duplicate usernames are not allowed"}), 400

    conn = get_db()
    cur  = conn.cursor()
    try:
        # 1. Insert trip
        cur.execute(
            "INSERT INTO trips (trip_name, created_by, is_active) VALUES (?, ?, 1)",
            (trip_name, user_id)
        )
        trip_id = cur.lastrowid

        # 2. Insert creator into trip_users
        cur.execute(
            "INSERT OR IGNORE INTO trip_users (trip_id, user_id) VALUES (?, ?)",
            (trip_id, user_id)
        )

        # 3. Insert each member
        for m in members:
            alias  = m.get('alias', '').strip().lower()
            uname  = m.get('username', '').strip().lower()
            is_creator_row = m.get('is_creator', False)

            if is_creator_row:
                # Creator row — already in trip_users as accepted, add to members
                cur.execute(
                    "INSERT INTO members (trip_id, name, user_id) VALUES (?, ?, ?)",
                    (trip_id, alias, user_id)
                )
            elif uname:
                # Username provided — look up in users table
                cur.execute("SELECT id FROM users WHERE LOWER(username) = ?", (uname,))
                urow = cur.fetchone()
                if urow:
                    member_uid = urow['id']
                    # Insert into trip_users as PENDING — NOT into members yet
                    cur.execute(
                        "INSERT OR IGNORE INTO trip_users (trip_id, user_id, status) VALUES (?, ?, 'pending')",
                        (trip_id, member_uid)
                    )
                    # Do NOT insert into members — only added on invite acceptance
                else:
                    # Username not found → treat as alias-only member
                    cur.execute(
                        "INSERT INTO members (trip_id, name, user_id) VALUES (?, ?, NULL)",
                        (trip_id, alias)
                    )
            else:
                # No username — alias-only member, add directly to members
                cur.execute(
                    "INSERT INTO members (trip_id, name, user_id) VALUES (?, ?, NULL)",
                    (trip_id, alias)
                )

        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

    return jsonify({"message": "Trip created!", "trip_id": trip_id})


# Kept for backward compatibility but no longer used by the frontend
@app.route('/save_trip', methods=['POST'])
@login_required
def save_trip():
    return jsonify({"message": "Use /create_trip instead"}), 410


@app.route('/save_members', methods=['POST'])
@login_required
def save_members():
    return jsonify({"message": "Use /create_trip instead"}), 410


# =========================================================
# ── DASHBOARD — URL-BASED ─────────────────────────────────
# =========================================================

@app.route('/dashboard/<int:trip_id>')
@login_required
def dashboard(trip_id):
    user_id = session['user_id']
    trip    = check_trip_access(trip_id, user_id)
    if not trip:
        return "Trip not found or access denied.", 404

    if not trip['is_active']:
        return redirect(url_for('results', trip_id=trip_id))

    conn = get_db()
    cur  = conn.cursor()
    cur.execute("SELECT name FROM members WHERE trip_id = ?", (trip_id,))
    members = [r["name"] for r in cur.fetchall()]
    conn.close()

    is_creator = is_trip_creator(trip_id, user_id)
    return render_template('dashboard.html',
                           trip_name=trip['trip_name'],
                           trip_id=trip_id,
                           members=members,
                           is_creator=is_creator)


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

    trip = check_trip_access(trip_id, user_id)
    if not trip:
        return jsonify({"status": "error", "message": "Trip not found or access denied"}), 404
    if not trip['is_active']:
        return jsonify({"status": "error", "message": "This trip is finished."}), 403

    try:
        expense_id = process_expense(data, trip_id)   # returns new expense_id
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400

    return jsonify({"status": "success", "expense_id": expense_id})


@app.route('/get_data/<int:trip_id>', methods=['GET'])
@login_required
def get_data(trip_id):
    user_id = session['user_id']
    trip    = check_trip_access(trip_id, user_id)
    if not trip:
        return jsonify([])

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

    # Access check via trip_users
    if not check_trip_access(trip_id, user_id):
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
            "id":      exp["id"],          # needed for delete_expense route
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

    # Only creator can finish a trip
    if not is_trip_creator(trip_id, user_id):
        conn.close()
        return jsonify({"status": "error", "message": "Only the trip creator can finish this trip"}), 403

    cur.execute(
        "UPDATE trips SET is_active = 0 WHERE id = ?",
        (trip_id,)
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
    trip = check_trip_access(trip_id, user_id)
    if not trip:
        return "Trip not found or access denied.", 404

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




# =========================================================
# ── INVITE ROUTES ─────────────────────────────────────────
# =========================================================

@app.route('/accept_invite/<int:trip_id>', methods=['POST'])
@login_required
def accept_invite(trip_id):
    """
    Accept a pending invite:
    1. Set trip_users.status = 'accepted'
    2. Add user to members table with their alias
    Alias is sent in the POST body.
    """
    user_id = session['user_id']
    data    = request.get_json() or {}
    alias   = data.get('alias', '').strip().lower()

    if not alias:
        return jsonify({"status": "error", "message": "Alias is required to accept invite"}), 400

    conn = get_db()
    cur  = conn.cursor()

    # Verify invite is actually pending for this user
    cur.execute("""
        SELECT status FROM trip_users
        WHERE trip_id = ? AND user_id = ?
    """, (trip_id, user_id))
    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify({"status": "error", "message": "Invite not found"}), 404
    if row['status'] != 'pending':
        conn.close()
        return jsonify({"status": "error", "message": "Invite already responded to"}), 400

    # Check alias uniqueness in this trip
    cur.execute(
        "SELECT id FROM members WHERE trip_id = ? AND name = ?",
        (trip_id, alias)
    )
    if cur.fetchone():
        conn.close()
        return jsonify({"status": "error", "message": f"Alias '{alias}' is already taken in this trip"}), 400

    try:
        # Mark as accepted
        cur.execute("""
            UPDATE trip_users SET status = 'accepted'
            WHERE trip_id = ? AND user_id = ?
        """, (trip_id, user_id))

        # Add to members table now that invite is accepted
        cur.execute(
            "INSERT INTO members (trip_id, name, user_id) VALUES (?, ?, ?)",
            (trip_id, alias, user_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

    return jsonify({"status": "success"})


@app.route('/reject_invite/<int:trip_id>', methods=['POST'])
@login_required
def reject_invite(trip_id):
    """
    Reject a pending invite:
    Sets trip_users.status = 'rejected'.
    User is NOT added to members. They lose all trip visibility.
    """
    user_id = session['user_id']
    conn    = get_db()
    cur     = conn.cursor()

    cur.execute("""
        SELECT status FROM trip_users
        WHERE trip_id = ? AND user_id = ?
    """, (trip_id, user_id))
    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify({"status": "error", "message": "Invite not found"}), 404
    if row['status'] != 'pending':
        conn.close()
        return jsonify({"status": "error", "message": "Invite already responded to"}), 400

    try:
        cur.execute("""
            UPDATE trip_users SET status = 'rejected'
            WHERE trip_id = ? AND user_id = ?
        """, (trip_id, user_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

    return jsonify({"status": "success"})

# =========================================================
# ── DELETE ROUTES ─────────────────────────────────────────
# =========================================================

@app.route('/delete_trip/<int:trip_id>', methods=['POST'])
@login_required
def delete_trip(trip_id):
    """
    Full trip delete — only the creator can do this.
    Non-creators should use /leave_trip instead.
    Manual cascade: expense_splits → expenses → members → trip_users → trip
    """
    user_id = session['user_id']

    if not is_trip_creator(trip_id, user_id):
        return jsonify({"status": "error", "message": "Only the trip creator can delete this trip"}), 403

    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("""
            DELETE FROM expense_splits
            WHERE expense_id IN (SELECT id FROM expenses WHERE trip_id = ?)
        """, (trip_id,))
        cur.execute("DELETE FROM expenses WHERE trip_id = ?", (trip_id,))
        cur.execute("DELETE FROM members WHERE trip_id = ?", (trip_id,))
        cur.execute("DELETE FROM trip_users WHERE trip_id = ?", (trip_id,))
        cur.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

    return jsonify({"status": "success"})


@app.route('/leave_trip/<int:trip_id>', methods=['POST'])
@login_required
def leave_trip(trip_id):
    """
    Non-creator leaves a trip — removes only their trip_users row.
    If they were the last user, auto-deletes the entire trip.
    Creator cannot leave — they must delete instead.
    """
    user_id = session['user_id']

    if not check_trip_access(trip_id, user_id):
        return jsonify({"status": "error", "message": "Trip not found or access denied"}), 404

    if is_trip_creator(trip_id, user_id):
        return jsonify({"status": "error",
                        "message": "You created this trip. Use Delete instead of Leave."}), 403

    conn = get_db()
    cur  = conn.cursor()
    try:
        # Get member id for this user in this trip (needed to clean up splits)
        cur.execute(
            "SELECT id FROM members WHERE trip_id = ? AND user_id = ?",
            (trip_id, user_id)
        )
        member_row = cur.fetchone()

        if member_row:
            member_id = member_row['id']
            # Delete expense_splits referencing this member FIRST
            # (FK constraint: expense_splits.member_id → members.id)
            cur.execute(
                "DELETE FROM expense_splits WHERE member_id = ?",
                (member_id,)
            )
            # Now safe to delete from members
            cur.execute(
                "DELETE FROM members WHERE id = ?",
                (member_id,)
            )

        # Remove from trip_users
        cur.execute(
            "DELETE FROM trip_users WHERE trip_id = ? AND user_id = ?",
            (trip_id, user_id)
        )

        # Check if anyone still has access (accepted users only)
        cur.execute("""
            SELECT COUNT(*) AS cnt FROM trip_users
            WHERE trip_id = ? AND status = 'accepted'
        """, (trip_id,))
        remaining = cur.fetchone()['cnt']

        if remaining == 0:
            # Last accepted user left — auto delete everything
            # Must delete in correct FK order: splits → expenses → members
            # → trip_users (pending/rejected rows) → trip
            cur.execute("""
                DELETE FROM expense_splits
                WHERE expense_id IN (SELECT id FROM expenses WHERE trip_id = ?)
            """, (trip_id,))
            cur.execute("DELETE FROM expenses WHERE trip_id = ?", (trip_id,))
            cur.execute("DELETE FROM members WHERE trip_id = ?", (trip_id,))
            cur.execute("DELETE FROM trip_users WHERE trip_id = ?", (trip_id,))
            cur.execute("DELETE FROM trips WHERE id = ?", (trip_id,))

        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

    return jsonify({"status": "success"})


@app.route('/delete_expense/<int:expense_id>', methods=['POST'])
@login_required
def delete_expense(expense_id):
    """
    Delete a single expense and its splits.
    Verifies the expense belongs to a trip owned by the current user.
    Only allowed on active trips (finished trips are read-only).
    """
    user_id = session['user_id']
    conn    = get_db()
    cur     = conn.cursor()

    # Verify expense exists and user has ACCEPTED access to its trip
    cur.execute("""
        SELECT e.id, t.is_active
        FROM   expenses   e
        JOIN   trips      t  ON e.trip_id  = t.id
        JOIN   trip_users tu ON tu.trip_id = t.id
        WHERE  e.id = ? AND tu.user_id = ? AND tu.status = 'accepted'
    """, (expense_id, user_id))
    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify({"status": "error", "message": "Expense not found or unauthorized"}), 404

    if not row['is_active']:
        conn.close()
        return jsonify({"status": "error", "message": "Cannot edit a finished trip"}), 403

    try:
        # Delete splits first, then expense
        cur.execute("DELETE FROM expense_splits WHERE expense_id = ?", (expense_id,))
        cur.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

    return jsonify({"status": "success"})

# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True)
