import csv
from cs50 import SQL
from flask import Flask, render_template, request, redirect

app = Flask(__name__)

db = SQL("sqlite:///patients.db")

# Route to import CSV data into the database
@app.route("/import_csv")
def import_csv():
    with open('patients.csv', 'r') as file:
        reader = csv.DictReader(file)  # Read CSV as dict
        for row in reader:
            db.execute(
                "INSERT INTO patients (firstName, lastName, dob, address) VALUES (?, ?, ?, ?)",
                row["First Name"], row["Last Name"], row["D.O.B (MM/DD/YYYY)"], row["Address"]
            )
    return "CSV Data Imported Successfully!"

# MAIN PAGE
@app.route("/", methods=["GET", "POST"])
def index():
    return render_template("index.html")

# GOTO add a patient
@app.route("/add", methods=["GET", "POST"])
def add():
    return render_template("add.html")

# Go to search
@app.route("/search", methods=["GET"])
def search():
    query = request.args.get("query")
    patients = []

    if query:
        words = query.strip().split()

        if len(words) == 2:
            first, last = words
            patients = db.execute(
                "SELECT * FROM patients WHERE firstName LIKE ? AND lastName LIKE ?",
                f"%{first}%", f"%{last}%"
            )
        else:
            patients = db.execute(
                "SELECT * FROM patients WHERE firstName LIKE ? OR lastName LIKE ?",
                f"%{query}%", f"%{query}%"
            )

    return render_template("search.html", patients=patients, searched=bool(query))

# Register a patient, insert with smallest missing ID or max+1
@app.route("/register", methods=["POST"])
def register():
    first = request.form.get("firstName")
    last = request.form.get("lastName")
    dob = request.form.get("dob")
    address = request.form.get("address")

    if not first or not last or not dob:
        return render_template("failure.html")

    # Find smallest missing ID (gap) or max + 1
    missing_id_query = db.execute("""
        SELECT MIN(t1.id + 1) AS next_id
        FROM patients t1
        LEFT JOIN patients t2 ON t1.id + 1 = t2.id
        WHERE t2.id IS NULL
    """)

    missing_id = missing_id_query[0]["next_id"]

    if missing_id is None:
        max_id_query = db.execute("SELECT MAX(id) AS max_id FROM patients")
        max_id = max_id_query[0]["max_id"]
        next_id = max_id + 1 if max_id else 1
    else:
        next_id = missing_id

    db.execute("INSERT INTO patients (id, firstName, lastName, dob, address) VALUES (?, ?, ?, ?, ?)",
               next_id, first, last, dob, address)

    return render_template("success.html")

@app.route("/results")
def results():
    patients = db.execute("SELECT * FROM patients")
    return render_template("find.html", patients=patients)

@app.route("/remove/<int:id>", methods=["POST"])
def remove(id):
    db.execute("DELETE FROM patients WHERE id = ?", id)
    return redirect("/search")

@app.route("/view")
def view():
    patients = db.execute("SELECT * FROM patients")
    return render_template("view.html", patients=patients)
