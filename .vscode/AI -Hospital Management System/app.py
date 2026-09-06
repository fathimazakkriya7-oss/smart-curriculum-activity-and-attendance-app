from flask import Flask, render_template, request, redirect
import sqlite3
import pickle

app = Flask(__name__)


# ---------------- DATABASE ----------------

def create_database():

    conn = sqlite3.connect("hospital.db")

    # Patients table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER,
            gender TEXT,
            phone TEXT,
            disease TEXT
        )
    """)

    # Doctors table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            specialization TEXT,
            phone TEXT
        )
    """)

    conn.commit()
    conn.close()


# ---------------- DASHBOARD ----------------

@app.route("/")
def home():
    return render_template("dashboard.html")


# ---------------- PATIENTS ----------------

@app.route("/patients", methods=["GET", "POST"])
def patients():

    conn = sqlite3.connect("hospital.db")

    if request.method == "POST":

        name = request.form["name"]
        age = request.form["age"]
        gender = request.form["gender"]
        phone = request.form["phone"]
        disease = request.form["disease"]

        conn.execute("""
            INSERT INTO patients
            (name, age, gender, phone, disease)
            VALUES (?, ?, ?, ?, ?)
        """, (name, age, gender, phone, disease))

        conn.commit()

    conn.row_factory = sqlite3.Row

    patient_list = conn.execute(
        "SELECT * FROM patients"
    ).fetchall()

    conn.close()

    return render_template(
        "patients.html",
        patients=patient_list
    )


# ---------------- DOCTORS ----------------

@app.route("/doctors", methods=["GET", "POST"])
def doctors():

    conn = sqlite3.connect("hospital.db")

    if request.method == "POST":

        name = request.form["name"]
        specialization = request.form["specialization"]
        phone = request.form["phone"]

        conn.execute("""
            INSERT INTO doctors
            (name, specialization, phone)
            VALUES (?, ?, ?)
        """, (name, specialization, phone))

        conn.commit()

    conn.row_factory = sqlite3.Row

    doctor_list = conn.execute(
        "SELECT * FROM doctors"
    ).fetchall()

    conn.close()

    return render_template(
        "doctors.html",
        doctors=doctor_list
    )
# ---------------- APPOINTMENTS ----------------

@app.route("/appointments", methods=["GET", "POST"])
def appointments():

    conn = sqlite3.connect("hospital.db")
    conn.row_factory = sqlite3.Row

    # Create appointments table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient TEXT NOT NULL,
            doctor TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL
        )
    """)

    if request.method == "POST":

        patient = request.form["patient"]
        doctor = request.form["doctor"]
        date = request.form["date"]
        time = request.form["time"]

        conn.execute("""
            INSERT INTO appointments
            (patient, doctor, date, time)
            VALUES (?, ?, ?, ?)
        """, (patient, doctor, date, time))

        conn.commit()

    # Get patients
    patient_list = conn.execute(
        "SELECT * FROM patients"
    ).fetchall()

    # Get doctors
    doctor_list = conn.execute(
        "SELECT * FROM doctors"
    ).fetchall()

    # Get appointments
    appointment_list = conn.execute(
        "SELECT * FROM appointments ORDER BY date, time"
    ).fetchall()

    conn.close()

    return render_template(
        "appointments.html",
        patients=patient_list,
        doctors=doctor_list,
        appointments=appointment_list
    )

# ---------------- AI PREDICTION ----------------

@app.route("/ai-prediction", methods=["GET", "POST"])
def ai_prediction():

    prediction = None

    if request.method == "POST":

        symptoms = request.form["symptoms"].lower()

        # Load trained AI model
        with open("model.pkl", "rb") as file:
            model = pickle.load(file)

        # Load vectorizer
        with open("vectorizer.pkl", "rb") as file:
            vectorizer = pickle.load(file)

        # Convert symptoms into numbers
        symptoms_vector = vectorizer.transform([symptoms])

        # AI prediction
        prediction = model.predict(symptoms_vector)[0]

    return render_template(
        "ai_prediction.html",
        prediction=prediction
    )


# ---------------- START ----------------

if __name__ == "__main__":

    create_database()

    app.run(debug=True)