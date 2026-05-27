# PayBait — Split Bills, Not Friendships

PayBait is a full-stack trip expense manager designed for collaborative group use. It allows members to log shared expenses, track payments, configure customisable splits, and resolve debts with minimal transactions. A greedy debt simplification algorithm reduces a complex web of obligations into the minimum number of direct payments required to settle all balances.

Built with a **Python/Flask** backend, a **PostgreSQL** relational database with optimised indexing, and a glassmorphic frontend in Vanilla CSS and ES6 JavaScript.

**Live Demo**: [paybait.onrender.com](https://paybait.onrender.com)
---
## Screenshots

<table>
  <tr>
    <td align="center"><b>Login</b></td>
    <td align="center"><b>InvitePanel</b></td>
    <td align="center"><b>Dashboard</b></td>
  </tr>
  <tr>
    <td><img src="screenshots/login.png" width="220"/></td>
    <td><img src="screenshots/invite.png" width="220"/></td>
    <td><img src="screenshots/dashboard.png" width="220"/></td>
  </tr>
  <tr>
    <td align="center"><b>Expense Entry</b></td>
    <td align="center"><b>Results & Settlement</b></td>
    <td align="center"><b>QR Share</b></td>
  </tr>
  <tr>
    <td><img src="screenshots/expense.png" width="220"/></td>
    <td><img src="screenshots/results.png" width="220"/></td>
    <td><img src="screenshots/qr.png" width="220"/></td>
  </tr>
</table>

## Key Features

### 1. Multi-User Trip Creation — Three-Step Guided Flow

- **Step 1 — Trip Naming**: The trip name is validated and sanitised server-side, with a maximum of 100 characters.
- **Step 2 — Member Count**: Configures the number of additional participants joining the trip.
- **Step 3 — Member Invitations**:
  - Existing users are searchable via a real-time debounced autocomplete dropdown.
  - Non-app participants may be added using a custom offline alias.
  - **Mutual Field Blocking**: The alias input is disabled when a username is entered, and vice versa, preventing duplicate entries and schema conflicts at the point of submission.

### 2. Invitation System and Side Panel

Invited users receive notifications in their Invites Panel on the landing dashboard. Each user may accept an invitation (selecting a personal alias for that trip) or reject it, preserving the trip structure for other members.

### 3. Real-Time Expense Dashboard

- **Custom Split Configuration**: Expenses can be divided evenly among members or assigned precise custom values per participant.
- **Instant Recalculation**: Balance totals and spending summaries update immediately on expense creation or deletion, without a page reload.
- **Read-Only Finalisation**: The trip creator may finalise a trip, locking all expenses and disabling modifications. The dashboard converts to a clean, read-only results view.

### 4. Greedy Debt Simplification Algorithm

- **Net Balance Calculation**: Computes each member's net position (total paid minus total owed).
- **Optimised Settlement**: Implements a greedy matching algorithm to minimise the number of transactions required.
  - Creditors (net balance > 0) and debtors (net balance < 0) are sorted in descending order by magnitude.
  - The largest debtor is matched against the largest creditor iteratively until all balances are settled.
  - A toggle allows users to switch between the original and optimised transaction views.
- **Per-Member Filtering**: Clicking a member's avatar filters the settlement list to display only transactions involving that individual.

### 5. QR Code Sharing and Public URL Tokens

PayBait generates a secure public token for each trip, rendering an on-demand base64 QR code and a shareable URL. The public link presents the trip summary in a secure, read-only state, with no authentication required.

### 6. Access Control and Membership Management

- **Creator Permissions**: Only the trip creator may add or remove members, finalise the trip, or delete it entirely.
- **Safe Departure**: Non-creator members may leave a trip at any time. Their account is unlinked, but all historical split data and aliases are preserved to maintain calculation integrity.
- **Cascading Cleanup**: If the last active member leaves a trip, the backend executes an automated multi-table cleanup, removing all associated expenses, splits, and orphaned database rows.

---

## Architecture and Technology Stack

![Architecture Diagram](workflow.png)

### Backend — Python 3.12 / Flask

- **Framework**: Flask, configured for standard production environments.
- **Session Management**: Permanent session lifetimes of two hours, with automated refresh on active requests.
- **Rate Limiting**: Flask-Limiter backed by **Redis** (Render Key Value) for persistent, process-safe rate limit state. Custom limits are applied to critical routes (login, signup, user autocomplete) to mitigate brute-force and denial-of-service attempts.
- **WSGI Server**: Gunicorn with worker processes calculated as `(2 × CPU cores) + 1`.

### Database Schema — Supabase PostgreSQL

A fully indexed relational schema with the following tables:

- **`users`**: Stores encrypted credentials with automatic timestamps.
- **`trips`**: Stores trip metadata linked to a creator, with a unique public hash token for link sharing.
- **`members`**: Maps usernames and aliases to their respective trips.
- **`expenses`**: The raw transaction ledger, linking each expense to a payer and trip.
- **`expense_splits`**: Maps each expense fraction to the corresponding member.
- **`trip_users`**: Tracks invitation status (`accepted`, `pending`, `rejected`) for each user–trip pair.

All foreign keys are explicitly indexed to optimise lookup performance on nested balance calculations.

---

## Security

- **Secure Cookies**: Session cookies are set with `SESSION_COOKIE_SECURE = True` (HTTPS-only transmission) and `SESSION_COOKIE_HTTPONLY = True` (preventing client-side script access).
- **CSRF Mitigation**: `SESSION_COOKIE_SAMESITE = 'Lax'` is enforced to defend against cross-site request forgery.
- **Security Headers**:
  - `X-Content-Type-Options: nosniff` — prevents MIME-type sniffing.
  - `X-Frame-Options: DENY` — prevents clickjacking via iframe embedding.
- **SQL Injection Prevention**: No raw SQL string interpolation. All database interactions use parameterised queries via `psycopg2`.
- **Password Storage**: Plaintext passwords are never stored. Passwords are hashed using PBKDF2-HMAC via `werkzeug.security`.
- **Connection Pool Management**: A `psycopg2.pool.SimpleConnectionPool` is used, bounded between 1 and 10 connections, to prevent database resource exhaustion. The pool issues a keepalive ping every 30 seconds to maintain live connections against **Supabase PostgreSQL**'s idle timeout, avoiding stale connection errors under low traffic.
- **Authorisation Decorators**: `check_trip_access` and `is_trip_creator` decorators run on every relevant request, verifying that the requesting user's invitation status is `accepted` before any private trip data is served.

---

## SEO and Crawler Policies

### Semantic Markup and Metadata

- All templates are fully mobile-responsive and use semantic HTML5 elements (`<header>`, `<nav>`, `<section>`).
- Web fonts (Syne and DM Sans) are loaded with print fallbacks to prevent flash of unstyled content (FOUC).
- Custom `<meta name="description">` tags are defined for all application routes.

### `robots.txt`

- **Allowed**: Public landing pages (`/`, `/home`).
- **Disallowed**: Authentication endpoints (`/login`, `/signup`), private dashboards (`/dashboard/`), trip result pages (`/results/`), and backend files (`/init_db.py`, `/static/`).

---

## Design System

- **Animated Background**: Floating mesh gradient orbs with CSS keyframe animation.
- **Noise Overlay**: An SVG grain overlay applied to panels and modals for visual texture.
- **Colour Palette**: HSL-based gradients with high-contrast semantic tokens — warm warnings, emerald active states, and soft ruby error indicators.
- **Glassmorphic Panels**: `backdrop-filter: blur(20px)` on card elements, with micro-interaction scale transitions and shake animations on invalid input fields.

---

## Error Handling

Dedicated error screens are mapped to Flask error handlers:

- **400 Bad Request**: Triggered on invalid submissions or missing query parameters.
- **404 Not Found**: A contextually themed "page not found" screen.
- **429 Too Many Requests**: Displays a pulse-animated rate-limit warning.
- **500 Internal Server Error**: A recovery screen with a direct return path to the home page, without exposing any server diagnostics.

---

## Installation

### Prerequisites

- Python 3.9 or later (Python 3.12 recommended)
- A running PostgreSQL instance
- `pip` or a virtual environment manager

---

### Step 1 — Clone the Repository and Create a Virtual Environment

```bash
# Create a virtual environment
python -m venv venv

# Activate — Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Activate — macOS / Linux
source venv/bin/activate
```

---

### Step 2 — Install Dependencies

```bash
pip install -r requirements.txt
```

**Core packages:**

- `Flask==3.1.3` — Web framework
- `Flask-Limiter==4.1.1` — IP-based request throttling
- `psycopg2-binary==2.9.12` — PostgreSQL adapter
- `python-dotenv==1.2.2` — Environment variable loader
- `qrcode==8.2` and `pillow==12.2.0` — QR code generation
- `gunicorn==23.0.0` — Production WSGI server

---

### Step 3 — Configure Environment Variables

Create a `.env` file in the project root:

```env
# PostgreSQL connection string
DATABASE_URL=postgresql://your_db_user:your_db_password@your_db_host:5432/your_db_name

# Secret key for signing session cookies
SECRET_KEY=your_highly_secure_random_string_here

# Base URL for generating shareable QR codes and links
BASE_URL=http://127.0.0.1:5000
```

---

### Step 4 — Initialise the Database Schema

```bash
python init_db.py
```

Expected output:

```
PostgreSQL database initialised successfully.
Tables: users, trips, trip_users, members, expenses, expense_splits
```

---

### Step 5 — Start the Application

#### Development

```bash
# Windows (PowerShell)
$env:FLASK_APP="app.py"
flask run

# macOS / Linux
export FLASK_APP=app.py
flask run
```

Access the application at `http://127.0.0.1:5000`.

#### Production (Gunicorn)

```bash
gunicorn -c gunicorn.conf.py app:app
```

Gunicorn reads the CPU count, spawns the appropriate number of worker processes, and binds to the configured port (default: 5000).

---

## Planned Improvements

1. **Multi-Currency Support** — Live exchange rate integration for international travel groups.
2. **Horizontal Scaling** — Gunicorn worker count currently optimised for a single Render dyno. Redis-backed rate limiting is already in place, so the architecture is ready for multi-instance deployment when needed.
3. **Receipt OCR** — Automated item parsing from photographed bills using a machine learning pipeline.