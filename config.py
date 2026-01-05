import os
from dotenv import load_dotenv

# Tải .env file nếu có
load_dotenv()

class Config:
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Database - ƯU TIÊN BIẾN MÔI TRƯỜNG TRỰC TIẾP
    DATABASE_URL = os.environ.get('DATABASE_URL', '')
    
    # Admin Credentials
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
    
    # JWT
    JWT_SECRET = os.environ.get('JWT_SECRET', 'jwt-secret-key-change-me')
    JWT_EXPIRES_HOURS = int(os.environ.get('JWT_EXPIRES_HOURS', 24))
    
    # Environment
    ENVIRONMENT = os.environ.get('FLASK_ENV', 'development')
    
    # CORS
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')
