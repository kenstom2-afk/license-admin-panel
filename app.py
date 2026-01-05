import os
import json
import uuid
import re
import csv
import io
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, ForeignKey, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import argon2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# ============== CONFIGURATION ==============
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production-12345')

# Get database URL from Render environment
DATABASE_URL = os.environ.get('DATABASE_URL')

# Fix for Render PostgreSQL URL format
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Fallback to SQLite for local development
if not DATABASE_URL:
    DATABASE_URL = 'sqlite:///licenses.db'

# Create database engine
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Initialize Argon2
argon2_hasher = argon2.PasswordHasher()

# ============== DATABASE MODELS ==============
class AdminUser(Base):
    __tablename__ = 'admin_users'
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class APIKey(Base):
    __tablename__ = 'api_keys'
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    permissions = Column(String(50), default='all')
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

class License(Base):
    __tablename__ = 'licenses'
    
    id = Column(Integer, primary_key=True, index=True)
    license_key = Column(String(100), unique=True, nullable=False, index=True)
    hwid = Column(String(200), nullable=True, index=True)
    status = Column(String(20), default='active', index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    expires_at = Column(DateTime, nullable=True, index=True)
    last_check = Column(DateTime, nullable=True)
    device_info = Column(Text, nullable=True)
    note = Column(Text, nullable=True)
    is_locked = Column(Boolean, default=False, index=True)
    lock_reason = Column(String(200), nullable=True)
    key_type = Column(String(20), default='auto', index=True)
    prefix = Column(String(20), default='LIC')
    format_type = Column(String(20), default='standard')
    allow_multiple_devices = Column(Boolean, default=False)
    auto_activate = Column(Boolean, default=True)

class LicenseActivation(Base):
    __tablename__ = 'license_activations'
    
    id = Column(Integer, primary_key=True, index=True)
    license_key = Column(String(100), nullable=False, index=True)
    hwid = Column(String(200), nullable=False, index=True)
    device_info = Column(Text, nullable=True)
    activated_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    
    # Composite unique constraint
    __table_args__ = (ForeignKeyConstraint(['license_key'], ['licenses.license_key']),)

# Create all tables
Base.metadata.create_all(bind=engine)

# ============== HELPER FUNCTIONS ==============
def get_db_session():
    """Get database session"""
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()

def validate_api_key():
    """Validate API key from request headers"""
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        return False, "No API key provided"
    
    db = get_db_session()
    try:
        key_record = db.query(APIKey).filter(
            APIKey.key == api_key,
            APIKey.is_active == True
        ).first()
        
        if key_record:
            # Update last used timestamp
            key_record.last_used = datetime.utcnow()
            db.commit()
            return True, "Valid API key"
        return False, "Invalid or inactive API key"
    except Exception as e:
        return False, f"Error validating API key: {str(e)}"
    finally:
        db.close()

def generate_license_key(prefix="LIC", format_type="standard"):
    """Generate license key with different formats"""
    if format_type == "compact":
        # LIC-XXXXXXXXXXXX
        return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"
    elif format_type == "extended":
        # LIC-XXXX-XXXX-XXXX-XXXX
        uuid_str = uuid.uuid4().hex.upper()
        return f"{prefix}-{uuid_str[:4]}-{uuid_str[4:8]}-{uuid_str[8:12]}-{uuid_str[12:16]}"
    else:
        # Standard: LIC-XXXX-XXXX-XXXX
        uuid_str = uuid.uuid4().hex.upper()
        return f"{prefix}-{uuid_str[:4]}-{uuid_str[4:8]}-{uuid_str[8:12]}"

def validate_custom_key_format(key):
    """Validate custom license key format"""
    if len(key) < 8:
        return False, "Key must be at least 8 characters"
    
    if not re.match(r'^[A-Z0-9-]+$', key):
        return False, "Only uppercase letters, numbers, and dashes allowed"
    
    # Check if key already exists
    db = get_db_session()
    try:
        existing = db.query(License).filter(License.license_key == key.upper()).first()
        if existing:
            return False, "This key already exists"
        return True, "Valid key format"
    finally:
        db.close()

def get_license_status(license):
    """Determine license status"""
    if license.is_locked:
        return 'locked'
    
    if license.status == 'revoked':
        return 'revoked'
    
    if license.expires_at and license.expires_at < datetime.utcnow():
        return 'expired'
    
    return license.status

# ============== INITIALIZE DATABASE ==============
def initialize_database():
    """Initialize database with default admin user and API key"""
    print("🔧 Initializing database...")
    db = get_db_session()
    try:
        # Check if admin user exists
        admin_exists = db.query(AdminUser).filter(AdminUser.username == 'admin').first()
        if not admin_exists:
            password_hash = argon2_hasher.hash("admin123")
            admin_user = AdminUser(
                username='admin',
                password_hash=password_hash
            )
            db.add(admin_user)
            print("✅ Created default admin user: admin / admin123")
        
        # Check if active API key exists
        api_key_exists = db.query(APIKey).filter(APIKey.is_active == True).first()
        if not api_key_exists:
            default_api_key = f"sk_{uuid.uuid4().hex[:32]}"
            api_key = APIKey(
                key=default_api_key,
                name="Default API Key",
                permissions='all',
                is_active=True
            )
            db.add(api_key)
            print(f"✅ Created default API key: {default_api_key[:12]}...")
        
        db.commit()
        print("✅ Database initialization complete!")
    except Exception as e:
        db.rollback()
        print(f"❌ Error initializing database: {e}")
    finally:
        db.close()

# Initialize on startup
initialize_database()

# ============== ROUTES ==============
@app.route('/')
def index():
    """Serve admin panel"""
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
                    <p><strong>Backend API:</strong> Active</p>
                    <p><strong>Database:</strong> PostgreSQL</p>
                    <p><a href="/admin" style="color: #00bbf9;">Go to Admin Panel</a></p>
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
    db = get_db_session()
    try:
        # Get table counts
        admin_count = db.query(AdminUser).count()
        api_key_count = db.query(APIKey).filter(APIKey.is_active == True).count()
        license_count = db.query(License).count()
        activation_count = db.query(LicenseActivation).count()
        
        # Get recent API key info
        api_key = db.query(APIKey).filter(APIKey.is_active == True).order_by(APIKey.created_at.desc()).first()
        api_key_info = None
        if api_key:
            api_key_info = {
                'name': api_key.name,
                'key_masked': api_key.key[:8] + '...' + api_key.key[-4:],
                'last_used': api_key.last_used.isoformat() if api_key.last_used else None
            }
        
        # Database info
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        return jsonify({
            'status': 'online',
            'version': '2.0.0',
            'database': 'PostgreSQL',
            'database_tables': tables,
            'counts': {
                'admin_users': admin_count,
                'api_keys': api_key_count,
                'licenses': license_count,
                'license_activations': activation_count
            },
            'api_key_info': api_key_info,
            'message': 'LicenseMaster Pro with PostgreSQL is running correctly'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Database error: {str(e)}'
        }), 500
    finally:
        db.close()

@app.route('/api/admin/setup', methods=['POST'])
def setup_system():
    """Setup system endpoint"""
    data = request.json or {}
    action = data.get('action', 'create_key')
    
    db = get_db_session()
    try:
        if action == 'create_key':
            name = data.get('name', 'Auto-generated Key')
            new_api_key = f"sk_{uuid.uuid4().hex[:32]}"
            
            api_key = APIKey(
                key=new_api_key,
                name=name,
                permissions='all',
                is_active=True
            )
            db.add(api_key)
            db.commit()
            
            return jsonify({
                'success': True,
                'api_key': new_api_key,
                'name': name,
                'message': 'New API key created successfully'
            })
        
        elif action == 'reset_admin':
            password_hash = argon2_hasher.hash("admin123")
            
            # Update or create admin user
            admin_user = db.query(AdminUser).filter(AdminUser.username == 'admin').first()
            if admin_user:
                admin_user.password_hash = password_hash
            else:
                admin_user = AdminUser(username='admin', password_hash=password_hash)
                db.add(admin_user)
            
            db.commit()
            
            return jsonify({
                'success': True,
                'message': 'Admin password reset to: admin123'
            })
        
        return jsonify({'success': False, 'message': 'Invalid action'}), 400
        
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
    finally:
        db.close()

# ============== ADMIN API ==============
@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    """Login endpoint"""
    data = request.json
    if not data:
        return jsonify({'success': False, 'message': 'No data received'}), 400
    
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'}), 400
    
    db = get_db_session()
    try:
        user = db.query(AdminUser).filter(AdminUser.username == username).first()
        if user:
            try:
                if argon2_hasher.verify(user.password_hash, password):
                    # Get or create API key
                    api_key = db.query(APIKey).filter(APIKey.is_active == True).first()
                    if not api_key:
                        api_key = APIKey(
                            key=f"sk_{uuid.uuid4().hex[:32]}",
                            name="Auto-generated for login",
                            permissions='all',
                            is_active=True
                        )
                        db.add(api_key)
                        db.commit()
                    
                    return jsonify({
                        'success': True,
                        'message': 'Login successful',
                        'username': username,
                        'api_key': api_key.key,
                        'api_key_masked': api_key.key[:8] + '...' + api_key.key[-4:]
                    })
            except:
                pass
        
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Login error: {str(e)}'}), 500
    finally:
        db.close()

@app.route('/api/admin/licenses', methods=['GET'])
def get_all_licenses():
    """Get all licenses"""
    valid, message = validate_api_key()
    if not valid:
        return jsonify({'error': message}), 401
    
    db = get_db_session()
    try:
        licenses = db.query(License).order_by(License.created_at.desc()).all()
        
        licenses_list = []
        for license in licenses:
            license_dict = {
                'id': license.id,
                'license_key': license.license_key,
                'hwid': license.hwid,
                'status': license.status,
                'actual_status': get_license_status(license),
                'created_at': license.created_at.isoformat() if license.created_at else None,
                'expires_at': license.expires_at.isoformat() if license.expires_at else None,
                'last_check': license.last_check.isoformat() if license.last_check else None,
                'device_info': license.device_info,
                'note': license.note,
                'is_locked': license.is_locked,
                'lock_reason': license.lock_reason,
                'key_type': license.key_type,
                'prefix': license.prefix,
                'format_type': license.format_type,
                'allow_multiple_devices': license.allow_multiple_devices,
                'auto_activate': license.auto_activate
            }
            licenses_list.append(license_dict)
        
        return jsonify({'success': True, 'licenses': licenses_list})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        db.close()

@app.route('/api/admin/licenses/create', methods=['POST'])
def create_license():
    """Create new license"""
    valid, message = validate_api_key()
    if not valid:
        return jsonify({'error': message}), 401
    
    data = request.json
    if not data:
        return jsonify({'success': False, 'error': 'No data received'}), 400
    
    # Get parameters
    try:
        days_valid = int(data.get('days_valid', 30))
    except (ValueError, TypeError):
        days_valid = 30
    
    # Validate range
    if days_valid < 1:
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
    
    db = get_db_session()
    try:
        if custom_key:
            # Validate custom key
            is_valid, msg = validate_custom_key_format(custom_key)
            if not is_valid:
                return jsonify({'success': False, 'error': f'Invalid custom key: {msg}'}), 400
            license_key = custom_key.upper()
            key_type = 'custom'
        else:
            # Generate auto key
            license_key = generate_license_key(prefix, format_type)
        
        expires_at = datetime.utcnow() + timedelta(days=days_valid)
        
        # Create license
        license = License(
            license_key=license_key,
            expires_at=expires_at,
            note=note,
            status='active',
            key_type=key_type,
            prefix=prefix,
            format_type=format_type,
            allow_multiple_devices=allow_multiple_devices,
            auto_activate=auto_activate
        )
        
        db.add(license)
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
        
    except IntegrityError:
        db.rollback()
        return jsonify({'success': False, 'error': 'License key already exists'}), 400
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        db.close()

@app.route('/api/admin/licenses/bulk', methods=['POST'])
def bulk_create_licenses():
    """Create multiple licenses"""
    valid, message = validate_api_key()
    if not valid:
        return jsonify({'error': message}), 401
    
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
    
    db = get_db_session()
    created_keys = []
    
    try:
        for i in range(count):
            # Generate key
            license_key = generate_license_key(prefix, format_type)
            expires_at = datetime.utcnow() + timedelta(days=days_valid)
            individual_note = f"{note} #{i+1}" if note else f"Bulk generated #{i+1}"
            
            # Create license
            license = License(
                license_key=license_key,
                expires_at=expires_at,
                note=individual_note,
                status='active',
                key_type='bulk',
                prefix=prefix,
                format_type=format_type,
                allow_multiple_devices=allow_multiple_devices
            )
            
            db.add(license)
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
    finally:
        db.close()

@app.route('/api/admin/licenses/reset', methods=['POST'])
def reset_license():
    """Reset license (clear HWID)"""
    valid, message = validate_api_key()
    if not valid:
        return jsonify({'error': message}), 401
    
    data = request.json
    if not data:
        return jsonify({'success': False, 'error': 'No data received'}), 400
    
    license_key = data.get('license_key')
    if not license_key:
        return jsonify({'success': False, 'error': 'License key required'}), 400
    
    db = get_db_session()
    try:
        license = db.query(License).filter(License.license_key == license_key).first()
        if not license:
            return jsonify({'success': False, 'error': 'License not found'}), 404
        
        # Reset license
        license.hwid = None
        license.device_info = None
        license.last_check = None
        license.is_locked = False
        license.lock_reason = None
        license.status = 'active'
        
        # Delete activations
        db.query(LicenseActivation).filter(LicenseActivation.license_key == license_key).delete()
        
        db.commit()
        
        return jsonify({
            'success': True,
            'message': 'License reset successfully'
        })
        
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        db.close()

@app.route('/api/admin/licenses/lock', methods=['POST'])
def lock_license():
    """Lock license"""
    valid, message = validate_api_key()
    if not valid:
        return jsonify({'error': message}), 401
    
    data = request.json
    if not data:
        return jsonify({'success': False, 'error': 'No data received'}), 400
    
    license_key = data.get('license_key')
    reason = data.get('reason', 'Admin lock')
    
    db = get_db_session()
    try:
        license = db.query(License).filter(License.license_key == license_key).first()
        if not license:
            return jsonify({'success': False, 'error': 'License not found'}), 404
        
        license.is_locked = True
        license.lock_reason = reason
        license.status = 'locked'
        
        db.commit()
        
        return jsonify({
            'success': True,
            'message': 'License locked successfully'
        })
        
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        db.close()

@app.route('/api/admin/licenses/unlock', methods=['POST'])
def unlock_license():
    """Unlock license"""
    valid, message = validate_api_key()
    if not valid:
        return jsonify({'error': message}), 401
    
    data = request.json
    if not data:
        return jsonify({'success': False, 'error': 'No data received'}), 400
    
    license_key = data.get('license_key')
    
    db = get_db_session()
    try:
        license = db.query(License).filter(License.license_key == license_key).first()
        if not license:
            return jsonify({'success': False, 'error': 'License not found'}), 404
        
        license.is_locked = False
        license.lock_reason = None
        license.status = 'active'
        
        db.commit()
        
        return jsonify({
            'success': True,
            'message': 'License unlocked successfully'
        })
        
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        db.close()

@app.route('/api/admin/licenses/delete', methods=['POST'])
def delete_license():
    """Delete license"""
    valid, message = validate_api_key()
    if not valid:
        return jsonify({'error': message}), 401
    
    data = request.json
    if not data:
        return jsonify({'success': False, 'error': 'No data received'}), 400
    
    license_key = data.get('license_key')
    
    db = get_db_session()
    try:
        # Delete activations first
        db.query(LicenseActivation).filter(LicenseActivation.license_key == license_key).delete()
        
        # Delete license
        result = db.query(License).filter(License.license_key == license_key).delete()
        
        if result == 0:
            return jsonify({'success': False, 'error': 'License not found'}), 404
        
        db.commit()
        
        return jsonify({
            'success': True,
            'message': 'License deleted successfully'
        })
        
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        db.close()

@app.route('/api/admin/licenses/export', methods=['GET'])
def export_licenses():
    """Export licenses to CSV"""
    valid, message = validate_api_key()
    if not valid:
        return jsonify({'error': message}), 401
    
    db = get_db_session()
    try:
        licenses = db.query(License).order_by(License.created_at.desc()).all()
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'License Key', 'HWID', 'Status', 'Actual Status', 'Created At', 'Expires At',
            'Key Type', 'Note', 'Is Locked', 'Lock Reason', 'Prefix', 'Format Type',
            'Allow Multiple Devices', 'Auto Activate'
        ])
        
        # Write data
        for license in licenses:
            actual_status = get_license_status(license)
            writer.writerow([
                license.license_key,
                license.hwid or '',
                license.status,
                actual_status,
                license.created_at.isoformat() if license.created_at else '',
                license.expires_at.isoformat() if license.expires_at else '',
                license.key_type,
                license.note or '',
                'Yes' if license.is_locked else 'No',
                license.lock_reason or '',
                license.prefix,
                license.format_type,
                'Yes' if license.allow_multiple_devices else 'No',
                'Yes' if license.auto_activate else 'No'
            ])
        
        csv_content = output.getvalue()
        
        return jsonify({
            'success': True,
            'csv_content': csv_content,
            'count': len(licenses),
            'message': f'Exported {len(licenses)} licenses'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        db.close()

# ============== CLIENT API ==============
@app.route('/api/client/validate', methods=['POST'])
def validate_license():
    """Validate license for client"""
    data = request.json
    if not data:
        return jsonify({'valid': False, 'message': 'No data received'}), 400
    
    license_key = data.get('license_key')
    hwid = data.get('hwid')
    device_info = data.get('device_info', '')
    
    if not license_key or not hwid:
        return jsonify({'valid': False, 'message': 'License key and HWID are required'}), 400
    
    db = get_db_session()
    try:
        license = db.query(License).filter(License.license_key == license_key).first()
        if not license:
            return jsonify({'valid': False, 'message': 'Invalid license key'})
        
        # Check if locked
        if license.is_locked:
            return jsonify({
                'valid': False,
                'message': f'License is locked: {license.lock_reason or "Unknown reason"}'
            })
        
        # Check expiration
        if license.expires_at and license.expires_at < datetime.utcnow():
            return jsonify({'valid': False, 'message': 'License has expired'})
        
        # Multiple devices handling
        if license.allow_multiple_devices:
            # Check if already activated for this HWID
            activation = db.query(LicenseActivation).filter(
                LicenseActivation.license_key == license_key,
                LicenseActivation.hwid == hwid
            ).first()
            
            if not activation:
                # New activation
                activation = LicenseActivation(
                    license_key=license_key,
                    hwid=hwid,
                    device_info=device_info
                )
                db.add(activation)
                is_first_activation = True
            else:
                # Update last used
                activation.last_used = datetime.utcnow()
                is_first_activation = False
            
            # Update license
            license.hwid = hwid  # Keep for backward compatibility
            license.device_info = device_info
            license.last_check = datetime.utcnow()
            
            # Count activations
            activation_count = db.query(LicenseActivation).filter(
                LicenseActivation.license_key == license_key
            ).count()
            
            db.commit()
            
            return jsonify({
                'valid': True,
                'message': f'License is valid (Device {activation_count})',
                'expires_at': license.expires_at.isoformat() if license.expires_at else None,
                'device_count': activation_count,
                'first_activation': is_first_activation
            })
        
        else:
            # Single device mode
            if not license.hwid:
                # First activation
                license.hwid = hwid
                license.device_info = device_info
                license.last_check = datetime.utcnow()
                
                # Create activation record
                activation = LicenseActivation(
                    license_key=license_key,
                    hwid=hwid,
                    device_info=device_info
                )
                db.add(activation)
                
                db.commit()
                
                return jsonify({
                    'valid': True,
                    'message': 'License activated successfully',
                    'expires_at': license.expires_at.isoformat() if license.expires_at else None,
                    'first_activation': True
                })
            
            # Check HWID match
            if license.hwid != hwid:
                return jsonify({
                    'valid': False,
                    'message': 'HWID mismatch. This license is bound to another device.'
                })
            
            # Update last check
            license.last_check = datetime.utcnow()
            
            # Update activation last used
            activation = db.query(LicenseActivation).filter(
                LicenseActivation.license_key == license_key,
                LicenseActivation.hwid == hwid
            ).first()
            if activation:
                activation.last_used = datetime.utcnow()
            
            db.commit()
            
            return jsonify({
                'valid': True,
                'message': 'License is valid',
                'expires_at': license.expires_at.isoformat() if license.expires_at else None,
                'first_activation': False
            })
        
    except Exception as e:
        db.rollback()
        return jsonify({'valid': False, 'message': f'Validation error: {str(e)}'}), 500
    finally:
        db.close()

@app.route('/api/client/check', methods=['POST'])
def check_license():
    """Check license status"""
    data = request.json
    if not data:
        return jsonify({'valid': False, 'message': 'No data received'}), 400
    
    license_key = data.get('license_key')
    hwid = data.get('hwid')
    
    if not license_key or not hwid:
        return jsonify({'valid': False, 'message': 'License key and HWID are required'}), 400
    
    db = get_db_session()
    try:
        license = db.query(License).filter(License.license_key == license_key).first()
        if not license:
            return jsonify({'valid': False, 'message': 'Invalid license key'})
        
        actual_status = get_license_status(license)
        
        # Check HWID match
        if license.allow_multiple_devices:
            activation = db.query(LicenseActivation).filter(
                LicenseActivation.license_key == license_key,
                LicenseActivation.hwid == hwid
            ).first()
            hwid_match = bool(activation)
        else:
            hwid_match = license.hwid == hwid
        
        return jsonify({
            'valid': hwid_match and actual_status == 'active',
            'status': actual_status,
            'is_locked': license.is_locked,
            'lock_reason': license.lock_reason,
            'expires_at': license.expires_at.isoformat() if license.expires_at else None,
            'hwid_match': hwid_match
        })
        
    except Exception as e:
        return jsonify({'valid': False, 'message': f'Check error: {str(e)}'}), 500
    finally:
        db.close()

# ============== API KEY MANAGEMENT ==============
@app.route('/api/admin/apikeys', methods=['GET'])
def get_api_keys():
    """Get all API keys"""
    valid, message = validate_api_key()
    if not valid:
        return jsonify({'error': message}), 401
    
    db = get_db_session()
    try:
        keys = db.query(APIKey).order_by(APIKey.created_at.desc()).all()
        
        keys_list = []
        for key in keys:
            key_dict = {
                'id': key.id,
                'key': key.key,
                'key_masked': key.key[:8] + '...' + key.key[-4:],
                'name': key.name,
                'permissions': key.permissions,
                'created_at': key.created_at.isoformat() if key.created_at else None,
                'last_used': key.last_used.isoformat() if key.last_used else None,
                'is_active': key.is_active
            }
            keys_list.append(key_dict)
        
        return jsonify({'success': True, 'api_keys': keys_list})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        db.close()

@app.route('/api/admin/apikeys/create', methods=['POST'])
def create_api_key():
    """Create new API key"""
    valid, message = validate_api_key()
    if not valid:
        return jsonify({'error': message}), 401
    
    data = request.json
    if not data:
        return jsonify({'success': False, 'error': 'No data received'}), 400
    
    name = data.get('name', 'New API Key')
    
    db = get_db_session()
    try:
        api_key = f"sk_{uuid.uuid4().hex[:32]}"
        
        key_record = APIKey(
            key=api_key,
            name=name,
            permissions='all',
            is_active=True
        )
        
        db.add(key_record)
        db.commit()
        
        return jsonify({
            'success': True,
            'api_key': api_key,
            'name': name,
            'message': 'API key created successfully'
        })
        
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        db.close()

# ============== STATISTICS ==============
@app.route('/api/admin/stats', methods=['GET'])
def get_stats():
    """Get system statistics"""
    valid, message = validate_api_key()
    if not valid:
        return jsonify({'error': message}), 401
    
    db = get_db_session()
    try:
        # Basic counts
        total_licenses = db.query(License).count()
        active_licenses = db.query(License).filter(
            License.status == 'active',
            License.is_locked == False
        ).count()
        locked_licenses = db.query(License).filter(License.is_locked == True).count()
        
        # Expired licenses
        expired_licenses = db.query(License).filter(
            License.expires_at < datetime.utcnow()
        ).count()
        
        # Key type distribution
        key_types = {}
        for key_type in db.query(License.key_type).distinct():
            if key_type[0]:
                count = db.query(License).filter(License.key_type == key_type[0]).count()
                key_types[key_type[0]] = count
        
        # Today's created licenses
        today = datetime.utcnow().date()
        today_created = db.query(License).filter(
            db.func.date(License.created_at) == today
        ).count()
        
        # Multiple devices licenses
        multi_device_licenses = db.query(License).filter(
            License.allow_multiple_devices == True
        ).count()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_licenses': total_licenses,
                'active_licenses': active_licenses,
                'locked_licenses': locked_licenses,
                'expired_licenses': expired_licenses,
                'key_types': key_types,
                'today_created': today_created,
                'multi_device_licenses': multi_device_licenses
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        db.close()

# ============== SEARCH LICENSES ==============
@app.route('/api/admin/licenses/search', methods=['POST'])
def search_licenses():
    """Search licenses"""
    valid, message = validate_api_key()
    if not valid:
        return jsonify({'error': message}), 401
    
    data = request.json
    if not data:
        return jsonify({'success': False, 'error': 'No data received'}), 400
    
    query = data.get('query', '')
    if not query:
        return jsonify({'success': False, 'error': 'Search query required'}), 400
    
    db = get_db_session()
    try:
        # Search in license_key, hwid, and note
        licenses = db.query(License).filter(
            (License.license_key.ilike(f'%{query}%')) |
            (License.hwid.ilike(f'%{query}%')) |
            (License.note.ilike(f'%{query}%'))
        ).order_by(License.created_at.desc()).all()
        
        licenses_list = []
        for license in licenses:
            license_dict = {
                'license_key': license.license_key,
                'hwid': license.hwid,
                'status': license.status,
                'actual_status': get_license_status(license),
                'created_at': license.created_at.isoformat() if license.created_at else None,
                'expires_at': license.expires_at.isoformat() if license.expires_at else None,
                'note': license.note,
                'is_locked': license.is_locked
            }
            licenses_list.append(license_dict)
        
        return jsonify({
            'success': True,
            'count': len(licenses_list),
            'licenses': licenses_list
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        db.close()

# ============== MAIN ENTRY POINT ==============
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
