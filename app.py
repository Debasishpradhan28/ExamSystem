import os
from dotenv import load_dotenv
import uuid
import PyPDF2
import re
from flask_talisman import Talisman
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_user, current_user, logout_user, login_required
from models import db, User, Department, TeacherCode, Exam, Question,Submission,ExamResult # Your models file

app = Flask(__name__)
app.config['SECRET_KEY'] = 'vssut_secure_exam_2026_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///exam_portal.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.jinja_env.globals.update(datetime_now=datetime.now)
load_dotenv()
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
Talisman(app, content_security_policy=None, force_https=False)
# Initialize Extensions
db.init_app(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- CORE GATEWAY ROUTES ---

@app.route("/")
@app.route("/home")
def home():
    return render_template('home.html')

@app.route("/login", defaults={'role': 'student'}, methods=['GET', 'POST'])
@app.route("/login/<role>", methods=['GET', 'POST'])
def login(role):
    if current_user.is_authenticated:
        return redirect(url_for(f'{current_user.role}_dashboard'))
    
    themes = {'admin': 'danger', 'teacher': 'primary', 'student': 'success'}
    theme_color = themes.get(role, 'success')

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and user.role == role and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            flash(f'Logged in as {user.role.capitalize()}', 'success')
            return redirect(url_for(f'{user.role}_dashboard'))
        else:
            flash(f'Invalid {role.capitalize()} credentials.', 'danger')
            
    return render_template('login.html', role=role, theme_color=theme_color)

@app.route("/register/<role>", methods=['GET', 'POST'])
def register(role):
    themes = {'admin': 'danger', 'teacher': 'primary', 'student': 'success'}
    theme_color = themes.get(role, 'success')
    departments = Department.query.all()

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        dept_id = request.form.get('dept_id')
        
        if role == 'teacher':
            auth_code = request.form.get('auth_code')
            code_entry = TeacherCode.query.filter_by(code=auth_code, is_used=False).first()
            if not code_entry:
                flash('Invalid or used Teacher Registration Code!', 'danger')
                return redirect(url_for('register', role=role))
            code_entry.is_used = True

        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'warning')
            return redirect(url_for('login', role=role))

        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(username=username, email=email, password=hashed_pw, role=role, dept_id=dept_id)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Account created! Please login.', 'success')
        return redirect(url_for('login', role=role))

    return render_template('register.html', role=role, theme_color=theme_color, departments=departments)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))

# --- ADMIN DASHBOARD & FUNCTIONS ---

@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    if current_user.role != 'admin': abort(403)
    return render_template('admin_dashboard.html', departments=Department.query.all(), codes=TeacherCode.query.all())

@app.route("/admin/add_dept", methods=['POST'])
@login_required
def add_dept():
    if current_user.role != 'admin': abort(403)
    name = request.form.get('dept_name')
    if name:
        db.session.add(Department(name=name))
        db.session.commit()
        flash(f'Dept {name} created.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route("/admin/generate_code", methods=['POST'])
@login_required
def generate_code():
    if current_user.role != 'admin': abort(403)
    new_code = str(uuid.uuid4())[:8].upper()
    db.session.add(TeacherCode(code=new_code))
    db.session.commit()
    flash(f'New Code: {new_code}', 'info')
    return redirect(url_for('admin_dashboard'))

# --- TEACHER DASHBOARD & EXAM CREATION ---

@app.route("/teacher/dashboard")
@login_required
def teacher_dashboard():
    if current_user.role != 'teacher': abort(403)
    exams = Exam.query.filter_by(dept_id=current_user.dept_id).all()
    return render_template('teacher_dashboard.html', exams=exams)

@app.route("/exam/create", methods=['GET', 'POST'])
@login_required
def create_exam():
    if current_user.role != 'teacher': abort(403)
    if request.method == 'POST':
        start_str = request.form.get('start_time') # e.g., '2026-03-15T10:00'
        end_str = request.form.get('end_time')
        
        start_dt = datetime.strptime(start_str, '%Y-%m-%dT%H:%M')
        end_dt = datetime.strptime(end_str, '%Y-%m-%dT%H:%M')
        new_exam = Exam(title=request.form.get('title'),start_time=start_dt,
            end_time=end_dt,duration=request.form.get('duration'),
                        dept_id=current_user.dept_id, teacher_id=current_user.id)
        db.session.add(new_exam)
        db.session.flush()

        q_texts = request.form.getlist('q_text[]')
        q_types = request.form.getlist('q_type[]')
        
        for i in range(len(q_texts)):
            q = Question(exam_id=new_exam.id, question_text=q_texts[i], q_type=q_types[i])
            if q_types[i] == 'mcq':
                q.opt_a = request.form.get(f'opt_a_{i}'); q.opt_b = request.form.get(f'opt_b_{i}')
                q.opt_c = request.form.get(f'opt_c_{i}'); q.opt_d = request.form.get(f'opt_d_{i}')
                q.correct_ans = request.form.get(f'correct_{i}')
            db.session.add(q)
        
        db.session.commit()
        flash('Exam Published!', 'success')
        return redirect(url_for('teacher_dashboard'))
    return render_template('create_exam.html')

@app.route("/exam/upload", methods=['GET', 'POST'])
@login_required
def upload_paper():
    if current_user.role != 'teacher': 
        abort(403)
    
    if request.method == 'POST':
        file = request.files.get('paper')
        title = request.form.get('title')
        duration = request.form.get('duration')
        start_str = request.form.get('start_time')
        end_str = request.form.get('end_time')

        if not file or not title:
            flash("Please provide a title and a PDF file.", "warning")
            return redirect(request.url)

        # 1. Convert times
        start_dt = datetime.strptime(start_str, '%Y-%m-%dT%H:%M')
        end_dt = datetime.strptime(end_str, '%Y-%m-%dT%H:%M')

        # 2. Extract Text from PDF
        try:
            pdf_reader = PyPDF2.PdfReader(file)
            full_text = ""
            for page in pdf_reader.pages:
                full_text += page.extract_text()
        except Exception as e:
            flash(f"Error reading PDF: {str(e)}", "danger")
            return redirect(request.url)

        # 3. Create the Exam Object first
        new_exam = Exam(
            title=title, 
            duration=duration, 
            start_time=start_dt,
            end_time=end_dt,
            dept_id=current_user.dept_id, 
            teacher_id=current_user.id
        )
        db.session.add(new_exam)
        db.session.flush() # Gets us new_exam.id

        # 4. Improved Regex for VSSUT Subjective Papers
        # Detects Q1, Q2, a), b), A), B) and marks in [brackets]
        subjective_pattern = r'([Q][0-9]+|[a-zA-Z][)])\s*(.*?)\s*(?:\[([0-9+x*]+)\]|(?=[Q][0-9]+|[a-zA-Z][)]|$))'
        
        try:
            matches = re.findall(subjective_pattern, full_text, re.DOTALL)
        except re.error as e:
            flash(f"Regex Error: {str(e)}", "danger")
            return redirect(url_for('teacher_dashboard'))
        
        count = 0
        for match in matches:
            q_label = match[0]
            q_content = match[1].strip()
            q_marks_str = match[2]
            
            # Skip noise like university headers if they are too short
            if len(q_content) < 10:
                continue

            # Calculate marks weightage
            try:
                # Basic cleaning to turn '4+4' into 8 or '2x3' into 6
                q_weight = eval(q_marks_str.replace('x', '*')) if q_marks_str else 2
            except:
                q_weight = 2 # Default fallback

            new_q = Question(
                exam_id=new_exam.id,
                question_text=f"{q_label} {q_content}",
                q_type='long', # Standard for VSSUT Mid-Sem/End-Sem
                marks=int(q_weight)
            )
            db.session.add(new_q)
            count += 1
        
        db.session.commit()
        flash(f"AI parsed {count} questions from the PDF. Please verify them below.", "success")
        
        # Redirect to the Review Page so the teacher can fix any parsing errors
        return redirect(url_for('review_exam', exam_id=new_exam.id))

    return render_template('create_exam_ai.html')

@app.route("/exam/review/<int:exam_id>", methods=['GET', 'POST'])
@login_required
def review_exam(exam_id):
    if current_user.role != 'teacher': abort(403)
    exam = Exam.query.get_or_404(exam_id)
    
    if request.method == 'POST':
        # Update all questions with the teacher's edits
        question_ids = request.form.getlist('q_id[]')
        q_texts = request.form.getlist('q_text[]')
        q_marks = request.form.getlist('q_marks[]')
        
        for i in range(len(question_ids)):
            q = Question.query.get(question_ids[i])
            if q:
                q.question_text = q_texts[i]
                q.marks = int(q_marks[i])
        
        db.session.commit()
        flash("Exam finalized and saved!", "success")
        return redirect(url_for('teacher_dashboard'))

    return render_template('review_exam.html', exam=exam)

@app.route("/teacher/grade/<int:exam_id>")
@login_required
def grade_list(exam_id):
    if current_user.role != 'teacher': abort(403)
    # Get all students who submitted this exam
    results = ExamResult.query.filter_by(exam_id=exam_id).all()
    return render_template('grade_list.html', results=results, exam_id=exam_id)

@app.route("/teacher/grade_student/<int:exam_id>/<int:student_id>", methods=['GET', 'POST'])
@login_required
def grade_student(exam_id, student_id):
    # 1. Authorization Check
    if current_user.role != 'teacher': 
        abort(403)
    
    # 2. Data Fetching
    student = User.query.get_or_404(student_id)
    answers = Submission.query.filter_by(exam_id=exam_id, student_id=student_id).all()
    result = ExamResult.query.filter_by(exam_id=exam_id, student_id=student_id).first()

    if not result:
        flash("No submission record found for this student.", "danger")
        return redirect(url_for('grade_list', exam_id=exam_id))

    # 3. Handling the Grading Submission
    if request.method == 'POST':
        total_new_score = 0
        for ans in answers:
            # Get the marks given by teacher from the form
            new_marks = request.form.get(f'marks_{ans.id}')
            if new_marks:
                ans.marks_awarded = int(new_marks)
                total_new_score += int(new_marks)
        
        # Update the overall Result table
        result.total_score = total_new_score
        result.status = "Completed"
        db.session.commit()
        
        flash(f"Grading completed for {student.username}. Total Marks: {total_new_score}", "success")
        return redirect(url_for('grade_list', exam_id=exam_id))

    # 4. FIX: Pass 'result' so the template can show tab-switch logs
    return render_template('grade_student.html', answers=answers, student=student, result=result)

@app.route("/exam/publish/<int:exam_id>", methods=['POST'])
@login_required
def publish_exam_results(exam_id):
    if current_user.role != 'teacher': 
        abort(403)
    
    exam = Exam.query.get_or_404(exam_id)
    
    # Security: Ensure only the creator can publish
    if exam.teacher_id != current_user.id:
        abort(403)

    exam.is_published = True
    db.session.commit()
    
    flash(f"Results for '{exam.title}' have been published to students!", "success")
    return redirect(url_for('teacher_dashboard'))

# --- STUDENT DASHBOARD ---

@app.route("/student/dashboard")
@login_required
def student_dashboard():
    if current_user.role != 'student': abort(403)
    exams = Exam.query.filter_by(dept_id=current_user.dept_id).all()
    return render_template('student_dashboard.html', exams=exams)

@app.route("/exam/attempt/<int:exam_id>", methods=['GET', 'POST'])
@login_required
def start_exam(exam_id):
    if current_user.role != 'student': abort(403)
    existing_result = ExamResult.query.filter_by(student_id=current_user.id, exam_id=exam_id).first()
    if existing_result:
        flash("You have already attempted this exam. Multiple attempts are not allowed.", "warning")
        return redirect(url_for('student_dashboard'))
    now=datetime.now()
    exam = Exam.query.get_or_404(exam_id)
    if now < exam.start_time:
        diff = (exam.start_time - now).seconds
        if diff > 5: # If it's more than 5 seconds early, block it
            flash(f"Exam starts at {exam.start_time.strftime('%H:%M')}. Please wait.", "info")
            return redirect(url_for('student_dashboard'))

    if now > exam.end_time:
        flash("The exam window has ended.", "danger")
        return redirect(url_for('student_dashboard'))
    
    total_marks = sum(q.marks for q in exam.questions)
    if request.method == 'POST':
        score = 0
        questions = Question.query.filter_by(exam_id=exam_id).all()
        
        for q in questions:
            student_ans = request.form.get(f'q_{q.id}')
            marks = 0
            
            # Auto-grade MCQs
            if q.q_type == 'mcq':
                if student_ans == q.correct_ans:
                    marks = q.marks
                    score += marks
            
            # Save the individual answer
            sub = Submission(
                student_id=current_user.id,
                exam_id=exam_id,
                question_id=q.id,
                answer_text=student_ans if student_ans else "",
                marks_awarded=marks
            )
            db.session.add(sub)
        
        
        has_subjective = any(q.q_type in ['short', 'long'] for q in questions)
        res = ExamResult(
            student_id=current_user.id,
            exam_id=exam_id,
            total_score=score,
            status="Completed" if not has_subjective else "Pending Review"
        )
        db.session.add(res)
        db.session.commit()
        
        flash("Exam submitted successfully!", "success")
        return redirect(url_for('student_dashboard'))

    return render_template('exam_room.html', exam=exam)
@app.route("/student/results")
@login_required
def student_results():
    if current_user.role != 'student': 
        abort(403)
    
    # Fetch all results for this student
    my_results = ExamResult.query.filter_by(student_id=current_user.id).all()
    
    return render_template('student_results.html', results=my_results)
# --- DB INITIALIZATION ---
# --- DB INITIALIZATION & PRODUCTION CONFIG ---
import os

# 1. Ensure the 'instance' folder exists for SQLite
if not os.path.exists(app.instance_path):
    os.makedirs(app.instance_path)

# 2. Initialize Database (This runs on Render startup)
with app.app_context():
    db.create_all()
    if not User.query.filter_by(role='admin').first():
        # Using a hashed password for your VSSUT Admin
        hp = bcrypt.generate_password_hash('admin123').decode('utf-8')
        db.session.add(User(username='MainAdmin', email='admin@vssut.ac.in', password=hp, role='admin'))
        
        depts = ['Computer Science', 'Electrical Eng', 'Mechanical Eng']
        for d in depts:
            if not Department.query.filter_by(name=d).first():
                db.session.add(Department(name=d))
        db.session.commit()

# 3. Handle Port for Render/Gunicorn
if __name__ == '__main__':
    # Local development settings
    app.run(debug=True, host='127.0.0.1', port=5000)