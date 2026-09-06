from flask import Flask, render_template, request, redirect, session, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date
import io
import os
import sqlite3

from openpyxl import Workbook

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph
)
from reportlab.lib.styles import getSampleStyleSheet

from functools import wraps


# =========================================================
# FLASK APPLICATION
# =========================================================

app = Flask(__name__)

# Secret key
app.secret_key = os.environ.get(
    "SMART_CAMPUS_SECRET_KEY",
    "smart-campus-secret-key"
)

# Session security
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

DATABASE = "database.db"


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db():

    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA foreign_keys = ON")

    return conn


# =========================================================
# CREATE DATABASE
# =========================================================

def create_database():

    conn = get_db()
    cursor = conn.cursor()

    # -----------------------------------------------------
    # STUDENTS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            reg_no TEXT UNIQUE NOT NULL,
            student_class TEXT NOT NULL,
            department TEXT DEFAULT 'CSE',
            year INTEGER DEFAULT 1
        )
    """)

    # -----------------------------------------------------
    # SUBJECTS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_name TEXT NOT NULL,
            subject_code TEXT UNIQUE NOT NULL
        )
    """)

    # -----------------------------------------------------
    # ATTENDANCE
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            register_no TEXT NOT NULL,
            student_name TEXT NOT NULL,
            subject_id INTEGER,
            date TEXT NOT NULL,
            status TEXT NOT NULL,

            UNIQUE(register_no, subject_id, date),

            FOREIGN KEY(subject_id)
            REFERENCES subjects(id)
        )
    """)

    # -----------------------------------------------------
    # CURRICULUM
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS curriculum (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            unit_name TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',

            FOREIGN KEY(subject_id)
            REFERENCES subjects(id)
        )
    """)

    # -----------------------------------------------------
    # ACTIVITIES
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            activity_name TEXT NOT NULL,
            score REAL DEFAULT 0,
            date TEXT NOT NULL,

            FOREIGN KEY(student_id)
            REFERENCES students(id)
        )
    """)

    # -----------------------------------------------------
    # MARKS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS marks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            internal_mark REAL DEFAULT 0,
            assignment_mark REAL DEFAULT 0,
            quiz_mark REAL DEFAULT 0,

            FOREIGN KEY(student_id)
            REFERENCES students(id),

            FOREIGN KEY(subject_id)
            REFERENCES subjects(id)
        )
    """)

    # -----------------------------------------------------
    # USERS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            student_id INTEGER
        )
    """)

    # -----------------------------------------------------
    # CHECK OLD USERS TABLE
    # -----------------------------------------------------

    user_columns = [
        row["name"]
        for row in cursor.execute(
            "PRAGMA table_info(users)"
        ).fetchall()
    ]

    if "student_id" not in user_columns:

        cursor.execute("""
            ALTER TABLE users
            ADD COLUMN student_id INTEGER
        """)

    # -----------------------------------------------------
    # CHECK OLD ATTENDANCE TABLE
    # -----------------------------------------------------

    attendance_columns = [
        row["name"]
        for row in cursor.execute(
            "PRAGMA table_info(attendance)"
        ).fetchall()
    ]

    if "subject_id" not in attendance_columns:

        cursor.execute("""
            ALTER TABLE attendance
            ADD COLUMN subject_id INTEGER
        """)

    # =====================================================
    # DEFAULT USERS
    # IMPORTANT:
    # Passwords are HASHED
    # =====================================================

    # ADMIN
    cursor.execute("""
        INSERT OR IGNORE INTO users
        (username, password, role)
        VALUES (?, ?, ?)
    """, (
        "admin",
        generate_password_hash("admin123"),
        "admin"
    ))

    # FACULTY
    cursor.execute("""
        INSERT OR IGNORE INTO users
        (username, password, role)
        VALUES (?, ?, ?)
    """, (
        "faculty",
        generate_password_hash("faculty123"),
        "faculty"
    ))

    # STUDENT
    cursor.execute("""
        INSERT OR IGNORE INTO users
        (username, password, role)
        VALUES (?, ?, ?)
    """, (
        "student",
        generate_password_hash("student123"),
        "student"
    ))

    # -----------------------------------------------------
    # CONNECT DEMO STUDENT ACCOUNT
    # -----------------------------------------------------

    student_record = cursor.execute("""
        SELECT id
        FROM students
        ORDER BY id
        LIMIT 1
    """).fetchone()

    if student_record:

        cursor.execute("""
            UPDATE users

            SET student_id = ?

            WHERE username = 'student'

            AND role = 'student'
        """, (
            student_record["id"],
        ))

    conn.commit()
    conn.close()


create_database()


# =========================================================
# ROLE PROTECTION
# =========================================================

def role_required(*allowed_roles):

    def decorator(function):

        @wraps(function)
        def wrapper(*args, **kwargs):

            # Not logged in
            if not session.get("logged_in"):

                return redirect("/login")

            # Wrong role
            if session.get("role") not in allowed_roles:

                if session.get("role") == "student":

                    dashboard_url = "/my_dashboard"

                elif session.get("role") == "faculty":

                    dashboard_url = "/faculty_dashboard"

                else:

                    dashboard_url = "/dashboard"

                return f"""
                <!DOCTYPE html>

                <html>

                <head>

                    <title>Access Denied</title>

                    <style>

                        body {{
                            font-family: Arial;
                            background: #f4f6f9;
                            text-align: center;
                            padding-top: 100px;
                        }}

                        .box {{
                            background: white;
                            width: 400px;
                            margin: auto;
                            padding: 40px;
                            border-radius: 15px;

                            box-shadow:
                                0 5px 20px
                                rgba(0,0,0,0.1);
                        }}

                        a {{
                            display: inline-block;
                            margin-top: 20px;
                            padding: 10px 20px;
                            background: #222;
                            color: white;
                            text-decoration: none;
                            border-radius: 7px;
                        }}

                    </style>

                </head>

                <body>

                    <div class="box">

                        <h1>🚫 Access Denied</h1>

                        <p>
                            You do not have permission
                            to access this page.
                        </p>

                        <a href="{dashboard_url}">
                            Return to Dashboard
                        </a>

                    </div>

                </body>

                </html>
                """

            return function(*args, **kwargs)

        return wrapper

    return decorator


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    if session.get("logged_in"):

        if session.get("role") == "student":

            return redirect("/my_dashboard")

        elif session.get("role") == "faculty":

            return redirect("/faculty_dashboard")

        elif session.get("role") == "admin":

            return redirect("/dashboard")

    return redirect("/login")


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    # Already logged in
    if session.get("logged_in"):

        if session.get("role") == "student":

            return redirect("/my_dashboard")

        elif session.get("role") == "faculty":

            return redirect("/faculty_dashboard")

        elif session.get("role") == "admin":

            return redirect("/dashboard")

        else:

            session.clear()

    # POST
    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        # Empty fields
        if not username or not password:

            flash(
                "Please enter username and password!"
            )

            return render_template(
                "login.html"
            )

        conn = get_db()

        user = conn.execute("""
            SELECT *
            FROM users
            WHERE username = ?
        """, (
            username,
        )).fetchone()

        conn.close()

        # User found
        if user:

            try:

                password_correct = check_password_hash(
                    user["password"],
                    password
                )

            except (ValueError, TypeError):

                password_correct = False

            if password_correct:

                # Clear old session
                session.clear()

                # Store session
                session["logged_in"] = True
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session["role"] = user["role"]

                flash(
                    "Login successful!"
                )

                # STUDENT
                if user["role"] == "student":

                    return redirect(
                        "/my_dashboard"
                    )

                # FACULTY
                elif user["role"] == "faculty":

                    return redirect(
                        "/faculty_dashboard"
                    )

                # ADMIN
                elif user["role"] == "admin":

                    return redirect(
                        "/dashboard"
                    )

        flash(
            "Invalid username or password!"
        )

    return render_template(
        "login.html"
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out."
    )

    return redirect("/login")


# =========================================================
# ADMIN / FACULTY DASHBOARD
# =========================================================

@app.route("/dashboard")
@role_required("admin", "faculty")
def dashboard():

    conn = get_db()

    # -----------------------------------------------------
    # TOTAL STUDENTS
    # -----------------------------------------------------

    total_students = conn.execute("""
        SELECT COUNT(*) AS count
        FROM students
    """).fetchone()["count"]

    # -----------------------------------------------------
    # ATTENDANCE STATS
    # -----------------------------------------------------

    attendance_stats = conn.execute("""
        SELECT

            COUNT(*) AS total,

            SUM(
                CASE
                    WHEN status = 'Present'
                    THEN 1
                    ELSE 0
                END
            ) AS present,

            SUM(
                CASE
                    WHEN status = 'Absent'
                    THEN 1
                    ELSE 0
                END
            ) AS absent

        FROM attendance
    """).fetchone()

    total_attendance = (
        attendance_stats["total"] or 0
    )

    present_count = (
        attendance_stats["present"] or 0
    )

    absent_count = (
        attendance_stats["absent"] or 0
    )

    if total_attendance > 0:

        overall_attendance = round(
            (
                present_count /
                total_attendance
            ) * 100,
            2
        )

    else:

        overall_attendance = 0

    # -----------------------------------------------------
    # STUDENT DATA
    # -----------------------------------------------------

    students = conn.execute("""
        SELECT

            students.id,
            students.name,
            students.reg_no,

            COUNT(attendance.id) AS total,

            SUM(
                CASE
                    WHEN attendance.status = 'Present'
                    THEN 1
                    ELSE 0
                END
            ) AS present

        FROM students

        LEFT JOIN attendance

            ON students.reg_no =
               attendance.register_no

        GROUP BY students.id

        ORDER BY students.name
    """).fetchall()

    student_data = []

    at_risk_count = 0

    for student in students:

        total = student["total"] or 0

        present = student["present"] or 0

        if total > 0:

            percentage = round(
                (present / total) * 100,
                2
            )

        else:

            percentage = 0

        if percentage < 75:

            risk = "At Risk"

            at_risk_count += 1

        else:

            risk = "Good"

        student_data.append({

            "id": student["id"],
            "name": student["name"],
            "reg_no": student["reg_no"],
            "present": present,
            "total": total,
            "percentage": percentage,
            "risk": risk

        })

    # -----------------------------------------------------
    # SUBJECT DATA
    # -----------------------------------------------------

    subjects = conn.execute("""
        SELECT

            subjects.subject_name,

            COUNT(attendance.id) AS total,

            SUM(
                CASE
                    WHEN attendance.status = 'Present'
                    THEN 1
                    ELSE 0
                END
            ) AS present

        FROM subjects

        LEFT JOIN attendance

            ON subjects.id =
               attendance.subject_id

        GROUP BY subjects.id

        ORDER BY subjects.subject_name
    """).fetchall()

    subject_data = []

    for subject in subjects:

        total = subject["total"] or 0

        present = subject["present"] or 0

        if total > 0:

            percentage = round(
                (present / total) * 100,
                2
            )

        else:

            percentage = 0

        subject_data.append({

            "name":
                subject["subject_name"],

            "percentage":
                percentage

        })

    # -----------------------------------------------------
    # TOP STUDENTS
    # -----------------------------------------------------

    top_students = sorted(
        student_data,
        key=lambda x: x["percentage"],
        reverse=True
    )[:5]

    # -----------------------------------------------------
    # RISK STUDENTS
    # -----------------------------------------------------

    risk_students = [
        student
        for student in student_data
        if student["percentage"] < 75
    ][:5]

    conn.close()

    return render_template(
        "dashboard.html",
        total_students=total_students,
        total_attendance=total_attendance,
        present_count=present_count,
        absent_count=absent_count,
        overall_attendance=overall_attendance,
        at_risk_count=at_risk_count,
        student_data=student_data,
        subject_data=subject_data,
        top_students=top_students,
        risk_students=risk_students
    )


# =========================================================
# FACULTY DASHBOARD
# =========================================================

@app.route("/faculty_dashboard")
@role_required("faculty")
def faculty_dashboard():

    conn = get_db()
    cursor = conn.cursor()

    # TOTAL STUDENTS
    total_students = cursor.execute("""
        SELECT COUNT(*) AS count
        FROM students
    """).fetchone()["count"]

    # TOTAL SUBJECTS
    total_subjects = cursor.execute("""
        SELECT COUNT(*) AS count
        FROM subjects
    """).fetchone()["count"]

    # TODAY
    today = date.today().isoformat()

    # TODAY PRESENT
    today_present = cursor.execute("""
        SELECT COUNT(*) AS count
        FROM attendance

        WHERE date = ?

        AND status = 'Present'
    """, (
        today,
    )).fetchone()["count"]

    # TODAY ABSENT
    today_absent = cursor.execute("""
        SELECT COUNT(*) AS count
        FROM attendance

        WHERE date = ?

        AND status = 'Absent'
    """, (
        today,
    )).fetchone()["count"]

    # OVERALL ATTENDANCE
    attendance_stats = cursor.execute("""
        SELECT

            COUNT(*) AS total,

            SUM(
                CASE
                    WHEN status = 'Present'
                    THEN 1
                    ELSE 0
                END
            ) AS present

        FROM attendance
    """).fetchone()

    total_attendance = (
        attendance_stats["total"] or 0
    )

    total_present = (
        attendance_stats["present"] or 0
    )

    if total_attendance > 0:

        attendance_percentage = round(
            (
                total_present /
                total_attendance
            ) * 100,
            2
        )

    else:

        attendance_percentage = 0

    # LOW ATTENDANCE
    low_attendance = cursor.execute("""
        SELECT

            s.id,
            s.name,
            s.reg_no,

            COUNT(a.id) AS total_classes,

            SUM(
                CASE
                    WHEN a.status = 'Present'
                    THEN 1
                    ELSE 0
                END
            ) AS present_classes

        FROM students s

        LEFT JOIN attendance a

            ON s.reg_no =
               a.register_no

        GROUP BY s.id

        HAVING
            total_classes > 0

            AND

            (
                present_classes * 100.0
                / total_classes
            ) < 75

        ORDER BY
            (
                present_classes * 100.0
                / total_classes
            ) ASC
    """).fetchall()

    # SUBJECT ATTENDANCE
    subject_attendance = cursor.execute("""
        SELECT

            sub.subject_name,

            COUNT(a.id) AS total_classes,

            SUM(
                CASE
                    WHEN a.status = 'Present'
                    THEN 1
                    ELSE 0
                END
            ) AS present_classes

        FROM subjects sub

        LEFT JOIN attendance a

            ON sub.id =
               a.subject_id

        GROUP BY sub.id

        ORDER BY sub.subject_name
    """).fetchall()

    # TOP STUDENTS
    # Correct average:
    # (Internal + Assignment + Quiz) / 3

    top_students = cursor.execute("""
        SELECT

            s.name,
            s.reg_no,

            AVG(
                (
                    COALESCE(m.internal_mark, 0)
                    +
                    COALESCE(m.assignment_mark, 0)
                    +
                    COALESCE(m.quiz_mark, 0)
                ) / 3.0
            ) AS average_mark

        FROM students s

        JOIN marks m

            ON s.id = m.student_id

        GROUP BY s.id

        ORDER BY average_mark DESC

        LIMIT 5
    """).fetchall()

    conn.close()

    return render_template(
        "faculty_dashboard.html",

        total_students=total_students,

        total_subjects=total_subjects,

        today_present=today_present,

        today_absent=today_absent,

        attendance_percentage=
            attendance_percentage,

        total_present=total_present,

        total_attendance=
            total_attendance,

        low_attendance=
            low_attendance,

        subject_attendance=
            subject_attendance,

        top_students=
            top_students
    )


# =========================================================
# STUDENT MANAGEMENT
# =========================================================

@app.route("/student", methods=["GET", "POST"])
@role_required("admin", "faculty")
def student():

    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        reg_no = request.form.get(
            "reg_no",
            ""
        ).strip()

        student_class = request.form.get(
            "student_class",
            ""
        ).strip()

        department = request.form.get(
            "department",
            "CSE"
        ).strip()

        year = request.form.get(
            "year",
            1
        )

        if not name or not reg_no or not student_class:

            flash(
                "Please fill all required fields!"
            )

            conn.close()

            return redirect("/student")

        try:

            cursor.execute("""
                INSERT INTO students
                (
                    name,
                    reg_no,
                    student_class,
                    department,
                    year
                )

                VALUES (?, ?, ?, ?, ?)
            """, (
                name,
                reg_no,
                student_class,
                department,
                year
            ))

            conn.commit()

            flash(
                "Student added successfully!"
            )

        except sqlite3.IntegrityError:

            flash(
                "Register number already exists!"
            )

        conn.close()

        return redirect("/student")

    students = cursor.execute("""
        SELECT *
        FROM students
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "student.html",
        students=students
    )


# =========================================================
# DELETE STUDENT
# =========================================================

@app.route("/delete/<int:id>")
@role_required("admin")
def delete_student(id):

    conn = get_db()

    try:

        conn.execute(
            "DELETE FROM students WHERE id = ?",
            (id,)
        )

        conn.commit()

        flash(
            "Student deleted successfully!"
        )

    except sqlite3.IntegrityError:

        flash(
            "Cannot delete this student because "
            "attendance, marks or activities are linked."
        )

    finally:

        conn.close()

    return redirect("/student")


# =========================================================
# EDIT STUDENT
# =========================================================

@app.route("/edit/<int:id>", methods=["GET", "POST"])
@role_required("admin", "faculty")
def edit_student(id):

    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        reg_no = request.form.get(
            "reg_no",
            ""
        ).strip()

        student_class = request.form.get(
            "student_class",
            ""
        ).strip()

        department = request.form.get(
            "department",
            "CSE"
        ).strip()

        year = request.form.get(
            "year",
            1
        )

        try:

            cursor.execute("""
                UPDATE students

                SET

                    name = ?,
                    reg_no = ?,
                    student_class = ?,
                    department = ?,
                    year = ?

                WHERE id = ?
            """, (
                name,
                reg_no,
                student_class,
                department,
                year,
                id
            ))

            conn.commit()

            flash(
                "Student updated successfully!"
            )

        except sqlite3.IntegrityError:

            flash(
                "Register number already exists!"
            )

        conn.close()

        return redirect("/student")

    student_data = cursor.execute("""
        SELECT *
        FROM students
        WHERE id = ?
    """, (
        id,
    )).fetchone()

    conn.close()

    if not student_data:

        return "Student not found", 404

    return render_template(
        "edit.html",
        student=student_data
    )


# =========================================================
# ATTENDANCE PAGE
# =========================================================

@app.route("/attendance")
@role_required("admin", "faculty")
def attendance():

    conn = get_db()

    students = conn.execute("""
        SELECT *
        FROM students
        ORDER BY name
    """).fetchall()

    subjects = conn.execute("""
        SELECT *
        FROM subjects
        ORDER BY subject_name
    """).fetchall()

    conn.close()

    return render_template(
        "attendance.html",
        students=students,
        subjects=subjects,
        current_date=str(date.today())
    )


# =========================================================
# SAVE ATTENDANCE
# =========================================================

@app.route("/save_attendance", methods=["POST"])
@role_required("admin", "faculty")
def save_attendance():

    conn = get_db()
    cursor = conn.cursor()

    attendance_date = request.form.get(
        "attendance_date"
    )

    subject_id = request.form.get(
        "subject_id"
    )

    if not attendance_date or not subject_id:

        conn.close()

        flash(
            "Please select date and subject!"
        )

        return redirect("/attendance")

    students = cursor.execute("""
        SELECT reg_no, name
        FROM students
    """).fetchall()

    saved = 0
    duplicate = 0

    for student in students:

        reg_no = student["reg_no"]
        name = student["name"]

        status = request.form.get(
            reg_no
        )

        if not status:

            continue

        if status not in ["Present", "Absent"]:

            continue

        try:

            cursor.execute("""
                INSERT INTO attendance
                (
                    register_no,
                    student_name,
                    subject_id,
                    date,
                    status
                )

                VALUES (?, ?, ?, ?, ?)
            """, (
                reg_no,
                name,
                subject_id,
                attendance_date,
                status
            ))

            saved += 1

        except sqlite3.IntegrityError:

            duplicate += 1

    conn.commit()
    conn.close()

    if duplicate > 0:

        flash(
            f"{saved} attendance records saved. "
            f"{duplicate} duplicate records skipped."
        )

    else:

        flash(
            f"{saved} attendance records "
            f"saved successfully!"
        )

    return redirect("/attendance")


# =========================================================
# ATTENDANCE REPORT
# =========================================================

@app.route("/report")
@role_required("admin", "faculty")
def report():

    conn = get_db()
    cursor = conn.cursor()

    students = cursor.execute("""
        SELECT
            reg_no,
            name,
            id
        FROM students
        ORDER BY name
    """).fetchall()

    report_data = []

    for student in students:

        reg_no = student["reg_no"]

        name = student["name"]

        present = cursor.execute("""
            SELECT COUNT(*)
            FROM attendance

            WHERE register_no = ?

            AND status = 'Present'
        """, (
            reg_no,
        )).fetchone()[0]

        total = cursor.execute("""
            SELECT COUNT(*)
            FROM attendance

            WHERE register_no = ?
        """, (
            reg_no,
        )).fetchone()[0]

        if total > 0:

            percentage = round(
                (present / total) * 100,
                2
            )

        else:

            percentage = 0

        if percentage >= 75:

            risk = "Low"

        elif percentage >= 65:

            risk = "Medium"

        else:

            risk = "High"

        report_data.append({

            "name": name,

            "reg_no": reg_no,

            "present": present,

            "total": total,

            "percentage": percentage,

            "risk": risk

        })

    conn.close()

    return render_template(
        "report.html",
        records=report_data
    )


# =========================================================
# SUBJECT-WISE ATTENDANCE
# =========================================================

@app.route("/subject_report")
@role_required("admin", "faculty")
def subject_report():

    conn = get_db()

    subjects = conn.execute("""
        SELECT *
        FROM subjects
        ORDER BY subject_name
    """).fetchall()

    students = conn.execute("""
        SELECT *
        FROM students
        ORDER BY name
    """).fetchall()

    report_data = []

    for student in students:

        student_data = {

            "name":
                student["name"],

            "reg_no":
                student["reg_no"],

            "subjects": []

        }

        for subject in subjects:

            result = conn.execute("""
                SELECT

                    COUNT(*) AS total,

                    SUM(
                        CASE
                            WHEN status = 'Present'
                            THEN 1
                            ELSE 0
                        END
                    ) AS present

                FROM attendance

                WHERE register_no = ?

                AND subject_id = ?

            """, (
                student["reg_no"],
                subject["id"]
            )).fetchone()

            total = result["total"] or 0

            present = result["present"] or 0

            if total > 0:

                percentage = round(
                    (present / total) * 100,
                    2
                )

            else:

                percentage = 0

            student_data["subjects"].append({

                "name":
                    subject["subject_name"],

                "present":
                    present,

                "total":
                    total,

                "percentage":
                    percentage

            })

        report_data.append(
            student_data
        )

    conn.close()

    return render_template(
        "subject_report.html",

        report=report_data,

        subjects=subjects
    )


# =========================================================
# DELETE ATTENDANCE
# =========================================================

@app.route("/delete_attendance/<int:id>")
@role_required("admin")
def delete_attendance(id):

    conn = get_db()

    conn.execute(
        "DELETE FROM attendance WHERE id = ?",
        (id,)
    )

    conn.commit()
    conn.close()

    flash(
        "Attendance record deleted!"
    )

    return redirect("/report")


# =========================================================
# SUBJECTS
# =========================================================

@app.route("/subjects", methods=["GET", "POST"])
@role_required("admin", "faculty")
def subjects():

    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":

        subject_name = request.form.get(
            "subject_name",
            ""
        ).strip()

        subject_code = request.form.get(
            "subject_code",
            ""
        ).strip()

        if not subject_name or not subject_code:

            flash(
                "Please enter subject name and code!"
            )

            conn.close()

            return redirect("/subjects")

        try:

            cursor.execute("""
                INSERT INTO subjects
                (
                    subject_name,
                    subject_code
                )

                VALUES (?, ?)
            """, (
                subject_name,
                subject_code
            ))

            conn.commit()

            flash(
                "Subject added successfully!"
            )

        except sqlite3.IntegrityError:

            flash(
                "Subject code already exists!"
            )

    subjects_data = cursor.execute("""
        SELECT *
        FROM subjects
        ORDER BY subject_name
    """).fetchall()

    conn.close()

    return render_template(
        "subjects.html",
        subjects=subjects_data
    )


# =========================================================
# CURRICULUM
# =========================================================

@app.route("/curriculum", methods=["GET", "POST"])
@role_required("admin", "faculty")
def curriculum():

    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":

        subject_id = request.form.get(
            "subject_id"
        )

        unit_name = request.form.get(
            "unit_name",
            ""
        ).strip()

        if not subject_id or not unit_name:

            flash(
                "Please select subject and enter unit name!"
            )

            conn.close()

            return redirect("/curriculum")

        cursor.execute("""
            INSERT INTO curriculum
            (
                subject_id,
                unit_name
            )

            VALUES (?, ?)
        """, (
            subject_id,
            unit_name
        ))

        conn.commit()

        flash(
            "Curriculum unit added!"
        )

    curriculum_data = cursor.execute("""
        SELECT

            curriculum.id,

            subjects.subject_name,

            curriculum.unit_name,

            curriculum.status

        FROM curriculum

        JOIN subjects

            ON curriculum.subject_id =
               subjects.id

        ORDER BY subjects.subject_name
    """).fetchall()

    subjects_data = cursor.execute("""
        SELECT *
        FROM subjects
        ORDER BY subject_name
    """).fetchall()

    conn.close()

    return render_template(
        "curriculum.html",

        curriculum=curriculum_data,

        subjects=subjects_data
    )


# =========================================================
# UPDATE CURRICULUM
# =========================================================

@app.route("/curriculum/update/<int:id>")
@role_required("admin", "faculty")
def update_curriculum(id):

    conn = get_db()

    conn.execute("""
        UPDATE curriculum

        SET status =
            CASE

                WHEN status = 'Pending'
                THEN 'Completed'

                ELSE 'Pending'

            END

        WHERE id = ?
    """, (
        id,
    ))

    conn.commit()
    conn.close()

    return redirect("/curriculum")


# =========================================================
# CURRICULUM PROGRESS
# =========================================================

@app.route("/curriculum_progress")
@role_required("admin", "faculty")
def curriculum_progress():

    conn = get_db()
    cursor = conn.cursor()

    subjects = cursor.execute("""
        SELECT

            subjects.id,

            subjects.subject_name,

            subjects.subject_code,

            COUNT(curriculum.id) AS total_units,

            SUM(
                CASE
                    WHEN curriculum.status = 'Completed'
                    THEN 1
                    ELSE 0
                END
            ) AS completed_units

        FROM subjects

        LEFT JOIN curriculum

            ON subjects.id =
               curriculum.subject_id

        GROUP BY subjects.id

        ORDER BY subjects.subject_name
    """).fetchall()

    progress_data = []

    for subject in subjects:

        total_units = (
            subject["total_units"] or 0
        )

        completed_units = (
            subject["completed_units"] or 0
        )

        if total_units > 0:

            percentage = round(
                (
                    completed_units /
                    total_units
                ) * 100,
                2
            )

        else:

            percentage = 0

        progress_data.append({

            "id":
                subject["id"],

            "subject_name":
                subject["subject_name"],

            "subject_code":
                subject["subject_code"],

            "total_units":
                total_units,

            "completed_units":
                completed_units,

            "pending_units":
                total_units -
                completed_units,

            "percentage":
                percentage

        })

    total_units = sum(
        item["total_units"]
        for item in progress_data
    )

    completed_units = sum(
        item["completed_units"]
        for item in progress_data
    )

    pending_units = (
        total_units -
        completed_units
    )

    if total_units > 0:

        overall_percentage = round(
            (
                completed_units /
                total_units
            ) * 100,
            2
        )

    else:

        overall_percentage = 0

    conn.close()

    return render_template(
        "curriculum_progress.html",

        progress_data=
            progress_data,

        total_units=
            total_units,

        completed_units=
            completed_units,

        pending_units=
            pending_units,

        overall_percentage=
            overall_percentage
    )


# =========================================================
# ACTIVITIES
# =========================================================

@app.route("/activities", methods=["GET", "POST"])
@role_required("admin", "faculty")
def activities():

    conn = get_db()

    if request.method == "POST":

        student_id = request.form.get(
            "student_id"
        )

        activity_name = request.form.get(
            "activity_name",
            ""
        ).strip()

        score = request.form.get(
            "score",
            0
        )

        activity_date = request.form.get(
            "date"
        )

        if (
            not student_id
            or not activity_name
            or not activity_date
        ):

            flash(
                "Please fill all activity fields!"
            )

            conn.close()

            return redirect("/activities")

        try:

            score_value = float(score)

        except (ValueError, TypeError):

            score_value = 0

        conn.execute("""
            INSERT INTO activities
            (
                student_id,
                activity_name,
                score,
                date
            )

            VALUES (?, ?, ?, ?)
        """, (
            student_id,
            activity_name,
            score_value,
            activity_date
        ))

        conn.commit()
        conn.close()

        flash(
            "Activity added successfully!"
        )

        return redirect("/activities")

    students = conn.execute("""
        SELECT *
        FROM students
        ORDER BY name
    """).fetchall()

    activities_list = conn.execute("""
        SELECT

            activities.id,

            students.name,

            students.reg_no,

            activities.activity_name,

            activities.score,

            activities.date

        FROM activities

        JOIN students

            ON activities.student_id =
               students.id

        ORDER BY activities.date DESC
    """).fetchall()

    conn.close()

    return render_template(
        "activities.html",

        students=students,

        activities=activities_list
    )


# =========================================================
# MARKS
# =========================================================

@app.route("/marks", methods=["GET", "POST"])
@role_required("admin", "faculty")
def marks():

    conn = get_db()

    if request.method == "POST":

        student_id = request.form.get(
            "student_id"
        )

        subject_id = request.form.get(
            "subject_id"
        )

        internal_mark = request.form.get(
            "internal_mark",
            0
        )

        assignment_mark = request.form.get(
            "assignment_mark",
            0
        )

        quiz_mark = request.form.get(
            "quiz_mark",
            0
        )

        try:

            internal_mark = float(
                internal_mark
            )

            assignment_mark = float(
                assignment_mark
            )

            quiz_mark = float(
                quiz_mark
            )

        except (ValueError, TypeError):

            flash(
                "Please enter valid marks!"
            )

            conn.close()

            return redirect("/marks")

        conn.execute("""
            INSERT INTO marks
            (
                student_id,
                subject_id,
                internal_mark,
                assignment_mark,
                quiz_mark
            )

            VALUES (?, ?, ?, ?, ?)
        """, (
            student_id,
            subject_id,
            internal_mark,
            assignment_mark,
            quiz_mark
        ))

        conn.commit()
        conn.close()

        flash(
            "Marks added successfully!"
        )

        return redirect("/marks")

    students = conn.execute("""
        SELECT *
        FROM students
        ORDER BY name
    """).fetchall()

    subjects = conn.execute("""
        SELECT *
        FROM subjects
        ORDER BY subject_name
    """).fetchall()

    marks_list = conn.execute("""
        SELECT

            marks.id,

            students.name,

            students.reg_no,

            subjects.subject_name,

            marks.internal_mark,

            marks.assignment_mark,

            marks.quiz_mark

        FROM marks

        JOIN students

            ON marks.student_id =
               students.id

        JOIN subjects

            ON marks.subject_id =
               subjects.id

        ORDER BY students.name
    """).fetchall()

    conn.close()

    return render_template(
        "marks.html",

        students=students,

        subjects=subjects,

        marks=marks_list
    )


# =========================================================
# SMART PERFORMANCE ANALYSIS
# =========================================================

@app.route("/performance")
@role_required("admin", "faculty")
def performance():

    conn = get_db()

    students = conn.execute("""
        SELECT *
        FROM students
        ORDER BY name
    """).fetchall()

    performance_data = []

    for student in students:

        student_id = student["id"]

        # -------------------------------------------------
        # MARKS
        # -------------------------------------------------

        marks = conn.execute("""
            SELECT

                AVG(internal_mark) AS internal,

                AVG(assignment_mark) AS assignment,

                AVG(quiz_mark) AS quiz

            FROM marks

            WHERE student_id = ?
        """, (
            student_id,
        )).fetchone()

        internal = (
            marks["internal"] or 0
        )

        assignment = (
            marks["assignment"] or 0
        )

        quiz = (
            marks["quiz"] or 0
        )

        marks_average = (
            internal +
            assignment +
            quiz
        ) / 3

        # -------------------------------------------------
        # ATTENDANCE
        # -------------------------------------------------

        attendance = conn.execute("""
            SELECT

                COUNT(*) AS total,

                SUM(
                    CASE
                        WHEN status = 'Present'
                        THEN 1
                        ELSE 0
                    END
                ) AS present

            FROM attendance

            WHERE register_no = ?
        """, (
            student["reg_no"],
        )).fetchone()

        total_attendance = (
            attendance["total"] or 0
        )

        present = (
            attendance["present"] or 0
        )

        if total_attendance > 0:

            attendance_percentage = (
                present /
                total_attendance
            ) * 100

        else:

            attendance_percentage = 0

        # -------------------------------------------------
        # ACTIVITIES
        # -------------------------------------------------

        activity = conn.execute("""
            SELECT

                AVG(score) AS activity_average

            FROM activities

            WHERE student_id = ?
        """, (
            student_id,
        )).fetchone()

        activity_average = (
            activity["activity_average"] or 0
        )

        # -------------------------------------------------
        # OVERALL
        # -------------------------------------------------

        overall = (

            marks_average * 0.50

            +

            attendance_percentage * 0.30

            +

            activity_average * 0.20

        )

        # -------------------------------------------------
        # RISK
        # -------------------------------------------------

        if overall >= 75:

            risk = "Low"

            recommendation = (
                "Excellent performance. "
                "Keep up the good work!"
            )

        elif overall >= 50:

            risk = "Medium"

            recommendation = (
                "Performance is average. "
                "Focus on improving marks "
                "and attendance."
            )

        else:

            risk = "High"

            recommendation = (
                "Student needs academic "
                "support and regular monitoring."
            )

        performance_data.append({

            "id":
                student["id"],

            "name":
                student["name"],

            "reg_no":
                student["reg_no"],

            "marks":
                round(
                    marks_average,
                    2
                ),

            "attendance":
                round(
                    attendance_percentage,
                    2
                ),

            "activities":
                round(
                    activity_average,
                    2
                ),

            "overall":
                round(
                    overall,
                    2
                ),

            "risk":
                risk,

            "recommendation":
                recommendation

        })

    conn.close()

    return render_template(
        "performance.html",
        performance=performance_data
    )


# =========================================================
# STUDENT PROFILE
# =========================================================

@app.route("/student_profile/<int:id>")
@role_required("admin", "faculty")
def student_profile(id):

    conn = get_db()

    student = conn.execute("""
        SELECT *
        FROM students
        WHERE id = ?
    """, (
        id,
    )).fetchone()

    if not student:

        conn.close()

        return "Student not found", 404

    # -----------------------------------------------------
    # MARKS
    # -----------------------------------------------------

    marks = conn.execute("""
        SELECT

            subjects.subject_name,

            marks.internal_mark,

            marks.assignment_mark,

            marks.quiz_mark

        FROM marks

        JOIN subjects

            ON marks.subject_id =
               subjects.id

        WHERE marks.student_id = ?
    """, (
        id,
    )).fetchall()

    # -----------------------------------------------------
    # ATTENDANCE
    # -----------------------------------------------------

    attendance = conn.execute("""
        SELECT

            COUNT(*) AS total,

            SUM(
                CASE
                    WHEN status = 'Present'
                    THEN 1
                    ELSE 0
                END
            ) AS present

        FROM attendance

        WHERE register_no = ?
    """, (
        student["reg_no"],
    )).fetchone()

    total_attendance = (
        attendance["total"] or 0
    )

    present = (
        attendance["present"] or 0
    )

    if total_attendance > 0:

        attendance_percentage = round(
            (
                present /
                total_attendance
            ) * 100,
            2
        )

    else:

        attendance_percentage = 0

    # -----------------------------------------------------
    # ACTIVITIES
    # -----------------------------------------------------

    activities = conn.execute("""
        SELECT

            activity_name,

            score,

            date

        FROM activities

        WHERE student_id = ?

        ORDER BY date DESC
    """, (
        id,
    )).fetchall()

    # -----------------------------------------------------
    # ACTIVITY AVERAGE
    # -----------------------------------------------------

    activity_result = conn.execute("""
        SELECT

            AVG(score) AS average

        FROM activities

        WHERE student_id = ?
    """, (
        id,
    )).fetchone()

    activity_average = round(
        activity_result["average"] or 0,
        2
    )

    # -----------------------------------------------------
    # MARKS AVERAGE
    # -----------------------------------------------------

    marks_result = conn.execute("""
        SELECT

            AVG(
                (
                    COALESCE(internal_mark, 0)
                    +
                    COALESCE(assignment_mark, 0)
                    +
                    COALESCE(quiz_mark, 0)
                ) / 3.0
            ) AS average

        FROM marks

        WHERE student_id = ?
    """, (
        id,
    )).fetchone()

    marks_average = round(
        marks_result["average"] or 0,
        2
    )

    # -----------------------------------------------------
    # OVERALL
    # -----------------------------------------------------

    overall = round(

        (marks_average * 0.50)

        +

        (attendance_percentage * 0.30)

        +

        (activity_average * 0.20),

        2
    )

    # -----------------------------------------------------
    # PERFORMANCE LEVEL
    # -----------------------------------------------------

    if overall >= 75:

        performance_level = "Excellent"

        risk = "Low"

        recommendation = (
            "Excellent performance. "
            "Keep up the good work!"
        )

    elif overall >= 50:

        performance_level = "Average"

        risk = "Medium"

        recommendation = (
            "Focus on improving marks, "
            "attendance and activities."
        )

    else:

        performance_level = "Needs Improvement"

        risk = "High"

        recommendation = (
            "Student needs academic support "
            "and regular monitoring."
        )

    conn.close()

    return render_template(

        "student_profile.html",

        student=student,

        marks=marks,

        activities=activities,

        attendance_percentage=
            attendance_percentage,

        present=present,

        total_attendance=
            total_attendance,

        activity_average=
            activity_average,

        marks_average=
            marks_average,

        overall=overall,

        performance_level=
            performance_level,

        risk=risk,

        recommendation=
            recommendation
    )


# =========================================================
# STUDENT DASHBOARD
# =========================================================

@app.route("/my_dashboard")
@role_required("student")
def my_dashboard():

    conn = get_db()

    # GET USER
    user = conn.execute("""
        SELECT student_id
        FROM users
        WHERE id = ?
    """, (
        session["user_id"],
    )).fetchone()

    if not user or not user["student_id"]:

        conn.close()

        return (
            "Student account is not connected.",
            403
        )

    # GET STUDENT
    student = conn.execute("""
        SELECT *
        FROM students
        WHERE id = ?
    """, (
        user["student_id"],
    )).fetchone()

    if not student:

        conn.close()

        return (
            "Student record not found.",
            404
        )

    reg_no = student["reg_no"]

    student_id = student["id"]

    # -----------------------------------------------------
    # ATTENDANCE
    # -----------------------------------------------------

    attendance_records = conn.execute("""
        SELECT status
        FROM attendance
        WHERE register_no = ?
    """, (
        reg_no,
    )).fetchall()

    total_attendance = len(
        attendance_records
    )

    present_count = sum(
        1
        for record in attendance_records
        if record["status"] == "Present"
    )

    absent_count = sum(
        1
        for record in attendance_records
        if record["status"] == "Absent"
    )

    if total_attendance > 0:

        attendance_percentage = round(
            (
                present_count /
                total_attendance
            ) * 100,
            2
        )

    else:

        attendance_percentage = 0

    # -----------------------------------------------------
    # MARKS
    # -----------------------------------------------------

    marks_records = conn.execute("""
        SELECT

            internal_mark,

            assignment_mark,

            quiz_mark

        FROM marks

        WHERE student_id = ?
    """, (
        student_id,
    )).fetchall()

    mark_values = []

    for mark in marks_records:

        average = (

            float(
                mark["internal_mark"] or 0
            )

            +

            float(
                mark["assignment_mark"] or 0
            )

            +

            float(
                mark["quiz_mark"] or 0
            )

        ) / 3

        mark_values.append(
            average
        )

    if mark_values:

        marks_average = round(
            sum(mark_values) /
            len(mark_values),
            2
        )

    else:

        marks_average = 0

    # -----------------------------------------------------
    # ACTIVITIES
    # -----------------------------------------------------

    activities = conn.execute("""
        SELECT *
        FROM activities

        WHERE student_id = ?

        ORDER BY date DESC
    """, (
        student_id,
    )).fetchall()

    activity_scores = [

        float(
            activity["score"] or 0
        )

        for activity in activities

    ]

    if activity_scores:

        activity_average = round(
            sum(activity_scores) /
            len(activity_scores),
            2
        )

    else:

        activity_average = 0

    # -----------------------------------------------------
    # OVERALL
    # -----------------------------------------------------

    overall = round(

        (marks_average * 0.50)

        +

        (attendance_percentage * 0.30)

        +

        (activity_average * 0.20),

        2
    )

    # -----------------------------------------------------
    # PERFORMANCE
    # -----------------------------------------------------

    if overall >= 75:

        performance_level = "Excellent"

        risk = "Low"

        recommendation = (
            "Keep up the excellent performance."
        )

    elif overall >= 50:

        performance_level = "Average"

        risk = "Medium"

        recommendation = (
            "Improve attendance, "
            "marks and activities."
        )

    else:

        performance_level = "Needs Improvement"

        risk = "High"

        recommendation = (
            "Immediate academic improvement "
            "is recommended."
        )

    # -----------------------------------------------------
    # RECENT ATTENDANCE
    # -----------------------------------------------------

    recent_attendance = conn.execute("""
        SELECT

            attendance.date,

            attendance.status,

            subjects.subject_name

        FROM attendance

        LEFT JOIN subjects

            ON attendance.subject_id =
               subjects.id

        WHERE attendance.register_no = ?

        ORDER BY attendance.date DESC

        LIMIT 5
    """, (
        reg_no,
    )).fetchall()

    # -----------------------------------------------------
    # RECENT ACTIVITIES
    # -----------------------------------------------------

    recent_activities = conn.execute("""
        SELECT

            activity_name,

            score,

            date

        FROM activities

        WHERE student_id = ?

        ORDER BY date DESC

        LIMIT 5
    """, (
        student_id,
    )).fetchall()

    conn.close()

    return render_template(

        "student_dashboard.html",

        student=student,

        attendance_percentage=
            attendance_percentage,

        present_count=
            present_count,

        absent_count=
            absent_count,

        total_attendance=
            total_attendance,

        marks_average=
            marks_average,

        activity_average=
            activity_average,

        overall=
            overall,

        performance_level=
            performance_level,

        risk=
            risk,

        recommendation=
            recommendation,

        recent_attendance=
            recent_attendance,

        recent_activities=
            recent_activities
    )


# =========================================================
# MY ATTENDANCE
# =========================================================

@app.route("/my_attendance")
@role_required("student")
def my_attendance():

    conn = get_db()

    user = conn.execute("""
        SELECT student_id
        FROM users
        WHERE id = ?
    """, (
        session["user_id"],
    )).fetchone()

    if not user or not user["student_id"]:

        conn.close()

        return (
            "Student account is not connected.",
            403
        )

    student = conn.execute("""
        SELECT *
        FROM students
        WHERE id = ?
    """, (
        user["student_id"],
    )).fetchone()

    if not student:

        conn.close()

        return (
            "Student record not found.",
            404
        )

    attendance = conn.execute("""
        SELECT

            attendance.date,

            attendance.status,

            subjects.subject_name,

            subjects.subject_code

        FROM attendance

        LEFT JOIN subjects

            ON attendance.subject_id =
               subjects.id

        WHERE attendance.register_no = ?

        ORDER BY attendance.date DESC
    """, (
        student["reg_no"],
    )).fetchall()

    total = len(attendance)

    present = sum(
        1
        for record in attendance
        if record["status"] == "Present"
    )

    absent = sum(
        1
        for record in attendance
        if record["status"] == "Absent"
    )

    if total > 0:

        percentage = round(
            (present / total) * 100,
            2
        )

    else:

        percentage = 0

    conn.close()

    return render_template(

        "my_attendance.html",

        student=student,

        attendance=attendance,

        total=total,

        present=present,

        absent=absent,

        percentage=percentage
    )


# =========================================================
# MY MARKS
# =========================================================

@app.route("/my_marks")
@role_required("student")
def my_marks():

    conn = get_db()

    user = conn.execute("""
        SELECT student_id
        FROM users
        WHERE id = ?
    """, (
        session["user_id"],
    )).fetchone()

    if not user or not user["student_id"]:

        conn.close()

        return (
            "Student account is not connected.",
            403
        )

    student = conn.execute("""
        SELECT *
        FROM students
        WHERE id = ?
    """, (
        user["student_id"],
    )).fetchone()

    if not student:

        conn.close()

        return (
            "Student record not found.",
            404
        )

    marks = conn.execute("""
        SELECT

            subjects.subject_name,

            subjects.subject_code,

            marks.internal_mark,

            marks.assignment_mark,

            marks.quiz_mark

        FROM marks

        JOIN subjects

            ON marks.subject_id =
               subjects.id

        WHERE marks.student_id = ?

        ORDER BY subjects.subject_name
    """, (
        student["id"],
    )).fetchall()

    conn.close()

    return render_template(

        "my_marks.html",

        student=student,

        marks=marks
    )


# =========================================================
# MY ACTIVITIES
# =========================================================

@app.route("/my_activities")
@role_required("student")
def my_activities():

    conn = get_db()

    user = conn.execute("""
        SELECT student_id
        FROM users
        WHERE id = ?
    """, (
        session["user_id"],
    )).fetchone()

    if not user or not user["student_id"]:

        conn.close()

        return (
            "Student account is not connected.",
            403
        )

    student = conn.execute("""
        SELECT *
        FROM students
        WHERE id = ?
    """, (
        user["student_id"],
    )).fetchone()

    if not student:

        conn.close()

        return (
            "Student record not found.",
            404
        )

    activities = conn.execute("""
        SELECT

            activity_name,

            score,

            date

        FROM activities

        WHERE student_id = ?

        ORDER BY date DESC
    """, (
        student["id"],
    )).fetchall()

    result = conn.execute("""
        SELECT

            COUNT(*) AS total,

            AVG(score) AS average

        FROM activities

        WHERE student_id = ?
    """, (
        student["id"],
    )).fetchone()

    total = result["total"] or 0

    average = round(
        result["average"] or 0,
        2
    )

    conn.close()

    return render_template(

        "my_activities.html",

        student=student,

        activities=activities,

        total=total,

        average=average
    )


# =========================================================
# MY PERFORMANCE
# =========================================================

@app.route("/my_performance")
@role_required("student")
def my_performance():

    conn = get_db()

    user = conn.execute("""
        SELECT student_id
        FROM users
        WHERE id = ?
    """, (
        session["user_id"],
    )).fetchone()

    if not user or not user["student_id"]:

        conn.close()

        return (
            "Student account is not connected.",
            403
        )

    student = conn.execute("""
        SELECT *
        FROM students
        WHERE id = ?
    """, (
        user["student_id"],
    )).fetchone()

    if not student:

        conn.close()

        return (
            "Student record not found.",
            404
        )

    # -----------------------------------------------------
    # MARKS
    # -----------------------------------------------------

    marks_result = conn.execute("""
        SELECT

            AVG(internal_mark) AS internal,

            AVG(assignment_mark) AS assignment,

            AVG(quiz_mark) AS quiz

        FROM marks

        WHERE student_id = ?
    """, (
        student["id"],
    )).fetchone()

    internal = (
        marks_result["internal"] or 0
    )

    assignment = (
        marks_result["assignment"] or 0
    )

    quiz = (
        marks_result["quiz"] or 0
    )

    marks_average = round(

        (
            internal +
            assignment +
            quiz
        ) / 3,

        2
    )

    # -----------------------------------------------------
    # ATTENDANCE
    # -----------------------------------------------------

    attendance = conn.execute("""
        SELECT

            COUNT(*) AS total,

            SUM(
                CASE
                    WHEN status = 'Present'
                    THEN 1
                    ELSE 0
                END
            ) AS present

        FROM attendance

        WHERE register_no = ?
    """, (
        student["reg_no"],
    )).fetchone()

    total_attendance = (
        attendance["total"] or 0
    )

    present = (
        attendance["present"] or 0
    )

    if total_attendance > 0:

        attendance_percentage = round(
            (
                present /
                total_attendance
            ) * 100,
            2
        )

    else:

        attendance_percentage = 0

    # -----------------------------------------------------
    # ACTIVITIES
    # -----------------------------------------------------

    activity = conn.execute("""
        SELECT

            AVG(score) AS average

        FROM activities

        WHERE student_id = ?
    """, (
        student["id"],
    )).fetchone()

    activity_average = round(
        activity["average"] or 0,
        2
    )

    # -----------------------------------------------------
    # OVERALL
    # -----------------------------------------------------

    overall = round(

        (marks_average * 0.50)

        +

        (attendance_percentage * 0.30)

        +

        (activity_average * 0.20),

        2
    )

    # -----------------------------------------------------
    # PERFORMANCE
    # -----------------------------------------------------

    if overall >= 75:

        performance_level = "Excellent"

        risk = "Low"

        recommendation = (
            "Excellent performance! "
            "Keep maintaining your marks, "
            "attendance and activities."
        )

    elif overall >= 50:

        performance_level = "Average"

        risk = "Medium"

        recommendation = (
            "Your performance is average. "
            "Try to improve your marks "
            "and attendance."
        )

    else:

        performance_level = "Needs Improvement"

        risk = "High"

        recommendation = (
            "You need to improve your "
            "academic performance and attendance."
        )

    conn.close()

    return render_template(

        "my_performance.html",

        student=student,

        marks_average=
            marks_average,

        attendance_percentage=
            attendance_percentage,

        activity_average=
            activity_average,

        overall=
            overall,

        performance_level=
            performance_level,

        risk=
            risk,

        recommendation=
            recommendation
    )


# =========================================================
# ADVANCED ATTENDANCE ANALYTICS
# =========================================================

@app.route("/attendance_analytics")
@role_required("admin", "faculty")
def attendance_analytics():

    conn = get_db()
    cursor = conn.cursor()

    # -----------------------------------------------------
    # OVERALL
    # -----------------------------------------------------

    overall = cursor.execute("""
        SELECT

            COUNT(*) AS total,

            SUM(
                CASE
                    WHEN status = 'Present'
                    THEN 1
                    ELSE 0
                END
            ) AS present,

            SUM(
                CASE
                    WHEN status = 'Absent'
                    THEN 1
                    ELSE 0
                END
            ) AS absent

        FROM attendance
    """).fetchone()

    total = overall["total"] or 0

    present = overall["present"] or 0

    absent = overall["absent"] or 0

    if total > 0:

        percentage = round(
            (present / total) * 100,
            2
        )

    else:

        percentage = 0

    # -----------------------------------------------------
    # SUBJECT-WISE
    # -----------------------------------------------------

    subject_data = cursor.execute("""
        SELECT

            subjects.subject_name,

            COUNT(attendance.id) AS total,

            SUM(
                CASE
                    WHEN attendance.status = 'Present'
                    THEN 1
                    ELSE 0
                END
            ) AS present,

            SUM(
                CASE
                    WHEN attendance.status = 'Absent'
                    THEN 1
                    ELSE 0
                END
            ) AS absent

        FROM subjects

        LEFT JOIN attendance

            ON subjects.id =
               attendance.subject_id

        GROUP BY subjects.id

        ORDER BY subjects.subject_name
    """).fetchall()

    # -----------------------------------------------------
    # STUDENT-WISE
    # -----------------------------------------------------

    student_data = cursor.execute("""
        SELECT

            students.id,

            students.name,

            students.reg_no,

            COUNT(attendance.id) AS total,

            SUM(
                CASE
                    WHEN attendance.status = 'Present'
                    THEN 1
                    ELSE 0
                END
            ) AS present,

            SUM(
                CASE
                    WHEN attendance.status = 'Absent'
                    THEN 1
                    ELSE 0
                END
            ) AS absent

        FROM students

        LEFT JOIN attendance

            ON students.reg_no =
               attendance.register_no

        GROUP BY students.id

        ORDER BY students.name
    """).fetchall()

    # -----------------------------------------------------
    # DATE-WISE
    # -----------------------------------------------------

    date_data = cursor.execute("""
        SELECT

            date,

            COUNT(*) AS total,

            SUM(
                CASE
                    WHEN status = 'Present'
                    THEN 1
                    ELSE 0
                END
            ) AS present,

            SUM(
                CASE
                    WHEN status = 'Absent'
                    THEN 1
                    ELSE 0
                END
            ) AS absent

        FROM attendance

        GROUP BY date

        ORDER BY date ASC
    """).fetchall()

    # -----------------------------------------------------
    # LOW ATTENDANCE
    # -----------------------------------------------------

    low_attendance = []

    for student in student_data:

        student_total = (
            student["total"] or 0
        )

        student_present = (
            student["present"] or 0
        )

        if student_total > 0:

            student_percentage = round(
                (
                    student_present /
                    student_total
                ) * 100,
                2
            )

        else:

            student_percentage = 0

        if student_percentage < 75:

            low_attendance.append({

                "name":
                    student["name"],

                "reg_no":
                    student["reg_no"],

                "total":
                    student_total,

                "present":
                    student_present,

                "absent":
                    student["absent"] or 0,

                "percentage":
                    student_percentage

            })

    conn.close()

    return render_template(

        "attendance_analytics.html",

        total=total,

        present=present,

        absent=absent,

        percentage=percentage,

        subject_data=
            subject_data,

        student_data=
            student_data,

        date_data=
            date_data,

        low_attendance=
            low_attendance
    )


# =========================================================
# AT-RISK STUDENT DETECTION
# =========================================================

@app.route("/at_risk_students")
@role_required("admin", "faculty")
def at_risk_students():

    conn = get_db()
    cursor = conn.cursor()

    students = cursor.execute("""
        SELECT

            id,
            name,
            reg_no

        FROM students

        ORDER BY name
    """).fetchall()

    at_risk = []

    normal_students = []

    for student in students:

        # -------------------------------------------------
        # ATTENDANCE
        # -------------------------------------------------

        attendance = cursor.execute("""
            SELECT

                COUNT(*) AS total,

                SUM(
                    CASE
                        WHEN status = 'Present'
                        THEN 1
                        ELSE 0
                    END
                ) AS present

            FROM attendance

            WHERE register_no = ?
        """, (
            student["reg_no"],
        )).fetchone()

        total_attendance = (
            attendance["total"] or 0
        )

        present_attendance = (
            attendance["present"] or 0
        )

        if total_attendance > 0:

            attendance_percentage = round(
                (
                    present_attendance /
                    total_attendance
                ) * 100,
                2
            )

        else:

            attendance_percentage = 0

        # -------------------------------------------------
        # MARKS
        # IMPORTANT:
        # Correct average is / 3
        # -------------------------------------------------

        marks = cursor.execute("""
            SELECT

                AVG(
                    (
                        COALESCE(internal_mark, 0)
                        +
                        COALESCE(assignment_mark, 0)
                        +
                        COALESCE(quiz_mark, 0)
                    ) / 3.0
                ) AS average_mark

            FROM marks

            WHERE student_id = ?
        """, (
            student["id"],
        )).fetchone()

        average_mark = round(
            marks["average_mark"] or 0,
            2
        )

        # -------------------------------------------------
        # ACTIVITIES
        # -------------------------------------------------

        activities = cursor.execute("""
            SELECT

                COUNT(*) AS total_activities,

                AVG(score) AS average_activity

            FROM activities

            WHERE student_id = ?
        """, (
            student["id"],
        )).fetchone()

        total_activities = (
            activities["total_activities"] or 0
        )

        average_activity = round(
            activities["average_activity"] or 0,
            2
        )

        # -------------------------------------------------
        # RISK CALCULATION
        # -------------------------------------------------

        risk_points = 0

        reasons = []

        # Attendance
        if attendance_percentage < 75:

            risk_points += 1

            reasons.append(
                "Low Attendance"
            )

        # Marks
        if average_mark < 40:

            risk_points += 1

            reasons.append(
                "Low Marks"
            )

        # Activity
        if (
            total_activities > 0
            and
            average_activity < 40
        ):

            risk_points += 1

            reasons.append(
                "Low Activity Performance"
            )

        # -------------------------------------------------
        # RISK LEVEL
        # -------------------------------------------------

        if risk_points >= 2:

            risk_level = "High Risk"

        elif risk_points == 1:

            risk_level = "Medium Risk"

        else:

            risk_level = "Normal"

        student_data = {

            "name":
                student["name"],

            "reg_no":
                student["reg_no"],

            "attendance":
                attendance_percentage,

            "marks":
                average_mark,

            "activity":
                average_activity,

            "risk_level":
                risk_level,

            "reasons":
                reasons

        }

        if risk_level == "Normal":

            normal_students.append(
                student_data
            )

        else:

            at_risk.append(
                student_data
            )

    conn.close()

    # -----------------------------------------------------
    # RISK COUNTS
    # -----------------------------------------------------

    high_risk = sum(

        1

        for student in at_risk

        if student["risk_level"]
        == "High Risk"

    )

    medium_risk = sum(

        1

        for student in at_risk

        if student["risk_level"]
        == "Medium Risk"

    )

    return render_template(

        "at_risk_students.html",

        at_risk=at_risk,

        normal_students=
            normal_students,

        high_risk=
            high_risk,

        medium_risk=
            medium_risk,

        total_at_risk=
            len(at_risk)
    )


# =========================================================
# AI PERFORMANCE PREDICTION
# =========================================================

@app.route("/performance_prediction")
@role_required("admin", "faculty")
def performance_prediction():

    conn = get_db()
    cursor = conn.cursor()

    students = cursor.execute("""
        SELECT

            id,
            name,
            reg_no

        FROM students

        ORDER BY name
    """).fetchall()

    predictions = []

    for student in students:

        # -------------------------------------------------
        # ATTENDANCE
        # -------------------------------------------------

        attendance = cursor.execute("""
            SELECT

                COUNT(*) AS total,

                SUM(
                    CASE
                        WHEN status = 'Present'
                        THEN 1
                        ELSE 0
                    END
                ) AS present

            FROM attendance

            WHERE register_no = ?
        """, (
            student["reg_no"],
        )).fetchone()

        total_attendance = (
            attendance["total"] or 0
        )

        present_attendance = (
            attendance["present"] or 0
        )

        if total_attendance > 0:

            attendance_percentage = round(
                (
                    present_attendance /
                    total_attendance
                ) * 100,
                2
            )

        else:

            attendance_percentage = 0

        # -------------------------------------------------
        # MARKS
        # Correct average / 3
        # -------------------------------------------------

        marks = cursor.execute("""
            SELECT

                AVG(
                    (
                        COALESCE(internal_mark, 0)
                        +
                        COALESCE(assignment_mark, 0)
                        +
                        COALESCE(quiz_mark, 0)
                    ) / 3.0
                ) AS average_mark

            FROM marks

            WHERE student_id = ?
        """, (
            student["id"],
        )).fetchone()

        average_mark = round(
            marks["average_mark"] or 0,
            2
        )

        # -------------------------------------------------
        # ACTIVITIES
        # -------------------------------------------------

        activities = cursor.execute("""
            SELECT

                AVG(score) AS average_activity

            FROM activities

            WHERE student_id = ?
        """, (
            student["id"],
        )).fetchone()

        activity_score = round(
            activities["average_activity"] or 0,
            2
        )

        # -------------------------------------------------
        # PREDICTION SCORE
        # -----------------------------------------------------

        prediction_score = round(

            (attendance_percentage * 0.40)

            +

            (average_mark * 0.40)

            +

            (activity_score * 0.20),

            2
        )

        # -------------------------------------------------
        # PREDICTION
        # -----------------------------------------------------

        if prediction_score >= 80:

            prediction = "Excellent"

            risk = "Low"

        elif prediction_score >= 60:

            prediction = "Good"

            risk = "Low"

        elif prediction_score >= 40:

            prediction = "Average"

            risk = "Medium"

        else:

            prediction = "At Risk"

            risk = "High"

        predictions.append({

            "name":
                student["name"],

            "reg_no":
                student["reg_no"],

            "attendance":
                attendance_percentage,

            "marks":
                average_mark,

            "activity":
                activity_score,

            "score":
                prediction_score,

            "prediction":
                prediction,

            "risk":
                risk

        })

    conn.close()

    # -----------------------------------------------------
    # COUNTS
    # -----------------------------------------------------

    excellent = sum(

        1

        for p in predictions

        if p["prediction"]
        == "Excellent"

    )

    good = sum(

        1

        for p in predictions

        if p["prediction"]
        == "Good"

    )

    average = sum(

        1

        for p in predictions

        if p["prediction"]
        == "Average"

    )

    at_risk = sum(

        1

        for p in predictions

        if p["prediction"]
        == "At Risk"

    )

    return render_template(

        "performance_prediction.html",

        predictions=
            predictions,

        excellent=
            excellent,

        good=
            good,

        average=
            average,

        at_risk=
            at_risk
    )


# =========================================================
# ATTENDANCE PDF
# =========================================================

@app.route("/attendance_pdf")
@role_required("admin", "faculty")
def attendance_pdf():

    conn = get_db()

    cursor = conn.cursor()

    records = cursor.execute("""
        SELECT

            register_no,

            student_name,

            date,

            status

        FROM attendance

        ORDER BY date DESC
    """).fetchall()

    conn.close()

    buffer = io.BytesIO()

    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4
    )

    styles = getSampleStyleSheet()

    elements = []

    title = Paragraph(
        "Smart Campus - Attendance Report",
        styles["Title"]
    )

    elements.append(title)

    data = [

        [
            "Register No",
            "Student Name",
            "Date",
            "Status"
        ]

    ]

    for record in records:

        data.append([

            record["register_no"],

            record["student_name"],

            record["date"],

            record["status"]

        ])

    table = Table(data)

    table.setStyle(
        TableStyle([

            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.grey
            ),

            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),

            (
                "GRID",
                (0, 0),
                (-1, -1),
                1,
                colors.black
            ),

            (
                "ALIGN",
                (0, 0),
                (-1, -1),
                "CENTER"
            ),

            (
                "PADDING",
                (0, 0),
                (-1, -1),
                6
            )

        ])
    )

    elements.append(table)

    pdf.build(elements)

    buffer.seek(0)

    return send_file(

        buffer,

        as_attachment=True,

        download_name=
            "attendance_report.pdf",

        mimetype=
            "application/pdf"
    )


# =========================================================
# ATTENDANCE EXCEL
# =========================================================

@app.route("/attendance_excel")
@role_required("admin", "faculty")
def attendance_excel():

    conn = get_db()

    cursor = conn.cursor()

    records = cursor.execute("""
        SELECT

            register_no,

            student_name,

            date,

            status

        FROM attendance

        ORDER BY date DESC
    """).fetchall()

    conn.close()

    workbook = Workbook()

    sheet = workbook.active

    sheet.title = "Attendance Report"

    sheet.append([

        "Register No",
        "Student Name",
        "Date",
        "Status"

    ])

    for record in records:

        sheet.append([

            record["register_no"],

            record["student_name"],

            record["date"],

            record["status"]

        ])

    sheet.column_dimensions[
        "A"
    ].width = 18

    sheet.column_dimensions[
        "B"
    ].width = 25

    sheet.column_dimensions[
        "C"
    ].width = 15

    sheet.column_dimensions[
        "D"
    ].width = 15

    buffer = io.BytesIO()

    workbook.save(buffer)

    buffer.seek(0)

    return send_file(

        buffer,

        as_attachment=True,

        download_name=
            "attendance_report.xlsx",

        mimetype=(
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        )
    )


# =========================================================
# PERFORMANCE EXCEL
# =========================================================

@app.route("/performance_excel")
@role_required("admin", "faculty")
def performance_excel():

    conn = get_db()

    cursor = conn.cursor()

    students = cursor.execute("""
        SELECT

            students.name,

            students.reg_no,

            AVG(
                (
                    COALESCE(
                        marks.internal_mark,
                        0
                    )

                    +

                    COALESCE(
                        marks.assignment_mark,
                        0
                    )

                    +

                    COALESCE(
                        marks.quiz_mark,
                        0
                    )

                ) / 3.0

            ) AS average_mark

        FROM students

        LEFT JOIN marks

            ON students.id =
               marks.student_id

        GROUP BY students.id

        ORDER BY average_mark DESC
    """).fetchall()

    conn.close()

    workbook = Workbook()

    sheet = workbook.active

    sheet.title = "Performance Report"

    sheet.append([

        "Student Name",

        "Register No",

        "Average Mark"

    ])

    for student in students:

        sheet.append([

            student["name"],

            student["reg_no"],

            round(
                student["average_mark"] or 0,
                2
            )

        ])

    sheet.column_dimensions[
        "A"
    ].width = 25

    sheet.column_dimensions[
        "B"
    ].width = 18

    sheet.column_dimensions[
        "C"
    ].width = 18

    buffer = io.BytesIO()

    workbook.save(buffer)

    buffer.seek(0)

    return send_file(

        buffer,

        as_attachment=True,

        download_name=
            "performance_report.xlsx",

        mimetype=(
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        )
    )


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )