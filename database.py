import psycopg
from psycopg import sql
from config import Config
import os

_connection = None

def get_db():
    """Kết nối đến PostgreSQL database"""
    global _connection
    
    if _connection is None or _connection.closed:
        try:
            # Parse DATABASE_URL
            db_url = Config.DATABASE_URL
            
            if not db_url:
                raise ValueError("DATABASE_URL không được cấu hình")
            
            # Kết nối với psycopg3
            _connection = psycopg.connect(
                db_url,
                autocommit=False
            )
            print("✅ Đã kết nối đến PostgreSQL database")
            
        except Exception as e:
            print(f"❌ Lỗi kết nối database: {e}")
            raise
    
    return _connection

def init_database():
    """Khởi tạo database tables"""
    conn = None
    try:
        conn = get_db()
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
        
    except Exception as e:
        print(f"❌ Lỗi khi khởi tạo database: {e}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()

def close_db():
    """Đóng kết nối database"""
    global _connection
    if _connection and not _connection.closed:
        _connection.close()
        print("Database connection closed")
