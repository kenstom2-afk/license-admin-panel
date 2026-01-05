import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tạo bảng admin users
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tạo bảng licenses
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE NOT NULL,
            product TEXT NOT NULL,
            owner TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at DATE,
            max_devices INTEGER DEFAULT 1,
            notes TEXT
        )
    ''')
    
    # Tạo bảng API keys
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_key TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tạo bảng license activations
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS license_activations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_id INTEGER NOT NULL,
            hwid TEXT NOT NULL,
            ip_address TEXT,
            activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (license_id) REFERENCES licenses (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def create_default_admin():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Kiểm tra xem đã có admin chưa
    cursor.execute('SELECT * FROM admin_users WHERE username = ?', ('admin',))
    admin = cursor.fetchone()
    
    if not admin:
        # Tạo admin mặc định với mật khẩu "Anhhuy123"
        hashed_password = hash_password("Anhhuy123")
        cursor.execute(
            'INSERT INTO admin_users (username, password) VALUES (?, ?)',
            ('admin', hashed_password)
        )
        print("✅ Default admin user created: admin / Anhhuy123")
    
    conn.commit()
    conn.close()

def create_default_api_key():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Kiểm tra xem đã có API key chưa
    cursor.execute('SELECT * FROM api_keys')
    api_key = cursor.fetchone()
    
    if not api_key:
        # Tạo API key mặc định
        api_key = f"sk_{secrets.token_hex(16)}"
        cursor.execute(
            'INSERT INTO api_keys (api_key, name) VALUES (?, ?)',
            (api_key, 'Default API Key')
        )
        print(f"✅ Default API Key created: {api_key[:20]}...")
    
    conn.commit()
    conn.close()