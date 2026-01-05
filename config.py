import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Database
    DATABASE_URL = os.environ.get('DATABASE_URL')
    
    # Admin Credentials
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
    
    # JWT
    JWT_SECRET = os.environ.get('JWT_SECRET') or 'jwt-secret-key-change-me'
    JWT_EXPIRES_HOURS = int(os.environ.get('JWT_EXPIRES_HOURS', 24))
    
    # Security
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
