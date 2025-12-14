from flask import Flask, request, jsonify
import sqlite3
import datetime
import sys
import os
from enum import Enum
from dataclasses import dataclass
from typing import List

app = Flask(__name__)

# ==========================================
# DATABASE MANAGER (Persistence Layer)
# ==========================================

# Get the correct path for database file (works in both exe and script mode)
if getattr(sys, 'frozen', False):
    # Running as compiled exe
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Running as script
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_FILE = os.path.join(BASE_DIR, "university.db")

def init_db():
    """Initializes the database tables if they don't exist."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Students Table
    c.execute('''CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE
                )''')
    
    # Sections (Classes) Table
    c.execute('''CREATE TABLE IF NOT EXISTS sections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    start_date TEXT,
                    end_date TEXT,
                    schedule_days TEXT
                )''')
    
    # Enrollments Table (Many-to-Many relationship)
    c.execute('''CREATE TABLE IF NOT EXISTS enrollments (
                    student_id INTEGER,
                    section_id INTEGER,
                    PRIMARY KEY (student_id, section_id),
                    FOREIGN KEY(student_id) REFERENCES students(id),
                    FOREIGN KEY(section_id) REFERENCES sections(id)
                )''')
    
    # Attendance Logs Table
    c.execute('''CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    section_id INTEGER,
                    student_id INTEGER,
                    date TEXT,
                    status TEXT,
                    UNIQUE(section_id, student_id, date)
                )''')
    
    conn.commit()
    conn.close()

def run_query(query, params=(), fetch_all=False, fetch_one=False):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(query, params)
    if fetch_all:
        data = [dict(row) for row in c.fetchall()]
        conn.close()
        return data
    elif fetch_one:
        row = c.fetchone()
        conn.close()
        return dict(row) if row else None
    conn.commit()
    conn.close()
    return None

# ==========================================
# BUSINESS LOGIC
# ==========================================

class Day(Enum):
    MON = 0; TUE = 1; WED = 2; THU = 3; FRI = 4; SAT = 5; SUN = 6

@dataclass
class SectionObj:
    id: int
    name: str
    start_date: datetime.date
    end_date: datetime.date
    schedule_days: List[int]

    def get_valid_sessions_up_to_today(self):
        """Generates a list of all class dates that have happened so far."""
        sessions = []
        current = self.start_date
        today = datetime.date.today()
        
        while current <= self.end_date and current <= today:
            if current.weekday() in self.schedule_days:
                sessions.append(current)
            current += datetime.timedelta(days=1)
        return sessions

    def get_all_future_sessions(self):
        """Generates dates for the drop-down menu."""
        sessions = []
        current = self.start_date
        while current <= self.end_date:
            if current.weekday() in self.schedule_days:
                sessions.append(current)
            current += datetime.timedelta(days=1)
        return sessions

def calculate_student_score(student_id, section_id):
    # 1. Get Section Details
    row = run_query("SELECT * FROM sections WHERE id = ?", (section_id,), fetch_one=True)
    if not row:
        return 100.0
    
    days_list = [int(d) for d in row['schedule_days'].split(',')]
    section = SectionObj(
        row['id'], row['name'], 
        datetime.datetime.strptime(row['start_date'], "%Y-%m-%d").date(),
        datetime.datetime.strptime(row['end_date'], "%Y-%m-%d").date(),
        days_list
    )

    # 2. Get Valid Past Sessions
    past_sessions = section.get_valid_sessions_up_to_today()
    if not past_sessions:
        return 100.0

    # 3. Get Recorded Attendance from DB
    logs = run_query("SELECT date, status FROM attendance WHERE section_id = ? AND student_id = ?", 
                     (section_id, student_id), fetch_all=True)
    log_map = {row['date']: row['status'] for row in logs}

    # 4. Calculate Score
    total_valid = 0
    points = 0.0

    for date_obj in past_sessions:
        date_str = date_obj.strftime("%Y-%m-%d")
        status_str = log_map.get(date_str, "ABSENT")
        
        if status_str == "EXCUSED":
            continue
        
        total_valid += 1
        
        if status_str == "PRESENT":
            points += 1.0
        elif status_str == "LATE":
            points += 0.5
    
    if total_valid == 0:
        return 100.0
    return (points / total_valid) * 100

# ==========================================
# HTML TEMPLATE (Embedded)
# ==========================================

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UniPlanner Pro - Global Attendance System</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
            padding: 30px;
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }

        .header h1 {
            font-size: 3rem;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
        }

        .header p {
            font-size: 1.2rem;
            opacity: 0.9;
        }

        .nav-tabs {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }

        .nav-tab {
            padding: 15px 30px;
            background: rgba(255, 255, 255, 0.2);
            color: white;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            font-size: 1rem;
            font-weight: 600;
            transition: all 0.3s ease;
            backdrop-filter: blur(10px);
        }

        .nav-tab:hover {
            background: rgba(255, 255, 255, 0.3);
            transform: translateY(-2px);
        }

        .nav-tab.active {
            background: white;
            color: #667eea;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        }

        .view {
            display: none;
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
            animation: fadeIn 0.5s ease;
        }

        .view.active {
            display: block;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .section-title {
            font-size: 2rem;
            margin-bottom: 25px;
            color: #667eea;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .form-group {
            margin-bottom: 25px;
        }

        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #555;
        }

        .form-control {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 1rem;
            transition: all 0.3s ease;
        }

        .form-control:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }

        .checkbox-group {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            margin-top: 10px;
        }

        .checkbox-item {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .checkbox-item input[type="checkbox"] {
            width: 20px;
            height: 20px;
            cursor: pointer;
        }

        .btn {
            padding: 12px 30px;
            border: none;
            border-radius: 10px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }

        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }

        .btn:active {
            transform: translateY(0);
        }

        .alert {
            padding: 15px 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            animation: slideDown 0.3s ease;
        }

        @keyframes slideDown {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .alert-success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }

        .alert-error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }

        .alert-info {
            background: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }

        .card {
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease;
        }

        .card:hover {
            transform: translateY(-5px);
        }

        .card h3 {
            color: #667eea;
            margin-bottom: 10px;
        }

        .attendance-grid {
            display: grid;
            gap: 15px;
            margin-top: 20px;
        }

        .attendance-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 10px;
            border: 2px solid #e0e0e0;
        }

        .attendance-item .student-name {
            font-weight: 600;
            color: #333;
        }

        .status-radio-group {
            display: flex;
            gap: 10px;
        }

        .status-radio {
            display: none;
        }

        .status-label {
            padding: 8px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 0.9rem;
            font-weight: 600;
        }

        .status-label:hover {
            border-color: #667eea;
        }

        .status-radio:checked + .status-label {
            background: #667eea;
            color: white;
            border-color: #667eea;
        }

        .status-label.present { border-color: #28a745; }
        .status-radio:checked + .status-label.present { background: #28a745; border-color: #28a745; }
        .status-label.late { border-color: #ffc107; }
        .status-radio:checked + .status-label.late { background: #ffc107; border-color: #ffc107; }
        .status-label.absent { border-color: #dc3545; }
        .status-radio:checked + .status-label.absent { background: #dc3545; border-color: #dc3545; }
        .status-label.excused { border-color: #6c757d; }
        .status-radio:checked + .status-label.excused { background: #6c757d; border-color: #6c757d; }

        .table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }

        .table th,
        .table td {
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid #e0e0e0;
        }

        .table th {
            background: #667eea;
            color: white;
            font-weight: 600;
        }

        .table tr:hover {
            background: #f8f9fa;
        }

        .badge {
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
        }

        .badge-success {
            background: #d4edda;
            color: #155724;
        }

        .badge-warning {
            background: #fff3cd;
            color: #856404;
        }

        .select-wrapper {
            position: relative;
        }

        .select-wrapper select {
            appearance: none;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23333' d='M6 9L1 4h10z'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: right 15px center;
            padding-right: 40px;
        }

        .loading {
            text-align: center;
            padding: 40px;
            color: #667eea;
            font-size: 1.2rem;
        }

        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #999;
        }

        .empty-state-icon {
            font-size: 4rem;
            margin-bottom: 20px;
        }

        @media (max-width: 768px) {
            .header h1 {
                font-size: 2rem;
            }

            .nav-tabs {
                flex-direction: column;
            }

            .view {
                padding: 20px;
            }

            .status-radio-group {
                flex-wrap: wrap;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎓 UniPlanner Pro</h1>
            <p>Global Attendance Management System</p>
        </div>

        <div class="nav-tabs">
            <button class="nav-tab active" onclick="showView('admin')">🛠️ Admin Dashboard</button>
            <button class="nav-tab" onclick="showView('professor')">👨‍🏫 Professor View</button>
            <button class="nav-tab" onclick="showView('student')">🧑‍🎓 Student Portal</button>
        </div>

        <!-- Admin Dashboard -->
        <div id="admin" class="view active">
            <h2 class="section-title">🛠️ Admin Dashboard</h2>
            
            <div id="admin-alerts"></div>

            <div class="grid">
                <div class="card">
                    <h3>Create Course</h3>
                    <form id="create-course-form" onsubmit="createCourse(event)">
                        <div class="form-group">
                            <label>Course Name</label>
                            <input type="text" class="form-control" name="name" placeholder="e.g., CS101" required>
                        </div>
                        <div class="form-group">
                            <label>Start Date</label>
                            <input type="date" class="form-control" name="start_date" required>
                        </div>
                        <div class="form-group">
                            <label>End Date</label>
                            <input type="date" class="form-control" name="end_date" required>
                        </div>
                        <div class="form-group">
                            <label>Schedule Days</label>
                            <div class="checkbox-group">
                                <div class="checkbox-item"><input type="checkbox" name="days" value="MON"> <label>Monday</label></div>
                                <div class="checkbox-item"><input type="checkbox" name="days" value="TUE"> <label>Tuesday</label></div>
                                <div class="checkbox-item"><input type="checkbox" name="days" value="WED"> <label>Wednesday</label></div>
                                <div class="checkbox-item"><input type="checkbox" name="days" value="THU"> <label>Thursday</label></div>
                                <div class="checkbox-item"><input type="checkbox" name="days" value="FRI"> <label>Friday</label></div>
                                <div class="checkbox-item"><input type="checkbox" name="days" value="SAT"> <label>Saturday</label></div>
                                <div class="checkbox-item"><input type="checkbox" name="days" value="SUN"> <label>Sunday</label></div>
                            </div>
                        </div>
                        <button type="submit" class="btn">Create Course</button>
                    </form>
                </div>

                <div class="card">
                    <h3>Register Student</h3>
                    <form id="register-student-form" onsubmit="registerStudent(event)">
                        <div class="form-group">
                            <label>Student Name</label>
                            <input type="text" class="form-control" name="name" required>
                        </div>
                        <div class="form-group">
                            <label>Email</label>
                            <input type="email" class="form-control" name="email" required>
                        </div>
                        <button type="submit" class="btn">Register Student</button>
                    </form>
                </div>
            </div>
        </div>

        <!-- Professor View -->
        <div id="professor" class="view">
            <h2 class="section-title">👨‍🏫 Professor Dashboard</h2>
            
            <div id="professor-alerts"></div>

            <div class="form-group">
                <label>Select Course</label>
                <div class="select-wrapper">
                    <select class="form-control" id="professor-course-select" onchange="loadProfessorData()">
                        <option value="">Loading courses...</option>
                    </select>
                </div>
            </div>

            <div id="professor-content" style="display: none;">
                <div class="card" style="margin-top: 20px;">
                    <h3>Manage Enrollment</h3>
                    <div class="form-group">
                        <label>Select Student to Enroll</label>
                        <div class="select-wrapper">
                            <select class="form-control" id="enroll-student-select"></select>
                        </div>
                        <button class="btn" style="margin-top: 15px;" onclick="enrollStudent()">Enroll Student</button>
                    </div>
                </div>

                <div class="card" style="margin-top: 20px;">
                    <h3>📝 Mark Attendance</h3>
                    <div class="form-group">
                        <label>Select Class Session</label>
                        <div class="select-wrapper">
                            <select class="form-control" id="attendance-date-select" onchange="loadAttendanceForm()"></select>
                        </div>
                    </div>
                    <div id="attendance-form-container"></div>
                </div>
            </div>
        </div>

        <!-- Student Portal -->
        <div id="student" class="view">
            <h2 class="section-title">🧑‍🎓 Student Portal</h2>
            
            <div class="form-group">
                <label>Identify Yourself</label>
                <div class="select-wrapper">
                    <select class="form-control" id="student-select" onchange="loadStudentReport()">
                        <option value="">Loading students...</option>
                    </select>
                </div>
            </div>

            <div id="student-report-container"></div>
        </div>
    </div>

    <script>
        // View Management
        function showView(viewName) {
            document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
            document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
            document.getElementById(viewName).classList.add('active');
            event.target.classList.add('active');

            // Load data when switching views
            if (viewName === 'professor') {
                loadCourses('professor-course-select');
            } else if (viewName === 'student') {
                loadStudents('student-select');
            }
        }

        // API Helper
        async function apiCall(url, options = {}) {
            try {
                const response = await fetch(url, {
                    headers: {
                        'Content-Type': 'application/json',
                        ...options.headers
                    },
                    ...options
                });
                return await response.json();
            } catch (error) {
                console.error('API Error:', error);
                return { success: false, message: 'Network error occurred' };
            }
        }

        // Alert Helper
        function showAlert(containerId, message, type = 'success') {
            const container = document.getElementById(containerId);
            const alert = document.createElement('div');
            alert.className = `alert alert-${type}`;
            alert.textContent = message;
            container.innerHTML = '';
            container.appendChild(alert);
            setTimeout(() => {
                alert.remove();
            }, 5000);
        }

        // Admin Functions
        async function createCourse(event) {
            event.preventDefault();
            const form = event.target;
            const formData = new FormData(form);
            const days = formData.getAll('days');
            
            if (days.length === 0) {
                showAlert('admin-alerts', 'Please select at least one schedule day', 'error');
                return;
            }

            const data = {
                name: formData.get('name'),
                start_date: formData.get('start_date'),
                end_date: formData.get('end_date'),
                schedule_days: days
            };

            const result = await apiCall('/api/sections', {
                method: 'POST',
                body: JSON.stringify(data)
            });

            if (result.success) {
                showAlert('admin-alerts', result.message, 'success');
                form.reset();
            } else {
                showAlert('admin-alerts', result.message || 'Error creating course', 'error');
            }
        }

        async function registerStudent(event) {
            event.preventDefault();
            const form = event.target;
            const formData = new FormData(form);

            const data = {
                name: formData.get('name'),
                email: formData.get('email')
            };

            const result = await apiCall('/api/students', {
                method: 'POST',
                body: JSON.stringify(data)
            });

            if (result.success) {
                showAlert('admin-alerts', result.message, 'success');
                form.reset();
            } else {
                showAlert('admin-alerts', result.message || 'Error registering student', 'error');
            }
        }

        // Load Courses
        async function loadCourses(selectId) {
            const select = document.getElementById(selectId);
            select.innerHTML = '<option value="">Loading...</option>';
            
            const courses = await apiCall('/api/sections');
            select.innerHTML = '<option value="">Select a course...</option>';
            
            courses.forEach(course => {
                const option = document.createElement('option');
                option.value = course.id;
                option.textContent = course.name;
                select.appendChild(option);
            });
        }

        // Load Students
        async function loadStudents(selectId) {
            const select = document.getElementById(selectId);
            select.innerHTML = '<option value="">Loading...</option>';
            
            const students = await apiCall('/api/students');
            select.innerHTML = '<option value="">Select a student...</option>';
            
            students.forEach(student => {
                const option = document.createElement('option');
                option.value = student.id;
                option.textContent = `${student.name} (${student.email || 'No email'})`;
                select.appendChild(option);
            });
        }

        // Professor Functions
        async function loadProfessorData() {
            const courseId = document.getElementById('professor-course-select').value;
            if (!courseId) {
                document.getElementById('professor-content').style.display = 'none';
                return;
            }

            document.getElementById('professor-content').style.display = 'block';

            // Load students for enrollment
            const students = await apiCall('/api/students');
            const enrollSelect = document.getElementById('enroll-student-select');
            enrollSelect.innerHTML = '<option value="">Select student...</option>';
            students.forEach(student => {
                const option = document.createElement('option');
                option.value = student.id;
                option.textContent = `${student.name} (${student.email || 'No email'})`;
                enrollSelect.appendChild(option);
            });

            // Load dates for attendance
            const dates = await apiCall(`/api/sections/${courseId}/dates`);
            const dateSelect = document.getElementById('attendance-date-select');
            dateSelect.innerHTML = '<option value="">Select date...</option>';
            dates.forEach(date => {
                const option = document.createElement('option');
                option.value = date;
                option.textContent = new Date(date).toLocaleDateString();
                dateSelect.appendChild(option);
            });

            loadAttendanceForm();
        }

        async function enrollStudent() {
            const courseId = document.getElementById('professor-course-select').value;
            const studentId = document.getElementById('enroll-student-select').value;

            if (!courseId || !studentId) {
                showAlert('professor-alerts', 'Please select both course and student', 'error');
                return;
            }

            const result = await apiCall('/api/enrollments', {
                method: 'POST',
                body: JSON.stringify({
                    student_id: parseInt(studentId),
                    section_id: parseInt(courseId)
                })
            });

            if (result.success) {
                showAlert('professor-alerts', result.message, 'success');
                loadProfessorData();
            } else {
                showAlert('professor-alerts', result.message || 'Error enrolling student', 'error');
            }
        }

        async function loadAttendanceForm() {
            const courseId = document.getElementById('professor-course-select').value;
            const date = document.getElementById('attendance-date-select').value;

            if (!courseId || !date) {
                document.getElementById('attendance-form-container').innerHTML = '';
                return;
            }

            // Load enrolled students
            const students = await apiCall(`/api/sections/${courseId}/students`);
            
            // Load existing attendance
            const existingAttendance = await apiCall(`/api/attendance?section_id=${courseId}&date=${date}`);

            let html = `<div class="attendance-grid">`;
            
            students.forEach(student => {
                const existingStatus = existingAttendance[student.id] || 'PRESENT';
                html += `
                    <div class="attendance-item">
                        <div class="student-name">${student.name}</div>
                        <div class="status-radio-group">
                            <input type="radio" name="attendance_${student.id}" value="PRESENT" id="present_${student.id}" 
                                   class="status-radio" ${existingStatus === 'PRESENT' ? 'checked' : ''}>
                            <label for="present_${student.id}" class="status-label present">Present</label>
                            
                            <input type="radio" name="attendance_${student.id}" value="LATE" id="late_${student.id}" 
                                   class="status-radio" ${existingStatus === 'LATE' ? 'checked' : ''}>
                            <label for="late_${student.id}" class="status-label late">Late</label>
                            
                            <input type="radio" name="attendance_${student.id}" value="ABSENT" id="absent_${student.id}" 
                                   class="status-radio" ${existingStatus === 'ABSENT' ? 'checked' : ''}>
                            <label for="absent_${student.id}" class="status-label absent">Absent</label>
                            
                            <input type="radio" name="attendance_${student.id}" value="EXCUSED" id="excused_${student.id}" 
                                   class="status-radio" ${existingStatus === 'EXCUSED' ? 'checked' : ''}>
                            <label for="excused_${student.id}" class="status-label excused">Excused</label>
                        </div>
                    </div>
                `;
            });

            html += `</div>
                <button class="btn" style="margin-top: 20px; width: 100%;" onclick="saveAttendance()">Save Attendance Records</button>
            `;

            document.getElementById('attendance-form-container').innerHTML = html;
        }

        async function saveAttendance() {
            const courseId = document.getElementById('professor-course-select').value;
            const date = document.getElementById('attendance-date-select').value;

            if (!courseId || !date) {
                showAlert('professor-alerts', 'Please select course and date', 'error');
                return;
            }

            const students = await apiCall(`/api/sections/${courseId}/students`);
            const records = {};

            students.forEach(student => {
                const selected = document.querySelector(`input[name="attendance_${student.id}"]:checked`);
                if (selected) {
                    records[student.id] = selected.value;
                }
            });

            const result = await apiCall('/api/attendance', {
                method: 'POST',
                body: JSON.stringify({
                    section_id: parseInt(courseId),
                    date: date,
                    records: records
                })
            });

            if (result.success) {
                showAlert('professor-alerts', result.message, 'success');
                loadAttendanceForm();
            } else {
                showAlert('professor-alerts', result.message || 'Error saving attendance', 'error');
            }
        }

        // Student Functions
        async function loadStudentReport() {
            const studentId = document.getElementById('student-select').value;
            if (!studentId) {
                document.getElementById('student-report-container').innerHTML = '';
                return;
            }

            const classes = await apiCall(`/api/students/${studentId}/classes`);

            if (classes.length === 0) {
                document.getElementById('student-report-container').innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">📚</div>
                        <p>You are not enrolled in any classes.</p>
                    </div>
                `;
                return;
            }

            let html = `
                <h3 style="margin: 30px 0 20px 0;">Progress Report</h3>
                <table class="table">
                    <thead>
                        <tr>
                            <th>Course</th>
                            <th>Attendance</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
            `;

            classes.forEach(cls => {
                const statusClass = cls.status === 'Good' ? 'badge-success' : 'badge-warning';
                html += `
                    <tr>
                        <td><strong>${cls.course}</strong></td>
                        <td>${cls.attendance}%</td>
                        <td><span class="badge ${statusClass}">${cls.status === 'Good' ? '🟢 Good' : '🔴 Warning'}</span></td>
                    </tr>
                `;
            });

            html += `
                    </tbody>
                </table>
                <p style="margin-top: 20px; color: #666; font-size: 0.9rem;">
                    Calculation: (Present + 0.5 × Late) / (Total Past Sessions - Excused)
                </p>
            `;

            document.getElementById('student-report-container').innerHTML = html;
        }

        // Initialize on page load
        window.addEventListener('DOMContentLoaded', () => {
            loadCourses('professor-course-select');
            loadStudents('student-select');
        });
    </script>
</body>
</html>'''

# ==========================================
# ROUTES
# ==========================================

@app.route('/')
def index():
    return HTML_TEMPLATE

# Admin Routes
@app.route('/api/sections', methods=['GET'])
def get_sections():
    sections = run_query("SELECT * FROM sections", fetch_all=True)
    return jsonify(sections)

@app.route('/api/sections', methods=['POST'])
def create_section():
    data = request.json
    day_map = {"MON":0, "TUE":1, "WED":2, "THU":3, "FRI":4, "SAT":5, "SUN":6}
    day_ints = ",".join([str(day_map[d]) for d in data['schedule_days']])
    
    run_query("INSERT INTO sections (name, start_date, end_date, schedule_days) VALUES (?, ?, ?, ?)",
              (data['name'], data['start_date'], data['end_date'], day_ints))
    return jsonify({"success": True, "message": f"Course '{data['name']}' created successfully!"})

@app.route('/api/students', methods=['GET'])
def get_students():
    students = run_query("SELECT * FROM students", fetch_all=True)
    return jsonify(students)

@app.route('/api/students', methods=['POST'])
def create_student():
    data = request.json
    try:
        run_query("INSERT INTO students (name, email) VALUES (?, ?)", (data['name'], data['email']))
        return jsonify({"success": True, "message": f"Student '{data['name']}' registered!"})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "message": "Email already exists."}), 400

# Professor Routes
@app.route('/api/sections/<int:section_id>/students', methods=['GET'])
def get_enrolled_students(section_id):
    enrolled = run_query('''
        SELECT s.id, s.name, s.email FROM students s
        JOIN enrollments e ON s.id = e.student_id
        WHERE e.section_id = ?
    ''', (section_id,), fetch_all=True)
    return jsonify(enrolled)

@app.route('/api/enrollments', methods=['POST'])
def enroll_student():
    data = request.json
    try:
        run_query("INSERT INTO enrollments (student_id, section_id) VALUES (?, ?)", 
                  (data['student_id'], data['section_id']))
        return jsonify({"success": True, "message": "Student enrolled successfully!"})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "message": "Student already enrolled."}), 400

@app.route('/api/sections/<int:section_id>/dates', methods=['GET'])
def get_section_dates(section_id):
    sec_row = run_query("SELECT * FROM sections WHERE id=?", (section_id,), fetch_one=True)
    if not sec_row:
        return jsonify([])
    
    days_list = [int(d) for d in sec_row['schedule_days'].split(',')]
    section_obj = SectionObj(
        sec_row['id'], sec_row['name'], 
        datetime.datetime.strptime(sec_row['start_date'], "%Y-%m-%d").date(),
        datetime.datetime.strptime(sec_row['end_date'], "%Y-%m-%d").date(),
        days_list
    )
    
    valid_dates = section_obj.get_all_future_sessions()
    date_options = [d.strftime("%Y-%m-%d") for d in valid_dates]
    return jsonify(date_options)

@app.route('/api/attendance', methods=['GET'])
def get_attendance():
    section_id = request.args.get('section_id')
    date = request.args.get('date')
    
    if section_id and date:
        logs = run_query("SELECT student_id, status FROM attendance WHERE section_id=? AND date=?", 
                        (section_id, date), fetch_all=True)
        return jsonify({row['student_id']: row['status'] for row in logs})
    return jsonify({})

@app.route('/api/attendance', methods=['POST'])
def save_attendance():
    data = request.json
    section_id = data['section_id']
    date = data['date']
    records = data['records']
    
    for student_id, status in records.items():
        run_query("INSERT OR REPLACE INTO attendance (section_id, student_id, date, status) VALUES (?, ?, ?, ?)",
                  (section_id, int(student_id), date, status))
    
    return jsonify({"success": True, "message": "Attendance saved successfully!"})

# Student Routes
@app.route('/api/students/<int:student_id>/classes', methods=['GET'])
def get_student_classes(student_id):
    classes = run_query('''
        SELECT sec.id, sec.name, sec.start_date, sec.end_date 
        FROM sections sec
        JOIN enrollments e ON sec.id = e.section_id
        WHERE e.student_id = ?
    ''', (student_id,), fetch_all=True)
        
    report_data = []
    for cls in classes:
        score = calculate_student_score(student_id, cls['id'])
        report_data.append({
            "course": cls['name'],
            "attendance": round(score, 1),
            "status": "Good" if score >= 75 else "Warning"
        })
    
    return jsonify(report_data)

if __name__ == '__main__':
    init_db()
    print("=" * 60)
    print("UniPlanner Pro - Global Attendance System")
    print("=" * 60)
    print("Server starting on http://0.0.0.0:5000")
    print("Accessible globally at http://YOUR_IP:5000")
    print("=" * 60)
    # Set debug=False when running as exe, True when running as script
    debug_mode = not getattr(sys, 'frozen', False)
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)
