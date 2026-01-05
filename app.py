from flask import Flask, render_template, jsonify, request, session, redirect, url_for
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

app = Flask(__name__, static_folder='static', template_folder='templates')
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
    
    # Bảng licenses với nhiều trường mới
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
    
    # Bảng license activations chi tiết
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS license_activations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_id INTEGER NOT NULL,
            hwid TEXT NOT NULL,
            ip_address TEXT,
            device_name TEXT,
            activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_check TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            FOREIGN KEY (license_id) REFERENCES licenses (id)
        )
    ''')
    
    # Bảng logs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        logger.info("✅ Default admin user created")
    
    # Tạo API key mặc định
    cursor.execute('SELECT * FROM api_keys')
    api_key = cursor.fetchone()
    
    if not api_key:
        api_key_value = f"sk_{secrets.token_hex(16)}"
        cursor.execute(
            'INSERT INTO api_keys (api_key, name) VALUES (?, ?)',
            (api_key_value, 'Default API Key')
        )
        logger.info("✅ Default API Key created")
    
    conn.commit()
    conn.close()
    logger.info("✅ Database initialized successfully!")

# Khởi tạo database
with app.app_context():
    init_db()

# ============ HELPER FUNCTIONS ============

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

def log_action(action, details=None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO admin_logs (admin_id, action, details, ip_address)
            VALUES (?, ?, ?, ?)
        ''', (
            session.get('admin_id'),
            action,
            json.dumps(details) if details else None,
            request.remote_addr
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Log action error: {str(e)}")

def generate_license_key(prefix="LIC", custom_key=None):
    if custom_key:
        # Validate custom key format
        if not re.match(r'^[A-Z0-9-]{8,50}$', custom_key):
            return None
        return custom_key.upper()
    else:
        # Generate random key
        return f"{prefix}-{secrets.token_hex(8).upper()}-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}-{secrets.token_hex(12).upper()}"

def calculate_expiry_date(days):
    if days <= 0:
        return None
    return (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

# ============ ROUTES ============

@app.route('/')
def index():
    return redirect('/login')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/admin')
@login_required
def admin_dashboard():
    return render_template('admin.html')

# ============ AUTH API ============

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    try:
        data = request.get_json()
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
            
            log_action('LOGIN', {'username': username})
            
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
@login_required
def admin_logout():
    log_action('LOGOUT')
    session.clear()
    return jsonify({'success': True, 'message': 'Đã đăng xuất'})

@app.route('/api/admin/change-password', methods=['POST'])
@login_required
def change_password():
    try:
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')
        
        if not current_password or not new_password or not confirm_password:
            return jsonify({'success': False, 'message': 'Vui lòng nhập đầy đủ thông tin'}), 400
        
        if new_password != confirm_password:
            return jsonify({'success': False, 'message': 'Mật khẩu mới không khớp'}), 400
        
        if len(new_password) < 6:
            return jsonify({'success': False, 'message': 'Mật khẩu phải có ít nhất 6 ký tự'}), 400
        
        username = session.get('username')
        current_hashed = hash_password(current_password)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify current password
        cursor.execute(
            'SELECT * FROM admin_users WHERE username = ? AND password = ?',
            (username, current_hashed)
        )
        admin = cursor.fetchone()
        
        if not admin:
            conn.close()
            return jsonify({'success': False, 'message': 'Mật khẩu hiện tại không đúng'}), 401
        
        # Update password
        new_hashed = hash_password(new_password)
        cursor.execute(
            'UPDATE admin_users SET password = ? WHERE username = ?',
            (new_hashed, username)
        )
        
        conn.commit()
        conn.close()
        
        log_action('CHANGE_PASSWORD')
        
        return jsonify({
            'success': True, 
            'message': 'Đã thay đổi mật khẩu thành công'
        })
    except Exception as e:
        logger.error(f"Change password error: {str(e)}")
        return jsonify({'success': False, 'message': 'Lỗi server'}), 500

# ============ DASHBOARD API ============

@app.route('/api/admin/stats')
@login_required
def get_stats():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # License stats
        cursor.execute('SELECT COUNT(*) FROM licenses')
        total_licenses = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM licenses WHERE status = "active"')
        active_licenses = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM licenses WHERE status = "inactive"')
        inactive_licenses = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM licenses WHERE status = "expired"')
        expired_licenses = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM licenses WHERE status = "banned"')
        banned_licenses = cursor.fetchone()[0]
        
        # API key stats
        cursor.execute('SELECT COUNT(*) FROM api_keys WHERE status = "active"')
        active_api_keys = cursor.fetchone()[0]
        
        # Today's stats
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('SELECT COUNT(*) FROM licenses WHERE DATE(created_at) = ?', (today,))
        today_licenses = cursor.fetchone()[0]
        
        # Expiring soon (within 7 days)
        cursor.execute('''
            SELECT COUNT(*) FROM licenses 
            WHERE status = "active" 
            AND expires_at IS NOT NULL 
            AND expires_at <= datetime('now', '+7 days')
        ''')
        expiring_soon = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'total_licenses': total_licenses,
                'active_licenses': active_licenses,
                'inactive_licenses': inactive_licenses,
                'expired_licenses': expired_licenses,
                'banned_licenses': banned_licenses,
                'active_api_keys': active_api_keys,
                'today_licenses': today_licenses,
                'expiring_soon': expiring_soon
            }
        })
    except Exception as e:
        logger.error(f"Stats error: {str(e)}")
        return jsonify({'success': False, 'message': 'Lỗi khi lấy thống kê'}), 500

@app.route('/api/admin/activity')
@login_required
def get_recent_activity():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT al.action, al.details, al.created_at, au.username
            FROM admin_logs al
            LEFT JOIN admin_users au ON al.admin_id = au.id
            ORDER BY al.created_at DESC
            LIMIT 50
        ''')
        rows = cursor.fetchall()
        conn.close()
        
        activities = []
        for row in rows:
            activities.append({
                'action': row['action'],
                'details': json.loads(row['details']) if row['details'] else None,
                'created_at': row['created_at'],
                'username': row['username'] or 'System'
            })
        
        return jsonify({'success': True, 'data': activities})
    except Exception as e:
        logger.error(f"Activity error: {str(e)}")
        return jsonify({'success': False, 'message': 'Lỗi khi lấy hoạt động'}), 500

# ============ LICENSE MANAGEMENT API ============

@app.route('/api/admin/licenses')
@login_required
def get_licenses():
    try:
        search = request.args.get('search', '')
        status = request.args.get('status', '')
        product = request.args.get('product', '')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = 'SELECT * FROM licenses WHERE 1=1'
        params = []
        
        if search:
            query += ' AND (license_key LIKE ? OR owner LIKE ? OR notes LIKE ?)'
            search_term = f'%{search}%'
            params.extend([search_term, search_term, search_term])
        
        if status:
            query += ' AND status = ?'
            params.append(status)
        
        if product:
            query += ' AND product = ?'
            params.append(product)
        
        query += ' ORDER BY created_at DESC'
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        licenses = []
        for row in rows:
            # Tính số ngày còn lại
            days_left = None
            if row['expires_at']:
                expires = datetime.strptime(row['expires_at'], '%Y-%m-%d %H:%M:%S')
                days_left = max(0, (expires - datetime.now()).days)
            
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
                'last_active': row['last_active'],
                'custom_days': row['custom_days'],
                'auto_renew': bool(row['auto_renew']),
                'reset_count': row['reset_count'],
                'last_reset': row['last_reset'],
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
        license_key = generate_license_key(custom_key=custom_key)
        if not license_key:
            return jsonify({'success': False, 'message': 'License key không hợp lệ'}), 400
        
        # Calculate expiry date (default 30 days, 24h/day)
        custom_days = int(data.get('custom_days', 30))
        expires_at = calculate_expiry_date(custom_days)
        
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
        
        license_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        log_action('CREATE_LICENSE', {
            'license_id': license_id,
            'license_key': license_key,
            'product': product,
            'days': custom_days
        })
        
        return jsonify({
            'success': True, 
            'message': 'Tạo license thành công',
            'license_key': license_key,
            'expires_at': expires_at
        })
    except Exception as e:
        logger.error(f"Create license error: {str(e)}")
        return jsonify({'success': False, 'message': 'Lỗi khi tạo license'}), 500

@app.route('/api/admin/licenses/update/<int:license_id>', methods=['POST'])
@login_required
def update_license(license_id):
    try:
        data = request.get_json()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get current license
        cursor.execute('SELECT * FROM licenses WHERE id = ?', (license_id,))
        license = cursor.fetchone()
        if not license:
            conn.close()
            return jsonify({'success': False, 'message': 'License không tồn tại'}), 404
        
        # Update license
        cursor.execute('''
            UPDATE licenses SET 
                product = ?, owner = ?, status = ?, max_devices = ?, 
                notes = ?, hwid_lock = ?, ip_lock = ?, custom_days = ?, auto_renew = ?
            WHERE id = ?
        ''', (
            data.get('product', license['product']),
            data.get('owner', license['owner']),
            data.get('status', license['status']),
            int(data.get('max_devices', license['max_devices'])),
            data.get('notes', license['notes']),
            data.get('hwid_lock', license['hwid_lock']),
            data.get('ip_lock', license['ip_lock']),
            int(data.get('custom_days', license['custom_days'])),
            bool(data.get('auto_renew', license['auto_renew'])),
            license_id
        ))
        
        conn.commit()
        conn.close()
        
        log_action('UPDATE_LICENSE', {
            'license_id': license_id,
            'changes': data
        })
        
        return jsonify({'success': True, 'message': 'Cập nhật license thành công'})
    except Exception as e:
        logger.error(f"Update license error: {str(e)}")
        return jsonify({'success': False, 'message': 'Lỗi khi cập nhật license'}), 500

@app.route('/api/admin/licenses/extend/<int:license_id>', methods=['POST'])
@login_required
def extend_license(license_id):
    try:
        data = request.get_json()
        days = int(data.get('days', 30))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get current license
        cursor.execute('SELECT * FROM licenses WHERE id = ?', (license_id,))
        license = cursor.fetchone()
        if not license:
            conn.close()
            return jsonify({'success': False, 'message': 'License không tồn tại'}), 404
        
        # Calculate new expiry
        if license['expires_at']:
            current_expiry = datetime.strptime(license['expires_at'], '%Y-%m-%d %H:%M:%S')
            new_expiry = current_expiry + timedelta(days=days)
        else:
            new_expiry = datetime.now() + timedelta(days=days)
        
        # Update license
        cursor.execute('''
            UPDATE licenses SET 
                expires_at = ?,
                status = 'active',
                custom_days = custom_days + ?
            WHERE id = ?
        ''', (new_expiry.strftime('%Y-%m-%d %H:%M:%S'), days, license_id))
        
        conn.commit()
        conn.close()
        
        log_action('EXTEND_LICENSE', {
            'license_id': license_id,
            'days': days,
            'new_expiry': new_expiry.strftime('%Y-%m-%d %H:%M:%S')
        })
        
        return jsonify({
            'success': True, 
            'message': f'Đã gia hạn license thêm {days} ngày',
            'new_expiry': new_expiry.strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        logger.error(f"Extend license error: {str(e)}")
        return jsonify({'success': False, 'message': 'Lỗi khi gia hạn license'}), 500

@app.route('/api/admin/licenses/reset/<int:license_id>', methods=['POST'])
@login_required
def reset_license(license_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get current license
        cursor.execute('SELECT * FROM licenses WHERE id = ?', (license_id,))
        license = cursor.fetchone()
        if not license:
            conn.close()
            return jsonify({'success': False, 'message': 'License không tồn tại'}), 404
        
        # Reset activations
        cursor.execute('DELETE FROM license_activations WHERE license_id = ?', (license_id,))
        
        # Reset license stats
        cursor.execute('''
            UPDATE licenses SET 
                total_activations = 0,
                last_active = NULL,
                reset_count = reset_count + 1,
                last_reset = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (license_id,))
        
        conn.commit()
        conn.close()
        
        log_action('RESET_LICENSE', {'license_id': license_id})
        
        return jsonify({'success': True, 'message': 'Đã reset license thành công'})
    except Exception as e:
        logger.error(f"Reset license error: {str(e)}")
        return jsonify({'success': False, 'message': 'Lỗi khi reset license'}), 500

@app.route('/api/admin/licenses/ban/<int:license_id>', methods=['POST'])
@login_required
def ban_license(license_id):
    try:
        data = request.get_json()
        reason = data.get('reason', 'Vi phạm điều khoản')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE licenses SET 
                status = 'banned',
                notes = notes || ? || ?
            WHERE id = ?
        ''', ('\n[BANNED] ', reason, license_id))
        
        conn.commit()
        conn.close()
        
        log_action('BAN_LICENSE', {
            'license_id': license_id,
            'reason': reason
        })
        
        return jsonify({'success': True, 'message': 'Đã khóa license thành công'})
    except Exception as e:
        logger.error(f"Ban license error: {str(e)}")
        return jsonify({'success': False, 'message': 'Lỗi khi khóa license'}), 500

@app.route('/api/admin/licenses/delete/<int:license_id>', methods=['POST'])
@login_required
def delete_license(license_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get license key for logging
        cursor.execute('SELECT license_key FROM licenses WHERE id = ?', (license_id,))
        license = cursor.fetchone()
        
        if license:
            # Delete activations first
            cursor.execute('DELETE FROM license_activations WHERE license_id = ?', (license_id,))
            
            # Delete license
            cursor.execute('DELETE FROM licenses WHERE id = ?', (license_id,))
            
            conn.commit()
            conn.close()
            
            log_action('DELETE_LICENSE', {'license_key': license['license_key']})
            
            return jsonify({'success': True, 'message': 'Đã xóa license thành công'})
        else:
            conn.close()
            return jsonify({'success': False, 'message': 'License không tồn tại'}), 404
    except Exception as e:
        logger.error(f"Delete license error: {str(e)}")
        return jsonify({'success': False, 'message': 'Lỗi khi xóa license'}), 500

@app.route('/api/admin/licenses/bulk', methods=['POST'])
@login_required
def bulk_license_actions():
    try:
        data = request.get_json()
        action = data.get('action')
        license_ids = data.get('license_ids', [])
        
        if not license_ids:
            return jsonify({'success': False, 'message': 'Vui lòng chọn ít nhất một license'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if action == 'delete':
            # Delete activations first
            cursor.execute('DELETE FROM license_activations WHERE license_id IN ({})'.format(
                ','.join('?' for _ in license_ids)
            ), license_ids)
            
            # Delete licenses
            cursor.execute('DELETE FROM licenses WHERE id IN ({})'.format(
                ','.join('?' for _ in license_ids)
            ), license_ids)
            
            message = f'Đã xóa {len(license_ids)} license'
            
        elif action == 'activate':
            cursor.execute('UPDATE licenses SET status = "active" WHERE id IN ({})'.format(
                ','.join('?' for _ in license_ids)
            ), license_ids)
            
            message = f'Đã kích hoạt {len(license_ids)} license'
            
        elif action == 'deactivate':
            cursor.execute('UPDATE licenses SET status = "inactive" WHERE id IN ({})'.format(
                ','.join('?' for _ in license_ids)
            ), license_ids)
            
            message = f'Đã vô hiệu hóa {len(license_ids)} license'
            
        elif action == 'ban':
            cursor.execute('UPDATE licenses SET status = "banned" WHERE id IN ({})'.format(
                ','.join('?' for _ in license_ids)
            ), license_ids)
            
            message = f'Đã khóa {len(license_ids)} license'
            
        else:
            conn.close()
            return jsonify({'success': False, 'message': 'Hành động không hợp lệ'}), 400
        
        conn.commit()
        conn.close()
        
        log_action('BULK_ACTION', {
            'action': action,
            'count': len(license_ids)
        })
        
        return jsonify({'success': True, 'message': message})
    except Exception as e:
        logger.error(f"Bulk action error: {str(e)}")
        return jsonify({'success': False, 'message': 'Lỗi khi thực hiện hành động'}), 500

@app.route('/api/admin/licenses/activations/<int:license_id>')
@login_required
def get_license_activations(license_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM license_activations 
            WHERE license_id = ? 
            ORDER BY activated_at DESC
        ''', (license_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        activations = []
        for row in rows:
            activations.append({
                'id': row['id'],
                'hwid': row['hwid'],
                'ip_address': row['ip_address'],
                'device_name': row['device_name'],
                'activated_at': row['activated_at'],
                'last_check': row['last_check'],
                'is_active': bool(row['is_active'])
            })
        
        return jsonify({'success': True, 'data': activations})
    except Exception as e:
        logger.error(f"Get activations error: {str(e)}")
        return jsonify({'success': False, 'message': 'Lỗi khi lấy danh sách activations'}), 500

# ============ API KEY MANAGEMENT ============

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
        
        log_action('CREATE_API_KEY', {'name': name})
        
        return jsonify({
            'success': True, 
            'message': 'Tạo API key thành công',
            'api_key': api_key
        })
    except Exception as e:
        logger.error(f"Create API key error: {str(e)}")
        return jsonify({'success': False, 'message': 'Lỗi khi tạo API key'}), 500

@app.route('/api/admin/apikeys/update/<int:key_id>', methods=['POST'])
@login_required
def update_apikey(key_id):
    try:
        data = request.get_json()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE api_keys SET 
                name = ?, 
                status = ?
            WHERE id = ?
        ''', (
            data.get('name', '').strip(),
            data.get('status', 'active'),
            key_id
        ))
        
        conn.commit()
        conn.close()
        
        log_action('UPDATE_API_KEY', {'key_id': key_id, 'changes': data})
        
        return jsonify({'success': True, 'message': 'Cập nhật API key thành công'})
    except Exception as e:
        logger.error(f"Update API key error: {str(e)}")
        return jsonify({'success': False, 'message': 'Lỗi khi cập nhật API key'}), 500

@app.route('/api/admin/apikeys/delete/<int:key_id>', methods=['POST'])
@login_required
def delete_apikey(key_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM api_keys WHERE id = ?', (key_id,))
        
        conn.commit()
        conn.close()
        
        log_action('DELETE_API_KEY', {'key_id': key_id})
        
        return jsonify({'success': True, 'message': 'Đã xóa API key'})
    except Exception as e:
        logger.error(f"Delete API key error: {str(e)}")
        return jsonify({'success': False, 'message': 'Lỗi khi xóa API key'}), 500

# ============ PUBLIC VERIFY API ============

@app.route('/api/verify', methods=['POST'])
def verify_license():
    try:
        data = request.get_json()
        license_key = data.get('license_key', '').strip().upper()
        hwid = data.get('hwid', '').strip()
        ip_address = request.remote_addr
        
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
        
        # Update API key last used
        cursor.execute('''
            UPDATE api_keys SET last_used = CURRENT_TIMESTAMP WHERE api_key = ?
        ''', (api_key,))
        
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
            expires_at = datetime.strptime(license['expires_at'], '%Y-%m-%d %H:%M:%S')
            if expires_at < datetime.now():
                cursor.execute('UPDATE licenses SET status = "expired" WHERE id = ?', (license['id'],))
                conn.commit()
                conn.close()
                return jsonify({'valid': False, 'message': 'License expired'})
        
        # Check HWID lock
        if license['hwid_lock']:
            allowed_hwids = [h.strip() for h in license['hwid_lock'].split(',') if h.strip()]
            if hwid and hwid not in allowed_hwids:
                conn.close()
                return jsonify({'valid': False, 'message': 'HWID not allowed'})
        
        # Check IP lock
        if license['ip_lock']:
            allowed_ips = [ip.strip() for ip in license['ip_lock'].split(',') if ip.strip()]
            if ip_address and ip_address not in allowed_ips:
                conn.close()
                return jsonify({'valid': False, 'message': 'IP not allowed'})
        
        # Check max devices
        cursor.execute('SELECT COUNT(*) FROM license_activations WHERE license_id = ? AND is_active = 1', (license['id'],))
        active_count = cursor.fetchone()[0]
        
        if active_count >= license['max_devices']:
            conn.close()
            return jsonify({'valid': False, 'message': 'Maximum devices reached'})
        
        # Record activation
        if hwid:
            cursor.execute('''
                SELECT * FROM license_activations 
                WHERE license_id = ? AND hwid = ?
            ''', (license['id'], hwid))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update existing activation
                cursor.execute('''
                    UPDATE license_activations SET 
                        is_active = 1,
                        last_check = CURRENT_TIMESTAMP,
                        ip_address = ?
                    WHERE id = ?
                ''', (ip_address, existing['id']))
            else:
                # Create new activation
                cursor.execute('''
                    INSERT INTO license_activations (license_id, hwid, ip_address)
                    VALUES (?, ?, ?)
                ''', (license['id'], hwid, ip_address))
        
        # Update license stats
        cursor.execute('''
            UPDATE licenses SET 
                total_activations = total_activations + 1,
                last_active = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (license['id'],))
        
        conn.commit()
        conn.close()
        
        # Calculate days left
        days_left = None
        if license['expires_at']:
            expires = datetime.strptime(license['expires_at'], '%Y-%m-%d %H:%M:%S')
            days_left = max(0, (expires - datetime.now()).days)
        
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

# ============ DEBUG & HEALTH ============

@app.route('/api/admin/debug')
def debug_info():
    return jsonify({
        'status': 'online',
        'server_time': datetime.now().isoformat(),
        'version': '2.0.0',
        'environment': os.environ.get('RENDER', 'development'),
        'database': 'ready'
    })

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
