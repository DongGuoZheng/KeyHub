import sqlite3
import datetime
import hashlib
import os

# Database path moved into dedicated folder to keep data isolated
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "db")
LEGACY_DB_PATH = os.path.join(BASE_DIR, "keyhub.db")
DB_PATH = os.path.join(DB_DIR, "keyhub.db")

# Ensure db directory exists and migrate old db file if necessary
os.makedirs(DB_DIR, exist_ok=True)
if os.path.exists(LEGACY_DB_PATH) and not os.path.exists(DB_PATH):
    os.replace(LEGACY_DB_PATH, DB_PATH)


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()

    # Create Projects table
    c.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL,
            is_default INTEGER DEFAULT 0
        )
    ''')

    # Create Keys table
    c.execute('''
        CREATE TABLE IF NOT EXISTS keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            remarks TEXT,
            project_id INTEGER,
            FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
        )
    ''')

    # Create MachineBindings table
    c.execute('''
        CREATE TABLE IF NOT EXISTS machine_bindings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_value TEXT NOT NULL,
            machine_id TEXT NOT NULL,
            bound_at TEXT NOT NULL,
            remarks TEXT,
            FOREIGN KEY (key_value) REFERENCES keys (key) ON DELETE CASCADE,
            UNIQUE(key_value, machine_id)
        )
    ''')
    
    # Create AdminUsers table
    c.execute('''
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    
    # Create default project if not exists
    try:
        c.execute('SELECT id FROM projects WHERE is_default = 1')
        if not c.fetchone():
            now = datetime.datetime.now().isoformat()
            c.execute('INSERT INTO projects (name, description, created_at, is_default) VALUES (?, ?, ?, ?)',
                      ('Default Project', 'System default project', now, 1))
    except sqlite3.IntegrityError:
        pass # Already exists
    
    # Create default admin user if not exists
    try:
        c.execute('SELECT id FROM admin_users WHERE username = ?', ('admin',))
        if not c.fetchone():
            now = datetime.datetime.now().isoformat()
            # Store password in plain text
            c.execute('INSERT INTO admin_users (username, password, created_at) VALUES (?, ?, ?)',
                      ('admin', 'admin123', now))
    except sqlite3.IntegrityError:
        pass # Already exists

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized.")
