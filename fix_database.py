import sqlite3
from app import init_db
import os

def fix_sitins_table():
    print("Starting database fix...")
    
    # Check if database file exists
    if os.path.exists('students.db'):
        print("Database file found")
    else:
        print("Database file not found, will be created")
    
    # Call the init_db function to recreate the sitins table with all required columns
    init_db()
    
    # Verify the fix
    conn = sqlite3.connect('students.db')
    cursor = conn.cursor()
    
    # Check if login_date column exists
    cursor.execute("PRAGMA table_info(sitins)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if "login_date" in columns:
        print("login_date column exists in sitins table")
    else:
        print("ERROR: login_date column is still missing")
    
    conn.close()
    print("Database fix completed")

if __name__ == "__main__":
    fix_sitins_table() 