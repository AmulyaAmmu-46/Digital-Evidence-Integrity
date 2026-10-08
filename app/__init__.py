from flask import Flask, render_template, request, g
from app.config import Config
from app.extensions import db, migrate, login_manager, bcrypt, csrf
import logging
import os
from datetime import datetime
from sqlalchemy import event
from sqlalchemy.engine import Engine


@event.listens_for(Engine, 'connect')
def enable_sqlite_foreign_keys(connection, connection_record):
    if connection.__class__.__module__.startswith('sqlite3'):
        cursor = connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)

    # Setup Logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.cases import cases_bp
    from app.routes.evidence import evidence_bp
    from app.routes.audit import audit_bp
    from app.routes.users import users_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(cases_bp, url_prefix='/cases')
    app.register_blueprint(evidence_bp, url_prefix='/evidence')
    app.register_blueprint(audit_bp, url_prefix='/audit')
    app.register_blueprint(users_bp, url_prefix='/users')

    @app.route('/health', methods=['GET'])
    def health_check():
        return {'status': 'ok'}, 200

    # Register error handlers
    register_error_handlers(app)
    
    # User loader
    from app.models.user import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.filter_by(id=user_id, is_active=True).first()

    @app.before_request
    def before_request():
        from app.services.audit_service import log_audit_event
        # We can capture the request here if needed, but usually we do it explicitly in routes.
        pass

    return app

def register_error_handlers(app):
    @app.errorhandler(400)
    def bad_request_error(error):
        return render_template('errors/http_error.html', status_code=400, message='The request could not be processed.'), 400

    @app.errorhandler(401)
    def unauthorized_error(error):
        return render_template('errors/http_error.html', status_code=401, message='Authentication is required.'), 401

    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html', error=error), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html', error=error), 404

    @app.errorhandler(413)
    def too_large_error(error):
        return render_template('errors/http_error.html', status_code=413, message='The uploaded file exceeds the allowed size.'), 413

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/http_error.html', status_code=500, message='An unexpected error occurred.'), 500
