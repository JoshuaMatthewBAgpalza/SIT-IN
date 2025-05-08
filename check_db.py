import sqlite3

def get_db_connection():
    conn = sqlite3.connect('students.db')
    conn.row_factory = sqlite3.Row
    return conn

def check_db_structure():
    # Get a database connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get a list of all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    print("Database Tables:")
    for table in tables:
        print(f"- {table['name']}")
        
        # Get table schema
        cursor.execute(f"PRAGMA table_info({table['name']})")
        columns = cursor.fetchall()
        
        print("  Columns:")
        for col in columns:
            print(f"    {col['name']} ({col['type']})")
            
        # Get a sample of data
        cursor.execute(f"SELECT * FROM {table['name']} LIMIT 1")
        row = cursor.fetchone()
        
        if row:
            print("  Sample data:")
            for key in row.keys():
                print(f"    {key}: {row[key]}")
        else:
            print("  No data in table")
        
        print()
    
    # Specifically check user data
    print("Checking users table...")
    try:
        cursor.execute("SELECT COUNT(*) as count FROM users")
        count = cursor.fetchone()['count']
        print(f"Number of users: {count}")
        
        if count > 0:
            cursor.execute("SELECT * FROM users LIMIT 3")
            users = cursor.fetchall()
            print("\nSample users:")
            for user in users:
                print(f"ID: {user['idno']}, Name: {user.get('firstname', 'N/A')} {user.get('lastname', 'N/A')}")
    except Exception as e:
        print(f"Error checking users table: {e}")
    
    conn.close()

if __name__ == "__main__":
    check_db_structure() 