from database import init_database, get_db_connection
import secrets

def create_sample_data():
    """Tạo dữ liệu mẫu"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Tạo 3 keys mẫu
    sample_keys = [
        ('Production Server', 'Server sản xuất chính'),
        ('Staging Server', 'Môi trường staging'),
        ('Development', 'Môi trường phát triển')
    ]
    
    for key_name, notes in sample_keys:
        server_key = f"sk_{secrets.token_hex(24)}"
        api_key = f"api_{secrets.token_hex(32)}"
        
        cur.execute("""
            INSERT INTO api_keys (key_name, server_key, api_key, notes, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (key_name, server_key, api_key, notes, 'active'))
        
        # Ghi log
        cur.execute("""
            INSERT INTO activity_logs (key_id, action, details)
            VALUES (currval('api_keys_id_seq'), 'CREATE', %s)
        """, (f'Tạo key mẫu: {key_name}',))
    
    conn.commit()
    cur.close()
    conn.close()
    
    print("✅ Dữ liệu mẫu đã được tạo")

if __name__ == '__main__':
    init_database()
    create_sample_data()
