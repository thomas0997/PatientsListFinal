import csv
import sqlite3
import os
import io
from flask import Flask, render_template, request, redirect, flash, url_for, send_file, jsonify
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
basedir = os.path.abspath(os.path.dirname(__file__))

# ---------- DATABASE CONNECTIONS ----------
def get_patient_db():
    conn = sqlite3.connect(os.path.join(basedir, "patients.db"))
    conn.row_factory = sqlite3.Row
    return conn

def get_inventory_db():
    conn = sqlite3.connect(os.path.join(basedir, "inventory.db"))
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/favicon.ico')
def favicon():
    return redirect(url_for('static', filename='favicon.ico'))

# CSV Upload Route - GET shows form, POST uploads CSV and imports data
@app.route("/upload", methods=["GET", "POST"])
def upload_csv():
    if request.method == "POST":
        action = request.form.get("action")

        if action == "upload_patients":
            file = request.files.get("file")
            if not file or file.filename == "":
                flash("No file selected")
                return redirect(request.url)

            if not file.filename.endswith(".csv"):
                flash("Please upload a CSV file")
                return redirect(request.url)

            try:
                stream = io.StringIO(file.stream.read().decode("UTF8"))
                reader = csv.DictReader(stream)

                db = get_patient_db()
                db.execute("DELETE FROM patients")
                db.execute("DELETE FROM sqlite_sequence WHERE name='patients'")
                db.commit()

                for row in reader:
                    db.execute(
                        "INSERT INTO patients (firstName, lastName, dob, address) VALUES (?, ?, ?, ?)",
                        (row["First Name"], row["Last Name"], row["D.O.B (MM/DD/YYYY)"], row["Address"])
                    )
                db.commit()
                flash("CSV Imported and Database Reset!")
            except Exception as e:
                flash(f"Error: {e}")
            return redirect(request.url)

        elif action == "export_inventory":
            db = get_inventory_db()
            meds = db.execute("SELECT * FROM medicines").fetchall()

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["Name", "Type", "Quantity"])
            for med in meds:
                writer.writerow([med["name"], med["type"], med["quantity"]])
            output.seek(0)

            return send_file(
                io.BytesIO(output.getvalue().encode()),
                mimetype="text/csv",
                as_attachment=True,
                download_name="inventory_export.csv"
            )

    return render_template("upload.html")


# Main Page
@app.route("/", methods=["GET", "POST"])
def index():
    return render_template("index.html")

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
    missing_id = db.execute("""SELECT MIN(t1.id + 1) AS next_id FROM patients t1 LEFT JOIN patients t2 ON t1.id + 1 = t2.id WHERE t2.id IS NULL""").fetchone()["next_id"]
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

# ---------- INVENTORY SECTION ----------
@app.route("/inventory")
def inventory_menu():
    return render_template("inventory/index.html")

@app.route("/inventory/view")
def inventory_view():
    db = get_inventory_db()
    meds = db.execute("SELECT * FROM medicines").fetchall()
    return render_template("inventory/view.html", meds=meds)

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

        if not name or quantity < 0:
            flash("Invalid input.")
            return redirect(request.url)

        db = get_inventory_db()
        db.execute("INSERT OR REPLACE INTO medicines (name, quantity) VALUES (?, ?)", (name, quantity))
        db.commit()
        return render_template("inventory/success.html")

    return render_template("inventory/add.html")

@app.route("/inventory/find", methods=["GET", "POST"])
def inventory_find():
    med = None
    searched = False
    if request.method == "POST":
        name = request.form.get("query")
        db = get_inventory_db()
        med = db.execute("SELECT * FROM medicines WHERE name LIKE ?", (f"%{name}%",)).fetchone()
        searched = True
    return render_template("inventory/find.html", med=med, searched=searched)

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

    # Update quantity in medicines table
    db.execute("UPDATE medicines SET quantity = ? WHERE name = ?", (new_qty, name))

    # Get today's date (not full timestamp)
    today = datetime.now().date().isoformat()

    # Try to find existing log entry for today and medicine
    existing_log = db.execute("""
        SELECT id, change FROM logs
        WHERE medicine_name = ? AND date(timestamp) = ?
        ORDER BY id DESC LIMIT 1
    """, (name, today)).fetchone()

    if existing_log:
        new_change = existing_log["change"] + change
        db.execute("UPDATE logs SET change = ?, timestamp = ? WHERE id = ?", (new_change, datetime.now().isoformat(), existing_log["id"]))
    else:
        db.execute("INSERT INTO logs (medicine_name, change, timestamp) VALUES (?, ?, ?)", (name, change, datetime.now().isoformat()))

    db.commit()

    return jsonify({"quantity": new_qty})