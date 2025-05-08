import sqlite3
from flask import Flask, request, render_template
from werkzeug.security import generate_password_hash

app = Flask(__name__)

# SQLite database file
db_file = 'students.db'

# Function to get the database connection
def get_db_connection():
    try:
        connection = sqlite3.connect(db_file)
        print("Connection established.")
        return connection
    except sqlite3.Error as e:
        print(f"Database connection failed: {e}")
        return None

# Function to execute queries (for insertion/updating)
def execute_query(query, params=None):
    connection = get_db_connection()
    if connection is None:
        print("Connection failed.")
        return False
    try:
        cursor = connection.cursor()  # Create cursor
        print(f"Executing query: {query}")
        cursor.execute(query, params or [])
        connection.commit()
        print("Query executed successfully.")
        return True
    except sqlite3.Error as e:
        print(f"Error executing query: {e}")
        return False
    finally:
        cursor.close()  # Close cursor
        connection.close()  # Close connection

# Function to initialize the database (if not already done)
def init_db():
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute(''' 
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        idno TEXT,
        lastname TEXT,
        firstname TEXT,
        middlename TEXT,
        course TEXT,
        year_level TEXT,
        email TEXT,
        username TEXT,
        password TEXT
    )
    ''')
    conn.commit()
    conn.close()

# Initialize the database
init_db()

# Route to serve the registration page
@app.route('/')
def index():
    return render_template('index.html')

# Handle registration form submission
@app.route('/register', methods=['POST'])
def register():
    # Fetch data from the form
    idno = request.form['idno']
    lastname = request.form['lastname']
    firstname = request.form['firstname']
    middlename = request.form['middlename']
    course = request.form['course']
    year_level = request.form['year_level']
    email = request.form['email']
    username = request.form['username']
    password = request.form['password']

    # Hash the password before storing it
    hashed_password = generate_password_hash(password, method='sha256')

    # SQL query to insert data into the users table
    query = '''
    INSERT INTO users (idno, lastname, firstname, middlename, course, year_level, email, username, password)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    '''
    
    # Execute the query
    params = (idno, lastname, firstname, middlename, course, year_level, email, username, hashed_password)
    success = execute_query(query, params)
    
    if success:
        return "Registration successful! You can now log in."
    else:
        return "Error during registration. Please try again."

if __name__ == '__main__':
    app.run(debug=True)
