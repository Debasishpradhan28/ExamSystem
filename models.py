from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

# 1. Departments Table
class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    # Relationship: One Dept has many Users and Exams
    users = db.relationship('User', backref='department', lazy=True)
    exams = db.relationship('Exam', backref='department', lazy=True)

# 2. Users Table (Admin, Teacher, Student)
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    role = db.Column(db.String(10), nullable=False) # 'admin', 'teacher', 'student'
    dept_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=True)

# 3. Teacher Registration Codes (Admin Generated)
class TeacherCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    is_used = db.Column(db.Boolean, default=False)

# 4. Exam Table
class Exam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=False)
    duration = db.Column(db.Integer, nullable=False) # In minutes
    dept_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    questions = db.relationship('Question', backref='exam', lazy=True, cascade="all, delete-orphan")
    is_published = db.Column(db.Boolean, default=False)

# 5. Question Table (Handles MCQ, Short, Long)
class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False)
    q_type = db.Column(db.String(10), nullable=False) # 'mcq', 'short', 'long'
    question_text = db.Column(db.Text, nullable=False)
    
    # For MCQs (Stored as strings, logic handles them as list)
    opt_a = db.Column(db.String(200))
    opt_b = db.Column(db.String(200))
    opt_c = db.Column(db.String(200))
    opt_d = db.Column(db.String(200))
    correct_ans = db.Column(db.String(200)) # Stores 'A', 'B', etc. or keywords
    marks = db.Column(db.Integer, default=1)

class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    answer_text = db.Column(db.Text, nullable=False)
    marks_awarded = db.Column(db.Integer, default=0)
    question = db.relationship('Question', backref='submissions')
    student = db.relationship('User', backref='submissions')

class ExamResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False)
    total_score = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="Pending")
    student = db.relationship('User', backref='results')
    exam = db.relationship('Exam', backref='results')
    cheating_report = db.Column(db.Text, default="No issues detected.")
    tab_switches = db.Column(db.Integer, default=0)