from flask import Flask, render_template, jsonify, request, make_response
from flask_cors import CORS
from functools import wraps
import os
from datetime import datetime, timedelta
import secrets
import jwt
from config import Config
from database import get_db, init_database, check_db_connection
from auth import login_required, generate_token, verify_token
import json

app = Flask(__name__, static_folder='.')
app.config.from_object(Config)
CORS(app)

# ==================== Routes ====================

@app.route('/')
def index():
    """Render admin panel - KHÔNG yêu cầu login ở trang chủ"""
    return render_template('admin.html')

@app.route('/login', methods=['POST'])
def login():
    """Đăng nhập"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON'}), 400
            
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Username và password là bắt buộc'}), 400
        
        # Kiểm tra thông tin đăng nhập
        if username != app.config['ADMIN_USERNAME']:
            return jsonify({'success': False, 'error': 'Sai thông tin đăng nhập'}), 401
        
        if password != app.config['ADMIN_PASSWORD']:
            return jsonify({'success': False, 'error': 'Sai thông tin đăng nhập'}), 401
        
        # Tạo token
        token = generate_token(username)
        
        response = jsonify({
            'success': True,
            'message': 'Đăng nhập thành công',
            'token': token,
            'user': {'username': username}
        })
        
        # Set HTTP-only cookie
        response.set_cookie(
            'token',
            token,
            httponly=True,
            secure=app.config.get('ENVIRONMENT') == 'production',
            samesite='Strict',
            max_age=24*60*60  # 24 giờ
        )
        
        return response
        
    except Exception as e:
        print(f"Login error: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@app.route('/api/verify', methods=['GET'])
@login_required
def verify():
    """Xác thực token"""
    return jsonify({
        'success': True,
        'data': {
            'user': request.user,
            'valid': True
        }
    })

@app.route('/api/keys', methods=['GET'])
@login_required
def get_keys():
    """Lấy danh sách tất cả keys"""
    try:
        conn = get_db()
        if conn is None:
            return jsonify({
                'success': False, 
                'error': 'Database không khả dụng',
                'data': []
            })
        
        cursor = conn.cursor()
        
        # Lấy tham số filter
        status = request.args.get('status')
        search = request.args.get('search', '')
        
        query = """
            SELECT id, key_name, server_key, api_key, status, notes, 
                   created_at, updated_at, last_reset_at
            FROM api_keys 
            WHERE 1=1
        """
        params = []
        
        if status:
            query += " AND status = %s"
            params.append(status)
        
        if search:
            query += " AND (key_name ILIKE %s OR server_key ILIKE %s OR api_key ILIKE %s)"
            search_term = f"%{search}%"
            params.extend([search_term, search_term, search_term])
        
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query, params)
        keys = cursor.fetchall()
        
        # Chuyển đổi sang dict
        keys_list = []
        for key in keys:
            keys_list.append({
                'id': key[0],
                'key_name': key[1],
                'server_key': key[2],
                'api_key': key[3],
                'status': key[4],
                'notes': key[5],
                'created_at': key[6].isoformat() if key[6] else None,
                'updated_at': key[7].isoformat() if key[7] else None,
                'last_reset_at': key[8].isoformat() if key[8] else None
            })
        
        # Đếm thống kê
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'active' THEN 1 END) as active,
                COUNT(CASE WHEN status = 'locked' THEN 1 END) as locked
            FROM api_keys
        """)
        stats = cursor.fetchone()
        
        cursor.close()
        
        return jsonify({
            'success': True,
            'data': keys_list,
            'stats': {
                'total': stats[0] if stats else 0,
                'active': stats[1] if stats else 0,
                'locked': stats[2] if stats else 0
            }
        })
        
    except Exception as e:
        print(f"Get keys error: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error', 'data': []}), 500

@app.route('/api/keys', methods=['POST'])
@login_required
def create_key():
    """Tạo key mới"""
    try:
        conn = get_db()
        if conn is None:
            return jsonify({'success': False, 'error': 'Database không khả dụng'}), 503
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON'}), 400
            
        key_name = data.get('key_name')
        notes = data.get('notes', '')
        
        if not key_name:
            return jsonify({'success': False, 'error': 'Tên key là bắt buộc'}), 400
        
        # Tạo keys ngẫu nhiên
        server_key = f"sk_{secrets.token_hex(24)}"
        api_key = f"api_{secrets.token_hex(32)}"
        
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO api_keys (key_name, server_key, api_key, notes)
            VALUES (%s, %s, %s, %s)
            RETURNING id, key_name, server_key, api_key, status, notes, created_at
        """, (key_name, server_key, api_key, notes))
        
        new_key = cursor.fetchone()
        
        # Ghi log
        cursor.execute("""
            INSERT INTO activity_logs (key_id, action, details)
            VALUES (%s, %s, %s)
        """, (new_key[0], 'CREATE', f'Tạo key mới: {key_name}'))
        
        conn.commit()
        cursor.close()
        
        return jsonify({
            'success': True,
            'message': 'Key đã được tạo thành công',
            'data': {
                'id': new_key[0],
                'key_name': new_key[1],
                'server_key': new_key[2],
                'api_key': new_key[3],
                'status': new_key[4],
                'notes': new_key[5],
                'created_at': new_key[6].isoformat() if new_key[6] else None
            }
        }), 201
        
    except Exception as e:
        print(f"Create key error: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@app.route('/api/keys/<int:key_id>/reset', methods=['PUT'])
@login_required
def reset_key(key_id):
    """Reset API key"""
    try:
        conn = get_db()
        if conn is None:
            return jsonify({'success': False, 'error': 'Database không khả dụng'}), 503
        
        cursor = conn.cursor()
        
        # Kiểm tra key tồn tại
        cursor.execute("SELECT id, key_name FROM api_keys WHERE id = %s", (key_id,))
        key = cursor.fetchone()
        
        if not key:
            cursor.close()
            return jsonify({'success': False, 'error': 'Key không tồn tại'}), 404
        
        # Tạo API key mới
        new_api_key = f"api_{secrets.token_hex(32)}"
        
        cursor.execute("""
            UPDATE api_keys 
            SET api_key = %s, last_reset_at = NOW(), updated_at = NOW()
            WHERE id = %s
            RETURNING id, key_name, server_key, api_key, last_reset_at
        """, (new_api_key, key_id))
        
        updated_key = cursor.fetchone()
        
        # Ghi log
        cursor.execute("""
            INSERT INTO activity_logs (key_id, action, details)
            VALUES (%s, %s, %s)
        """, (key_id, 'RESET', f'Reset API key: {key[1]}'))
        
        conn.commit()
        cursor.close()
        
        return jsonify({
            'success': True,
            'message': 'Key đã được reset thành công',
            'data': {
                'id': updated_key[0],
                'key_name': updated_key[1],
                'server_key': updated_key[2],
                'api_key': updated_key[3],
                'last_reset_at': updated_key[4].isoformat() if updated_key[4] else None
            }
        })
        
    except Exception as e:
        print(f"Reset key error: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@app.route('/api/keys/<int:key_id>/lock', methods=['PUT'])
@login_required
def toggle_lock(key_id):
    """Lock/Unlock key"""
    try:
        conn = get_db()
        if conn is None:
            return jsonify({'success': False, 'error': 'Database không khả dụng'}), 503
        
        cursor = conn.cursor()
        
        # Kiểm tra key tồn tại
        cursor.execute("SELECT id, key_name, status FROM api_keys WHERE id = %s", (key_id,))
        key = cursor.fetchone()
        
        if not key:
            cursor.close()
            return jsonify({'success': False, 'error': 'Key không tồn tại'}), 404
        
        # Chuyển đổi trạng thái
        new_status = 'locked' if key[2] == 'active' else 'active'
        
        cursor.execute("""
            UPDATE api_keys 
            SET status = %s, updated_at = NOW()
            WHERE id = %s
            RETURNING id, key_name, status
        """, (new_status, key_id))
        
        updated_key = cursor.fetchone()
        
        # Ghi log
        action = 'LOCK' if new_status == 'locked' else 'UNLOCK'
        cursor.execute("""
            INSERT INTO activity_logs (key_id, action, details)
            VALUES (%s, %s, %s)
        """, (key_id, action, f'{action} key: {key[1]}'))
        
        conn.commit()
        cursor.close()
        
        return jsonify({
            'success': True,
            'message': f'Key đã được {new_status} thành công',
            'data': {
                'id': updated_key[0],
                'key_name': updated_key[1],
                'status': updated_key[2]
            }
        })
        
    except Exception as e:
        print(f"Toggle lock error: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@app.route('/api/keys/<int:key_id>', methods=['DELETE'])
@login_required
def delete_key(key_id):
    """Xóa key"""
    try:
        conn = get_db()
        if conn is None:
            return jsonify({'success': False, 'error': 'Database không khả dụng'}), 503
        
        cursor = conn.cursor()
        
        # Kiểm tra key tồn tại
        cursor.execute("SELECT id, key_name FROM api_keys WHERE id = %s", (key_id,))
        key = cursor.fetchone()
        
        if not key:
            cursor.close()
            return jsonify({'success': False, 'error': 'Key không tồn tại'}), 404
        
        # Lưu thông tin trước khi xóa
        key_name = key[1]
        
        # Xóa key
        cursor.execute("DELETE FROM api_keys WHERE id = %s RETURNING id", (key_id,))
        deleted_id = cursor.fetchone()
        
        if not deleted_id:
            conn.rollback()
            cursor.close()
            return jsonify({'success': False, 'error': 'Xóa key thất bại'}), 500
        
        # Ghi log
        cursor.execute("""
            INSERT INTO activity_logs (key_id, action, details)
            VALUES (%s, %s, %s)
        """, (None, 'DELETE', f'Xóa key: {key_name} (ID: {key_id})'))
        
        conn.commit()
        cursor.close()
        
        return jsonify({
            'success': True,
            'message': 'Key đã được xóa thành công',
            'data': {'id': key_id, 'key_name': key_name}
        })
        
    except Exception as e:
        print(f"Delete key error: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@app.route('/api/activity', methods=['GET'])
@login_required
def get_activity():
    """Lấy lịch sử hoạt động"""
    try:
        conn = get_db()
        if conn is None:
            return jsonify({
                'success': True,
                'data': []
            })
        
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT al.id, al.key_id, al.action, al.details, al.performed_at, ak.key_name 
            FROM activity_logs al
            LEFT JOIN api_keys ak ON al.key_id = ak.id
            ORDER BY al.performed_at DESC
            LIMIT 50
        """)
        
        activities = cursor.fetchall()
        
        activity_list = []
        for activity in activities:
            activity_list.append({
                'id': activity[0],
                'key_id': activity[1],
                'action': activity[2],
                'details': activity[3],
                'performed_at': activity[4].isoformat() if activity[4] else None,
                'key_name': activity[5]
            })
        
        cursor.close()
        
        return jsonify({
            'success': True,
            'data': activity_list
        })
        
    except Exception as e:
        print(f"Get activity error: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error', 'data': []}), 500

@app.route('/api/stats', methods=['GET'])
@login_required
def get_stats():
    """Lấy thống kê"""
    try:
        conn = get_db()
        if conn is None:
            return jsonify({
                'success': True,
                'data': {
                    'total_keys': 0,
                    'active_keys': 0,
                    'locked_keys': 0,
                    'total_resets': 0,
                    'recent_activity': 0
                }
            })
        
        cursor = conn.cursor()
        
        # Thống kê cơ bản
        cursor.execute("""
            SELECT 
                COUNT(*) as total_keys,
                COUNT(CASE WHEN status = 'active' THEN 1 END) as active_keys,
                COUNT(CASE WHEN status = 'locked' THEN 1 END) as locked_keys,
                COALESCE(COUNT(last_reset_at), 0) as total_resets
            FROM api_keys
        """)
        
        stats = cursor.fetchone()
        
        # Hoạt động gần đây
        cursor.execute("""
            SELECT COUNT(*) as recent_activity
            FROM activity_logs 
            WHERE performed_at > NOW() - INTERVAL '24 hours'
        """)
        
        recent = cursor.fetchone()
        
        cursor.close()
        
        return jsonify({
            'success': True,
            'data': {
                'total_keys': stats[0] or 0,
                'active_keys': stats[1] or 0,
                'locked_keys': stats[2] or 0,
                'total_resets': stats[3] or 0,
                'recent_activity': recent[0] or 0
            }
        })
        
    except Exception as e:
        print(f"Get stats error: {str(e)}")
        return jsonify({
            'success': True,
            'data': {
                'total_keys': 0,
                'active_keys': 0,
                'locked_keys': 0,
                'total_resets': 0,
                'recent_activity': 0
            }
        })

@app.route('/api/validate', methods=['GET'])
def validate_key():
    """Kiểm tra key hợp lệ (public endpoint)"""
    try:
        conn = get_db()
        if conn is None:
            return jsonify({'success': False, 'error': 'Database không khả dụng'}), 503
        
        key = request.args.get('key')
        
        if not key:
            return jsonify({'success': False, 'error': 'Thiếu tham số key'}), 400
        
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT key_name, status, created_at, last_reset_at
            FROM api_keys 
            WHERE server_key = %s OR api_key = %s
        """, (key, key))
        
        key_data = cursor.fetchone()
        cursor.close()
        
        if not key_data:
            return jsonify({'success': False, 'error': 'Key không tồn tại'}), 404
        
        if key_data[1] != 'active':
            return jsonify({
                'success': False, 
                'error': f'Key đã bị {key_data[1]}'
            }), 403
        
        return jsonify({
            'success': True,
            'data': {
                'key_name': key_data[0],
                'status': key_data[1],
                'created_at': key_data[2].isoformat() if key_data[2] else None,
                'last_reset_at': key_data[3].isoformat() if key_data[3] else None
            }
        })
        
    except Exception as e:
        print(f"Validate key error: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

# ==================== Health Check ====================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        db_status, db_message = check_db_connection()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': {
                'connected': db_status,
                'message': db_message
            },
            'service': 'Admin Panel API',
            'version': '1.0.1',
            'endpoints': {
                'api': 'available',
                'frontend': 'available'
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'degraded',
            'timestamp': datetime.now().isoformat(),
            'error': str(e),
            'service': 'Admin Panel API'
        }), 500

# ==================== Static Files ====================

@app.route('/style.css')
def serve_css():
    return app.send_static_file('style.css')

@app.route('/script.js')
def serve_js():
    return app.send_static_file('script.js')

# ==================== Error Handlers ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500

# ==================== Application Startup ====================

def initialize_app():
    """Khởi tạo ứng dụng sau khi startup"""
    print("🚀 Đang khởi động Admin Panel...")
    print(f"📁 Environment: {app.config.get('ENVIRONMENT', 'development')}")
    
    # Khởi tạo database (non-blocking)
    try:
        init_database()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"⚠️  Database initialization warning: {e}")
        print("Ứng dụng vẫn sẽ chạy nhưng có thể có giới hạn chức năng")

# ==================== Run App ====================

if __name__ == '__main__':
    # Khởi tạo ứng dụng
    initialize_app()
    
    port = int(os.environ.get('PORT', 5000))
    print(f"🌐 Server sẽ chạy trên port: {port}")
    
    # Chỉ chạy debug mode trong development
    debug_mode = os.environ.get('FLASK_ENV') != 'production'
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
else:
    # Khi chạy với gunicorn, khởi tạo sau khi import
    import threading
    import time
    
    def delayed_init():
        """Khởi tạo database sau 2 giây để đảm bảo app đã sẵn sàng"""
        time.sleep(2)
        initialize_app()
    
    # Chạy initialization trong thread riêng
    init_thread = threading.Thread(target=delayed_init, daemon=True)
    init_thread.start()
