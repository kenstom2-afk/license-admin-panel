from flask import Flask, render_template, jsonify, request, session, redirect, url_for, send_from_directory
from flask_cors import CORS
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
import sqlite3
import os
import json
import logging
import re

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, 
            static_folder='static',
            static_url_path='/static',
            template_folder='templates')

app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['DATABASE_PATH'] = os.path.join(os.path.dirname(__file__), 'database.db')
CORS(app)

# ============ DATABASE FUNCTIONS ============

def get_db_connection():
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    logger.info("Initializing database...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Bảng admin users
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Bảng licenses
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE NOT NULL,
            product TEXT NOT NULL,
            owner TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            max_devices INTEGER DEFAULT 1,
            notes TEXT,
            hwid_lock TEXT,
            ip_lock TEXT,
            total_activations INTEGER DEFAULT 0,
            last_active TIMESTAMP,
            custom_days INTEGER DEFAULT 30,
            auto_renew BOOLEAN DEFAULT FALSE,
            reset_count INTEGER DEFAULT 0,
            last_reset TIMESTAMP
        )
    ''')
    
    # Bảng API keys
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_key TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used TIMESTAMP
        )
    ''')
    
    conn.commit()
    
    # Tạo admin mặc định
    cursor.execute('SELECT * FROM admin_users WHERE username = ?', ('admin',))
    admin = cursor.fetchone()
    
    if not admin:
        hashed_password = hash_password("Anhhuy123")
        cursor.execute(
            'INSERT INTO admin_users (username, password) VALUES (?, ?)',
            ('admin', hashed_password)
        )
        logger.info("✅ Default admin user created: admin / Anhhuy123")
    
    # Tạo API key mặc định
    cursor.execute('SELECT * FROM api_keys')
    api_key = cursor.fetchone()
    
    if not api_key:
        api_key_value = f"sk_{secrets.token_hex(16)}"
        cursor.execute(
            'INSERT INTO api_keys (api_key, name) VALUES (?, ?)',
            (api_key_value, 'Default API Key')
        )
        logger.info(f"✅ Default API Key created: {api_key_value}")
    
    conn.commit()
    conn.close()
    logger.info("✅ Database initialized successfully!")

# Khởi tạo database khi app start
with app.app_context():
    try:
        init_db()
    except Exception as e:
        logger.error(f"Database init error: {e}")

# ============ HELPER FUNCTIONS ============

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

# ============ ROUTES ============

@app.route('/')
def index():
    return redirect('/login')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/admin')
def admin_dashboard():
    if 'logged_in' not in session:
        return redirect('/login')
    return render_template('admin.html')

# ============ STATIC FILES ============

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico', mimetype='image/vnd.microsoft.icon')

# ============ ADMIN API ============

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Invalid request'}), 400
            
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'success': False, 'message': 'Vui lòng nhập đầy đủ thông tin'}), 400
        
        hashed_password = hash_password(password)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM admin_users WHERE username = ? AND password = ?',
            (username, hashed_password)
        )
        admin = cursor.fetchone()
        conn.close()
        
        if admin:
            session['logged_in'] = True
            session['username'] = username
            session['admin_id'] = admin['id']
            
            return jsonify({
                'success': True, 
                'message': 'Đăng nhập thành công',
                'redirect': '/admin'
            })
        else:
            return jsonify({'success': False, 'message': 'Tên đăng nhập hoặc mật khẩu không đúng'}), 401
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'success': False, 'message': 'Lỗi server'}), 500

@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Đã đăng xuất'})

@app.route('/api/admin/stats')
@login_required
def get_stats():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM licenses')
        total_licenses = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM licenses WHERE status = "active"')
        active_licenses = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM licenses WHERE status = "inactive"')
        inactive_licenses = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM licenses WHERE status = "expired"')
        expired_licenses = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM api_keys WHERE status = "active"')
        active_api_keys = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'total_licenses': total_licenses,
                'active_licenses': active_licenses,
                'inactive_licenses': inactive_licenses,
                'expired_licenses': expired_licenses,
                'active_api_keys': active_api_keys,
                'today_licenses': 0,
                'expiring_soon': 0
            }
        })
    except Exception as e:
        logger.error(f"Stats error: {str(e)}")
        return jsonify({'success': False, 'message': 'Lỗi khi lấy thống kê'}), 500

@app.route('/api/admin/licenses')
@login_required
def get_licenses():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM licenses ORDER BY created_at DESC')
        rows = cursor.fetchall()
        conn.close()
        
        licenses = []
        for row in rows:
            # Tính số ngày còn lại
            days_left = None
            if row['expires_at']:
                try:
                    expires = datetime.strptime(row['expires_at'], '%Y-%m-%d %H:%M:%S')
                    days_left = max(0, (expires - datetime.now()).days)
                except:
                    days_left = 0
            
            licenses.append({
                'id': row['id'],
                'license_key': row['license_key'],
                'product': row['product'],
                'owner': row['owner'] or '',
                'status': row['status'],
                'created_at': row['created_at'],
                'expires_at': row['expires_at'],
                'max_devices': row['max_devices'],
                'notes': row['notes'],
                'hwid_lock': row['hwid_lock'],
                'ip_lock': row['ip_lock'],
                'total_activations': row['total_activations'],
                'custom_days': row['custom_days'],
                'auto_renew': bool(row['auto_renew']),
                'days_left': days_left
            })
        
        return jsonify({'success': True, 'data': licenses})
    except Exception as e:
        logger.error(f"Get licenses error: {str(e)}")
        return jsonify({'success': False, 'message': 'Lỗi khi lấy danh sách license'}), 500

@app.route('/api/admin/licenses/create', methods=['POST'])
@login_required
def create_license():
    try:
        data = request.get_json()
        
        # Validate input
        product = data.get('product', '').strip()
        if not product:
            return jsonify({'success': False, 'message': 'Vui lòng nhập tên sản phẩm'}), 400
        
        custom_key = data.get('custom_key', '').strip()
        if custom_key:
            # Check if custom key already exists
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM licenses WHERE license_key = ?', (custom_key.upper(),))
            if cursor.fetchone():
                conn.close()
                return jsonify({'success': False, 'message': 'License key đã tồn tại'}), 400
        
        # Generate license key
        if custom_key:
            license_key = custom_key.upper()
        else:
            license_key = f"LIC-{secrets.token_hex(8).upper()}"
        
        # Calculate expiry date
        custom_days = int(data.get('custom_days', 30))
        expires_at = (datetime.now() + timedelta(days=custom_days)).strftime('%Y-%m-%d %H:%M:%S')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO licenses (
                license_key, product, owner, status, expires_at, max_devices, 
                notes, hwid_lock, ip_lock, custom_days, auto_renew
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            license_key,
            product,
            data.get('owner', '').strip(),
            data.get('status', 'active'),
            expires_at,
            int(data.get('max_devices', 1)),
            data.get('notes', '').strip(),
            data.get('hwid_lock', '').strip(),
            data.get('ip_lock', '').strip(),
            custom_days,
            bool(data.get('auto_renew', False))
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': 'Tạo license thành công',
            'license_key': license_key,
            'expires_at': expires_at
        })
    except Exception as e:
        logger.error(f"Create license error: {str(e)}")
        return jsonify({'success': False, 'message': 'Lỗi khi tạo license'}), 500

@app.route('/api/admin/licenses/delete/<int:license_id>', methods=['POST'])
@login_required
def delete_license(license_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM licenses WHERE id = ?', (license_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Đã xóa license'})
    except Exception as e:
        logger.error(f"Delete license error: {str(e)}")
        return jsonify({'success': False, 'message': 'Lỗi khi xóa license'}), 500

@app.route('/api/admin/apikeys')
@login_required
def get_apikeys():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM api_keys ORDER BY created_at DESC')
        rows = cursor.fetchall()
        conn.close()
        
        apikeys = []
        for row in rows:
            apikeys.append({
                'id': row['id'],
                'key': row['api_key'],
                'name': row['name'],
                'status': row['status'],
                'created_at': row['created_at'],
                'last_used': row['last_used']
            })
        
        return jsonify({'success': True, 'data': apikeys})
    except Exception as e:
        logger.error(f"Get API keys error: {str(e)}")
        return jsonify({'success': False, 'message': 'Lỗi khi lấy API keys'}), 500

@app.route('/api/admin/apikeys/create', methods=['POST'])
@login_required
def create_apikey():
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        
        if not name:
            return jsonify({'success': False, 'message': 'Vui lòng nhập tên API Key'}), 400
        
        api_key = f"sk_{secrets.token_hex(16)}"
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO api_keys (api_key, name, status)
            VALUES (?, ?, ?)
        ''', (api_key, name, 'active'))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': 'Tạo API key thành công',
            'api_key': api_key
        })
    except Exception as e:
        logger.error(f"Create API key error: {str(e)}")
        return jsonify({'success': False, 'message': 'Lỗi khi tạo API key'}), 500

@app.route('/api/admin/apikeys/delete/<int:key_id>', methods=['POST'])
@login_required
def delete_apikey(key_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM api_keys WHERE id = ?', (key_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Đã xóa API key'})
    except Exception as e:
        logger.error(f"Delete API key error: {str(e)}")
        return jsonify({'success': False, 'message': 'Lỗi khi xóa API key'}), 500

@app.route('/api/admin/debug')
def debug_info():
    return jsonify({
        'status': 'online',
        'server_time': datetime.now().isoformat(),
        'version': '2.0.0',
        'database': 'ready'
    })

# ============ PUBLIC API ============

@app.route('/api/verify', methods=['POST'])
def verify_license():
    try:
        data = request.get_json()
        license_key = data.get('license_key', '').strip().upper()
        hwid = data.get('hwid', '').strip()
        
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({'valid': False, 'message': 'API key required'}), 401
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify API key
        cursor.execute('''
            SELECT * FROM api_keys 
            WHERE api_key = ? AND status = "active"
        ''', (api_key,))
        
        valid_api_key = cursor.fetchone()
        if not valid_api_key:
            conn.close()
            return jsonify({'valid': False, 'message': 'Invalid API key'}), 401
        
        # Verify license
        cursor.execute('SELECT * FROM licenses WHERE license_key = ?', (license_key,))
        license = cursor.fetchone()
        
        if not license:
            conn.close()
            return jsonify({'valid': False, 'message': 'Invalid license'})
        
        # Check status
        if license['status'] != 'active':
            conn.close()
            return jsonify({'valid': False, 'message': f'License is {license["status"]}'})
        
        # Check expiration
        if license['expires_at']:
            try:
                expires_at = datetime.strptime(license['expires_at'], '%Y-%m-%d %H:%M:%S')
                if expires_at < datetime.now():
                    cursor.execute('UPDATE licenses SET status = "expired" WHERE id = ?', (license['id'],))
                    conn.commit()
                    conn.close()
                    return jsonify({'valid': False, 'message': 'License expired'})
            except:
                pass
        
        conn.close()
        
        # Calculate days left
        days_left = None
        if license['expires_at']:
            try:
                expires = datetime.strptime(license['expires_at'], '%Y-%m-%d %H:%M:%S')
                days_left = max(0, (expires - datetime.now()).days)
            except:
                days_left = 0
        
        return jsonify({
            'valid': True,
            'message': 'License valid',
            'product': license['product'],
            'max_devices': license['max_devices'],
            'days_left': days_left,
            'owner': license['owner']
        })
    except Exception as e:
        logger.error(f"Verify license error: {str(e)}")
        return jsonify({'valid': False, 'message': 'Server error'}), 500

# ============ ERROR HANDLERS ============

@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'message': 'Not found'}), 404

@app.errorhandler(500)
def server_error(error):
    logger.error(f"Server error: {str(error)}")
    return jsonify({'success': False, 'message': 'Internal server error'}), 500

# ============ MAIN ============

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    logger.info(f"Starting License Admin Panel v2.0 on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
