import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
from config import Config

def generate_token(username):
    """Tạo JWT token"""
    payload = {
        'username': username,
        'role': 'admin',
        'exp': datetime.utcnow() + timedelta(hours=Config.JWT_EXPIRES_HOURS),
        'iat': datetime.utcnow()
    }
    
    token = jwt.encode(payload, Config.JWT_SECRET, algorithm='HS256')
    return token

def verify_token(token):
    """Xác thực JWT token"""
    try:
        payload = jwt.decode(token, Config.JWT_SECRET, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None  # Token hết hạn
    except jwt.InvalidTokenError:
        return None  # Token không hợp lệ
    except Exception as e:
        print(f"Token verification error: {str(e)}")
        return None

def login_required(f):
    """Decorator yêu cầu đăng nhập"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        
        # Lấy token từ Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        # Hoặc từ cookie
        if not token:
            token = request.cookies.get('token')
        
        if not token:
            return jsonify({
                'success': False,
                'error': 'Token is missing'
            }), 401
        
        # Xác thực token
        payload = verify_token(token)
        if not payload:
            return jsonify({
                'success': False,
                'error': 'Invalid or expired token'
            }), 401
        
        # Gán thông tin user vào request
        request.user = payload
        return f(*args, **kwargs)
    
    return decorated_function
