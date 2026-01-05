import psycopg2
from psycopg2.extras import RealDictCursor
from config import Config
import os

def get_db_connection():
    """Kết nối đến PostgreSQL database"""
    try:
        conn = psycopg2.connect(
            Config.DATABASE_URL,
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        print(f"❌ Lỗi kết nối database: {e}")
        raise

def init_database():
    """Khởi tạo database tables"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Tạo bảng api_keys
        cur.execute("""
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
        cur.execute("""
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
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_keys_status 
            ON api_keys(status)
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_keys_created 
            ON api_keys(created_at DESC)
        """)
        
        conn.commit()
        print("✅ Database tables đã được khởi tạo")
        
    except Exception as e:
        print(f"❌ Lỗi khi khởi tạo database: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            cur.close()
            conn.close()
