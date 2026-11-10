import os
import sqlite3
from datetime import date
from functools import wraps
from html import escape
from flask import (
    Flask, request, redirect, url_for,
    flash, render_template_string, session
)
from markupsafe import Markup

# ==========================================
# FLASK CONFIGURATION
# ==========================================

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "library-system-secret-key")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Vercel serverless temporary DB support
DATABASE = "/tmp/library.db" if os.environ.get("VERCEL") else "library.db"


# ==========================================
# DATABASE CONNECTION & INITIALIZATION
# ==========================================

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            isbn TEXT NOT NULL UNIQUE,
            total_copies INTEGER NOT NULL,
            available_copies INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT NOT NULL,
            membership_type TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            member_id INTEGER NOT NULL,
            borrow_date TEXT NOT NULL,
            return_date TEXT,
            status TEXT NOT NULL, -- 'Borrowed', 'Returned'
            FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
            FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    conn.close()

init_db()


# ==========================================
# BASE HTML TEMPLATE (Tailwind CSS)
# ==========================================

BASE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Library Management System</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 text-slate-800 min-h-screen flex flex-col">
    <!-- Navbar -->
    <nav class="bg-emerald-900 text-white shadow-md">
        <div class="max-w-7xl mx-auto px-4 py-3 flex justify-between items-center">
            <a href="/" class="text-xl font-bold tracking-wide flex items-center gap-2">📚 Library Management System</a>
            <div class="space-x-2 text-sm font-medium">
                <a href="/" class="px-3 py-2 rounded-lg hover:bg-emerald-800 transition">Dashboard</a>
                <a href="/books" class="px-3 py-2 rounded-lg hover:bg-emerald-800 transition">Books</a>
                <a href="/members" class="px-3 py-2 rounded-lg hover:bg-emerald-800 transition">Members</a>
                <a href="/transactions" class="px-3 py-2 rounded-lg hover:bg-emerald-800 transition">Borrow & Return</a>
            </div>
        </div>
    </nav>

    <!-- Main Content Container -->
    <main class="flex-grow max-w-7xl w-full mx-auto px-4 py-8">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <div class="space-y-3 mb-6">
                    {% for category, message in messages %}
                        {% set colors = {
                            'danger': 'bg-red-50 text-red-700 border-red-200',
                            'success': 'bg-emerald-50 text-emerald-700 border-emerald-200',
                            'info': 'bg-blue-50 text-blue-700 border-blue-200'
                        } %}
                        <div class="p-4 rounded-xl text-sm font-medium border {{ colors.get(category, colors['info']) }}">
                            {{ message }}
                        </div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}

        {{ content | safe }}
    </main>

    <!-- Footer -->
    <footer class="bg-white border-t border-slate-200 text-center py-4 text-sm text-slate-500">
        Academic Lab Project &bull; Flask & Tailwind CSS
    </footer>
</body>
</html>
"""


# ==========================================
# ROUTES: HOME / DASHBOARD
# ==========================================

@app.route("/")
def index():
    conn = get_db_connection()
    total_books = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    total_members = conn.execute("SELECT COUNT(*) FROM members").fetchone()[0]
    active_loans = conn.execute("SELECT COUNT(*) FROM transactions WHERE status = 'Borrowed'").fetchone()[0]
    conn.close()

    content = f"""
    <div class="space-y-8">
        <div class="bg-gradient-to-r from-emerald-800 to-emerald-600 text-white p-8 rounded-2xl shadow-sm">
            <h1 class="text-3xl font-extrabold mb-2">Library Portal & Inventory Dashboard</h1>
            <p class="text-emerald-100 max-w-2xl">Track book catalog stock, manage library members, and monitor active book checkouts and returns.</p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 flex items-center justify-between">
                <div>
                    <p class="text-sm font-medium text-slate-500 uppercase">Book Catalog</p>
                    <p class="text-3xl font-bold text-slate-900 mt-1">{total_books}</p>
                </div>
                <a href="/books" class="p-3 bg-emerald-50 text-emerald-600 rounded-xl hover:bg-emerald-100 transition font-medium text-sm">Manage &rarr;</a>
            </div>
            <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 flex items-center justify-between">
                <div>
                    <p class="text-sm font-medium text-slate-500 uppercase">Library Members</p>
                    <p class="text-3xl font-bold text-slate-900 mt-1">{total_members}</p>
                </div>
                <a href="/members" class="p-3 bg-emerald-50 text-emerald-600 rounded-xl hover:bg-emerald-100 transition font-medium text-sm">Manage &rarr;</a>
            </div>
            <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 flex items-center justify-between">
                <div>
                    <p class="text-sm font-medium text-slate-500 uppercase">Active Loans</p>
                    <p class="text-3xl font-bold text-slate-900 mt-1">{active_loans}</p>
                </div>
                <a href="/transactions" class="p-3 bg-emerald-50 text-emerald-600 rounded-xl hover:bg-emerald-100 transition font-medium text-sm">Manage &rarr;</a>
            </div>
        </div>
    </div>
    """
    return render_template_string(BASE_HTML, content=Markup(content))


# ==========================================
# ROUTES: BOOK MANAGEMENT
# ==========================================

@app.route("/books", methods=["GET", "POST"])
def manage_books():
    conn = get_db_connection()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        isbn = request.form.get("isbn", "").strip()
        copies = request.form.get("copies", "1")

        if not title or not author or not isbn:
            flash("All book fields are required.", "danger")
        else:
            try:
                num_copies = int(copies)
                conn.execute(
                    "INSERT INTO books (title, author, isbn, total_copies, available_copies) VALUES (?, ?, ?, ?, ?)",
                    (title, author, isbn, num_copies, num_copies)
                )
                conn.commit()
                flash("Book added to catalog successfully!", "success")
            except sqlite3.IntegrityError:
                flash("ISBN already exists in the catalog!", "danger")
        return redirect(url_for("manage_books"))

    books = conn.execute("SELECT * FROM books ORDER BY id DESC").fetchall()
    conn.close()

    rows = ""
    for b in books:
        status_badge = f'<span class="px-2 py-1 text-xs font-semibold rounded-full bg-emerald-100 text-emerald-800">{b["available_copies"]} Available</span>' if b["available_copies"] > 0 else '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-red-100 text-red-800">Out of Stock</span>'
        rows += f"""
        <tr class="hover:bg-slate-50 border-b border-slate-100">
            <td class="px-6 py-4 text-sm font-semibold text-slate-900">{escape(b['title'])}</td>
            <td class="px-6 py-4 text-sm text-slate-800">{escape(b['author'])}</td>
            <td class="px-6 py-4 text-sm font-mono text-slate-600">{escape(b['isbn'])}</td>
            <td class="px-6 py-4 text-sm text-slate-600">{b['total_copies']} Total</td>
            <td class="px-6 py-4 text-sm">{status_badge}</td>
        </tr>
        """

    content = f"""
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <!-- Add Book Form -->
        <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 h-fit">
            <h2 class="text-xl font-bold text-slate-900 mb-4">Add New Book</h2>
            <form method="POST" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">Book Title</label>
                    <input type="text" name="title" required class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none">
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">Author Name</label>
                    <input type="text" name="author" required class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none">
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">ISBN Number</label>
                    <input type="text" name="isbn" required class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none">
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">Number of Copies</label>
                    <input type="number" min="1" name="copies" value="3" required class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none">
                </div>
                <button type="submit" class="w-full py-3 bg-emerald-600 text-white font-semibold rounded-xl hover:bg-emerald-700 transition">Save Book</button>
            </form>
        </div>

        <!-- Book Catalog Table -->
        <div class="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div class="bg-slate-900 text-white px-6 py-4">
                <h3 class="font-bold text-lg">Library Book Catalog</h3>
            </div>
            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-slate-200">
                    <thead class="bg-slate-50 text-left text-xs font-semibold text-slate-500 uppercase">
                        <tr>
                            <th class="px-6 py-3">Title</th>
                            <th class="px-6 py-3">Author</th>
                            <th class="px-6 py-3">ISBN</th>
                            <th class="px-6 py-3">Total Copies</th>
                            <th class="px-6 py-3">Availability</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-200 bg-white">
                        {rows if rows else '<tr><td colspan="5" class="px-6 py-6 text-center text-slate-500">No books added yet.</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    """
    return render_template_string(BASE_HTML, content=Markup(content))


# ==========================================
# ROUTES: MEMBER MANAGEMENT
# ==========================================

@app.route("/members", methods=["GET", "POST"])
def manage_members():
    conn = get_db_connection()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        m_type = request.form.get("membership_type", "Student")

        if not name or not email or not phone:
            flash("All member fields are required.", "danger")
        else:
            try:
                conn.execute(
                    "INSERT INTO members (name, email, phone, membership_type) VALUES (?, ?, ?, ?)",
                    (name, email, phone, m_type)
                )
                conn.commit()
                flash("Member registered successfully!", "success")
            except sqlite3.IntegrityError:
                flash("Email address is already registered!", "danger")
        return redirect(url_for("manage_members"))

    members = conn.execute("SELECT * FROM members ORDER BY id DESC").fetchall()
    conn.close()

    rows = ""
    for m in members:
        rows += f"""
        <tr class="hover:bg-slate-50 border-b border-slate-100">
            <td class="px-6 py-4 text-sm font-semibold text-slate-900">{escape(m['name'])}</td>
            <td class="px-6 py-4 text-sm text-slate-600">{escape(m['email'])}</td>
            <td class="px-6 py-4 text-sm text-slate-600">{escape(m['phone'])}</td>
            <td class="px-6 py-4 text-sm font-medium text-emerald-600">{escape(m['membership_type'])}</td>
        </tr>
        """

    content = f"""
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <!-- Add Member Form -->
        <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 h-fit">
            <h2 class="text-xl font-bold text-slate-900 mb-4">Register Member</h2>
            <form method="POST" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">Full Name</label>
                    <input type="text" name="name" required class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none">
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">Email Address</label>
                    <input type="email" name="email" required class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none">
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">Phone Number</label>
                    <input type="text" name="phone" required class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none">
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">Membership Type</label>
                    <select name="membership_type" class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none">
                        <option value="Student">Student</option>
                        <option value="Faculty">Faculty</option>
                        <option value="Researcher">Researcher</option>
                    </select>
                </div>
                <button type="submit" class="w-full py-3 bg-emerald-600 text-white font-semibold rounded-xl hover:bg-emerald-700 transition">Register Member</button>
            </form>
        </div>

        <!-- Members Table -->
        <div class="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div class="bg-slate-900 text-white px-6 py-4">
                <h3 class="font-bold text-lg">Registered Library Members</h3>
            </div>
            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-slate-200">
                    <thead class="bg-slate-50 text-left text-xs font-semibold text-slate-500 uppercase">
                        <tr>
                            <th class="px-6 py-3">Name</th>
                            <th class="px-6 py-3">Email</th>
                            <th class="px-6 py-3">Phone</th>
                            <th class="px-6 py-3">Type</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-200 bg-white">
                        {rows if rows else '<tr><td colspan="4" class="px-6 py-6 text-center text-slate-500">No members registered yet.</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    """
    return render_template_string(BASE_HTML, content=Markup(content))


# ==========================================
# ROUTES: TRANSACTIONS (BORROW / RETURN)
# ==========================================

@app.route("/transactions", methods=["GET", "POST"])
def manage_transactions():
    conn = get_db_connection()
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "borrow":
            book_id = request.form.get("book_id")
            member_id = request.form.get("member_id")
            
            if not book_id or not member_id:
                flash("Please select both a book and a member.", "danger")
            else:
                book = conn.execute("SELECT available_copies FROM books WHERE id = ?", (book_id,)).fetchone()
                if book and book["available_copies"] > 0:
                    conn.execute("UPDATE books SET available_copies = available_copies - 1 WHERE id = ?", (book_id,))
                    conn.execute(
                        "INSERT INTO transactions (book_id, member_id, borrow_date, status) VALUES (?, ?, ?, ?)",
                        (book_id, member_id, str(date.today()), "Borrowed")
                    )
                    conn.commit()
                    flash("Book checked out successfully!", "success")
                else:
                    flash("Selected book is currently out of stock!", "danger")
        
        elif action == "return":
            txn_id = request.form.get("transaction_id")
            if txn_id:
                txn = conn.execute("SELECT book_id FROM transactions WHERE id = ? AND status = 'Borrowed'", (txn_id,)).fetchone()
                if txn:
                    conn.execute("UPDATE transactions SET status = 'Returned', return_date = ? WHERE id = ?", (str(date.today()), txn_id))
                    conn.execute("UPDATE books SET available_copies = available_copies + 1 WHERE id = ?", (txn["book_id"],))
                    conn.commit()
                    flash("Book returned successfully!", "success")
        
        return redirect(url_for("manage_transactions"))

    books = conn.execute("SELECT id, title, available_copies FROM books WHERE available_copies > 0").fetchall()
    members = conn.execute("SELECT id, name, email FROM members").fetchall()
    
    transactions = conn.execute("""
        SELECT transactions.id, books.title, members.name, transactions.borrow_date, transactions.return_date, transactions.status
        FROM transactions
        JOIN books ON transactions.book_id = books.id
        JOIN members ON transactions.member_id = members.id
        ORDER BY transactions.id DESC
    """).fetchall()
    conn.close()

    book_options = "".join([f'<option value="{b["id"]}">{b["title"]} ({b["available_copies"]} left)</option>' for b in books])
    member_options = "".join([f'<option value="{m["id"]}">{m["name"]} ({m["email"]})</option>' for m in members])

    rows = ""
    for t in transactions:
        badge = '<span class="px-2.5 py-1 text-xs font-semibold rounded-full bg-amber-100 text-amber-800">Borrowed</span>' if t["status"] == "Borrowed" else '<span class="px-2.5 py-1 text-xs font-semibold rounded-full bg-emerald-100 text-emerald-800">Returned</span>'
        action_btn = f'''
        <form method="POST" class="inline">
            <input type="hidden" name="action" value="return">
            <input type="hidden" name="transaction_id" value="{t["id"]}">
            <button type="submit" class="px-3 py-1 bg-emerald-50 text-emerald-700 rounded-lg text-xs font-medium hover:bg-emerald-100 transition">Return Book</button>
        </form>
        ''' if t["status"] == "Borrowed" else f'<span class="text-xs text-slate-400">Completed ({t["return_date"]})</span>'

        rows += f"""
        <tr class="hover:bg-slate-50 border-b border-slate-100">
            <td class="px-6 py-4 text-sm font-semibold text-slate-900">{escape(t['title'])}</td>
            <td class="px-6 py-4 text-sm text-slate-800">{escape(t['name'])}</td>
            <td class="px-6 py-4 text-sm text-slate-600">{t['borrow_date']}</td>
            <td class="px-6 py-4 text-sm">{badge}</td>
            <td class="px-6 py-4 text-sm">{action_btn}</td>
        </tr>
        """

    content = f"""
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <!-- Borrow Form -->
        <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 h-fit">
            <h2 class="text-xl font-bold text-slate-900 mb-4">Checkout Book</h2>
            <form method="POST" class="space-y-4">
                <input type="hidden" name="action" value="borrow">
                <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">Select Book</label>
                    <select name="book_id" required class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none">
                        <option value="">Choose available book...</option>
                        {book_options}
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">Select Member</label>
                    <select name="member_id" required class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none">
                        <option value="">Choose member...</option>
                        {member_options}
                    </select>
                </div>
                <button type="submit" class="w-full py-3 bg-emerald-600 text-white font-semibold rounded-xl hover:bg-emerald-700 transition">Issue Book</button>
            </form>
        </div>

        <!-- Transactions Table -->
        <div class="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div class="bg-slate-900 text-white px-6 py-4">
                <h3 class="font-bold text-lg">Borrow & Return Activity Log</h3>
            </div>
            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-slate-200">
                    <thead class="bg-slate-50 text-left text-xs font-semibold text-slate-500 uppercase">
                        <tr>
                            <th class="px-6 py-3">Book Title</th>
                            <th class="px-6 py-3">Member Name</th>
                            <th class="px-6 py-3">Borrow Date</th>
                            <th class="px-6 py-3">Status</th>
                            <th class="px-6 py-3">Action</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-200 bg-white">
                        {rows if rows else '<tr><td colspan="5" class="px-6 py-6 text-center text-slate-500">No active transactions recorded yet.</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    """
    return render_template_string(BASE_HTML, content=Markup(content))


# ==========================================
# RUN APPLICATION
# ==========================================

if __name__ == "__main__":
    app.run(debug=True)