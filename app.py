from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_cors import CORS
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from functools import wraps
import sqlite3
import os
import json
import logging
import re

# ============ CONFIGURATION ============
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, 
            static_folder='../static',
            template_folder='../templates')

app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['DATABASE_PATH'] = os.path.join(os.path.dirname(__file__), 'license.db')
CORS(app)

# ============ DATABASE SETUP ============
def get_db_connection():
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_database():
    logger.info("Initializing database...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Admin users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Server keys table (for shell script authentication)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS server_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_name TEXT NOT NULL,
            server_key TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'active',
            permissions TEXT DEFAULT 'all',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used TIMESTAMP
        )
    ''')
    
    # API keys table (for client verification)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_name TEXT NOT NULL,
            api_key TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used TIMESTAMP
        )
    ''')
    
    # Licenses table with all features
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
            last_reset TIMESTAMP,
            is_custom_key BOOLEAN DEFAULT FALSE,
            metadata TEXT
        )
    ''')
    
    # License activations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS license_activations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_id INTEGER NOT NULL,
            hwid TEXT NOT NULL,
            ip_address TEXT,
            device_name TEXT,
            country TEXT,
            activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_check TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            FOREIGN KEY (license_id) REFERENCES licenses (id)
        )
    ''')
    
    # Activity logs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    
    # Create default admin if not exists
    cursor.execute('SELECT * FROM admin_users WHERE username = ?', ('admin',))
    admin = cursor.fetchone()
    
    if not admin:
        hashed_password = hash_password("Anhhuy123")
        cursor.execute(
            'INSERT INTO admin_users (username, password) VALUES (?, ?)',
            ('admin', hashed_password)
        )
        logger.info("✅ Default admin user created: admin / Anhhuy123")
    
    # Create default server key for shell scripts
    cursor.execute('SELECT * FROM server_keys')
    server_key = cursor.fetchone()
    
    if not server_key:
        server_key_value = f"server_{secrets.token_hex(24)}"
        cursor.execute(
            'INSERT INTO server_keys (key_name, server_key, permissions) VALUES (?, ?, ?)',
            ('Default Server Key', server_key_value, 'all')
        )
        logger.info(f"✅ Default Server Key created: {server_key_value}")
    
    # Create default API key
    cursor.execute('SELECT * FROM api_keys')
    api_key = cursor.fetchone()
    
    if not api_key:
        api_key_value = f"api_{secrets.token_hex(24)}"
        cursor.execute(
            'INSERT INTO api_keys (key_name, api_key) VALUES (?, ?)',
            ('Default API Key', api_key_value)
        )
        logger.info(f"✅ Default API Key created: {api_key_value}")
    
    conn.commit()
    conn.close()
    logger.info("✅ Database initialized successfully!")

# Initialize database
with app.app_context():
    init_database()

# ============ HELPER FUNCTIONS ============
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

def server_key_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        server_key = request.headers.get('X-Server-Key')
        if not server_key:
            return jsonify({'success': False, 'message': 'Server key required'}), 401
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM server_keys WHERE server_key = ? AND status = "active"', (server_key,))
        valid_key = cursor.fetchone()
        conn.close()
        
        if not valid_key:
            return jsonify({'success': False, 'message': 'Invalid server key'}), 401
        
        # Update last used
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE server_keys SET last_used = CURRENT_TIMESTAMP WHERE server_key = ?', (server_key,))
        conn.commit()
        conn.close()
        
        return f(*args, **kwargs)
    return decorated_function

def api_key_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({'success': False, 'message': 'API key required'}), 401
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM api_keys WHERE api_key = ? AND status = "active"', (api_key,))
        valid_key = cursor.fetchone()
        conn.close()
        
        if not valid_key:
            return jsonify({'success': False, 'message': 'Invalid API key'}), 401
        
        # Update last used
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE api_keys SET last_used = CURRENT_TIMESTAMP WHERE api_key = ?', (api_key,))
        conn.commit()
        conn.close()
        
        return f(*args, **kwargs)
    return decorated_function

def log_activity(action, details=None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO activity_logs (admin_id, action, details, ip_address)
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
        logger.error(f"Activity log error: {str(e)}")

def generate_license_key(custom_key=None):
    if custom_key:
        if not re.match(r'^[A-Z0-9-]{10,50}$', custom_key):
            return None
        return custom_key.upper()
    else:
        return f"LIC-{secrets.token_hex(8).upper()}-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}-{secrets.token_hex(8).upper()}"

# ============ ADMIN ROUTES ============
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

# ============ ADMIN API ENDPOINTS ============
@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'success': False, 'message': 'Please enter username and password'}), 400
        
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
            
            log_activity('LOGIN', {'username': username})
            
            return jsonify({
                'success': True, 
                'message': 'Login successful',
                'redirect': '/admin'
            })
        else:
            return jsonify({'success': False, 'message': 'Invalid username or password'}), 401
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'success': False, 'message': 'Server error'}), 500

@app.route('/api/admin/logout', methods=['POST'])
@login_required
def admin_logout():
    log_activity('LOGOUT')
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'})

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
        
        # API keys stats
        cursor.execute('SELECT COUNT(*) FROM api_keys WHERE status = "active"')
        active_api_keys = cursor.fetchone()[0]
        
        # Server keys stats
        cursor.execute('SELECT COUNT(*) FROM server_keys WHERE status = "active"')
        active_server_keys = cursor.fetchone()[0]
        
        # Today's stats
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('SELECT COUNT(*) FROM licenses WHERE DATE(created_at) = ?', (today,))
        today_licenses = cursor.fetchone()[0]
        
        # Custom keys
        cursor.execute('SELECT COUNT(*) FROM licenses WHERE is_custom_key = 1')
        custom_keys = cursor.fetchone()[0]
        
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
                'active_server_keys': active_server_keys,
                'today_licenses': today_licenses,
                'custom_keys': custom_keys
            }
        })
    except Exception as e:
        logger.error(f"Stats error: {str(e)}")
        return jsonify({'success': False, 'message': 'Error getting statistics'}), 500

# ============ LICENSE MANAGEMENT API ============
@app.route('/api/admin/licenses', methods=['GET'])
@login_required
def get_licenses():
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        search = request.args.get('search', '')
        status = request.args.get('status', '')
        
        offset = (page - 1) * limit
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = 'SELECT * FROM licenses WHERE 1=1'
        count_query = 'SELECT COUNT(*) FROM licenses WHERE 1=1'
        params = []
        
        if search:
            query += ' AND (license_key LIKE ? OR owner LIKE ? OR product LIKE ?)'
            count_query += ' AND (license_key LIKE ? OR owner LIKE ? OR product LIKE ?)'
            search_term = f'%{search}%'
            params.extend([search_term, search_term, search_term])
        
        if status:
            query += ' AND status = ?'
            count_query += ' AND status = ?'
            params.append(status)
        
        query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
        
        # Get total count
        count_params = params.copy()
        cursor.execute(count_query, count_params)
        total = cursor.fetchone()[0]
        
        # Get licenses
        params.extend([limit, offset])
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        licenses = []
        for row in rows:
            # Calculate days left (24h/day)
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
                'last_active': row['last_active'],
                'custom_days': row['custom_days'],
                'auto_renew': bool(row['auto_renew']),
                'reset_count': row['reset_count'],
                'last_reset': row['last_reset'],
                'is_custom_key': bool(row['is_custom_key']),
                'days_left': days_left
            })
        
        return jsonify({
            'success': True,
            'data': licenses,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total,
                'pages': (total + limit - 1) // limit
            }
        })
    except Exception as e:
        logger.error(f"Get licenses error: {str(e)}")
        return jsonify({'success': False, 'message': 'Error getting licenses'}), 500

@app.route('/api/admin/licenses/create', methods=['POST'])
@login_required
def create_license():
    try:
        data = request.get_json()
        
        product = data.get('product', '').strip()
        if not product:
            return jsonify({'success': False, 'message': 'Product name is required'}), 400
        
        custom_key = data.get('custom_key', '').strip()
        is_custom = bool(custom_key)
        
        if custom_key:
            # Check if custom key already exists
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM licenses WHERE license_key = ?', (custom_key.upper(),))
            if cursor.fetchone():
                conn.close()
                return jsonify({'success': False, 'message': 'License key already exists'}), 400
        
        # Generate license key
        license_key = generate_license_key(custom_key=custom_key)
        if not license_key:
            return jsonify({'success': False, 'message': 'Invalid license key format'}), 400
        
        # Calculate expiry (24h/day)
        custom_days = int(data.get('custom_days', 30))
        expires_at = (datetime.now() + timedelta(days=custom_days)).strftime('%Y-%m-%d %H:%M:%S')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO licenses (
                license_key, product, owner, status, expires_at, max_devices, 
                notes, hwid_lock, ip_lock, custom_days, auto_renew, is_custom_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            bool(data.get('auto_renew', False)),
            is_custom
        ))
        
        license_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        log_activity('CREATE_LICENSE', {
            'license_id': license_id,
            'license_key': license_key,
            'product': product,
            'days': custom_days,
            'is_custom': is_custom
        })
        
        return jsonify({
            'success': True, 
            'message': 'License created successfully',
            'license_key': license_key,
            'expires_at': expires_at,
            'is_custom': is_custom
        })
    except Exception as e:
        logger.error(f"Create license error: {str(e)}")
        return jsonify({'success': False, 'message': 'Error creating license'}), 500

@app.route('/api/admin/licenses/<int:license_id>', methods=['GET'])
@login_required
def get_license_details(license_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM licenses WHERE id = ?', (license_id,))
        license = cursor.fetchone()
        
        if not license:
            conn.close()
            return jsonify({'success': False, 'message': 'License not found'}), 404
        
        # Get activations
        cursor.execute('SELECT * FROM license_activations WHERE license_id = ? ORDER BY activated_at DESC', (license_id,))
        activations = cursor.fetchall()
        
        conn.close()
        
        # Format license data
        license_data = {
            'id': license['id'],
            'license_key': license['license_key'],
            'product': license['product'],
            'owner': license['owner'] or '',
            'status': license['status'],
            'created_at': license['created_at'],
            'expires_at': license['expires_at'],
            'max_devices': license['max_devices'],
            'notes': license['notes'],
            'hwid_lock': license['hwid_lock'],
            'ip_lock': license['ip_lock'],
            'total_activations': license['total_activations'],
            'last_active': license['last_active'],
            'custom_days': license['custom_days'],
            'auto_renew': bool(license['auto_renew']),
            'reset_count': license['reset_count'],
            'last_reset': license['last_reset'],
            'is_custom_key': bool(license['is_custom_key'])
        }
        
        # Format activations
        activations_list = []
        for act in activations:
            activations_list.append({
                'id': act['id'],
                'hwid': act['hwid'],
                'ip_address': act['ip_address'],
                'device_name': act['device_name'],
                'country': act['country'],
                'activated_at': act['activated_at'],
                'last_check': act['last_check'],
                'is_active': bool(act['is_active'])
            })
        
        return jsonify({
            'success': True,
            'license': license_data,
            'activations': activations_list
        })
    except Exception as e:
        logger.error(f"License details error: {str(e)}")
        return jsonify({'success': False, 'message': 'Error getting license details'}), 500

@app.route('/api/admin/licenses/<int:license_id>/reset', methods=['POST'])
@login_required
def reset_license(license_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if license exists
        cursor.execute('SELECT * FROM licenses WHERE id = ?', (license_id,))
        license = cursor.fetchone()
        
        if not license:
            conn.close()
            return jsonify({'success': False, 'message': 'License not found'}), 404
        
        # Delete all activations
        cursor.execute('DELETE FROM license_activations WHERE license_id = ?', (license_id,))
        
        # Reset license stats
        cursor.execute('''
            UPDATE licenses SET 
                total_activations = 0,
                last_active = NULL,
                reset_count = reset_count + 1,
                last_reset = CURRENT_TIMESTAMP,
                status = 'active'
            WHERE id = ?
        ''', (license_id,))
        
        conn.commit()
        conn.close()
        
        log_activity('RESET_LICENSE', {
            'license_id': license_id,
            'license_key': license['license_key']
        })
        
        return jsonify({'success': True, 'message': 'License reset successfully'})
    except Exception as e:
        logger.error(f"Reset license error: {str(e)}")
        return jsonify({'success': False, 'message': 'Error resetting license'}), 500

@app.route('/api/admin/licenses/<int:license_id>/extend', methods=['POST'])
@login_required
def extend_license(license_id):
    try:
        data = request.get_json()
        days = int(data.get('days', 30))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM licenses WHERE id = ?', (license_id,))
        license = cursor.fetchone()
        
        if not license:
            conn.close()
            return jsonify({'success': False, 'message': 'License not found'}), 404
        
        # Calculate new expiry (24h/day)
        if license['expires_at']:
            try:
                current_expiry = datetime.strptime(license['expires_at'], '%Y-%m-%d %H:%M:%S')
                new_expiry = current_expiry + timedelta(days=days)
            except:
                new_expiry = datetime.now() + timedelta(days=days)
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
        
        log_activity('EXTEND_LICENSE', {
            'license_id': license_id,
            'license_key': license['license_key'],
            'days': days
        })
        
        return jsonify({
            'success': True, 
            'message': f'License extended by {days} days',
            'new_expiry': new_expiry.strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        logger.error(f"Extend license error: {str(e)}")
        return jsonify({'success': False, 'message': 'Error extending license'}), 500

@app.route('/api/admin/licenses/<int:license_id>/ban', methods=['POST'])
@login_required
def ban_license(license_id):
    try:
        data = request.get_json()
        reason = data.get('reason', 'Violation of terms')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE licenses SET 
                status = 'banned',
                notes = COALESCE(notes || ?, ?)
            WHERE id = ?
        ''', ('\n[BANNED] ' + reason, '[BANNED] ' + reason, license_id))
        
        conn.commit()
        conn.close()
        
        log_activity('BAN_LICENSE', {
            'license_id': license_id,
            'reason': reason
        })
        
        return jsonify({'success': True, 'message': 'License banned successfully'})
    except Exception as e:
        logger.error(f"Ban license error: {str(e)}")
        return jsonify({'success': False, 'message': 'Error banning license'}), 500

@app.route('/api/admin/licenses/<int:license_id>', methods=['DELETE'])
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
            
            log_activity('DELETE_LICENSE', {'license_key': license['license_key']})
            
            return jsonify({'success': True, 'message': 'License deleted successfully'})
        else:
            conn.close()
            return jsonify({'success': False, 'message': 'License not found'}), 404
    except Exception as e:
        logger.error(f"Delete license error: {str(e)}")
        return jsonify({'success': False, 'message': 'Error deleting license'}), 500

# ============ SERVER KEY MANAGEMENT ============
@app.route('/api/admin/server-keys', methods=['GET'])
@login_required
def get_server_keys():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM server_keys ORDER BY created_at DESC')
        rows = cursor.fetchall()
        conn.close()
        
        keys = []
        for row in rows:
            keys.append({
                'id': row['id'],
                'key_name': row['key_name'],
                'server_key': row['server_key'],
                'status': row['status'],
                'permissions': row['permissions'],
                'created_at': row['created_at'],
                'last_used': row['last_used']
            })
        
        return jsonify({'success': True, 'data': keys})
    except Exception as e:
        logger.error(f"Get server keys error: {str(e)}")
        return jsonify({'success': False, 'message': 'Error getting server keys'}), 500

@app.route('/api/admin/server-keys/create', methods=['POST'])
@login_required
def create_server_key():
    try:
        data = request.get_json()
        key_name = data.get('key_name', '').strip()
        
        if not key_name:
            return jsonify({'success': False, 'message': 'Key name is required'}), 400
        
        server_key = f"server_{secrets.token_hex(24)}"
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO server_keys (key_name, server_key, permissions)
            VALUES (?, ?, ?)
        ''', (key_name, server_key, data.get('permissions', 'all')))
        
        conn.commit()
        conn.close()
        
        log_activity('CREATE_SERVER_KEY', {'key_name': key_name})
        
        return jsonify({
            'success': True, 
            'message': 'Server key created successfully',
            'server_key': server_key
        })
    except Exception as e:
        logger.error(f"Create server key error: {str(e)}")
        return jsonify({'success': False, 'message': 'Error creating server key'}), 500

@app.route('/api/admin/server-keys/<int:key_id>/delete', methods=['POST'])
@login_required
def delete_server_key(key_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM server_keys WHERE id = ?', (key_id,))
        
        conn.commit()
        conn.close()
        
        log_activity('DELETE_SERVER_KEY', {'key_id': key_id})
        
        return jsonify({'success': True, 'message': 'Server key deleted successfully'})
    except Exception as e:
        logger.error(f"Delete server key error: {str(e)}")
        return jsonify({'success': False, 'message': 'Error deleting server key'}), 500

# ============ API KEY MANAGEMENT ============
@app.route('/api/admin/api-keys', methods=['GET'])
@login_required
def get_api_keys():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM api_keys ORDER BY created_at DESC')
        rows = cursor.fetchall()
        conn.close()
        
        keys = []
        for row in rows:
            keys.append({
                'id': row['id'],
                'key_name': row['key_name'],
                'api_key': row['api_key'],
                'status': row['status'],
                'created_at': row['created_at'],
                'last_used': row['last_used']
            })
        
        return jsonify({'success': True, 'data': keys})
    except Exception as e:
        logger.error(f"Get API keys error: {str(e)}")
        return jsonify({'success': False, 'message': 'Error getting API keys'}), 500

@app.route('/api/admin/api-keys/create', methods=['POST'])
@login_required
def create_api_key():
    try:
        data = request.get_json()
        key_name = data.get('key_name', '').strip()
        
        if not key_name:
            return jsonify({'success': False, 'message': 'Key name is required'}), 400
        
        api_key = f"api_{secrets.token_hex(24)}"
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO api_keys (key_name, api_key)
            VALUES (?, ?)
        ''', (key_name, api_key))
        
        conn.commit()
        conn.close()
        
        log_activity('CREATE_API_KEY', {'key_name': key_name})
        
        return jsonify({
            'success': True, 
            'message': 'API key created successfully',
            'api_key': api_key
        })
    except Exception as e:
        logger.error(f"Create API key error: {str(e)}")
        return jsonify({'success': False, 'message': 'Error creating API key'}), 500

@app.route('/api/admin/api-keys/<int:key_id>/delete', methods=['POST'])
@login_required
def delete_api_key(key_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM api_keys WHERE id = ?', (key_id,))
        
        conn.commit()
        conn.close()
        
        log_activity('DELETE_API_KEY', {'key_id': key_id})
        
        return jsonify({'success': True, 'message': 'API key deleted successfully'})
    except Exception as e:
        logger.error(f"Delete API key error: {str(e)}")
        return jsonify({'success': False, 'message': 'Error deleting API key'}), 500

# ============ ACTIVITY LOGS ============
@app.route('/api/admin/activity', methods=['GET'])
@login_required
def get_activity_logs():
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        offset = (page - 1) * limit
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT al.*, au.username
            FROM activity_logs al
            LEFT JOIN admin_users au ON al.admin_id = au.id
            ORDER BY al.created_at DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        
        rows = cursor.fetchall()
        
        cursor.execute('SELECT COUNT(*) FROM activity_logs')
        total = cursor.fetchone()[0]
        
        conn.close()
        
        logs = []
        for row in rows:
            logs.append({
                'id': row['id'],
                'action': row['action'],
                'details': json.loads(row['details']) if row['details'] else None,
                'username': row['username'] or 'System',
                'ip_address': row['ip_address'],
                'created_at': row['created_at']
            })
        
        return jsonify({
            'success': True,
            'data': logs,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total,
                'pages': (total + limit - 1) // limit
            }
        })
    except Exception as e:
        logger.error(f"Activity logs error: {str(e)}")
        return jsonify({'success': False, 'message': 'Error getting activity logs'}), 500

# ============ PUBLIC VERIFICATION API ============
@app.route('/api/v1/verify', methods=['POST'])
@api_key_required
def verify_license():
    try:
        data = request.get_json()
        license_key = data.get('license_key', '').strip().upper()
        hwid = data.get('hwid', '').strip()
        device_name = data.get('device_name', '').strip()
        ip_address = request.remote_addr
        
        if not license_key:
            return jsonify({'success': False, 'message': 'License key is required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get license
        cursor.execute('SELECT * FROM licenses WHERE license_key = ?', (license_key,))
        license = cursor.fetchone()
        
        if not license:
            conn.close()
            return jsonify({'success': False, 'message': 'Invalid license key'})
        
        # Check status
        if license['status'] != 'active':
            conn.close()
            return jsonify({
                'success': False,
                'message': f'License is {license["status"]}',
                'status': license['status']
            })
        
        # Check expiration (24h/day)
        if license['expires_at']:
            try:
                expires_at = datetime.strptime(license['expires_at'], '%Y-%m-%d %H:%M:%S')
                if expires_at < datetime.now():
                    cursor.execute('UPDATE licenses SET status = "expired" WHERE id = ?', (license['id'],))
                    conn.commit()
                    conn.close()
                    return jsonify({'success': False, 'message': 'License has expired'})
            except:
                pass
        
        # Check HWID lock
        if license['hwid_lock']:
            allowed_hwids = [h.strip() for h in license['hwid_lock'].split(',') if h.strip()]
            if hwid and hwid not in allowed_hwids:
                conn.close()
                return jsonify({'success': False, 'message': 'HWID not authorized'})
        
        # Check IP lock
        if license['ip_lock']:
            allowed_ips = [ip.strip() for ip in license['ip_lock'].split(',') if ip.strip()]
            if ip_address and ip_address not in allowed_ips:
                conn.close()
                return jsonify({'success': False, 'message': 'IP address not authorized'})
        
        # Check if HWID is already activated
        if hwid:
            cursor.execute('SELECT * FROM license_activations WHERE license_id = ? AND hwid = ?', (license['id'], hwid))
            existing_activation = cursor.fetchone()
            
            if existing_activation:
                # Update existing activation
                cursor.execute('''
                    UPDATE license_activations SET 
                        is_active = 1,
                        last_check = CURRENT_TIMESTAMP,
                        device_name = COALESCE(?, device_name),
                        ip_address = ?
                    WHERE id = ?
                ''', (device_name, ip_address, existing_activation['id']))
            else:
                # Check max devices limit
                cursor.execute('SELECT COUNT(*) FROM license_activations WHERE license_id = ? AND is_active = 1', (license['id'],))
                active_count = cursor.fetchone()[0]
                
                if active_count >= license['max_devices']:
                    conn.close()
                    return jsonify({'success': False, 'message': 'Maximum device limit reached'})
                
                # Create new activation
                cursor.execute('''
                    INSERT INTO license_activations (license_id, hwid, device_name, ip_address)
                    VALUES (?, ?, ?, ?)
                ''', (license['id'], hwid, device_name, ip_address))
        
        # Update license stats
        cursor.execute('''
            UPDATE licenses SET 
                total_activations = total_activations + 1,
                last_active = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (license['id'],))
        
        conn.commit()
        conn.close()
        
        # Calculate days left (24h/day)
        days_left = 0
        if license['expires_at']:
            try:
                expires = datetime.strptime(license['expires_at'], '%Y-%m-%d %H:%M:%S')
                days_left = max(0, (expires - datetime.now()).days)
            except:
                pass
        
        return jsonify({
            'success': True,
            'message': 'License is valid',
            'license': {
                'key': license['license_key'],
                'product': license['product'],
                'owner': license['owner'] or '',
                'max_devices': license['max_devices'],
                'days_left': days_left,
                'status': license['status']
            }
        })
    except Exception as e:
        logger.error(f"Verify license error: {str(e)}")
        return jsonify({'success': False, 'message': 'Server error'}), 500

# ============ SERVER API (FOR SHELL SCRIPTS) ============
@app.route('/api/server/licenses', methods=['GET'])
@server_key_required
def server_get_licenses():
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 100))
        offset = (page - 1) * limit
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT license_key, product, owner, status, expires_at, 
                   max_devices, total_activations, created_at
            FROM licenses 
            ORDER BY created_at DESC 
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        
        rows = cursor.fetchall()
        conn.close()
        
        licenses = []
        for row in rows:
            licenses.append({
                'license_key': row['license_key'],
                'product': row['product'],
                'owner': row['owner'] or '',
                'status': row['status'],
                'expires_at': row['expires_at'],
                'max_devices': row['max_devices'],
                'total_activations': row['total_activations'],
                'created_at': row['created_at']
            })
        
        return jsonify({'success': True, 'data': licenses})
    except Exception as e:
        logger.error(f"Server get licenses error: {str(e)}")
        return jsonify({'success': False, 'message': 'Error getting licenses'}), 500

@app.route('/api/server/licenses/create', methods=['POST'])
@server_key_required
def server_create_license():
    try:
        data = request.get_json()
        
        product = data.get('product', 'Default Product').strip()
        if not product:
            return jsonify({'success': False, 'message': 'Product name is required'}), 400
        
        # Generate license key
        license_key = generate_license_key()
        
        # Calculate expiry (24h/day)
        days = int(data.get('days', 30))
        expires_at = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO licenses (license_key, product, owner, expires_at, custom_days, max_devices)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            license_key,
            product,
            data.get('owner', '').strip(),
            expires_at,
            days,
            int(data.get('max_devices', 1))
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': 'License created successfully',
            'license_key': license_key,
            'expires_at': expires_at,
            'days': days
        })
    except Exception as e:
        logger.error(f"Server create license error: {str(e)}")
        return jsonify({'success': False, 'message': 'Error creating license'}), 500

@app.route('/api/server/licenses/<string:license_key>', methods=['GET'])
@server_key_required
def server_get_license(license_key):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM licenses WHERE license_key = ?', (license_key.upper(),))
        license = cursor.fetchone()
        
        if not license:
            conn.close()
            return jsonify({'success': False, 'message': 'License not found'}), 404
        
        # Get activations
        cursor.execute('SELECT * FROM license_activations WHERE license_id = ?', (license['id'],))
        activations = cursor.fetchall()
        
        conn.close()
        
        # Calculate days left
        days_left = 0
        if license['expires_at']:
            try:
                expires = datetime.strptime(license['expires_at'], '%Y-%m-%d %H:%M:%S')
                days_left = max(0, (expires - datetime.now()).days)
            except:
                pass
        
        license_data = {
            'license_key': license['license_key'],
            'product': license['product'],
            'owner': license['owner'] or '',
            'status': license['status'],
            'created_at': license['created_at'],
            'expires_at': license['expires_at'],
            'max_devices': license['max_devices'],
            'notes': license['notes'],
            'hwid_lock': license['hwid_lock'],
            'ip_lock': license['ip_lock'],
            'total_activations': license['total_activations'],
            'last_active': license['last_active'],
            'days_left': days_left
        }
        
        activations_list = []
        for act in activations:
            activations_list.append({
                'hwid': act['hwid'],
                'ip_address': act['ip_address'],
                'device_name': act['device_name'],
                'activated_at': act['activated_at'],
                'last_check': act['last_check'],
                'is_active': bool(act['is_active'])
            })
        
        return jsonify({
            'success': True,
            'license': license_data,
            'activations': activations_list
        })
    except Exception as e:
        logger.error(f"Server get license error: {str(e)}")
        return jsonify({'success': False, 'message': 'Error getting license'}), 500

@app.route('/api/server/licenses/<string:license_key>/reset', methods=['POST'])
@server_key_required
def server_reset_license(license_key):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM licenses WHERE license_key = ?', (license_key.upper(),))
        license = cursor.fetchone()
        
        if not license:
            conn.close()
            return jsonify({'success': False, 'message': 'License not found'}), 404
        
        # Delete all activations
        cursor.execute('DELETE FROM license_activations WHERE license_id = ?', (license['id'],))
        
        # Reset license
        cursor.execute('''
            UPDATE licenses SET 
                total_activations = 0,
                last_active = NULL,
                reset_count = reset_count + 1,
                last_reset = CURRENT_TIMESTAMP,
                status = 'active'
            WHERE id = ?
        ''', (license['id'],))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'License reset successfully'})
    except Exception as e:
        logger.error(f"Server reset license error: {str(e)}")
        return jsonify({'success': False, 'message': 'Error resetting license'}), 500

@app.route('/api/server/licenses/<string:license_key>/ban', methods=['POST'])
@server_key_required
def server_ban_license(license_key):
    try:
        reason = request.json.get('reason', 'Violation detected')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE licenses SET 
                status = 'banned',
                notes = COALESCE(notes || ?, ?)
            WHERE license_key = ?
        ''', ('\n[BANNED] ' + reason, '[BANNED] ' + reason, license_key.upper()))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'License banned successfully'})
    except Exception as e:
        logger.error(f"Server ban license error: {str(e)}")
        return jsonify({'success': False, 'message': 'Error banning license'}), 500

@app.route('/api/server/licenses/<string:license_key>/extend', methods=['POST'])
@server_key_required
def server_extend_license(license_key):
    try:
        days = int(request.json.get('days', 30))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM licenses WHERE license_key = ?', (license_key.upper(),))
        license = cursor.fetchone()
        
        if not license:
            conn.close()
            return jsonify({'success': False, 'message': 'License not found'}), 404
        
        # Calculate new expiry
        if license['expires_at']:
            try:
                current_expiry = datetime.strptime(license['expires_at'], '%Y-%m-%d %H:%M:%S')
                new_expiry = current_expiry + timedelta(days=days)
            except:
                new_expiry = datetime.now() + timedelta(days=days)
        else:
            new_expiry = datetime.now() + timedelta(days=days)
        
        cursor.execute('''
            UPDATE licenses SET 
                expires_at = ?,
                status = 'active',
                custom_days = custom_days + ?
            WHERE license_key = ?
        ''', (new_expiry.strftime('%Y-%m-%d %H:%M:%S'), days, license_key.upper()))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': f'License extended by {days} days',
            'new_expiry': new_expiry.strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        logger.error(f"Server extend license error: {str(e)}")
        return jsonify({'success': False, 'message': 'Error extending license'}), 500

# ============ SYSTEM ENDPOINTS ============
@app.route('/api/system/status', methods=['GET'])
def system_status():
    return jsonify({
        'status': 'online',
        'timestamp': datetime.now().isoformat(),
        'version': '2.0.0',
        'endpoints': {
            'admin_panel': '/admin',
            'verification': '/api/v1/verify',
            'server_api': '/api/server/*',
            'client_example': '/api/client/example.sh'
        }
    })

@app.route('/api/client/example.sh', methods=['GET'])
def client_example():
    """Example shell script for client verification"""
    example_script = '''#!/bin/bash
# License Verification Script
# Usage: ./verify.sh LICENSE_KEY HWID

LICENSE_KEY="$1"
HWID="$2"
API_KEY="YOUR_API_KEY_HERE"
API_URL="https://your-domain.com/api/v1/verify"

if [ -z "$LICENSE_KEY" ] || [ -z "$HWID" ]; then
    echo "Usage: $0 LICENSE_KEY HWID"
    exit 1
fi

response=$(curl -s -X POST "$API_URL" \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: $API_KEY" \\
  -d "{\\"license_key\\": \\"$LICENSE_KEY\\", \\"hwid\\": \\"$HWID\\"}")

if echo "$response" | grep -q '"success":true'; then
    echo "✅ License is valid!"
    echo "$response" | python3 -m json.tool
    exit 0
else
    echo "❌ License verification failed"
    echo "$response"
    exit 1
fi
'''
    return example_script, 200, {'Content-Type': 'text/plain'}

@app.route('/api/server/example.sh', methods=['GET'])
def server_example():
    """Example shell script for server management"""
    example_script = '''#!/bin/bash
# Server Management Script
# For managing licenses via server API

SERVER_KEY="YOUR_SERVER_KEY_HERE"
BASE_URL="https://your-domain.com/api/server"

function create_license() {
    local product="$1"
    local days="$2"
    local owner="$3"
    
    response=$(curl -s -X POST "$BASE_URL/licenses/create" \\
      -H "Content-Type: application/json" \\
      -H "X-Server-Key: $SERVER_KEY" \\
      -d "{\\"product\\": \\"$product\\", \\"days\\": $days, \\"owner\\": \\"$owner\\"}")
    
    echo "$response"
}

function get_license() {
    local license_key="$1"
    
    response=$(curl -s -X GET "$BASE_URL/licenses/$license_key" \\
      -H "X-Server-Key: $SERVER_KEY")
    
    echo "$response"
}

function reset_license() {
    local license_key="$1"
    
    response=$(curl -s -X POST "$BASE_URL/licenses/$license_key/reset" \\
      -H "X-Server-Key: $SERVER_KEY")
    
    echo "$response"
}

function extend_license() {
    local license_key="$1"
    local days="$2"
    
    response=$(curl -s -X POST "$BASE_URL/licenses/$license_key/extend" \\
      -H "Content-Type: application/json" \\
      -H "X-Server-Key: $SERVER_KEY" \\
      -d "{\\"days\\": $days}")
    
    echo "$response"
}

# Usage examples:
# create_license "MyProduct" 30 "John Doe"
# get_license "LIC-XXXXXXXXXXXX"
# reset_license "LIC-XXXXXXXXXXXX"
# extend_license "LIC-XXXXXXXXXXXX" 30
'''
    return example_script, 200, {'Content-Type': 'text/plain'}

# ============ ERROR HANDLERS ============
@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'message': 'Endpoint not found'}), 404

@app.errorhandler(500)
def server_error(error):
    logger.error(f"Server error: {str(error)}")
    return jsonify({'success': False, 'message': 'Internal server error'}), 500

# ============ MAIN ============
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    logger.info(f"🚀 Starting License Admin System v2.0 on port {port}")
    logger.info(f"📊 Admin Panel: http://localhost:{port}/admin")
    logger.info(f"🔐 Login: admin / Anhhuy123")
    logger.info(f"🌐 API Documentation:")
    logger.info(f"   - Client Verification: POST /api/v1/verify")
    logger.info(f"   - Server Management: /api/server/*")
    logger.info(f"   - System Status: GET /api/system/status")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
