import os
import sqlite3
import json
import uuid
import hashlib
import re
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, g, send_file
from flask_cors import CORS
from cryptography.fernet import Fernet
import base64
import argon2

app = Flask(__name__, static_folder='.', static_url_path='')
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
                lock_reason TEXT,
                key_type TEXT DEFAULT 'auto'
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
            password_hash = argon2_hasher.hash("Ccmscnlk123")
            cursor.execute(
                "INSERT INTO admin_users (username, password_hash) VALUES (?, ?)",
                ("admin", password_hash)
            )
            print("✅ Default admin user created: admin / Admin123")
        
        # ĐẢM BẢO LUÔN CÓ ÍT NHẤT 1 API KEY
        cursor.execute("SELECT COUNT(*) as count FROM api_keys")
        if cursor.fetchone()[0] == 0:
            default_api_key = f"sk_{uuid.uuid4().hex[:32]}"
            cursor.execute(
                "INSERT INTO api_keys (key, name, permissions) VALUES (?, ?, ?)",
                (default_api_key, "Default API Key", "all")
            )
            print(f"✅ Default API Key created: {default_api_key[:12]}...")
        
        db.commit()
        print("✅ Database initialized successfully!")

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

def validate_custom_key_format(key):
    """Validate custom license key format"""
    # Basic validation
    if len(key) < 8:
        return False, "Key must be at least 8 characters"
    
    # Only allow uppercase letters, numbers, and dashes
    if not re.match(r'^[A-Z0-9-]+$', key):
        return False, "Only uppercase letters, numbers, and dashes allowed"
    
    # Check if key already exists
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM licenses WHERE license_key = ?", (key,))
    if cursor.fetchone()[0] > 0:
        return False, "This key already exists"
    
    return True, "Valid key format"

# ============== ROUTES ==============
@app.route('/')
def index():
    """Trả về file admin.html"""
    try:
        return send_file('admin.html')
    except:
        # Fallback nếu không có file
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>License Admin</title>
            <style>
                body { font-family: Arial; padding: 20px; background: #0f172a; color: white; }
                .container { max-width: 800px; margin: 0 auto; }
                .btn { background: #4361ee; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
                .card { background: #1e293b; padding: 20px; border-radius: 10px; margin: 20px 0; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>📋 License Admin Panel</h1>
                <div class="card">
                    <p>System is running! API endpoints are active.</p>
                    <p><a href="/api/admin/debug" target="_blank" style="color: #4cc9f0;">Check System Status</a></p>
                    <p><button class="btn" onclick="window.location.reload()">Reload Page</button></p>
                </div>
            </div>
        </body>
        </html>
        '''

@app.route('/admin')
def admin():
    return index()

# ============== DEBUG & SETUP ENDPOINTS ==============
@app.route('/api/admin/debug', methods=['GET'])
def debug_info():
    """Debug endpoint to check system status"""
    db = get_db()
    cursor = db.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row['name'] for row in cursor.fetchall()]
    
    # Count records
    admin_count = cursor.execute("SELECT COUNT(*) FROM admin_users").fetchone()[0]
    api_key_count = cursor.execute("SELECT COUNT(*) FROM api_keys").fetchone()[0]
    license_count = cursor.execute("SELECT COUNT(*) FROM licenses").fetchone()[0]
    
    # Get first API key (masked)
    cursor.execute("SELECT key, name FROM api_keys LIMIT 1")
    api_key_row = cursor.fetchone()
    api_key_info = None
    if api_key_row:
        api_key_info = {
            'name': api_key_row['name'],
            'key_masked': api_key_row['key'][:8] + '...' + api_key_row['key'][-4:]
        }
    
    return jsonify({
        'status': 'online',
        'database_tables': tables,
        'counts': {
            'admin_users': admin_count,
            'api_keys': api_key_count,
            'licenses': license_count
        },
        'api_key_info': api_key_info,
        'message': 'System is running correctly' if api_key_count > 0 else 'No API keys found!'
    })

@app.route('/api/admin/setup', methods=['POST'])
def setup_system():
    """Setup system with default API key"""
    data = request.json
    action = data.get('action', 'create_key')
    
    db = get_db()
    cursor = db.cursor()
    
    if action == 'create_key':
        # Create new API key
        new_api_key = f"sk_{uuid.uuid4().hex[:32]}"
        cursor.execute(
            "INSERT INTO api_keys (key, name, permissions) VALUES (?, ?, ?)",
            (new_api_key, "Auto-generated Key", "all")
        )
        db.commit()
        
        return jsonify({
            'success': True,
            'api_key': new_api_key,
            'message': 'New API key created successfully. Save this key!'
        })
    
    elif action == 'reset_admin':
        # Reset admin password
        password_hash = argon2_hasher.hash("Ccmscnlk")
        cursor.execute(
            "INSERT OR REPLACE INTO admin_users (username, password_hash) VALUES (?, ?)",
            ("admin", password_hash)
        )
        db.commit()
        
        return jsonify({
            'success': True,
            'message': 'Admin password reset to: Anhhuy'
        })
    
    return jsonify({'success': False, 'message': 'Invalid action'})

# ============== ADMIN API ==============
@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    """Login endpoint - returns API key directly"""
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
                # Get or create API key
                cursor.execute("SELECT key FROM api_keys LIMIT 1")
                api_key_row = cursor.fetchone()
                
                if api_key_row:
                    api_key = api_key_row['key']
                else:
                    # Create new API key if none exists
                    api_key = f"sk_{uuid.uuid4().hex[:32]}"
                    cursor.execute(
                        "INSERT INTO api_keys (key, name, permissions) VALUES (?, ?, ?)",
                        (api_key, "Auto-generated for login", "all")
                    )
                    db.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Login successful',
                    'username': username,
                    'api_key': api_key,  # Trả về API key luôn
                    'api_key_masked': api_key[:8] + '...' + api_key[-4:]
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
        licenses.append(license_data)
    
    return jsonify({'licenses': licenses})

@app.route('/api/admin/licenses/create', methods=['POST'])
def create_license():
    """Create new license với option custom key"""
    if not validate_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    data = request.json
    if not data:
        return jsonify({'success': False, 'error': 'No data received'}), 400
    
    # Get parameters
    try:
        days_valid = int(data.get('days_valid', 30))
    except (ValueError, TypeError):
        days_valid = 30
    
    # Ensure valid range
    if days_valid <= 0:
        days_valid = 30
    if days_valid > 3650:
        days_valid = 3650
    
    note = data.get('note', '')
    custom_key = data.get('custom_key', '')
    key_type = 'custom' if custom_key else 'auto'
    
    # Determine which key to use
    if custom_key:
        # Validate custom key
        is_valid, message = validate_custom_key_format(custom_key)
        if not is_valid:
            return jsonify({'success': False, 'error': f'Invalid custom key: {message}'}), 400
        license_key = custom_key.upper()
    else:
        # Generate auto key
        license_key = generate_license_key()
    
    expires_at = datetime.now() + timedelta(days=days_valid)
    
    db = get_db()
    cursor = db.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO licenses (license_key, expires_at, note, status, key_type)
            VALUES (?, ?, ?, 'active', ?)
        ''', (license_key, expires_at, note, key_type))
        
        db.commit()
        return jsonify({
            'success': True,
            'license_key': license_key,
            'expires_at': expires_at.isoformat(),
            'message': 'License created successfully',
            'key_type': key_type
        })
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': 'License key already exists'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/admin/licenses/bulk', methods=['POST'])
def bulk_create_licenses():
    """Create multiple licenses with prefix"""
    if not validate_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    data = request.json
    if not data:
        return jsonify({'success': False, 'error': 'No data received'}), 400
    
    # Get parameters
    try:
        count = int(data.get('count', 5))
        days_valid = int(data.get('days_valid', 30))
        prefix = data.get('prefix', 'VIP').upper().replace(' ', '-')
        note = data.get('note', 'Bulk generated')
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid parameters'}), 400
    
    # Validate
    if count < 1 or count > 100:
        return jsonify({'success': False, 'error': 'Count must be between 1-100'}), 400
    if days_valid <= 0 or days_valid > 3650:
        return jsonify({'success': False, 'error': 'Invalid days valid'}), 400
    
    created_keys = []
    db = get_db()
    cursor = db.cursor()
    
    try:
        for i in range(count):
            # Generate key with prefix
            unique_part = f"{uuid.uuid4().hex[:4].upper()}-{uuid.uuid4().hex[:4].upper()}"
            license_key = f"{prefix}-{unique_part}"
            expires_at = datetime.now() + timedelta(days=days_valid)
            
            # Insert into database
            cursor.execute('''
                INSERT INTO licenses (license_key, expires_at, note, status, key_type)
                VALUES (?, ?, ?, 'active', 'bulk')
            ''', (license_key, expires_at, f"{note} #{i+1}", 'active'))
            
            created_keys.append({
                'key': license_key,
                'expires_at': expires_at.isoformat()
            })
        
        db.commit()
        return jsonify({
            'success': True,
            'count': count,
            'keys': created_keys,
            'message': f'Successfully created {count} license(s)'
        })
        
    except Exception as e:
        db.rollback()
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
    
    # Count by key type
    cursor.execute("SELECT key_type, COUNT(*) as count FROM licenses GROUP BY key_type")
    key_types = {row['key_type']: row['count'] for row in cursor.fetchall()}
    
    return jsonify({
        'total_licenses': total,
        'active_licenses': active,
        'locked_licenses': locked,
        'expired_licenses': expired,
        'key_types': key_types
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
