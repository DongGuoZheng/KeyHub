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

    # Create Licenses table (replaces keys table)
    c.execute('''
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            license_key TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            remarks TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE,
            UNIQUE(project_id, license_key)
        )
    ''')

    # Create indexes for licenses table
    c.execute('CREATE INDEX IF NOT EXISTS idx_licenses_project_id ON licenses(project_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_licenses_license_key ON licenses(license_key)')
    
    # Migrate licenses table if it has old columns (subject_type, subject_value, expires_at, meta)
    try:
        # Check if licenses table exists and has old columns
        c.execute("PRAGMA table_info(licenses)")
        columns = [row[1] for row in c.fetchall()]
        old_columns = ['subject_type', 'subject_value', 'expires_at', 'meta']
        has_old_columns = any(col in columns for col in old_columns)
        
        if has_old_columns:
            print("检测到旧表结构，开始迁移数据...")
            # Create temporary table with new structure
            c.execute('''
                CREATE TABLE IF NOT EXISTS licenses_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    license_key TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    remarks TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE,
                    UNIQUE(project_id, license_key)
                )
            ''')
            
            # Copy data from old table to new table
            c.execute('''
                INSERT INTO licenses_new (
                    id, project_id, license_key, is_active, remarks, created_at
                )
                SELECT 
                    id, project_id, license_key, is_active, remarks, created_at
                FROM licenses
            ''')
            
            # Drop old table and indexes
            c.execute('DROP INDEX IF EXISTS idx_licenses_subject')
            c.execute('DROP TABLE licenses')
            
            # Rename new table
            c.execute('ALTER TABLE licenses_new RENAME TO licenses')
            
            # Recreate indexes
            c.execute('CREATE INDEX IF NOT EXISTS idx_licenses_project_id ON licenses(project_id)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_licenses_license_key ON licenses(license_key)')
            
            conn.commit()
            print("数据迁移完成：已删除 subject_type, subject_value, expires_at, meta 字段")
    except Exception as e:
        print(f"迁移表结构时出错: {e}")
        conn.rollback()
    
    # Create AdminUsers table
    c.execute('''
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    
    # Migrate data from old keys table to licenses table (if keys table exists)
    try:
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='keys'")
        if c.fetchone():
            # Check if licenses table is empty (migration not done yet)
            c.execute("SELECT COUNT(*) FROM licenses")
            if c.fetchone()[0] == 0:
                # Migrate data from keys to licenses
                c.execute('''
                    INSERT INTO licenses (
                        project_id, 
                        license_key, 
                        is_active, 
                        remarks, 
                        created_at
                    )
                    SELECT 
                        project_id,
                        key as license_key,
                        is_active,
                        remarks,
                        created_at
                    FROM keys
                ''')
                print("数据已从 keys 表迁移到 licenses 表")
    except Exception as e:
        print(f"迁移数据时出错（可能 keys 表不存在）: {e}")
    
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
