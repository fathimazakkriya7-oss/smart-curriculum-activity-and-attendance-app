from flask import Flask, render_template, request, redirect
from datetime import date
import sqlite3

app = Flask(__name__)

# Create database
def create_database():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    register_no TEXT,
    student_name TEXT,
    date TEXT,
    status TEXT
)
""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        reg_no TEXT NOT NULL,
        student_class TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()

create_database()

@app.route("/")
def home():
    return redirect("/student")

@app.route("/student", methods=["GET", "POST"])
def student():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
   

    if request.method == "POST":
        name = request.form["name"]
        reg_no = request.form["reg_no"]
        student_class = request.form["student_class"]

        cursor.execute(
            "INSERT INTO students (name, reg_no, student_class) VALUES (?, ?, ?)",
            (name, reg_no, student_class)
        )

        conn.commit()

    cursor.execute("SELECT * FROM students")
    students = cursor.fetchall()

    conn.close()

    return render_template("student.html", students=students)

@app.route("/delete/<int:id>")
def delete_student(id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM students WHERE id = ?", (id,))

    conn.commit()
    conn.close()

    return redirect("/student")


@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_student(id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    if request.method == "POST":
        name = request.form["name"]
        reg_no = request.form["reg_no"]
        student_class = request.form["student_class"]

        cursor.execute("""
            UPDATE students
            SET name = ?, reg_no = ?, student_class = ?
            WHERE id = ?
        """, (name, reg_no, student_class, id))

        conn.commit()
        conn.close()

        return redirect("/student")

    cursor.execute("SELECT * FROM students WHERE id = ?", (id,))
    student = cursor.fetchone()

    conn.close()

    return render_template("edit.html", student=student)


@app.route("/dashboard")
def dashboard():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM attendance WHERE status='Present'")
    present = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM attendance WHERE status='Absent'")
    absent = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        total_students=total_students,
        present=present,
        absent=absent
    )
@app.route("/attendance")
def attendance():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM students")
    students = cursor.fetchall()

    conn.close()

    return render_template("attendance.html", students=students)
from datetime import date

@app.route("/save_attendance", methods=["POST"])
def save_attendance():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    today = date.today()

    # Get all students
    cursor.execute("SELECT reg_no, name FROM students")
    students = cursor.fetchall()

    # Save attendance
    for student in students:
        reg_no = student[0]
        name = student[1]
        status = request.form.get(reg_no)

        cursor.execute("""
            INSERT INTO attendance
            (register_no, student_name, date, status)
            VALUES (?, ?, ?, ?)
        """, (reg_no, name, str(today), status))

    conn.commit()
    conn.close()

    return redirect("/dashboard")
@app.route("/report")
def report():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT reg_no, name FROM students")
    students = cursor.fetchall()

    report_data = []

    for student in students:
        reg_no = student[0]
        name = student[1]

        cursor.execute("""
            SELECT COUNT(*) FROM attendance
            WHERE register_no = ? AND status = 'Present'
        """, (reg_no,))
        present = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM attendance
            WHERE register_no = ?
        """, (reg_no,))
        total = cursor.fetchone()[0]

        percentage = 0
        if total > 0:
            percentage = (present / total) * 100

        report_data.append((name, reg_no, present, total, round(percentage, 2)))

    conn.close()

    return render_template("report.html", records=report_data)
@app.route("/delete_attendance/<int:id>")
def delete_attendance(id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM attendance WHERE id = ?", (id,))

    conn.commit()
    conn.close()

    return redirect("/report")
if __name__ == "__main__":
    app.run(debug=True)