import csv
import sqlite3
import os
from flask import Flask, render_template, request, redirect

app = Flask(__name__)

basedir = os.path.abspath(os.path.dirname(__file__))

# Connect to SQLite DB with absolute path
def get_db():
    conn = sqlite3.connect(os.path.join(basedir, "patients.db"))
    conn.row_factory = sqlite3.Row  # For dict-style access (e.g., row["firstName"])
    return conn

# Import CSV
@app.route("/import_csv")
def import_csv():
    db = get_db()
    with open('patients.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            db.execute(
                "INSERT INTO patients (firstName, lastName, dob, address) VALUES (?, ?, ?, ?)",
                (row["First Name"], row["Last Name"], row["D.O.B (MM/DD/YYYY)"], row["Address"])
            )
        db.commit()
    return "CSV Data Imported Successfully!"

# Main Page
@app.route("/", methods=["GET", "POST"])
def index():
    return render_template("index.html")

# Add Patient Page
@app.route("/add", methods=["GET", "POST"])
def add():
    return render_template("add.html")

# Search Patients
@app.route("/search", methods=["GET"])
def search():
    db = get_db()
    query = request.args.get("query")
    patients = []

    if query:
        words = query.strip().split()
        if len(words) == 2:
            first, last = words
            patients = db.execute(
                "SELECT * FROM patients WHERE firstName LIKE ? AND lastName LIKE ?",
                (f"%{first}%", f"%{last}%")
            ).fetchall()
        else:
            patients = db.execute(
                "SELECT * FROM patients WHERE firstName LIKE ? OR lastName LIKE ?",
                (f"%{query}%", f"%{query}%")
            ).fetchall()

    return render_template("search.html", patients=patients, searched=bool(query))

# Register Patient
@app.route("/register", methods=["POST"])
def register():
    db = get_db()
    first = request.form.get("firstName")
    last = request.form.get("lastName")
    dob = request.form.get("dob")
    address = request.form.get("address")

    if not first or not last or not dob:
        return render_template("failure.html")

    # Find smallest missing ID
    missing_id_query = db.execute("""
        SELECT MIN(t1.id + 1) AS next_id
        FROM patients t1
        LEFT JOIN patients t2 ON t1.id + 1 = t2.id
        WHERE t2.id IS NULL
    """).fetchone()

    missing_id = missing_id_query["next_id"]

    if missing_id is None:
        max_id_query = db.execute("SELECT MAX(id) AS max_id FROM patients").fetchone()
        max_id = max_id_query["max_id"]
        next_id = max_id + 1 if max_id else 1
    else:
        next_id = missing_id

    db.execute(
        "INSERT INTO patients (id, firstName, lastName, dob, address) VALUES (?, ?, ?, ?, ?)",
        (next_id, first, last, dob, address)
    )
    db.commit()
    return render_template("success.html")

# View All Results
@app.route("/results")
def results():
    db = get_db()
    patients = db.execute("SELECT * FROM patients").fetchall()
    return render_template("find.html", patients=patients)

# Remove a Patient
@app.route("/remove/<int:id>", methods=["POST"])
def remove(id):
    db = get_db()
    db.execute("DELETE FROM patients WHERE id = ?", (id,))
    db.commit()
    return redirect("/search")

# View All Patients
@app.route("/view")
def view():
    db = get_db()
    patients = db.execute("SELECT * FROM patients").fetchall()
    return render_template("view.html", patients=patients)
