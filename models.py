from database import get_db_connection
from datetime import datetime

class APIKey:
    @staticmethod
    def create(key_name, notes=''):
        """Tạo key mới"""
        import secrets
        server_key = f"sk_{secrets.token_hex(24)}"
        api_key = f"api_{secrets.token_hex(32)}"
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO api_keys (key_name, server_key, api_key, notes)
            VALUES (%s, %s, %s, %s)
            RETURNING *
        """, (key_name, server_key, api_key, notes))
        
        new_key = cur.fetchone()
        conn.commit()
        conn.close()
        
        return new_key
    
    @staticmethod
    def get_all(status=None, search=''):
        """Lấy tất cả keys"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        query = "SELECT * FROM api_keys WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = %s"
            params.append(status)
        
        if search:
            query += " AND (key_name ILIKE %s OR server_key ILIKE %s)"
            search_term = f"%{search}%"
            params.extend([search_term, search_term])
        
        query += " ORDER BY created_at DESC"
        cur.execute(query, params)
        
        keys = cur.fetchall()
        conn.close()
        
        return keys
    
    @staticmethod
    def get_by_id(key_id):
        """Lấy key theo ID"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM api_keys WHERE id = %s", (key_id,))
        key = cur.fetchone()
        conn.close()
        
        return key

class ActivityLog:
    @staticmethod
    def log(key_id, action, details, ip_address=None):
        """Ghi log hoạt động"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO activity_logs (key_id, action, details, ip_address)
            VALUES (%s, %s, %s, %s)
        """, (key_id, action, details, ip_address))
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_recent(limit=50):
        """Lấy log gần đây"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT al.*, ak.key_name 
            FROM activity_logs al
            LEFT JOIN api_keys ak ON al.key_id = ak.id
            ORDER BY al.performed_at DESC
            LIMIT %s
        """, (limit,))
        
        logs = cur.fetchall()
        conn.close()
        
        return logs
