"""
Admin Panel - Server Key & API Manager
Phiên bản tối giản, code sạch, ít lỗi
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import os
import secrets
import jwt
from datetime import datetime, timedelta
from functools import wraps
import hashlib

# ==================== INITIALIZATION ====================
app = Flask(__name__, static_folder='.')
CORS(app, supports_credentials=True)

# Configuration
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-key-change-in-production'),
    ADMIN_USERNAME=os.environ.get('ADMIN_USERNAME', 'admin'),
    ADMIN_PASSWORD_HASH=os.environ.get('ADMIN_PASSWORD_HASH', 
        hashlib.sha256('admin123'.encode()).hexdigest()),  # Default hash of 'admin123'
    JWT_SECRET=os.environ.get('JWT_SECRET', 'jwt-secret-change-me'),
    JWT_EXPIRES_HOURS=24
)

# In-memory storage (for demo - replace with database in production)
keys_storage = []
activity_logs = []
next_id = 1

# ==================== AUTHENTICATION ====================
def generate_token(username):
    """Generate JWT token"""
    payload = {
        'username': username,
        'role': 'admin',
        'exp': datetime.utcnow() + timedelta(hours=app.config['JWT_EXPIRES_HOURS']),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, app.config['JWT_SECRET'], algorithm='HS256')

def verify_token(token):
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, app.config['JWT_SECRET'], algorithms=['HS256'])
        return payload
    except:
        return None

def login_required(f):
    """Decorator for protected routes"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        # Get token from cookie
        if not token:
            token = request.cookies.get('token')
        
        if not token:
            return jsonify({'success': False, 'error': 'Token required'}), 401
        
        payload = verify_token(token)
        if not payload:
            return jsonify({'success': False, 'error': 'Invalid token'}), 401
        
        request.user = payload
        return f(*args, **kwargs)
    
    return decorated

# ==================== KEY MANAGEMENT FUNCTIONS ====================
def generate_server_key():
    """Generate secure server key"""
    return f"sk_{secrets.token_hex(24)}"

def generate_api_key():
    """Generate secure API key"""
    return f"api_{secrets.token_hex(32)}"

def log_activity(action, details, key_id=None):
    """Log admin activity"""
    activity_logs.append({
        'id': len(activity_logs) + 1,
        'key_id': key_id,
        'action': action,
        'details': details,
        'timestamp': datetime.now().isoformat(),
        'ip': request.remote_addr
    })
    # Keep only last 100 logs
    if len(activity_logs) > 100:
        activity_logs.pop(0)

# ==================== ROUTES ====================

@app.route('/')
def index():
    """Serve admin panel"""
    return render_template('admin.html')

# ========== AUTH ROUTES ==========

@app.route('/api/login', methods=['POST'])
def login():
    """Admin login"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Invalid request'}), 400
        
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Missing credentials'}), 400
        
        # Verify credentials
        if username != app.config['ADMIN_USERNAME']:
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
        
        # Hash the provided password and compare
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if password_hash != app.config['ADMIN_PASSWORD_HASH']:
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
        
        # Generate token
        token = generate_token(username)
        
        response = jsonify({
            'success': True,
            'message': 'Login successful',
            'token': token,
            'user': {'username': username}
        })
        
        # Set HTTP-only cookie
        response.set_cookie(
            'token',
            token,
            httponly=True,
            secure=os.environ.get('FLASK_ENV') == 'production',
            samesite='Strict',
            max_age=86400  # 24 hours
        )
        
        log_activity('LOGIN', f'User {username} logged in')
        return response
        
    except Exception as e:
        return jsonify({'success': False, 'error': 'Server error'}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    """Admin logout"""
    response = jsonify({'success': True, 'message': 'Logged out'})
    response.delete_cookie('token')
    log_activity('LOGOUT', 'User logged out')
    return response

@app.route('/api/verify', methods=['GET'])
@login_required
def verify():
    """Verify token"""
    return jsonify({
        'success': True,
        'user': request.user
    })

# ========== KEY MANAGEMENT ROUTES ==========

@app.route('/api/keys', methods=['GET'])
@login_required
def get_keys():
    """Get all keys with optional filtering"""
    try:
        status_filter = request.args.get('status')
        search_query = request.args.get('search', '').lower()
        
        filtered_keys = keys_storage.copy()
        
        # Apply status filter
        if status_filter:
            filtered_keys = [k for k in filtered_keys if k['status'] == status_filter]
        
        # Apply search filter
        if search_query:
            filtered_keys = [
                k for k in filtered_keys
                if search_query in k['key_name'].lower() or 
                   search_query in k['server_key'].lower() or
                   search_query in k['api_key'].lower()
            ]
        
        # Sort by creation date (newest first)
        filtered_keys.sort(key=lambda x: x['created_at'], reverse=True)
        
        # Calculate statistics
        total = len(keys_storage)
        active = sum(1 for k in keys_storage if k['status'] == 'active')
        locked = total - active
        
        return jsonify({
            'success': True,
            'data': filtered_keys,
            'stats': {'total': total, 'active': active, 'locked': locked}
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': 'Failed to get keys'}), 500

@app.route('/api/keys', methods=['POST'])
@login_required
def create_key():
    """Create new server key and API key"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Invalid request'}), 400
        
        key_name = data.get('key_name', '').strip()
        notes = data.get('notes', '').strip()
        
        if not key_name:
            return jsonify({'success': False, 'error': 'Key name is required'}), 400
        
        global next_id
        
        # Generate new keys
        new_key = {
            'id': next_id,
            'key_name': key_name,
            'server_key': generate_server_key(),
            'api_key': generate_api_key(),
            'status': 'active',
            'notes': notes,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'last_reset_at': None
        }
        
        keys_storage.append(new_key)
        next_id += 1
        
        log_activity('CREATE', f'Created key: {key_name}', new_key['id'])
        
        return jsonify({
            'success': True,
            'message': 'Key created successfully',
            'data': new_key
        }), 201
        
    except Exception as e:
        return jsonify({'success': False, 'error': 'Failed to create key'}), 500

@app.route('/api/keys/<int:key_id>/reset', methods=['PUT'])
@login_required
def reset_key(key_id):
    """Reset API key"""
    try:
        key = next((k for k in keys_storage if k['id'] == key_id), None)
        if not key:
            return jsonify({'success': False, 'error': 'Key not found'}), 404
        
        # Generate new API key
        key['api_key'] = generate_api_key()
        key['last_reset_at'] = datetime.now().isoformat()
        key['updated_at'] = datetime.now().isoformat()
        
        log_activity('RESET', f'Reset API key for: {key["key_name"]}', key_id)
        
        return jsonify({
            'success': True,
            'message': 'API key reset successfully',
            'data': {
                'id': key['id'],
                'key_name': key['key_name'],
                'api_key': key['api_key'],
                'last_reset_at': key['last_reset_at']
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': 'Failed to reset key'}), 500

@app.route('/api/keys/<int:key_id>/lock', methods=['PUT'])
@login_required
def toggle_lock_key(key_id):
    """Lock or unlock a key"""
    try:
        key = next((k for k in keys_storage if k['id'] == key_id), None)
        if not key:
            return jsonify({'success': False, 'error': 'Key not found'}), 404
        
        # Toggle status
        new_status = 'locked' if key['status'] == 'active' else 'active'
        key['status'] = new_status
        key['updated_at'] = datetime.now().isoformat()
        
        action = 'LOCKED' if new_status == 'locked' else 'UNLOCKED'
        log_activity(action, f'{action} key: {key["key_name"]}', key_id)
        
        return jsonify({
            'success': True,
            'message': f'Key {new_status} successfully',
            'data': {
                'id': key['id'],
                'key_name': key['key_name'],
                'status': key['status']
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': 'Failed to update key'}), 500

@app.route('/api/keys/<int:key_id>', methods=['DELETE'])
@login_required
def delete_key(key_id):
    """Delete a key"""
    try:
        key = next((k for k in keys_storage if k['id'] == key_id), None)
        if not key:
            return jsonify({'success': False, 'error': 'Key not found'}), 404
        
        # Remove key
        keys_storage[:] = [k for k in keys_storage if k['id'] != key_id]
        
        log_activity('DELETE', f'Deleted key: {key["key_name"]}', key_id)
        
        return jsonify({
            'success': True,
            'message': 'Key deleted successfully',
            'data': {'id': key_id, 'key_name': key['key_name']}
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': 'Failed to delete key'}), 500

# ========== ACTIVITY & STATS ROUTES ==========

@app.route('/api/activity', methods=['GET'])
@login_required
def get_activity():
    """Get activity logs"""
    try:
        return jsonify({
            'success': True,
            'data': activity_logs[-50:]  # Last 50 activities
        })
    except:
        return jsonify({'success': True, 'data': []})

@app.route('/api/stats', methods=['GET'])
@login_required
def get_stats():
    """Get system statistics"""
    try:
        total = len(keys_storage)
        active = sum(1 for k in keys_storage if k['status'] == 'active')
        locked = total - active
        recent_activity = len([a for a in activity_logs 
                              if datetime.fromisoformat(a['timestamp']) > 
                              datetime.now() - timedelta(hours=24)])
        
        return jsonify({
            'success': True,
            'data': {
                'total_keys': total,
                'active_keys': active,
                'locked_keys': locked,
                'recent_activity': recent_activity
            }
        })
    except:
        return jsonify({
            'success': True,
            'data': {'total_keys': 0, 'active_keys': 0, 'locked_keys': 0, 'recent_activity': 0}
        })

# ========== PUBLIC VALIDATION ROUTE ==========

@app.route('/api/validate', methods=['GET'])
def validate_key():
    """Public endpoint to validate a key"""
    try:
        key_value = request.args.get('key')
        if not key_value:
            return jsonify({'success': False, 'error': 'Key parameter required'}), 400
        
        # Find key by server_key or api_key
        key = next((k for k in keys_storage 
                   if k['server_key'] == key_value or k['api_key'] == key_value), None)
        
        if not key:
            return jsonify({'success': False, 'error': 'Invalid key'}), 404
        
        if key['status'] != 'active':
            return jsonify({
                'success': False, 
                'error': f'Key is {key["status"]}'
            }), 403
        
        return jsonify({
            'success': True,
            'data': {
                'key_name': key['key_name'],
                'status': key['status'],
                'created_at': key['created_at']
            }
        })
        
    except:
        return jsonify({'success': False, 'error': 'Validation failed'}), 500

# ========== HEALTH CHECK ==========

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Render"""
    return jsonify({
        'status': 'healthy',
        'service': 'Admin Panel API',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

# ========== STATIC FILES ==========

@app.route('/style.css')
def serve_css():
    return app.send_static_file('style.css')

@app.route('/script.js')
def serve_js():
    return app.send_static_file('script.js')

# ========== ERROR HANDLERS ==========

@app.errorhandler(404)
def not_found(e):
    return jsonify({'success': False, 'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500

# ========== INITIALIZE SAMPLE DATA ==========

def initialize_sample_data():
    """Initialize with sample data for demo"""
    global next_id, keys_storage, activity_logs
    
    if not keys_storage:
        sample_keys = [
            {
                'id': 1,
                'key_name': 'Production Server',
                'server_key': 'sk_prod_' + secrets.token_hex(20),
                'api_key': 'api_prod_' + secrets.token_hex(28),
                'status': 'active',
                'notes': 'Main production server',
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'last_reset_at': None
            },
            {
                'id': 2,
                'key_name': 'Staging Environment',
                'server_key': 'sk_stage_' + secrets.token_hex(20),
                'api_key': 'api_stage_' + secrets.token_hex(28),
                'status': 'active',
                'notes': 'Testing and staging',
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'last_reset_at': None
            },
            {
                'id': 3,
                'key_name': 'Development',
                'server_key': 'sk_dev_' + secrets.token_hex(20),
                'api_key': 'api_dev_' + secrets.token_hex(28),
                'status': 'locked',
                'notes': 'Development server (currently locked)',
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'last_reset_at': None
            }
        ]
        
        keys_storage.extend(sample_keys)
        next_id = 4
        
        # Add sample activity logs
        log_activity('SYSTEM', 'System initialized with sample data')
        log_activity('CREATE', 'Created key: Production Server', 1)
        log_activity('CREATE', 'Created key: Staging Environment', 2)
        log_activity('CREATE', 'Created key: Development', 3)
        log_activity('LOCK', 'Locked key: Development', 3)

# ========== START APPLICATION ==========

if __name__ == '__main__':
    # Initialize sample data
    initialize_sample_data()
    
    # Get port from environment or default
    port = int(os.environ.get('PORT', 5000))
    
    # Run app
    print(f"🚀 Admin Panel starting on port {port}")
    print(f"🔐 Admin login: {app.config['ADMIN_USERNAME']}")
    print(f"📊 Sample keys initialized: {len(keys_storage)}")
    
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_ENV') != 'production')
