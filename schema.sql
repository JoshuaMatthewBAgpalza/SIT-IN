-- Create sitins table
CREATE TABLE IF NOT EXISTS sitins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    lab_number TEXT NOT NULL,
    purpose TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users(idno)
);

-- Add remaining_sessions column to users table if it doesn't exist
ALTER TABLE users ADD COLUMN remaining_sessions INTEGER DEFAULT 30; 