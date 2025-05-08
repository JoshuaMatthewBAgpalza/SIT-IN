import sqlite3
from datetime import datetime

def get_db_connection():
    conn = sqlite3.connect('students.db')
    conn.row_factory = sqlite3.Row
    return conn

def add_sample_students():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Sample students data
        students = [
            {
                'idno': '12345',
                'username': 'john.doe',
                'firstname': 'John',
                'lastname': 'Doe',
                'course': 'BSCS',
                'year_level': 3,
                'password': 'password',
                'remaining_sessions': 25
            },
            {
                'idno': '23456',
                'username': 'jane.smith',
                'firstname': 'Jane',
                'lastname': 'Smith',
                'course': 'BSIT',
                'year_level': 2,
                'password': 'password',
                'remaining_sessions': 15
            },
            {
                'idno': '34567',
                'username': 'bob.johnson',
                'firstname': 'Bob',
                'lastname': 'Johnson',
                'course': 'BSEMC',
                'year_level': 4,
                'password': 'password',
                'remaining_sessions': 5
            },
            {
                'idno': '45678',
                'username': 'alice.williams',
                'firstname': 'Alice',
                'lastname': 'Williams',
                'course': 'BSCS',
                'year_level': 1,
                'password': 'password',
                'remaining_sessions': 20
            },
            {
                'idno': '56789',
                'username': 'charlie.brown',
                'firstname': 'Charlie',
                'lastname': 'Brown',
                'course': 'BSIT',
                'year_level': 3,
                'password': 'password',
                'remaining_sessions': 0
            }
        ]
        
        for student in students:
            # Check if student already exists
            cursor.execute('SELECT idno FROM users WHERE idno = ?', (student['idno'],))
            if cursor.fetchone():
                print(f"Student with ID {student['idno']} already exists. Skipping.")
                continue
                
            # Insert student
            cursor.execute('''
                INSERT INTO users (idno, username, firstname, lastname, course, year_level, password, is_admin, remaining_sessions)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
            ''', (
                student['idno'],
                student['username'],
                student['firstname'],
                student['lastname'],
                student['course'],
                student['year_level'],
                student['password'],
                student['remaining_sessions']
            ))
            
            print(f"Added student: {student['firstname']} {student['lastname']}")
        
        # Add some sit-in records for students
        sitins = [
            {
                'student_id': '12345',
                'lab_number': '524',
                'purpose': 'C Programming',
                'login_date': '2023-11-15',
                'login_time': '09:30:00',
                'logout_time': '11:30:00',
                'status': 'Completed'
            },
            {
                'student_id': '23456',
                'lab_number': '526',
                'purpose': 'Java Programming',
                'login_date': '2023-11-16',
                'login_time': '13:00:00',
                'logout_time': '15:00:00',
                'status': 'Completed'
            },
            {
                'student_id': '12345',
                'lab_number': '528',
                'purpose': 'Python Programming',
                'login_date': datetime.now().strftime('%Y-%m-%d'),
                'login_time': '10:00:00',
                'logout_time': None,
                'status': 'Active'
            }
        ]
        
        for sitin in sitins:
            # Insert sit-in record
            cursor.execute('''
                INSERT INTO sitins (student_id, lab_number, purpose, login_date, login_time, logout_time, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                sitin['student_id'],
                sitin['lab_number'],
                sitin['purpose'],
                sitin['login_date'],
                sitin['login_time'],
                sitin['logout_time'],
                sitin['status']
            ))
            
            print(f"Added sit-in record for student ID: {sitin['student_id']}")
        
        conn.commit()
        print("Sample students and sit-ins added successfully.")
        
    except Exception as e:
        print(f"Error adding sample students: {str(e)}")
    finally:
        conn.close()

if __name__ == '__main__':
    add_sample_students() 