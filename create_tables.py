import sqlite3

def create_tables():
    conn = sqlite3.connect('students.db')
    cursor = conn.cursor()
    
    # Create sitins table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sitins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        lab_number TEXT NOT NULL,
        purpose TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        login_time TEXT,
        logout_time TEXT,
        status TEXT DEFAULT 'Active'
    )
    ''')
    
    # Create feedback table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        message TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES users(idno)
    )
    ''')
    
    # Check if login_time, logout_time, and status columns exist, and add them if they don't
    try:
        cursor.execute('SELECT login_time FROM sitins LIMIT 1')
    except sqlite3.OperationalError:
        cursor.execute('ALTER TABLE sitins ADD COLUMN login_time TEXT')
        print("Added login_time column to sitins table")
        
    try:
        cursor.execute('SELECT logout_time FROM sitins LIMIT 1')
    except sqlite3.OperationalError:
        cursor.execute('ALTER TABLE sitins ADD COLUMN logout_time TEXT')
        print("Added logout_time column to sitins table")
        
    try:
        cursor.execute('SELECT status FROM sitins LIMIT 1')
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE sitins ADD COLUMN status TEXT DEFAULT 'Active'")
        print("Added status column to sitins table")
    
    # Add remaining_sessions column to users table if it doesn't exist
    try:
        cursor.execute('SELECT remaining_sessions FROM users LIMIT 1')
    except sqlite3.OperationalError:
        cursor.execute('ALTER TABLE users ADD COLUMN remaining_sessions INTEGER DEFAULT 30')
        print("Added remaining_sessions column to users table")
    
    conn.commit()
    print("Tables created/updated successfully!")
    conn.close()

if __name__ == "__main__":
    create_tables() 