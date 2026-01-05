import psycopg
from config import Config
import os
import time

_connection = None
_db_initialized = False

def get_db():
    """Kết nối đến PostgreSQL database"""
    global _connection
    
    if _connection is None or _connection.closed:
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                # Parse DATABASE_URL
                db_url = Config.DATABASE_URL
                
                if not db_url:
                    # Thử lấy từ biến môi trường trực tiếp
                    db_url = os.environ.get('DATABASE_URL')
                    
                if not db_url:
                    print("⚠️  Cảnh báo: DATABASE_URL không được cấu hình")
                    print("Ứng dụng sẽ chạy ở chế độ không có database")
                    return None
                
                # Kết nối với psycopg3
                _connection = psycopg.connect(
                    db_url,
                    autocommit=False
                )
                print(f"✅ Đã kết nối đến PostgreSQL database (lần thử {attempt + 1})")
                break
                
            except Exception as e:
                print(f"❌ Lỗi kết nối database (lần thử {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    print(f"⏳ Thử lại sau {retry_delay} giây...")
                    time.sleep(retry_delay)
                else:
                    print("⚠️  Không thể kết nối database, ứng dụng sẽ chạy ở chế độ limited")
                    _connection = None
    
    return _connection

def init_database():
    """Khởi tạo database tables - CHỈ GỌI KHI CÓ KẾT NỐI"""
    global _db_initialized
    
    if _db_initialized:
        return
    
    conn = None
    cursor = None
    try:
        conn = get_db()
        if conn is None:
            print("⚠️  Không có kết nối database, bỏ qua khởi tạo tables")
            return
        
        cursor = conn.cursor()
        
        # Tạo bảng api_keys
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id SERIAL PRIMARY KEY,
                key_name VARCHAR(255) NOT NULL,
                server_key VARCHAR(512) UNIQUE NOT NULL,
                api_key VARCHAR(512) UNIQUE NOT NULL,
                status VARCHAR(50) DEFAULT 'active',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_reset_at TIMESTAMP
            )
        """)
        
        # Tạo bảng activity_logs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id SERIAL PRIMARY KEY,
                key_id INTEGER,
                action VARCHAR(100) NOT NULL,
                details TEXT,
                performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address VARCHAR(45)
            )
        """)
        
        # Tạo indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_keys_status 
            ON api_keys(status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_keys_created 
            ON api_keys(created_at DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_activity_logs_key_id 
            ON activity_logs(key_id)
        """)
        
        conn.commit()
        print("✅ Database tables đã được khởi tạo")
        _db_initialized = True
        
    except Exception as e:
        print(f"❌ Lỗi khi khởi tạo database: {e}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()

def close_db():
    """Đóng kết nối database"""
    global _connection, _db_initialized
    if _connection and not _connection.closed:
        _connection.close()
        _connection = None
        _db_initialized = False
        print("Database connection closed")

# Helper function để kiểm tra database connection
def check_db_connection():
    """Kiểm tra kết nối database"""
    try:
        conn = get_db()
        if conn is None:
            return False, "No database connection"
        
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        return True, "Database connected"
    except Exception as e:
        return False, str(e)
