from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_cors import CORS
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
from database import init_db, create_default_admin, create_default_api_key, get_db_connection
import sqlite3
import os

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
CORS(app)

# Khởi tạo database
init_db()
create_default_admin()
create_default_api_key()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return redirect(url_for('login_page'))

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
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
        return jsonify({'success': True, 'message': 'Đăng nhập thành công'})
    else:
        return jsonify({'success': False, 'message': 'Tên đăng nhập hoặc mật khẩu không đúng'}), 401

@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Đã đăng xuất'})

@app.route('/admin')
@login_required
def admin_dashboard():
    return render_template('admin.html')

@app.route('/api/admin/stats')
@login_required
def get_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Lấy tổng số license
    cursor.execute('SELECT COUNT(*) FROM licenses')
    total_licenses = cursor.fetchone()[0]
    
    # Lấy số license active
    cursor.execute('SELECT COUNT(*) FROM licenses WHERE status = "active"')
    active_licenses = cursor.fetchone()[0]
    
    # Lấy số license inactive
    cursor.execute('SELECT COUNT(*) FROM licenses WHERE status = "inactive"')
    inactive_licenses = cursor.fetchone()[0]
    
    # Lấy số license expired
    cursor.execute('SELECT COUNT(*) FROM licenses WHERE status = "expired"')
    expired_licenses = cursor.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'total_licenses': total_licenses,
        'active_licenses': active_licenses,
        'inactive_licenses': inactive_licenses,
        'expired_licenses': expired_licenses
    })

@app.route('/api/admin/licenses')
@login_required
def get_licenses():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM licenses ORDER BY created_at DESC')
    licenses = cursor.fetchall()
    conn.close()
    
    licenses_list = []
    for license in licenses:
        licenses_list.append({
            'id': license[0],
            'license_key': license[1],
            'product': license[2],
            'owner': license[3],
            'status': license[4],
            'created_at': license[5],
            'expires_at': license[6],
            'max_devices': license[7],
            'notes': license[8]
        })
    
    return jsonify(licenses_list)

@app.route('/api/admin/licenses/create', methods=['POST'])
@login_required
def create_license():
    data = request.get_json()
    
    # Tạo license key ngẫu nhiên
    license_key = f"LIC-{secrets.token_hex(8).upper()}-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}-{secrets.token_hex(12).upper()}"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
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
        
        return jsonify({'success': True, 'license_key': license_key})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/licenses/update/<int:license_id>', methods=['POST'])
@login_required
def update_license(license_id):
    data = request.get_json()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE licenses 
            SET product = ?, owner = ?, status = ?, expires_at = ?, max_devices = ?, notes = ?
            WHERE id = ?
        ''', (
            data.get('product'),
            data.get('owner'),
            data.get('status'),
            data.get('expires_at'),
            data.get('max_devices'),
            data.get('notes'),
            license_id
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/licenses/delete/<int:license_id>', methods=['POST'])
@login_required
def delete_license(license_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('DELETE FROM licenses WHERE id = ?', (license_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/apikeys')
@login_required
def get_apikeys():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM api_keys ORDER BY created_at DESC')
    apikeys = cursor.fetchall()
    conn.close()
    
    apikeys_list = []
    for key in apikeys:
        apikeys_list.append({
            'id': key[0],
            'key': key[1],
            'name': key[2],
            'status': key[3],
            'created_at': key[4]
        })
    
    return jsonify(apikeys_list)

@app.route('/api/admin/apikeys/create', methods=['POST'])
@login_required
def create_apikey():
    data = request.get_json()
    api_key = f"sk_{secrets.token_hex(16)}"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO api_keys (api_key, name, status)
            VALUES (?, ?, ?)
        ''', (api_key, data.get('name', 'New API Key'), 'active'))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'api_key': api_key})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/apikeys/delete/<int:key_id>', methods=['POST'])
@login_required
def delete_apikey(key_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('DELETE FROM api_keys WHERE id = ?', (key_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/debug')
def debug_info():
    return jsonify({
        'status': 'online',
        'server_time': datetime.now().isoformat(),
        'version': '1.0.0'
    })

@app.route('/api/verify', methods=['POST'])
def verify_license():
    data = request.get_json()
    license_key = data.get('license_key')
    hwid = data.get('hwid')
    api_key = request.headers.get('X-API-Key')
    
    if not api_key:
        return jsonify({'valid': False, 'message': 'API key required'}), 401
    
    # Kiểm tra API key
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM api_keys WHERE api_key = ? AND status = "active"', (api_key,))
    valid_api_key = cursor.fetchone()
    
    if not valid_api_key:
        conn.close()
        return jsonify({'valid': False, 'message': 'Invalid API key'}), 401
    
    # Kiểm tra license
    cursor.execute('SELECT * FROM licenses WHERE license_key = ? AND status = "active"', (license_key,))
    license = cursor.fetchone()
    
    if not license:
        conn.close()
        return jsonify({'valid': False, 'message': 'Invalid license'})
    
    # Kiểm tra expiration
    if license[6]:  # expires_at
        expires_at = datetime.strptime(license[6], '%Y-%m-%d')
        if expires_at < datetime.now():
            cursor.execute('UPDATE licenses SET status = "expired" WHERE id = ?', (license[0],))
            conn.commit()
            conn.close()
            return jsonify({'valid': False, 'message': 'License expired'})
    
    conn.close()
    return jsonify({'valid': True, 'message': 'License valid'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)