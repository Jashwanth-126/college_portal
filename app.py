from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import csv
from io import BytesIO
from datetime import date, datetime, timedelta
import datetime as dt # Import the module as 'dt' to avoid conflicts
from reportlab.lib.pagesizes import letter
from io import StringIO, BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from flask_mail import Mail, Message
import random
from datetime import datetime
from flask import jsonify # Needed for the new API route
from werkzeug.utils import secure_filename
import uuid
# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Create Flask app first
app = Flask(__name__)
app.secret_key = "SDCinstitute@123"  # Change this in production!

# --- Email Config ---
app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", "587"))
app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "True") == "True"
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = app.config["MAIL_USERNAME"]
app.config["MAIL_TIMEOUT"] = 10
mail = Mail(app)

# --- Supabase connection --
@app.route("/")
def index():
    return render_template("index.html")
# --- ADMIN LOGIN ---
@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        gmail = request.form["gmail"]

        # Fetch admin details from Supabase
        response = supabase.table("admins").select("*").eq("gmail", gmail).execute()
        
        if response.data:
            admin = response.data[0]
            if (
                admin["username"] == username
                and admin["password"] == password
                and admin["gmail"] == gmail
            ):
                session["admin"] = admin["username"]
                return redirect(url_for("admin_dashboard"))
            else:
                flash("Invalid credentials, please try again.", "error")
        else:
            flash("Admin not found.", "error")
    
    return render_template("admin_login.html")


@app.route("/dashboard")
def admin_dashboard():
    if "admin" in session:
        return render_template("admin_dashboard.html", admin=session["admin"])
    else:
        return redirect(url_for("admin_login"))

# --- FORGOT PASSWORD ---
@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        gmail = request.form["gmail"]
        new_password = request.form["new_password"]

        # Update password in DB
        response = supabase.table("admins").update({"password": new_password}).eq("gmail", gmail).execute()

        if response.data:
            flash("Password updated successfully! Please login.")
            return redirect(url_for("admin_login"))
        else:
            flash("Gmail not found. Please try again.")
    
    return render_template("forgot_password.html")

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("admin_login"))


# --- JINJA2 CUSTOM FILTERS ---

def datetimeformat(value, format='%Y-%m-%d %I:%M %p'):
    """
    Custom filter to format Supabase ISO timestamps using the standard dt.datetime module access.
    """
    if value is None:
        return ""
    
    # 1. Prepare the value: Replace 'Z' with '+00:00' (UTC timezone)
    prepared_value = value.replace('Z', '+00:00')
    
    # 2. Determine the parsing format based on whether microseconds are present.
    if '.' in prepared_value:
        parse_format = '%Y-%m-%dT%H:%M:%S.%f%z'
    else:
        parse_format = '%Y-%m-%dT%H:%M:%S%z'
        
    try:
        # CRITICAL FIX: Use the 'dt' alias to call the standard class method
        dt_obj = dt.datetime.strptime(prepared_value, parse_format)
        
        # 3. Format the datetime object to the desired output string
        return dt_obj.strftime(format)
        
    except ValueError:
        # Fallback if the parsing fails
        return value

# Register the filter with Flask's Jinja environment
app.jinja_env.filters['datetimeformat'] = datetimeformat

# ----------------------------

@app.route("/register_student", methods=["GET", "POST"])
def register_student():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        username = request.form["username"]
        gmail = request.form["gmail"]
        password = f"{username}@123"

        # ✅ Check if gmail already exists
        existing = supabase.table("students").select("*").eq("gmail", gmail).execute()

        if existing.data:  
            flash("Student with this Gmail already exists!", "error")
        else:
            # Insert new student
            supabase.table("students").insert({
                "username": username,
                "gmail": gmail,
                "password": password
            }).execute()

            # Send email with credentials
            try:
                msg = Message(
                    subject="Your Student Account - SDC PU College",
                    recipients=[gmail],
                    body=f"Hello {username},\n\nYour student account has been created.\n\nUsername: {username}\nPassword: {password}\n\nRegards,\nSDC PU College"
                )
                mail.send(msg)
                flash("Student registered successfully and email sent!", "success")
            except Exception as e:
                flash(f"Student registered but failed to send email: {str(e)}", "error")

    # Fetch all students to display
    students = supabase.table("students").select("username, gmail").execute().data
    return render_template("register_student.html", students=students)




# --- EXPORT STUDENTS AS CSV ---
@app.route("/export_students/csv")
def export_students_csv():
    students = supabase.table("students").select("username, gmail").execute().data

    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["Username", "Gmail"])
    for s in students:
        writer.writerow([s["username"], s["gmail"]])

    output = Response(si.getvalue(), mimetype="text/csv")
    output.headers["Content-Disposition"] = "attachment; filename=students.csv"
    return output


# --- EXPORT STUDENTS AS PDF ---
@app.route("/export_students/pdf")
def export_students_pdf():
    students = supabase.table("students").select("username, gmail").execute().data

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    p.setFont("Helvetica-Bold", 14)
    p.drawString(200, height - 50, "Registered Students")

    p.setFont("Helvetica", 12)
    y = height - 100
    p.drawString(100, y, "Username")
    p.drawString(300, y, "Gmail")
    y -= 20

    for s in students:
        p.drawString(100, y, s["username"])
        p.drawString(300, y, s["gmail"])
        y -= 20
        if y < 50:  # new page if too many students
            p.showPage()
            y = height - 100

    p.save()
    buffer.seek(0)

    return Response(buffer, mimetype="application/pdf",
                    headers={"Content-Disposition": "attachment;filename=students.pdf"})

# --- USER LOGIN ---
# --- USER LOGIN (FIXED) ---
@app.route("/user_login", methods=["GET", "POST"])
def user_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        gmail = request.form["gmail"]

        # Step 1: Check in 'students' table for general login credentials (Selecting '*' only)
        result = (
            supabase.table("students")
            .select("*")
            .eq("username", username)
            .eq("gmail", gmail)
            .eq("password", password)
            .execute()
        )

        if result.data:
            # Step 2: Fetch the corresponding record from 'att_students' for attendance features
            att_result = (
                supabase.table("att_students")
                .select("id, section_id")
                .eq("username", username) # Linking via username
                .execute()
            )
            
            # Start session with basic user data
            session["user"] = username
            
            # Clear previous attendance keys before setting them
            session.pop("att_student_id", None)
            session.pop("section_id", None)
            
            if att_result.data:
                # Attendance profile found, store the required IDs
                att_student_info = att_result.data[0]
                session["att_student_id"] = att_student_info["id"] # ID used in 'attendance' table
                session["section_id"] = att_student_info["section_id"]
                flash("Login successful!", "success")
            else:
                # Attendance profile NOT found
                flash("Login successful. IMPORTANT: Your attendance profile is currently inactive. Contact Admin.", "warning") 

            return redirect(url_for("user_dashboard")) 

        else:
            flash("Invalid login credentials!", "error")

    return render_template("user_login.html")

# --- USER DASHBOARD (Simplified) ---
@app.route("/user_dashboard")
def user_dashboard():
    if "user" not in session:
        return redirect(url_for("user_login"))
        
    return render_template("user_dashboard.html", 
                           user=session["user"], 
                           section_id=session.get("section_id"))

# --- USER LOGOUT ---
@app.route("/user_logout")
def user_logout():
    session.pop("user", None)
    flash("You have been logged out.", "success")
    return redirect(url_for("user_login"))



# --- USER FORGOT PASSWORD: STEP 1 (Enter Gmail) ---
@app.route("/user_forgot_password", methods=["GET", "POST"])
def user_forgot_password():
    if request.method == "POST":
        gmail = request.form["gmail"]

        # Check if user exists
        result = supabase.table("students").select("*").eq("gmail", gmail).execute()

        if result.data:
            # Generate random 6-digit OTP
            otp = str(random.randint(100000, 999999))
            session["reset_gmail"] = gmail
            session["reset_otp"] = otp

            # Send OTP via mail
            msg = Message("Password Reset OTP - SDC PU College", recipients=[gmail])
            msg.body = f"Your OTP for password reset is: {otp}\n\nDo not share this with anyone."
            mail.send(msg)

            flash("OTP sent to your registered Gmail.", "success")
            return redirect(url_for("verify_otp"))
        else:
            flash("No account found with this Gmail.", "error")

    return render_template("user_forgot_password.html")


# --- USER FORGOT PASSWORD: STEP 2 (Verify OTP) ---
@app.route("/verify_otp", methods=["GET", "POST"])
def verify_otp():
    if request.method == "POST":
        entered_otp = request.form["otp"]

        if "reset_otp" in session and entered_otp == session["reset_otp"]:
            flash("OTP verified! Please reset your password.", "success")
            return redirect(url_for("reset_password"))
        else:
            flash("Invalid OTP. Try again.", "error")

    return render_template("verify_otp.html")


# --- USER FORGOT PASSWORD: STEP 3 (Reset Password) ---
@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        if new_password != confirm_password:
            flash("Passwords do not match!", "error")
        else:
            gmail = session.get("reset_gmail")
            if gmail:
                supabase.table("students").update({"password": new_password}).eq("gmail", gmail).execute()

                # Clear session values
                session.pop("reset_gmail", None)
                session.pop("reset_otp", None)

                flash("Password reset successful! Please login with new password.", "success")
                return redirect(url_for("user_login"))
            else:
                flash("Session expired. Try again.", "error")
                return redirect(url_for("user_forgot_password"))

    return render_template("reset_password.html")


# --- STUDENT ATTENDANCE VIEW ---
# --- STUDENT ATTENDANCE VIEW ---
@app.route("/student/attendance")
def student_attendance_view():
    # Ensure the user is logged in AND has a stored attendance ID
    if "user" not in session or "att_student_id" not in session:
        flash("Please login to view your attendance.", "error")
        return redirect(url_for("user_login"))

    att_student_id = session["att_student_id"]
    
    # Fetch all attendance records for the logged-in student
    records = (
        supabase.table("attendance")
        .select("attendance_date, status")
        .eq("student_id", att_student_id)
        .order("attendance_date", desc=True) # Show most recent first
        .execute().data
    )

    # Calculate statistics
    total_present = sum(1 for r in records if r["status"] == "Present")
    total_absent = sum(1 for r in records if r["status"] == "Absent")
    
    # Total classes marked (excluding 'Holiday' or other ignored statuses)
    total_class_days = total_present + total_absent
    
    # Calculate attendance percentage
    if total_class_days > 0:
        percentage = round((total_present / total_class_days) * 100, 2)
    else:
        percentage = 0.0

    return render_template(
        "student_attendance.html", # This new template displays the details
        records=records,
        total_class_days=total_class_days,
        total_present=total_present,
        total_absent=total_absent,
        percentage=percentage
    )

# ------------- HELPERS -------------
def require_admin():
    if "admin" not in session:
        flash("Please login as Admin.", "error")
        return False
    return True

def get_file_extension(filename):
    """Safely extracts the file extension."""
    if '.' in filename:
        return filename.rsplit('.', 1)[1].lower()
    return ''

def is_sunday(d: date) -> bool:
    return d.weekday() == 6  # 0=Mon ... 6=Sun

def is_holiday(d: date) -> bool:
    # holidays.holiday_date (DATE)
    res = supabase.table("holidays").select("holiday_date").eq("holiday_date", d.isoformat()).execute()
    return bool(res.data)

def is_working_day(d: date) -> bool:
    return (not is_sunday(d)) and (not is_holiday(d))

# Get course ids by name (Science/Commerce)
def get_course_id(course_name: str):
    res = supabase.table("courses").select("id,name").eq("name", course_name).single().execute()
    return res.data["id"] if res.data else None

# ------------- ATTENDANCE DASHBOARD (LEFT=SCIENCE, RIGHT=COMMERCE) -------------
@app.route("/attendance", methods=["GET", "POST"])
def attendance_dashboard():
    if not require_admin(): 
        return redirect(url_for("admin_login"))

    science_id = get_course_id("Science")
    commerce_id = get_course_id("Commerce")

    sci_classes = supabase.table("classes").select("*").eq("course_id", science_id).execute().data if science_id else []
    com_classes = supabase.table("classes").select("*").eq("course_id", commerce_id).execute().data if commerce_id else []

    # If form submitted, capture the selected date
    selected_date = request.form.get("attendance_date") if request.method == "POST" else None

    return render_template("attendance.html",
                           science_classes=sci_classes,
                           commerce_classes=com_classes,
                           selected_date=selected_date)


# ------------- SECTIONS LIST + ADD -------------
@app.route("/class/<int:class_id>/sections", methods=["GET", "POST"])
def manage_sections(class_id):
    if not require_admin(): 
        return redirect(url_for("admin_login"))

    # 🔹 Get selected date from query
    selected_date = request.args.get("date")

    if request.method == "POST":
        sec_name = request.form.get("section_name", "").strip()
        if not sec_name:
            flash("Section name is required.", "error")
        else:
            existing = (supabase.table("sections")
                        .select("id,name").eq("class_id", class_id).eq("name", sec_name).execute().data)
            if existing:
                flash(f"Section '{sec_name}' already exists for this class.", "error")
            else:
                supabase.table("sections").insert({"class_id": class_id, "name": sec_name}).execute()
                flash("Section added.", "success")

    sections = supabase.table("sections").select("*").eq("class_id", class_id).order("name").execute().data
    cls = supabase.table("classes").select("id,name,course_id").eq("id", class_id).single().execute().data
    course = supabase.table("courses").select("id,name").eq("id", cls["course_id"]).single().execute().data if cls else None

    return render_template("sections.html", sections=sections, class_info=cls, course=course, selected_date=selected_date)

from datetime import date # Ensure 'date' is imported from 'datetime' at the top of your file
# --- ABSENCE EMAIL HELPER FUNCTION (Keep this) ---
def send_absence_email(student_name, student_email, absence_date):
    """Helper function to send absence notification email."""
    try:
        from flask_mail import Message # Assuming Message is imported globally
        # If not, ensure 'from flask_mail import Mail, Message' is at the top of your file
        
        msg = Message(
            subject=f"URGENT: Absence Notification - {absence_date}",
            recipients=[student_email],
            body=f"""
Dear Parent/Guardian of {student_name},

This email is to notify you that {student_name} was marked **ABSENT** from class today, {absence_date}.

Please ensure your child's attendance is maintained and contact the school administration immediately if there is a valid reason for this absence.

Thank you,
SDC Institute Admin Team
"""
        )
        mail.send(msg)
        return True
    except Exception as e:
        # NOTE: For production, you might want a more robust logging solution.
        print(f"ERROR sending absence email to {student_email}: {e}")
        return False


# --- NEW STRUCTURED SYLLABUS MANAGEMENT ROUTES ---

@app.route("/admin/syllabus_manager", methods=["GET"])
def admin_syllabus_manager():
    if not require_admin():
        return redirect(url_for("admin_login"))

    sections = supabase.table("sections").select("id, name").order("name").execute().data
    selected_section_id = request.args.get("section_id", type=int)
    syllabus_subjects = []
    selected_section_name = None

    if selected_section_id:
        # Fetch all defined syllabus subjects for the selected section
        syllabus_subjects = (
            supabase.table("section_subject_syllabi")
            .select("*")
            .eq("section_id", selected_section_id)
            .order("subject_name")
            .execute().data
        )
        
        # Get the name of the selected section for display
        try:
            section_data = supabase.table("sections").select("name").eq("id", selected_section_id).single().execute().data
            selected_section_name = section_data["name"]
        except:
            selected_section_name = f"ID {selected_section_id}"

    return render_template(
        "admin_syllabus_structured.html", 
        sections=sections, 
        selected_section_id=selected_section_id,
        selected_section_name=selected_section_name,
        syllabus_subjects=syllabus_subjects
    )


@app.route("/admin/syllabus_subject_save", methods=["POST"])
def admin_syllabus_subject_save():
    if not require_admin():
        return redirect(url_for("admin_login"))

    action = request.form.get("action")
    section_id = request.form.get("section_id", type=int)

    if not section_id:
        flash("Section not selected.", "error")
        return redirect(url_for("admin_syllabus_manager"))

    # --- Save/Update Logic ---
    if action == "save":
        subject_id = request.form.get("subject_id", type=int) # ID exists for editing
        subject_name = request.form.get("subject_name").strip()
        exam_marks = request.form.get("exam_marks", type=int)
        lab_marks = request.form.get("lab_marks", type=int)
        assignment_marks = request.form.get("assignment_marks", type=int)
        
        if not subject_name or exam_marks is None or lab_marks is None or assignment_marks is None:
            flash("All fields are required and must be numeric.", "error")
            return redirect(url_for("admin_syllabus_manager", section_id=section_id))

        total_marks = exam_marks + lab_marks + assignment_marks
        
        data = {
            "section_id": section_id,
            "subject_name": subject_name,
            "exam_marks": exam_marks,
            "lab_marks": lab_marks,
            "assignment_marks": assignment_marks,
            "total_marks": total_marks
        }

        try:
            if subject_id:
                # Update existing record
                supabase.table("section_subject_syllabi").update(data).eq("id", subject_id).execute()
                flash(f"Syllabus for {subject_name} updated successfully.", "success")
            else:
                # Insert new record
                supabase.table("section_subject_syllabi").insert(data).execute()
                flash(f"Syllabus for {subject_name} added successfully.", "success")

        except Exception as e:
            flash(f"Error saving syllabus subject. Make sure the subject name is unique: {str(e)}", "error")
            
    # --- Delete Logic ---
    elif action == "delete":
        subject_id = request.form.get("subject_id_to_delete", type=int)
        if subject_id:
             try:
                supabase.table("section_subject_syllabi").delete().eq("id", subject_id).execute()
                flash("Syllabus subject deleted successfully.", "success")
             except Exception as e:
                flash(f"Error deleting subject: {str(e)}", "error")

    return redirect(url_for("admin_syllabus_manager", section_id=section_id))


# --- MODIFIED ATTENDANCE VIEW ROUTE (Cleaned up old syllabus fetch) ---

@app.route("/section/<int:section_id>/students", methods=["GET", "POST"])
def section_students(section_id):
    if not require_admin():
        return redirect(url_for("admin_login"))

    # --- Add new student into att_students ---
    if request.method == "POST":
        # Check if the request is for adding a student 
        if "name" in request.form and "username" in request.form:
            name = request.form["name"]
            username = request.form["username"]

            supabase.table("att_students").insert({
                "section_id": section_id,
                "name": name,
                "username": username
            }).execute()

            flash("Student added successfully.", "success")
            return redirect(url_for("section_students", section_id=section_id))


    # --- Date handling ---
    selected_date = request.args.get("date", date.today().isoformat())

    # --- Get section & class info ---
    section_data = supabase.table("sections").select("*").eq("id", section_id).execute().data
    if not section_data:
         flash("Section not found.", "error")
         return redirect(url_for("admin_dashboard"))
    section = section_data[0]
    
    class_info = supabase.table("classes").select("*").eq("id", section["class_id"]).execute().data[0]
    course = supabase.table("courses").select("*").eq("id", class_info["course_id"]).execute().data[0]

    # --- Fetch students from att_students ---
    students = supabase.table("att_students").select("*").eq("section_id", section_id).order("name").execute().data

    # --- Attendance records for that date ---
    att_records = []
    if students:
        student_ids = [s["id"] for s in students]
        att_records = supabase.table("attendance").select("student_id,status") \
                        .in_("student_id", student_ids).eq("attendance_date", selected_date).execute().data

    att_map = {a["student_id"]: a["status"] for a in att_records}

    # --- Edit permission: only today or past dates ---
    can_edit = (selected_date <= date.today().isoformat())
    
    # NOTE: The fetching of the old 'current_syllabus' is now REMOVED
    
    return render_template(
        "section_students.html",
        section=section,
        class_info=class_info,
        course=course,
        students=students,
        selected_date=selected_date,
        att_map=att_map,
        can_edit=can_edit
    )

# --- KEEP THE MARK ATTENDANCE ROUTE AS IS ---
# Mark today's attendance (Present/Absent toggles)
# Mark or update attendance for a specific student and date
@app.route("/section/<int:section_id>/mark_attendance", methods=["POST"])
def mark_attendance(section_id):
    # Ensure all required functions (like require_admin, send_absence_email, etc.) are available.
    if not require_admin(): 
        return redirect(url_for("admin_login"))

    # Fetch date from form or use today's date
    selected_date = request.form.get("date", date.today().isoformat())

    if selected_date > date.today().isoformat():
        flash("Cannot mark attendance for future dates.", "error")
        # Ensure we always return
        return redirect(url_for("section_students", section_id=section_id, date=selected_date))

    updates = []
    absent_student_ids = []
    
    # 1. Collect all updates and identify absences
    for key, value in request.form.items():
        if key.startswith("student_"):
            try:
                sid = int(key.replace("student_", ""))
                if value in ("Present", "Absent", "Holiday"):
                    updates.append({
                        "student_id": sid,
                        "attendance_date": selected_date, 
                        "status": value
                    })
                    if value == "Absent":
                        absent_student_ids.append(sid)
            except ValueError:
                # Skip if student ID key is malformed
                continue

    email_count = 0
    
    # 2. Fetch necessary student details for emailing ONLY if there are absences
    if absent_student_ids:
        try:
            # A. Fetch student names/usernames from att_students
            att_students_details = (
                supabase.table("att_students").select("id, name, username")
                .in_("id", absent_student_ids).execute().data
            )
            att_student_map = {s['id']: s for s in att_students_details}
            usernames = [s['username'] for s in att_students_details if 'username' in s]
            
            # B. Fetch emails from main 'students' table
            main_students = (
                supabase.table("students").select("username, gmail")
                .in_("username", usernames).execute().data
            )
            email_map = {s['username']: s['gmail'] for s in main_students}
            
            # 3. Send emails for absent students
            for sid in absent_student_ids:
                student_info = att_student_map.get(sid)
                if student_info:
                    student_email = email_map.get(student_info.get('username'))
                    
                    # Ensure student_email is a valid recipient string before sending
                    if student_email and "@" in student_email:
                        # NOTE: send_absence_email must be defined in app.py
                        if send_absence_email(student_info['name'], student_email, selected_date):
                            email_count += 1
                            
        except Exception as e:
            flash(f"Error processing absence emails: {str(e)}", "warning")
            # We don't stop the database save just because the email failed

    
    # 4. Save all attendance records (upsert all at once)
    try:
        for row in updates:
            # Note: Supabase upserting rows one by one is common in Flask/Supabase apps, 
            # but if this causes performance issues, look into batching or RLS rules.
            supabase.table("attendance").upsert(row, on_conflict="student_id,attendance_date").execute()
        
        # Flash success message only if database save was successful
        if absent_student_ids:
            flash(f"Attendance saved. {email_count} absence notifications sent.", "success")
        else:
            flash("Attendance saved.", "success")

    except Exception as e:
        flash(f"Database Error: Could not save attendance records: {str(e)}", "error")
    
    # 5. FINAL RETURN STATEMENT (Guaranteed to be hit)
    return redirect(url_for("section_students", section_id=section_id, date=selected_date))
    
@app.route("/student/structured_syllabus")
def student_structured_syllabus():
    # 1. Check Login and Section ID
    if "user" not in session or "section_id" not in session:
        flash("Please log in to view your syllabus.", "error")
        return redirect(url_for("user_login"))

    section_id = session["section_id"]
    
    # 2. Fetch Section Name for display
    section_name = "Your Section"
    try:
        section_data = supabase.table("sections").select("name").eq("id", section_id).single().execute().data
        section_name = section_data["name"]
    except:
        pass # Use default name if not found

    # 3. Fetch Structured Syllabus Subjects
    syllabus_subjects = []
    try:
        syllabus_subjects = (
            supabase.table("section_subject_syllabi")
            .select("*")
            .eq("section_id", section_id)
            .order("subject_name")
            .execute().data
        )
    except Exception as e:
        flash(f"Error fetching syllabus: {str(e)}", "error")

    # 4. Render Template
    return render_template(
        "student_structured_syllabus.html",
        section_name=section_name,
        syllabus_subjects=syllabus_subjects
    )


# ------------- MONTHLY REPORT (PDF) -------------
from flask import Flask, render_template, request, send_file
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import calendar, datetime

from supabase import create_client

# ---------- ATTENDANCE REPORT ----------
@app.route("/attendance_report", methods=["GET", "POST"])
def attendance_report():
    if request.method == "GET":
        # Load all courses/classes/sections for dropdowns
        courses = supabase.table("courses").select("*").execute().data
        classes = supabase.table("classes").select("*").execute().data
        sections = supabase.table("sections").select("*").execute().data
        return render_template(
            "attendance_report.html",
            courses=courses,
            classes=classes,
            sections=sections,
            current_year=datetime.datetime.now().year
        )

    # ---------- POST: Generate PDF ----------
    section_id = int(request.form["section_id"])
    month = int(request.form["month"])
    year = int(request.form["year"])

    # Fetch students in this section
    students = supabase.table("att_students").select("*").eq("section_id", section_id).execute().data

    # Attendance for that month
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{calendar.monthrange(year, month)[1]}"

    attendance_records = (
        supabase.table("attendance")
        .select("student_id,attendance_date,status")
        .gte("attendance_date", start_date)
        .lte("attendance_date", end_date)
        .execute().data
    )

    # Count distinct days
    class_days = set([rec["attendance_date"] for rec in attendance_records])
    total_classes = len(class_days)

    # Build report data
    data = [["Student Name", "Total Classes", "Present", "Absent", "Percentage"]]
    for stu in students:
        stu_recs = [r for r in attendance_records if r["student_id"] == stu["id"]]
        present_count = sum(1 for r in stu_recs if r["status"] == "Present")
        absent_count = total_classes - present_count
        percent = round((present_count / total_classes) * 100, 2) if total_classes > 0 else 0
        data.append([stu["name"], total_classes, present_count, absent_count, f"{percent}%"])

    # ---------- PDF ----------
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    style = getSampleStyleSheet()
    elements = []

    title = Paragraph(
        f"Attendance Report - Section {section_id} ({calendar.month_name[month]} {year})",
        style["Title"]
    )
    elements.append(title)

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.gray),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ]))
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"attendance_report_{section_id}_{month}_{year}.pdf",
        mimetype="application/pdf"
    )

from flask_mail import Message # Ensure this import is at the top of your app.py

def send_marks_email(student_name, student_email, subject, exam_date, marks_obtained, total_marks):
    """Helper function to send marks notification email."""
    try:
        msg = Message(
            subject=f"New Exam Result: {subject} - {exam_date}",
            recipients=[student_email],
            body=f"""
Dear {student_name},

Your results for the recent exam have been published.

Subject: {subject}
Exam Date: {exam_date}
Marks Obtained: {marks_obtained}
Total Marks: {total_marks}

Percentage: {round((marks_obtained / total_marks) * 100, 2)}%

Please contact the administration if you have any questions.

Thank you,
SDC Institute Admin Team
"""
        )
        mail.send(msg)
        return True
    except Exception as e:
        print(f"ERROR sending email to {student_email}: {e}")
        return False


@app.route("/marks_entry", methods=["GET", "POST"])
def marks_entry():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    sections = supabase.table("sections").select("*").execute().data
    
    # Initialize all local variables passed to render_template
    students = []
    section_id = None
    subject_name = None
    exam_date = None
    total_marks = None
    marks_map = {} 

    if request.method == "POST":
        # Ensure form data is treated as integers where required
        try:
            section_id = int(request.form.get("section_id"))
        except (ValueError, TypeError):
            flash("Invalid section ID.", "error")
            return redirect(url_for("marks_entry"))
            
        subject_name = request.form.get("subject_name")
        exam_date = request.form.get("exam_date")
        total_marks = request.form.get("total_marks")

        # Check if marks were submitted (i.e., students data is present)
        if "marks_submitted" in request.form:
            # --- SAVE MARKS & SEND EMAIL ---
            if not total_marks or not total_marks.isdigit():
                flash("Total Marks is required and must be a number.", "error")
                students = supabase.table("att_students").select("*").eq("section_id", section_id).order("name").execute().data
            else:
                total_marks_int = int(total_marks)
                
                # Fetch full student details, including 'username' and 'gmail' for email and cross-reference
                att_students_in_section = supabase.table("att_students").select("id, name, username").eq("section_id", section_id).execute().data
                att_students_map = {s['id']: s for s in att_students_in_section}
                
                # Fetch emails from the main 'students' table using a list of usernames
                usernames = [s['username'] for s in att_students_in_section]
                main_students = supabase.table("students").select("username, gmail").in_("username", usernames).execute().data
                email_map = {s['username']: s['gmail'] for s in main_students}
                
                save_errors = False
                email_count = 0
                
                for att_student in att_students_in_section:
                    student_id = att_student['id']
                    marks_value = request.form.get(f"marks_{student_id}")
                    
                    if marks_value and marks_value.isdigit():
                        marks_obtained_int = int(marks_value)
                        
                        try:
                            # 1. SAVE MARKS
                            supabase.table("marks").upsert({
                                "student_id": student_id,
                                "subject_name": subject_name,
                                "exam_date": exam_date,
                                "marks": marks_obtained_int,
                                "total_marks": total_marks_int 
                            }, on_conflict="student_id,subject_name,exam_date").execute()
                            
                            # 2. SEND EMAIL
                            student_email = email_map.get(att_student['username'])
                            if student_email:
                                if send_marks_email(att_student['name'], student_email, subject_name, exam_date, marks_obtained_int, total_marks_int):
                                    email_count += 1
                                    
                        except Exception as e:
                            flash(f"Database error during save for {att_student['name']}. Marks were NOT saved. Details: {str(e)}", "error")
                            save_errors = True
                            break # Stop processing if a critical save error occurs

                    elif marks_value:
                         flash(f"Invalid mark entered for {att_student['name']}. Marks must be a number.", "error")
                         save_errors = True
                         break
                
                if not save_errors:
                    flash(f"Marks saved successfully! {email_count} result emails sent.", "success")
                    return redirect(url_for("marks_entry"))
                else:
                    students = att_students_in_section # Reload students list if error occurs

        else:
            # --- LOAD STUDENTS TO SHOW FORM ---
            students = supabase.table("att_students").select("*").eq("section_id", section_id).order("name").execute().data
            
            # Fetch existing marks for pre-filling the form
            marks_map = {} 
            if students:
                student_ids = [s["id"] for s in students]
                
                existing_marks_raw = supabase.table("marks").select("student_id, marks, total_marks") \
                    .in_("student_id", student_ids) \
                    .eq("subject_name", subject_name) \
                    .eq("exam_date", exam_date) \
                    .execute().data
                
                marks_map = {m["student_id"]: m["marks"] for m in existing_marks_raw}
                
                # Pre-fill total marks if found in existing records
                if existing_marks_raw and existing_marks_raw[0].get("total_marks") is not None:
                    total_marks = existing_marks_raw[0]["total_marks"]
                
    return render_template("marks_entry.html", 
                           sections=sections, 
                           students=students, 
                           section_id=section_id,
                           subject_name=subject_name,
                           exam_date=exam_date,
                           total_marks=total_marks,
                           marks_map=marks_map)


@app.route("/marks_report", methods=["GET", "POST"])
def marks_report():
    if not require_admin():
        return redirect(url_for("admin_login"))
    
    sections = supabase.table("sections").select("id, name").execute().data
    section_map = {s['id']: s['name'] for s in sections} # Map ID to Name for display
    
    # Initialize variables for GET request and report state
    students = []
    marks_map = {}
    selected_section = None
    subject_name = None
    exam_date = None
    total_marks = None
    
    # --- NEW LOGIC: Fetch ALL Unique Exams ---
    all_marks_raw = supabase.table("marks").select("student_id, subject_name, exam_date, total_marks").execute().data
    
    # 1. Get all att_students to link student_id back to section_id
    all_att_students = supabase.table("att_students").select("id, section_id").execute().data
    student_section_map = {s['id']: s['section_id'] for s in all_att_students}
    
    # 2. Client-side distinct filtering and mapping
    unique_exams = {}
    for mark in all_marks_raw:
        section_id = student_section_map.get(mark['student_id'])
        if section_id is not None:
            key = (section_id, mark['subject_name'], mark['exam_date'])
            
            if key not in unique_exams:
                unique_exams[key] = {
                    "section_id": section_id,
                    "section_name": section_map.get(section_id, 'Unknown Section'),
                    "subject_name": mark['subject_name'],
                    "exam_date": mark['exam_date'],
                    "total_marks": mark['total_marks']
                }
    
    all_exams_data = list(unique_exams.values())
    all_exams_data.sort(key=lambda x: x['exam_date'], reverse=True) # Sort by date descending
    # --- END NEW LOGIC ---

    if request.method == "POST":
        try:
            section_id = int(request.form["section_id"])
        except (ValueError, TypeError):
            flash("Invalid section selected.", "error")
            return redirect(url_for("marks_report"))
            
        subject_name = request.form["subject_name"].strip()
        exam_date = request.form["exam_date"].strip()
        selected_section = section_id

        # Get students in section
        students = supabase.table("att_students").select("*").eq("section_id", section_id).order("name").execute().data

        # Get marks for students for this exam
        # Assuming total_marks column now exists in the 'marks' table
        marks = supabase.table("marks").select("student_id, marks, total_marks") \
            .eq("subject_name", subject_name) \
            .eq("exam_date", exam_date) \
            .execute().data
        
        # Process marks and extract total_marks
        marks_map = {m["student_id"]: m["marks"] for m in marks}
        
        if marks and marks[0].get("total_marks") is not None:
            total_marks = marks[0]["total_marks"]

        return render_template("marks_report.html", 
                               sections=sections, 
                               students=students, 
                               marks_map=marks_map, 
                               selected_section=selected_section, 
                               subject_name=subject_name, 
                               exam_date=exam_date,
                               total_marks=total_marks,
                               all_exams_data=all_exams_data) # Pass the list of all exams

    return render_template("marks_report.html", 
                           sections=sections, 
                           students=students, 
                           marks_map=marks_map, 
                           selected_section=selected_section, 
                           subject_name=subject_name, 
                           exam_date=exam_date, 
                           total_marks=total_marks,
                           all_exams_data=all_exams_data) # Pass the list of all exams


@app.route("/student/marks")
def student_marks_view():
    # Ensure the user is logged in and their attendance profile is active
    if "user" not in session or "att_student_id" not in session:
        flash("Please log in to view your marks report.", "error")
        return redirect(url_for("user_login"))

    att_student_id = session["att_student_id"]

    # Fetch all marks records for the student, sorted by the exam date
    marks_records = (
        supabase.table("marks")
        .select("subject_name, exam_date, marks, total_marks")
        .eq("student_id", att_student_id)
        .order("exam_date", desc=True)
        .execute().data
    )

    total_exams = len(marks_records)
    
    return render_template(
        "student_marks.html",
        marks_records=marks_records,
        total_exams=total_exams
    )


# Helper function (Ensure this is in your file, likely near other helpers)
def get_file_extension(filename):
    if '.' in filename:
        return filename.rsplit('.', 1)[1].lower()
    return ''

# API Route to fetch subjects for a selected section via AJAX/Fetch
@app.route("/api/syllabus_subjects/<int:section_id>", methods=["GET"])
def get_syllabus_subjects(section_id):
    if not require_admin():
        return jsonify({"error": "Unauthorized"}), 401 

    subjects = (
        supabase.table("section_subject_syllabi")
        .select("id, subject_name")
        .eq("section_id", section_id)
        .order("subject_name")
        .execute().data
    )
    return jsonify(subjects)


def get_file_extension(filename):
    if '.' in filename:
        return filename.rsplit('.', 1)[1].lower()
    return '' 


@app.route("/admin/add_note", methods=["GET", "POST"])
def add_note_logic():
    if not require_admin():
        # Redirect to Admin login if not authenticated
        return redirect(url_for("admin_login"))

    # Fetch all sections to populate the first dropdown
    sections_response = supabase.table("sections").select("id, name").order("name").execute().data
    
    if request.method == "GET":
        # Display the form
        return render_template("add_note_form.html", sections=sections_response)

    if request.method == "POST":
        # Get form data
        syllabus_subject_id = request.form.get("syllabus_subject_id", type=int)
        title = request.form.get("title")
        note_type = request.form.get("note_type")
        uploaded_by = session["admin"] # Confirmed correct key for Admin identifier

        content_url = None
        content_text = None
        
        if not syllabus_subject_id:
            flash("Subject must be selected from the syllabus.", "error")
            return redirect(request.url)

        try:
            # Fetch the parent section_id for Storage folder organization
            syllabus_data = supabase.table("section_subject_syllabi").select("section_id").eq("id", syllabus_subject_id).single().execute().data
            section_id = syllabus_data["section_id"]
            
            if note_type in ["PDF", "Image"]:
                file = request.files.get("file_upload")
               
                if not file or file.filename == "":
                    flash("No file selected for file upload.", "error")
                    return redirect(request.url)

                # 1. Secure filename and create unique path
                original_filename = secure_filename(file.filename)
                file_extension = get_file_extension(original_filename)
                unique_filename = f"{uuid.uuid4()}.{file_extension}"
                storage_path = f"notes/{section_id}/{unique_filename}"
                
                # 2. Upload file to Supabase Storage
                file_bytes = file.read() 
                
                # --- FIX: The Supabase client raises an exception on failure, eliminating the need for db_response.get("error").
                supabase.storage.from_("subject-notes").upload(
                    path=storage_path,
                    file=file_bytes,
                    file_options={"content-type": file.mimetype, "upsert": "true"}
                )
                
                # 3. Get the public URL
                content_url = (
                    supabase.storage
                    .from_("subject-notes")
                    .get_public_url(storage_path)
                )
  
            elif note_type in ["Link", "Text"]:
                content_input = request.form.get("content_input")
                if not content_input:
                    flash(f"Content cannot be empty for {note_type} notes.", "error")
                    return redirect(request.url)

                if note_type == "Link":
                    content_url = content_input
                else: # Text
                    content_text = content_input
     
            # 4. Insert note metadata into the database
            data_to_insert = {
                "syllabus_subject_id": syllabus_subject_id, # Link to the syllabus entry
                "title": title,
                "note_type": note_type,
                "content_url": content_url,
                "content_text": content_text,
                "uploaded_by": uploaded_by
            }
            
            # --- FIX: The Supabase client raises an exception on failure, eliminating the need for db_response.get("error").
            supabase.table("subject_notes").insert(data_to_insert).execute()
            
            flash("Note added successfully to the section's syllabus!", "success")
            return redirect(url_for("admin_dashboard"))

        except Exception as e:
            # Catch any Supabase API exceptions (including RLS, storage, or bad data)
            flash(f"An error occurred: {e}", "error")
            return redirect(request.url)

    return redirect(url_for("admin_dashboard"))


@app.route("/student/notes/<int:syllabus_subject_id>")
def student_notes_view(syllabus_subject_id):
    # Student/User login check
    if "user" not in session:
        flash("Please log in to view notes.", "error")
        return redirect(url_for("user_login"))

    # Fetch all notes for the specific syllabus entry
    notes = (
        supabase.table("subject_notes")
        .select("*")
        .eq("syllabus_subject_id", syllabus_subject_id)
        .order("created_at", desc=True)
        .execute().data
    )
    
    # Fetch the subject name for the header
    subject_data = (
        supabase.table("section_subject_syllabi")
        .select("subject_name")
        .eq("id", syllabus_subject_id)
        .single().execute().data
    )
    
    subject_name = subject_data.get("subject_name", "Subject")

    # This requires a new template: 'templates/student_notes_view.html'
    return render_template("student_notes_view.html", 
                           notes=notes, 
                           subject_name=subject_name)





if __name__ == "__main__":
    # Render sets the PORT environment variable. We use 5000 as a local fallback.
    port = int(os.environ.get("PORT", 5000))
    
    # In development, you can use debug=True. For Render, the production server (Gunicorn) 
    # will be used, and debug should generally be False in a live setting.
    app.run(host='0.0.0.0', port=port, debug=True)

