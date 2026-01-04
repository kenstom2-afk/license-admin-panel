Flask==2.3.3
Flask-CORS==4.0.0
cryptography==41.0.7
argon2-cffi==23.1.0
# THAY THẾ TOÀN BỘ PHẦN CUỐI:

if __name__ == '__main__':
    # Chạy với Render
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
