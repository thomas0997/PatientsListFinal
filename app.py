import csv
import sqlite3
import os
import io
from datetime import datetime
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, redirect, flash, url_for, send_file, jsonify, session

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
basedir = os.path.abspath(os.path.dirname(__file__))

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# ---------- DATABASE ----------
def get_patient_db():
    conn = sqlite3.connect(os.path.join(basedir, "patients.db"))
    conn.row_factory = sqlite3.Row
    return conn

def get_inventory_db():
    conn = sqlite3.connect(os.path.join(basedir, "inventory.db"))
    conn.row_factory = sqlite3.Row
    return conn

# ---------- FORCE LOGOUT ON FIRST REQUEST ----------
@app.before_request
def force_logout_on_visit():
    if request.endpoint == "index":
        session.clear()

# ---------- AUTH ----------
@app.route("/reg1", methods=["GET", "POST"])
def register_user():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            flash("All fields are required.")
            return redirect("/reg1")

        db = get_inventory_db()
        existing = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            flash("Username already exists.")
            return redirect("/reg1")

        hash_pw = generate_password_hash(password)
        db.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hash_pw))
        db.commit()
        flash("✅ Account created! Please log in.")
        return redirect("/login")

    return render_template("reg1.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        db = get_inventory_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session["name"] = username
            return redirect("/index")
        else:
            flash("Login failed. Try again.")
            return redirect("/login")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---------- MAIN ROUTES ----------
@app.route("/")
def index():
    return redirect("/login")

@app.route("/index")
def main_dashboard():
    if "name" not in session:
        return redirect("/login")
    return render_template("index.html", name=session["name"])

@app.route("/add", methods=["GET", "POST"])
def add():
    return render_template("add.html")

@app.route("/patients")
def patients_home():
    return render_template("patientslist.html")

@app.route("/search")
def search():
    db = get_patient_db()
    query = request.args.get("query")
    patients = []
    if query:
        words = query.strip().split()
        if len(words) == 2:
            patients = db.execute("SELECT * FROM patients WHERE firstName LIKE ? AND lastName LIKE ?", (f"%{words[0]}%", f"%{words[1]}%")).fetchall()
        else:
            patients = db.execute("SELECT * FROM patients WHERE firstName LIKE ? OR lastName LIKE ?", (f"%{query}%", f"%{query}%")).fetchall()
    return render_template("search.html", patients=patients, searched=bool(query))

@app.route("/register", methods=["POST"])
def register():
    db = get_patient_db()
    first = request.form.get("firstName")
    last = request.form.get("lastName")
    dob = request.form.get("dob")
    address = request.form.get("address")
    if not first or not last or not dob:
        return render_template("failure.html")
    missing_id = db.execute("SELECT MIN(t1.id + 1) AS next_id FROM patients t1 LEFT JOIN patients t2 ON t1.id + 1 = t2.id WHERE t2.id IS NULL").fetchone()["next_id"]
    next_id = missing_id if missing_id else (db.execute("SELECT MAX(id) AS max_id FROM patients").fetchone()["max_id"] or 0) + 1
    db.execute("INSERT INTO patients (id, firstName, lastName, dob, address) VALUES (?, ?, ?, ?, ?)", (next_id, first, last, dob, address))
    db.commit()
    return render_template("success.html")

@app.route("/results")
def results():
    db = get_patient_db()
    patients = db.execute("SELECT * FROM patients").fetchall()
    return render_template("find.html", patients=patients)

@app.route("/remove/<int:id>", methods=["POST"])
def remove(id):
    db = get_patient_db()
    db.execute("DELETE FROM patients WHERE id = ?", (id,))
    db.commit()
    return redirect("/search")

@app.route("/view")
def view():
    db = get_patient_db()
    patients = db.execute("SELECT * FROM patients").fetchall()
    return render_template("view.html", patients=patients)

# ---------- INVENTORY ----------
@app.route("/inventory")
def inventory_menu():
    return render_template("inventory/index.html")

@app.route("/inventory/view")
def inventory_view():
    sort = request.args.get("sort", "desc")
    order = "DESC" if sort == "desc" else "ASC"
    db = get_inventory_db()
    meds = db.execute(f"SELECT * FROM medicines ORDER BY quantity {order}").fetchall()
    return render_template("inventory/view.html", meds=meds, sort=sort)

@app.route("/inventory/logs")
def inventory_logs():
    db = get_inventory_db()
    logs = db.execute("SELECT * FROM logs ORDER BY id DESC").fetchall()
    return render_template("inventory/logs.html", logs=logs)

@app.route("/inventory/logs/clear", methods=["POST"])
def clear_inventory_logs():
    db = get_inventory_db()
    db.execute("DELETE FROM logs")
    db.commit()
    flash("All logs have been cleared.")
    return redirect("/inventory/logs")

@app.route("/inventory/add", methods=["GET", "POST"])
def add_medicine():
    if request.method == "POST":
        name = request.form.get("name")
        quantity = int(request.form.get("quantity") or 0)
        user = session.get("name", "Unknown")
        if not name or quantity < 0:
            flash("Invalid input.")
            return redirect(request.url)
        db = get_inventory_db()
        db.execute("INSERT OR REPLACE INTO medicines (name, quantity) VALUES (?, ?)", (name, quantity))
        db.execute("INSERT INTO logs (medicine_name, change, timestamp, user) VALUES (?, ?, ?, ?)", (name, quantity, datetime.now().isoformat(), user))
        db.commit()
        return render_template("inventory/success.html")
    return render_template("inventory/add.html")

@app.route("/inventory/find", methods=["GET", "POST"])
def inventory_find():
    meds = []
    searched = False
    if request.method == "POST":
        name = request.form.get("query")
        db = get_inventory_db()
        meds = db.execute("SELECT * FROM medicines WHERE name LIKE ?", (f"%{name}%",)).fetchall()
        searched = True
    return render_template("inventory/find.html", meds=meds, searched=searched)

@app.route("/inventory/remove/<name>", methods=["POST"])
def remove_medicine(name):
    db = get_inventory_db()
    db.execute("DELETE FROM medicines WHERE name = ?", (name,))
    db.execute("DELETE FROM logs WHERE medicine_name = ?", (name,))
    db.commit()
    return redirect("/inventory/view")

@app.route("/inventory/ajax-update/<name>", methods=["POST"])
def ajax_update_quantity(name):
    data = request.get_json()
    action = data.get("action")
    db = get_inventory_db()
    med = db.execute("SELECT * FROM medicines WHERE name = ?", (name,)).fetchone()
    if not med:
        return jsonify({"error": "Medicine not found"}), 404

    change = 1 if action == "add" else -1
    new_qty = max(0, med["quantity"] + change)
    db.execute("UPDATE medicines SET quantity = ? WHERE name = ?", (new_qty, name))

    username = session.get("name", "Unknown")

    today = datetime.now().date().isoformat()
    existing_log = db.execute(
        "SELECT id, change FROM logs WHERE medicine_name = ? AND date(timestamp) = ? ORDER BY id DESC LIMIT 1",
        (name, today)
    ).fetchone()

    if existing_log:
        new_change = existing_log["change"] + change
        db.execute(
            "UPDATE logs SET change = ?, timestamp = ?, user = ? WHERE id = ?",
            (new_change, datetime.now().isoformat(), username, existing_log["id"])
        )
    else:
        db.execute(
            "INSERT INTO logs (medicine_name, change, timestamp, user) VALUES (?, ?, ?, ?)",
            (name, change, datetime.now().isoformat(), username)
        )

    db.commit()
    return jsonify({"quantity": new_qty})

# ---------- RUN ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)