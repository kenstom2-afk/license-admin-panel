import os
import sqlite3
import json
import uuid
import hashlib
import re
import csv
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, g, send_file, send_from_directory
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
        
        # Tạo bảng licenses với các cột mới
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
                key_type TEXT DEFAULT 'auto',
                prefix TEXT DEFAULT 'LIC',
                format_type TEXT DEFAULT 'standard',
                allow_multiple_devices INTEGER DEFAULT 0,
                auto_activate INTEGER DEFAULT 1
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # Tạo bảng license_activations (cho multiple devices)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS license_activations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_key TEXT NOT NULL,
                hwid TEXT NOT NULL,
                device_info TEXT,
                activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP,
                FOREIGN KEY (license_key) REFERENCES licenses (license_key)
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
            print("✅ Default admin user created: admin / admin123")
        
        # ĐẢM BẢO LUÔN CÓ ÍT NHẤT 1 API KEY
        cursor.execute("SELECT COUNT(*) as count FROM api_keys")
        if cursor.fetchone()[0] == 0:
            default_api_key = f"sk_{uuid.uuid4().hex[:32]}"
            cursor.execute(
                "INSERT INTO api_keys (key, name, permissions, is_active) VALUES (?, ?, ?, ?)",
                (default_api_key, "Default API Key", "all", 1)
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
    cursor.execute("SELECT * FROM api_keys WHERE key = ? AND is_active = 1", (api_key,))
    api_key_data = cursor.fetchone()
    
    if api_key_data:
        # Update last used timestamp
        cursor.execute("UPDATE api_keys SET last_used = ? WHERE key = ?", (datetime.now(), api_key))
        db.commit()
        return True
    
    return False

def generate_license_key(prefix="LIC", format_type="standard"):
    """Generate license key with different formats"""
    if format_type == "compact":
        # Compact: LIC-XXXXXXXXXXXX
        return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"
    elif format_type == "extended":
        # Extended: LIC-XXXX-XXXX-XXXX-XXXX
        uuid_str = uuid.uuid4().hex.upper()
        return f"{prefix}-{uuid_str[:4]}-{uuid_str[4:8]}-{uuid_str[8:12]}-{uuid_str[12:16]}"
    else:
        # Standard: LIC-XXXX-XXXX-XXXX
        uuid_str = uuid.uuid4().hex.upper()
        return f"{prefix}-{uuid_str[:4]}-{uuid_str[4:8]}-{uuid_str[8:12]}"

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

def get_license_status(license_data):
    """Determine license status"""
    if license_data['is_locked']:
        return 'locked'
    
    if license_data['status'] == 'revoked':
        return 'revoked'
    
    if license_data['expires_at']:
        expires_at = license_data['expires_at']
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        
        if expires_at < datetime.now():
            return 'expired'
    
    return license_data['status']

# ============== ROUTES ==============
@app.route('/')
def index():
    """Trả về file admin.html"""
    try:
        return send_file('admin.html')
    except:
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>LicenseMaster Pro</title>
            <style>
                body { font-family: Inter, Arial; padding: 20px; background: #0f172a; color: white; }
                .container { max-width: 800px; margin: 0 auto; }
                .btn { background: #3a86ff; color: white; padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer; }
                .card { background: #1e293b; padding: 20px; border-radius: 12px; margin: 20px 0; border: 1px solid #334155; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>📋 LicenseMaster Pro</h1>
                <div class="card">
                    <p>Professional License Management System is running!</p>
                    <p><a href="/api/admin/debug" target="_blank" style="color: #00bbf9;">Check System Status</a></p>
                    <p><button class="btn" onclick="window.location.reload()">Reload Admin Panel</button></p>
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
    api_key_count = cursor.execute("SELECT COUNT(*) FROM api_keys WHERE is_active = 1").fetchone()[0]
    license_count = cursor.execute("SELECT COUNT(*) FROM licenses").fetchone()[0]
    
    # Get API key info
    cursor.execute("SELECT key, name, last_used FROM api_keys WHERE is_active = 1 ORDER BY created_at DESC LIMIT 1")
    api_key_row = cursor.fetchone()
    api_key_info = None
    if api_key_row:
        api_key_info = {
            'name': api_key_row['name'],
            'key_masked': api_key_row['key'][:8] + '...' + api_key_row['key'][-4:],
            'last_used': api_key_row['last_used']
        }
    
    # Get system stats
    active_licenses = cursor.execute("SELECT COUNT(*) FROM licenses WHERE status = 'active' AND is_locked = 0").fetchone()[0]
    locked_licenses = cursor.execute("SELECT COUNT(*) FROM licenses WHERE is_locked = 1").fetchone()[0]
    
    return jsonify({
        'status': 'online',
        'version': '2.0.0',
        'database_tables': tables,
        'counts': {
            'admin_users': admin_count,
            'api_keys': api_key_count,
            'licenses': license_count,
            'active_licenses': active_licenses,
            'locked_licenses': locked_licenses
        },
        'api_key_info': api_key_info,
        'message': 'LicenseMaster Pro is running correctly'
    })

@app.route('/api/admin/setup', methods=['POST'])
def setup_system():
    """Setup system with default API key"""
    data = request.json
    action = data.get('action', 'create_key')
    
    db = get_db()
    cursor = db.cursor()
    
    if action == 'create_key':
        name = data.get('name', 'Auto-generated Key')
        new_api_key = f"sk_{uuid.uuid4().hex[:32]}"
        cursor.execute(
            "INSERT INTO api_keys (key, name, permissions, is_active) VALUES (?, ?, ?, ?)",
            (new_api_key, name, "all", 1)
        )
        db.commit()
        
        return jsonify({
            'success': True,
            'api_key': new_api_key,
            'name': name,
            'message': 'New API key created successfully. Save this key!'
        })
    
    elif action == 'reset_admin':
        # Reset admin password
        password_hash = argon2_hasher.hash("Anhhuykute123")
        cursor.execute(
            "INSERT OR REPLACE INTO admin_users (username, password_hash) VALUES (?, ?)",
            ("admin", password_hash)
        )
        db.commit()
        
        return jsonify({
            'success': True,
            'message': 'Admin password reset to: admin123'
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
                cursor.execute("SELECT key FROM api_keys WHERE is_active = 1 LIMIT 1")
                api_key_row = cursor.fetchone()
                
                if api_key_row:
                    api_key = api_key_row['key']
                else:
                    # Create new API key if none exists
                    api_key = f"sk_{uuid.uuid4().hex[:32]}"
                    cursor.execute(
                        "INSERT INTO api_keys (key, name, permissions, is_active) VALUES (?, ?, ?, ?)",
                        (api_key, "Auto-generated for login", "all", 1)
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
        # Calculate actual status
        license_data['actual_status'] = get_license_status(license_data)
        licenses.append(license_data)
    
    return jsonify({'licenses': licenses})

@app.route('/api/admin/licenses/create', methods=['POST'])
def create_license():
    """Create new license với nhiều options"""
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
    prefix = data.get('prefix', 'LIC').upper().replace(' ', '-')
    format_type = data.get('format_type', 'standard')
    key_type = data.get('key_type', 'auto')
    allow_multiple_devices = bool(data.get('allow_multiple_devices', False))
    auto_activate = bool(data.get('auto_activate', True))
    
    # Determine which key to use
    if custom_key:
        # Validate custom key
        is_valid, message = validate_custom_key_format(custom_key)
        if not is_valid:
            return jsonify({'success': False, 'error': f'Invalid custom key: {message}'}), 400
        license_key = custom_key.upper()
        key_type = 'custom'
    else:
        # Generate auto key based on type
        if key_type == 'bulk' or 'count' in data:
            # This should use the bulk endpoint
            return jsonify({'success': False, 'error': 'Use /bulk endpoint for bulk generation'}), 400
        
        license_key = generate_license_key(prefix, format_type)
    
    expires_at = datetime.now() + timedelta(days=days_valid)
    
    db = get_db()
    cursor = db.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO licenses (license_key, expires_at, note, status, key_type, prefix, 
                                 format_type, allow_multiple_devices, auto_activate)
            VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?)
        ''', (license_key, expires_at, note, key_type, prefix, format_type, 
              int(allow_multiple_devices), int(auto_activate)))
        
        db.commit()
        return jsonify({
            'success': True,
            'license_key': license_key,
            'expires_at': expires_at.isoformat(),
            'message': 'License created successfully',
            'key_type': key_type,
            'prefix': prefix,
            'format_type': format_type
        })
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': 'License key already exists'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/admin/licenses/bulk', methods=['POST'])
def bulk_create_licenses():
    """Create multiple licenses với prefix"""
    if not validate_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    data = request.json
    if not data:
        return jsonify({'success': False, 'error': 'No data received'}), 400
    
    # Get parameters
    try:
        count = int(data.get('count', 5))
        days_valid = int(data.get('days_valid', 30))
        prefix = data.get('prefix', 'BULK').upper().replace(' ', '-')
        note = data.get('note', 'Bulk generated')
        format_type = data.get('format_type', 'standard')
        allow_multiple_devices = bool(data.get('allow_multiple_devices', False))
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
            # Generate key với prefix và format
            if format_type == "compact":
                unique_part = f"{uuid.uuid4().hex[:12].upper()}"
                license_key = f"{prefix}-{unique_part}"
            elif format_type == "extended":
                uuid_str = uuid.uuid4().hex.upper()
                license_key = f"{prefix}-{uuid_str[:4]}-{uuid_str[4:8]}-{uuid_str[8:12]}-{uuid_str[12:16]}"
            else:
                # Standard format
                uuid_str = uuid.uuid4().hex.upper()
                license_key = f"{prefix}-{uuid_str[:4]}-{uuid_str[4:8]}-{uuid_str[8:12]}"
            
            expires_at = datetime.now() + timedelta(days=days_valid)
            individual_note = f"{note} #{i+1}" if note else f"Bulk generated #{i+1}"
            
            # Insert into database
            cursor.execute('''
                INSERT INTO licenses (license_key, expires_at, note, status, key_type, prefix, 
                                     format_type, allow_multiple_devices)
                VALUES (?, ?, ?, 'active', 'bulk', ?, ?, ?)
            ''', (license_key, expires_at, individual_note, prefix, format_type, 
                  int(allow_multiple_devices)))
            
            created_keys.append({
                'key': license_key,
                'expires_at': expires_at.isoformat(),
                'note': individual_note
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
    
    # Also delete from activations table
    cursor.execute('DELETE FROM license_activations WHERE license_key = ?', (license_key,))
    
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

@app.route('/api/admin/licenses/unlock', methods=['POST'])
def unlock_license():
    if not validate_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    data = request.json
    license_key = data.get('license_key')
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('''
        UPDATE licenses 
        SET is_locked = 0,
            lock_reason = NULL,
            status = 'active'
        WHERE license_key = ?
    ''', (license_key,))
    
    db.commit()
    
    if cursor.rowcount > 0:
        return jsonify({
            'success': True,
            'message': 'License unlocked successfully'
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
    
    # Delete from activations first
    cursor.execute('DELETE FROM license_activations WHERE license_key = ?', (license_key,))
    # Then delete from licenses
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

@app.route('/api/admin/licenses/export', methods=['GET'])
def export_licenses():
    """Export licenses to CSV"""
    if not validate_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        SELECT license_key, hwid, status, created_at, expires_at, 
               key_type, note, is_locked, lock_reason
        FROM licenses 
        ORDER BY created_at DESC
    ''')
    
    licenses = []
    for row in cursor.fetchall():
        license_data = dict(row)
        license_data['actual_status'] = get_license_status(license_data)
        licenses.append(license_data)
    
    # Create CSV content
    csv_content = []
    csv_content.append(['License Key', 'HWID', 'Status', 'Created At', 'Expires At', 
                       'Key Type', 'Note', 'Is Locked', 'Lock Reason'])
    
    for license in licenses:
        csv_content.append([
            license['license_key'],
            license['hwid'] or '',
            license['actual_status'],
            license['created_at'],
            license['expires_at'] or '',
            license['key_type'],
            license['note'] or '',
            'Yes' if license['is_locked'] else 'No',
            license['lock_reason'] or ''
        ])
    
    # Create CSV file
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerows(csv_content)
    
    return jsonify({
        'success': True,
        'csv_content': output.getvalue(),
        'count': len(licenses),
        'message': f'Exported {len(licenses)} licenses'
    })

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
    ''', (license_key,))
    
    license_data = cursor.fetchone()
    
    if not license_data:
        return jsonify({
            'valid': False,
            'message': 'Invalid license key'
        })
    
    license_dict = dict(license_data)
    
    # Kiểm tra nếu bị locked
    if license_dict['is_locked']:
        return jsonify({
            'valid': False,
            'message': f'License is locked: {license_dict.get("lock_reason", "Unknown reason")}'
        })
    
    # Kiểm tra hạn sử dụng
    expires_at = license_dict['expires_at']
    if expires_at:
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        
        if expires_at < datetime.now():
            return jsonify({
                'valid': False,
                'message': 'License has expired'
            })
    
    # Kiểm tra multiple devices
    allow_multiple = bool(license_dict['allow_multiple_devices'])
    
    if not allow_multiple:
        # Single device mode
        if not license_dict['hwid']:
            # First activation
            cursor.execute('''
                UPDATE licenses 
                SET hwid = ?,
                    device_info = ?,
                    last_check = ?
                WHERE license_key = ?
            ''', (hwid, device_info, datetime.now(), license_key))
            db.commit()
            
            # Record activation
            cursor.execute('''
                INSERT INTO license_activations (license_key, hwid, device_info)
                VALUES (?, ?, ?)
            ''', (license_key, hwid, device_info))
            db.commit()
            
            return jsonify({
                'valid': True,
                'message': 'License activated successfully',
                'expires_at': license_dict['expires_at'],
                'first_activation': True
            })
        
        # Check HWID match
        if license_dict['hwid'] != hwid:
            return jsonify({
                'valid': False,
                'message': 'HWID mismatch. This license is bound to another device.'
            })
        
        # Update last check
        cursor.execute('''
            UPDATE licenses 
            SET last_check = ?
            WHERE license_key = ?
        ''', (datetime.now(), license_key))
        db.commit()
        
        # Update activation last used
        cursor.execute('''
            UPDATE license_activations 
            SET last_used = ?
            WHERE license_key = ? AND hwid = ?
        ''', (datetime.now(), license_key, hwid))
        db.commit()
        
        return jsonify({
            'valid': True,
            'message': 'License is valid',
            'expires_at': license_dict['expires_at'],
            'first_activation': False
        })
    else:
        # Multiple devices mode
        # Check if this HWID is already activated
        cursor.execute('''
            SELECT * FROM license_activations 
            WHERE license_key = ? AND hwid = ?
        ''', (license_key, hwid))
        
        existing_activation = cursor.fetchone()
        
        if not existing_activation:
            # New activation for this device
            cursor.execute('''
                INSERT INTO license_activations (license_key, hwid, device_info)
                VALUES (?, ?, ?)
            ''', (license_key, hwid, device_info))
            
            # Update license's last check and HWID (for backward compatibility)
            cursor.execute('''
                UPDATE licenses 
                SET hwid = ?,
                    device_info = ?,
                    last_check = ?
                WHERE license_key = ?
            ''', (hwid, device_info, datetime.now(), license_key))
        else:
            # Update last used
            cursor.execute('''
                UPDATE license_activations 
                SET last_used = ?
                WHERE license_key = ? AND hwid = ?
            ''', (datetime.now(), license_key, hwid))
        
        db.commit()
        
        # Count activations
        cursor.execute('SELECT COUNT(*) FROM license_activations WHERE license_key = ?', (license_key,))
        activation_count = cursor.fetchone()[0]
        
        return jsonify({
            'valid': True,
            'message': f'License is valid (Device {activation_count})',
            'expires_at': license_dict['expires_at'],
            'device_count': activation_count,
            'first_activation': not bool(existing_activation)
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
    
    cursor.execute('SELECT * FROM licenses WHERE license_key = ?', (license_key,))
    license_data = cursor.fetchone()
    
    if not license_data:
        return jsonify({'valid': False, 'message': 'Invalid license key'})
    
    license_dict = dict(license_data)
    
    # Check if multiple devices allowed
    if bool(license_dict['allow_multiple_devices']):
        cursor.execute('SELECT * FROM license_activations WHERE license_key = ? AND hwid = ?', (license_key, hwid))
        activation = cursor.fetchone()
        hwid_match = bool(activation)
    else:
        hwid_match = license_dict['hwid'] == hwid
    
    actual_status = get_license_status(license_dict)
    
    return jsonify({
        'valid': hwid_match and actual_status == 'active',
        'status': actual_status,
        'is_locked': bool(license_dict['is_locked']),
        'lock_reason': license_dict['lock_reason'],
        'expires_at': license_dict['expires_at'],
        'hwid_match': hwid_match
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
        "INSERT INTO api_keys (key, name, permissions, is_active) VALUES (?, ?, ?, ?)",
        (api_key, name, 'all', 1)
    )
    db.commit()
    
    return jsonify({
        'success': True,
        'api_key': api_key,
        'name': name,
        'message': 'API key created successfully'
    })

@app.route('/api/admin/apikeys/regenerate', methods=['POST'])
def regenerate_api_key():
    if not validate_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    data = request.json
    old_key = data.get('old_key')
    
    db = get_db()
    cursor = db.cursor()
    
    # Deactivate old key
    cursor.execute("UPDATE api_keys SET is_active = 0 WHERE key = ?", (old_key,))
    
    # Create new key
    new_key = f"sk_{uuid.uuid4().hex[:32]}"
    cursor.execute(
        "INSERT INTO api_keys (key, name, permissions, is_active) VALUES (?, ?, ?, ?)",
        (new_key, 'Regenerated Key', 'all', 1)
    )
    
    db.commit()
    
    return jsonify({
        'success': True,
        'new_api_key': new_key,
        'message': 'API key regenerated successfully'
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
    
    cursor.execute("SELECT COUNT(*) as active FROM licenses WHERE status = 'active' AND is_locked = 0")
    active = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) as locked FROM licenses WHERE is_locked = 1")
    locked = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) as expired FROM licenses WHERE expires_at < datetime('now')")
    expired = cursor.fetchone()[0]
    
    # Count by key type
    cursor.execute("SELECT key_type, COUNT(*) as count FROM licenses GROUP BY key_type")
    key_types = {row['key_type']: row['count'] for row in cursor.fetchall()}
    
    # Recent activity
    cursor.execute("SELECT COUNT(*) as today FROM licenses WHERE date(created_at) = date('now')")
    today = cursor.fetchone()[0]
    
    # Multiple devices count
    cursor.execute("SELECT COUNT(DISTINCT license_key) as multi_device FROM licenses WHERE allow_multiple_devices = 1")
    multi_device = cursor.fetchone()[0]
    
    return jsonify({
        'total_licenses': total,
        'active_licenses': active,
        'locked_licenses': locked,
        'expired_licenses': expired,
        'key_types': key_types,
        'today_created': today,
        'multi_device_licenses': multi_device
    })

@app.route('/api/admin/licenses/search', methods=['POST'])
def search_licenses():
    if not validate_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    data = request.json
    query = data.get('query', '')
    
    if not query:
        return jsonify({'error': 'Search query required'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('''
        SELECT * FROM licenses 
        WHERE license_key LIKE ? OR hwid LIKE ? OR note LIKE ?
        ORDER BY created_at DESC
    ''', (f'%{query}%', f'%{query}%', f'%{query}%'))
    
    licenses = []
    for row in cursor.fetchall():
        license_data = dict(row)
        license_data['actual_status'] = get_license_status(license_data)
        licenses.append(license_data)
    
    return jsonify({
        'success': True,
        'count': len(licenses),
        'licenses': licenses
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
