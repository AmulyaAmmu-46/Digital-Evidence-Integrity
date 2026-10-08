import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    APP_ENV = os.environ.get('APP_ENV', 'development').lower()
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if SECRET_KEY in ('default-dev-key', 'super-secret-academic-key-change-in-prod', 'default_secret_key_change_me') or (SECRET_KEY and SECRET_KEY.startswith('REPLACE_ME')):
        SECRET_KEY = None
    if not SECRET_KEY:
        if APP_ENV == 'production':
            raise RuntimeError('SECRET_KEY must be configured in production.')
        SECRET_KEY = os.urandom(32)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI', 'sqlite:///' + os.path.join(basedir, 'forensics.db'))
    if APP_ENV == 'production' and (len(SECRET_KEY) < 32 or SQLALCHEMY_DATABASE_URI.startswith(('sqlite:', 'REPLACE_ME'))):
        raise RuntimeError('Production requires a strong SECRET_KEY and a configured production database URI.')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(basedir, 'uploads'))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = APP_ENV == 'production'
    # 50 MB max upload size
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 50 * 1024 * 1024))
