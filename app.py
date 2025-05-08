from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, send_from_directory  # Added send_from_directory import
import sqlite3
import json
import os
import mimetypes
import random
import string
import csv
import datetime
from datetime import datetime
from io import StringIO
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key'  

# Initialize SQLite database and create tables if they don't exist
def init_db():
    conn = None
    try:
        conn = sqlite3.connect('ccs_sitin.db', timeout=30)
        conn.execute('PRAGMA journal_mode=WAL')  # Use Write-Ahead Logging
        conn.execute('PRAGMA foreign_keys = ON')
        c = conn.cursor()

        # Create users table for admin and student accounts
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                idno TEXT UNIQUE,
                username TEXT UNIQUE,
                firstname TEXT,
                middlename TEXT,
                lastname TEXT,
                password TEXT,
                role TEXT,
                course TEXT,
                year_level TEXT,
                contact TEXT,
                email TEXT,
                created_at TEXT,
                remaining_sessions INTEGER DEFAULT 10,
                points INTEGER DEFAULT 0,
                profile_image TEXT
            )
        ''')

        # Create laboratories table for lab information
        c.execute('''
            CREATE TABLE IF NOT EXISTS laboratories (
                id INTEGER PRIMARY KEY,
                lab_number TEXT UNIQUE,
                lab_name TEXT,
                status TEXT DEFAULT 'Available',
                description TEXT
            )
        ''')

        # Create computers table for computer management
        c.execute('''
            CREATE TABLE IF NOT EXISTS computers (
                id INTEGER PRIMARY KEY,
                lab_number TEXT,
                pc_number TEXT,
                status TEXT DEFAULT 'Available',
                description TEXT,
                student_id TEXT,
                FOREIGN KEY (lab_number) REFERENCES laboratories (lab_number),
                UNIQUE(lab_number, pc_number)
            )
        ''')

        # Create sit-ins table for tracking student lab usage
        c.execute('''
            CREATE TABLE IF NOT EXISTS sitins (
                id INTEGER PRIMARY KEY,
                student_id TEXT,
                lab_number TEXT,
                pc_number TEXT,
                subject TEXT,
                professor TEXT,
                purpose TEXT,
                login_date TEXT,
                login_time TEXT,
                logout_time TEXT,
                timestamp TEXT,
                status TEXT DEFAULT 'active',
                feedback TEXT,
                rating INTEGER,
                FOREIGN KEY (student_id) REFERENCES users (idno),
                FOREIGN KEY (lab_number) REFERENCES laboratories (lab_number)
            )
        ''')
        
        # Create reservations table
        c.execute('''
            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY,
                student_id TEXT,
                laboratory_number TEXT,
                computer_number TEXT,
                reservation_date TEXT,
                reservation_time TEXT,
                time_out TEXT,
                purpose TEXT,
                status TEXT DEFAULT 'Pending',
                created_at TEXT,
                timeout_approved INTEGER DEFAULT 0,
                FOREIGN KEY (student_id) REFERENCES users (idno),
                FOREIGN KEY (laboratory_number) REFERENCES laboratories (lab_number)
            )
        ''')

        # Check if timeout_approved column exists in reservations table
        c.execute("PRAGMA table_info(reservations)")
        columns = [column[1] for column in c.fetchall()]
        if 'timeout_approved' not in columns:
            c.execute("ALTER TABLE reservations ADD COLUMN timeout_approved INTEGER DEFAULT 0")
            conn.commit()
            
        # Create a table for announcements
        c.execute('''
            CREATE TABLE IF NOT EXISTS announcement (
                id INTEGER PRIMARY KEY,
                title TEXT,
                content TEXT,
                created_at TEXT,
                created_by TEXT,
                updated_at TEXT
            )
        ''')

        # Create feedback table
        c.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY,
                user_id TEXT,
                message TEXT,
                created_at TEXT,
                status TEXT DEFAULT 'unread',
                admin_reply TEXT,
                replied_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (idno)
            )
        ''')
        
        # Create lab schedules table
        c.execute('''
            CREATE TABLE IF NOT EXISTS lab_schedules (
                id INTEGER PRIMARY KEY,
                laboratory INTEGER,
                course TEXT,
                subject TEXT,
                professor TEXT,
                day_of_week TEXT,
                start_time TEXT,
                end_time TEXT,
                created_at TEXT
            )
        ''')
        
        # Create resource materials table
        c.execute('''
            CREATE TABLE IF NOT EXISTS resource_materials (
                id INTEGER PRIMARY KEY,
                title TEXT,
                description TEXT,
                file_path TEXT,
                file_name TEXT,
                file_type TEXT,
                file_size TEXT,
                uploaded_by TEXT,
                created_at TEXT
            )
        ''')

        # Create points_history table if not exists
        c.execute('''
            CREATE TABLE IF NOT EXISTS points_history (
                id INTEGER PRIMARY KEY,
                student_id TEXT,
                points INTEGER,
                source TEXT DEFAULT 'System',
                reason TEXT,
                description TEXT,
                date TEXT,
                created_at TEXT,
                FOREIGN KEY (student_id) REFERENCES users (idno)
            )
        ''')

        conn.commit()
    except Exception as e:
        print(f"Error initializing database: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

# SQLite database connection
def get_db_connection():
    conn = sqlite3.connect('students.db', timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")  # Use Write-Ahead Logging
    conn.row_factory = sqlite3.Row
    
    try:
        # Auto-fix is_admin column if missing
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if "is_admin" not in columns:
            print("is_admin column missing, adding it...")
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
                # Make sure admin has is_admin = 1
                cursor.execute('UPDATE users SET is_admin = 1 WHERE username = "admin"')
                conn.commit()
                print("Added is_admin column successfully")
            except Exception as e:
                print(f"Error adding is_admin column: {str(e)}")
        
        # Check if the points column exists in users table
        if "points" not in columns:
            print("points column missing from users table, adding it...")
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN points INTEGER DEFAULT 0")
                conn.commit()
                print("Added points column to users table successfully")
            except Exception as e:
                print(f"Error adding points column: {str(e)}")
        
        # Check if the login_date column exists in sitins table
        cursor.execute("PRAGMA table_info(sitins)")
        sitins_columns = [column[1] for column in cursor.fetchall()]
        
        if "login_date" not in sitins_columns:
            print("login_date column missing from sitins table, adding it...")
            try:
                cursor.execute("ALTER TABLE sitins ADD COLUMN login_date TEXT DEFAULT (date('now', 'localtime'))")
                conn.commit()
                print("Added login_date column to sitins table successfully")
            except Exception as e:
                print(f"Error adding login_date column: {str(e)}")
    except Exception as e:
        print(f"Error in get_db_connection: {str(e)}")
    
    return conn

# Route to display the registration form
@app.route('/register', methods=['GET'])
def register_page():
    return render_template('registration.html')  

# Route to handle the form submission for registration
@app.route('/register', methods=['POST'])
def register():
    if request.method == 'POST':
        # Get the form data
        idno = request.form['idno']
        lastname = request.form['lastname']
        firstname = request.form['firstname']
        middlename = request.form['middlename']
        course = request.form['course']
        year_level = request.form['year_level']
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']

        # Connect to the database and insert the data
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(''' 
            INSERT INTO users (idno, lastname, firstname, middlename, course, year_level, email, username, password, remaining_sessions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 30)
        ''', (idno, lastname, firstname, middlename, course, year_level, email, username, password))

        conn.commit()
        conn.close()

        return redirect(url_for('login'))  

# Route for login page (this handles both GET and POST methods)
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Get the login data from the form
        username = request.form['username']
        password = request.form['password']

        # Check if it's admin login
        if username == 'admin' and password == 'admin':
            session['admin'] = True 
            return redirect(url_for('admin_dashboard'))

        # Check credentials in the database for student login
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['user_id'] = user['idno']  
            return redirect(url_for('user_dashboard'))  
        else:
            return render_template('login.html', error="Invalid credentials. Please try again.")

    return render_template('login.html')  

# Route for admin dashboard
@app.route('/admin_dashboard')
def admin_dashboard():
    # Check if admin is in session
    if 'admin' not in session:
        flash('You must be logged in as admin to access the admin dashboard')
        return redirect(url_for('login'))
    
    try:
        connection = sqlite3.connect('students.db')
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        
        # Count students registered
        cursor.execute('SELECT COUNT(*) FROM users')
        students_count = cursor.fetchone()[0]
        
        # Count active sit-ins
        cursor.execute('SELECT COUNT(*) FROM sitins WHERE logout_time IS NULL')
        active_sitin_count = cursor.fetchone()[0]
        
        # Count total sit-ins
        cursor.execute('SELECT COUNT(*) FROM sitins')
        total_sitin_count = cursor.fetchone()[0]
        
        # Get programming language distribution
        cursor.execute('''
            SELECT purpose, COUNT(*) as count 
            FROM sitins 
            GROUP BY purpose 
            ORDER BY count DESC
        ''')
        purpose_stats = cursor.fetchall()
        purpose_labels = []
        purpose_data = []
        
        for purpose, count in purpose_stats:
            purpose_labels.append(purpose)
            purpose_data.append(count)
        
        # Fill with zeros if no data
        if not purpose_labels:
            purpose_labels = ['C Programming', 'C# Programming', 'Java Programming', '.NET Programming', 'PHP Programming', 'Python Programming']
            purpose_data = [0, 0, 0, 0, 0, 0]
        
        # Get announcements
        try:
            # Try to get from the announcement table
            cursor.execute('''
                SELECT id, title, content, created_at, created_by 
                FROM announcement 
                ORDER BY created_at DESC
            ''')
            announcements = cursor.fetchall()
        except Exception as e:
            print(f"Error fetching announcements: {e}")
            # If the announcement table doesn't exist or there was an error, return an empty list
            announcements = []
        
        # Check if active_sitin_count exists for the navbar
        cursor.execute('SELECT COUNT(*) FROM sitins WHERE logout_time IS NULL')
        sitin_count = cursor.fetchone()[0]
        
        connection.close()
        
        return render_template('admin_dashboard.html', 
                              sitin_count=sitin_count,
                              students_count=students_count,
                              active_sitin_count=active_sitin_count,
                              total_sitin_count=total_sitin_count,
                              purpose_labels=json.dumps(purpose_labels),
                              purpose_data=json.dumps(purpose_data),
                              announcements=announcements)
    
    except Exception as e:
        print(f"Error fetching dashboard data: {e}")
        if 'connection' in locals():
            connection.close()
        return render_template('admin_dashboard.html', 
                            sitin_count=0, 
                            active_sitin_count=0, 
                            students_count=0,
                            total_sitin_count=0,
                            purpose_labels=json.dumps([]),
                            purpose_data=json.dumps([]),
                            announcements=[],
                            error=str(e))

# Route for user dashboard page (student dashboard)
@app.route('/user_dashboard')
def user_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))  

    # Get user data from the database
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE idno = ?', (user_id,))
    user = cursor.fetchone()

    # Fetch announcements for the dashboard
    try:
        conn.row_factory = sqlite3.Row  # Ensure row factory is set
        cursor = conn.cursor()  # Get a new cursor with the row factory applied
        cursor.execute('''
            SELECT id, title, content, created_at, created_by 
            FROM announcement 
            ORDER BY created_at DESC
            LIMIT 5
        ''')
        announcements = cursor.fetchall()
    except Exception as e:
        print(f"Error fetching announcements for user dashboard: {e}")
        announcements = []

    conn.close()

    if user:
        return render_template('user_dashboard.html', user=user, announcements=announcements)  

    return redirect(url_for('login')) 

# Route for reservation page
@app.route('/reservation', methods=['GET', 'POST'])
def reservation():
    if 'user_id' not in session:
        flash('Please log in first', 'danger')
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Check if computer_number column exists in reservations table
        cursor.execute("PRAGMA table_info(reservations)")
        columns = [column[1] for column in cursor.fetchall()]

        # Add computer_number column if it doesn't exist
        if 'computer_number' not in columns:
            cursor.execute("ALTER TABLE reservations ADD COLUMN computer_number INTEGER")
            conn.commit()
            
        # Add time_out column if it doesn't exist
        if 'time_out' not in columns:
            cursor.execute("ALTER TABLE reservations ADD COLUMN time_out TEXT")
            conn.commit()
            
        # Add completed_at column if it doesn't exist
        if 'completed_at' not in columns:
            cursor.execute("ALTER TABLE reservations ADD COLUMN completed_at TEXT")
            conn.commit()
    except Exception as e:
        print(f"Error updating reservations table: {str(e)}")
        # If error occurs (like column already exists), continue anyway
        pass
    
    # Get user's remaining session time
    cursor.execute('SELECT remaining_sessions FROM users WHERE idno = ?', (session['user_id'],))
    user = cursor.fetchone()
    remaining_sessions = user['remaining_sessions']
    
    # Get all laboratories and their available computers
    labs = []
    lab_numbers = ['524', '526', '528', '530', '542', '544', '517']
    
    for lab_number in lab_numbers:
        # Get computers for this laboratory
        cursor.execute('''
            SELECT c.*, u.firstname, u.lastname 
            FROM computers c
            LEFT JOIN users u ON c.student_id = u.idno
            WHERE c.lab_number = ?
            ORDER BY c.pc_number
        ''', (lab_number,))
        computers = cursor.fetchall()
        
        # Count available computers
        available_count = sum(1 for computer in computers if computer['status'] == 'Available')
        
        labs.append({
            'number': lab_number,
            'available_computers': available_count,
            'computers': computers
        })
    
    if request.method == 'POST':
        student_id = session['user_id']
        laboratory = request.form.get('laboratory')
        computer = request.form.get('computer')
        purpose = request.form.get('purpose')
        date = request.form.get('date')
        time_in = request.form.get('time_in')
        
        # Validate inputs
        if not all([laboratory, computer, purpose, date, time_in]):
            flash('Please fill in all fields', 'danger')
            return redirect(url_for('reservation'))
        
        # Validate time_in (must be between 8 AM and 8 PM)
        try:
            hours_in = int(time_in.split(':')[0])
            if hours_in < 8 or hours_in >= 20:
                flash('Please select a time between 8:00 AM and 8:00 PM for Time-In', 'danger')
                return redirect(url_for('reservation'))
        except:
            flash('Invalid time format for Time-In', 'danger')
            return redirect(url_for('reservation'))
            
        # Check if the computer is still available
        cursor.execute('''
            SELECT * FROM computers 
            WHERE lab_number = ? AND pc_number = ? AND status = 'Available'
        ''', (laboratory, computer))
        
        if not cursor.fetchone():
            flash('Sorry, this computer is no longer available', 'danger')
            return redirect(url_for('reservation'))
        
        # Check if user already has a reservation for this date and time
        cursor.execute('''
            SELECT * FROM reservations 
            WHERE student_id = ? AND reservation_date = ? AND reservation_time = ? AND status = 'Pending'
        ''', (student_id, date, time_in))
        
        if cursor.fetchone():
            flash('You already have a reservation for this time slot', 'warning')
            return redirect(url_for('reservation'))
        
        # Create the reservation
        try:
            cursor.execute('''
                INSERT INTO reservations (
                    student_id, laboratory_number, computer_number, reservation_date, 
                    reservation_time, time_out, purpose, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ''', (student_id, laboratory, computer, date, time_in, time_in, purpose, 'Pending'))
            
            conn.commit()
            flash('Reservation submitted successfully', 'success')
            return redirect(url_for('user_dashboard'))  
        except Exception as e:
            conn.rollback()
            flash(f'Error creating reservation: {str(e)}', 'danger')
            return redirect(url_for('reservation'))
    
    conn.close()
    return render_template('reservation.html', 
                         labs=labs,
                         remaining_sessions=remaining_sessions)

@app.route('/update_user', methods=['POST'])
def update_user():
    if 'user_id' not in session:
        return redirect(url_for('login'))  

    # Get form data
    user_id = session['user_id']
    
    # Get the fields from the form, making them optional with defaults
    course = request.form.get('course', '')
    year_level = request.form.get('year_level', '')
    
    # Connect to database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get current user data
    cursor.execute('SELECT * FROM users WHERE idno = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        flash('User not found', 'danger')
        return redirect(url_for('profile'))
    
    # Update only the fields that were submitted
    update_fields = []
    params = []
    
    if course:
        update_fields.append('course = ?')
        params.append(course)
    
    if year_level:
        update_fields.append('year_level = ?')
        params.append(year_level)
    
    # Only perform update if there are fields to update
    if update_fields:
        # Add user_id as the last parameter
        params.append(user_id)
        
        # Build and execute the SQL query
        update_query = f'UPDATE users SET {", ".join(update_fields)} WHERE idno = ?'
        cursor.execute(update_query, params)
        conn.commit()
    
    conn.close()
    flash('Profile updated successfully', 'success')
    return redirect(url_for('profile'))

# Route to delete student from admin dashboard
@app.route('/delete_student/<idno>', methods=['GET', 'POST'])
def delete_student(idno):
    if 'admin' not in session:
        if request.method == 'POST':
            return jsonify({"error": "Unauthorized access"}), 403
        return redirect(url_for('login'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First delete related records from sitins table
        cursor.execute('DELETE FROM sitins WHERE student_id = ?', (idno,))
        
        # Then delete the user
        cursor.execute('DELETE FROM users WHERE idno = ?', (idno,))
        
        conn.commit()
        conn.close()

        if request.method == 'POST':
            return jsonify({"success": True, "message": "Student deleted successfully"})
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        print(f"Error deleting student: {str(e)}")
        if request.method == 'POST':
            return jsonify({"error": str(e)}), 500
        return redirect(url_for('admin_dashboard'))

# Route to update student information
@app.route('/update_student', methods=['POST'])
def update_student():
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized access'}), 403
    
    # Check if the request is JSON (API request) or form data
    if request.is_json:
        data = request.get_json()
        idno = data.get('idno')
        firstname = data.get('firstname')
        lastname = data.get('lastname')
        course = data.get('course')
        year_level = data.get('year_level')
        remaining_sessions = data.get('remaining_sessions')
        
        if not idno:
            return jsonify({'error': 'Student ID is required'}), 400
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Build the update query dynamically based on provided fields
            fields_to_update = []
            params = []
            
            if firstname:
                fields_to_update.append('firstname = ?')
                params.append(firstname)
            
            if lastname:
                fields_to_update.append('lastname = ?')
                params.append(lastname)
            
            if course:
                fields_to_update.append('course = ?')
                params.append(course)
            
            if year_level:
                fields_to_update.append('year_level = ?')
                params.append(year_level)
                
            if remaining_sessions is not None:
                fields_to_update.append('remaining_sessions = ?')
                params.append(remaining_sessions)
            
            # Add student_id to params
            params.append(idno)
            
            if fields_to_update:
                update_query = f"UPDATE users SET {', '.join(fields_to_update)} WHERE idno = ?"
                cursor.execute(update_query, params)
                conn.commit()
            
            conn.close()
            
            return jsonify({'success': True, 'message': 'Student updated successfully'})
            
        except Exception as e:
            print(f"Error updating student: {str(e)}")
            return jsonify({'error': str(e)}), 500
    else:
        # This is a form submission
        return jsonify({'error': 'Form submissions not supported, use JSON API'}), 400

# Route to change student password
@app.route('/change_password', methods=['POST'])
def change_password():
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized access'}), 403
    
    # Check if the request is JSON
    if request.is_json:
        data = request.get_json()
        idno = data.get('idno') or data.get('student_id')
        password = data.get('password') or data.get('new_password')
        
        if not all([idno, password]):
            return jsonify({'error': 'Missing required fields'}), 400
            
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Consider using password hashing in production
            # For now, store as is to maintain compatibility
            cursor.execute('UPDATE users SET password = ? WHERE idno = ?', 
                          (password, idno))
            
            conn.commit()
            conn.close()
            
            return jsonify({'success': True, 'message': 'Password changed successfully'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    else:
        # This is a form submission
        return jsonify({'error': 'Form submissions not supported, use JSON API'}), 400

# Route for students (to fetch data via AJAX)
@app.route('/view_students')
def view_students():
    if 'admin' not in session:
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Count active sit-ins for the navbar badge
        cursor.execute('SELECT COUNT(*) as count FROM sitins WHERE logout_time IS NULL')
        active_count = cursor.fetchone()['count']
        
        # Try to use is_admin column if it exists, otherwise filter by username
        try:
            cursor.execute('''
                SELECT idno, username, firstname, lastname, course, year_level, remaining_sessions
                FROM users
                WHERE is_admin = 0
                ORDER BY lastname
            ''')
        except sqlite3.OperationalError:
            # If is_admin column doesn't exist, exclude admin by username
            cursor.execute('''
                SELECT idno, username, firstname, lastname, course, year_level, remaining_sessions
                FROM users
                WHERE username != 'admin'
                ORDER BY lastname
            ''')
        
        students_raw = cursor.fetchall()
        # Convert to list of dictionaries for the template
        students = []
        for student in students_raw:
            students.append(dict(student))
        
        conn.close()
        
        # If AJAX request, return JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(students)
        
        # Flash a message if no students are found
        if not students:
            flash('No students found in the database. Add some students to get started!', 'warning')
        
        # Otherwise render template
        return render_template('view_students.html', students=students, active_count=active_count)
        
    except Exception as e:
        print(f"Error fetching students: {str(e)}")
        flash(f'Error fetching students: {str(e)}', 'danger')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify([])
        return render_template('view_students.html', students=[], error=str(e), active_count=0)

# Route to get all students for AJAX requests
@app.route('/students')
def get_students():
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized access'}), 403
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Try to use is_admin column if it exists, otherwise filter by username
        try:
            cursor.execute('''
                SELECT idno, username, firstname, lastname, email, course, year_level, remaining_sessions
                FROM users
                WHERE is_admin = 0
                ORDER BY lastname
            ''')
        except sqlite3.OperationalError:
            # If is_admin column doesn't exist, exclude admin by username
            cursor.execute('''
                SELECT idno, username, firstname, lastname, email, course, year_level, remaining_sessions
                FROM users
                WHERE username != 'admin'
                ORDER BY lastname
            ''')
        
        students = cursor.fetchall()
        conn.close()
        
        # Convert to list of dictionaries
        students_list = []
        for student in students:
            student_dict = {key: student[key] for key in student.keys()}
            students_list.append(student_dict)
            
        return jsonify(students_list)
        
    except Exception as e:
        print(f"Error fetching students: {str(e)}")
        return jsonify([]), 500

@app.route('/search_student', methods=['GET'])
def search_student():
    student_id = request.args.get('idno')  # Get the student ID from query parameters
    print(f"Searching for student with ID: {student_id}")

    if not student_id:
        return jsonify({'error': 'No student ID provided'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Query the database for the student using the provided ID
        cursor.execute("SELECT * FROM users WHERE idno = ?", (student_id,))
        student = cursor.fetchone()

        if not student:
            print(f"No student found with ID: {student_id}")
            return jsonify({'error': 'Student not found'}), 404

        # Convert row to dict for easier access
        student_dict = dict(student)
        print(f"Student found: {student_dict['firstname']} {student_dict['lastname']}")

        # Get the laboratory number from reservations if available
        cursor.execute("SELECT laboratory_number FROM reservations WHERE student_id = ? ORDER BY id DESC LIMIT 1", (student_dict['idno'],))
        reservation = cursor.fetchone()
        lab_number = reservation['laboratory_number'] if reservation else 'N/A'
        
        conn.close()

        # Return the student details in JSON format
        student_data = {
            'idno': student_dict['idno'],
            'username': student_dict['username'],
            'firstname': student_dict['firstname'],
            'lastname': student_dict['lastname'],
            'course': student_dict['course'],
            'year_level': student_dict['year_level'],
            'laboratory_number': lab_number
        }
        return jsonify(student_data)
    
    except Exception as e:
        print(f"Error in search_student: {str(e)}")
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@app.route('/submit_sitin', methods=['POST'])
def submit_sitin():
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized access'}), 401
    
    try:
        # Get and validate input data
        data = request.get_json()
        print(f"Received data: {data}")
        
        # Check if data is None (invalid JSON)
        if data is None:
            print("Invalid JSON data received")
            return jsonify({'error': 'Invalid request data format'}), 400
        
        # Extract fields with fallbacks to empty strings
        student_id = data.get('student_id', '').strip()
        lab_number = data.get('lab_number', '').strip()
        purpose = data.get('purpose', '').strip()
        
        print(f"Extracted fields: student_id={student_id}, lab_number={lab_number}, purpose={purpose}")
        
        # Validate all required fields are present
        if not student_id:
            return jsonify({'error': 'Student ID is required'}), 400
        if not lab_number:
            return jsonify({'error': 'Lab number is required'}), 400
        if not purpose:
            return jsonify({'error': 'Purpose is required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if student exists
        cursor.execute('SELECT * FROM users WHERE idno = ?', (student_id,))
        student = cursor.fetchone()
        
        if not student:
            conn.close()
            return jsonify({'error': 'Student not found'}), 404
        
        # Check if student has remaining sessions
        if student['remaining_sessions'] <= 0:
            conn.close()
            return jsonify({'error': 'Student has no remaining sessions'}), 400
            
        # Check if student has an active sit-in
        cursor.execute('''
            SELECT * FROM sitins 
            WHERE student_id = ? AND logout_time IS NULL
        ''', (student_id,))
        
        active_sitin = cursor.fetchone()
        if active_sitin:
            conn.close()
            return jsonify({'error': 'Student already has an active sit-in session'}), 400
        
        # Get current time for login_time
        now = datetime.now()
        login_time = now.strftime('%H:%M:%S')
        login_date = now.strftime('%Y-%m-%d')
        
        # Create the sit-in record
        cursor.execute('''
            INSERT INTO sitins (student_id, lab_number, purpose, login_date, login_time, status)
            VALUES (?, ?, ?, ?, ?, 'Active')
        ''', (student_id, lab_number, purpose, login_date, login_time))
        
        conn.commit()
        
        # Get the sit-in details including the generated ID
        sitin_id = cursor.lastrowid
        conn.close()
        
        print(f"Successfully created sit-in with ID: {sitin_id}")
        
        return jsonify({
            'success': True,
            'message': 'Sit-in recorded successfully',
            'sitin_id': sitin_id
        })
        
    except Exception as e:
        print(f"Error submitting sit-in: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/complete_sitin/<int:sitin_id>', methods=['POST'])
def complete_sitin(sitin_id):
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized access'}), 401
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get current time
        now = datetime.now().strftime('%H:%M:%S')
        
        # Get student_id for this sit-in
        cursor.execute('SELECT student_id FROM sitins WHERE id = ?', (sitin_id,))
        sitin = cursor.fetchone()
        
        if not sitin:
            conn.close()
            return jsonify({'error': 'Sit-in not found'}), 404
            
        student_id = sitin['student_id']
        
        # Update sit-in record
        cursor.execute('''
            UPDATE sitins 
            SET logout_time = ?, status = 'Completed' 
            WHERE id = ?
        ''', (now, sitin_id))
        
        # Deduct from user's remaining sessions
        cursor.execute('''
            UPDATE users 
            SET remaining_sessions = MAX(0, remaining_sessions - 1) 
            WHERE idno = ?
        ''', (student_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Sit-in completed successfully'})
    
    except Exception as e:
        print(f"Error completing sit-in: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/current_sitins')
def current_sitins():
    if 'admin' not in session:
        return redirect(url_for('login'))
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Count active sit-ins (just for the navbar badge)
        cursor.execute('SELECT COUNT(*) as count FROM sitins WHERE logout_time IS NULL')
        active_count = cursor.fetchone()['count']
        
        # Query to fetch ONLY COMPLETED sit-ins with student details
        cursor.execute('''
            SELECT s.id AS sitin_id, s.student_id, s.lab_number, s.purpose, s.timestamp,
                   s.login_date, s.login_time, s.logout_time, s.status,
                   u.firstname, u.lastname, u.course
            FROM sitins s
            JOIN users u ON s.student_id = u.idno
            WHERE s.logout_time IS NOT NULL
            ORDER BY s.timestamp DESC
        ''')
        
        sitins = cursor.fetchall()
        
        # Get statistics by purpose
        cursor.execute('''
            SELECT purpose, COUNT(*) as count 
            FROM sitins 
            WHERE logout_time IS NOT NULL
            GROUP BY purpose
        ''')
        purpose_stats = cursor.fetchall()
        
        # Count by lab
        cursor.execute('''
            SELECT lab_number, COUNT(*) as count 
            FROM sitins 
            WHERE logout_time IS NOT NULL
            GROUP BY lab_number
        ''')
        lab_stats = cursor.fetchall()
        
        # Process the lab stats for chart.js
        lab_numbers = ['524', '526', '528', '530', '542', '544']
        lab_data = [0, 0, 0, 0, 0, 0]
        
        for stat in lab_stats:
            if stat['lab_number'] in lab_numbers:
                idx = lab_numbers.index(stat['lab_number'])
                lab_data[idx] = stat['count']
                
        # Process the purpose stats for chart.js
        purpose_labels = ['C Programming', 'C# Programming', 'Java Programming', '.NET Programming', 'PHP Programming', 'Python Programming']
        purpose_data = [0, 0, 0, 0, 0, 0]
        
        for stat in purpose_stats:
            if stat['purpose'] in purpose_labels:
                idx = purpose_labels.index(stat['purpose'])
                purpose_data[idx] = stat['count']
        
        conn.close()
        
        # Convert to list of dictionaries
        sitins_list = []
        for sitin in sitins:
            sitin_dict = {key: sitin[key] for key in sitin.keys()}
            sitins_list.append(sitin_dict)
            
        return render_template('current_sitins.html', 
                              sitins=sitins_list, 
                              active_count=active_count,
                              active_sitins=[],  # Empty list since we don't want to show active sit-ins here
                              purpose_stats=purpose_stats,
                              lab_stats=lab_stats,
                              lab_data=lab_data,
                              purpose_data=purpose_data)
        
    except Exception as e:
        print(f"Error fetching sit-ins: {str(e)}")
        return render_template('current_sitins.html', sitins=[], error=str(e))

# Route for sit-in page
@app.route('/sitin')
def sitin_page():
    if 'admin' not in session:
        return redirect(url_for('login'))
        
    # Get search_id parameter if it exists
    search_id = request.args.get('search_id')
    student_info = None
    
    # If search_id is provided, get student info
    if search_id:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE idno = ?', (search_id,))
            student = cursor.fetchone()
            
            if student:
                student_info = {
                    'idno': student['idno'],
                    'name': f"{student['firstname']} {student['lastname']}",
                    'course': student['course'],
                    'year_level': student['year_level']
                }
        except Exception as e:
            print(f"Error getting student info: {str(e)}")
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Count active sit-ins
        cursor.execute('SELECT COUNT(*) as count FROM sitins WHERE logout_time IS NULL')
        active_count = cursor.fetchone()['count']
        
        # Fetch active sit-ins with student details
        cursor.execute('''
            SELECT s.id AS sitin_id, s.student_id, s.lab_number, s.purpose, s.timestamp,
                   s.login_date, s.login_time, s.logout_time, s.status,
                   u.firstname, u.lastname, u.course
            FROM sitins s
            JOIN users u ON s.student_id = u.idno
            WHERE s.logout_time IS NULL
            ORDER BY s.timestamp DESC
        ''')
        active_sitins = cursor.fetchall()
        
        # Fetch pending reservations
        cursor.execute('''
            SELECT r.id, r.student_id, r.laboratory_number, r.computer_number, 
                   r.purpose, r.reservation_date, r.reservation_time, r.time_out,
                   r.status, r.created_at
            FROM reservations r
            WHERE r.status = 'Pending'
            ORDER BY r.reservation_date ASC, r.reservation_time ASC
        ''')
        pending_reservations = cursor.fetchall()
        
        # Fetch all reservations
        cursor.execute('''
            SELECT r.id, r.student_id, r.laboratory_number, r.computer_number, 
                   r.purpose, r.reservation_date, r.reservation_time, r.time_out,
                   r.status, r.created_at, u.firstname, u.lastname
            FROM reservations r
            LEFT JOIN users u ON r.student_id = u.idno
            ORDER BY r.reservation_date ASC, r.reservation_time ASC
        ''')
        all_reservations = cursor.fetchall()
        
        conn.close()
        
        # Convert active sit-ins to list of dictionaries
        active_sitins_list = []
        for sitin in active_sitins:
            sitin_dict = {key: sitin[key] for key in sitin.keys()}
            active_sitins_list.append(sitin_dict)
            
        # Convert pending reservations to list of dictionaries
        pending_reservations_list = []
        for reservation in pending_reservations:
            reservation_dict = {key: reservation[key] for key in reservation.keys()}
            pending_reservations_list.append(reservation_dict)
            
        return render_template('sitin_page.html', 
                              active_count=active_count,
                              active_sitins=active_sitins_list,
                              pending_reservations=pending_reservations_list,
                              all_reservations=all_reservations,
                              search_student=student_info)
        
    except Exception as e:
        print(f"Error fetching data: {str(e)}")
        return render_template('sitin_page.html', 
                              active_sitins=[], 
                              pending_reservations=[],
                              all_reservations=[],
                              error=str(e), 
                              search_student=student_info)

# Routes for announcement operations
@app.route('/add_announcement', methods=['POST'])
def add_announcement():
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized access'}), 401
    
    try:
        data = request.get_json()
        title = data.get('title')
        content = data.get('content')
        
        if not title or not content:
            return jsonify({'error': 'Title and content are required'}), 400
        
        # Get admin username from session
        admin_username = session.get('username', 'Admin')
        
        # Connect to the database
        connection = sqlite3.connect('students.db')
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        
        # Get current timestamp
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            INSERT INTO announcement (title, content, created_by, created_at)
            VALUES (?, ?, ?, ?)
        ''', (title, content, admin_username, current_time))
        
        connection.commit()
        announcement_id = cursor.lastrowid
        
        # Get the created announcement
        cursor.execute('''
            SELECT id, title, content, created_at, created_by 
            FROM announcement 
            WHERE id = ?
        ''', (announcement_id,))
        
        announcement = cursor.fetchone()
        connection.close()
        
        if announcement:
            return jsonify({
                'success': True,
                'announcement': {
                    'id': announcement['id'],
                    'title': announcement['title'],
                    'content': announcement['content'],
                    'created_at': announcement['created_at'],
                    'created_by': announcement['created_by']
                }
            })
        else:
            return jsonify({'error': 'Failed to retrieve created announcement'}), 500
    
    except Exception as e:
        print(f"Error adding announcement: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/edit_announcement/<int:announcement_id>', methods=['POST'])
def edit_announcement(announcement_id):
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized access'}), 401
    
    try:
        data = request.get_json()
        title = data.get('title')
        content = data.get('content')
        
        if not title or not content:
            return jsonify({'error': 'Title and content are required'}), 400
        
        connection = sqlite3.connect('students.db')
        cursor = connection.cursor()
        
        cursor.execute('''
            UPDATE announcement
            SET title = ?, content = ?
            WHERE id = ?
        ''', (title, content, announcement_id))
        
        connection.commit()
        
        if cursor.rowcount == 0:
            connection.close()
            return jsonify({'error': 'Announcement not found'}), 404
        
        connection.close()
        return jsonify({'success': True})
    
    except Exception as e:
        print(f"Error editing announcement: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/delete_announcement/<int:announcement_id>', methods=['POST'])
def delete_announcement(announcement_id):
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized access'}), 401
    
    try:
        connection = sqlite3.connect('students.db')
        cursor = connection.cursor()
        
        cursor.execute('DELETE FROM announcement WHERE id = ?', (announcement_id,))
        connection.commit()
        
        if cursor.rowcount == 0:
            connection.close()
            return jsonify({'error': 'Announcement not found'}), 404
            
        connection.close()
        return jsonify({'success': True})
    
    except Exception as e:
        print(f"Error deleting announcement: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/sitin_report')
def sitin_report():
    if 'admin' not in session:
        return redirect(url_for('login'))
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Count active sit-ins for navbar
        cursor.execute('SELECT COUNT(*) as count FROM sitins WHERE logout_time IS NULL')
        active_count = cursor.fetchone()['count']
        
        # Query to fetch ONLY COMPLETED sit-ins with student details for the report
        cursor.execute('''
            SELECT s.id AS sitin_id, s.student_id, s.lab_number, s.purpose, s.timestamp,
                   s.login_date, s.login_time, s.logout_time, s.status,
                   u.firstname, u.lastname, u.course, u.year_level
            FROM sitins s
            JOIN users u ON s.student_id = u.idno
            WHERE s.logout_time IS NOT NULL
            ORDER BY s.timestamp DESC
        ''')
        
        completed_sitins = cursor.fetchall()
        
        # Get statistics by month
        cursor.execute('''
            SELECT 
                strftime('%m-%Y', timestamp) as month_year,
                COUNT(*) as count
            FROM sitins
            WHERE logout_time IS NOT NULL
            GROUP BY month_year
            ORDER BY timestamp DESC
            LIMIT 12
        ''')
        monthly_stats = cursor.fetchall()
        
        # Get statistics by course
        cursor.execute('''
            SELECT 
                u.course,
                COUNT(*) as count
            FROM sitins s
            JOIN users u ON s.student_id = u.idno
            WHERE s.logout_time IS NOT NULL
            GROUP BY u.course
        ''')
        course_stats = cursor.fetchall()
        
        # Get statistics by year level
        cursor.execute('''
            SELECT 
                u.year_level,
                COUNT(*) as count
            FROM sitins s
            JOIN users u ON s.student_id = u.idno
            WHERE s.logout_time IS NOT NULL
            GROUP BY u.year_level
        ''')
        year_level_stats = cursor.fetchall()
        
        # Calculate average session duration
        cursor.execute('''
            SELECT 
                AVG(strftime('%s', logout_time) - strftime('%s', login_time)) as avg_duration_seconds
            FROM sitins
            WHERE logout_time IS NOT NULL AND login_time IS NOT NULL
        ''')
        avg_duration_result = cursor.fetchone()
        avg_duration_minutes = 0
        if avg_duration_result and avg_duration_result['avg_duration_seconds']:
            avg_duration_minutes = round(avg_duration_result['avg_duration_seconds'] / 60, 2)
        
        conn.close()
        
        # Convert to list of dictionaries
        sitins_list = []
        for sitin in completed_sitins:
            sitin_dict = {key: sitin[key] for key in sitin.keys()}
            
            # Calculate session duration if login and logout times exist
            if sitin_dict['login_time'] and sitin_dict['logout_time']:
                login_time = datetime.strptime(sitin_dict['login_time'], '%H:%M:%S')
                logout_time = datetime.strptime(sitin_dict['logout_time'], '%H:%M:%S')
                duration = logout_time - login_time
                minutes = duration.total_seconds() / 60
                sitin_dict['duration_minutes'] = round(minutes, 2)
            else:
                sitin_dict['duration_minutes'] = 'N/A'
                
            sitins_list.append(sitin_dict)
        
        # Prepare data for monthly chart
        months = []
        monthly_counts = []
        for stat in monthly_stats:
            months.append(stat['month_year'])
            monthly_counts.append(stat['count'])
            
        # Prepare data for course chart
        courses = []
        course_counts = []
        for stat in course_stats:
            courses.append(stat['course'])
            course_counts.append(stat['count'])
            
        # Prepare data for year level chart
        year_levels = []
        year_level_counts = []
        for stat in year_level_stats:
            year_levels.append(f"Year {stat['year_level']}")
            year_level_counts.append(stat['count'])
            
        return render_template('sitin_report.html', 
                              sitins=sitins_list,
                              active_count=active_count,
                              months=months,
                              monthly_counts=monthly_counts,
                              courses=courses,
                              course_counts=course_counts,
                              year_levels=year_levels,
                              year_level_counts=year_level_counts,
                              avg_duration_minutes=avg_duration_minutes)
        
    except Exception as e:
        print(f"Error fetching sit-in reports: {str(e)}")
        return render_template('sitin_report.html', sitins=[], error=str(e))

# Route for submitting feedback
@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    if 'user_id' not in session:
        return jsonify({'error': 'Please login to submit feedback'}), 401
    
    try:
        data = request.get_json()
        message = data.get('message')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        student_id = session['user_id']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO feedback (student_id, message)
            VALUES (?, ?)
        ''', (student_id, message))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Feedback submitted successfully'})
    
    except Exception as e:
        print(f"Error submitting feedback: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Route for viewing feedback reports
@app.route('/feedback_report')
def feedback_report():
    if 'admin' not in session:
        return redirect(url_for('login'))
    
    try:
        # Get active sit-in count for nav badge
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM sitins WHERE logout_time IS NULL')
        active_count = cursor.fetchone()[0]
        
        # Get feedback data with join to users table
        cursor.execute('''
            SELECT 
                s.id,
                s.student_id,
                u.firstname,
                u.lastname,
                u.course,
                u.year_level,
                s.feedback,
                s.feedback_response,
                s.timestamp
            FROM 
                sitins s
            JOIN 
                users u ON s.student_id = u.idno
            WHERE 
                s.feedback IS NOT NULL
            ORDER BY 
                s.timestamp DESC
        ''')
        
        feedbacks = cursor.fetchall()
        conn.close()
        
        # Convert to list of dictionaries
        feedback_list = []
        for fb in feedbacks:
            feedback_list.append({
                'id': fb[0],
                'student_id': fb[1],
                'firstname': fb[2],
                'lastname': fb[3],
                'course': fb[4],
                'year_level': fb[5],
                'message': fb[6],
                'feedback_response': fb[7],
                'timestamp': fb[8]
            })
        
        return render_template('feedback_report.html', feedback_entries=feedback_list, active_count=active_count)
    
    except Exception as e:
        print(f"Error loading feedback report: {e}")
        return render_template('feedback_report.html', feedback_entries=[], active_count=0, error=str(e))

# Route to get user's remaining sessions
@app.route('/get_user_sessions/<student_id>', methods=['GET'])
def get_user_sessions(student_id):
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized access'}), 401
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT idno, firstname, lastname, remaining_sessions FROM users WHERE idno = ?', (student_id,))
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        user_data = {
            'idno': user['idno'],
            'name': f"{user['firstname']} {user['lastname']}",
            'remaining_sessions': user['remaining_sessions']
        }
        
        return jsonify({'success': True, 'user': user_data})
        
    except Exception as e:
        print(f"Error getting user sessions: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Route to create announcement (admin only)
@app.route('/create_announcement', methods=['GET', 'POST'])
def create_announcement():
    if 'admin' not in session:
        if request.method == 'POST':
            return jsonify({'error': 'Unauthorized access'}), 401
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            # Handle both JSON and form data
            if request.is_json:
                data = request.json
                title = data.get('title')
                content = data.get('content')
            else:
                title = request.form.get('title')
                content = request.form.get('content')
            
            if not title or not content:
                flash('Title and content are required', 'danger')
                return render_template('create_announcement.html')
            
            conn = sqlite3.connect('students.db')
            cursor = conn.cursor()
            
            # Use current timestamp for created_at
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Get admin name from session
            admin_name = session.get('username', 'Admin')
            
            cursor.execute(
                'INSERT INTO announcement (title, content, created_by, created_at) VALUES (?, ?, ?, ?)',
                (title, content, admin_name, current_time)
            )
            
            conn.commit()
            conn.close()
            
            flash('Announcement created successfully!', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            print(f"Error creating announcement: {str(e)}")
            flash(f'Error creating announcement: {str(e)}', 'danger')
            return render_template('create_announcement.html')
    
    return render_template('create_announcement.html')

# Route to get announcements for user dashboard
@app.route('/get_announcements')
def get_announcements():
    try:
        conn = sqlite3.connect('students.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, title, content, created_at, created_by 
            FROM announcement 
            ORDER BY created_at DESC
            LIMIT 10
        ''')
        
        announcements = cursor.fetchall()
        conn.close()
        
        # Convert to list of dictionaries
        announcements_list = []
        for a in announcements:
            announcement_dict = {
                'id': a['id'],
                'title': a['title'],
                'content': a['content'],
                'created_at': a['created_at'],
                'created_by': a['created_by']
            }
            announcements_list.append(announcement_dict)
            
        return jsonify(announcements_list)
    except Exception as e:
        print(f"Error getting announcements: {e}")
        return jsonify([])

@app.route('/logout')
def logout():
    # Clear the session
    session.clear()
    # Redirect to login page
    return redirect(url_for('login'))

@app.route('/reset_all_sessions', methods=['POST'])
def reset_all_sessions():
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update all users' remaining_sessions to 30
        cursor.execute('UPDATE users SET remaining_sessions = 30')
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'All sessions have been reset successfully'})
    except Exception as e:
        print(f"Error in reset_all_sessions: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Route for sit-in history page
@app.route('/sitin_history')
def sitin_history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    student_id = session['user_id']
    
    # Get sit-in records for this student
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            s.id, 
            s.student_id, 
            s.purpose, 
            s.lab_number, 
            s.login_time, 
            s.logout_time, 
            s.timestamp,
            s.feedback,
            s.feedback_response
        FROM 
            sitins s
        WHERE 
            s.student_id = ?
        ORDER BY 
            s.timestamp DESC
    ''', (student_id,))
    sitins = cursor.fetchall()
    
    # Convert to list of dictionaries for easier access in template
    sitins_list = []
    for sitin in sitins:
        sitins_list.append({
            'id': sitin[0],
            'student_id': sitin[1],
            'purpose': sitin[2],
            'lab_number': sitin[3],
            'login_time': sitin[4],
            'logout_time': sitin[5],
            'timestamp': sitin[6],
            'feedback': sitin[7],
            'feedback_response': sitin[8]
        })
    
    conn.close()
    
    return render_template('sitin_history.html', sitins=sitins_list)

# Route to submit feedback for a specific sit-in session
@app.route('/submit_sitin_feedback', methods=['POST'])
def submit_sitin_feedback():
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    data = request.get_json()
    sitin_id = data.get('sitin_id')
    message = data.get('message')
    
    if not sitin_id or not message:
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if this is the student's sit-in record
        cursor.execute('SELECT student_id FROM sitins WHERE id = ?', (sitin_id,))
        sitin = cursor.fetchone()
        
        if not sitin or sitin[0] != session['user_id']:
            conn.close()
            return jsonify({'error': 'You can only provide feedback for your own sit-in sessions'}), 403
        
        # Update the sit-in record with feedback
        cursor.execute('UPDATE sitins SET feedback = ? WHERE id = ?', (message, sitin_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Feedback submitted successfully'})
    
    except Exception as e:
        print(f"Error submitting feedback: {e}")
        return jsonify({'error': str(e)}), 500

# Route for admin to reply to feedback
@app.route('/reply_to_feedback', methods=['POST'])
def reply_to_feedback():
    if 'admin' not in session:
        return jsonify({'error': 'Admin access required'}), 401
    
    data = request.get_json()
    sitin_id = data.get('sitin_id')
    response = data.get('response')
    
    if not sitin_id or not response:
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update the sit-in record with admin response
        cursor.execute('UPDATE sitins SET feedback_response = ? WHERE id = ?', (response, sitin_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Response submitted successfully'})
    
    except Exception as e:
        print(f"Error submitting response: {e}")
        return jsonify({'error': str(e)}), 500

# Route for admin to delete feedback
@app.route('/delete_feedback', methods=['POST'])
def delete_feedback():
    if 'admin' not in session:
        return jsonify({'error': 'Admin access required'}), 401
    
    data = request.get_json()
    sitin_id = data.get('sitin_id')
    
    if not sitin_id:
        return jsonify({'error': 'Missing sitin_id'}), 400
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Remove the feedback (and response) for this sit-in
        cursor.execute('UPDATE sitins SET feedback = NULL, feedback_response = NULL WHERE id = ?', (sitin_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Feedback deleted successfully'})
    
    except Exception as e:
        print(f"Error deleting feedback: {e}")
        return jsonify({'error': str(e)}), 500

# Route for resetting an individual student's sessions
@app.route('/reset_student_sessions/<student_id>', methods=['POST'])
def reset_student_sessions(student_id):
    if 'admin' not in session:
        return jsonify({'error': 'Admin access required'}), 401
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Reset the student's remaining_sessions to 30
        cursor.execute('UPDATE users SET remaining_sessions = 30 WHERE idno = ?', (student_id,))
        conn.commit()
        
        conn.close()
        
        return jsonify({'success': True, 'message': f'Sessions reset for student {student_id}'})
    
    except Exception as e:
        print(f"Error resetting sessions: {e}")
        return jsonify({'error': str(e)}), 500

# Route for profile page
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))  

    # Get user data from the database
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE idno = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()

    if user:
        return render_template('profile.html', user=user)  

    return redirect(url_for('login'))

@app.route('/view_student')
def view_student():
    if 'admin' not in session:
        return redirect(url_for('login'))
    
    student_id = request.args.get('id')
    if not student_id:
        return redirect(url_for('view_students'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Count active sit-ins for the navbar badge
        cursor.execute('SELECT COUNT(*) as count FROM sitins WHERE logout_time IS NULL')
        active_count = cursor.fetchone()['count']
        
        # Get the student details - try with is_admin first, then without if it fails
        try:
            cursor.execute('''
                SELECT * FROM users WHERE idno = ? AND is_admin = 0
            ''', (student_id,))
        except sqlite3.OperationalError:
            # If is_admin column doesn't exist, exclude admin by username
            cursor.execute('''
                SELECT * FROM users WHERE idno = ? AND username != 'admin'
            ''', (student_id,))
        
        student = cursor.fetchone()
        if not student:
            conn.close()
            flash('Student not found', 'error')
            return redirect(url_for('view_students'))
        
        # Get student's sit-in history
        cursor.execute('''
            SELECT * FROM sitins 
            WHERE student_id = ? 
            ORDER BY login_date DESC, login_time DESC
        ''', (student_id,))
        
        sit_ins = cursor.fetchall()
        
        conn.close()
        
        # Convert student to dict for the template
        student_dict = dict(student)
        
        # Convert sit-ins to list of dicts
        sit_ins_list = []
        for sit_in in sit_ins:
            sit_ins_list.append(dict(sit_in))
        
        return render_template('view_students.html', 
                              single_student=student_dict, 
                              sit_ins=sit_ins_list, 
                              active_count=active_count,
                              students=[])
        
    except Exception as e:
        print(f"Error viewing student: {str(e)}")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('view_students'))

@app.route('/export_students')
def export_students():
    if 'admin' not in session:
        return redirect(url_for('login'))
    
    export_format = request.args.get('format', 'csv')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT idno, username, firstname, lastname, course, year_level, remaining_sessions
            FROM users
            WHERE is_admin = 0
            ORDER BY lastname
        ''')
        
        students_raw = cursor.fetchall()
        conn.close()
        
        # Convert to list of dictionaries
        students = []
        for student in students_raw:
            students.append(dict(student))
            
        # For now, just return the data as JSON
        return jsonify(students)
        
    except Exception as e:
        print(f"Error exporting students: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_student')
def get_student():
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized access'}), 403
    
    student_id = request.args.get('id')
    if not student_id:
        return jsonify({'error': 'No student ID provided'}), 400
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT idno, username, firstname, lastname, course, year_level as yearlevel, remaining_sessions
            FROM users
            WHERE idno = ? AND is_admin = 0
        ''', (student_id,))
        
        student = cursor.fetchone()
        conn.close()
        
        if not student:
            return jsonify({'error': 'Student not found'}), 404
        
        # Convert to dict
        student_dict = dict(student)
        
        return jsonify(student_dict)
        
    except Exception as e:
        print(f"Error fetching student: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/add_student', methods=['POST'])
def add_student():
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized access'}), 403
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Extract data
        idno = data.get('idno', '').strip()
        username = data.get('username', '').strip()
        firstname = data.get('firstname', '').strip()
        lastname = data.get('lastname', '').strip()
        course = data.get('course', '').strip()
        yearlevel = data.get('yearlevel', '').strip()
        password = data.get('password', '').strip()
        
        # Validate required fields
        if not all([idno, username, firstname, lastname, course, yearlevel, password]):
            return jsonify({'error': 'All fields are required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if ID already exists
        cursor.execute('SELECT idno FROM users WHERE idno = ?', (idno,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'error': 'Student ID already exists'}), 400
        
        # Check if is_admin column exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Insert new student
        try:
            if "is_admin" in columns:
                cursor.execute('''
                    INSERT INTO users (idno, username, firstname, lastname, course, year_level, password, is_admin, remaining_sessions)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0, 25)
                ''', (idno, username, firstname, lastname, course, yearlevel, password))
            else:
                cursor.execute('''
                    INSERT INTO users (idno, username, firstname, lastname, course, year_level, password, remaining_sessions)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 25)
                ''', (idno, username, firstname, lastname, course, yearlevel, password))
        except sqlite3.OperationalError as e:
            # Fallback if previous checks failed
            if "no such column: is_admin" in str(e):
                cursor.execute('''
                    INSERT INTO users (idno, username, firstname, lastname, course, year_level, password, remaining_sessions)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 25)
                ''', (idno, username, firstname, lastname, course, yearlevel, password))
            else:
                raise
        
        conn.commit()
        conn.close()
        
        flash('Student added successfully!', 'success')
        return jsonify({'success': True, 'message': 'Student added successfully'})
        
    except Exception as e:
        print(f"Error adding student: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/reset_sessions', methods=['POST'])
def reset_sessions():
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized access'}), 403
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        idno = data.get('idno')
        if idno is None:
            return jsonify({'error': 'Student ID is required'}), 400
            
        # Convert to string if it's an integer
        idno = str(idno).strip()
        
        if not idno:
            return jsonify({'error': 'Student ID is required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if student exists
        cursor.execute('SELECT idno FROM users WHERE idno = ? AND is_admin = 0', (idno,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'error': 'Student not found'}), 404
        
        # Reset sessions to 30 (changed from 25)
        cursor.execute('UPDATE users SET remaining_sessions = 30 WHERE idno = ?', (idno,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Sessions reset successfully'})
        
    except Exception as e:
        print(f"Error resetting sessions: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/delete_student', methods=['POST'])
def delete_student_api():
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized access'}), 403
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        idno = data.get('idno', '').strip()
        
        if not idno:
            return jsonify({'error': 'Student ID is required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if is_admin column exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Check if student exists - handle missing is_admin column
        try:
            if "is_admin" in columns:
                cursor.execute('SELECT idno FROM users WHERE idno = ? AND is_admin = 0', (idno,))
            else:
                cursor.execute('SELECT idno FROM users WHERE idno = ? AND username != "admin"', (idno,))
        except sqlite3.OperationalError:
            cursor.execute('SELECT idno FROM users WHERE idno = ?', (idno,))
        
        if not cursor.fetchone():
            conn.close()
            return jsonify({'error': 'Student not found'}), 404
        
        # Delete student
        cursor.execute('DELETE FROM users WHERE idno = ?', (idno,))
        
        # Also delete any related sit-ins
        cursor.execute('DELETE FROM sitins WHERE student_id = ?', (idno,))
        
        conn.commit()
        conn.close()
        
        flash('Student deleted successfully!', 'success')
        return jsonify({'success': True, 'message': 'Student deleted successfully'})
        
    except Exception as e:
        print(f"Error deleting student: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Route to add sessions to a student (for Lab Usage Points)
@app.route('/add_sessions', methods=['POST'])
def add_sessions():
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized access'}), 401
    
    try:
        data = request.get_json()
        student_id = data.get('student_id')
        sessions_to_add = data.get('sessions', 0)
        
        if not student_id:
            return jsonify({'error': 'Student ID is required'}), 400
        
        if sessions_to_add <= 0:
            return jsonify({'error': 'Sessions to add must be greater than 0'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if student exists
        cursor.execute('SELECT * FROM users WHERE idno = ?', (student_id,))
        student = cursor.fetchone()
        
        if not student:
            conn.close()
            return jsonify({'error': 'Student not found'}), 404
        
        # Update the student's remaining sessions
        cursor.execute('''
            UPDATE users 
            SET remaining_sessions = remaining_sessions + ? 
            WHERE idno = ?
        ''', (sessions_to_add, student_id))
        
        conn.commit()
        
        # Get the updated remaining sessions
        cursor.execute('SELECT remaining_sessions FROM users WHERE idno = ?', (student_id,))
        updated = cursor.fetchone()
        remaining_sessions = updated['remaining_sessions'] if updated else 0
        
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Added {sessions_to_add} sessions to {student_id}',
            'remaining_sessions': remaining_sessions
        })
        
    except Exception as e:
        print(f"Error adding sessions: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Route for the leaderboard
@app.route('/leaderboard')
def leaderboard():
    if 'admin' not in session and 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Count active sit-ins for the navbar badge
        cursor.execute('SELECT COUNT(*) as count FROM sitins WHERE logout_time IS NULL')
        active_count = cursor.fetchone()['count']
        
        # Get users with the most completed sit-ins
        cursor.execute('''
            SELECT 
                u.idno, 
                u.firstname, 
                u.lastname, 
                u.course, 
                u.year_level,
                COUNT(s.id) as total_sitins
            FROM 
                users u
            LEFT JOIN 
                sitins s ON u.idno = s.student_id AND s.status = 'Completed'
            WHERE 
                u.is_admin = 0
            GROUP BY 
                u.idno
            ORDER BY 
                total_sitins DESC
            LIMIT 20
        ''')
        top_sitins = cursor.fetchall()
        
        # Check if points_history table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='points_history'")
        points_history_exists = cursor.fetchone() is not None
        
        if points_history_exists:
            # Get users with the most lab usage points (from points_history)
            cursor.execute('''
                SELECT 
                    u.idno, 
                    u.firstname, 
                    u.lastname, 
                    u.course, 
                    u.year_level,
                    u.remaining_sessions,
                    COALESCE(SUM(ph.points), 0) as lab_points
                FROM 
                    users u
                LEFT JOIN 
                    points_history ph ON u.idno = ph.student_id
                WHERE 
                    u.is_admin = 0
                GROUP BY 
                    u.idno
                ORDER BY 
                    lab_points DESC
                LIMIT 20
            ''')
        else:
            # If points_history doesn't exist, use remaining_sessions as a fallback
            cursor.execute('''
                SELECT 
                    idno, 
                    firstname, 
                    lastname, 
                    course, 
                    year_level, 
                    remaining_sessions,
                    remaining_sessions * 3 as lab_points
                FROM 
                    users
                WHERE 
                    is_admin = 0
                ORDER BY 
                    remaining_sessions DESC
                LIMIT 20
            ''')
        
        top_points = cursor.fetchall()
        
        conn.close()
        
        return render_template(
            'leaderboard.html', 
            top_sitins=top_sitins, 
            top_points=top_points, 
            active_count=active_count
        )
        
    except Exception as e:
        print(f"Error loading leaderboard: {str(e)}")
        flash(f"Error loading leaderboard: {str(e)}", 'danger')
        if 'admin' in session:
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('user_dashboard'))

# Route for admin reservation management page
@app.route('/admin_reservation')
def admin_reservation():
    if 'admin' not in session:
        flash('You must be logged in as admin to access this page', 'danger')
        return redirect(url_for('login'))
    
    try:
        # Get all reservations
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Count active sit-ins for navbar
        cursor.execute('SELECT COUNT(*) as count FROM sitins WHERE logout_time IS NULL')
        active_sitin_count = cursor.fetchone()['count']
        
        cursor.execute('''
            SELECT r.id, r.student_id, u.firstname, u.lastname, r.laboratory_number, 
                   r.computer_number, r.purpose, r.reservation_date, r.reservation_time, 
                   r.time_out, r.status, r.completed_at
            FROM reservations r
            JOIN users u ON r.student_id = u.idno
            ORDER BY r.reservation_date DESC, r.reservation_time ASC
        ''')
        
        reservations = cursor.fetchall()
        conn.close()
        
        return render_template('admin_reservation.html', reservations=reservations, active_sitin_count=active_sitin_count)
    
    except Exception as e:
        print(f"Error loading admin reservation page: {str(e)}")
        return render_template('admin_reservation.html', reservations=[], active_sitin_count=0, error=str(e))

# Route for computer control page
@app.route('/computer_control', methods=['GET', 'POST'])
def computer_control():
    if 'admin' not in session:
        flash('You must be logged in as admin to access this page', 'danger')
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Count active sit-ins for navbar
        cursor.execute('SELECT COUNT(*) as count FROM sitins WHERE logout_time IS NULL')
        active_sitin_count = cursor.fetchone()['count']
        
        # Default laboratory
        selected_lab = request.args.get('laboratory', '524')
        
        # Check if computers table exists, if not create it
        cursor.execute('''
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='computers'
        ''')
        
        if cursor.fetchone() is None:
            # Create computers table with lab_number column
            cursor.execute('''
                CREATE TABLE computers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pc_number INTEGER NOT NULL,
                    lab_number TEXT NOT NULL,
                    status TEXT DEFAULT 'Available',
                    student_id TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(pc_number, lab_number)
                )
            ''')
            
            # Initialize computers for each laboratory (50 computers per lab)
            labs = ['524', '526', '528', '530', '542', '544', '517']
            for lab in labs:
                for i in range(1, 51):
                    cursor.execute('''
                        INSERT INTO computers (pc_number, lab_number, status)
                        VALUES (?, ?, 'Available')
                    ''', (i, lab))
            
            conn.commit()
        else:
            # Check the structure of the table to see which column exists
            cursor.execute('PRAGMA table_info(computers)')
            columns = [column[1] for column in cursor.fetchall()]
            
            # If laboratory column exists but lab_number doesn't, rename it
            if 'laboratory' in columns and 'lab_number' not in columns:
                try:
                    cursor.execute('ALTER TABLE computers RENAME COLUMN laboratory TO lab_number')
                    conn.commit()
                except Exception as column_err:
                    print(f"Error renaming column: {str(column_err)}")
        
        # If form is submitted to update computer status
        if request.method == 'POST':
            pc_id = request.form.get('pc_id')
            new_status = request.form.get('status')
            student_id = request.form.get('student_id', None)
            
            if pc_id and new_status:
                # Update computer status
                if new_status == 'Used':
                    # For automatic marking as used, we don't require a student ID
                    # If student_id is provided, use it; otherwise, just mark as Used without a student
                    if student_id:
                        cursor.execute('''
                            UPDATE computers 
                            SET status = ?, student_id = ? 
                            WHERE id = ?
                        ''', (new_status, student_id, pc_id))
                    else:
                        cursor.execute('''
                            UPDATE computers 
                            SET status = ?, student_id = NULL 
                            WHERE id = ?
                        ''', (new_status, pc_id))
                else:
                    cursor.execute('''
                        UPDATE computers 
                        SET status = ?, student_id = NULL 
                        WHERE id = ?
                    ''', (new_status, pc_id))
                
                # Get the PC number for a better message
                cursor.execute('SELECT pc_number FROM computers WHERE id = ?', (pc_id,))
                pc_result = cursor.fetchone()
                pc_number = pc_result['pc_number'] if pc_result else pc_id
                
                conn.commit()
                
                # Check if it's an AJAX request
                is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                
                if is_ajax:
                    # Return JSON response for AJAX requests
                    message = f'Computer PC-{pc_number} has been marked as {new_status} successfully'
                    return jsonify({
                        'success': True,
                        'message': message,
                        'pc_number': pc_number,
                        'status': new_status
                    })
                else:
                    # Flash message for regular form submissions
                    if new_status == 'Used':
                        flash(f'Computer PC-{pc_number} has been marked as USED successfully', 'success')
                    else:
                        flash(f'Computer PC-{pc_number} has been marked as AVAILABLE successfully', 'success')
                
                # Redirect back to the same laboratory
                return redirect(url_for('computer_control', laboratory=selected_lab))
        
        # Determine which column to use for querying
        column_name = 'lab_number' if 'lab_number' in columns else 'laboratory'
        
        # Get computers for the selected laboratory using the appropriate column
        try:
            cursor.execute(f'''
                SELECT c.id, c.pc_number, c.{column_name} as lab_number, c.status, c.student_id,
                       u.firstname, u.lastname, u.course
                FROM computers c
                LEFT JOIN users u ON c.student_id = u.idno
                WHERE c.{column_name} = ?
                ORDER BY c.pc_number
            ''', (selected_lab,))
            
            computers = cursor.fetchall()
            
            # Ensure we have exactly 50 computers
            if len(computers) < 50:
                # Get the existing PC numbers
                existing_pc_numbers = set(computer['pc_number'] for computer in computers)
                
                # Create missing computers
                for i in range(1, 51):
                    if i not in existing_pc_numbers:
                        cursor.execute(f'''
                            INSERT INTO computers (pc_number, {column_name}, status)
                            VALUES (?, ?, 'Available')
                        ''', (i, selected_lab))
                
                conn.commit()
                
                # Query again to get all 50 computers
                cursor.execute(f'''
                    SELECT c.id, c.pc_number, c.{column_name} as lab_number, c.status, c.student_id,
                           u.firstname, u.lastname, u.course
                    FROM computers c
                    LEFT JOIN users u ON c.student_id = u.idno
                    WHERE c.{column_name} = ?
                    ORDER BY c.pc_number
                ''', (selected_lab,))
                
                computers = cursor.fetchall()
        except Exception as query_err:
            # If there's an error, try recreating the computers table
            print(f"Error querying computers: {str(query_err)}")
            cursor.execute("DROP TABLE IF EXISTS computers")
            
            # Create the table with the correct structure
            cursor.execute('''
                CREATE TABLE computers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pc_number INTEGER NOT NULL,
                    lab_number TEXT NOT NULL,
                    status TEXT DEFAULT 'Available',
                    student_id TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(pc_number, lab_number)
                )
            ''')
            
            # Initialize computers for each laboratory (50 computers per lab)
            labs = ['524', '526', '528', '530', '542', '544', '517']
            for lab in labs:
                for i in range(1, 51):
                    cursor.execute('''
                        INSERT INTO computers (pc_number, lab_number, status)
                        VALUES (?, ?, 'Available')
                    ''', (i, lab))
            
            conn.commit()
            
            # Try querying again with the correct column
            cursor.execute('''
                SELECT c.id, c.pc_number, c.lab_number, c.status, c.student_id,
                       u.firstname, u.lastname, u.course
                FROM computers c
                LEFT JOIN users u ON c.student_id = u.idno
                WHERE c.lab_number = ?
                ORDER BY c.pc_number
            ''', (selected_lab,))
            
            computers = cursor.fetchall()
        
        # Get all students for dropdown
        cursor.execute('''
            SELECT idno, firstname, lastname
            FROM users
            WHERE is_admin = 0
            ORDER BY lastname, firstname
        ''')
        students = cursor.fetchall()
        
        # Get count of available and used computers
        cursor.execute(f'''
            SELECT status, COUNT(*) as count
            FROM computers
            WHERE {column_name} = ?
            GROUP BY status
        ''', (selected_lab,))
        
        status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
        available_count = status_counts.get('Available', 0)
        used_count = status_counts.get('Used', 0)
        
        conn.close()
        
        return render_template('computer_control.html', 
                              computers=computers,
                              students=students,
                              active_sitin_count=active_sitin_count,
                              selected_lab=selected_lab,
                              available_count=available_count,
                              used_count=used_count)
    
    except Exception as e:
        print(f"Error loading computer control page: {str(e)}")
        flash(f'Error: {str(e)}', 'danger')
        return render_template('computer_control.html', 
                             computers=[],
                             students=[],
                             active_sitin_count=0,
                             selected_lab='524',
                             available_count=0,
                             used_count=0,
                             error=str(e))

# Route for updating reservation status (approve/reject)
@app.route('/update_reservation_status', methods=['POST'])
def update_reservation_status():
    if 'admin' not in session:
        flash('You must be logged in as admin to perform this action', 'danger')
        return redirect(url_for('login'))
    
    conn = None
    try:
        reservation_id = request.form.get('reservation_id')
        status = request.form.get('status')
        laboratory_number = request.form.get('laboratory_number')
        computer_number = request.form.get('computer_number')
        approval_type = request.form.get('approval_type', 'standard')  # Default to standard if not specified
        
        if not reservation_id or not status:
            flash('Missing required information', 'danger')
            return redirect(url_for('admin_reservation'))
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get student ID from the reservation
        cursor.execute('SELECT student_id, laboratory_number, computer_number FROM reservations WHERE id = ?', (reservation_id,))
        reservation = cursor.fetchone()
        
        if not reservation:
            flash('Reservation not found', 'danger')
            return redirect(url_for('admin_reservation'))
        
        student_id = reservation['student_id']
        
        # If laboratory_number and computer_number were not in form data, get them from the reservation
        if not laboratory_number:
            laboratory_number = reservation['laboratory_number']
        if not computer_number:
            computer_number = reservation['computer_number']
        
        # If this is a completion action (timeout or rewards)
        if status == 'Completed':
            # Update the reservation status to Completed
            cursor.execute(
                'UPDATE reservations SET status = ? WHERE id = ?',
                (status, reservation_id)
            )
            
            # Get current timestamp for completion time
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # If rewards option was selected, add a point to the user
            if approval_type == 'rewards':
                # Add +1 point to the student for rewards
                current_date = datetime.now().strftime('%Y-%m-%d')
                
                # Record the timeout/completion time
                cursor.execute(
                    'UPDATE reservations SET completed_at = ? WHERE id = ?',
                    (current_time, reservation_id)
                )
                
                # Mark the computer as Available again
                cursor.execute(
                    'UPDATE computers SET status = ?, student_id = NULL WHERE lab_number = ? AND pc_number = ?',
                    ('Available', laboratory_number, computer_number)
                )
                
                # Check if points_history table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='points_history'")
                if not cursor.fetchone():
                    # Create points_history table if it doesn't exist
                    cursor.execute('''
                        CREATE TABLE points_history (
                            id INTEGER PRIMARY KEY,
                            student_id TEXT,
                            points INTEGER,
                            source TEXT DEFAULT 'System',
                            reason TEXT,
                            description TEXT,
                            date TEXT,
                            created_at TEXT,
                            FOREIGN KEY (student_id) REFERENCES users (idno)
                        )
                    ''')
                    conn.commit()
                else:
                    # Check if the table has all required columns
                    cursor.execute('PRAGMA table_info(points_history)')
                    columns = [column[1] for column in cursor.fetchall()]
                    
                    # Add missing columns if necessary
                    if 'reason' not in columns:
                        cursor.execute('ALTER TABLE points_history ADD COLUMN reason TEXT')
                        conn.commit()
                    
                    if 'source' not in columns:
                        cursor.execute('ALTER TABLE points_history ADD COLUMN source TEXT DEFAULT "System"')
                        conn.commit()
                    
                    if 'description' not in columns:
                        cursor.execute('ALTER TABLE points_history ADD COLUMN description TEXT')
                        conn.commit()
                    
                    if 'date' not in columns:
                        cursor.execute('ALTER TABLE points_history ADD COLUMN date TEXT')
                        conn.commit()
                    
                    if 'created_at' not in columns:
                        cursor.execute('ALTER TABLE points_history ADD COLUMN created_at TEXT')
                        conn.commit()
                
                # Add the reward point to points_history
                cursor.execute('''
                    INSERT INTO points_history (student_id, points, source, reason, description, date, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    student_id, 
                    1, 
                    'Rewards', 
                    'Reservation Completion Reward', 
                    'Reward point for completed reservation',
                    current_date,
                    current_time
                ))
                
                # Update user's total points
                try:
                    # Get current points
                    cursor.execute('SELECT points FROM users WHERE idno = ?', (student_id,))
                    user_data = cursor.fetchone()
                    current_points = user_data['points'] if user_data and 'points' in user_data else 0
                    
                    # Add the new point
                    new_points = current_points + 1
                    
                    # Check if user has 3 or more points
                    if new_points >= 3:
                        # Convert points to sessions (1 session per 3 points)
                        sessions_to_add = new_points // 3
                        remaining_points = new_points % 3
                        
                        # Update user with remaining points and add sessions
                        cursor.execute('''
                            UPDATE users 
                            SET points = ?, remaining_sessions = remaining_sessions + ? 
                            WHERE idno = ?
                        ''', (remaining_points, sessions_to_add, student_id))
                        
                        # Add record to points history for the conversion
                        cursor.execute('''
                            INSERT INTO points_history (student_id, points, source, reason, description, date, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            student_id, 
                            -1 * (new_points - remaining_points), 
                            'Conversion', 
                            'Points Converted to Sessions', 
                            f'Converted {new_points - remaining_points} points to {sessions_to_add} sessions',
                            current_date,
                            current_time
                        ))
                        
                        flash(f'Reservation completed with rewards. {sessions_to_add} sessions added to student {student_id} from {new_points - remaining_points} points!', 'success')
                    else:
                        # Just update points if less than 3
                        cursor.execute('''
                            UPDATE users SET points = ? WHERE idno = ?
                        ''', (new_points, student_id))
                        
                        flash(f'Reservation completed with rewards, +1 point added to student {student_id}', 'success')
                    
                    # Log success
                    print(f"Successfully processed points for user {student_id}")
                except Exception as points_error:
                    print(f"Error adding points to user {student_id}: {points_error}")
                    # Check if points column exists
                    cursor.execute("PRAGMA table_info(users)")
                    columns = [column[1] for column in cursor.fetchall()]
                    if "points" not in columns:
                        # Add points column if it doesn't exist
                        cursor.execute("ALTER TABLE users ADD COLUMN points INTEGER DEFAULT 0")
                        conn.commit()
                        print(f"Added missing points column to users table and retrying update")
                        cursor.execute('''
                            UPDATE users SET points = 1 WHERE idno = ?
                        ''', (student_id,))
                
                flash(f'Reservation completed with rewards, +1 point added to student {student_id}', 'success')
            else:
                # This is a timeout completion
                # Mark the computer as Available again
                cursor.execute(
                    'UPDATE computers SET status = ?, student_id = NULL WHERE lab_number = ? AND pc_number = ?',
                    ('Available', laboratory_number, computer_number)
                )
                
                # Record the timeout - update reservation with completion time
                cursor.execute(
                    'UPDATE reservations SET completed_at = ? WHERE id = ?',
                    (current_time, reservation_id)
                )
                
                flash(f'Reservation timed out for student {student_id}', 'success')
        # Standard approval flow
        elif status == 'Approved':
            # Update the reservation status
            cursor.execute(
                'UPDATE reservations SET status = ? WHERE id = ?',
                (status, reservation_id)
            )
            
            # If approved, handle based on approval type
            # Get current remaining sessions
            cursor.execute('SELECT remaining_sessions FROM users WHERE idno = ?', (student_id,))
            user = cursor.fetchone()
            
            if approval_type == 'standard' or approval_type == 'timeout':
                if user and user['remaining_sessions'] > 0:
                    # Deduct one session
                    cursor.execute(
                        'UPDATE users SET remaining_sessions = remaining_sessions - 1 WHERE idno = ?',
                        (student_id,)
                    )
                    
                    # Mark the computer as Used
                    cursor.execute(
                        'UPDATE computers SET status = ?, student_id = ? WHERE lab_number = ? AND pc_number = ?',
                        ('Used', student_id, laboratory_number, computer_number)
                    )
                    
                    if approval_type == 'timeout':
                        # For timeout approval, log this specifically
                        cursor.execute(
                            'UPDATE reservations SET timeout_approved = 1 WHERE id = ?',
                            (reservation_id,)
                        )
                        flash(f'Reservation approved with timeout, computer PC-{computer_number} marked as Used, and 1 session deducted from student {student_id}', 'success')
                    else:
                        flash(f'Reservation approved, computer PC-{computer_number} marked as Used, and 1 session deducted from student {student_id}', 'success')
                else:
                    flash(f'Reservation approved but student {student_id} has no remaining sessions to deduct', 'warning')
            
            elif approval_type == 'rewards':
                if user and user['remaining_sessions'] > 0:
                    # Deduct one session
                    cursor.execute(
                        'UPDATE users SET remaining_sessions = remaining_sessions - 1 WHERE idno = ?',
                        (student_id,)
                    )
                    
                    # Mark the computer as Used
                    cursor.execute(
                        'UPDATE computers SET status = ?, student_id = ? WHERE lab_number = ? AND pc_number = ?',
                        ('Used', student_id, laboratory_number, computer_number)
                    )
                    
                    # Add +1 point to the student for rewards approval
                    current_date = datetime.now().strftime('%Y-%m-%d')
                    
                    # Check if points_history table exists
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='points_history'")
                    if not cursor.fetchone():
                        # Create points_history table if it doesn't exist
                        cursor.execute('''
                            CREATE TABLE points_history (
                                id INTEGER PRIMARY KEY,
                                student_id TEXT,
                                points INTEGER,
                                source TEXT DEFAULT 'System',
                                reason TEXT,
                                description TEXT,
                                date TEXT,
                                created_at TEXT,
                                FOREIGN KEY (student_id) REFERENCES users (idno)
                            )
                        ''')
                    else:
                        # Check if the table has all required columns
                        cursor.execute('PRAGMA table_info(points_history)')
                        columns = [column[1] for column in cursor.fetchall()]
                        
                        # Add missing columns if necessary
                        if 'reason' not in columns:
                            cursor.execute('ALTER TABLE points_history ADD COLUMN reason TEXT')
                            conn.commit()
                        
                        if 'source' not in columns:
                            cursor.execute('ALTER TABLE points_history ADD COLUMN source TEXT DEFAULT "System"')
                            conn.commit()
                        
                        if 'description' not in columns:
                            cursor.execute('ALTER TABLE points_history ADD COLUMN description TEXT')
                            conn.commit()
                        
                        if 'date' not in columns:
                            cursor.execute('ALTER TABLE points_history ADD COLUMN date TEXT')
                            conn.commit()
                        
                        if 'created_at' not in columns:
                            cursor.execute('ALTER TABLE points_history ADD COLUMN created_at TEXT')
                            conn.commit()
                    
                    # Add the reward point to points_history
                    cursor.execute('''
                        INSERT INTO points_history (student_id, points, source, reason, description, date, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                    ''', (
                        student_id, 
                        1, 
                        'Rewards', 
                        'Reservation Reward', 
                        'Reward point for approved reservation',
                        current_date
                    ))
                    
                    # Update user's total points
                    try:
                        cursor.execute('''
                            UPDATE users SET points = COALESCE(points, 0) + 1 WHERE idno = ?
                        ''', (student_id,))
                        
                        # Log success
                        print(f"Successfully added points to user {student_id}")
                    except Exception as points_error:
                        print(f"Error adding points to user {student_id}: {points_error}")
                        # Check if points column exists
                        cursor.execute("PRAGMA table_info(users)")
                        columns = [column[1] for column in cursor.fetchall()]
                        if "points" not in columns:
                            # Add points column if it doesn't exist
                            cursor.execute("ALTER TABLE users ADD COLUMN points INTEGER DEFAULT 0")
                            conn.commit()
                            print(f"Added missing points column to users table and retrying update")
                            cursor.execute('''
                                UPDATE users SET points = 1 WHERE idno = ?
                            ''', (student_id,))
                    
                    flash(f'Reservation approved with rewards, computer PC-{computer_number} marked as Used, 1 session deducted, and +1 point added to student {student_id}', 'success')
                else:
                    flash(f'Reservation approved but student {student_id} has no remaining sessions to deduct', 'warning')
        # For rejection 
        else:
            # Update the reservation status for rejection
            cursor.execute(
                'UPDATE reservations SET status = ? WHERE id = ?',
                ('Rejected', reservation_id)
            )
            flash(f'Reservation has been rejected', 'success')
        
        conn.commit()
        
        # Redirect based on referrer
        referrer = request.referrer
        if referrer and 'sitin' in referrer:
            return redirect(url_for('sitin_page'))
        else:
            return redirect(url_for('admin_reservation'))
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error updating reservation status: {str(e)}")
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('admin_reservation'))
    finally:
        if conn:
            conn.close()

# Route for user reservation history
@app.route('/user_reservation_history')
def user_reservation_history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    student_id = session['user_id']
    status_filter = request.args.get('status', None)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get user info for display
        cursor.execute('SELECT * FROM users WHERE idno = ?', (student_id,))
        user = cursor.fetchone()
        
        # Get reservations for this student, with optional status filter
        if status_filter:
            cursor.execute('''
                SELECT id, laboratory_number, computer_number, purpose, reservation_date, 
                       reservation_time, time_out, status, created_at, completed_at
                FROM reservations
                WHERE student_id = ? AND status = ?
                ORDER BY reservation_date DESC, reservation_time DESC
            ''', (student_id, status_filter))
        else:
            cursor.execute('''
                SELECT id, laboratory_number, computer_number, purpose, reservation_date, 
                       reservation_time, time_out, status, created_at, completed_at
                FROM reservations
                WHERE student_id = ?
                ORDER BY reservation_date DESC, reservation_time DESC
            ''', (student_id,))
        
        reservations = cursor.fetchall()
        
        # Get all approved reservations
        cursor.execute('''
            SELECT id, laboratory_number, computer_number, purpose, reservation_date, 
                   reservation_time, time_out, status, created_at, completed_at
            FROM reservations
            WHERE student_id = ? AND status = 'Approved'
            ORDER BY reservation_date DESC, reservation_time DESC
        ''', (student_id,))
        
        approved_reservations = cursor.fetchall()
        conn.close()
        
        return render_template('user_reservation_history.html', 
                              user=user, 
                              reservations=reservations,
                              approved_reservations=approved_reservations,
                              current_filter=status_filter)
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        print(f"Error fetching reservation history: {str(e)}")
        flash(f"Error: {str(e)}", "danger")
        return redirect(url_for('user_dashboard'))

# Route to handle profile image updates
@app.route('/update_profile_image', methods=['POST'])
def update_profile_image():
    if 'user_id' not in session:
        return jsonify({'error': 'You must be logged in'}), 401
    
    user_id = session['user_id']
    
    if 'profile_image' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['profile_image']
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file:
        # Save the file with a secure name
        filename = secure_filename(f"profile_{user_id}.jpg")
        file_path = os.path.join(app.static_folder, filename)
        
        try:
            # Save the file
            file.save(file_path)
            
            # Update the user's profile image in the database
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET profile_image = ? WHERE idno = ?', (filename, user_id))
            conn.commit()
            conn.close()
            
            return jsonify({'success': True, 'filename': filename})
        
        except Exception as e:
            print(f"Error updating profile image: {e}")
            return jsonify({'error': str(e)}), 500
    
    return jsonify({'error': 'Could not update profile image'}), 500

# Route for lab usage points page
@app.route('/lab_usage_points')
def lab_usage_points():
    if 'admin' not in session:
        flash('You must be logged in as admin to view this page', 'danger')
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if the points_history table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='points_history'")
        if not cursor.fetchone():
            # Create the points_history table if it doesn't exist
            cursor.execute('''
                CREATE TABLE points_history (
                    id INTEGER PRIMARY KEY,
                    student_id TEXT,
                    points INTEGER,
                    source TEXT DEFAULT 'System',
                    reason TEXT,
                    description TEXT,
                    date TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES users (idno)
                )
            ''')
            conn.commit()
        else:
            # Check if needed columns exist
            cursor.execute('PRAGMA table_info(points_history)')
            columns = [column[1] for column in cursor.fetchall()]
            
            # Add missing columns if necessary
            if 'source' not in columns:
                cursor.execute('ALTER TABLE points_history ADD COLUMN source TEXT DEFAULT "System"')
                conn.commit()
            
            if 'description' not in columns:
                cursor.execute('ALTER TABLE points_history ADD COLUMN description TEXT')
                conn.commit()
                
            if 'created_at' not in columns:
                cursor.execute('ALTER TABLE points_history ADD COLUMN created_at TEXT')
                conn.commit()
        
        # Query points history with dynamic column selection
        cursor.execute('PRAGMA table_info(points_history)')
        columns = [column[1] for column in cursor.fetchall()]
        
        # Build a dynamic SELECT query based on available columns
        select_columns = ['id', 'student_id', 'points']
        
        if 'source' in columns:
            select_columns.append('source')
        
        if 'reason' in columns:
            select_columns.append('reason')
            
        if 'description' in columns:
            select_columns.append('description')
            
        if 'date' in columns:
            select_columns.append('date')
            
        if 'created_at' in columns:
            select_columns.append('created_at')
        
        select_query = f"SELECT {', '.join(select_columns)} FROM points_history ORDER BY id DESC"
        cursor.execute(select_query)
        points_history = cursor.fetchall()
        
        # Get all users
        cursor.execute('SELECT * FROM users')
        users = cursor.fetchall()
        
        conn.close()
        
        return render_template('lab_usage_points.html', points_history=points_history, users=users, columns=select_columns)
    
    except Exception as e:
        print(f"Error in lab_usage_points: {str(e)}")
        flash(f"An error occurred: {str(e)}", 'danger')
        return redirect(url_for('dashboard'))

# Route for getting points history of a student
@app.route('/get_points_history')
def get_points_history():
    if 'admin' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    student_id = request.args.get('student_id')
    if not student_id:
        return jsonify({'error': 'Student ID is required'}), 400
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        history = []
        
        # Check if points_history table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='points_history'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            # Create points_history table with all required columns
            cursor.execute('''
                CREATE TABLE points_history (
                    id INTEGER PRIMARY KEY,
                    student_id TEXT,
                    points INTEGER,
                    source TEXT DEFAULT 'System',
                    reason TEXT,
                    description TEXT,
                    date TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES users (idno)
                )
            ''')
            conn.commit()
        else:
            # Check the table structure
            cursor.execute('PRAGMA table_info(points_history)')
            columns = [column[1] for column in cursor.fetchall()]
            
            # If the source column doesn't exist, add it
            if 'source' not in columns:
                cursor.execute('ALTER TABLE points_history ADD COLUMN source TEXT DEFAULT "System"')
                conn.commit()
            
            # If description doesn't exist but reason does, use reason as description
            description_field = 'description'
            if 'description' not in columns and 'reason' in columns:
                description_field = 'reason'
            
            # If date doesn't exist but created_at does, use created_at as date
            date_field = 'date'
            if 'date' not in columns:
                if 'created_at' in columns:
                    date_field = 'created_at'
                elif 'timestamp' in columns:
                    date_field = 'timestamp'
            
            # Get points history for the student
            try:
                query = f'''
                    SELECT id, points, source, {description_field} as reason, {date_field} as date
                    FROM points_history
                    WHERE student_id = ?
                    ORDER BY {date_field} DESC
                '''
                cursor.execute(query, (student_id,))
                
                rows = cursor.fetchall()
                
                for row in rows:
                    history.append({
                        'id': row[0],
                        'points': row[1],
                        'source': row[2] if row[2] else 'System',
                        'reason': row[3],
                        'date': row[4]
                    })
            except Exception as inner_e:
                print(f"Error fetching points history: {inner_e}")
        
        conn.close()
        return jsonify(history)
    
    except Exception as e:
        print(f"Error fetching points history: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Route for adding lab points to a student
@app.route('/add_lab_points', methods=['POST'])
def add_lab_points():
    if 'admin' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    data = request.get_json()
    student_id = data.get('student_id')
    points = data.get('points')
    reason = data.get('reason')
    
    if not student_id or not points:
        return jsonify({'error': 'Student ID and points are required'}), 400
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if points_history table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='points_history'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            # Create points_history table if it doesn't exist
            cursor.execute('''
                CREATE TABLE points_history (
                    id INTEGER PRIMARY KEY,
                    student_id TEXT,
                    points INTEGER,
                    source TEXT DEFAULT 'Manual Addition',
                    reason TEXT,
                    description TEXT,
                    date TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES users (idno)
                )
            ''')
            conn.commit()
        else:
            # Check table structure
            cursor.execute('PRAGMA table_info(points_history)')
            columns = [column[1] for column in cursor.fetchall()]
            
            # If source doesn't exist, add it
            if 'source' not in columns:
                cursor.execute('ALTER TABLE points_history ADD COLUMN source TEXT DEFAULT "Manual Addition"')
                conn.commit()
            
            # If description doesn't exist, add it
            if 'description' not in columns:
                cursor.execute('ALTER TABLE points_history ADD COLUMN description TEXT')
                conn.commit()
        
        # Get current remaining_sessions (points)
        cursor.execute('SELECT remaining_sessions FROM users WHERE idno = ?', (student_id,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'error': 'Student not found'}), 404
        
        # Each lab point equals to 1/3 of a remaining session
        sessions_to_add = points / 3
        current_sessions = user['remaining_sessions']
        new_sessions = current_sessions + sessions_to_add
        
        # Update the user's remaining_sessions
        cursor.execute('UPDATE users SET remaining_sessions = ? WHERE idno = ?', (new_sessions, student_id))
        
        # Add to points history - adapt to the table structure
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Use different fields based on what's available in the table
        description_field = 'description, ' if 'description' in columns else ''
        reason_field = 'reason, ' if 'reason' in columns else ''
        source_field = 'source, ' if 'source' in columns else ''
        date_field = 'date, ' if 'date' in columns else ''
        created_at_field = 'created_at' if 'created_at' in columns else 'date' if 'date' in columns else 'created_at'
        
        # Build dynamic query
        fields = f"student_id, points, {source_field}{reason_field}{description_field}{created_at_field}"
        values = f"?, ?, {'?, ' if 'source' in columns else ''}{'?, ' if 'reason' in columns else ''}{'?, ' if 'description' in columns else ''}?"
        
        # Prepare parameters
        params = [student_id, points]
        if 'source' in columns:
            params.append('Manual Addition')
        if 'reason' in columns:
            params.append(reason)
        if 'description' in columns:
            params.append(reason)  # Use reason as description if needed
        params.append(now)  # For created_at or date field
        
        # Execute query
        cursor.execute(f'''
            INSERT INTO points_history ({fields})
            VALUES ({values})
        ''', params)
        
        conn.commit()
        
        # Calculate total points (sessions * 3)
        total_points = int(new_sessions * 3)
        
        conn.close()
        return jsonify({'success': True, 'total_points': total_points})
    
    except Exception as e:
        print(f"Error adding lab points: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Route for resetting leaderboard points
@app.route('/reset_leaderboard_points', methods=['POST'])
def reset_leaderboard_points():
    if 'admin' not in session:
        flash('You must be logged in as admin to perform this action', 'danger')
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if points_history table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='points_history'")
        if cursor.fetchone():
            # Check table structure
            cursor.execute('PRAGMA table_info(points_history)')
            columns = [column[1] for column in cursor.fetchall()]
            
            # Clear points history
            cursor.execute('DELETE FROM points_history')
            
            # Add a record for the reset action
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Build dynamic query based on available columns
            fields = ['student_id', 'points']
            values = ['admin', 0]
            
            if 'source' in columns:
                fields.append('source')
                values.append('System')
            
            if 'reason' in columns:
                fields.append('reason')
                values.append('Points reset by administrator')
            
            if 'description' in columns:
                fields.append('description')
                values.append('Points reset by administrator')
            
            if 'date' in columns:
                fields.append('date')
                values.append(now)
            
            if 'created_at' in columns:
                fields.append('created_at')
                values.append(now)
            
            # Construct and execute the query
            fields_str = ', '.join(fields)
            placeholders = ', '.join(['?' for _ in values])
            
            cursor.execute(f'''
                INSERT INTO points_history ({fields_str})
                VALUES ({placeholders})
            ''', values)
        else:
            # Create the points_history table if it doesn't exist
            cursor.execute('''
                CREATE TABLE points_history (
                    id INTEGER PRIMARY KEY,
                    student_id TEXT,
                    points INTEGER,
                    source TEXT DEFAULT 'System',
                    reason TEXT,
                    description TEXT,
                    date TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES users (idno)
                )
            ''')
            
            # Add a record for the reset action
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT INTO points_history (student_id, points, source, reason, description, date, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('admin', 0, 'System', 'Points reset by administrator', 'Points reset by administrator', now, now))
        
        conn.commit()
        conn.close()
        
        flash('Lab usage points have been reset successfully. Student sit-in sessions remain unchanged.', 'success')
        return redirect(url_for('leaderboard'))
    
    except Exception as e:
        print(f"Error resetting leaderboard points: {str(e)}")
        flash(f"Error resetting leaderboard points: {str(e)}", 'danger')
        return redirect(url_for('leaderboard'))

# Route for uploading lab schedule
@app.route('/upload_lab_schedule', methods=['POST'])
def upload_lab_schedule():
    if 'admin' not in session:
        flash('You must be logged in as admin', 'danger')
        return redirect(url_for('login'))
    
    try:
        # Get form data
        laboratory = request.form.get('laboratory')
        day = request.form.get('day')  # Get the new day field
        course = request.form.get('course')
        instructor = request.form.get('instructor')
        start_time = request.form.get('startTime')
        end_time = request.form.get('endTime')
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if lab_schedules table exists
        cursor.execute('''
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='lab_schedules'
        ''')
        
        # If table doesn't exist, create it with the new schema including day field
        if cursor.fetchone() is None:
            cursor.execute('''
                CREATE TABLE lab_schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    laboratory TEXT NOT NULL,
                    day TEXT NOT NULL,
                    course TEXT NOT NULL,
                    instructor TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            ''')
            conn.commit()
        else:
            # Check if required columns exist and add them if missing
            cursor.execute('PRAGMA table_info(lab_schedules)')
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'day' not in columns:
                cursor.execute('ALTER TABLE lab_schedules ADD COLUMN day TEXT')
                conn.commit()
            
            if 'start_time' not in columns:
                cursor.execute('ALTER TABLE lab_schedules ADD COLUMN start_time TEXT')
                conn.commit()
            
            if 'end_time' not in columns:
                cursor.execute('ALTER TABLE lab_schedules ADD COLUMN end_time TEXT')
                conn.commit()
                
            if 'created_at' not in columns:
                cursor.execute('ALTER TABLE lab_schedules ADD COLUMN created_at TEXT')
                conn.commit()
        
        # Insert the lab schedule with day field
        cursor.execute('''
            INSERT INTO lab_schedules (laboratory, day, course, instructor, start_time, end_time, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (laboratory, day, course, instructor, start_time, end_time, created_at))
        conn.commit()
        conn.close()
        
        flash('Lab schedule added successfully!', 'success')
    except Exception as e:
        flash(f'Error adding lab schedule: {str(e)}', 'danger')
    
    return redirect(url_for('admin_dashboard'))

# Route for uploading resource materials
@app.route('/upload_resource_materials', methods=['POST'])
def upload_resource_materials():
    if 'admin' not in session:
        flash('You must be logged in as admin', 'danger')
        return redirect(url_for('login'))
    
    try:
        # Get form data
        title = request.form.get('resourceTitle')
        description = request.form.get('resourceDescription')
        resource_type = request.form.get('resourceType', 'file')
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if resources table exists, create if not
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                file_path TEXT NOT NULL,
                resource_type TEXT DEFAULT 'file',
                created_at TEXT NOT NULL
            )
        ''')
        conn.commit()
        
        # Add resource_type column if it doesn't exist
        cursor.execute("PRAGMA table_info(resources)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'resource_type' not in columns:
            cursor.execute("ALTER TABLE resources ADD COLUMN resource_type TEXT DEFAULT 'file'")
            conn.commit()
        
        file_path = ''
        
        # Process resource based on type (file or link)
        if resource_type == 'file':
            # Check if file was uploaded
            if 'resourceFile' not in request.files:
                flash('No file part', 'danger')
                return redirect(url_for('admin_dashboard'))
            
            file = request.files['resourceFile']
            
            # If user does not select file, browser also
            # submit an empty part without filename
            if file.filename == '':
                flash('No selected file', 'danger')
                return redirect(url_for('admin_dashboard'))
            
            # Save the file
            from werkzeug.utils import secure_filename
            import os
            
            # Create upload directory if it doesn't exist
            upload_folder = os.path.join('static', 'uploads')
            os.makedirs(os.path.join(app.root_path, upload_folder), exist_ok=True)
            
            filename = secure_filename(file.filename)
            file_path = os.path.join(upload_folder, filename)
                    
            # Save to filesystem
            file.save(os.path.join(app.root_path, file_path))
        else:
            # Handle link type
            gdrive_link = request.form.get('resourceLink', '')
            if not gdrive_link:
                flash('No link provided', 'danger')
                return redirect(url_for('admin_dashboard'))
            
            # Store the link as the file_path
            file_path = gdrive_link
        
        # Insert the resource with resource_type
        cursor.execute('''
            INSERT INTO resources (title, description, file_path, resource_type, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (title, description, file_path, resource_type, created_at))
        conn.commit()
        conn.close()
        
        flash('Resource materials uploaded successfully!', 'success')
    except Exception as e:
        flash(f'Error uploading resource materials: {str(e)}', 'danger')
    
    return redirect(url_for('admin_dashboard'))

# Route for viewing lab schedules
@app.route('/view_lab_schedules')
def view_lab_schedules():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get day filter from query parameters
    day_filter = request.args.get('day')
    
    try:
        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if lab_schedules table exists
        cursor.execute('''
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='lab_schedules'
        ''')
        
        if cursor.fetchone() is None:
            # Table doesn't exist, create it with appropriate schema
            cursor.execute('''
                CREATE TABLE lab_schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    laboratory TEXT NOT NULL,
                    day TEXT NOT NULL,
                    course TEXT NOT NULL,
                    instructor TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            ''')
            conn.commit()
            schedules = []
        else:
            # Check table structure
            cursor.execute('PRAGMA table_info(lab_schedules)')
            columns = [column[1] for column in cursor.fetchall()]
            
            # Check if the required columns exist, add them if they don't
            if 'day' not in columns:
                cursor.execute('ALTER TABLE lab_schedules ADD COLUMN day TEXT')
                conn.commit()
                
            if 'start_time' not in columns:
                cursor.execute('ALTER TABLE lab_schedules ADD COLUMN start_time TEXT')
                conn.commit()
            
            if 'end_time' not in columns:
                cursor.execute('ALTER TABLE lab_schedules ADD COLUMN end_time TEXT')
                conn.commit()
                
            if 'created_at' not in columns:
                cursor.execute('ALTER TABLE lab_schedules ADD COLUMN created_at TEXT')
                conn.commit()
            
            # Refresh column list after potential alterations
            cursor.execute('PRAGMA table_info(lab_schedules)')
            columns = [column[1] for column in cursor.fetchall()]
            
            # Build the query dynamically based on available columns
            select_columns = ['id']
            
            # Add required columns with fallbacks
            if 'laboratory' in columns:
                select_columns.append('laboratory')
            else:
                select_columns.append("'' AS laboratory")
                
            if 'day' in columns:
                select_columns.append('day')
            else:
                select_columns.append("'' AS day")
                
            if 'course' in columns:
                select_columns.append('course')
            else:
                select_columns.append("'' AS course")
                
            if 'instructor' in columns:
                select_columns.append('instructor')
            else:
                select_columns.append("'' AS instructor")
            
            if 'start_time' in columns:
                select_columns.append('start_time')
            else:
                select_columns.append("'' AS start_time")
                
            if 'end_time' in columns:
                select_columns.append('end_time')
            else:
                select_columns.append("'' AS end_time")
            
            if 'created_at' in columns:
                select_columns.append('created_at')
            else:
                select_columns.append("'' AS created_at")
            
            # Construct the query
            query = f"SELECT {', '.join(select_columns)} FROM lab_schedules"
            
            # Add filter for day if provided
            if day_filter:
                query += f" WHERE day = ?"
                cursor.execute(query, (day_filter,))
            else:
                cursor.execute(query)
            
            schedules = cursor.fetchall()
            
            # Convert to list of dictionaries for easier access in template
            column_names = [col[0] for col in cursor.description]
            schedules = [dict(zip(column_names, row)) for row in schedules]
        
        conn.close()
        
        return render_template('view_lab_schedules.html', schedules=schedules, day_filter=day_filter)
    except Exception as e:
        flash(f'Error viewing lab schedules: {str(e)}', 'danger')
        return render_template('view_lab_schedules.html', schedules=[])

# Route for viewing resources/materials
@app.route('/view_resources')
def view_resources():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if resources table exists
        cursor.execute('''
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='resources'
        ''')
        
        if cursor.fetchone() is None:
            # Table doesn't exist, return empty list
            resources = []
        else:
            # Fetch all resources
            cursor.execute('''
                SELECT id, title, description, file_path, resource_type, created_at
                FROM resources
                ORDER BY created_at DESC
            ''')
            resources = cursor.fetchall()
        
        conn.close()
        
        return render_template('view_resources.html', resources=resources)
    
    except Exception as e:
        print(f"Error fetching resources: {e}")
        return render_template('view_resources.html', resources=[], error=str(e))

@app.route('/download_resource/<int:resource_id>')
def download_resource(resource_id):
    if 'user_id' not in session and 'admin' not in session:
        return redirect(url_for('login'))
    
    try:
        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get resource details
        cursor.execute('SELECT id, title, file_path, resource_type FROM resources WHERE id = ?', (resource_id,))
        resource = cursor.fetchone()
        conn.close()
        
        if not resource:
            flash('Resource not found', 'error')
            return redirect(url_for('view_resources'))
            
        # Check if it's a link type resource
        if resource['resource_type'] == 'link':
            # Redirect to the external link
            return redirect(resource['file_path'])
            
        # Get the file path stored in the database
        file_path = resource['file_path']
        
        # Extract the filename from the path
        filename = os.path.basename(file_path)
        
        # Determine the directory path
        if file_path.startswith('static/'):
            # The file path includes 'static/' prefix
            dir_path = os.path.dirname(file_path)
        else:
            # The file path doesn't include 'static/' prefix
            dir_path = os.path.join('static', os.path.dirname(file_path))
        
        # Determine mime type based on file extension
        import mimetypes
        mimetype = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        
        # Return the file for download
        return send_from_directory(
            os.path.join(app.root_path, dir_path),
            filename,
            mimetype=mimetype,
            as_attachment=True
        )
        
    except Exception as e:
        flash(f'Error downloading resource: {str(e)}', 'error')
        return redirect(url_for('view_resources'))

# Route for viewing rewards/points earned
@app.route('/view_points')
def view_points():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    try:
        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get user info including points
        cursor.execute('''
            SELECT * FROM users WHERE idno = ?
        ''', (user_id,))
        user = cursor.fetchone()
        
        # Check if points_history table exists
        cursor.execute('''
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='points_history'
        ''')
        
        # If table exists, check its structure
        if cursor.fetchone() is not None:
            try:
                # Try to query the table structure
                cursor.execute('PRAGMA table_info(points_history)')
                columns = [column[1] for column in cursor.fetchall()]
                
                # Check if required columns exist, add them if they don't
                if 'reason' not in columns:
                    cursor.execute('ALTER TABLE points_history ADD COLUMN reason TEXT')
                    conn.commit()
                
                # If 'created_at' doesn't exist but 'timestamp' does, use timestamp
                time_column = 'created_at'
                if 'created_at' not in columns and 'timestamp' in columns:
                    time_column = 'timestamp'
                elif 'created_at' not in columns:
                    cursor.execute('ALTER TABLE points_history ADD COLUMN created_at TEXT')
                    conn.commit()
                
                # If 'description' doesn't exist, add it
                if 'description' not in columns:
                    cursor.execute('ALTER TABLE points_history ADD COLUMN description TEXT')
                    conn.commit()
                
                # Fetch user's points history using the correct column name
                cursor.execute(f'''
                    SELECT id, student_id, description, points, {time_column} as date_time 
                    FROM points_history
                    WHERE student_id = ?
                    ORDER BY {time_column} DESC
                ''', (user_id,))
                points_history = cursor.fetchall()
            except Exception as inner_e:
                print(f"Error querying points_history: {inner_e}")
                # If there was an error, drop and recreate the table
                cursor.execute('DROP TABLE points_history')
                conn.commit()
                cursor.execute('''
                    CREATE TABLE points_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        description TEXT NOT NULL,
                        points INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        reason TEXT,
                        source TEXT DEFAULT 'System'
                    )
                ''')
                conn.commit()
                points_history = []
        else:
            # Table doesn't exist, create it
            cursor.execute('''
                CREATE TABLE points_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    description TEXT NOT NULL,
                    points INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    reason TEXT,
                    source TEXT DEFAULT 'System'
                )
            ''')
            conn.commit()
            points_history = []
        
        conn.close()
        
        return render_template('view_points.html', user=user, points_history=points_history)
    
    except Exception as e:
        print(f"Error fetching points: {e}")
        return render_template('view_points.html', user=None, points_history=[], error=str(e))

# Route for getting all lab schedules (for the history tab)
@app.route('/get_lab_schedules', methods=['GET'])
def get_lab_schedules():
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized access'}), 401
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if lab_schedules table exists
        cursor.execute('''
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='lab_schedules'
        ''')
        
        if cursor.fetchone() is None:
            conn.close()
            return jsonify([])
        
        # Get all schedules
        cursor.execute('''
            SELECT id, laboratory, day, course, instructor, start_time, end_time, created_at
            FROM lab_schedules
            ORDER BY created_at DESC
        ''')
        
        schedules = cursor.fetchall()
        conn.close()
        
        # Convert to list of dictionaries
        result = []
        for schedule in schedules:
            result.append({
                'id': schedule['id'],
                'laboratory': schedule['laboratory'],
                'day': schedule['day'],
                'course': schedule['course'],
                'instructor': schedule['instructor'],
                'start_time': schedule['start_time'],
                'end_time': schedule['end_time'],
                'created_at': schedule['created_at']
            })
        
        return jsonify(result)
    
    except Exception as e:
        print(f"Error fetching lab schedules: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Route for editing lab schedule
@app.route('/edit_lab_schedule', methods=['POST'])
def edit_lab_schedule():
    if 'admin' not in session:
        flash('You must be logged in as admin', 'danger')
        return redirect(url_for('login'))
    
    try:
        # Get form data
        schedule_id = request.form.get('schedule_id')
        laboratory = request.form.get('laboratory')
        day = request.form.get('day')
        course = request.form.get('course')
        instructor = request.form.get('instructor')
        start_time = request.form.get('startTime')
        end_time = request.form.get('endTime')
        
        # Validate required fields
        if not all([schedule_id, laboratory, day, course, instructor, start_time, end_time]):
            flash('All fields are required', 'danger')
            return redirect(url_for('admin_dashboard'))
        
        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update the schedule
        cursor.execute('''
            UPDATE lab_schedules 
            SET laboratory = ?, day = ?, course = ?, instructor = ?, start_time = ?, end_time = ?
            WHERE id = ?
        ''', (laboratory, day, course, instructor, start_time, end_time, schedule_id))
        
        conn.commit()
        conn.close()
        
        flash('Lab schedule updated successfully!', 'success')
    except Exception as e:
        flash(f'Error updating lab schedule: {str(e)}', 'danger')
    
    return redirect(url_for('admin_dashboard'))

# Route for deleting lab schedule
@app.route('/delete_lab_schedule', methods=['POST'])
def delete_lab_schedule():
    if 'admin' not in session:
        flash('You must be logged in as admin', 'danger')
        return redirect(url_for('login'))
    
    try:
        # Get schedule ID
        schedule_id = request.form.get('schedule_id')
        
        if not schedule_id:
            flash('Schedule ID is required', 'danger')
            return redirect(url_for('admin_dashboard'))
        
        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Delete the schedule
        cursor.execute('DELETE FROM lab_schedules WHERE id = ?', (schedule_id,))
        conn.commit()
        conn.close()
        
        flash('Lab schedule deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting lab schedule: {str(e)}', 'danger')
    
    return redirect(url_for('admin_dashboard'))

# Route for getting all resources (for the history tab)
@app.route('/get_resources', methods=['GET'])
def get_resources():
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized access'}), 401
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if resources table exists
        cursor.execute('''
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='resources'
        ''')
        
        if cursor.fetchone() is None:
            conn.close()
            return jsonify([])
        
        # Get all resources
        cursor.execute('''
            SELECT id, title, description, file_path, resource_type, created_at
            FROM resources
            ORDER BY created_at DESC
        ''')
        
        resources = cursor.fetchall()
        conn.close()
        
        # Convert to list of dictionaries
        resource_list = []
        for resource in resources:
            resource_dict = dict(resource)
            if resource_dict.get('resource_type') == 'link':
                resource_dict['file_type'] = 'LINK'
            else:
                resource_dict['file_type'] = os.path.splitext(resource['file_path'])[1].lstrip('.').upper()
            resource_list.append(resource_dict)
        
        return jsonify(resource_list)
    
    except Exception as e:
        print(f"Error fetching resources: {e}")
        return jsonify({'error': str(e)}), 500

# Route for editing resource
@app.route('/edit_resource', methods=['POST'])
def edit_resource():
    if 'admin' not in session:
        flash('You must be logged in as admin', 'danger')
        return redirect(url_for('login'))
    
    try:
        # Get form data
        resource_id = request.form.get('resource_id')
        title = request.form.get('resourceTitle')
        description = request.form.get('resourceDescription')
        resource_type = request.form.get('resourceType', 'file')
        
        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get current resource data
        cursor.execute('SELECT file_path, resource_type FROM resources WHERE id = ?', (resource_id,))
        resource = cursor.fetchone()
        
        if not resource:
            conn.close()
            flash('Resource not found', 'danger')
            return redirect(url_for('admin_dashboard'))
        
        # Initialize file_path with current value
        file_path = resource['file_path']
        
        # Check if a new file was uploaded or link was provided
        if resource_type == 'file':
            if 'resourceFile' in request.files and request.files['resourceFile'].filename != '':
                file = request.files['resourceFile']
                
                # Save the new file
                from werkzeug.utils import secure_filename
                import os
                
                # Create upload directory if it doesn't exist
                upload_folder = os.path.join('static', 'uploads')
                os.makedirs(os.path.join(app.root_path, upload_folder), exist_ok=True)
                
                filename = secure_filename(file.filename)
                new_file_path = os.path.join(upload_folder, filename)
                
                # Save to filesystem
                file.save(os.path.join(app.root_path, new_file_path))
                
                # Delete old file if it exists and is not a link
                if resource['resource_type'] == 'file':
                    try:
                        old_file_path = os.path.join(app.root_path, file_path)
                        if os.path.exists(old_file_path):
                            os.remove(old_file_path)
                    except Exception as e:
                        print(f"Could not delete old file: {e}")
                
                # Update with new file path
                file_path = new_file_path
        else:
            # Handle link update
            new_link = request.form.get('resourceLink', '')
            if new_link:
                file_path = new_link
        
        # Update the resource in database
        cursor.execute('''
            UPDATE resources 
            SET title = ?, description = ?, file_path = ?, resource_type = ?
            WHERE id = ?
        ''', (title, description, file_path, resource_type, resource_id))
        conn.commit()
        conn.close()
        
        flash('Resource updated successfully!', 'success')
    except Exception as e:
        flash(f'Error updating resource: {str(e)}', 'danger')
    
    return redirect(url_for('admin_dashboard'))

# Route for deleting resource
@app.route('/delete_resource', methods=['POST'])
def delete_resource():
    if 'admin' not in session:
        flash('You must be logged in as admin', 'danger')
        return redirect(url_for('login'))
    
    try:
        # Get resource ID from form
        resource_id = request.form.get('resource_id')
        
        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get the file path before deleting
        cursor.execute('SELECT file_path FROM resources WHERE id = ?', (resource_id,))
        resource = cursor.fetchone()
        
        if not resource:
            conn.close()
            flash('Resource not found', 'danger')
            return redirect(url_for('admin_dashboard'))
        
        file_path = resource['file_path']
        
        # Delete from database
        cursor.execute('DELETE FROM resources WHERE id = ?', (resource_id,))
        conn.commit()
        conn.close()
        
        # Delete the file from the filesystem
        try:
            full_file_path = os.path.join(app.root_path, file_path)
            if os.path.exists(full_file_path):
                os.remove(full_file_path)
        except Exception as e:
            print(f"Could not delete file: {e}")
        
        flash('Resource deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting resource: {str(e)}', 'danger')
    
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)

app.run(debug=True, host=" 172.19.131.140" , port="5000")