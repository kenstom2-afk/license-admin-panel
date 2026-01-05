from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_cors import CORS
from functools import wraps
import os
from datetime import datetime, timedelta
import secrets
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor
from config import Config
from database import get_db_connection, init_database
from auth import login_required, generate_token, verify_token

app = Flask(__name__, static_folder='.')
app.config.from_object(Config)
CORS(app)

# Khởi tạo database
init_database()

# ==================== Routes ====================

@app.route('/')
@login_required
def index():
    """Render admin panel"""
    return render_template('admin.html')

@app.route('/login', methods=['POST'])
def login():
    """Đăng nhập"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    # Kiểm tra thông tin đăng nhập
    if username != app.config['ADMIN_USERNAME']:
        return jsonify({'success': False, 'error': 'Sai thông tin đăng nhập'}), 401
    
    # Kiểm tra password (hash với bcrypt trong production)
    if password != app.config['ADMIN_PASSWORD']:
        return jsonify({'success': False, 'error': 'Sai thông tin đăng nhập'}), 401
    
    # Tạo token
    token = generate_token(username)
    
    return jsonify({
        'success': True,
        'message': 'Đăng nhập thành công',
        'token': token,
        'user': {'username': username}
    })

@app.route('/api/keys', methods=['GET'])
@login_required
def get_keys():
    """Lấy danh sách tất cả keys"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Lấy tham số filter
    status = request.args.get('status')
    search = request.args.get('search', '')
    
    query = "SELECT * FROM api_keys WHERE 1=1"
    params = []
    
    if status:
        query += " AND status = %s"
        params.append(status)
    
    if search:
        query += " AND (key_name ILIKE %s OR server_key ILIKE %s OR api_key ILIKE %s)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term, search_term])
    
    query += " ORDER BY created_at DESC"
    
    cur.execute(query, params)
    keys = cur.fetchall()
    
    # Đếm thống kê
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN status = 'active' THEN 1 END) as active,
            COUNT(CASE WHEN status = 'locked' THEN 1 END) as locked
        FROM api_keys
    """)
    stats = cur.fetchone()
    
    cur.close()
    conn.close()
    
    return jsonify({
        'success': True,
        'data': keys,
        'stats': stats
    })

@app.route('/api/keys', methods=['POST'])
@login_required
def create_key():
    """Tạo key mới"""
    data = request.get_json()
    key_name = data.get('key_name')
    notes = data.get('notes', '')
    
    if not key_name:
        return jsonify({'success': False, 'error': 'Tên key là bắt buộc'}), 400
    
    # Tạo keys ngẫu nhiên
    server_key = f"sk_{secrets.token_hex(24)}"
    api_key = f"api_{secrets.token_hex(32)}"
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        INSERT INTO api_keys (key_name, server_key, api_key, notes)
        VALUES (%s, %s, %s, %s)
        RETURNING *
    """, (key_name, server_key, api_key, notes))
    
    new_key = cur.fetchone()
    conn.commit()
    
    # Ghi log
    cur.execute("""
        INSERT INTO activity_logs (key_id, action, details)
        VALUES (%s, %s, %s)
    """, (new_key['id'], 'CREATE', f'Tạo key mới: {key_name}'))
    conn.commit()
    
    cur.close()
    conn.close()
    
    return jsonify({
        'success': True,
        'message': 'Key đã được tạo thành công',
        'data': new_key
    }), 201

@app.route('/api/keys/<int:key_id>/reset', methods=['PUT'])
@login_required
def reset_key(key_id):
    """Reset API key"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Kiểm tra key tồn tại
    cur.execute("SELECT * FROM api_keys WHERE id = %s", (key_id,))
    key = cur.fetchone()
    
    if not key:
        cur.close()
        conn.close()
        return jsonify({'success': False, 'error': 'Key không tồn tại'}), 404
    
    # Tạo API key mới
    new_api_key = f"api_{secrets.token_hex(32)}"
    
    cur.execute("""
        UPDATE api_keys 
        SET api_key = %s, last_reset_at = NOW(), updated_at = NOW()
        WHERE id = %s
        RETURNING *
    """, (new_api_key, key_id))
    
    updated_key = cur.fetchone()
    
    # Ghi log
    cur.execute("""
        INSERT INTO activity_logs (key_id, action, details)
        VALUES (%s, %s, %s)
    """, (key_id, 'RESET', f'Reset API key: {key["key_name"]}'))
    
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({
        'success': True,
        'message': 'Key đã được reset thành công',
        'data': updated_key
    })

@app.route('/api/keys/<int:key_id>/lock', methods=['PUT'])
@login_required
def toggle_lock(key_id):
    """Lock/Unlock key"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Kiểm tra key tồn tại
    cur.execute("SELECT * FROM api_keys WHERE id = %s", (key_id,))
    key = cur.fetchone()
    
    if not key:
        cur.close()
        conn.close()
        return jsonify({'success': False, 'error': 'Key không tồn tại'}), 404
    
    # Chuyển đổi trạng thái
    new_status = 'locked' if key['status'] == 'active' else 'active'
    
    cur.execute("""
        UPDATE api_keys 
        SET status = %s, updated_at = NOW()
        WHERE id = %s
        RETURNING *
    """, (new_status, key_id))
    
    updated_key = cur.fetchone()
    
    # Ghi log
    action = 'LOCK' if new_status == 'locked' else 'UNLOCK'
    cur.execute("""
        INSERT INTO activity_logs (key_id, action, details)
        VALUES (%s, %s, %s)
    """, (key_id, action, f'{action} key: {key["key_name"]}'))
    
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({
        'success': True,
        'message': f'Key đã được {new_status} thành công',
        'data': updated_key
    })

@app.route('/api/keys/<int:key_id>', methods=['DELETE'])
@login_required
def delete_key(key_id):
    """Xóa key"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Kiểm tra key tồn tại
    cur.execute("SELECT * FROM api_keys WHERE id = %s", (key_id,))
    key = cur.fetchone()
    
    if not key:
        cur.close()
        conn.close()
        return jsonify({'success': False, 'error': 'Key không tồn tại'}), 404
    
    # Lưu thông tin trước khi xóa
    key_name = key['key_name']
    
    # Xóa key
    cur.execute("DELETE FROM api_keys WHERE id = %s RETURNING id", (key_id,))
    
    # Ghi log
    cur.execute("""
        INSERT INTO activity_logs (key_id, action, details)
        VALUES (%s, %s, %s)
    """, (None, 'DELETE', f'Xóa key: {key_name}'))
    
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({
        'success': True,
        'message': 'Key đã được xóa thành công'
    })

@app.route('/api/activity', methods=['GET'])
@login_required
def get_activity():
    """Lấy lịch sử hoạt động"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT al.*, ak.key_name 
        FROM activity_logs al
        LEFT JOIN api_keys ak ON al.key_id = ak.id
        ORDER BY al.performed_at DESC
        LIMIT 50
    """)
    
    activity = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify({
        'success': True,
        'data': activity
    })

@app.route('/api/validate', methods=['GET'])
def validate_key():
    """Kiểm tra key hợp lệ (public endpoint)"""
    key = request.args.get('key')
    
    if not key:
        return jsonify({'success': False, 'error': 'Thiếu tham số key'}), 400
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT key_name, status, created_at, last_reset_at
        FROM api_keys 
        WHERE server_key = %s OR api_key = %s
    """, (key, key))
    
    key_data = cur.fetchone()
    cur.close()
    conn.close()
    
    if not key_data:
        return jsonify({'success': False, 'error': 'Key không tồn tại'}), 404
    
    if key_data['status'] != 'active':
        return jsonify({
            'success': False, 
            'error': f'Key đã bị {key_data["status"]}'
        }), 403
    
    return jsonify({
        'success': True,
        'data': key_data
    })

@app.route('/api/stats', methods=['GET'])
@login_required
def get_stats():
    """Lấy thống kê"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Thống kê cơ bản
    cur.execute("""
        SELECT 
            COUNT(*) as total_keys,
            COUNT(CASE WHEN status = 'active' THEN 1 END) as active_keys,
            COUNT(CASE WHEN status = 'locked' THEN 1 END) as locked_keys,
            COUNT(DISTINCT DATE(created_at)) as days_active,
            COALESCE(COUNT(last_reset_at), 0) as total_resets
        FROM api_keys
    """)
    
    stats = cur.fetchone()
    
    # Hoạt động gần đây
    cur.execute("""
        SELECT COUNT(*) as recent_activity
        FROM activity_logs 
        WHERE performed_at > NOW() - INTERVAL '24 hours'
    """)
    
    recent = cur.fetchone()
    
    cur.close()
    conn.close()
    
    return jsonify({
        'success': True,
        'data': {
            **stats,
            'recent_activity': recent['recent_activity']
        }
    })

# ==================== Health Check ====================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        conn = get_db_connection()
        conn.close()
        db_status = 'connected'
    except Exception as e:
        db_status = f'error: {str(e)}'
    
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'database': db_status,
        'service': 'Admin Panel API'
    })

# ==================== Run App ====================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
