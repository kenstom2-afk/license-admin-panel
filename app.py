import os
import sqlite3
import json
import uuid
import hashlib
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, g
from flask_cors import CORS
from cryptography.fernet import Fernet
import base64
import argon2

app = Flask(__name__)
CORS(app)

# IMPORTANT: Use environment variable or default for Render
app.secret_key = os.environ.get('SECRET_KEY', 'your-super-secret-key-change-this-in-production-12345')

# Cấu hình database
DATABASE = 'licenses.db'

# Khởi tạo Argon2
argon2_hasher = argon2.PasswordHasher()

# ============== DATABASE FUNCTIONS ==============
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # Tạo bảng licenses
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS licenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_key TEXT UNIQUE NOT NULL,
                hwid TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                last_check TIMESTAMP,
                device_info TEXT,
                note TEXT,
                is_locked INTEGER DEFAULT 0,
                lock_reason TEXT
            )
        ''')
        
        # Tạo bảng admin_users
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tạo bảng api_keys
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                permissions TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Thêm admin mặc định nếu chưa có
        cursor.execute("SELECT COUNT(*) as count FROM admin_users")
        if cursor.fetchone()[0] == 0:
            password_hash = argon2_hasher.hash("admin123")
            cursor.execute(
                "INSERT INTO admin_users (username, password_hash) VALUES (?, ?)",
                ("admin", password_hash)
            )
        
        # Thêm API key mặc định
        cursor.execute("SELECT COUNT(*) as count FROM api_keys")
        if cursor.fetchone()[0] == 0:
            default_api_key = f"sk_{uuid.uuid4().hex[:32]}"
            cursor.execute(
                "INSERT INTO api_keys (key, name, permissions) VALUES (?, ?, ?)",
                (default_api_key, "Default API Key", "all")
            )
        
        db.commit()

# ============== HELPER FUNCTIONS ==============
def validate_api_key():
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        return False
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM api_keys WHERE key = ?", (api_key,))
    return cursor.fetchone() is not None

def generate_license_key():
    return f"LIC-{uuid.uuid4().hex[:8].upper()}-{uuid.uuid4().hex[:8].upper()}-{uuid.uuid4().hex[:8].upper()}"

# ============== ROUTES ==============
@app.route('/')
def index():
    return render_template('admin.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

# ============== ADMIN API ==============
@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM admin_users WHERE username = ?", (username,))
    user = cursor.fetchone()
    
    if user:
        try:
            if argon2_hasher.verify(user['password_hash'], password):
                return jsonify({
                    'success': True,
                    'message': 'Login successful',
                    'username': username
                })
        except:
            pass
    
    return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

@app.route('/api/admin/licenses', methods=['GET'])
def get_all_licenses():
    if not validate_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM licenses ORDER BY created_at DESC')
    
    licenses = []
    for row in cursor.fetchall():
        license_data = dict(row)
        # Convert datetime to string
        for key in license_data:
            if isinstance(license_data[key], datetime):
                license_data[key] = license_data[key].isoformat()
            elif isinstance(license_data[key], str) and 'T' in license_data[key]:
                # Already ISO string
                pass
        licenses.append(license_data)
    
    return jsonify({'licenses': licenses})

@app.route('/api/admin/licenses/create', methods=['POST'])
def create_license():
    if not validate_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    data = request.json
    days_valid = data.get('days_valid', 30)
    note = data.get('note', '')
    
    license_key = generate_license_key()
    expires_at = datetime.now() + timedelta(days=days_valid)
    
    db = get_db()
    cursor = db.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO licenses (license_key, expires_at, note, status)
            VALUES (?, ?, ?, 'active')
        ''', (license_key, expires_at, note))
        
        db.commit()
        return jsonify({
            'success': True,
            'license_key': license_key,
            'expires_at': expires_at.isoformat(),
            'message': 'License created successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/admin/licenses/reset', methods=['POST'])
def reset_license():
    if not validate_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    data = request.json
    license_key = data.get('license_key')
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('''
        UPDATE licenses 
        SET hwid = NULL, 
            device_info = NULL,
            last_check = NULL,
            is_locked = 0,
            lock_reason = NULL,
            status = 'active'
        WHERE license_key = ?
    ''', (license_key,))
    
    db.commit()
    
    if cursor.rowcount > 0:
        return jsonify({
            'success': True,
            'message': 'License reset successfully'
        })
    else:
        return jsonify({'success': False, 'message': 'License not found'}), 404

@app.route('/api/admin/licenses/lock', methods=['POST'])
def lock_license():
    if not validate_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    data = request.json
    license_key = data.get('license_key')
    reason = data.get('reason', 'Admin lock')
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('''
        UPDATE licenses 
        SET is_locked = 1,
            lock_reason = ?,
            status = 'locked'
        WHERE license_key = ?
    ''', (reason, license_key))
    
    db.commit()
    
    if cursor.rowcount > 0:
        return jsonify({
            'success': True,
            'message': 'License locked successfully'
        })
    else:
        return jsonify({'success': False, 'message': 'License not found'}), 404

@app.route('/api/admin/licenses/delete', methods=['POST'])
def delete_license():
    if not validate_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    data = request.json
    license_key = data.get('license_key')
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('DELETE FROM licenses WHERE license_key = ?', (license_key,))
    db.commit()
    
    if cursor.rowcount > 0:
        return jsonify({
            'success': True,
            'message': 'License deleted successfully'
        })
    else:
        return jsonify({'success': False, 'message': 'License not found'}), 404

@app.route('/api/admin/licenses/revoke', methods=['POST'])
def revoke_license():
    if not validate_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    data = request.json
    license_key = data.get('license_key')
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('''
        UPDATE licenses 
        SET status = 'revoked',
            is_locked = 1,
            lock_reason = 'Revoked by admin'
        WHERE license_key = ?
    ''', (license_key,))
    
    db.commit()
    
    if cursor.rowcount > 0:
        return jsonify({
            'success': True,
            'message': 'License revoked successfully'
        })
    else:
        return jsonify({'success': False, 'message': 'License not found'}), 404

# ============== CLIENT API ==============
@app.route('/api/client/validate', methods=['POST'])
def validate_license():
    data = request.json
    license_key = data.get('license_key')
    hwid = data.get('hwid')
    device_info = data.get('device_info', '')
    
    if not license_key or not hwid:
        return jsonify({
            'valid': False,
            'message': 'License key and HWID are required'
        }), 400
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('''
        SELECT * FROM licenses 
        WHERE license_key = ? 
        AND status = 'active'
    ''', (license_key,))
    
    license_data = cursor.fetchone()
    
    if not license_data:
        return jsonify({
            'valid': False,
            'message': 'Invalid license key'
        })
    
    # Kiểm tra nếu bị locked
    if license_data['is_locked']:
        return jsonify({
            'valid': False,
            'message': f'License is locked: {license_data.get("lock_reason", "Unknown reason")}'
        })
    
    # Kiểm tra hạn sử dụng
    expires_at = license_data['expires_at']
    if expires_at:
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        
        if expires_at < datetime.now():
            return jsonify({
                'valid': False,
                'message': 'License has expired'
            })
    
    # Nếu license chưa có HWID (lần đầu kích hoạt)
    if not license_data['hwid']:
        cursor.execute('''
            UPDATE licenses 
            SET hwid = ?,
                device_info = ?,
                last_check = ?
            WHERE license_key = ?
        ''', (hwid, device_info, datetime.now(), license_key))
        db.commit()
        
        return jsonify({
            'valid': True,
            'message': 'License activated successfully',
            'expires_at': license_data['expires_at']
        })
    
    # Kiểm tra HWID có khớp không
    if license_data['hwid'] != hwid:
        return jsonify({
            'valid': False,
            'message': 'HWID mismatch. This license is bound to another device.'
        })
    
    # Cập nhật thời gian check cuối
    cursor.execute('''
        UPDATE licenses 
        SET last_check = ?
        WHERE license_key = ?
    ''', (datetime.now(), license_key))
    db.commit()
    
    return jsonify({
        'valid': True,
        'message': 'License is valid',
        'expires_at': license_data['expires_at']
    })

@app.route('/api/client/check', methods=['POST'])
def check_license():
    data = request.json
    license_key = data.get('license_key')
    hwid = data.get('hwid')
    
    if not license_key or not hwid:
        return jsonify({'valid': False, 'message': 'License key and HWID are required'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('SELECT * FROM licenses WHERE license_key = ? AND hwid = ?', (license_key, hwid))
    license_data = cursor.fetchone()
    
    if not license_data:
        return jsonify({'valid': False, 'message': 'Invalid license or HWID'})
    
    return jsonify({
        'valid': license_data['status'] == 'active' and not license_data['is_locked'],
        'status': license_data['status'],
        'is_locked': bool(license_data['is_locked']),
        'lock_reason': license_data['lock_reason'],
        'expires_at': license_data['expires_at']
    })

# ============== API KEY MANAGEMENT ==============
@app.route('/api/admin/apikeys', methods=['GET'])
def get_api_keys():
    if not validate_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM api_keys ORDER BY created_at DESC")
    
    keys = []
    for row in cursor.fetchall():
        key_data = dict(row)
        key_data['key_masked'] = key_data['key'][:8] + '...' + key_data['key'][-4:]
        keys.append(key_data)
    
    return jsonify({'api_keys': keys})

@app.route('/api/admin/apikeys/create', methods=['POST'])
def create_api_key():
    if not validate_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    data = request.json
    name = data.get('name', 'New API Key')
    
    api_key = f"sk_{uuid.uuid4().hex[:32]}"
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute(
        "INSERT INTO api_keys (key, name, permissions) VALUES (?, ?, ?)",
        (api_key, name, 'all')
    )
    db.commit()
    
    return jsonify({
        'success': True,
        'api_key': api_key,
        'name': name,
        'message': 'API key created successfully'
    })

# ============== STATISTICS ==============
@app.route('/api/admin/stats', methods=['GET'])
def get_stats():
    if not validate_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT COUNT(*) as total FROM licenses")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) as active FROM licenses WHERE status = 'active'")
    active = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) as locked FROM licenses WHERE is_locked = 1")
    locked = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) as expired FROM licenses WHERE expires_at < datetime('now')")
    expired = cursor.fetchone()[0]
    
    return jsonify({
        'total_licenses': total,
        'active_licenses': active,
        'locked_licenses': locked,
        'expired_licenses': expired
    })

# ============== INITIALIZE & RUN ==============
# Khởi tạo database khi ứng dụng start
with app.app_context():
    init_db()

if __name__ == '__main__':
    # Lấy port từ environment variable (Render cung cấp)
    port = int(os.environ.get('PORT', 8080))
    
    # Khởi động ứng dụng
    app.run(host='0.0.0.0', port=port, debug=False)
