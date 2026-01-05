import secrets
from database import get_db, init_database

def create_sample_data():
    """Tạo dữ liệu mẫu"""
    conn = None
    cursor = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Đếm xem đã có dữ liệu chưa
        cursor.execute("SELECT COUNT(*) FROM api_keys")
        count = cursor.fetchone()[0]
        
        if count > 0:
            print("⚠️  Database đã có dữ liệu, bỏ qua tạo dữ liệu mẫu")
            return
        
        # Tạo 3 keys mẫu
        sample_keys = [
            ('Production Server', 'Server sản xuất chính'),
            ('Staging Server', 'Môi trường staging'),
            ('Development', 'Môi trường phát triển')
        ]
        
        for key_name, notes in sample_keys:
            server_key = f"sk_{secrets.token_hex(24)}"
            api_key = f"api_{secrets.token_hex(32)}"
            
            cursor.execute("""
                INSERT INTO api_keys (key_name, server_key, api_key, notes, status)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (key_name, server_key, api_key, notes, 'active'))
            
            new_id = cursor.fetchone()[0]
            
            # Ghi log
            cursor.execute("""
                INSERT INTO activity_logs (key_id, action, details)
                VALUES (%s, %s, %s)
            """, (new_id, 'CREATE', f'Tạo key mẫu: {key_name}'))
        
        conn.commit()
        print("✅ Dữ liệu mẫu đã được tạo")
        
    except Exception as e:
        print(f"❌ Lỗi khi tạo dữ liệu mẫu: {e}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()

if __name__ == '__main__':
    print("🔄 Đang khởi tạo database...")
    init_database()
    create_sample_data()
    print("✅ Khởi tạo database hoàn tất!")
