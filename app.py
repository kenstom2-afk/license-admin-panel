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

# Cấu hình logging cho Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['DATABASE_PATH'] = os.path.join(os.path.dirname(__file__), 'database.db')
CORS(app)

def get_db_connection():
    """Kết nối đến SQLite database"""
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    """Hash password với SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    """Khởi tạo database và các bảng"""
    logger.info("Initializing database...")
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
    
    # Tạo admin mặc định nếu chưa có
    cursor.execute('SELECT * FROM admin_users WHERE username = ?', ('admin',))
    admin = cursor.fetchone()
    
    if not admin:
        hashed_password = hash_password("Anhhuy123")
        cursor.execute(
            'INSERT INTO admin_users (username, password) VALUES (?, ?)',
            ('admin', hashed_password)
        )
        logger.info("✅ Default admin user created: admin / Anhhuy123")
    
    # Tạo API key mặc định nếu chưa có
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
    init_db()

def login_required(f):
    """Decorator cho các route yêu cầu đăng nhập"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

# ============ ROUTES ============

@app.route('/')
def index():
    """Trang chủ - redirect đến login"""
    return redirect('/login')

@app.route('/login')
def login_page():
    """Trang đăng nhập"""
    return render_template('login.html')

@app.route('/favicon.ico')
def favicon():
    """Favicon"""
    return send_from_directory('static', 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/admin')
def admin_dashboard():
    """Trang admin dashboard"""
    if 'logged_in' not in session:
        return redirect('/login')
    return render_template('admin.html')

# ============ ADMIN API ============

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    """Đăng nhập admin"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
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
    """Đăng xuất"""
    session.clear()
    return jsonify({'success': True, 'message': 'Đã đăng xuất'})

@app.route('/api/admin/stats')
@login_required
def get_stats():
    """Lấy thống kê"""
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
        total_api_keys = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'total_licenses': total_licenses,
                'active_licenses': active_licenses,
                'inactive_licenses': inactive_licenses,
                'expired_licenses': expired_licenses,
                'total_api_keys': total_api_keys
            }
        })
    except Exception as e:
        logger.error(f"Stats error: {str(e)}")
        return jsonify({'success': False, 'message': 'Lỗi khi lấy thống kê'}), 500

@app.route('/api/admin/licenses')
@login_required
def get_licenses():
    """Lấy danh sách licenses"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM licenses ORDER BY created_at DESC')
        rows = cursor.fetchall()
        conn.close()
        
        licenses = []
        for row in rows:
            licenses.append({
                'id': row[0],
                'license_key': row[1],
                'product': row[2],
                'owner': row[3] or '',
                'status': row[4],
                'created_at': row[5],
                'expires_at': row[6] or '',
                'max_devices': row[7],
                'notes': row[8] or ''
            })
        
        return jsonify({'success': True, 'data': licenses})
    except Exception as e:
        logger.error(f"Get licenses error: {str(e)}")
        return jsonify({'success': False, 'message': 'Lỗi khi lấy danh sách license'}), 500

@app.route('/api/admin/licenses/create', methods=['POST'])
@login_required
def create_license():
    """Tạo license mới"""
    try:
        data = request.get_json()
        
        # Tạo license key
        license_key = f"LIC-{secrets.token_hex(8).upper()}"
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO licenses (license_key, product, owner, status, expires_at, max_devices, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            license_key,
            data.get('product', 'Default Product'),
            data.get('owner', ''),
            data.get('status', 'active'),
            data.get('expires_at', None),
            data.get('max_devices', 1),
            data.get('notes', '')
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': 'Tạo license thành công',
            'license_key': license_key
        })
    except Exception as e:
        logger.error(f"Create license error: {str(e)}")
        return jsonify({'success': False, 'message': 'Lỗi khi tạo license'}), 500

@app.route('/api/admin/licenses/delete/<int:license_id>', methods=['POST'])
@login_required
def delete_license(license_id):
    """Xóa license"""
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
    """Lấy danh sách API keys"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM api_keys ORDER BY created_at DESC')
        rows = cursor.fetchall()
        conn.close()
        
        apikeys = []
        for row in rows:
            apikeys.append({
                'id': row[0],
                'key': row[1],
                'name': row[2],
                'status': row[3],
                'created_at': row[4]
            })
        
        return jsonify({'success': True, 'data': apikeys})
    except Exception as e:
        logger.error(f"Get API keys error: {str(e)}")
        return jsonify({'success': False, 'message': 'Lỗi khi lấy API keys'}), 500

@app.route('/api/admin/apikeys/create', methods=['POST'])
@login_required
def create_apikey():
    """Tạo API key mới"""
    try:
        data = request.get_json()
        api_key = f"sk_{secrets.token_hex(16)}"
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO api_keys (api_key, name, status)
            VALUES (?, ?, ?)
        ''', (api_key, data.get('name', 'New API Key'), 'active'))
        
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
    """Xóa API key"""
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
    """Debug endpoint để kiểm tra server"""
    return jsonify({
        'status': 'online',
        'server_time': datetime.now().isoformat(),
        'version': '1.0.0',
        'environment': os.environ.get('RENDER', 'development')
    })

# ============ PUBLIC API ============

@app.route('/api/verify', methods=['POST'])
def verify_license():
    """API verify license cho client"""
    try:
        data = request.get_json()
        license_key = data.get('license_key')
        hwid = data.get('hwid')
        api_key = request.headers.get('X-API-Key')
        
        if not api_key:
            return jsonify({'valid': False, 'message': 'API key required'}), 401
        
        # Verify API key
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM api_keys WHERE api_key = ? AND status = "active"', (api_key,))
        valid_api_key = cursor.fetchone()
        
        if not valid_api_key:
            conn.close()
            return jsonify({'valid': False, 'message': 'Invalid API key'}), 401
        
        # Verify license
        cursor.execute('SELECT * FROM licenses WHERE license_key = ?', (license_key,))
        license_row = cursor.fetchone()
        
        if not license_row:
            conn.close()
            return jsonify({'valid': False, 'message': 'Invalid license'})
        
        # Check status
        if license_row[4] != 'active':  # status column
            conn.close()
            return jsonify({'valid': False, 'message': f'License is {license_row[4]}'})
        
        # Check expiration
        if license_row[6]:  # expires_at column
            expires_at = datetime.strptime(license_row[6], '%Y-%m-%d')
            if expires_at < datetime.now():
                cursor.execute('UPDATE licenses SET status = "expired" WHERE id = ?', (license_row[0],))
                conn.commit()
                conn.close()
                return jsonify({'valid': False, 'message': 'License expired'})
        
        conn.close()
        return jsonify({'valid': True, 'message': 'License valid'})
    except Exception as e:
        logger.error(f"Verify license error: {str(e)}")
        return jsonify({'valid': False, 'message': 'Server error'}), 500

# ============ ERROR HANDLERS ============

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(error):
    logger.error(f"Server error: {str(error)}")
    return jsonify({'error': 'Internal server error'}), 500

# ============ MAIN ============

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    logger.info(f"Starting server on port {port} (debug={debug})")
    app.run(host='0.0.0.0', port=port, debug=debug)
